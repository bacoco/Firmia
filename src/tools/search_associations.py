"""Associations search MCP tool implementation."""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime

from mcp.server.fastmcp import Tool
from pydantic import Field
from structlog import get_logger

from ..models.association import (
    SearchAssociationsInput,
    SearchAssociationsOutput,
    Association,
    AssociationDetails
)
from ..api import RNAAPI
from ..cache import get_cache_manager
from ..privacy import get_audit_logger

logger = get_logger(__name__)


class AssociationSearchOrchestrator:
    """Orchestrates association searches across RNA."""
    
    def __init__(self):
        self.rna_api = RNAAPI()
        self.cache_manager = get_cache_manager()
        self.audit_logger = get_audit_logger()
        self.logger = logger.bind(component="association_orchestrator")
    
    async def search_associations(
        self,
        params: SearchAssociationsInput,
        caller_id: str = "mcp_client",
        ip_address: Optional[str] = None
    ) -> SearchAssociationsOutput:
        """Search associations with caching."""
        start_time = datetime.utcnow()
        
        # Build cache key
        cache_key = self._build_cache_key(params)
        
        # Check cache first
        cached_results = await self.cache_manager.get_search_results(cache_key)
        if cached_results and not params.force_refresh:
            self.logger.info("association_cache_hit", cache_key=cache_key)
            return SearchAssociationsOutput(**cached_results)
        
        # Search RNA
        try:
            rna_results = await self.rna_api.search_associations(
                query=params.query,
                postal_code=params.postal_code,
                page=params.page,
                per_page=params.per_page
            )
            
            # Parse associations
            associations = self._parse_associations(rna_results["associations"])
            
            # Build result
            result = SearchAssociationsOutput(
                total_results=rna_results["total"],
                associations=associations,
                page=params.page,
                per_page=params.per_page,
                total_pages=(rna_results["total"] + params.per_page - 1) // params.per_page,
                query=params.query,
                filters_applied={
                    "postal_code": params.postal_code
                },
                metadata={
                    "source": "rna",
                    "search_time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    "cache_hit": False
                }
            )
            
            # Cache the results
            await self.cache_manager.set_search_results(
                cache_key,
                result.dict(),
                ttl=300  # 5 minutes for association searches
            )
            
            # Audit log
            await self.audit_logger.log_access(
                tool="search_associations",
                operation="search",
                caller_id=caller_id,
                siren=None,  # Associations might not have SIREN
                ip_address=ip_address,
                response_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                status_code=200,
                metadata={
                    "query": params.query,
                    "total_results": result.total_results,
                    "filters": result.filters_applied
                }
            )
            
            return result
            
        except Exception as e:
            self.logger.error("association_search_failed",
                            error=str(e),
                            params=params.dict())
            
            # Return empty result on error
            return SearchAssociationsOutput(
                total_results=0,
                associations=[],
                page=params.page,
                per_page=params.per_page,
                total_pages=0,
                query=params.query,
                filters_applied=params.dict(exclude={"query", "page", "per_page", "force_refresh"}),
                metadata={
                    "error": str(e),
                    "search_time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000)
                }
            )
    
    def _build_cache_key(self, params: SearchAssociationsInput) -> str:
        """Build cache key for association search."""
        key_parts = ["association_search", f"q:{params.query}"]
        
        if params.postal_code:
            key_parts.append(f"cp:{params.postal_code}")
        
        key_parts.extend([f"page:{params.page}", f"size:{params.per_page}"])
        
        return ":".join(key_parts)
    
    def _parse_associations(self, rna_associations: List[Dict[str, Any]]) -> List[Association]:
        """Parse RNA associations into model objects."""
        associations = []
        
        for assoc in rna_associations:
            try:
                association = Association(
                    rna_id=assoc["rna_id"],
                    siren=assoc.get("siren"),
                    siret=assoc.get("siret"),
                    name=assoc["name"],
                    short_name=assoc.get("short_name"),
                    object=assoc.get("object"),
                    is_active=assoc.get("is_active", True),
                    creation_date=assoc.get("creation_date"),
                    dissolution_date=assoc.get("dissolution_date"),
                    is_public_utility=assoc.get("is_public_utility", False),
                    address={
                        "street": assoc["address"].get("street"),
                        "postal_code": assoc["address"].get("postal_code"),
                        "city": assoc["address"].get("city"),
                        "country": assoc["address"].get("country", "France")
                    },
                    email=assoc.get("email"),
                    website=assoc.get("website"),
                    phone=assoc.get("phone")
                )
                
                associations.append(association)
                
            except Exception as e:
                self.logger.warning("association_parse_failed",
                                  rna_id=assoc.get("rna_id"),
                                  error=str(e))
        
        return associations
    
    async def get_association_details(
        self,
        identifier: str,
        identifier_type: str = "rna",
        caller_id: str = "mcp_client",
        ip_address: Optional[str] = None
    ) -> Optional[AssociationDetails]:
        """Get detailed association information."""
        start_time = datetime.utcnow()
        
        # Get association data
        if identifier_type == "rna":
            assoc_data = await self.rna_api.get_association_by_rna(identifier)
        elif identifier_type == "siren":
            assoc_data = await self.rna_api.get_association_by_siren(identifier)
        else:
            raise ValueError(f"Invalid identifier type: {identifier_type}")
        
        if not assoc_data:
            return None
        
        # Parse to detailed model
        details = AssociationDetails(
            rna_id=assoc_data["rna_id"],
            siren=assoc_data.get("siren"),
            siret=assoc_data.get("siret"),
            name=assoc_data["name"],
            short_name=assoc_data.get("short_name"),
            object=assoc_data.get("object"),
            object_social=assoc_data.get("object_social"),
            is_active=assoc_data.get("is_active", True),
            creation_date=assoc_data.get("creation_date"),
            declaration_date=assoc_data.get("declaration_date"),
            publication_date=assoc_data.get("publication_date"),
            dissolution_date=assoc_data.get("dissolution_date"),
            last_update=assoc_data.get("last_update"),
            type=assoc_data.get("type"),
            type_label=assoc_data.get("type_label"),
            is_public_utility=assoc_data.get("is_public_utility", False),
            is_alsace_moselle=assoc_data.get("is_alsace_moselle", False),
            regime=assoc_data.get("regime"),
            is_recognized=assoc_data.get("is_recognized", False),
            headquarters_address=assoc_data.get("headquarters_address"),
            management_address=assoc_data.get("management_address"),
            prefecture=assoc_data.get("prefecture"),
            sub_prefecture=assoc_data.get("sub_prefecture"),
            has_ccp=assoc_data.get("has_ccp", False),
            has_bank_account=assoc_data.get("has_bank_account", False),
            accepts_donations=assoc_data.get("accepts_donations", False),
            email=assoc_data.get("email"),
            website=assoc_data.get("website"),
            phone=assoc_data.get("phone"),
            members_count=assoc_data.get("members_count"),
            volunteers_count=assoc_data.get("volunteers_count"),
            employees_count=assoc_data.get("employees_count"),
            main_activity=assoc_data.get("main_activity"),
            secondary_activities=assoc_data.get("secondary_activities", [])
        )
        
        # Audit log
        await self.audit_logger.log_access(
            tool="search_associations",
            operation="get_details",
            caller_id=caller_id,
            siren=details.siren,
            ip_address=ip_address,
            response_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
            status_code=200,
            metadata={
                "identifier": identifier,
                "identifier_type": identifier_type,
                "rna_id": details.rna_id
            }
        )
        
        return details
    
    async def check_if_association(
        self,
        siren: str,
        caller_id: str = "mcp_client"
    ) -> Dict[str, Any]:
        """Check if a SIREN belongs to an association."""
        is_association = await self.rna_api.check_if_association(siren)
        
        result = {
            "siren": siren,
            "is_association": is_association,
            "source": "rna"
        }
        
        if is_association:
            # Get basic info
            assoc_data = await self.rna_api.get_association_by_siren(siren)
            if assoc_data:
                result.update({
                    "rna_id": assoc_data["rna_id"],
                    "name": assoc_data["name"],
                    "type": assoc_data.get("type_label", "Association")
                })
        
        return result
    
    async def close(self) -> None:
        """Close API clients."""
        await self.rna_api.close()


class SearchAssociationsTool(Tool):
    """MCP tool for searching associations."""
    
    name = "search_associations"
    description = "Search associations in the RNA (Répertoire National des Associations)"
    
    def __init__(self):
        super().__init__()
        self.orchestrator = AssociationSearchOrchestrator()
    
    async def run(
        self,
        query: str = Field(..., description="Search query (name, RNA ID, or SIREN)"),
        postal_code: Optional[str] = Field(None, description="Filter by postal code"),
        page: int = Field(1, ge=1, description="Page number"),
        per_page: int = Field(20, ge=1, le=100, description="Results per page")
    ) -> Dict[str, Any]:
        """Search associations."""
        # Build input model
        params = SearchAssociationsInput(
            query=query,
            postal_code=postal_code,
            page=page,
            per_page=per_page
        )
        
        # Execute search
        result = await self.orchestrator.search_associations(params)
        
        # Return as dict for MCP
        return result.dict()


class GetAssociationDetailsTool(Tool):
    """MCP tool for getting association details."""
    
    name = "get_association_details"
    description = "Get detailed information about an association"
    
    def __init__(self):
        super().__init__()
        self.orchestrator = AssociationSearchOrchestrator()
    
    async def run(
        self,
        identifier: str = Field(..., description="RNA ID (W123456789) or SIREN"),
        identifier_type: str = Field("rna", description="Type of identifier: 'rna' or 'siren'")
    ) -> Dict[str, Any]:
        """Get association details."""
        details = await self.orchestrator.get_association_details(
            identifier,
            identifier_type
        )
        
        if details:
            return details.dict()
        
        return {
            "error": "Association not found",
            "identifier": identifier,
            "identifier_type": identifier_type
        }


class CheckIfAssociationTool(Tool):
    """MCP tool for checking if a SIREN is an association."""
    
    name = "check_if_association"
    description = "Check if a SIREN belongs to an association"
    
    def __init__(self):
        super().__init__()
        self.orchestrator = AssociationSearchOrchestrator()
    
    async def run(
        self,
        siren: str = Field(..., description="Company SIREN (9 digits)", pattern="^[0-9]{9}$")
    ) -> Dict[str, Any]:
        """Check if SIREN is an association."""
        return await self.orchestrator.check_if_association(siren)