"""Integration tests for extended APIs (BODACC, RNA, RGE)."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import date, datetime

from src.tools.search_legal_announcements import SearchLegalAnnouncementsTool
from src.tools.search_associations import SearchAssociationsTool
from src.tools.check_certifications import CheckCertificationsTool


@pytest.fixture
def announcement_tool():
    """Create announcement search tool."""
    return SearchLegalAnnouncementsTool()


@pytest.fixture
def association_tool():
    """Create association search tool."""
    return SearchAssociationsTool()


@pytest.fixture
def certification_tool():
    """Create certification check tool."""
    return CheckCertificationsTool()


@pytest.fixture
def mock_bodacc_data():
    """Mock BODACC API responses."""
    return {
        "announcements": [
            {
                "id": "ann_001",
                "type": "C",
                "type_label": "Procédures collectives",
                "publication_date": "2024-01-15",
                "bodacc_number": "2024B00123",
                "court": "Tribunal de Commerce de Paris",
                "siren": "123456789",
                "denomination": "EXAMPLE COMPANY SAS",
                "title": "Jugement d'ouverture de redressement judiciaire",
                "content": "Par jugement en date du 10/01/2024...",
                "procedure_type": "Redressement judiciaire",
                "procedure_date": "2024-01-10",
                "administrators": [
                    {"name": "Me DUPONT", "role": "Administrateur judiciaire"}
                ]
            }
        ],
        "total": 1,
        "limit": 20,
        "offset": 0
    }


@pytest.fixture
def mock_rna_data():
    """Mock RNA API responses."""
    return {
        "associations": [
            {
                "rna_id": "W123456789",
                "siren": "987654321",
                "siret": "98765432100001",
                "name": "ASSOCIATION EXAMPLE",
                "short_name": "ASSEX",
                "object": "Promotion de l'économie sociale et solidaire",
                "is_active": True,
                "creation_date": "2010-05-15",
                "is_public_utility": True,
                "address": {
                    "street": "10 rue de la Solidarité",
                    "postal_code": "75001",
                    "city": "PARIS",
                    "country": "France"
                },
                "email": "contact@assex.fr",
                "website": "https://www.assex.fr"
            }
        ],
        "total": 1,
        "page": 1,
        "per_page": 20
    }


@pytest.fixture
def mock_rge_data():
    """Mock RGE API responses."""
    return {
        "is_rge_certified": True,
        "total_certifications": 2,
        "active_certifications": 2,
        "expired_certifications": 0,
        "certification_domains": ["ISOLATION", "CHAUFFAGE"],
        "certifications": [
            {
                "type": "RGE",
                "code": "QUALIBAT-7131",
                "name": "Isolation thermique par l'intérieur",
                "certifying_body": "QUALIBAT",
                "validity_date": "2025-12-31",
                "is_valid": True,
                "domain": "ISOLATION",
                "competencies": [
                    {"code": "7131", "label": "Isolation des murs"}
                ]
            },
            {
                "type": "RGE",
                "code": "QUALIBAT-5311",
                "name": "Installation de chauffage",
                "certifying_body": "QUALIBAT",
                "validity_date": "2025-06-30",
                "is_valid": True,
                "domain": "CHAUFFAGE",
                "competencies": [
                    {"code": "5311", "label": "Chaudières gaz"}
                ]
            }
        ],
        "next_expiry": "2025-06-30"
    }


@pytest.mark.asyncio
async def test_search_legal_announcements(announcement_tool, mock_bodacc_data):
    """Test searching legal announcements."""
    with patch.object(announcement_tool.orchestrator.bodacc_api, 'search_announcements') as mock_search:
        mock_search.return_value = mock_bodacc_data
        
        result = await announcement_tool.run(
            siren="123456789",
            announcement_type="procedure_collective",
            page=1,
            per_page=20
        )
        
        assert result["total_results"] == 1
        assert len(result["announcements"]) == 1
        assert result["announcements"][0]["type"] == "procedure_collective"
        assert result["announcements"][0]["siren"] == "123456789"


@pytest.mark.asyncio
async def test_search_by_date_range(announcement_tool, mock_bodacc_data):
    """Test searching announcements by date range."""
    with patch.object(announcement_tool.orchestrator.bodacc_api, 'search_announcements') as mock_search:
        mock_search.return_value = mock_bodacc_data
        
        result = await announcement_tool.run(
            date_from="2024-01-01",
            date_to="2024-01-31",
            page=1,
            per_page=20
        )
        
        assert result["total_results"] == 1
        mock_search.assert_called_once()
        # Check date parameters were passed
        call_args = mock_search.call_args[1]
        assert call_args["date_from"] == date(2024, 1, 1)
        assert call_args["date_to"] == date(2024, 1, 31)


@pytest.mark.asyncio
async def test_search_associations(association_tool, mock_rna_data):
    """Test searching associations."""
    with patch.object(association_tool.orchestrator.rna_api, 'search_associations') as mock_search:
        mock_search.return_value = mock_rna_data
        
        result = await association_tool.run(
            query="ASSOCIATION EXAMPLE",
            postal_code="75001",
            page=1,
            per_page=20
        )
        
        assert result["total_results"] == 1
        assert len(result["associations"]) == 1
        assert result["associations"][0]["rna_id"] == "W123456789"
        assert result["associations"][0]["is_public_utility"] is True


@pytest.mark.asyncio
async def test_get_association_details(association_tool, mock_rna_data):
    """Test getting association details."""
    with patch.object(association_tool.orchestrator.rna_api, 'get_association_by_rna') as mock_get:
        # Return detailed data
        mock_get.return_value = {
            **mock_rna_data["associations"][0],
            "members_count": 150,
            "volunteers_count": 50,
            "employees_count": 5,
            "accepts_donations": True
        }
        
        # Create details tool
        from src.tools.search_associations import GetAssociationDetailsTool
        details_tool = GetAssociationDetailsTool()
        
        result = await details_tool.run(
            identifier="W123456789",
            identifier_type="rna"
        )
        
        assert result["rna_id"] == "W123456789"
        assert result["members_count"] == 150
        assert result["accepts_donations"] is True


@pytest.mark.asyncio
async def test_check_certifications(certification_tool, mock_rge_data):
    """Test checking company certifications."""
    with patch.object(certification_tool.orchestrator.rge_api, 'check_certification_status') as mock_check:
        mock_check.return_value = mock_rge_data
        
        result = await certification_tool.run(
            siren="123456789",
            force_refresh=False
        )
        
        assert result["has_certifications"] is True
        assert len(result["certifications"]) == 2
        assert result["certification_summary"]["rge"]["certified"] is True
        assert result["certification_summary"]["rge"]["active_count"] == 2


@pytest.mark.asyncio
async def test_search_certified_companies(certification_tool):
    """Test searching certified companies."""
    from src.tools.check_certifications import SearchCertifiedCompaniesTool
    search_tool = SearchCertifiedCompaniesTool()
    
    mock_results = {
        "total": 5,
        "companies": [
            {
                "siret": "12345678900001",
                "siren": "123456789",
                "name": "ECO RENOVATION",
                "address": {
                    "postal_code": "75001",
                    "city": "PARIS"
                },
                "certifications": [
                    {
                        "type": "RGE",
                        "code": "QUALIBAT-7131",
                        "is_valid": True
                    }
                ]
            }
        ],
        "limit": 20,
        "offset": 0
    }
    
    with patch.object(search_tool.orchestrator.rge_api, 'search_certified_companies') as mock_search:
        mock_search.return_value = mock_results
        
        result = await search_tool.run(
            postal_code="75001",
            domain="ISOLATION",
            page=1,
            per_page=20
        )
        
        assert result["total"] == 5
        assert len(result["companies"]) == 1
        assert result["companies"][0]["name"] == "ECO RENOVATION"


@pytest.mark.asyncio
async def test_mixed_search_companies_and_associations():
    """Test mixed search including associations."""
    from src.tools.search_companies import SearchCompaniesTool
    search_tool = SearchCompaniesTool()
    
    # Mock company results
    company_results = {
        "results": [
            {
                "siren": "123456789",
                "name": "EXAMPLE COMPANY",
                "legal_form": "SAS",
                "source": "recherche_entreprises"
            }
        ],
        "pagination": {"total": 1, "page": 1, "per_page": 20, "total_pages": 1}
    }
    
    # Mock association results
    association_results = {
        "associations": [
            {
                "rna_id": "W987654321",
                "siren": "987654321",
                "name": "EXAMPLE ASSOCIATION",
                "is_active": True,
                "address": {"postal_code": "75001", "city": "PARIS"}
            }
        ],
        "total": 1
    }
    
    with patch.object(search_tool.orchestrator.recherche_api, 'search') as mock_company:
        with patch.object(search_tool.orchestrator.rna_api, 'search_associations') as mock_assoc:
            mock_company.return_value = company_results
            mock_assoc.return_value = association_results
            
            result = await search_tool.run(
                query="EXAMPLE",
                include_associations=True,
                page=1,
                per_page=20
            )
            
            # Should have results from both sources
            assert result["results"] is not None
            # Check that both APIs were called
            mock_company.assert_called_once()
            mock_assoc.assert_called_once()


@pytest.mark.asyncio
async def test_announcement_timeline():
    """Test getting announcement timeline for a company."""
    from src.tools.search_legal_announcements import GetAnnouncementTimelineTool
    timeline_tool = GetAnnouncementTimelineTool()
    
    mock_timeline = [
        {
            "date": "2024-01-15",
            "type": "C",
            "type_label": "Procédures collectives",
            "title": "Redressement judiciaire",
            "court": "TC Paris"
        },
        {
            "date": "2023-06-10",
            "type": "B",
            "type_label": "Création d'établissement",
            "title": "Ouverture établissement Lyon"
        }
    ]
    
    with patch.object(timeline_tool.orchestrator.bodacc_api, 'get_company_timeline') as mock_timeline_api:
        mock_timeline_api.return_value = mock_timeline
        
        result = await timeline_tool.run(siren="123456789")
        
        assert result["siren"] == "123456789"
        assert result["total_announcements"] == 2
        assert result["has_collective_procedures"] is True


@pytest.mark.asyncio
async def test_financial_health_check():
    """Test checking financial health via announcements."""
    from src.tools.search_legal_announcements import CheckFinancialHealthTool
    health_tool = CheckFinancialHealthTool()
    
    mock_health = {
        "siren": "123456789",
        "total_announcements": 5,
        "announcement_types": {"C": 2, "B": 3},
        "has_collective_procedures": True,
        "recent_collective_procedures": True,
        "financial_risk": "HIGH"
    }
    
    with patch.object(health_tool.orchestrator.bodacc_api, 'check_financial_health') as mock_health_api:
        mock_health_api.return_value = mock_health
        
        result = await health_tool.run(siren="123456789")
        
        assert result["financial_risk"] == "HIGH"
        assert result["has_collective_procedures"] is True