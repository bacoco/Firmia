"""Analytics engine for company and market analysis."""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

import duckdb
from structlog import get_logger

from ..cache import get_cache_manager

logger = get_logger(__name__)


@dataclass
class AnalyticsResult:
    """Container for analytics query results."""
    query_type: str
    data: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    executed_at: datetime
    row_count: int
    execution_time_ms: float


class CompanyAnalyzer:
    """Analyzes individual company data using DuckDB."""
    
    def __init__(self):
        self.cache_manager = get_cache_manager()
        self.logger = logger.bind(component="company_analyzer")
    
    async def get_company_timeline(
        self,
        siren: str,
        event_types: Optional[List[str]] = None
    ) -> AnalyticsResult:
        """Get comprehensive timeline of company events."""
        start_time = datetime.utcnow()
        
        # Build query
        query = f"""
        SELECT 
            event_date,
            event_type,
            event_description,
            source,
            details
        FROM business_events
        WHERE siren = ?
        """
        
        if event_types:
            placeholders = ",".join("?" for _ in event_types)
            query += f" AND event_type IN ({placeholders})"
        
        query += " ORDER BY event_date DESC LIMIT 100"
        
        # Execute query
        params = [siren]
        if event_types:
            params.extend(event_types)
        
        results = await self.cache_manager.query_analytics(query, params)
        
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return AnalyticsResult(
            query_type="company_timeline",
            data=results,
            metadata={
                "siren": siren,
                "event_types": event_types
            },
            executed_at=datetime.utcnow(),
            row_count=len(results),
            execution_time_ms=execution_time
        )
    
    async def get_financial_evolution(
        self,
        siren: str,
        years: int = 5
    ) -> AnalyticsResult:
        """Analyze financial evolution over time."""
        start_time = datetime.utcnow()
        
        query = """
        SELECT 
            year,
            revenue,
            net_income,
            total_assets,
            equity,
            employee_count,
            revenue_growth_pct,
            profit_margin
        FROM company_financials
        WHERE siren = ?
            AND year >= ?
        ORDER BY year DESC
        """
        
        current_year = datetime.utcnow().year
        params = [siren, current_year - years]
        
        results = await self.cache_manager.query_analytics(query, params)
        
        # Calculate trends
        if len(results) > 1:
            revenue_trend = self._calculate_trend([r["revenue"] for r in results if r["revenue"]])
            growth_trend = self._calculate_trend([r["revenue_growth_pct"] for r in results if r["revenue_growth_pct"]])
        else:
            revenue_trend = "insufficient_data"
            growth_trend = "insufficient_data"
        
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return AnalyticsResult(
            query_type="financial_evolution",
            data=results,
            metadata={
                "siren": siren,
                "years_analyzed": years,
                "revenue_trend": revenue_trend,
                "growth_trend": growth_trend
            },
            executed_at=datetime.utcnow(),
            row_count=len(results),
            execution_time_ms=execution_time
        )
    
    async def get_peer_comparison(
        self,
        siren: str,
        naf_code: Optional[str] = None,
        department: Optional[str] = None,
        limit: int = 10
    ) -> AnalyticsResult:
        """Compare company with peers."""
        start_time = datetime.utcnow()
        
        # First, get company info
        company_query = """
        SELECT naf_code, department, employee_range, revenue
        FROM companies
        WHERE siren = ?
        """
        
        company_info = await self.cache_manager.query_analytics(company_query, [siren])
        
        if not company_info:
            return AnalyticsResult(
                query_type="peer_comparison",
                data=[],
                metadata={"error": "Company not found"},
                executed_at=datetime.utcnow(),
                row_count=0,
                execution_time_ms=0
            )
        
        company = company_info[0]
        naf_code = naf_code or company.get("naf_code")
        department = department or company.get("department")
        
        # Find peers
        peer_query = """
        SELECT 
            siren,
            denomination,
            employee_range,
            revenue,
            creation_date,
            legal_form,
            (
                CASE 
                    WHEN employee_range = ? THEN 10
                    ELSE 0
                END +
                CASE 
                    WHEN department = ? THEN 5
                    ELSE 0
                END
            ) as similarity_score
        FROM companies
        WHERE naf_code = ?
            AND siren != ?
            AND is_active = true
        ORDER BY similarity_score DESC, revenue DESC
        LIMIT ?
        """
        
        params = [
            company.get("employee_range"),
            department,
            naf_code,
            siren,
            limit
        ]
        
        peers = await self.cache_manager.query_analytics(peer_query, params)
        
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return AnalyticsResult(
            query_type="peer_comparison",
            data=peers,
            metadata={
                "target_siren": siren,
                "naf_code": naf_code,
                "department": department,
                "company_info": company
            },
            executed_at=datetime.utcnow(),
            row_count=len(peers),
            execution_time_ms=execution_time
        )
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend from a series of values."""
        if len(values) < 2:
            return "insufficient_data"
        
        # Simple linear trend
        avg_change = sum(values[i] - values[i-1] for i in range(1, len(values))) / (len(values) - 1)
        
        if avg_change > 5:
            return "strong_growth"
        elif avg_change > 0:
            return "moderate_growth"
        elif avg_change > -5:
            return "stable"
        elif avg_change > -10:
            return "moderate_decline"
        else:
            return "strong_decline"


class MarketAnalyzer:
    """Analyzes market-wide data and trends."""
    
    def __init__(self):
        self.cache_manager = get_cache_manager()
        self.logger = logger.bind(component="market_analyzer")
    
    async def get_sector_statistics(
        self,
        naf_code: str,
        department: Optional[str] = None
    ) -> AnalyticsResult:
        """Get statistics for a business sector."""
        start_time = datetime.utcnow()
        
        query = """
        SELECT 
            COUNT(*) as company_count,
            COUNT(DISTINCT department) as geographic_spread,
            AVG(CAST(employee_count AS INTEGER)) as avg_employees,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY revenue) as median_revenue,
            AVG(revenue) as avg_revenue,
            SUM(CASE WHEN creation_date > CURRENT_DATE - INTERVAL '1 year' THEN 1 ELSE 0 END) as new_companies,
            SUM(CASE WHEN cessation_date > CURRENT_DATE - INTERVAL '1 year' THEN 1 ELSE 0 END) as ceased_companies,
            AVG(CASE WHEN is_active THEN 1 ELSE 0 END) * 100 as active_rate
        FROM companies
        WHERE naf_code = ?
        """
        
        params = [naf_code]
        
        if department:
            query += " AND department = ?"
            params.append(department)
        
        results = await self.cache_manager.query_analytics(query, params)
        
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return AnalyticsResult(
            query_type="sector_statistics",
            data=results,
            metadata={
                "naf_code": naf_code,
                "department": department,
                "analysis_date": datetime.utcnow().isoformat()
            },
            executed_at=datetime.utcnow(),
            row_count=len(results),
            execution_time_ms=execution_time
        )
    
    async def get_geographic_distribution(
        self,
        naf_code: Optional[str] = None,
        limit: int = 20
    ) -> AnalyticsResult:
        """Get geographic distribution of companies."""
        start_time = datetime.utcnow()
        
        query = """
        SELECT 
            department,
            COUNT(*) as company_count,
            AVG(CAST(employee_count AS INTEGER)) as avg_employees,
            SUM(revenue) as total_revenue,
            COUNT(DISTINCT naf_code) as sector_diversity
        FROM companies
        WHERE is_active = true
        """
        
        params = []
        
        if naf_code:
            query += " AND naf_code = ?"
            params.append(naf_code)
        
        query += """
        GROUP BY department
        ORDER BY company_count DESC
        LIMIT ?
        """
        params.append(limit)
        
        results = await self.cache_manager.query_analytics(query, params)
        
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return AnalyticsResult(
            query_type="geographic_distribution",
            data=results,
            metadata={
                "naf_code": naf_code,
                "limit": limit
            },
            executed_at=datetime.utcnow(),
            row_count=len(results),
            execution_time_ms=execution_time
        )
    
    async def get_creation_trends(
        self,
        months: int = 12,
        naf_code: Optional[str] = None,
        department: Optional[str] = None
    ) -> AnalyticsResult:
        """Analyze company creation trends."""
        start_time = datetime.utcnow()
        
        query = """
        SELECT 
            DATE_TRUNC('month', creation_date) as month,
            COUNT(*) as companies_created,
            AVG(CAST(capital AS FLOAT)) as avg_initial_capital,
            COUNT(DISTINCT naf_code) as sectors_represented
        FROM companies
        WHERE creation_date >= CURRENT_DATE - INTERVAL '? months'
        """
        
        params = [months]
        
        if naf_code:
            query += " AND naf_code = ?"
            params.append(naf_code)
        
        if department:
            query += " AND department = ?"
            params.append(department)
        
        query += """
        GROUP BY DATE_TRUNC('month', creation_date)
        ORDER BY month DESC
        """
        
        results = await self.cache_manager.query_analytics(query, params)
        
        # Calculate growth rate
        if len(results) >= 2:
            recent_avg = sum(r["companies_created"] for r in results[:3]) / 3
            older_avg = sum(r["companies_created"] for r in results[-3:]) / 3
            growth_rate = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
        else:
            growth_rate = 0
        
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return AnalyticsResult(
            query_type="creation_trends",
            data=results,
            metadata={
                "months_analyzed": months,
                "naf_code": naf_code,
                "department": department,
                "growth_rate": round(growth_rate, 2)
            },
            executed_at=datetime.utcnow(),
            row_count=len(results),
            execution_time_ms=execution_time
        )
    
    async def get_market_concentration(
        self,
        naf_code: str,
        metric: str = "revenue"  # revenue, employees, or establishments
    ) -> AnalyticsResult:
        """Calculate market concentration (HHI index)."""
        start_time = datetime.utcnow()
        
        # Get top companies and total market
        query = f"""
        WITH market_data AS (
            SELECT 
                siren,
                denomination,
                {metric} as metric_value,
                SUM({metric}) OVER () as total_market
            FROM companies
            WHERE naf_code = ?
                AND is_active = true
                AND {metric} IS NOT NULL
                AND {metric} > 0
        )
        SELECT 
            siren,
            denomination,
            metric_value,
            total_market,
            (metric_value::FLOAT / total_market) * 100 as market_share
        FROM market_data
        ORDER BY metric_value DESC
        LIMIT 50
        """
        
        params = [naf_code]
        results = await self.cache_manager.query_analytics(query, params)
        
        # Calculate HHI (Herfindahl-Hirschman Index)
        hhi = sum((r["market_share"] ** 2) for r in results)
        
        # Determine concentration level
        if hhi < 1500:
            concentration = "low"
        elif hhi < 2500:
            concentration = "moderate"
        else:
            concentration = "high"
        
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return AnalyticsResult(
            query_type="market_concentration",
            data=results[:10],  # Return top 10
            metadata={
                "naf_code": naf_code,
                "metric": metric,
                "hhi_index": round(hhi, 2),
                "concentration_level": concentration,
                "total_companies": len(results)
            },
            executed_at=datetime.utcnow(),
            row_count=len(results),
            execution_time_ms=execution_time
        )