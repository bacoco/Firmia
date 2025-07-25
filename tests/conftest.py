"""Pytest configuration and shared fixtures."""

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Add src to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Load test environment
test_env = Path(__file__).parent / "test.env"
if test_env.exists():
    load_dotenv(test_env)
else:
    # Set minimal test environment
    os.environ["INSEE_CLIENT_ID"] = "test_client_id"
    os.environ["INSEE_CLIENT_SECRET"] = "test_client_secret"
    os.environ["INPI_USERNAME"] = "test_username"
    os.environ["INPI_PASSWORD"] = "test_password"
    os.environ["API_ENTREPRISE_TOKEN"] = "test_jwt_token"
    os.environ["ENVIRONMENT"] = "test"
    os.environ["LOG_LEVEL"] = "DEBUG"


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for testing."""
    from src.config import Settings
    
    settings = Settings(
        insee_client_id="test_insee_id",
        insee_client_secret="test_insee_secret",
        inpi_username="test_inpi_user",
        inpi_password="test_inpi_pass",
        api_entreprise_token="test_api_entreprise_token",
        environment="test",
        log_level="DEBUG"
    )
    
    monkeypatch.setattr("src.config.settings", settings)
    return settings


@pytest.fixture
async def auth_manager():
    """Create auth manager for testing."""
    from src.auth import AuthManager
    
    manager = AuthManager()
    yield manager
    await manager.close()