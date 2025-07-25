"""Recherche d'Entreprises API client implementation."""

from typing import Optional, List, Dict, Any

from ..models.company import CompanySearchResult, Address, Pagination
from ..resilience import circuit_breaker
from .base import BaseAPIClient, APIError

class RechercheEntreprisesAPI(BaseAPIClient):
    """Client for the Recherche d'Entreprises API (no auth required)."""
    
    BASE_URL = "https://recherche-entreprises.api.gouv.fr"
    API_NAME = "Recherche Entreprises"
    RATE_LIMIT = 3000  # 50 req/s = 3000 req/min
    REQUIRES_AUTH = False
    
    @circuit_breaker(
        name="recherche_entreprises",
        failure_threshold=5,
        recovery_timeout=60
    )
    async def search(
        self,
        query: str,
        page: int = 1,
        per_page: int = 20,
        naf_code: Optional[str] = None,
        postal_code: Optional[str] = None,
        department: Optional[str] = None,
        employee_range: Optional[str] = None,
        legal_status: Optional[str] = None
    ) -> Dict[str, Any]:
        """Search for companies with the given query and filters."""
        # Build parameters
        params = {
            "q": query,
            "page": page,
            "per_page": min(per_page, 25)  # API max is 25
        }
        
        # Add optional filters
        if naf_code:
            params["naf"] = naf_code
        if postal_code:
            params["code_postal"] = postal_code
        if department:
            params["departement"] = department
        if employee_range:
            params["tranche_effectif"] = employee_range
        
        # Map legal status
        if legal_status:
            if legal_status == "active":
                params["etat_administratif"] = "A"
            elif legal_status == "ceased":
                params["etat_administratif"] = "C"
            # "all" means no filter
        
        # Make request
        response = await self.get("/search", params=params)
        data = response.json()
        
        # Parse results
        results = []
        for item in data.get("results", []):
            # Extract headquarters info
            siege = item.get("siege", {})
            
            # Build address
            address = None
            if siege:
                address = Address(
                    street=siege.get("adresse"),
                    postal_code=siege.get("code_postal"),
                    city=siege.get("commune"),
                    latitude=siege.get("latitude"),
                    longitude=siege.get("longitude")
                )
            
            # Create search result
            result = CompanySearchResult(
                siren=item.get("siren"),
                siret=item.get("siret") or siege.get("siret"),
                name=item.get("nom_complet") or item.get("denomination") or item.get("nom_raison_sociale", ""),
                legal_form=self._extract_legal_form(item),
                naf_code=item.get("naf") or item.get("activite_principale"),
                employee_range=item.get("tranche_effectif"),
                address=address,
                creation_date=item.get("date_creation"),
                is_active=item.get("etat_administratif") == "A",
                is_headquarters=True if siege else None,
                source="recherche_entreprises"
            )
            
            results.append(result)
        
        # Build response with pagination
        return {
            "results": results,
            "pagination": Pagination(
                total=data.get("total_results", 0),
                page=data.get("page", page),
                per_page=data.get("per_page", per_page),
                total_pages=data.get("total_pages", 0)
            )
        }
    
    def _extract_legal_form(self, data: Dict[str, Any]) -> Optional[str]:
        """Extract legal form from various possible fields."""
        # Try different field names used by the API
        for field in ["forme_juridique", "categorie_juridique", "nature_juridique"]:
            if field in data and data[field]:
                return str(data[field])
        return None
    
    async def get_company_by_siren(self, siren: str) -> Optional[Dict[str, Any]]:
        """Get company details by SIREN."""
        # Search by exact SIREN
        result = await self.search(query=siren, per_page=1)
        
        if result["results"]:
            # Find exact match
            for company in result["results"]:
                if company.siren == siren:
                    return company.dict()
        
        return None
    
    async def search_by_name_and_location(
        self,
        name: str,
        postal_code: Optional[str] = None,
        department: Optional[str] = None
    ) -> List[CompanySearchResult]:
        """Search companies by name and location."""
        result = await self.search(
            query=name,
            postal_code=postal_code,
            department=department,
            per_page=25
        )
        
        return result["results"]
    
    async def search_by_executive(
        self,
        executive_name: str,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """Search companies by executive/director name."""
        # The API supports searching in executive names
        return await self.search(
            query=executive_name,
            page=page,
            per_page=per_page
        )
    
    async def get_all_establishments(self, siren: str) -> List[Dict[str, Any]]:
        """Get all establishments for a company."""
        # Search for all SIRET starting with the SIREN
        establishments = []
        page = 1
        
        while True:
            result = await self.search(
                query=siren,
                page=page,
                per_page=25
            )
            
            # Filter to only establishments of this SIREN
            for company in result["results"]:
                if company.siren == siren and company.siret:
                    establishments.append({
                        "siret": company.siret,
                        "is_headquarters": company.is_headquarters,
                        "address": company.address.dict() if company.address else None,
                        "naf_code": company.naf_code,
                        "employee_range": company.employee_range,
                        "is_active": company.is_active
                    })
            
            # Check if more pages
            if page >= result["pagination"].total_pages:
                break
            
            page += 1
            
            # Safety limit
            if page > 10:
                break
        
        return establishments
    
    async def health_check(self) -> bool:
        """Check if API is healthy."""
        try:
            # Simple search to test API
            await self.search("test", per_page=1)
            return True
        except Exception:
            return False