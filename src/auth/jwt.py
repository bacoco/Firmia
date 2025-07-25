"""JWT authentication client implementation."""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import json
import base64

import httpx
from pydantic import BaseModel

from .base import AuthClient, Token
from ..config import settings


class JWTConfig(BaseModel):
    """JWT authentication configuration."""
    login_url: Optional[str] = None  # For INPI-style login
    username: Optional[str] = None
    password: Optional[str] = None
    static_token: Optional[str] = None  # For API Entreprise long-lived token
    token_lifetime: int = 86400  # Default 24 hours


class JWTClient(AuthClient):
    """JWT authentication client for INPI and API Entreprise."""
    
    def __init__(self, service_name: str, config: JWTConfig):
        super().__init__(service_name)
        self.config = config
        self._http_client = httpx.AsyncClient(timeout=30.0) if config.login_url else None
    
    def _decode_jwt_payload(self, token: str) -> Dict[str, Any]:
        """Decode JWT payload to extract expiration."""
        try:
            # JWT structure: header.payload.signature
            parts = token.split('.')
            if len(parts) != 3:
                return {}
            
            # Decode payload (add padding if necessary)
            payload = parts[1]
            payload += '=' * (4 - len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload)
            
            return json.loads(decoded)
        except Exception as e:
            self.logger.warning("jwt_decode_failed", error=str(e))
            return {}
    
    async def authenticate(self) -> Token:
        """Perform JWT authentication."""
        if self.config.static_token:
            # API Entreprise case - long-lived token
            self.logger.info("jwt_using_static_token")
            
            # Try to decode expiration from token
            payload = self._decode_jwt_payload(self.config.static_token)
            exp = payload.get("exp")
            
            if exp:
                expires_at = datetime.fromtimestamp(exp)
            else:
                # Assume 6 months validity if can't decode
                expires_at = datetime.utcnow() + timedelta(days=180)
            
            return Token(
                value=self.config.static_token,
                expires_at=expires_at,
                token_type="Bearer"
            )
        
        elif self.config.login_url and self.config.username and self.config.password:
            # INPI case - login to get JWT
            self.logger.info("jwt_authenticating", login_url=self.config.login_url)
            
            try:
                response = await self._http_client.post(
                    self.config.login_url,
                    json={
                        "username": self.config.username,
                        "password": self.config.password
                    }
                )
                response.raise_for_status()
                
                token_data = response.json()
                token_value = token_data.get("token")
                
                if not token_value:
                    raise ValueError("No token in response")
                
                # Try to extract expiration from JWT
                payload = self._decode_jwt_payload(token_value)
                exp = payload.get("exp")
                
                if exp:
                    expires_at = datetime.fromtimestamp(exp)
                else:
                    # Use configured lifetime
                    expires_at = datetime.utcnow() + timedelta(seconds=self.config.token_lifetime)
                
                self.logger.info("jwt_authenticated", expires_at=expires_at.isoformat())
                
                return Token(
                    value=token_value,
                    expires_at=expires_at,
                    token_type="Bearer"
                )
                
            except httpx.HTTPError as e:
                self.logger.error("jwt_authentication_failed", 
                                error=str(e),
                                status_code=getattr(e.response, "status_code", None))
                raise
        else:
            raise ValueError(f"Invalid JWT configuration for {self.service_name}")
    
    async def refresh(self) -> Token:
        """Refresh JWT token by re-authenticating."""
        # JWT typically doesn't have refresh tokens, so we re-authenticate
        return await self.authenticate()
    
    async def close(self):
        """Close HTTP client if exists."""
        if self._http_client:
            await self._http_client.aclose()


# Factory functions for specific JWT clients
def create_inpi_jwt_client() -> JWTClient:
    """Create JWT client for INPI RNE API."""
    config = JWTConfig(
        login_url="https://registre-national-entreprises.inpi.fr/api/sso/login",
        username=settings.inpi_username,
        password=settings.inpi_password,
        token_lifetime=86400  # 24 hours
    )
    return JWTClient("inpi", config)


def create_api_entreprise_jwt_client() -> JWTClient:
    """Create JWT client for API Entreprise."""
    config = JWTConfig(
        static_token=settings.api_entreprise_token,
        token_lifetime=15552000  # 6 months
    )
    return JWTClient("api_entreprise", config)