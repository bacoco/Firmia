"""Main authentication manager orchestrating all auth mechanisms."""

from typing import Dict, Optional, Any
from functools import lru_cache
import asyncio

from structlog import get_logger

from .base import AuthClient
from .oauth2 import create_insee_oauth_client, create_dgfip_oauth_client
from .jwt import create_inpi_jwt_client, create_api_entreprise_jwt_client
from ..config import settings

logger = get_logger(__name__)


class AuthManager:
    """Manages authentication for all external APIs."""
    
    def __init__(self):
        self.clients: Dict[str, AuthClient] = {}
        self._initialized = False
        self._init_lock = asyncio.Lock()
        self.logger = logger.bind(component="auth_manager")
    
    async def initialize(self) -> None:
        """Initialize all authentication clients."""
        async with self._init_lock:
            if self._initialized:
                return
            
            self.logger.info("initializing_auth_clients")
            
            # Create OAuth2 clients
            self.clients["insee"] = create_insee_oauth_client()
            
            dgfip_client = create_dgfip_oauth_client()
            if dgfip_client:
                self.clients["dgfip"] = dgfip_client
            else:
                self.logger.warning("dgfip_client_not_configured")
            
            # Create JWT clients
            self.clients["inpi"] = create_inpi_jwt_client()
            self.clients["api_entreprise"] = create_api_entreprise_jwt_client()
            
            # Pre-authenticate clients that don't require immediate API calls
            # This helps with startup time and early error detection
            static_clients = ["api_entreprise"]  # Static token, no API call needed
            
            for client_name in static_clients:
                if client_name in self.clients:
                    try:
                        await self.clients[client_name].get_token()
                        self.logger.info("pre_authenticated_client", client=client_name)
                    except Exception as e:
                        self.logger.error("pre_authentication_failed", 
                                        client=client_name, 
                                        error=str(e))
            
            self._initialized = True
            self.logger.info("auth_clients_initialized", 
                           clients=list(self.clients.keys()))
    
    async def get_token(self, service: str) -> str:
        """Get valid token for a service."""
        if not self._initialized:
            await self.initialize()
        
        if service not in self.clients:
            raise ValueError(f"Unknown service: {service}")
        
        return await self.clients[service].get_token()
    
    async def get_headers(self, service: str) -> Dict[str, str]:
        """Get authentication headers for a service."""
        if not self._initialized:
            await self.initialize()
        
        if service not in self.clients:
            # Some APIs don't require authentication
            if service in ["recherche_entreprises", "bodacc", "rna", "rge"]:
                return {}
            raise ValueError(f"Unknown service: {service}")
        
        return await self.clients[service].get_headers_async()
    
    def get_additional_headers(self, service: str) -> Dict[str, str]:
        """Get additional service-specific headers."""
        if service == "api_entreprise":
            # API Entreprise requires additional headers
            return {
                "X-Recipient-Id": settings.insee_client_id,  # Using INSEE SIREN as recipient
                "X-Recipient-Object": "firmia-mcp-server",
                "X-Recipient-Context": "french-company-intelligence"
            }
        return {}
    
    async def invalidate_token(self, service: str) -> None:
        """Invalidate token for a service (e.g., after 401 response)."""
        if service in self.clients:
            self.clients[service].invalidate_token()
            self.logger.info("token_invalidated", service=service)
    
    async def close(self) -> None:
        """Close all HTTP clients."""
        self.logger.info("closing_auth_clients")
        
        tasks = []
        for client in self.clients.values():
            if hasattr(client, "close"):
                tasks.append(client.close())
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        self._initialized = False
        self.clients.clear()
    
    def get_service_status(self) -> Dict[str, Dict[str, Any]]:
        """Get authentication status for all services."""
        status = {}
        
        for service, client in self.clients.items():
            client_status = {
                "configured": True,
                "has_token": client._token is not None,
                "token_expired": client._token.is_expired if client._token else None,
                "expires_in": client._token.expires_in_seconds if client._token else None
            }
            status[service] = client_status
        
        # Add non-authenticated services
        for service in ["recherche_entreprises", "bodacc", "rna", "rge"]:
            status[service] = {
                "configured": True,
                "has_token": False,
                "token_expired": None,
                "expires_in": None,
                "note": "No authentication required"
            }
        
        return status


# Singleton instance
_auth_manager: Optional[AuthManager] = None


@lru_cache(maxsize=1)
def get_auth_manager() -> AuthManager:
    """Get the singleton AuthManager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager