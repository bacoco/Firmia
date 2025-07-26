"""Demo Firmia MCP server with mock implementations for testing."""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
from datetime import datetime
import random

from fastmcp import FastMCP
from structlog import get_logger

from .config import settings
from .logging_config import setup_logging

# Initialize logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Manage server lifecycle."""
    logger.info("starting_firmia_demo_server", 
                version="0.1.0-demo",
                environment=settings.environment)
    
    yield
    
    logger.info("shutting_down_firmia_demo_server")


# Create the MCP server
mcp = FastMCP(
    name="Firmia Demo",
    version="0.1.0-demo"
)

# Configure the MCP server with lifespan
mcp.lifespan = lifespan


# =============================================================================
# MOCK DATA GENERATORS
# =============================================================================

def generate_mock_company(siren: str = None) -> Dict[str, Any]:
    """Generate mock company data."""
    if not siren:
        siren = str(random.randint(100000000, 999999999))
    
    company_names = ["Tech Innovate", "Data Solutions", "Green Energy", "Smart Systems", "Digital Services"]
    cities = ["Paris", "Lyon", "Marseille", "Toulouse", "Bordeaux"]
    
    return {
        "siren": siren,
        "siret": siren + "00014",
        "nom_complet": f"{random.choice(company_names)} SAS",
        "nom_commercial": random.choice(company_names),
        "siege": {
            "adresse": f"{random.randint(1, 100)} Rue de la République",
            "code_postal": f"{random.randint(10, 95)}000",
            "ville": random.choice(cities)
        },
        "date_creation": f"{random.randint(2000, 2023)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
        "effectif": random.choice(["1-10", "11-50", "51-200", "201-500", "500+"]),
        "forme_juridique": "SAS",
        "capital_social": random.randint(1000, 100000),
        "naf_code": "6201Z",
        "naf_libelle": "Programmation informatique"
    }


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
    """Search for French companies and associations (DEMO - returns mock data)."""
    
    # Generate mock results
    results = []
    total = random.randint(50, 200)
    
    for i in range(min(per_page, total - (page - 1) * per_page)):
        company = generate_mock_company()
        company["score"] = random.uniform(0.7, 1.0)
        company["source"] = random.choice(["recherche_entreprises", "insee", "inpi"])
        results.append(company)
    
    return {
        "results": results,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page
        },
        "demo_mode": True
    }


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
    """Search BODACC legal announcements (DEMO - returns mock data)."""
    
    announcement_types = ["IMMATRICULATION", "MODIFICATION", "RADIATION", "PROCEDURE_COLLECTIVE", "VENTE"]
    
    results = []
    total = random.randint(20, 100)
    
    for i in range(min(per_page, total - (page - 1) * per_page)):
        announcement = {
            "id": f"BODACC-{random.randint(1000000, 9999999)}",
            "type": announcement_type or random.choice(announcement_types),
            "date_publication": f"2024-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
            "company": generate_mock_company(),
            "description": "Mock announcement description",
            "tribunal": "Tribunal de Commerce de Paris"
        }
        results.append(announcement)
    
    return {
        "results": results,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page
        },
        "demo_mode": True
    }


@mcp.tool()
async def search_associations(
    query: str,
    department: Optional[str] = None,
    page: int = 1,
    per_page: int = 20
) -> Dict[str, Any]:
    """Search RNA for associations (DEMO - returns mock data)."""
    
    results = []
    total = random.randint(10, 50)
    
    for i in range(min(per_page, total - (page - 1) * per_page)):
        association = {
            "rna_id": f"W{random.randint(100000000, 999999999)}",
            "titre": f"Association {query} {i+1}",
            "objet": "Association à but non lucratif",
            "date_creation": f"{random.randint(1990, 2023)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
            "siege": {
                "adresse": f"{random.randint(1, 100)} Avenue des Associations",
                "code_postal": department + "000" if department else "75000",
                "ville": "Paris"
            },
            "is_active": True
        }
        results.append(association)
    
    return {
        "results": results,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page
        },
        "demo_mode": True
    }


@mcp.tool()
async def search_certified_companies(
    certification_type: str,
    department: Optional[str] = None,
    activity_domain: Optional[str] = None,
    page: int = 1,
    per_page: int = 20
) -> Dict[str, Any]:
    """Find RGE certified companies (DEMO - returns mock data)."""
    
    results = []
    total = random.randint(20, 100)
    
    for i in range(min(per_page, total - (page - 1) * per_page)):
        company = generate_mock_company()
        company["certifications"] = [{
            "type": certification_type,
            "domain": activity_domain or "ISOLATION",
            "valid_from": "2023-01-01",
            "valid_until": "2025-12-31",
            "certificate_number": f"RGE-{random.randint(100000, 999999)}"
        }]
        results.append(company)
    
    return {
        "results": results,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page
        },
        "demo_mode": True
    }


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
    """Get company profile (DEMO - returns mock data)."""
    
    if not siren or len(siren) != 9 or not siren.isdigit():
        raise ValueError("Invalid SIREN format. Must be 9 digits.")
    
    profile = generate_mock_company(siren)
    
    if include_establishments:
        profile["establishments"] = [
            {
                "siret": siren + f"{i:05d}",
                "type": "Principal" if i == 14 else "Secondaire",
                "adresse": f"{random.randint(1, 100)} Rue Filiale {i}",
                "ville": random.choice(["Paris", "Lyon", "Marseille"]),
                "is_active": True
            }
            for i in [14, 21, 35]
        ]
    
    if include_financials:
        profile["financials"] = {
            "chiffre_affaires": random.randint(100000, 10000000),
            "resultat_net": random.randint(-50000, 500000),
            "effectif": random.randint(1, 500),
            "year": 2023
        }
    
    if include_officials:
        profile["officials"] = [
            {
                "nom": "Dupont",
                "prenom": "Jean",
                "fonction": "Président",
                "date_nomination": "2020-01-15"
            }
        ]
    
    profile["data_sources"] = ["recherche_entreprises", "insee", "inpi"]
    profile["last_updated"] = datetime.utcnow().isoformat()
    profile["demo_mode"] = True
    
    return profile


@mcp.tool()
async def get_company_analytics(
    siren: str,
    include_timeline: bool = True,
    include_financial_evolution: bool = True,
    include_employee_evolution: bool = True,
    include_peer_comparison: bool = True
) -> Dict[str, Any]:
    """Get company analytics (DEMO - returns mock data)."""
    
    analytics = {
        "siren": siren,
        "company_name": f"Demo Company {siren}",
        "demo_mode": True
    }
    
    if include_timeline:
        analytics["timeline"] = [
            {
                "date": f"{year}-01-01",
                "event": random.choice(["Capital increase", "New establishment", "CEO change"]),
                "details": "Mock event details"
            }
            for year in range(2020, 2024)
        ]
    
    if include_financial_evolution:
        analytics["financial_evolution"] = {
            "years": [2020, 2021, 2022, 2023],
            "revenue": [random.randint(500000, 2000000) for _ in range(4)],
            "profit": [random.randint(-100000, 300000) for _ in range(4)]
        }
    
    if include_employee_evolution:
        analytics["employee_evolution"] = {
            "years": [2020, 2021, 2022, 2023],
            "count": [random.randint(10, 100) for _ in range(4)]
        }
    
    if include_peer_comparison:
        analytics["peer_comparison"] = {
            "company_rank": random.randint(1, 100),
            "total_peers": 500,
            "metrics": {
                "revenue_percentile": random.randint(40, 90),
                "growth_percentile": random.randint(30, 80),
                "profitability_percentile": random.randint(20, 95)
            }
        }
    
    return analytics


@mcp.tool()
async def get_company_health_score(
    siren: str,
    include_details: bool = True,
    include_recommendations: bool = True,
    include_predictions: bool = False
) -> Dict[str, Any]:
    """Get company health score (DEMO - returns mock data)."""
    
    score = random.randint(40, 95)
    
    result = {
        "siren": siren,
        "company_name": f"Demo Company {siren}",
        "health_score": score,
        "risk_level": "LOW" if score > 70 else "MEDIUM" if score > 40 else "HIGH",
        "demo_mode": True
    }
    
    if include_details:
        result["score_breakdown"] = {
            "financial_health": random.randint(30, 100),
            "operational_efficiency": random.randint(40, 100),
            "market_position": random.randint(35, 100),
            "growth_trajectory": random.randint(25, 100)
        }
    
    if include_recommendations:
        result["recommendations"] = [
            "Improve cash flow management",
            "Diversify customer base",
            "Invest in digital transformation"
        ][:random.randint(1, 3)]
    
    if include_predictions:
        result["predictions"] = {
            "6_month_outlook": random.choice(["STABLE", "IMPROVING", "DECLINING"]),
            "12_month_outlook": random.choice(["STABLE", "IMPROVING", "UNCERTAIN"]),
            "confidence": random.uniform(0.6, 0.9)
        }
    
    return result


# =============================================================================
# SIMPLE TOOLS FOR REMAINING FUNCTIONALITY
# =============================================================================

@mcp.tool()
async def get_association_details(rna_id: str) -> Dict[str, Any]:
    """Get association details (DEMO)."""
    return {
        "rna_id": rna_id,
        "titre": f"Association Demo {rna_id}",
        "objet": "Association à but non lucratif - Demo",
        "date_creation": "2010-05-15",
        "is_active": True,
        "demo_mode": True
    }


@mcp.tool()
async def check_if_association(siren: str) -> Dict[str, Any]:
    """Check if SIREN is an association (DEMO)."""
    is_association = random.choice([True, False])
    return {
        "siren": siren,
        "is_association": is_association,
        "association_details": {
            "rna_id": f"W{siren}",
            "titre": f"Association {siren}"
        } if is_association else None,
        "demo_mode": True
    }


@mcp.tool()
async def check_certifications(siren: str) -> Dict[str, Any]:
    """Check company certifications (DEMO)."""
    has_certifications = random.choice([True, False])
    return {
        "siren": siren,
        "has_certifications": has_certifications,
        "certifications": [
            {
                "type": "RGE",
                "domain": "ISOLATION",
                "valid_until": "2025-12-31"
            }
        ] if has_certifications else [],
        "demo_mode": True
    }


@mcp.tool()
async def download_document(
    siren: str,
    document_type: str,
    year: Optional[int] = None
) -> Dict[str, Any]:
    """Download document (DEMO - returns mock URL)."""
    return {
        "siren": siren,
        "document_type": document_type,
        "year": year or 2023,
        "download_url": f"https://demo.firmia.fr/documents/{siren}/{document_type}_{year or 2023}.pdf",
        "expires_at": (datetime.utcnow().timestamp() + 3600),
        "demo_mode": True
    }


@mcp.tool()
async def list_documents(siren: str) -> Dict[str, Any]:
    """List available documents (DEMO)."""
    return {
        "siren": siren,
        "available": ["KBIS", "BILAN", "STATUTS"],
        "requires_auth": [],
        "demo_mode": True
    }


@mcp.tool()
async def get_announcement_timeline(
    siren: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """Get announcement timeline (DEMO)."""
    return {
        "siren": siren,
        "timeline": [
            {
                "date": f"2024-{m:02d}-15",
                "type": random.choice(["MODIFICATION", "IMMATRICULATION"]),
                "description": f"Mock announcement {m}"
            }
            for m in range(1, 6)
        ],
        "demo_mode": True
    }


@mcp.tool()
async def check_financial_health(siren: str) -> Dict[str, Any]:
    """Check financial health (DEMO)."""
    has_procedures = random.choice([True, False])
    return {
        "siren": siren,
        "has_collective_procedures": has_procedures,
        "procedure_count": random.randint(1, 3) if has_procedures else 0,
        "risk_level": "HIGH" if has_procedures else "LOW",
        "checked_at": datetime.utcnow().isoformat(),
        "demo_mode": True
    }


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
    """Get market analytics (DEMO)."""
    return {
        "naf_code": naf_code or "6201Z",
        "department": department,
        "total_companies": random.randint(1000, 10000),
        "sector_stats": {
            "average_revenue": random.randint(100000, 1000000),
            "average_employees": random.randint(5, 50),
            "growth_rate": random.uniform(-5, 15)
        } if include_sector_stats else None,
        "demo_mode": True
    }


@mcp.tool()
async def get_trend_analysis(
    topic: str,
    period: str = "12M",
    include_forecast: bool = True
) -> Dict[str, Any]:
    """Get trend analysis (DEMO)."""
    return {
        "topic": topic,
        "period": period,
        "trend": random.choice(["INCREASING", "STABLE", "DECREASING"]),
        "change_percentage": random.uniform(-10, 20),
        "forecast": {
            "next_6_months": random.choice(["UP", "STABLE", "DOWN"]),
            "confidence": random.uniform(0.6, 0.9)
        } if include_forecast else None,
        "demo_mode": True
    }


@mcp.tool()
async def get_certification_domains() -> Dict[str, Any]:
    """Get certification domains (DEMO)."""
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
        },
        "demo_mode": True
    }


@mcp.tool()
async def export_data(
    data_type: str,
    format: str = "json",
    query: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Export data (DEMO)."""
    return {
        "export_id": f"demo_export_{datetime.utcnow().timestamp()}",
        "format": format,
        "data_type": data_type,
        "status": "completed",
        "download_url": f"/demo/exports/{data_type}_{format}",
        "expires_at": (datetime.utcnow().timestamp() + 3600),
        "demo_mode": True
    }


@mcp.tool()
async def batch_operation(
    operation: str,
    items: List[Dict[str, Any]],
    parallel: bool = True,
    max_workers: int = 10
) -> Dict[str, Any]:
    """Batch operation (DEMO)."""
    return {
        "operation": operation,
        "total_items": len(items),
        "successful": len(items),
        "failed": 0,
        "results": [{"success": True, "demo": True} for _ in items],
        "execution_time": f"{random.uniform(0.5, 2.0):.2f}s",
        "demo_mode": True
    }


@mcp.tool()
async def update_static_data(
    dataset: Optional[str] = None,
    force: bool = False
) -> Dict[str, Any]:
    """Update static data (DEMO)."""
    return {
        "dataset": dataset or "ALL",
        "status": "completed",
        "records_processed": random.randint(10000, 100000),
        "duration": f"{random.uniform(30, 120):.1f}s",
        "demo_mode": True
    }


@mcp.tool()
async def get_pipeline_status() -> Dict[str, Any]:
    """Get pipeline status (DEMO)."""
    return {
        "datasets": {
            "SIRENE_STOCK": {
                "last_update": "2024-01-15T03:00:00Z",
                "records": 5000000,
                "status": "healthy"
            },
            "BODACC": {
                "last_update": "2024-01-20T02:00:00Z",
                "records": 1500000,
                "status": "healthy"
            }
        },
        "scheduler": {
            "status": "running",
            "next_run": "2024-01-21T03:00:00Z"
        },
        "demo_mode": True
    }


@mcp.tool()
async def health_check() -> Dict[str, Any]:
    """Check server health."""
    return {
        "status": "healthy",
        "version": "0.1.0-demo",
        "environment": settings.environment,
        "auth_status": {
            "all_services": "demo_mode"
        },
        "cache_status": "demo_mode",
        "tools_available": 23,
        "demo_mode": True
    }


# Main entry point
def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()