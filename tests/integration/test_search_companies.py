"""Integration tests for company search functionality."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from src.tools.search_companies import SearchCompaniesTool, SearchCompaniesInput


@pytest.fixture
def search_tool():
    """Create search tool instance."""
    return SearchCompaniesTool()


@pytest.fixture
def mock_api_responses():
    """Mock API responses for testing."""
    return {
        "recherche_entreprises": {
            "results": [
                {
                    "siren": "123456789",
                    "nom_complet": "EXAMPLE COMPANY SAS",
                    "siege": {
                        "siret": "12345678900001",
                        "code_postal": "75001",
                        "ville": "PARIS"
                    },
                    "dirigeants": [
                        {
                            "nom": "DUPONT",
                            "prenoms": "Jean",
                            "qualite": "Président"
                        }
                    ]
                }
            ],
            "total": 1,
            "page": 1,
            "per_page": 20
        },
        "insee": {
            "unitesLegales": [
                {
                    "siren": "123456789",
                    "denominationUniteLegale": "EXAMPLE COMPANY",
                    "categorieJuridiqueUniteLegale": "5710",
                    "activitePrincipaleUniteLegale": "62.01Z",
                    "trancheEffectifsUniteLegale": "21",
                    "etatAdministratifUniteLegale": "A"
                }
            ],
            "header": {
                "total": 1,
                "debut": 0,
                "nombre": 20
            }
        },
        "inpi": {
            "companies": [
                {
                    "siren": "123456789",
                    "formality": {
                        "content": {
                            "denomination": "EXAMPLE COMPANY SAS",
                            "formeJuridique": {
                                "code": "5710",
                                "libelle": "SAS"
                            },
                            "capital": {
                                "montant": 50000,
                                "devise": "EUR"
                            }
                        }
                    }
                }
            ],
            "total": 1
        }
    }


@pytest.mark.asyncio
async def test_search_by_name(search_tool, mock_api_responses):
    """Test searching companies by name."""
    with patch.object(search_tool.orchestrator.recherche_api, '_make_request') as mock_recherche:
        mock_recherche.return_value = mock_api_responses["recherche_entreprises"]
        
        result = await search_tool.run(
            query="EXAMPLE COMPANY",
            page=1,
            per_page=20
        )
        
        assert result["total_results"] >= 1
        assert len(result["companies"]) >= 1
        assert result["companies"][0]["siren"] == "123456789"
        assert "EXAMPLE COMPANY" in result["companies"][0]["denomination"]


@pytest.mark.asyncio
async def test_search_with_filters(search_tool, mock_api_responses):
    """Test searching with filters."""
    with patch.object(search_tool.orchestrator.recherche_api, '_make_request') as mock_recherche:
        with patch.object(search_tool.orchestrator.insee_api, '_make_request') as mock_insee:
            mock_recherche.return_value = mock_api_responses["recherche_entreprises"]
            mock_insee.return_value = mock_api_responses["insee"]
            
            result = await search_tool.run(
                query="EXAMPLE COMPANY",
                naf_code="62.01Z",
                employee_range="21",
                page=1,
                per_page=20
            )
            
            assert result["total_results"] >= 1
            assert result["applied_filters"]["naf_code"] == "62.01Z"
            assert result["applied_filters"]["employee_range"] == "21"


@pytest.mark.asyncio
async def test_search_by_siren(search_tool, mock_api_responses):
    """Test direct SIREN search."""
    with patch.object(search_tool.orchestrator.recherche_api, '_make_request') as mock_recherche:
        mock_recherche.return_value = mock_api_responses["recherche_entreprises"]
        
        result = await search_tool.run(
            query="123456789",
            page=1,
            per_page=20
        )
        
        assert result["total_results"] >= 1
        assert result["companies"][0]["siren"] == "123456789"


@pytest.mark.asyncio
async def test_search_with_location(search_tool, mock_api_responses):
    """Test searching with location filter."""
    with patch.object(search_tool.orchestrator.recherche_api, '_make_request') as mock_recherche:
        mock_recherche.return_value = mock_api_responses["recherche_entreprises"]
        
        result = await search_tool.run(
            query="EXAMPLE COMPANY",
            postal_code="75001",
            page=1,
            per_page=20
        )
        
        assert result["total_results"] >= 1
        assert result["applied_filters"]["postal_code"] == "75001"


@pytest.mark.asyncio
async def test_search_error_handling(search_tool):
    """Test error handling in search."""
    with patch.object(search_tool.orchestrator.recherche_api, '_make_request') as mock_recherche:
        mock_recherche.side_effect = Exception("API Error")
        
        result = await search_tool.run(
            query="ERROR TEST",
            page=1,
            per_page=20
        )
        
        assert result["total_results"] == 0
        assert result["companies"] == []
        assert result["metadata"]["completeness_score"] < 100


@pytest.mark.asyncio
async def test_search_pagination(search_tool, mock_api_responses):
    """Test pagination handling."""
    with patch.object(search_tool.orchestrator.recherche_api, '_make_request') as mock_recherche:
        mock_recherche.return_value = {
            **mock_api_responses["recherche_entreprises"],
            "total": 100,
            "page": 2,
            "per_page": 20
        }
        
        result = await search_tool.run(
            query="EXAMPLE",
            page=2,
            per_page=20
        )
        
        assert result["page"] == 2
        assert result["per_page"] == 20
        assert result["total_results"] == 100
        assert result["total_pages"] == 5


@pytest.mark.asyncio
async def test_search_cache_hit(search_tool, mock_api_responses):
    """Test search result caching."""
    with patch.object(search_tool.orchestrator.cache_manager, 'get_search_results') as mock_cache_get:
        mock_cache_get.return_value = {
            "total_results": 1,
            "companies": [{"siren": "123456789", "denomination": "CACHED COMPANY"}],
            "page": 1,
            "per_page": 20,
            "from_cache": True
        }
        
        result = await search_tool.run(
            query="CACHED",
            page=1,
            per_page=20
        )
        
        assert result["total_results"] == 1
        assert result["companies"][0]["denomination"] == "CACHED COMPANY"
        assert result.get("from_cache") is True


@pytest.mark.asyncio
async def test_multi_source_search(search_tool, mock_api_responses):
    """Test multi-source search coordination."""
    with patch.object(search_tool.orchestrator.recherche_api, '_make_request') as mock_recherche:
        with patch.object(search_tool.orchestrator.insee_api, '_make_request') as mock_insee:
            with patch.object(search_tool.orchestrator.inpi_api, 'search_companies') as mock_inpi:
                mock_recherche.return_value = mock_api_responses["recherche_entreprises"]
                mock_insee.return_value = mock_api_responses["insee"]
                mock_inpi.return_value = mock_api_responses["inpi"]["companies"]
                
                result = await search_tool.run(
                    query="EXAMPLE",
                    naf_code="62.01Z",
                    include_inpi=True,
                    page=1,
                    per_page=20
                )
                
                assert result["total_results"] >= 1
                assert result["metadata"]["sources_used"] == sorted(["recherche_entreprises", "insee_sirene", "inpi_rne"])


@pytest.mark.asyncio
async def test_search_privacy_filtering(search_tool, mock_api_responses):
    """Test privacy filtering in search results."""
    # Add privacy-sensitive data to mock response
    private_response = {
        **mock_api_responses["recherche_entreprises"],
        "results": [{
            **mock_api_responses["recherche_entreprises"]["results"][0],
            "dirigeants": [{
                "nom": "DUPONT",
                "prenoms": "Jean",
                "date_naissance": "1970-01-15",
                "qualite": "Président"
            }]
        }]
    }
    
    with patch.object(search_tool.orchestrator.recherche_api, '_make_request') as mock_recherche:
        mock_recherche.return_value = private_response
        
        result = await search_tool.run(
            query="EXAMPLE",
            page=1,
            per_page=20
        )
        
        # Check that birth date is filtered
        executive = result["companies"][0]["executives"][0]
        assert "birth_date" not in executive or executive["birth_date"] is None or len(executive["birth_date"]) <= 7