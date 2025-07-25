"""Integration tests for company profile functionality."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from src.tools.get_company_profile import GetCompanyProfileTool


@pytest.fixture
def profile_tool():
    """Create profile tool instance."""
    return GetCompanyProfileTool()


@pytest.fixture
def mock_company_data():
    """Mock company data from various sources."""
    return {
        "insee": {
            "siren": "123456789",
            "denominationUniteLegale": "EXAMPLE COMPANY",
            "sigleUniteLegale": "EXCO",
            "categorieJuridiqueUniteLegale": "5710",
            "activitePrincipaleUniteLegale": "62.01Z",
            "trancheEffectifsUniteLegale": "21",
            "dateCreationUniteLegale": "2010-01-15",
            "etatAdministratifUniteLegale": "A",
            "privacy_status": "O",
            "etablissementSiege": {
                "siret": "12345678900001",
                "codePostalEtablissement": "75001",
                "libelleCommuneEtablissement": "PARIS"
            }
        },
        "inpi": {
            "siren": "123456789",
            "denomination": "EXAMPLE COMPANY SAS",
            "sigle": "EXCO",
            "legal_form": {
                "code": "5710",
                "libelle": "SAS, société par actions simplifiée"
            },
            "capital": 100000,
            "creation_date": "2010-01-15",
            "is_active": True,
            "executives": [
                {
                    "role": "Président",
                    "name": "DUPONT",
                    "first_name": "Jean",
                    "birth_date": "1970-01",
                    "nationality": "Française"
                }
            ]
        },
        "establishments": [
            {
                "siret": "12345678900001",
                "is_headquarters": True,
                "address": {
                    "street": "1 RUE DE LA PAIX",
                    "postal_code": "75001",
                    "city": "PARIS",
                    "country": "France"
                },
                "employee_range": "20 à 49 salariés",
                "activity": "Programmation informatique"
            },
            {
                "siret": "12345678900002",
                "is_headquarters": False,
                "address": {
                    "street": "10 AVENUE DES CHAMPS",
                    "postal_code": "69001",
                    "city": "LYON",
                    "country": "France"
                },
                "employee_range": "10 à 19 salariés",
                "activity": "Programmation informatique"
            }
        ],
        "documents": [
            {
                "id": "doc_001",
                "type": "kbis",
                "name": "Extrait KBIS",
                "date": "2024-01-15"
            },
            {
                "id": "doc_002",
                "type": "statuts",
                "name": "Statuts constitutifs",
                "date": "2010-01-15"
            }
        ],
        "certifications": {
            "rge": None,
            "bio": False,
            "ess": False,
            "qualiopi": True
        }
    }


@pytest.mark.asyncio
async def test_get_basic_company_profile(profile_tool, mock_company_data):
    """Test getting basic company profile."""
    with patch.object(profile_tool.orchestrator.insee_api, 'get_legal_unit') as mock_insee:
        with patch.object(profile_tool.orchestrator.inpi_api, 'get_company_details') as mock_inpi:
            mock_insee.return_value = mock_company_data["insee"]
            mock_inpi.return_value = mock_company_data["inpi"]
            
            result = await profile_tool.run(
                siren="123456789",
                include_establishments=False,
                include_documents=False,
                include_financials=True,
                include_certifications=False,
                include_bank_info=False
            )
            
            assert result["company"]["siren"] == "123456789"
            assert result["company"]["denomination"] == "EXAMPLE COMPANY SAS"
            assert result["company"]["legal_form"]["code"] == "5710"
            assert result["company"]["financials"]["capital"] == 100000
            assert len(result["company"]["executives"]) == 1
            assert result["metadata"]["sources"] == ["insee", "inpi"]


@pytest.mark.asyncio
async def test_get_profile_with_establishments(profile_tool, mock_company_data):
    """Test getting profile with establishments."""
    with patch.object(profile_tool.orchestrator.insee_api, 'get_legal_unit') as mock_insee:
        with patch.object(profile_tool.orchestrator.inpi_api, 'get_company_details') as mock_inpi:
            with patch.object(profile_tool.orchestrator, '_get_establishments') as mock_estabs:
                mock_insee.return_value = mock_company_data["insee"]
                mock_inpi.return_value = mock_company_data["inpi"]
                mock_estabs.return_value = mock_company_data["establishments"]
                
                result = await profile_tool.run(
                    siren="123456789",
                    include_establishments=True,
                    include_documents=False,
                    include_financials=True,
                    include_certifications=False,
                    include_bank_info=False
                )
                
                assert len(result["company"]["establishments"]) == 2
                assert result["company"]["establishments"][0]["is_headquarters"] is True
                assert result["company"]["establishments"][1]["siret"] == "12345678900002"


@pytest.mark.asyncio
async def test_get_profile_with_documents(profile_tool, mock_company_data):
    """Test getting profile with documents list."""
    with patch.object(profile_tool.orchestrator.insee_api, 'get_legal_unit') as mock_insee:
        with patch.object(profile_tool.orchestrator.inpi_api, 'get_company_details') as mock_inpi:
            with patch.object(profile_tool.orchestrator.inpi_api, 'get_company_documents') as mock_docs:
                mock_insee.return_value = mock_company_data["insee"]
                mock_inpi.return_value = mock_company_data["inpi"]
                mock_docs.return_value = mock_company_data["documents"]
                
                result = await profile_tool.run(
                    siren="123456789",
                    include_establishments=False,
                    include_documents=True,
                    include_financials=True,
                    include_certifications=False,
                    include_bank_info=False
                )
                
                assert "documents" in result["metadata"]["sources"]


@pytest.mark.asyncio
async def test_get_profile_with_certifications(profile_tool, mock_company_data):
    """Test getting profile with certifications."""
    with patch.object(profile_tool.orchestrator.insee_api, 'get_legal_unit') as mock_insee:
        with patch.object(profile_tool.orchestrator.inpi_api, 'get_company_details') as mock_inpi:
            with patch.object(profile_tool.orchestrator, '_get_certifications') as mock_certs:
                mock_insee.return_value = mock_company_data["insee"]
                mock_inpi.return_value = mock_company_data["inpi"]
                mock_certs.return_value = mock_company_data["certifications"]
                
                result = await profile_tool.run(
                    siren="123456789",
                    include_establishments=False,
                    include_documents=False,
                    include_financials=True,
                    include_certifications=True,
                    include_bank_info=False
                )
                
                assert result["company"]["certifications"]["qualiopi"] is True
                assert result["company"]["certifications"]["bio"] is False


@pytest.mark.asyncio
async def test_profile_cache_hit(profile_tool):
    """Test profile caching."""
    cached_profile = {
        "company": {
            "siren": "123456789",
            "denomination": "CACHED COMPANY",
            "source": ["cache"]
        },
        "metadata": {
            "last_update": datetime.utcnow().isoformat(),
            "sources": ["cache"],
            "from_cache": True
        }
    }
    
    with patch.object(profile_tool.orchestrator.cache_manager, 'get_company_profile') as mock_cache:
        mock_cache.return_value = cached_profile
        
        result = await profile_tool.run(siren="123456789")
        
        assert result["company"]["denomination"] == "CACHED COMPANY"
        assert result["metadata"]["from_cache"] is True


@pytest.mark.asyncio
async def test_profile_privacy_filtering(profile_tool, mock_company_data):
    """Test privacy filtering for protected companies."""
    private_insee_data = {
        **mock_company_data["insee"],
        "privacy_status": "P"  # Protected
    }
    
    with patch.object(profile_tool.orchestrator.insee_api, 'get_legal_unit') as mock_insee:
        with patch.object(profile_tool.orchestrator.inpi_api, 'get_company_details') as mock_inpi:
            mock_insee.return_value = private_insee_data
            mock_inpi.return_value = mock_company_data["inpi"]
            
            result = await profile_tool.run(siren="123456789")
            
            # Check that sensitive executive data is filtered
            executive = result["company"]["executives"][0]
            assert executive.get("birth_date") is None or len(executive["birth_date"]) <= 7


@pytest.mark.asyncio
async def test_profile_error_handling(profile_tool):
    """Test error handling when APIs fail."""
    with patch.object(profile_tool.orchestrator.insee_api, 'get_legal_unit') as mock_insee:
        with patch.object(profile_tool.orchestrator.inpi_api, 'get_company_details') as mock_inpi:
            mock_insee.side_effect = Exception("INSEE API Error")
            mock_inpi.side_effect = Exception("INPI API Error")
            
            # Should still return a result with degraded data
            result = await profile_tool.run(siren="123456789")
            
            assert result["company"]["siren"] == "123456789"
            assert result["company"]["denomination"] == "SIREN 123456789"  # Fallback
            assert result["metadata"]["completeness_score"] < 100


@pytest.mark.asyncio
async def test_profile_data_fusion(profile_tool, mock_company_data):
    """Test data fusion with precedence rules."""
    # INSEE has different data than INPI
    insee_data = {
        **mock_company_data["insee"],
        "denominationUniteLegale": "OLD COMPANY NAME",
        "capital": 50000  # INSEE doesn't have capital
    }
    
    with patch.object(profile_tool.orchestrator.insee_api, 'get_legal_unit') as mock_insee:
        with patch.object(profile_tool.orchestrator.inpi_api, 'get_company_details') as mock_inpi:
            mock_insee.return_value = insee_data
            mock_inpi.return_value = mock_company_data["inpi"]
            
            result = await profile_tool.run(siren="123456789")
            
            # INPI data should take precedence
            assert result["company"]["denomination"] == "EXAMPLE COMPANY SAS"
            assert result["company"]["financials"]["capital"] == 100000


@pytest.mark.asyncio
async def test_profile_completeness_calculation(profile_tool, mock_company_data):
    """Test completeness score calculation."""
    with patch.object(profile_tool.orchestrator.insee_api, 'get_legal_unit') as mock_insee:
        with patch.object(profile_tool.orchestrator.inpi_api, 'get_company_details') as mock_inpi:
            with patch.object(profile_tool.orchestrator, '_get_establishments') as mock_estabs:
                # INSEE succeeds
                mock_insee.return_value = mock_company_data["insee"]
                # INPI fails
                mock_inpi.side_effect = Exception("INPI Error")
                # Establishments succeed
                mock_estabs.return_value = mock_company_data["establishments"]
                
                result = await profile_tool.run(
                    siren="123456789",
                    include_establishments=True
                )
                
                # 2 out of 3 sources succeeded = 66.67%
                assert result["metadata"]["completeness_score"] == pytest.approx(66.67, rel=0.1)