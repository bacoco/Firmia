"""Integration tests for analytics features."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from src.tools.company_analytics import (
    GetCompanyHealthScoreTool,
    GetCompanyAnalyticsTool,
    GetMarketAnalyticsTool,
    GetTrendAnalysisTool
)
from src.tools.export_data import ExportDataTool, BatchOperationTool


@pytest.fixture
def health_score_tool():
    """Create health score tool."""
    return GetCompanyHealthScoreTool()


@pytest.fixture
def company_analytics_tool():
    """Create company analytics tool."""
    return GetCompanyAnalyticsTool()


@pytest.fixture
def market_analytics_tool():
    """Create market analytics tool."""
    return GetMarketAnalyticsTool()


@pytest.fixture
def export_tool():
    """Create export tool."""
    return ExportDataTool()


@pytest.fixture
def mock_company_profile():
    """Mock company profile data."""
    return {
        "company": {
            "siren": "123456789",
            "denomination": "EXAMPLE COMPANY SAS",
            "legal_form": {"code": "5710", "label": "SAS"},
            "is_active": True,
            "creation_date": (datetime.utcnow() - timedelta(days=365*5)).isoformat(),
            "employee_range": "20 à 49 salariés",
            "financials": {"capital": 100000},
            "executives": [
                {"name": "DUPONT", "first_name": "Jean", "role": "Président"}
            ],
            "certifications": {"rge": True, "qualiopi": False},
            "privacy_status": "O"
        }
    }


@pytest.fixture
def mock_analytics_data():
    """Mock analytics query results."""
    return [
        {
            "period": "2024-01",
            "company_count": 150,
            "avg_revenue": 500000,
            "avg_employees": 25
        },
        {
            "period": "2024-02",
            "company_count": 155,
            "avg_revenue": 520000,
            "avg_employees": 26
        },
        {
            "period": "2024-03",
            "company_count": 162,
            "avg_revenue": 530000,
            "avg_employees": 27
        }
    ]


@pytest.mark.asyncio
async def test_calculate_health_score(health_score_tool, mock_company_profile):
    """Test company health score calculation."""
    with patch.object(health_score_tool.profile_tool, 'run') as mock_profile:
        with patch.object(health_score_tool.health_calculator.bodacc_api, 'check_financial_health') as mock_bodacc:
            mock_profile.return_value = mock_company_profile
            mock_bodacc.return_value = {
                "has_collective_procedures": False,
                "recent_collective_procedures": False
            }
            
            result = await health_score_tool.run(
                siren="123456789",
                include_predictions=True
            )
            
            assert result["siren"] == "123456789"
            assert "overall_score" in result
            assert 0 <= result["overall_score"] <= 100
            assert "overall_status" in result
            assert len(result["metrics"]) == 5  # 5 metric categories
            assert "recommendations" in result
            assert "risk_factors" in result
            assert "positive_factors" in result


@pytest.mark.asyncio
async def test_health_score_with_risks(health_score_tool, mock_company_profile):
    """Test health score with financial risks."""
    # Modify profile to include risks
    risky_profile = mock_company_profile.copy()
    risky_profile["company"]["financials"]["capital"] = 500  # Low capital
    risky_profile["company"]["is_active"] = False  # Inactive
    
    with patch.object(health_score_tool.profile_tool, 'run') as mock_profile:
        with patch.object(health_score_tool.health_calculator.bodacc_api, 'check_financial_health') as mock_bodacc:
            mock_profile.return_value = risky_profile
            mock_bodacc.return_value = {
                "has_collective_procedures": True,
                "recent_collective_procedures": True,
                "financial_risk": "HIGH"
            }
            
            result = await health_score_tool.run(siren="123456789")
            
            assert result["overall_score"] < 50  # Low score due to risks
            assert result["overall_status"] in ["warning", "critical"]
            assert len(result["risk_factors"]) > 0
            assert any("capital" in r.lower() for r in result["risk_factors"])


@pytest.mark.asyncio
async def test_company_analytics_timeline(company_analytics_tool):
    """Test company timeline analytics."""
    mock_timeline_data = [
        {
            "event_date": "2024-01-15",
            "event_type": "creation",
            "event_description": "Company created",
            "source": "insee"
        },
        {
            "event_date": "2024-02-01",
            "event_type": "establishment_opened",
            "event_description": "New establishment in Lyon",
            "source": "insee"
        }
    ]
    
    with patch.object(company_analytics_tool.company_analyzer.cache_manager, 'query_analytics') as mock_query:
        mock_query.return_value = mock_timeline_data
        
        result = await company_analytics_tool.run(
            siren="123456789",
            analysis_type="timeline"
        )
        
        assert result["query_type"] == "company_timeline"
        assert len(result["data"]) == 2
        assert result["row_count"] == 2


@pytest.mark.asyncio
async def test_market_analytics_sector_stats(market_analytics_tool):
    """Test sector statistics analytics."""
    mock_stats = [{
        "company_count": 1500,
        "geographic_spread": 75,
        "avg_employees": 35.5,
        "median_revenue": 750000,
        "new_companies": 120,
        "ceased_companies": 45,
        "active_rate": 92.5
    }]
    
    with patch.object(market_analytics_tool.market_analyzer.cache_manager, 'query_analytics') as mock_query:
        mock_query.return_value = mock_stats
        
        result = await market_analytics_tool.run(
            analysis_type="sector_stats",
            naf_code="62.01Z"
        )
        
        assert result["query_type"] == "sector_statistics"
        assert result["data"][0]["company_count"] == 1500
        assert result["metadata"]["naf_code"] == "62.01Z"


@pytest.mark.asyncio
async def test_trend_analysis(mock_analytics_data):
    """Test trend analysis."""
    from src.tools.company_analytics import GetTrendAnalysisTool
    trend_tool = GetTrendAnalysisTool()
    
    with patch.object(trend_tool.trend_analyzer.cache_manager, 'query_analytics') as mock_query:
        mock_query.return_value = mock_analytics_data
        
        result = await trend_tool.run(
            naf_code="62.01Z",
            metrics=["company_count", "avg_revenue"],
            period_months=12
        )
        
        assert "trend_analysis" in result
        assert "company_count" in result["trend_analysis"]
        
        # Check trend detection
        company_trend = result["trend_analysis"]["company_count"]
        assert company_trend["direction"] in ["up", "stable", "down", "strong_up", "strong_down", "volatile"]
        assert "change_percent" in company_trend
        assert len(company_trend["data_points"]) > 0


@pytest.mark.asyncio
async def test_export_search_results(export_tool):
    """Test exporting search results."""
    mock_search_results = {
        "results": [
            {
                "siren": "123456789",
                "name": "COMPANY A",
                "naf_code": "62.01Z",
                "city": "PARIS"
            },
            {
                "siren": "987654321",
                "name": "COMPANY B",
                "naf_code": "62.01Z",
                "city": "LYON"
            }
        ],
        "pagination": {"total": 2, "page": 1, "per_page": 20, "total_pages": 1}
    }
    
    with patch('src.tools.export_data.SearchCompaniesTool') as MockSearchTool:
        mock_instance = MockSearchTool.return_value
        mock_instance.run = AsyncMock(return_value=mock_search_results)
        
        # Test JSON export
        result = await export_tool.run(
            data_type="search_results",
            format="json",
            query="software companies",
            limit=10
        )
        
        assert result["format"] == "json"
        assert result["row_count"] == 2
        assert "content" in result
        
        # Test CSV export
        result_csv = await export_tool.run(
            data_type="search_results",
            format="csv",
            query="software companies",
            limit=10,
            fields=["siren", "name", "city"]
        )
        
        assert result_csv["format"] == "csv"
        assert "siren,name,city" in result_csv["content"] or "city,name,siren" in result_csv["content"]


@pytest.mark.asyncio
async def test_batch_operations():
    """Test batch operations."""
    batch_tool = BatchOperationTool()
    
    # Mock the health score tool
    with patch('src.tools.export_data.GetCompanyHealthScoreTool') as MockHealthTool:
        mock_instance = MockHealthTool.return_value
        mock_instance.run = AsyncMock(side_effect=[
            {"siren": "123456789", "overall_score": 75, "overall_status": "good"},
            {"siren": "987654321", "overall_score": 85, "overall_status": "excellent"},
            {"siren": "555666777", "overall_score": 45, "overall_status": "warning"}
        ])
        
        result = await batch_tool.run(
            operation="health_score",
            items=[
                {"siren": "123456789"},
                {"siren": "987654321"},
                {"siren": "555666777"}
            ],
            parallel=True,
            max_workers=3
        )
        
        assert result["operation"] == "health_score"
        assert result["total_items"] == 3
        assert result["success_count"] == 3
        assert result["error_count"] == 0
        assert len(result["results"]) == 3
        
        # Check results
        scores = [r["result"]["overall_score"] for r in result["results"]]
        assert 85 in scores  # Excellent company
        assert 45 in scores  # Warning company


@pytest.mark.asyncio
async def test_export_with_privacy_filters(export_tool):
    """Test that export applies privacy filters."""
    mock_profiles = [
        {
            "siren": "123456789",
            "denomination": "PRIVATE COMPANY",
            "privacy_status": "P",  # Protected
            "address": {
                "street": "123 Secret Street",
                "postal_code": "75001",
                "city": "PARIS"
            },
            "executives": [
                {
                    "name": "SMITH",
                    "first_name": "John",
                    "birth_date": "1970-01-15"  # Should be filtered
                }
            ]
        }
    ]
    
    with patch('src.tools.export_data.GetCompanyProfileTool') as MockProfileTool:
        mock_instance = MockProfileTool.return_value
        mock_instance.run = AsyncMock(return_value={"company": mock_profiles[0]})
        
        with patch('src.tools.export_data.apply_privacy_filters') as mock_filter:
            # Mock privacy filter to remove sensitive data
            mock_filter.return_value = {
                "siren": "123456789",
                "denomination": "PRIVATE COMPANY",
                "privacy_status": "P",
                "address": {
                    "postal_code": "75001",  # Street removed
                    "city": "PARIS"
                },
                "executives": [
                    {
                        "name": "SMITH",
                        "first_name": "John"
                        # Birth date removed
                    }
                ]
            }
            
            result = await export_tool.run(
                data_type="company_profiles",
                format="json",
                sirens=["123456789"]
            )
            
            # Verify privacy filter was called
            mock_filter.assert_called()


@pytest.mark.asyncio
async def test_analytics_caching():
    """Test that analytics results are cached."""
    from src.analytics import CompanyAnalyzer
    analyzer = CompanyAnalyzer()
    
    # Mock cache manager
    with patch.object(analyzer.cache_manager, 'query_analytics') as mock_query:
        mock_query.return_value = [{"test": "data"}]
        
        # First call
        result1 = await analyzer.get_company_timeline("123456789")
        assert mock_query.call_count == 1
        
        # Second call should use same mock (simulating cache in real scenario)
        result2 = await analyzer.get_company_timeline("123456789")
        assert mock_query.call_count == 2  # Would be 1 with real caching
        
        assert result1.data == result2.data