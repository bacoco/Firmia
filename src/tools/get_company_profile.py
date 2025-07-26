"""Unified company profile MCP tool implementation."""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime

from pydantic import Field
from structlog import get_logger

from ..models.company import (
    GetCompanyProfileInput,
    GetCompanyProfileOutput,
    Company,
    Address,
    Executive,
    Establishment,
    Financials,
    Certifications
)
from ..api import RechercheEntreprisesAPI, INSEESireneAPI, INPIRNEAPI
from ..cache import get_cache_manager
from ..privacy import apply_privacy_filters, get_audit_logger
from ..resilience import circuit_breaker

logger = get_logger(__name__)


class CompanyProfileOrchestrator:
    """Orchestrates company profile data from multiple sources."""
    
    def __init__(self):
        self.recherche_api = RechercheEntreprisesAPI()
        self.insee_api = INSEESireneAPI()
        self.inpi_api = INPIRNEAPI()
        self.cache_manager = get_cache_manager()
        self.audit_logger = get_audit_logger()
        self.logger = logger.bind(component="profile_orchestrator")
    
    async def get_complete_profile(
        self,
        params: GetCompanyProfileInput,
        caller_id: str = "mcp_client",
        ip_address: Optional[str] = None
    ) -> GetCompanyProfileOutput:
        """Get complete company profile with data fusion."""
        start_time = datetime.utcnow()
        
        # Check cache first
        cached_profile = await self.cache_manager.get_company_profile(params.siren)
        if cached_profile:
            self.logger.info("profile_cache_hit", siren=params.siren)
            return GetCompanyProfileOutput(**cached_profile)
        
        # Check privacy status first (from INSEE)
        privacy_status = await self._check_privacy_status(params.siren)
        
        # Prepare parallel API calls
        tasks = []
        task_names = []
        
        # Always get basic data
        tasks.append(self._get_insee_data(params.siren))
        task_names.append("insee")
        
        tasks.append(self._get_inpi_data(params.siren))
        task_names.append("inpi")
        
        # Conditional data fetching
        if params.include_establishments:
            tasks.append(self._get_establishments(params.siren))
            task_names.append("establishments")
        
        if params.include_documents:
            tasks.append(self._get_documents_list(params.siren))
            task_names.append("documents")
        
        if params.include_certifications:
            tasks.append(self._get_certifications(params.siren))
            task_names.append("certifications")
        
        if params.include_bank_info and await self._check_bank_access(caller_id):
            tasks.append(self._get_bank_info(params.siren))
            task_names.append("bank_info")
        
        # Execute all calls in parallel
        self.logger.info("fetching_company_data",
                        siren=params.siren,
                        sources=task_names)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build result map
        result_map = {}
        for i, (name, result) in enumerate(zip(task_names, results)):
            if isinstance(result, Exception):
                self.logger.error(f"{name}_fetch_failed",
                                siren=params.siren,
                                error=str(result))
                result_map[name] = None
            else:
                result_map[name] = result
        
        # Merge data with precedence rules
        merged_company = self._merge_company_data(
            result_map,
            params.siren,
            privacy_status
        )
        
        # Apply privacy filters
        filtered_company = apply_privacy_filters(merged_company, "Company")
        
        # Build metadata
        metadata = self._build_metadata(result_map, start_time)
        
        # Create output
        output = GetCompanyProfileOutput(
            company=filtered_company,
            metadata=metadata
        )
        
        # Cache the result
        await self.cache_manager.set_company_profile(
            params.siren,
            output.dict(),
            ttl=3600  # 1 hour
        )
        
        # Audit log
        await self.audit_logger.log_access(
            tool="get_company_profile",
            operation="retrieve",
            caller_id=caller_id,
            siren=params.siren,
            ip_address=ip_address,
            response_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
            status_code=200,
            metadata={
                "sources_used": list(result_map.keys()),
                "cache_hit": False,
                "privacy_filtered": privacy_status == "P"
            }
        )
        
        return output
    
    async def _check_privacy_status(self, siren: str) -> Optional[str]:
        """Check privacy/diffusion status from INSEE."""
        try:
            insee_data = await self.insee_api.get_legal_unit(siren)
            if insee_data:
                return insee_data.get("privacy_status", "O")
        except Exception as e:
            self.logger.error("privacy_check_failed",
                            siren=siren,
                            error=str(e))
        return "O"  # Default to open if check fails
    
    async def _get_insee_data(self, siren: str) -> Optional[Dict[str, Any]]:
        """Get data from INSEE Sirene."""
        try:
            return await self.insee_api.get_legal_unit(siren)
        except Exception as e:
            self.logger.error("insee_fetch_failed",
                            siren=siren,
                            error=str(e))
            return None
    
    async def _get_inpi_data(self, siren: str) -> Optional[Dict[str, Any]]:
        """Get data from INPI RNE."""
        try:
            return await self.inpi_api.get_company_details(siren)
        except Exception as e:
            self.logger.error("inpi_fetch_failed",
                            siren=siren,
                            error=str(e))
            return None
    
    async def _get_establishments(self, siren: str) -> List[Dict[str, Any]]:
        """Get all establishments for a company."""
        establishments = []
        
        # Try INSEE first (more complete)
        try:
            insee_estabs = await self.insee_api.get_establishments_by_siren(siren)
            establishments.extend(insee_estabs)
        except Exception as e:
            self.logger.error("insee_establishments_failed",
                            siren=siren,
                            error=str(e))
        
        # Also check Recherche Entreprises
        try:
            recherche_estabs = await self.recherche_api.get_all_establishments(siren)
            # Merge with INSEE data, avoiding duplicates
            existing_sirets = {e.get("siret") for e in establishments}
            for estab in recherche_estabs:
                if estab.get("siret") not in existing_sirets:
                    establishments.append(estab)
        except Exception as e:
            self.logger.error("recherche_establishments_failed",
                            siren=siren,
                            error=str(e))
        
        return establishments
    
    async def _get_documents_list(self, siren: str) -> List[Dict[str, Any]]:
        """Get list of available documents."""
        try:
            return await self.inpi_api.get_company_documents(siren)
        except Exception:
            return []
    
    async def _get_certifications(self, siren: str) -> Dict[str, Any]:
        """Get company certifications."""
        # This would integrate with RGE and other certification APIs
        # For now, return empty certifications
        return {
            "rge": None,
            "bio": False,
            "ess": False,
            "qualiopi": False
        }
    
    async def _get_bank_info(self, siren: str) -> Optional[Dict[str, Any]]:
        """Get bank information (requires special authorization)."""
        # FICOBA integration would go here
        # For now, return None as it requires special auth
        return None
    
    async def _check_bank_access(self, caller_id: str) -> bool:
        """Check if caller has bank info access."""
        # In production, check against authorized caller list
        return False
    
    def _merge_company_data(
        self,
        data_sources: Dict[str, Any],
        siren: str,
        privacy_status: str
    ) -> Company:
        """Merge data from multiple sources with precedence rules."""
        # Precedence: INPI RNE > INSEE current > Recherche Entreprises
        
        # Start with base structure
        merged = {
            "siren": siren,
            "privacy_status": privacy_status,
            "source": [],
            "last_update": datetime.utcnow()
        }
        
        # Apply INPI data (highest priority)
        inpi_data = data_sources.get("inpi")
        if inpi_data:
            merged.update({
                "denomination": inpi_data.get("denomination"),
                "sigle": inpi_data.get("sigle"),
                "legal_form": inpi_data.get("legal_form"),
                "creation_date": inpi_data.get("creation_date"),
                "cessation_date": inpi_data.get("closure_date"),
                "is_active": inpi_data.get("is_active", True),
                "executives": self._parse_executives(inpi_data.get("executives", [])),
                "source": ["inpi_rne"]
            })
            
            # Financial data from INPI
            if inpi_data.get("capital"):
                merged["financials"] = Financials(
                    capital=inpi_data["capital"]
                )
        
        # Apply INSEE data (second priority)
        insee_data = data_sources.get("insee")
        if insee_data:
            # Fill in missing fields
            if not merged.get("denomination"):
                merged["denomination"] = insee_data.get("denomination")
            if not merged.get("legal_form"):
                merged["legal_form"] = insee_data.get("legal_form")
            
            merged.update({
                "naf_code": insee_data.get("naf_code"),
                "employee_range": insee_data.get("employee_range"),
                "creation_date": merged.get("creation_date") or insee_data.get("creation_date"),
                "is_headquarters": insee_data.get("nic_siege") is not None
            })
            
            if "insee_sirene" not in merged.get("source", []):
                merged["source"].append("insee_sirene")
        
        # Add establishments if available
        establishments_data = data_sources.get("establishments", [])
        if establishments_data:
            merged["establishments"] = self._parse_establishments(establishments_data)
        
        # Add certifications
        cert_data = data_sources.get("certifications")
        if cert_data:
            merged["certifications"] = Certifications(**cert_data)
        
        # Ensure we have a denomination
        if not merged.get("denomination"):
            merged["denomination"] = f"SIREN {siren}"
        
        # Create Company object
        return Company(**merged)
    
    def _parse_executives(self, executives_data: List[Dict[str, Any]]) -> List[Executive]:
        """Parse executive data into Executive models."""
        executives = []
        for exec_data in executives_data:
            try:
                executive = Executive(
                    role=exec_data.get("role", ""),
                    name=exec_data.get("name", ""),
                    first_name=exec_data.get("first_name"),
                    birth_date=exec_data.get("birth_date"),
                    nationality=exec_data.get("nationality")
                )
                executives.append(executive)
            except Exception as e:
                self.logger.warning("executive_parse_failed",
                                  error=str(e),
                                  data=exec_data)
        return executives
    
    def _parse_establishments(self, establishments_data: List[Dict[str, Any]]) -> List[Establishment]:
        """Parse establishment data into Establishment models."""
        establishments = []
        for estab_data in establishments_data:
            try:
                # Parse address
                address = None
                if estab_data.get("address"):
                    address = Address(**estab_data["address"])
                
                establishment = Establishment(
                    siret=estab_data.get("siret", ""),
                    is_headquarters=estab_data.get("is_headquarters", False),
                    address=address,
                    employee_range=estab_data.get("employee_range"),
                    activity=estab_data.get("activity")
                )
                establishments.append(establishment)
            except Exception as e:
                self.logger.warning("establishment_parse_failed",
                                  error=str(e),
                                  data=estab_data)
        return establishments
    
    def _build_metadata(
        self,
        result_map: Dict[str, Any],
        start_time: datetime
    ) -> Dict[str, Any]:
        """Build metadata about data sources and freshness."""
        sources_used = [k for k, v in result_map.items() if v is not None]
        
        return {
            "last_update": datetime.utcnow().isoformat(),
            "sources": sources_used,
            "response_time_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
            "data_freshness": self._calculate_data_freshness(result_map),
            "completeness_score": self._calculate_completeness(result_map)
        }
    
    def _calculate_data_freshness(self, result_map: Dict[str, Any]) -> str:
        """Calculate overall data freshness."""
        # In production, check actual data timestamps
        # For now, return current
        return "current"
    
    def _calculate_completeness(self, result_map: Dict[str, Any]) -> float:
        """Calculate data completeness score."""
        total_sources = len(result_map)
        successful_sources = sum(1 for v in result_map.values() if v is not None)
        
        if total_sources == 0:
            return 0.0
        
        return (successful_sources / total_sources) * 100
    
    async def close(self) -> None:
        """Close API clients."""
        await self.recherche_api.close()
        await self.insee_api.close()
        await self.inpi_api.close()


class GetCompanyProfileTool(Tool):
    """MCP tool for getting unified company profile."""
    
    name = "get_company_profile"
    description = "Get comprehensive company profile with data from multiple government sources"
    
    def __init__(self):
        super().__init__()
        self.orchestrator = CompanyProfileOrchestrator()
    
    async def run(
        self,
        siren: str = Field(..., description="Company SIREN (9 digits)", pattern="^[0-9]{9}$"),
        include_establishments: bool = Field(True, description="Include all establishments"),
        include_documents: bool = Field(False, description="Include available documents list"),
        include_financials: bool = Field(True, description="Include financial information"),
        include_certifications: bool = Field(True, description="Include certifications (RGE, etc.)"),
        include_bank_info: bool = Field(False, description="Include bank info (requires special auth)")
    ) -> Dict[str, Any]:
        """Get unified company profile."""
        # Build input model
        params = GetCompanyProfileInput(
            siren=siren,
            include_establishments=include_establishments,
            include_documents=include_documents,
            include_financials=include_financials,
            include_certifications=include_certifications,
            include_bank_info=include_bank_info
        )
        
        # Execute profile fetch
        result = await self.orchestrator.get_complete_profile(params)
        
        # Return as dict for MCP
        return result.dict()