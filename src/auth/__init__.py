"""Authentication management for multiple API providers."""

from .manager import AuthManager, get_auth_manager
from .oauth2 import OAuth2Client
from .jwt import JWTClient

__all__ = [
    "AuthManager",
    "get_auth_manager",
    "OAuth2Client",
    "JWTClient",
]