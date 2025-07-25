"""Company analytics MCP tool implementation."""

from typing import Optional, Dict, Any, List
from datetime import datetime

from fastmcp import Tool
from pydantic import Field
from structlog import get_logger

from ..analytics import CompanyAnalyzer, MarketAnalyzer, HealthScoreCalculator, TrendAnalyzer
from ..tools.get_company_profile import GetCompanyProfileTool
from ..privacy import get_audit_logger

logger = get_logger(__name__)


class GetCompanyHealthScoreTool(Tool):
    """MCP tool for calculating company health scores."""
    
    name = "get_company_health_score"
    description = "Calculate comprehensive health score with risk assessment and recommendations"
    
    def __init__(self):
        super().__init__()
        self.health_calculator = HealthScoreCalculator()
        self.profile_tool = GetCompanyProfileTool()
        self.audit_logger = get_audit_logger()
        self.logger = logger.bind(component="health_score_tool")
    
    async def run(
        self,
        siren: str = Field(..., description="Company SIREN (9 digits)", pattern="^[0-9]{9}$"),
        include_predictions: bool = Field(False, description="Include future predictions")
    ) -> Dict[str, Any]:
        """Calculate company health score."""
        start_time = datetime.utcnow()
        
        # Get company profile first
        profile_result = await self.profile_tool.run(
            siren=siren,
            include_establishments=True,
            include_financials=True,
            include_certifications=True
        )
        
        if not profile_result or not profile_result.get("company"):
            return {
                "error": "Company not found",
                "siren": siren
            }
        
        # Convert to Company model
        from ..models.company import Company
        company = Company(**profile_result["company"])
        
        # Calculate health score
        health_score = await self.health_calculator.calculate_health_score(
            company,
            include_predictions=include_predictions
        )
        
        # Audit log
        await self.audit_logger.log_access(
            tool="get_company_health_score",
            operation="calculate",
            caller_id="mcp_client",
            siren=siren,
            ip_address=None,
            response_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
            status_code=200,
            metadata={
                "overall_score": health_score.overall_score,
                "overall_status": health_score.overall_status,
                "include_predictions": include_predictions
            }
        )
        
        # Return as dict
        return {
            "siren": health_score.siren,
            "overall_score": health_score.overall_score,
            "overall_status": health_score.overall_status,
            "metrics": [
                {
                    "name": m.name,
                    "value": m.value,
                    "weight": m.weight,
                    "status": m.status,
                    "details": m.details
                }
                for m in health_score.metrics
            ],
            "risk_factors": health_score.risk_factors,
            "positive_factors": health_score.positive_factors,
            "recommendations": health_score.recommendations,
            "calculated_at": health_score.calculated_at.isoformat(),
            "data_sources": health_score.data_sources
        }


class GetCompanyAnalyticsTool(Tool):
    """MCP tool for company-specific analytics."""
    
    name = "get_company_analytics"
    description = "Get detailed analytics for a specific company (timeline, financials, peers)"
    
    def __init__(self):
        super().__init__()
        self.company_analyzer = CompanyAnalyzer()
        self.logger = logger.bind(component="company_analytics_tool")
    
    async def run(
        self,
        siren: str = Field(..., description="Company SIREN (9 digits)", pattern="^[0-9]{9}$"),
        analysis_type: str = Field(..., description="Type: timeline, financial_evolution, peer_comparison"),
        years: Optional[int] = Field(5, description="Years to analyze (for financial_evolution)"),
        event_types: Optional[List[str]] = Field(None, description="Event types to filter (for timeline)"),
        limit: Optional[int] = Field(10, description="Number of peers to return")
    ) -> Dict[str, Any]:
        """Get company analytics."""
        
        if analysis_type == "timeline":
            result = await self.company_analyzer.get_company_timeline(
                siren=siren,
                event_types=event_types
            )
        
        elif analysis_type == "financial_evolution":
            result = await self.company_analyzer.get_financial_evolution(
                siren=siren,
                years=years or 5
            )
        
        elif analysis_type == "peer_comparison":
            result = await self.company_analyzer.get_peer_comparison(
                siren=siren,
                limit=limit or 10
            )
        
        else:
            return {
                "error": f"Unknown analysis type: {analysis_type}",
                "valid_types": ["timeline", "financial_evolution", "peer_comparison"]
            }
        
        return {
            "query_type": result.query_type,
            "data": result.data,
            "metadata": result.metadata,
            "row_count": result.row_count,
            "execution_time_ms": result.execution_time_ms,
            "executed_at": result.executed_at.isoformat()
        }


class GetMarketAnalyticsTool(Tool):
    """MCP tool for market-wide analytics."""
    
    name = "get_market_analytics"
    description = "Get market analytics (sector stats, geographic distribution, trends)"
    
    def __init__(self):
        super().__init__()
        self.market_analyzer = MarketAnalyzer()
        self.logger = logger.bind(component="market_analytics_tool")
    
    async def run(
        self,
        analysis_type: str = Field(..., description="Type: sector_stats, geographic, creation_trends, concentration"),
        naf_code: Optional[str] = Field(None, description="NAF code for sector analysis"),
        department: Optional[str] = Field(None, description="Department code filter"),
        months: Optional[int] = Field(12, description="Months to analyze (for trends)"),
        metric: Optional[str] = Field("revenue", description="Metric for concentration (revenue/employees)")
    ) -> Dict[str, Any]:
        """Get market analytics."""
        
        if analysis_type == "sector_stats":
            if not naf_code:
                return {"error": "naf_code required for sector statistics"}
            
            result = await self.market_analyzer.get_sector_statistics(
                naf_code=naf_code,
                department=department
            )
        
        elif analysis_type == "geographic":
            result = await self.market_analyzer.get_geographic_distribution(
                naf_code=naf_code,
                limit=20
            )
        
        elif analysis_type == "creation_trends":
            result = await self.market_analyzer.get_creation_trends(
                months=months or 12,
                naf_code=naf_code,
                department=department
            )
        
        elif analysis_type == "concentration":
            if not naf_code:
                return {"error": "naf_code required for market concentration"}
            
            result = await self.market_analyzer.get_market_concentration(
                naf_code=naf_code,
                metric=metric or "revenue"
            )
        
        else:
            return {
                "error": f"Unknown analysis type: {analysis_type}",
                "valid_types": ["sector_stats", "geographic", "creation_trends", "concentration"]
            }
        
        return {
            "query_type": result.query_type,
            "data": result.data,
            "metadata": result.metadata,
            "row_count": result.row_count,
            "execution_time_ms": result.execution_time_ms,
            "executed_at": result.executed_at.isoformat()
        }


class GetTrendAnalysisTool(Tool):
    """MCP tool for trend analysis."""
    
    name = "get_trend_analysis"
    description = "Analyze trends in business data with forecasting and seasonality detection"
    
    def __init__(self):
        super().__init__()
        self.trend_analyzer = TrendAnalyzer()
        self.logger = logger.bind(component="trend_analysis_tool")
    
    async def run(
        self,
        naf_code: str = Field(..., description="NAF code for sector"),
        metrics: Optional[List[str]] = Field(
            ["company_count", "avg_revenue", "avg_employees"],
            description="Metrics to analyze"
        ),
        period_months: int = Field(24, description="Months of history to analyze")
    ) -> Dict[str, Any]:
        """Analyze trends."""
        
        # Analyze trends
        trend_results = await self.trend_analyzer.analyze_sector_trends(
            naf_code=naf_code,
            metrics=metrics or ["company_count", "avg_revenue", "avg_employees"],
            period_months=period_months
        )
        
        # Convert to serializable format
        output = {}
        for metric, analysis in trend_results.items():
            output[metric] = {
                "direction": analysis.direction,
                "change_percent": round(analysis.change_percent, 2),
                "volatility": round(analysis.volatility, 2),
                "data_points": [
                    {
                        "timestamp": p.timestamp.isoformat(),
                        "value": p.value
                    }
                    for p in analysis.data_points
                ],
                "forecast": analysis.forecast,
                "seasonality": analysis.seasonality,
                "anomalies": analysis.anomalies
            }
        
        # Also check for emerging sectors
        emerging = await self.trend_analyzer.identify_emerging_sectors()
        
        return {
            "naf_code": naf_code,
            "period_months": period_months,
            "trend_analysis": output,
            "emerging_sectors": emerging[:5]  # Top 5
        }


class UpdateStaticDataTool(Tool):
    """MCP tool for manually triggering static data updates."""
    
    name = "update_static_data"
    description = "Manually trigger update of static datasets (SIRENE, BODACC, etc.)"
    
    def __init__(self):
        super().__init__()
        from ..pipeline.scheduler import get_pipeline_scheduler
        self.scheduler = get_pipeline_scheduler()
        self.logger = logger.bind(component="update_static_data_tool")
    
    async def run(
        self,
        dataset: Optional[str] = Field(None, description="Specific dataset to update (or 'all')"),
        force: bool = Field(False, description="Force update even if recently updated")
    ) -> Dict[str, Any]:
        """Update static data."""
        
        if dataset == "all" or dataset is None:
            # Update all datasets
            self.logger.info("updating_all_datasets", force=force)
            results = await self.scheduler.force_update_all()
            
            return {
                "status": "completed",
                "datasets_updated": len(results),
                "results": results
            }
        
        else:
            # Update specific dataset
            if dataset not in self.scheduler.jobs:
                return {
                    "error": f"Unknown dataset: {dataset}",
                    "available_datasets": list(self.scheduler.jobs.keys())
                }
            
            self.logger.info("updating_dataset", dataset=dataset, force=force)
            result = await self.scheduler.run_job_now(dataset)
            
            return {
                "status": "completed",
                "dataset": dataset,
                "result": result
            }


class GetPipelineStatusTool(Tool):
    """MCP tool for checking data pipeline status."""
    
    name = "get_pipeline_status"
    description = "Get status of data pipeline and scheduled jobs"
    
    def __init__(self):
        super().__init__()
        from ..pipeline.scheduler import get_pipeline_scheduler
        self.scheduler = get_pipeline_scheduler()
    
    async def run(self) -> Dict[str, Any]:
        """Get pipeline status."""
        jobs_status = self.scheduler.get_all_jobs_status()
        
        return {
            "pipeline_running": self.scheduler._running,
            "total_jobs": len(jobs_status),
            "jobs": jobs_status,
            "server_time": datetime.utcnow().isoformat()
        }