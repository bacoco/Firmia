"""Legal announcements search MCP tool implementation."""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, date

from fastmcp import Tool
from pydantic import Field
from structlog import get_logger

from ..models.announcement import (
    SearchAnnouncementsInput,
    SearchAnnouncementsOutput,
    LegalAnnouncement,
    AnnouncementType
)
from ..api import BODACCAPI
from ..cache import get_cache_manager
from ..privacy import get_audit_logger

logger = get_logger(__name__)


class AnnouncementSearchOrchestrator:
    """Orchestrates legal announcement searches across BODACC."""
    
    def __init__(self):
        self.bodacc_api = BODACCAPI()
        self.cache_manager = get_cache_manager()
        self.audit_logger = get_audit_logger()
        self.logger = logger.bind(component="announcement_orchestrator")
    
    async def search_announcements(
        self,
        params: SearchAnnouncementsInput,
        caller_id: str = "mcp_client",
        ip_address: Optional[str] = None
    ) -> SearchAnnouncementsOutput:
        """Search legal announcements with caching."""
        start_time = datetime.utcnow()
        
        # Build cache key
        cache_key = self._build_cache_key(params)
        
        # Check cache first
        cached_results = await self.cache_manager.get_search_results(cache_key)
        if cached_results and not params.force_refresh:
            self.logger.info("announcement_cache_hit", cache_key=cache_key)
            return SearchAnnouncementsOutput(**cached_results)
        
        # Search BODACC
        try:
            bodacc_results = await self.bodacc_api.search_announcements(
                siren=params.siren,
                denomination=params.company_name,
                announcement_type=params.announcement_type.value if params.announcement_type else None,
                date_from=params.date_from,
                date_to=params.date_to,
                limit=params.per_page,
                offset=(params.page - 1) * params.per_page
            )
            
            # Parse announcements
            announcements = self._parse_announcements(bodacc_results["announcements"])
            
            # Build result
            result = SearchAnnouncementsOutput(
                total_results=bodacc_results["total"],
                announcements=announcements,
                page=params.page,
                per_page=params.per_page,
                total_pages=(bodacc_results["total"] + params.per_page - 1) // params.per_page,
                filters_applied={
                    "siren": params.siren,
                    "company_name": params.company_name,
                    "announcement_type": params.announcement_type.value if params.announcement_type else None,
                    "date_from": params.date_from.isoformat() if params.date_from else None,
                    "date_to": params.date_to.isoformat() if params.date_to else None
                },
                metadata={
                    "source": "bodacc",
                    "search_time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "cache_hit": False
                }
            )
            
            # Cache the results
            await self.cache_manager.set_search_results(
                cache_key,
                result.dict(),
                ttl=300  # 5 minutes for announcement searches
            )
            
            # Audit log
            await self.audit_logger.log_access(
                tool="search_legal_announcements",
                operation="search",
                caller_id=caller_id,
                siren=params.siren,
                ip_address=ip_address,
                response_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                status_code=200,
                metadata={
                    "total_results": result.total_results,
                    "filters": result.filters_applied
                }
            )
            
            return result
            
        except Exception as e:
            self.logger.error("announcement_search_failed",
                            error=str(e),
                            params=params.dict())
            
            # Return empty result on error
            return SearchAnnouncementsOutput(
                total_results=0,
                announcements=[],
                page=params.page,
                per_page=params.per_page,
                total_pages=0,
                filters_applied=params.dict(exclude_unset=True),
                metadata={
                    "error": str(e),
                    "search_time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000)
                }
            )
    
    def _build_cache_key(self, params: SearchAnnouncementsInput) -> str:
        """Build cache key for announcement search."""
        key_parts = ["announcement_search"]
        
        if params.siren:
            key_parts.append(f"siren:{params.siren}")
        if params.company_name:
            key_parts.append(f"name:{params.company_name}")
        if params.announcement_type:
            key_parts.append(f"type:{params.announcement_type.value}")
        if params.date_from:
            key_parts.append(f"from:{params.date_from.isoformat()}")
        if params.date_to:
            key_parts.append(f"to:{params.date_to.isoformat()}")
        
        key_parts.extend([f"page:{params.page}", f"size:{params.per_page}"])
        
        return ":".join(key_parts)
    
    def _parse_announcements(self, bodacc_announcements: List[Dict[str, Any]]) -> List[LegalAnnouncement]:
        """Parse BODACC announcements into model objects."""
        announcements = []
        
        for ann in bodacc_announcements:
            try:
                # Map BODACC type to enum
                type_mapping = {
                    "A": AnnouncementType.VENTE_CESSION,
                    "B": AnnouncementType.CREATION_ETABLISSEMENT,
                    "C": AnnouncementType.PROCEDURE_COLLECTIVE,
                    "D": AnnouncementType.DEPOT_COMPTES,
                    "P": AnnouncementType.RECTIFICATIF
                }
                
                announcement = LegalAnnouncement(
                    id=ann["id"],
                    type=type_mapping.get(ann["type"], AnnouncementType.AUTRE),
                    type_label=ann["type_label"],
                    publication_date=ann["publication_date"],
                    bodacc_number=ann["bodacc_number"],
                    court=ann.get("court"),
                    siren=ann.get("siren"),
                    company_name=ann.get("denomination"),
                    title=ann.get("title"),
                    content=ann.get("content"),
                    pdf_url=ann.get("pdf_url")
                )
                
                announcements.append(announcement)
                
            except Exception as e:
                self.logger.warning("announcement_parse_failed",
                                  announcement_id=ann.get("id"),
                                  error=str(e))
        
        return announcements
    
    async def get_company_timeline(
        self,
        siren: str,
        caller_id: str = "mcp_client",
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get chronological timeline of announcements for a company."""
        start_time = datetime.utcnow()
        
        # Get all announcements
        timeline = await self.bodacc_api.get_company_timeline(siren, limit=100)
        
        # Group by year
        timeline_by_year = {}
        for event in timeline:
            if event["date"]:
                year = event["date"][:4]
                if year not in timeline_by_year:
                    timeline_by_year[year] = []
                timeline_by_year[year].append(event)
        
        # Audit log
        await self.audit_logger.log_access(
            tool="search_legal_announcements",
            operation="timeline",
            caller_id=caller_id,
            siren=siren,
            ip_address=ip_address,
            response_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
            status_code=200,
            metadata={
                "total_events": len(timeline),
                "years_covered": list(timeline_by_year.keys())
            }
        )
        
        return {
            "siren": siren,
            "total_announcements": len(timeline),
            "timeline": timeline,
            "by_year": timeline_by_year,
            "has_collective_procedures": any(
                e["type"] == "C" for e in timeline
            )
        }
    
    async def check_financial_health(
        self,
        siren: str,
        caller_id: str = "mcp_client"
    ) -> Dict[str, Any]:
        """Check company financial health based on legal announcements."""
        return await self.bodacc_api.check_financial_health(siren)
    
    async def close(self) -> None:
        """Close API clients."""
        await self.bodacc_api.close()


class SearchLegalAnnouncementsTool(Tool):
    """MCP tool for searching legal announcements."""
    
    name = "search_legal_announcements"
    description = "Search official legal announcements from BODACC (bankruptcy, sales, procedures)"
    
    def __init__(self):
        super().__init__()
        self.orchestrator = AnnouncementSearchOrchestrator()
    
    async def run(
        self,
        siren: Optional[str] = Field(None, description="Company SIREN (9 digits)", pattern="^[0-9]{9}$"),
        company_name: Optional[str] = Field(None, description="Company name to search"),
        announcement_type: Optional[str] = Field(None, description="Type: vente_cession, creation_etablissement, procedure_collective, depot_comptes, rectificatif"),
        date_from: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)"),
        date_to: Optional[str] = Field(None, description="End date (YYYY-MM-DD)"),
        page: int = Field(1, ge=1, description="Page number"),
        per_page: int = Field(20, ge=1, le=100, description="Results per page")
    ) -> Dict[str, Any]:
        """Search legal announcements."""
        # Map string type to enum
        type_enum = None
        if announcement_type:
            type_mapping = {
                "vente_cession": AnnouncementType.VENTE_CESSION,
                "creation_etablissement": AnnouncementType.CREATION_ETABLISSEMENT,
                "procedure_collective": AnnouncementType.PROCEDURE_COLLECTIVE,
                "depot_comptes": AnnouncementType.DEPOT_COMPTES,
                "rectificatif": AnnouncementType.RECTIFICATIF
            }
            type_enum = type_mapping.get(announcement_type)
        
        # Parse dates
        date_from_obj = date.fromisoformat(date_from) if date_from else None
        date_to_obj = date.fromisoformat(date_to) if date_to else None
        
        # Build input model
        params = SearchAnnouncementsInput(
            siren=siren,
            company_name=company_name,
            announcement_type=type_enum,
            date_from=date_from_obj,
            date_to=date_to_obj,
            page=page,
            per_page=per_page
        )
        
        # Execute search
        result = await self.orchestrator.search_announcements(params)
        
        # Return as dict for MCP
        return result.dict()


class GetAnnouncementTimelineTool(Tool):
    """MCP tool for getting company announcement timeline."""
    
    name = "get_announcement_timeline"
    description = "Get chronological timeline of all legal announcements for a company"
    
    def __init__(self):
        super().__init__()
        self.orchestrator = AnnouncementSearchOrchestrator()
    
    async def run(
        self,
        siren: str = Field(..., description="Company SIREN (9 digits)", pattern="^[0-9]{9}$")
    ) -> Dict[str, Any]:
        """Get announcement timeline."""
        return await self.orchestrator.get_company_timeline(siren)


class CheckFinancialHealthTool(Tool):
    """MCP tool for checking financial health via legal announcements."""
    
    name = "check_financial_health"
    description = "Check company financial health based on legal announcements (bankruptcy, procedures)"
    
    def __init__(self):
        super().__init__()
        self.orchestrator = AnnouncementSearchOrchestrator()
    
    async def run(
        self,
        siren: str = Field(..., description="Company SIREN (9 digits)", pattern="^[0-9]{9}$")
    ) -> Dict[str, Any]:
        """Check financial health."""
        return await self.orchestrator.check_financial_health(siren)