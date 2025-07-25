"""Unit tests for authentication module."""

from datetime import datetime, timedelta
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.auth.base import Token
from src.auth.oauth2 import OAuth2Client, OAuth2Config
from src.auth.jwt import JWTClient, JWTConfig
from src.auth.manager import AuthManager


class TestToken:
    """Test Token model."""
    
    def test_token_not_expired(self):
        """Test token that is not expired."""
        token = Token(
            value="test_token",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        assert not token.is_expired
        assert token.expires_in_seconds > 0
    
    def test_token_expired(self):
        """Test token that is expired."""
        token = Token(
            value="test_token",
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        assert token.is_expired
        assert token.expires_in_seconds == 0
    
    def test_token_no_expiration(self):
        """Test token without expiration."""
        token = Token(value="test_token")
        assert not token.is_expired
        assert token.expires_in_seconds is None


class TestOAuth2Client:
    """Test OAuth2 authentication client."""
    
    @pytest.fixture
    def oauth_config(self):
        """Create OAuth2 config for testing."""
        return OAuth2Config(
            token_url="https://example.com/token",
            client_id="test_client",
            client_secret="test_secret"
        )
    
    @pytest.fixture
    def oauth_client(self, oauth_config):
        """Create OAuth2 client for testing."""
        return OAuth2Client("test_service", oauth_config)
    
    @pytest.mark.asyncio
    async def test_authenticate_success(self, oauth_client):
        """Test successful OAuth2 authentication."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test_access_token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(oauth_client._http_client, "post", return_value=mock_response):
            token = await oauth_client.authenticate()
            
            assert token.value == "test_access_token"
            assert token.token_type == "Bearer"
            assert token.expires_at > datetime.utcnow()
    
    @pytest.mark.asyncio
    async def test_get_token_caches(self, oauth_client):
        """Test that get_token caches the token."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test_access_token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(oauth_client._http_client, "post", return_value=mock_response) as mock_post:
            # First call should authenticate
            token1 = await oauth_client.get_token()
            assert mock_post.call_count == 1
            
            # Second call should use cached token
            token2 = await oauth_client.get_token()
            assert mock_post.call_count == 1
            assert token1 == token2


class TestJWTClient:
    """Test JWT authentication client."""
    
    @pytest.fixture
    def jwt_static_config(self):
        """Create JWT config with static token."""
        return JWTConfig(
            static_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
    
    @pytest.fixture
    def jwt_login_config(self):
        """Create JWT config with login."""
        return JWTConfig(
            login_url="https://example.com/login",
            username="test_user",
            password="test_pass"
        )
    
    @pytest.mark.asyncio
    async def test_static_token_auth(self, jwt_static_config):
        """Test JWT authentication with static token."""
        client = JWTClient("test_service", jwt_static_config)
        token = await client.authenticate()
        
        assert token.value == jwt_static_config.static_token
        assert token.expires_at > datetime.utcnow()
    
    @pytest.mark.asyncio
    async def test_login_auth_success(self, jwt_login_config):
        """Test JWT authentication with login."""
        client = JWTClient("test_service", jwt_login_config)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "token": "test_jwt_token"
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(client._http_client, "post", return_value=mock_response):
            token = await client.authenticate()
            
            assert token.value == "test_jwt_token"
            assert token.expires_at > datetime.utcnow()


class TestAuthManager:
    """Test authentication manager."""
    
    @pytest.mark.asyncio
    async def test_initialize(self, mock_settings):
        """Test auth manager initialization."""
        manager = AuthManager()
        
        with patch("src.auth.manager.create_insee_oauth_client") as mock_insee, \
             patch("src.auth.manager.create_inpi_jwt_client") as mock_inpi, \
             patch("src.auth.manager.create_api_entreprise_jwt_client") as mock_api:
            
            # Mock the client creation
            mock_insee.return_value = MagicMock()
            mock_inpi.return_value = MagicMock()
            mock_api_client = MagicMock()
            mock_api_client.get_token = AsyncMock(return_value="test_token")
            mock_api.return_value = mock_api_client
            
            await manager.initialize()
            
            assert "insee" in manager.clients
            assert "inpi" in manager.clients
            assert "api_entreprise" in manager.clients
            assert manager._initialized
    
    @pytest.mark.asyncio
    async def test_get_headers_no_auth(self):
        """Test getting headers for services that don't require auth."""
        manager = AuthManager()
        
        headers = await manager.get_headers("recherche_entreprises")
        assert headers == {}
        
        headers = await manager.get_headers("bodacc")
        assert headers == {}
    
    @pytest.mark.asyncio
    async def test_get_additional_headers(self):
        """Test getting additional headers for API Entreprise."""
        manager = AuthManager()
        
        headers = manager.get_additional_headers("api_entreprise")
        assert "X-Recipient-Id" in headers
        assert "X-Recipient-Object" in headers
        assert "X-Recipient-Context" in headers
        
        headers = manager.get_additional_headers("insee")
        assert headers == {}