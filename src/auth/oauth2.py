"""OAuth2 authentication client implementation."""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta

import httpx
from pydantic import BaseModel

from .base import AuthClient, Token
from ..config import settings


class OAuth2Config(BaseModel):
    """OAuth2 client configuration."""
    token_url: str
    client_id: str
    client_secret: str
    scope: Optional[str] = None
    grant_type: str = "client_credentials"


class OAuth2Client(AuthClient):
    """OAuth2 authentication client for INSEE and DGFIP APIs."""
    
    def __init__(self, service_name: str, config: OAuth2Config):
        super().__init__(service_name)
        self.config = config
        self._http_client = httpx.AsyncClient(timeout=30.0)
    
    async def authenticate(self) -> Token:
        """Perform OAuth2 client credentials authentication."""
        self.logger.info("oauth2_authenticating", token_url=self.config.token_url)
        
        data = {
            "grant_type": self.config.grant_type,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }
        
        if self.config.scope:
            data["scope"] = self.config.scope
        
        try:
            response = await self._http_client.post(
                self.config.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            
            token_data = response.json()
            
            # Calculate expiration time
            expires_in = token_data.get("expires_in", 3600)
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            token = Token(
                value=token_data["access_token"],
                expires_at=expires_at,
                token_type=token_data.get("token_type", "Bearer"),
                refresh_token=token_data.get("refresh_token")
            )
            
            self.logger.info("oauth2_authenticated", 
                           expires_in=expires_in,
                           has_refresh_token=bool(token.refresh_token))
            
            return token
            
        except httpx.HTTPError as e:
            self.logger.error("oauth2_authentication_failed", 
                            error=str(e),
                            status_code=getattr(e.response, "status_code", None))
            raise
    
    async def refresh(self) -> Token:
        """Refresh OAuth2 token using refresh token or re-authenticate."""
        if self._token and self._token.refresh_token:
            self.logger.info("oauth2_refreshing_with_refresh_token")
            
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self._token.refresh_token,
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
            }
            
            try:
                response = await self._http_client.post(
                    self.config.token_url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                response.raise_for_status()
                
                token_data = response.json()
                expires_in = token_data.get("expires_in", 3600)
                expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                
                return Token(
                    value=token_data["access_token"],
                    expires_at=expires_at,
                    token_type=token_data.get("token_type", "Bearer"),
                    refresh_token=token_data.get("refresh_token", self._token.refresh_token)
                )
                
            except httpx.HTTPError:
                self.logger.warning("oauth2_refresh_token_failed_reauthenticating")
                return await self.authenticate()
        else:
            # No refresh token, re-authenticate
            return await self.authenticate()
    
    async def close(self):
        """Close HTTP client."""
        await self._http_client.aclose()


# Factory functions for specific OAuth2 clients
def create_insee_oauth_client() -> OAuth2Client:
    """Create OAuth2 client for INSEE API."""
    config = OAuth2Config(
        token_url="https://portail-api.insee.fr/token",
        client_id=settings.insee_client_id,
        client_secret=settings.insee_client_secret,
        scope="default"
    )
    return OAuth2Client("insee", config)


def create_dgfip_oauth_client() -> Optional[OAuth2Client]:
    """Create OAuth2 client for DGFIP API if credentials are available."""
    if settings.dgfip_client_id and settings.dgfip_client_secret:
        config = OAuth2Config(
            token_url="https://api.dgfip.finances.gouv.fr/oauth/token",
            client_id=settings.dgfip_client_id,
            client_secret=settings.dgfip_client_secret
        )
        return OAuth2Client("dgfip", config)
    return None