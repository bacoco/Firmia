"""Base API client with resilience patterns."""

from typing import Optional, Dict, Any, Type, List
from abc import ABC, abstractmethod
import asyncio

import httpx
from pydantic import BaseModel
from structlog import get_logger

from ..auth import get_auth_manager
from ..cache import get_cache_manager
from ..resilience import circuit_breaker, retry_with_backoff, RetryConfig
from ..config import settings

logger = get_logger(__name__)


class APIError(Exception):
    """Base exception for API errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class RateLimitError(APIError):
    """Rate limit exceeded error."""
    pass


class AuthenticationError(APIError):
    """Authentication failed error."""
    pass


class BaseAPIClient(ABC):
    """Base client for all external API integrations."""
    
    # Override in subclasses
    BASE_URL: str = ""
    API_NAME: str = ""
    RATE_LIMIT: int = 100  # requests per minute
    REQUIRES_AUTH: bool = True
    AUTH_SERVICE: str = ""  # e.g., "insee", "inpi"
    
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self.logger = logger.bind(api=self.API_NAME)
        self.auth_manager = get_auth_manager() if self.REQUIRES_AUTH else None
        self.cache_manager = get_cache_manager()
    
    def get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=self.timeout,
                follow_redirects=True,
                http2=True
            )
        return self._client
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def get_headers(self) -> Dict[str, str]:
        """Get request headers including authentication."""
        headers = {
            "User-Agent": f"Firmia-MCP-Server/{settings.environment}",
            "Accept": "application/json"
        }
        
        if self.REQUIRES_AUTH and self.auth_manager:
            auth_headers = await self.auth_manager.get_headers(self.AUTH_SERVICE)
            headers.update(auth_headers)
            
            # Add any service-specific headers
            additional_headers = self.auth_manager.get_additional_headers(self.AUTH_SERVICE)
            headers.update(additional_headers)
        
        return headers
    
    async def check_rate_limit(self) -> None:
        """Check if rate limit allows request."""
        if not self.cache_manager:
            return
        
        allowed, remaining = await self.cache_manager.check_rate_limit(
            self.API_NAME.lower().replace(" ", "_"),
            settings.insee_client_id  # Use as client ID
        )
        
        if not allowed:
            self.logger.warning("rate_limit_exceeded", 
                              api=self.API_NAME,
                              retry_after=remaining)
            raise RateLimitError(
                f"Rate limit exceeded for {self.API_NAME}. Retry after {remaining} seconds.",
                status_code=429
            )
    
    @retry_with_backoff(config=RetryConfig(max_attempts=3))
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None
    ) -> httpx.Response:
        """Make HTTP request with retry logic."""
        # Check rate limit
        await self.check_rate_limit()
        
        # Get headers
        headers = await self.get_headers()
        if extra_headers:
            headers.update(extra_headers)
        
        # Make request
        client = self.get_client()
        
        self.logger.debug("api_request",
                        method=method,
                        endpoint=endpoint,
                        has_params=bool(params),
                        has_json=bool(json_data))
        
        try:
            response = await client.request(
                method=method,
                url=endpoint,
                params=params,
                json=json_data,
                headers=headers
            )
            
            # Log response
            self.logger.debug("api_response",
                            status_code=response.status_code,
                            content_length=len(response.content))
            
            # Handle common status codes
            if response.status_code == 401:
                # Invalidate token and retry
                if self.auth_manager:
                    await self.auth_manager.invalidate_token(self.AUTH_SERVICE)
                raise AuthenticationError(
                    f"Authentication failed for {self.API_NAME}",
                    status_code=401
                )
            
            elif response.status_code == 429:
                # Rate limit hit
                retry_after = response.headers.get("Retry-After", "60")
                raise RateLimitError(
                    f"Rate limit exceeded. Retry after {retry_after} seconds.",
                    status_code=429
                )
            
            # Raise for other errors
            response.raise_for_status()
            
            return response
            
        except httpx.HTTPError as e:
            self.logger.error("api_request_failed",
                            error=str(e),
                            status_code=getattr(e.response, "status_code", None))
            raise APIError(
                f"{self.API_NAME} request failed: {str(e)}",
                status_code=getattr(e.response, "status_code", None)
            )
    
    async def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> httpx.Response:
        """Make GET request."""
        return await self._make_request("GET", endpoint, params=params, **kwargs)
    
    async def post(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> httpx.Response:
        """Make POST request."""
        return await self._make_request("POST", endpoint, json_data=json_data, **kwargs)
    
    async def put(
        self,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> httpx.Response:
        """Make PUT request."""
        return await self._make_request("PUT", endpoint, json_data=json_data, **kwargs)
    
    async def delete(
        self,
        endpoint: str,
        **kwargs
    ) -> httpx.Response:
        """Make DELETE request."""
        return await self._make_request("DELETE", endpoint, **kwargs)
    
    def parse_response(
        self,
        response: httpx.Response,
        model_class: Optional[Type[BaseModel]] = None
    ) -> Any:
        """Parse API response."""
        try:
            data = response.json()
            
            if model_class:
                # Parse into Pydantic model
                if isinstance(data, list):
                    return [model_class(**item) for item in data]
                else:
                    return model_class(**data)
            
            return data
            
        except Exception as e:
            self.logger.error("response_parse_error",
                            error=str(e),
                            content_preview=response.text[:200])
            raise APIError(f"Failed to parse {self.API_NAME} response: {str(e)}")
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if API is healthy."""
        pass


class PaginatedAPIClient(BaseAPIClient):
    """Base client with pagination support."""
    
    async def get_all_pages(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        max_pages: Optional[int] = None,
        page_param: str = "page",
        per_page_param: str = "per_page",
        per_page: int = 100
    ) -> List[Any]:
        """Get all pages of paginated results."""
        if params is None:
            params = {}
        
        params[per_page_param] = per_page
        all_results = []
        page = 1
        
        while True:
            if max_pages and page > max_pages:
                break
            
            params[page_param] = page
            
            response = await self.get(endpoint, params=params)
            data = response.json()
            
            # Extract results (API-specific, override in subclass)
            results = self.extract_results_from_page(data)
            if not results:
                break
            
            all_results.extend(results)
            
            # Check if more pages
            if not self.has_more_pages(data, page):
                break
            
            page += 1
            
            # Small delay to be respectful
            await asyncio.sleep(0.1)
        
        return all_results
    
    def extract_results_from_page(self, page_data: Dict[str, Any]) -> List[Any]:
        """Extract results from page data. Override in subclass."""
        if "results" in page_data:
            return page_data["results"]
        elif "data" in page_data:
            return page_data["data"]
        elif isinstance(page_data, list):
            return page_data
        return []
    
    def has_more_pages(self, page_data: Dict[str, Any], current_page: int) -> bool:
        """Check if there are more pages. Override in subclass."""
        if "total_pages" in page_data:
            return current_page < page_data["total_pages"]
        elif "next" in page_data:
            return page_data["next"] is not None
        elif "has_more" in page_data:
            return page_data["has_more"]
        return False