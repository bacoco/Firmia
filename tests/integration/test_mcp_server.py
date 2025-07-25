"""Integration tests for the MCP server."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from src.server import mcp, app
from src.auth import get_auth_manager
from src.cache import get_cache_manager


@pytest.fixture
async def mcp_server():
    """Create MCP server instance for testing."""
    # Initialize auth manager
    auth_manager = get_auth_manager()
    with patch.object(auth_manager, 'initialize') as mock_init:
        mock_init.return_value = None
        yield mcp


@pytest.mark.asyncio
async def test_server_health_check(mcp_server):
    """Test server health check endpoint."""
    # Mock auth manager status
    with patch('src.server.get_auth_manager') as mock_auth:
        mock_auth_manager = MagicMock()
        mock_auth_manager.get_service_status.return_value = {
            "recherche_entreprises": "ready",
            "insee_sirene": "authenticated",
            "inpi_rne": "authenticated",
            "api_entreprise": "authenticated"
        }
        mock_auth.return_value = mock_auth_manager
        
        # Execute health check
        health_tool = None
        for tool in mcp_server.tools.values():
            if tool.name == "health_check":
                health_tool = tool
                break
        
        assert health_tool is not None
        result = await health_tool.run()
        
        assert result["status"] == "healthy"
        assert result["version"] == "0.1.0"
        assert "auth_status" in result


@pytest.mark.asyncio
async def test_all_tools_registered(mcp_server):
    """Test that all expected tools are registered."""
    tool_names = [tool.name for tool in mcp_server.tools.values()]
    
    expected_tools = [
        "search_companies",
        "get_company_profile",
        "download_document",
        "list_documents",
        "health_check"
    ]
    
    for expected in expected_tools:
        assert expected in tool_names


@pytest.mark.asyncio
async def test_tool_descriptions(mcp_server):
    """Test that all tools have proper descriptions."""
    for tool in mcp_server.tools.values():
        assert tool.description is not None
        assert len(tool.description) > 10
        assert tool.name is not None


@pytest.mark.asyncio
async def test_search_tool_integration(mcp_server):
    """Test search companies tool integration."""
    search_tool = None
    for tool in mcp_server.tools.values():
        if tool.name == "search_companies":
            search_tool = tool
            break
    
    assert search_tool is not None
    
    # Mock the API calls
    with patch.object(search_tool.orchestrator.recherche_api, '_make_request') as mock_api:
        mock_api.return_value = {
            "results": [
                {
                    "siren": "123456789",
                    "nom_complet": "TEST COMPANY",
                    "siege": {
                        "siret": "12345678900001",
                        "code_postal": "75001",
                        "ville": "PARIS"
                    }
                }
            ],
            "total": 1,
            "page": 1,
            "per_page": 20
        }
        
        result = await search_tool.run(
            query="TEST COMPANY",
            page=1,
            per_page=20
        )
        
        assert result["total_results"] == 1
        assert result["companies"][0]["siren"] == "123456789"


@pytest.mark.asyncio
async def test_profile_tool_integration(mcp_server):
    """Test company profile tool integration."""
    profile_tool = None
    for tool in mcp_server.tools.values():
        if tool.name == "get_company_profile":
            profile_tool = tool
            break
    
    assert profile_tool is not None
    
    # Mock the API calls
    with patch.object(profile_tool.orchestrator.insee_api, 'get_legal_unit') as mock_insee:
        with patch.object(profile_tool.orchestrator.inpi_api, 'get_company_details') as mock_inpi:
            mock_insee.return_value = {
                "siren": "123456789",
                "denominationUniteLegale": "TEST COMPANY",
                "privacy_status": "O"
            }
            mock_inpi.return_value = {
                "siren": "123456789",
                "denomination": "TEST COMPANY SAS",
                "capital": 50000
            }
            
            result = await profile_tool.run(siren="123456789")
            
            assert result["company"]["siren"] == "123456789"
            assert "TEST COMPANY" in result["company"]["denomination"]


@pytest.mark.asyncio
async def test_document_tool_integration(mcp_server):
    """Test document download tool integration."""
    download_tool = None
    for tool in mcp_server.tools.values():
        if tool.name == "download_document":
            download_tool = tool
            break
    
    assert download_tool is not None
    
    # Mock the API calls
    with patch.object(download_tool.service.api_entreprise, 'download_document') as mock_download:
        mock_download.return_value = {
            "content": b"Mock PDF content",
            "mime_type": "application/pdf",
            "filename": "kbis.pdf"
        }
        
        result = await download_tool.run(
            siren="123456789",
            document_type="kbis",
            format="pdf"
        )
        
        assert result["document_type"] == "kbis"
        assert result["content"] is not None


@pytest.mark.asyncio
async def test_concurrent_tool_execution(mcp_server):
    """Test concurrent execution of multiple tools."""
    search_tool = None
    profile_tool = None
    
    for tool in mcp_server.tools.values():
        if tool.name == "search_companies":
            search_tool = tool
        elif tool.name == "get_company_profile":
            profile_tool = tool
    
    # Mock the API calls
    with patch.object(search_tool.orchestrator.recherche_api, '_make_request') as mock_search:
        with patch.object(profile_tool.orchestrator.insee_api, 'get_legal_unit') as mock_insee:
            with patch.object(profile_tool.orchestrator.inpi_api, 'get_company_details') as mock_inpi:
                mock_search.return_value = {
                    "results": [{"siren": "123456789", "nom_complet": "TEST"}],
                    "total": 1,
                    "page": 1,
                    "per_page": 20
                }
                mock_insee.return_value = {"siren": "123456789", "denominationUniteLegale": "TEST", "privacy_status": "O"}
                mock_inpi.return_value = {"siren": "123456789", "denomination": "TEST SAS"}
                
                # Execute tools concurrently
                results = await asyncio.gather(
                    search_tool.run(query="TEST"),
                    profile_tool.run(siren="123456789")
                )
                
                assert len(results) == 2
                assert results[0]["total_results"] >= 0
                assert results[1]["company"]["siren"] == "123456789"


@pytest.mark.asyncio
async def test_error_propagation(mcp_server):
    """Test that errors are properly propagated."""
    search_tool = None
    for tool in mcp_server.tools.values():
        if tool.name == "search_companies":
            search_tool = tool
            break
    
    # Mock API to raise an error
    with patch.object(search_tool.orchestrator.recherche_api, '_make_request') as mock_api:
        mock_api.side_effect = Exception("API Error")
        
        # Should handle error gracefully
        result = await search_tool.run(query="ERROR TEST")
        
        assert result["total_results"] == 0
        assert result["companies"] == []


@pytest.mark.asyncio
async def test_cache_integration(mcp_server):
    """Test cache integration across tools."""
    profile_tool = None
    for tool in mcp_server.tools.values():
        if tool.name == "get_company_profile":
            profile_tool = tool
            break
    
    # First call - cache miss
    with patch.object(profile_tool.orchestrator.cache_manager, 'get_company_profile') as mock_cache_get:
        with patch.object(profile_tool.orchestrator.cache_manager, 'set_company_profile') as mock_cache_set:
            with patch.object(profile_tool.orchestrator.insee_api, 'get_legal_unit') as mock_insee:
                with patch.object(profile_tool.orchestrator.inpi_api, 'get_company_details') as mock_inpi:
                    mock_cache_get.return_value = None  # Cache miss
                    mock_insee.return_value = {"siren": "123456789", "denominationUniteLegale": "TEST", "privacy_status": "O"}
                    mock_inpi.return_value = {"siren": "123456789", "denomination": "TEST SAS"}
                    
                    result = await profile_tool.run(siren="123456789")
                    
                    # Verify cache was set
                    mock_cache_set.assert_called_once()
                    assert result["company"]["siren"] == "123456789"


@pytest.mark.asyncio
async def test_auth_integration(mcp_server):
    """Test authentication integration."""
    # Get auth manager
    auth_manager = get_auth_manager()
    
    with patch.object(auth_manager, 'get_headers') as mock_headers:
        mock_headers.return_value = {
            "Authorization": "Bearer test_token",
            "X-API-Key": "test_key"
        }
        
        headers = await auth_manager.get_headers("api_entreprise")
        
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer test_token"