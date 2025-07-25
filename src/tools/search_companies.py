"""Multi-source company search MCP tool implementation."""

import asyncio
from typing import List, Dict, Any, Optional, Set
from datetime import datetime

from mcp.server.fastmcp import Tool
from pydantic import Field
from structlog import get_logger

from ..models.company import (
    SearchCompaniesInput, 
    SearchCompaniesOutput,
    CompanySearchResult,
    Pagination
)
from ..api import RechercheEntreprisesAPI, INSEESireneAPI, RNAAPI
from ..cache import get_cache_manager
from ..privacy import apply_privacy_filters

logger = get_logger(__name__)


class CompanySearchOrchestrator:
    """Orchestrates search across multiple API sources."""
    
    def __init__(self):
        self.recherche_api = RechercheEntreprisesAPI()
        self.insee_api = INSEESireneAPI()
        self.rna_api = RNAAPI()
        self.cache_manager = get_cache_manager()
        self.logger = logger.bind(component="search_orchestrator")
    
    async def search_all_sources(
        self,
        params: SearchCompaniesInput
    ) -> SearchCompaniesOutput:
        """Search across all available sources and merge results."""
        # Check cache first
        cache_key = self._generate_cache_key(params)
        cached_result = await self.cache_manager.get_search_result(params.dict())
        
        if cached_result:
            self.logger.info("search_cache_hit", query=params.query)
            return SearchCompaniesOutput(**cached_result)
        
        # Prepare search tasks
        tasks = []
        
        # Always search Recherche Entreprises (no auth, fast)
        tasks.append(self._search_recherche_entreprises(params))
        
        # Search INSEE if more comprehensive results needed
        if params.filters and (params.filters.naf_code or params.filters.employee_range):
            tasks.append(self._search_insee(params))
        
        # Search static DuckDB data if available
        tasks.append(self._search_static_data(params))
        
        # Search associations if requested
        if params.include_associations:
            tasks.append(self._search_associations(params))
        
        # Execute searches in parallel
        self.logger.info("executing_parallel_search", 
                       query=params.query,
                       sources=len(tasks))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Merge and deduplicate results
        merged_results = self._merge_search_results(results, params)
        
        # Apply privacy filters
        filtered_results = self._apply_privacy_filters(merged_results)
        
        # Create output with pagination
        output = SearchCompaniesOutput(
            results=filtered_results,
            pagination=self._calculate_pagination(filtered_results, params)
        )
        
        # Cache results
        await self.cache_manager.set_search_result(
            params.dict(),
            output.dict(),
            ttl=300  # 5 minutes
        )
        
        return output
    
    async def _search_recherche_entreprises(
        self,
        params: SearchCompaniesInput
    ) -> Dict[str, Any]:
        """Search using Recherche Entreprises API."""
        try:
            result = await self.recherche_api.search(
                query=params.query,
                page=params.page,
                per_page=params.per_page,
                naf_code=params.filters.naf_code if params.filters else None,
                postal_code=params.filters.postal_code if params.filters else None,
                department=params.filters.department if params.filters else None,
                employee_range=params.filters.employee_range if params.filters else None,
                legal_status=params.filters.legal_status if params.filters else None
            )
            
            self.logger.info("recherche_entreprises_results",
                           count=len(result["results"]),
                           total=result["pagination"].total)
            
            return result
            
        except Exception as e:
            self.logger.error("recherche_entreprises_search_failed",
                            error=str(e))
            return {"results": [], "pagination": None}
    
    async def _search_insee(
        self,
        params: SearchCompaniesInput
    ) -> Dict[str, Any]:
        """Search using INSEE Sirene API."""
        try:
            # Build INSEE query
            query_parts = [params.query]
            
            if params.filters:
                if params.filters.naf_code:
                    query_parts.append(f"activitePrincipaleUniteLegale:{params.filters.naf_code}")
                if params.filters.postal_code:
                    query_parts.append(f"codePostalEtablissement:{params.filters.postal_code}")
                if params.filters.employee_range:
                    query_parts.append(f"trancheEffectifsUniteLegale:{params.filters.employee_range}")
            
            insee_query = " AND ".join(query_parts)
            
            result = await self.insee_api.search_companies(
                query=insee_query,
                page=params.page,
                per_page=params.per_page
            )
            
            # Convert INSEE format to our format
            converted_results = []
            for company in result["results"]:
                converted = CompanySearchResult(
                    siren=company["siren"],
                    siret=None,  # INSEE search returns legal units, not establishments
                    name=company["denomination"] or company["siren"],
                    legal_form=company["legal_form"]["label"] if company.get("legal_form") else None,
                    naf_code=company.get("naf_code"),
                    employee_range=company.get("employee_range"),
                    address=None,  # No address in legal unit search
                    creation_date=company.get("creation_date"),
                    is_active=company.get("is_active", True),
                    is_headquarters=None,
                    source="insee_sirene"
                )
                converted_results.append(converted)
            
            return {
                "results": converted_results,
                "pagination": result["pagination"]
            }
            
        except Exception as e:
            self.logger.error("insee_search_failed", error=str(e))
            return {"results": [], "pagination": None}
    
    async def _search_static_data(
        self,
        params: SearchCompaniesInput
    ) -> Dict[str, Any]:
        """Search in static DuckDB data."""
        try:
            companies = await self.cache_manager.search_companies_static(
                query=params.query,
                limit=params.per_page,
                offset=(params.page - 1) * params.per_page
            )
            
            # Convert to our format
            results = []
            for company in companies:
                result = CompanySearchResult(
                    siren=company["siren"],
                    siret=None,
                    name=company["denomination"] or company["siren"],
                    legal_form=company.get("legal_form"),
                    naf_code=company.get("naf_code"),
                    employee_range=company.get("employee_range"),
                    address=None,
                    creation_date=company.get("creation_date"),
                    is_active=company.get("cessation_date") is None,
                    is_headquarters=None,
                    source="sirene"  # Static data source
                )
                results.append(result)
            
            return {
                "results": results,
                "pagination": {
                    "total": len(results),  # Approximate
                    "page": params.page,
                    "per_page": params.per_page,
                    "total_pages": 1
                }
            }
            
        except Exception as e:
            self.logger.error("static_data_search_failed", error=str(e))
            return {"results": [], "pagination": None}
    
    def _merge_search_results(
        self,
        results: List[Any],
        params: SearchCompaniesInput
    ) -> List[CompanySearchResult]:
        """Merge and deduplicate results from multiple sources."""
        merged_map: Dict[str, CompanySearchResult] = {}
        seen_sirens: Set[str] = set()
        
        # Process each source's results
        for source_result in results:
            if isinstance(source_result, Exception):
                continue
            
            if not isinstance(source_result, dict) or "results" not in source_result:
                continue
            
            for company in source_result["results"]:
                if isinstance(company, CompanySearchResult):
                    siren = company.siren
                    
                    # Deduplicate by SIREN
                    if siren and siren not in seen_sirens:
                        seen_sirens.add(siren)
                        merged_map[siren] = company
                    elif siren in merged_map:
                        # Merge data from multiple sources
                        existing = merged_map[siren]
                        merged_map[siren] = self._merge_company_data(existing, company)
        
        # Convert back to list and sort by relevance
        merged_list = list(merged_map.values())
        
        # Simple relevance scoring
        query_lower = params.query.lower()
        for company in merged_list:
            score = 0
            if company.name and query_lower in company.name.lower():
                score += 10
            if company.siren and company.siren.startswith(params.query):
                score += 5
            company.relevance_score = score  # type: ignore
        
        # Sort by relevance and name
        merged_list.sort(
            key=lambda x: (-getattr(x, 'relevance_score', 0), x.name or ''),
        )
        
        # Paginate results
        start_idx = (params.page - 1) * params.per_page
        end_idx = start_idx + params.per_page
        
        return merged_list[start_idx:end_idx]
    
    def _merge_company_data(
        self,
        existing: CompanySearchResult,
        new_data: CompanySearchResult
    ) -> CompanySearchResult:
        """Merge data from multiple sources for the same company."""
        # Priority: INPI RNE > INSEE > Recherche Entreprises > RNA > Static
        source_priority = {
            "inpi_rne": 5,
            "insee_sirene": 4,
            "recherche_entreprises": 3,
            "rna": 2,  # Associations
            "sirene": 1  # Static data
        }
        
        existing_priority = source_priority.get(existing.source, 0)
        new_priority = source_priority.get(new_data.source, 0)
        
        if new_priority > existing_priority:
            # Replace with higher priority data but keep missing fields
            for field, value in existing.dict().items():
                if value is not None and getattr(new_data, field) is None:
                    setattr(new_data, field, value)
            return new_data
        else:
            # Keep existing but fill in missing fields
            for field, value in new_data.dict().items():
                if value is not None and getattr(existing, field) is None:
                    setattr(existing, field, value)
            return existing
    
    def _apply_privacy_filters(
        self,
        results: List[CompanySearchResult]
    ) -> List[CompanySearchResult]:
        """Apply RGPD privacy filters to search results."""
        filtered = []
        
        for result in results:
            # Apply filters based on privacy status
            filtered_result = apply_privacy_filters(result, "CompanySearchResult")
            filtered.append(filtered_result)
        
        return filtered
    
    def _calculate_pagination(
        self,
        results: List[CompanySearchResult],
        params: SearchCompaniesInput
    ) -> Pagination:
        """Calculate pagination information."""
        # This is approximate as we don't know exact total from all sources
        # In production, you might want to estimate based on the primary source
        total_estimate = len(results)
        
        if len(results) == params.per_page:
            # Likely more results available
            total_estimate = (params.page + 1) * params.per_page
        
        return Pagination(
            total=total_estimate,
            page=params.page,
            per_page=params.per_page,
            total_pages=max(1, (total_estimate + params.per_page - 1) // params.per_page)
        )
    
    def _generate_cache_key(self, params: SearchCompaniesInput) -> str:
        """Generate cache key for search parameters."""
        return f"search:{params.query}:{params.page}:{params.per_page}:{params.filters}"
    
    async def _search_associations(
        self,
        params: SearchCompaniesInput
    ) -> Dict[str, Any]:
        """Search using RNA API for associations."""
        try:
            result = await self.rna_api.search_associations(
                query=params.query,
                postal_code=params.filters.postal_code if params.filters else None,
                page=params.page,
                per_page=params.per_page
            )
            
            # Convert associations to CompanySearchResult format
            converted_results = []
            for assoc in result["associations"]:
                converted = CompanySearchResult(
                    siren=assoc.get("siren", ""),
                    name=assoc["name"],
                    siret=assoc.get("siret"),
                    naf_code="",  # Associations don't have NAF
                    legal_form="Association",
                    is_active=assoc.get("is_active", True),
                    address=assoc.get("address", {}),
                    establishment_count=1,
                    employee_range="",
                    executives=[],
                    source="rna",
                    metadata={
                        "rna_id": assoc["rna_id"],
                        "is_public_utility": assoc.get("is_public_utility", False),
                        "object": assoc.get("object"),
                        "type": "association"
                    }
                )
                converted_results.append(converted)
            
            self.logger.info("rna_search_results",
                           count=len(converted_results),
                           total=result["total"])
            
            return {
                "results": converted_results,
                "pagination": {
                    "total": result["total"],
                    "page": params.page,
                    "per_page": params.per_page,
                    "total_pages": (result["total"] + params.per_page - 1) // params.per_page
                }
            }
            
        except Exception as e:
            self.logger.error("rna_search_failed", error=str(e))
            return {"results": [], "pagination": None}
    
    async def close(self) -> None:
        """Close API clients."""
        await self.recherche_api.close()
        await self.insee_api.close()
        await self.rna_api.close()


class SearchCompaniesTool(Tool):
    """MCP tool for searching French companies and associations."""
    
    name = "search_companies"
    description = "Search for French companies and associations across multiple government databases"
    
    def __init__(self):
        super().__init__()
        self.orchestrator = CompanySearchOrchestrator()
    
    async def run(
        self,
        query: str = Field(..., description="Search query (name, SIREN/SIRET, executive name)"),
        page: int = Field(1, ge=1, description="Page number"),
        per_page: int = Field(20, ge=1, le=25, description="Results per page"),
        naf_code: Optional[str] = Field(None, description="NAF activity code filter"),
        postal_code: Optional[str] = Field(None, description="Postal code filter"),
        department: Optional[str] = Field(None, description="Department code filter"),
        employee_range: Optional[str] = Field(None, description="Employee range filter"),
        legal_status: Optional[str] = Field(None, description="Legal status: active, ceased, or all"),
        include_associations: bool = Field(False, description="Include associations in search")
    ) -> Dict[str, Any]:
        """Execute company search across multiple sources."""
        # Build input model
        params = SearchCompaniesInput(
            query=query,
            page=page,
            per_page=per_page,
            include_associations=include_associations
        )
        
        # Add filters if provided
        if any([naf_code, postal_code, department, employee_range, legal_status]):
            from ..models.company import SearchFilters
            params.filters = SearchFilters(
                naf_code=naf_code,
                postal_code=postal_code,
                department=department,
                employee_range=employee_range,
                legal_status=legal_status
            )
        
        # Execute search
        result = await self.orchestrator.search_all_sources(params)
        
        # Return as dict for MCP
        return result.dict()