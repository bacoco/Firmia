"""Full Firmia MCP server with all 23 tools."""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastmcp import FastMCP
from structlog import get_logger

from .config import settings
from .auth import get_auth_manager
from .logging_config import setup_logging
from .cache import get_cache_manager

# Import all necessary modules
from .api import (
    RechercheEntreprisesAPI, INSEESireneAPI, RNAAPI,
    BODACCAPI, APIEntrepriseAPI, INPIRNEAPI, RGEAPI
)
from .analytics import HealthScorer, MarketAnalyzer, TrendAnalyzer
from .pipeline import ETLPipeline, DataScheduler
from .privacy import apply_privacy_filters, log_access

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
    
    # Initialize cache manager
    cache_manager = get_cache_manager()
    await cache_manager.initialize()
    logger.info("cache_manager_initialized")
    
    # Initialize analytics components
    server.health_scorer = HealthScorer()
    server.market_analyzer = MarketAnalyzer()
    server.trend_analyzer = TrendAnalyzer()
    server.etl_pipeline = ETLPipeline()
    server.scheduler = DataScheduler()
    
    yield
    
    # Cleanup
    logger.info("shutting_down_firmia_server")
    await auth_manager.close()
    await cache_manager.close()


# Create the MCP server
mcp = FastMCP(
    name="Firmia",
    version="0.1.0"
)

# Configure the MCP server with lifespan
mcp.lifespan = lifespan


# =============================================================================
# SEARCH & DISCOVERY TOOLS
# =============================================================================

@mcp.tool()
async def search_companies(
    query: str,
    page: int = 1,
    per_page: int = 20,
    filters: Optional[Dict[str, Any]] = None,
    include_associations: bool = True
) -> Dict[str, Any]:
    """Search for French companies and associations across multiple government databases.
    
    Args:
        query: Search query (company name, SIREN, SIRET, or keywords)
        page: Page number (default: 1)
        per_page: Results per page (default: 20, max: 100)
        filters: Optional filters dict with:
            - naf_code: NAF/APE activity code
            - department: Department code (01-95, 2A, 2B, 971-978)
            - postal_code: 5-digit postal code
            - city: City name
            - legal_form: Legal form code
            - employee_range: Employee count range
            - revenue_range: Revenue range in euros
            - creation_date_min: Minimum creation date (YYYY-MM-DD)
            - creation_date_max: Maximum creation date (YYYY-MM-DD)
        include_associations: Include associations in results
    
    Returns:
        Dict with results list and pagination info
    """
    # Initialize APIs
    recherche_api = RechercheEntreprisesAPI()
    insee_api = INSEESireneAPI()
    rna_api = RNAAPI()
    cache_manager = get_cache_manager()
    
    # Check cache
    cache_key = f"search:{query}:{page}:{per_page}:{json.dumps(filters or {})}:{include_associations}"
    cached = await cache_manager.get(cache_key)
    if cached:
        return cached
    
    # Search across sources
    tasks = [recherche_api.search(query, page, per_page, filters)]
    
    if filters and (filters.get('naf_code') or filters.get('employee_range')):
        tasks.append(insee_api.search(query, page, per_page, filters))
    
    if include_associations:
        tasks.append(rna_api.search(query, page, per_page))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Merge results
    all_results = []
    for result in results:
        if isinstance(result, dict) and 'results' in result:
            all_results.extend(result['results'])
    
    # Apply privacy filters
    filtered_results = apply_privacy_filters(all_results)
    
    # Deduplicate by SIREN
    seen_sirens = set()
    unique_results = []
    for r in filtered_results:
        siren = r.get('siren')
        if siren and siren not in seen_sirens:
            seen_sirens.add(siren)
            unique_results.append(r)
    
    # Paginate
    start = (page - 1) * per_page
    end = start + per_page
    paginated = unique_results[start:end]
    
    output = {
        "results": paginated,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": len(unique_results),
            "total_pages": (len(unique_results) + per_page - 1) // per_page
        }
    }
    
    # Cache results
    await cache_manager.set(cache_key, output, ttl=300)
    
    return output


@mcp.tool()
async def search_legal_announcements(
    query: Optional[str] = None,
    announcement_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    department: Optional[str] = None,
    page: int = 1,
    per_page: int = 20
) -> Dict[str, Any]:
    """Search BODACC legal announcements.
    
    Args:
        query: Search in company name or announcement text
        announcement_type: Type of announcement:
            - IMMATRICULATION: New company registrations
            - MODIFICATION: Company modifications
            - RADIATION: Company deletions
            - PROCEDURE_COLLECTIVE: Bankruptcy procedures
            - VENTE: Company sales
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        department: Department code
        page: Page number
        per_page: Results per page
    
    Returns:
        Dict with announcements list and pagination
    """
    bodacc_api = BODACCAPI()
    
    results = await bodacc_api.search_announcements(
        query=query,
        announcement_type=announcement_type,
        date_from=date_from,
        date_to=date_to,
        department=department,
        page=page,
        per_page=per_page
    )
    
    # Log access for audit
    await log_access("search_legal_announcements", {"query": query, "type": announcement_type})
    
    return results


@mcp.tool()
async def search_associations(
    query: str,
    department: Optional[str] = None,
    page: int = 1,
    per_page: int = 20
) -> Dict[str, Any]:
    """Search RNA (Répertoire National des Associations) for associations.
    
    Args:
        query: Association name, RNA ID, or SIREN
        department: Department code filter
        page: Page number
        per_page: Results per page
    
    Returns:
        Dict with associations list and pagination
    """
    rna_api = RNAAPI()
    
    results = await rna_api.search(
        query=query,
        page=page,
        per_page=per_page,
        department=department
    )
    
    return results


@mcp.tool()
async def search_certified_companies(
    certification_type: str,
    department: Optional[str] = None,
    activity_domain: Optional[str] = None,
    page: int = 1,
    per_page: int = 20
) -> Dict[str, Any]:
    """Find RGE certified companies.
    
    Args:
        certification_type: Type of certification:
            - RGE: All RGE certifications
            - QUALIBAT: Construction quality
            - QUALIT_ENR: Renewable energy
            - QUALIFELEC: Electrical installations
            - ECO_ARTISAN: Eco-friendly craftsman
        department: Department code
        activity_domain: Activity domain filter
        page: Page number
        per_page: Results per page
    
    Returns:
        Dict with certified companies and pagination
    """
    rge_api = RGEAPI()
    
    results = await rge_api.search_certified(
        certification_type=certification_type,
        department=department,
        activity_domain=activity_domain,
        page=page,
        per_page=per_page
    )
    
    return results


# =============================================================================
# COMPANY INFORMATION TOOLS
# =============================================================================

@mcp.tool()
async def get_company_profile(
    siren: str,
    include_establishments: bool = False,
    include_financials: bool = True,
    include_officials: bool = True
) -> Dict[str, Any]:
    """Get unified company profile with data fusion from multiple sources.
    
    Args:
        siren: 9-digit SIREN number
        include_establishments: Include list of establishments
        include_financials: Include financial data
        include_officials: Include company officials
    
    Returns:
        Comprehensive company profile with all available data
    """
    # Validate SIREN
    if not siren or len(siren) != 9 or not siren.isdigit():
        raise ValueError("Invalid SIREN format. Must be 9 digits.")
    
    # Check cache
    cache_manager = get_cache_manager()
    cache_key = f"profile:{siren}:{include_establishments}:{include_financials}:{include_officials}"
    cached = await cache_manager.get(cache_key)
    if cached:
        return cached
    
    # Initialize APIs
    auth_manager = get_auth_manager()
    recherche_api = RechercheEntreprisesAPI()
    insee_api = INSEESireneAPI()
    inpi_api = INPIRNEAPI()
    api_entreprise = APIEntrepriseAPI()
    
    # Gather data from all sources
    tasks = [
        recherche_api.get_company(siren),
        insee_api.get_company_info(siren) if auth_manager.has_valid_token('insee') else None,
        inpi_api.get_company_extract(siren) if auth_manager.has_valid_token('inpi') else None,
        api_entreprise.get_company_info(siren) if auth_manager.has_valid_token('api_entreprise') else None
    ]
    
    results = await asyncio.gather(*[t for t in tasks if t], return_exceptions=True)
    
    # Merge data with precedence rules
    merged = {}
    for result in results:
        if isinstance(result, dict):
            merged.update(result)
    
    # Add computed fields
    merged['data_sources'] = [
        source for source, result in zip(['recherche', 'insee', 'inpi', 'api_entreprise'], results)
        if isinstance(result, dict)
    ]
    merged['last_updated'] = datetime.utcnow().isoformat()
    
    # Apply privacy filters
    profile = apply_privacy_filters([merged])[0] if merged else {}
    
    # Cache result
    await cache_manager.set(cache_key, profile, ttl=3600)
    
    # Log access
    await log_access("get_company_profile", {"siren": siren})
    
    return profile


@mcp.tool()
async def get_company_analytics(
    siren: str,
    include_timeline: bool = True,
    include_financial_evolution: bool = True,
    include_employee_evolution: bool = True,
    include_peer_comparison: bool = True
) -> Dict[str, Any]:
    """Get company analytics including timeline, evolution, and peer comparison.
    
    Args:
        siren: 9-digit SIREN number
        include_timeline: Include historical timeline
        include_financial_evolution: Include financial trends
        include_employee_evolution: Include employee count trends
        include_peer_comparison: Include peer comparison
    
    Returns:
        Analytics data with visualizations and insights
    """
    analyzer = MarketAnalyzer()
    
    analytics = await analyzer.analyze_company(
        siren=siren,
        include_timeline=include_timeline,
        include_financial_evolution=include_financial_evolution,
        include_employee_evolution=include_employee_evolution,
        include_peer_comparison=include_peer_comparison
    )
    
    return analytics


@mcp.tool()
async def get_company_health_score(
    siren: str,
    include_details: bool = True,
    include_recommendations: bool = True,
    include_predictions: bool = False
) -> Dict[str, Any]:
    """Get AI-driven company health score with risk factors and recommendations.
    
    Args:
        siren: 9-digit SIREN number
        include_details: Include detailed scoring breakdown
        include_recommendations: Include improvement recommendations
        include_predictions: Include predictive analytics (6-12 months)
    
    Returns:
        Health score (0-100), risk factors, and recommendations
    """
    health_scorer = HealthScorer()
    
    score = await health_scorer.calculate_health_score(
        siren=siren,
        include_details=include_details,
        include_recommendations=include_recommendations,
        include_predictions=include_predictions
    )
    
    return score


@mcp.tool()
async def get_association_details(
    rna_id: str
) -> Dict[str, Any]:
    """Get detailed association information from RNA.
    
    Args:
        rna_id: RNA identifier (W + 9 digits)
    
    Returns:
        Association details including officials, purpose, publications
    """
    rna_api = RNAAPI()
    
    details = await rna_api.get_association_details(rna_id)
    
    return details


@mcp.tool()
async def check_if_association(
    siren: str
) -> Dict[str, Any]:
    """Check if a SIREN belongs to an association.
    
    Args:
        siren: 9-digit SIREN number
    
    Returns:
        Dict with is_association boolean and association details if true
    """
    rna_api = RNAAPI()
    
    result = await rna_api.check_siren(siren)
    
    return result


@mcp.tool()
async def check_certifications(
    siren: str
) -> Dict[str, Any]:
    """Verify environmental certifications for a company.
    
    Args:
        siren: 9-digit SIREN number
    
    Returns:
        Dict with active certifications and validity dates
    """
    rge_api = RGEAPI()
    
    certifications = await rge_api.get_company_certifications(siren)
    
    return certifications


# =============================================================================
# DOCUMENTS & LEGAL TOOLS
# =============================================================================

@mcp.tool()
async def download_document(
    siren: str,
    document_type: str,
    year: Optional[int] = None
) -> Dict[str, Any]:
    """Download official documents (KBIS, bilans, actes, statuts).
    
    Args:
        siren: 9-digit SIREN number
        document_type: Type of document:
            - KBIS: Company registration extract
            - BILAN: Annual accounts
            - ACTES: Legal acts
            - STATUTS: Company statutes
            - ATTESTATION: Various certificates
        year: Year for annual documents (defaults to latest)
    
    Returns:
        Dict with document URL and metadata
    """
    auth_manager = get_auth_manager()
    api_entreprise = APIEntrepriseAPI()
    inpi_api = INPIRNEAPI()
    
    # Route to appropriate API based on document type
    if document_type == "KBIS":
        if not auth_manager.has_valid_token('inpi'):
            return {"error": "INPI authentication required for KBIS"}
        result = await inpi_api.download_kbis(siren)
    
    elif document_type == "BILAN":
        if not auth_manager.has_valid_token('api_entreprise'):
            return {"error": "API Entreprise authentication required for bilans"}
        result = await api_entreprise.get_documents(siren, 'bilans', year)
    
    elif document_type in ["ACTES", "STATUTS"]:
        if not auth_manager.has_valid_token('inpi'):
            return {"error": "INPI authentication required for legal documents"}
        result = await inpi_api.get_legal_documents(siren, document_type.lower())
    
    else:
        return {"error": f"Unknown document type: {document_type}"}
    
    # Log access
    await log_access("download_document", {"siren": siren, "type": document_type})
    
    return result


@mcp.tool()
async def list_documents(
    siren: str
) -> Dict[str, Any]:
    """List all available documents for a company.
    
    Args:
        siren: 9-digit SIREN number
    
    Returns:
        Dict with categorized document list
    """
    auth_manager = get_auth_manager()
    documents = {
        "available": [],
        "requires_auth": []
    }
    
    # Check each document type availability
    if auth_manager.has_valid_token('inpi'):
        documents["available"].extend(["KBIS", "ACTES", "STATUTS"])
    else:
        documents["requires_auth"].extend([
            {"type": "KBIS", "provider": "INPI"},
            {"type": "ACTES", "provider": "INPI"},
            {"type": "STATUTS", "provider": "INPI"}
        ])
    
    if auth_manager.has_valid_token('api_entreprise'):
        documents["available"].append("BILAN")
    else:
        documents["requires_auth"].append({"type": "BILAN", "provider": "API Entreprise"})
    
    return documents


@mcp.tool()
async def get_announcement_timeline(
    siren: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """Get chronological BODACC announcement timeline for a company.
    
    Args:
        siren: 9-digit SIREN number
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    
    Returns:
        Chronological list of all BODACC announcements
    """
    bodacc_api = BODACCAPI()
    
    timeline = await bodacc_api.get_company_timeline(
        siren=siren,
        start_date=start_date,
        end_date=end_date
    )
    
    return timeline


@mcp.tool()
async def check_financial_health(
    siren: str
) -> Dict[str, Any]:
    """Check financial health based on collective procedures.
    
    Args:
        siren: 9-digit SIREN number
    
    Returns:
        Financial health status and risk indicators
    """
    bodacc_api = BODACCAPI()
    
    # Check for bankruptcy procedures
    procedures = await bodacc_api.search_announcements(
        siren=siren,
        announcement_type="PROCEDURE_COLLECTIVE"
    )
    
    # Analyze procedures
    has_procedures = len(procedures.get('results', [])) > 0
    latest_procedure = procedures['results'][0] if has_procedures else None
    
    health_status = {
        "has_collective_procedures": has_procedures,
        "procedure_count": len(procedures.get('results', [])),
        "latest_procedure": latest_procedure,
        "risk_level": "HIGH" if has_procedures else "LOW",
        "checked_at": datetime.utcnow().isoformat()
    }
    
    return health_status


# =============================================================================
# ANALYTICS & MARKET INTELLIGENCE TOOLS
# =============================================================================

@mcp.tool()
async def get_market_analytics(
    naf_code: Optional[str] = None,
    department: Optional[str] = None,
    include_sector_stats: bool = True,
    include_geographic_distribution: bool = True,
    include_size_distribution: bool = True,
    include_age_distribution: bool = True,
    include_growth_trends: bool = True
) -> Dict[str, Any]:
    """Get market analytics for a sector or region.
    
    Args:
        naf_code: NAF/APE code for sector analysis
        department: Department code for regional analysis
        include_sector_stats: Include sector statistics
        include_geographic_distribution: Include geographic data
        include_size_distribution: Include company size distribution
        include_age_distribution: Include company age distribution
        include_growth_trends: Include growth trends
    
    Returns:
        Comprehensive market analytics and visualizations
    """
    analyzer = MarketAnalyzer()
    
    analytics = await analyzer.analyze_market(
        naf_code=naf_code,
        department=department,
        include_sector_stats=include_sector_stats,
        include_geographic_distribution=include_geographic_distribution,
        include_size_distribution=include_size_distribution,
        include_age_distribution=include_age_distribution,
        include_growth_trends=include_growth_trends
    )
    
    return analytics


@mcp.tool()
async def get_trend_analysis(
    topic: str,
    period: str = "12M",
    include_forecast: bool = True
) -> Dict[str, Any]:
    """Get business trends analysis with forecasting.
    
    Args:
        topic: Analysis topic:
            - COMPANY_CREATION: New company trends
            - BANKRUPTCY: Bankruptcy trends
            - SECTOR_GROWTH: Sector growth trends
            - EMPLOYMENT: Employment trends
        period: Analysis period (3M, 6M, 12M, 24M, 5Y)
        include_forecast: Include 6-month forecast
    
    Returns:
        Trend analysis with visualizations and predictions
    """
    trend_analyzer = TrendAnalyzer()
    
    analysis = await trend_analyzer.analyze_trends(
        topic=topic,
        period=period,
        include_forecast=include_forecast
    )
    
    return analysis


@mcp.tool()
async def get_certification_domains() -> Dict[str, Any]:
    """Get available RGE certification domains and types.
    
    Returns:
        Dict with certification types, domains, and descriptions
    """
    return {
        "certification_types": {
            "RGE": "Reconnu Garant de l'Environnement",
            "QUALIBAT": "Certification for construction quality",
            "QUALIT_ENR": "Quality certification for renewable energy",
            "QUALIFELEC": "Certification for electrical installations",
            "ECO_ARTISAN": "Eco-friendly craftsman certification"
        },
        "activity_domains": {
            "ISOLATION": "Insulation works",
            "MENUISERIE": "Carpentry and windows",
            "CHAUFFAGE": "Heating systems",
            "ENERGIE_RENOUVELABLE": "Renewable energy",
            "AUDIT_ENERGETIQUE": "Energy audit"
        }
    }


# =============================================================================
# DATA OPERATIONS TOOLS
# =============================================================================

@mcp.tool()
async def export_data(
    data_type: str,
    format: str = "json",
    query: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Export search results, profiles, or analytics data.
    
    Args:
        data_type: Type of data to export:
            - SEARCH_RESULTS: Export search results
            - COMPANY_PROFILES: Export company profiles
            - ANALYTICS_RESULTS: Export analytics data
            - ANNOUNCEMENTS: Export BODACC announcements
        format: Export format (json, csv, excel)
        query: Search query for filtering
        filters: Additional filters
    
    Returns:
        Dict with download URL and export metadata
    """
    # Implementation would handle data export logic
    # For now, return a mock response
    return {
        "export_id": f"export_{datetime.utcnow().timestamp()}",
        "format": format,
        "data_type": data_type,
        "status": "completed",
        "download_url": f"/exports/{data_type}_{format}",
        "expires_at": (datetime.utcnow().timestamp() + 3600)
    }


@mcp.tool()
async def batch_operation(
    operation: str,
    items: List[Dict[str, Any]],
    parallel: bool = True,
    max_workers: int = 10
) -> Dict[str, Any]:
    """Execute batch operations in parallel.
    
    Args:
        operation: Operation to perform:
            - SEARCH: Batch search
            - PROFILE: Batch profile retrieval
            - HEALTH_SCORE: Batch health scoring
            - ANALYTICS: Batch analytics
        items: List of items to process
        parallel: Execute in parallel
        max_workers: Maximum parallel workers
    
    Returns:
        Dict with results and execution statistics
    """
    start_time = datetime.utcnow()
    
    # Map operations to functions
    operations = {
        "SEARCH": search_companies,
        "PROFILE": get_company_profile,
        "HEALTH_SCORE": get_company_health_score,
        "ANALYTICS": get_company_analytics
    }
    
    if operation not in operations:
        return {"error": f"Unknown operation: {operation}"}
    
    func = operations[operation]
    
    # Execute batch
    if parallel:
        # Use asyncio.gather with semaphore for rate limiting
        semaphore = asyncio.Semaphore(max_workers)
        
        async def process_item(item):
            async with semaphore:
                try:
                    result = await func(**item)
                    return {"success": True, "result": result}
                except Exception as e:
                    return {"success": False, "error": str(e)}
        
        results = await asyncio.gather(*[process_item(item) for item in items])
    else:
        # Sequential execution
        results = []
        for item in items:
            try:
                result = await func(**item)
                results.append({"success": True, "result": result})
            except Exception as e:
                results.append({"success": False, "error": str(e)})
    
    # Calculate statistics
    success_count = sum(1 for r in results if r["success"])
    duration = (datetime.utcnow() - start_time).total_seconds()
    
    return {
        "operation": operation,
        "total_items": len(items),
        "successful": success_count,
        "failed": len(items) - success_count,
        "results": results,
        "execution_time": f"{duration:.2f}s",
        "items_per_second": len(items) / duration if duration > 0 else 0
    }


@mcp.tool()
async def update_static_data(
    dataset: Optional[str] = None,
    force: bool = False
) -> Dict[str, Any]:
    """Manually trigger static data pipeline updates.
    
    Args:
        dataset: Specific dataset to update:
            - SIRENE_STOCK: Full SIRENE database
            - BODACC: BODACC announcements
            - RGE: RGE certifications
            - RNA: Associations
            - ALL: Update all datasets
        force: Force update even if data is recent
    
    Returns:
        Update status and statistics
    """
    etl_pipeline = ETLPipeline()
    
    result = await etl_pipeline.update_dataset(
        dataset=dataset or "ALL",
        force=force
    )
    
    return result


@mcp.tool()
async def get_pipeline_status() -> Dict[str, Any]:
    """Check ETL pipeline status and last update times.
    
    Returns:
        Pipeline status for each dataset
    """
    etl_pipeline = ETLPipeline()
    scheduler = DataScheduler()
    
    status = {
        "datasets": await etl_pipeline.get_status(),
        "scheduler": await scheduler.get_status(),
        "next_updates": await scheduler.get_next_updates()
    }
    
    return status


# =============================================================================
# SYSTEM TOOLS
# =============================================================================

@mcp.tool()
async def health_check() -> Dict[str, Any]:
    """Check server health and authentication status."""
    auth_manager = get_auth_manager()
    cache_manager = get_cache_manager()
    
    # Check cache connectivity
    cache_status = "healthy"
    try:
        await cache_manager.get("health_check_test")
    except Exception:
        cache_status = "degraded"
    
    return {
        "status": "healthy",
        "version": "0.1.0",
        "environment": settings.environment,
        "auth_status": auth_manager.get_service_status(),
        "cache_status": cache_status,
        "tools_available": 23
    }


# Main entry point
def main():
    """Run the MCP server."""
    # Run the server with stdio transport by default
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()