"""Environmental certifications check MCP tool implementation."""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime

from pydantic import Field
from structlog import get_logger

from ..models.certification import (
    CheckCertificationsInput,
    CheckCertificationsOutput,
    Certification,
    CertificationStatus
)
from ..api import RGEAPI
from ..cache import get_cache_manager
from ..privacy import get_audit_logger

logger = get_logger(__name__)


class CertificationCheckOrchestrator:
    """Orchestrates certification checks across RGE and other sources."""
    
    def __init__(self):
        self.rge_api = RGEAPI()
        self.cache_manager = get_cache_manager()
        self.audit_logger = get_audit_logger()
        self.logger = logger.bind(component="certification_orchestrator")
    
    async def check_certifications(
        self,
        params: CheckCertificationsInput,
        caller_id: str = "mcp_client",
        ip_address: Optional[str] = None
    ) -> CheckCertificationsOutput:
        """Check company certifications."""
        start_time = datetime.utcnow()
        
        # Build cache key
        cache_key = f"certifications:{params.siren}"
        
        # Check cache first
        cached_results = await self.cache_manager.get_certifications(cache_key)
        if cached_results and not params.force_refresh:
            self.logger.info("certification_cache_hit", siren=params.siren)
            return CheckCertificationsOutput(**cached_results)
        
        # Get RGE certifications
        rge_status = await self.rge_api.check_certification_status(params.siren)
        
        # Parse certifications
        certifications = self._parse_certifications(rge_status.get("certifications", []))
        
        # Build result
        result = CheckCertificationsOutput(
            siren=params.siren,
            has_certifications=len(certifications) > 0,
            certifications=certifications,
            certification_summary={
                "rge": {
                    "certified": rge_status.get("is_rge_certified", False),
                    "domains": rge_status.get("certification_domains", []),
                    "active_count": rge_status.get("active_certifications", 0),
                    "next_expiry": rge_status.get("next_expiry")
                },
                "bio": False,  # Would need additional API
                "ess": False,  # Would need additional API
                "qualiopi": False  # Would need additional API
            },
            metadata={
                "source": "rge",
                "check_time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                "cache_hit": False
            }
        )
        
        # Cache the results
        await self.cache_manager.set_certifications(
            cache_key,
            result.dict(),
            ttl=3600  # 1 hour for certifications
        )
        
        # Audit log
        await self.audit_logger.log_access(
            tool="check_certifications",
            operation="check",
            caller_id=caller_id,
            siren=params.siren,
            ip_address=ip_address,
            response_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
            status_code=200,
            metadata={
                "has_certifications": result.has_certifications,
                "certification_count": len(result.certifications)
            }
        )
        
        return result
    
    def _parse_certifications(self, rge_certifications: List[Dict[str, Any]]) -> List[Certification]:
        """Parse RGE certifications into model objects."""
        certifications = []
        
        for cert in rge_certifications:
            try:
                certification = Certification(
                    type="RGE",
                    code=cert["code"],
                    name=cert["name"],
                    certifying_body=cert["certifying_body"],
                    validity_start=None,  # RGE doesn't provide start date
                    validity_end=cert.get("validity_date"),
                    is_valid=cert.get("is_valid", False),
                    domain=cert.get("domain"),
                    competencies=[
                        {"code": c["code"], "label": c["label"]} 
                        for c in cert.get("competencies", [])
                    ],
                    metadata={
                        "meta_domain": cert.get("meta_domain"),
                        "source": "rge"
                    }
                )
                
                certifications.append(certification)
                
            except Exception as e:
                self.logger.warning("certification_parse_failed",
                                  cert_code=cert.get("code"),
                                  error=str(e))
        
        return certifications
    
    async def search_certified_companies(
        self,
        params: Dict[str, Any],
        caller_id: str = "mcp_client",
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search for certified companies."""
        start_time = datetime.utcnow()
        
        # Search RGE
        results = await self.rge_api.search_certified_companies(
            query=params.get("query"),
            postal_code=params.get("postal_code"),
            certification_domain=params.get("domain"),
            certification_type=params.get("certification_type"),
            limit=params.get("per_page", 20),
            offset=(params.get("page", 1) - 1) * params.get("per_page", 20)
        )
        
        # Audit log
        await self.audit_logger.log_access(
            tool="check_certifications",
            operation="search",
            caller_id=caller_id,
            siren=None,
            ip_address=ip_address,
            response_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
            status_code=200,
            metadata={
                "total_results": results["total"],
                "filters": params
            }
        )
        
        return results
    
    async def close(self) -> None:
        """Close API clients."""
        await self.rge_api.close()


class CheckCertificationsTool(Tool):
    """MCP tool for checking company certifications."""
    
    name = "check_certifications"
    description = "Check environmental and quality certifications (RGE, Bio, ESS, Qualiopi)"
    
    def __init__(self):
        super().__init__()
        self.orchestrator = CertificationCheckOrchestrator()
    
    async def run(
        self,
        siren: str = Field(..., description="Company SIREN (9 digits)", pattern="^[0-9]{9}$"),
        force_refresh: bool = Field(False, description="Force refresh from source")
    ) -> Dict[str, Any]:
        """Check company certifications."""
        # Build input model
        params = CheckCertificationsInput(
            siren=siren,
            force_refresh=force_refresh
        )
        
        # Execute check
        result = await self.orchestrator.check_certifications(params)
        
        # Return as dict for MCP
        return result.dict()


class SearchCertifiedCompaniesTool(Tool):
    """MCP tool for searching certified companies."""
    
    name = "search_certified_companies"
    description = "Search companies with specific certifications (RGE, etc.)"
    
    def __init__(self):
        super().__init__()
        self.orchestrator = CertificationCheckOrchestrator()
    
    async def run(
        self,
        query: Optional[str] = Field(None, description="Search query"),
        postal_code: Optional[str] = Field(None, description="Filter by postal code"),
        domain: Optional[str] = Field(None, description="Certification domain (ENR, ISOLATION, etc.)"),
        certification_type: Optional[str] = Field(None, description="Certification type (QUALIBAT, QUALIT'ENR, etc.)"),
        page: int = Field(1, ge=1, description="Page number"),
        per_page: int = Field(20, ge=1, le=100, description="Results per page")
    ) -> Dict[str, Any]:
        """Search certified companies."""
        params = {
            "query": query,
            "postal_code": postal_code,
            "domain": domain,
            "certification_type": certification_type,
            "page": page,
            "per_page": per_page
        }
        
        # Execute search
        return await self.orchestrator.search_certified_companies(params)


class GetCertificationDomainsTool(Tool):
    """MCP tool for getting certification domains and types."""
    
    name = "get_certification_domains"
    description = "Get available certification domains and types"
    
    def __init__(self):
        super().__init__()
        self.rge_api = RGEAPI()
    
    async def run(self) -> Dict[str, Any]:
        """Get certification domains and types."""
        return {
            "domains": self.rge_api.get_domain_labels(),
            "certification_types": self.rge_api.get_certification_types(),
            "description": "RGE certification domains and types available for search"
        }