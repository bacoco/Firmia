"""Base authentication classes and interfaces."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio

from pydantic import BaseModel
from structlog import get_logger

logger = get_logger(__name__)


class Token(BaseModel):
    """Authentication token with expiration tracking."""
    value: str
    expires_at: Optional[datetime] = None
    token_type: str = "Bearer"
    refresh_token: Optional[str] = None
    
    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() >= self.expires_at
    
    @property
    def expires_in_seconds(self) -> Optional[int]:
        """Get seconds until expiration."""
        if not self.expires_at:
            return None
        delta = self.expires_at - datetime.utcnow()
        return int(delta.total_seconds()) if delta.total_seconds() > 0 else 0


class AuthClient(ABC):
    """Base authentication client interface."""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self._token: Optional[Token] = None
        self._refresh_lock = asyncio.Lock()
        self.logger = logger.bind(service=service_name)
    
    @abstractmethod
    async def authenticate(self) -> Token:
        """Perform initial authentication."""
        pass
    
    @abstractmethod
    async def refresh(self) -> Token:
        """Refresh the authentication token."""
        pass
    
    async def get_token(self) -> str:
        """Get valid token, refreshing if necessary."""
        async with self._refresh_lock:
            # Check if we need to authenticate or refresh
            if not self._token:
                self.logger.info("performing_initial_authentication")
                self._token = await self.authenticate()
            elif self._token.is_expired:
                self.logger.info("token_expired_refreshing")
                try:
                    self._token = await self.refresh()
                except Exception as e:
                    self.logger.warning("refresh_failed_reauthenticating", error=str(e))
                    self._token = await self.authenticate()
            elif self._token.expires_in_seconds and self._token.expires_in_seconds < 300:
                # Proactively refresh if expiring in less than 5 minutes
                self.logger.info("token_expiring_soon_refreshing", 
                               expires_in=self._token.expires_in_seconds)
                try:
                    self._token = await self.refresh()
                except Exception:
                    # Don't fail if proactive refresh fails
                    pass
            
            return self._token.value
    
    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers synchronously (for sync contexts)."""
        if not self._token:
            raise RuntimeError("Token not available. Call get_token() first.")
        return {
            "Authorization": f"{self._token.token_type} {self._token.value}"
        }
    
    async def get_headers_async(self) -> Dict[str, str]:
        """Get authentication headers, ensuring token is valid."""
        token = await self.get_token()
        return {
            "Authorization": f"{self._token.token_type} {token}"
        }
    
    def invalidate_token(self) -> None:
        """Invalidate the current token."""
        self._token = None
        self.logger.info("token_invalidated")