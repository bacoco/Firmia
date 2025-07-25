"""Main MCP server for Firmia French Company Intelligence."""

import asyncio
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP
from structlog import get_logger

from .config import settings
from .auth import get_auth_manager
from .logging_config import setup_logging

# Initialize logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Manage server lifecycle."""
    logger.info("starting_firmia_server", 
                version="0.1.0",
                environment=settings.environment)
    
    # Initialize authentication manager
    auth_manager = get_auth_manager()
    try:
        await auth_manager.initialize()
        logger.info("auth_manager_initialized")
    except Exception as e:
        logger.warning("auth_initialization_failed", error=str(e))
        # Continue running even if auth fails - tools will handle individual auth errors
    
    yield
    
    # Cleanup
    logger.info("shutting_down_firmia_server")
    await auth_manager.close()


# Create the MCP server
mcp = FastMCP(
    name="Firmia",
    version="0.1.0"
)

# Configure the MCP server with lifespan
mcp.lifespan = lifespan


# Health check endpoint
@mcp.tool()
async def health_check() -> dict:
    """Check server health and authentication status."""
    auth_manager = get_auth_manager()
    
    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.environment,
        "auth_status": auth_manager.get_service_status()
    }


# Simple test tool
@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b


# Main entry point
def main():
    """Run the MCP server."""
    # Run the server with stdio transport by default
    # Can be changed to "sse" or "streamable-http" if needed
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()