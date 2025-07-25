"""Main MCP server for Firmia French Company Intelligence."""

import asyncio
from contextlib import asynccontextmanager

from fastmcp import FastMCP
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
        logger.error("auth_initialization_failed", error=str(e))
        raise
    
    yield
    
    # Cleanup
    logger.info("shutting_down_firmia_server")
    await auth_manager.close()


# Create the MCP server
mcp = FastMCP(
    name="Firmia MCP Server",
    version="0.1.0"
)

# Configure server with lifespan
app = mcp.create_mcp_server(
    transport="stdio",
    lifespan=lifespan
)


# Import tools
from .tools.search_companies import SearchCompaniesTool
from .tools.get_company_profile import GetCompanyProfileTool
from .tools.download_document import DownloadDocumentTool, ListDocumentsTool
from .tools.search_legal_announcements import (
    SearchLegalAnnouncementsTool,
    GetAnnouncementTimelineTool,
    CheckFinancialHealthTool
)
from .tools.search_associations import (
    SearchAssociationsTool,
    GetAssociationDetailsTool,
    CheckIfAssociationTool
)
from .tools.check_certifications import (
    CheckCertificationsTool,
    SearchCertifiedCompaniesTool,
    GetCertificationDomainsTool
)

# Register tools
mcp.add_tool(SearchCompaniesTool())
mcp.add_tool(GetCompanyProfileTool())
mcp.add_tool(DownloadDocumentTool())
mcp.add_tool(ListDocumentsTool())
mcp.add_tool(SearchLegalAnnouncementsTool())
mcp.add_tool(GetAnnouncementTimelineTool())
mcp.add_tool(CheckFinancialHealthTool())
mcp.add_tool(SearchAssociationsTool())
mcp.add_tool(GetAssociationDetailsTool())
mcp.add_tool(CheckIfAssociationTool())
mcp.add_tool(CheckCertificationsTool())
mcp.add_tool(SearchCertifiedCompaniesTool())
mcp.add_tool(GetCertificationDomainsTool())

# Health check endpoint (for development/testing)
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


# Main entry point
def main():
    """Run the MCP server."""
    import uvicorn
    
    uvicorn.run(
        app,
        host=settings.mcp_host,
        port=settings.mcp_port,
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    main()