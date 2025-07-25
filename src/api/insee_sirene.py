"""INSEE Sirene V3.11 API client implementation."""

from typing import Optional, List, Dict, Any
from datetime import datetime

from ..models.company import Company, Address, Executive, Establishment, Financials
from ..resilience import circuit_breaker
from .base import BaseAPIClient, APIError


class INSEESireneAPI(BaseAPIClient):
    """Client for INSEE Sirene V3.11 API with OAuth2 authentication."""
    
    BASE_URL = "https://portail-api.insee.fr/entreprises/sirene/V3.11"
    API_NAME = "INSEE Sirene"
    RATE_LIMIT = 30  # 30 req/min per token
    REQUIRES_AUTH = True
    AUTH_SERVICE = "insee"
    
    @circuit_breaker(
        name="insee_sirene",
        failure_threshold=3,
        recovery_timeout=120
    )
    async def get_legal_unit(self, siren: str) -> Optional[Dict[str, Any]]:
        """Get legal unit (company) information by SIREN."""
        try:
            response = await self.get(f"/siren/{siren}")
            data = response.json()
            
            # Check if successful
            header = data.get("header", {})
            if header.get("statut") != 200:
                self.logger.warning("insee_legal_unit_not_found",
                                  siren=siren,
                                  message=header.get("message"))
                return None
            
            return self._parse_legal_unit(data.get("uniteLegale", {}))
            
        except APIError as e:
            if e.status_code == 404:
                return None
            raise
    
    async def get_establishment(self, siret: str) -> Optional[Dict[str, Any]]:
        """Get establishment information by SIRET."""
        try:
            response = await self.get(f"/siret/{siret}")
            data = response.json()
            
            header = data.get("header", {})
            if header.get("statut") != 200:
                return None
            
            return self._parse_establishment(data.get("etablissement", {}))
            
        except APIError as e:
            if e.status_code == 404:
                return None
            raise
    
    async def get_establishments_by_siren(
        self,
        siren: str,
        only_active: bool = True
    ) -> List[Dict[str, Any]]:
        """Get all establishments for a SIREN."""
        params = {
            "q": f"siren:{siren}",
            "nombre": 100  # Max allowed
        }
        
        if only_active:
            params["q"] += " AND etatAdministratifEtablissement:A"
        
        try:
            response = await self.get("/siret", params=params)
            data = response.json()
            
            establishments = []
            for item in data.get("etablissements", []):
                parsed = self._parse_establishment(item)
                if parsed:
                    establishments.append(parsed)
            
            return establishments
            
        except Exception as e:
            self.logger.error("insee_establishments_fetch_failed",
                            siren=siren,
                            error=str(e))
            return []
    
    def _parse_legal_unit(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse INSEE legal unit data into our format."""
        # Extract basic info
        result = {
            "siren": data.get("siren"),
            "denomination": data.get("denominationUniteLegale"),
            "sigle": data.get("sigleUniteLegale"),
            "privacy_status": data.get("statutDiffusionUniteLegale", "O"),
            "creation_date": data.get("dateCreationUniteLegale"),
            "legal_form": {
                "code": data.get("categorieJuridiqueUniteLegale"),
                "label": self._get_legal_form_label(data.get("categorieJuridiqueUniteLegale"))
            },
            "naf_code": data.get("activitePrincipaleUniteLegale"),
            "employee_range": data.get("trancheEffectifsUniteLegale"),
            "is_active": data.get("etatAdministratifUniteLegale") == "A",
            "nic_siege": data.get("nicSiegeUniteLegale"),
            "category": data.get("categorieEntreprise"),
            "source": ["insee_sirene"]
        }
        
        # Handle diffusion protection
        if result["privacy_status"] == "P":
            # Remove sensitive fields for protected entities
            protected_fields = [
                "prenomUsuelUniteLegale",
                "identifiantAssociationUniteLegale"
            ]
            for field in protected_fields:
                if field in data:
                    data.pop(field)
        
        # Add historical data if available
        periods = data.get("periodesUniteLegale", [])
        if periods:
            result["history"] = self._parse_historical_periods(periods)
        
        return result
    
    def _parse_establishment(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse INSEE establishment data."""
        if not data:
            return None
        
        # Extract address
        address = self._parse_address(data)
        
        result = {
            "siret": data.get("siret"),
            "nic": data.get("nic"),
            "is_headquarters": data.get("etablissementSiege") == "true",
            "creation_date": data.get("dateCreationEtablissement"),
            "employee_range": data.get("trancheEffectifsEtablissement"),
            "is_active": data.get("etatAdministratifEtablissement") == "A",
            "address": address,
            "activity": {
                "naf_code": data.get("activitePrincipaleEtablissement"),
                "label": data.get("activitePrincipaleEtablissementLibelle")
            }
        }
        
        return result
    
    def _parse_address(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse address from INSEE data."""
        # Check diffusion status
        if data.get("statutDiffusionEtablissement") == "P":
            # Protected - only return minimal info
            return {
                "postal_code": data.get("codePostalEtablissement"),
                "city": data.get("libelleCommuneEtablissement")
            }
        
        # Build full address
        address_parts = []
        
        # Number and street type
        if data.get("numeroVoieEtablissement"):
            address_parts.append(data["numeroVoieEtablissement"])
        if data.get("indiceRepetitionEtablissement"):
            address_parts.append(data["indiceRepetitionEtablissement"])
        if data.get("typeVoieEtablissement"):
            address_parts.append(data["typeVoieEtablissement"])
        if data.get("libelleVoieEtablissement"):
            address_parts.append(data["libelleVoieEtablissement"])
        
        street = " ".join(address_parts) if address_parts else None
        
        return {
            "street": street,
            "postal_code": data.get("codePostalEtablissement"),
            "city": data.get("libelleCommuneEtablissement"),
            "complement": data.get("complementAdresseEtablissement"),
            "distribution": data.get("distributionSpecialeEtablissement")
        }
    
    def _parse_historical_periods(self, periods: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse historical period data."""
        history = []
        
        for period in periods:
            entry = {
                "start_date": period.get("dateDebut"),
                "end_date": period.get("dateFin"),
                "state": period.get("etatAdministratifUniteLegale"),
                "denomination": period.get("denominationUniteLegale"),
                "legal_form": period.get("categorieJuridiqueUniteLegale")
            }
            history.append(entry)
        
        # Sort by date
        history.sort(key=lambda x: x["start_date"] or "", reverse=True)
        
        return history
    
    def _get_legal_form_label(self, code: Optional[str]) -> Optional[str]:
        """Get legal form label from code."""
        if not code:
            return None
        
        # Common legal forms mapping
        legal_forms = {
            "5710": "Société anonyme à conseil d'administration",
            "5720": "Société anonyme à directoire",
            "5499": "Société à responsabilité limitée (SARL)",
            "5498": "SARL unipersonnelle",
            "5307": "Société par actions simplifiée (SAS)",
            "5308": "SAS unipersonnelle",
            "1000": "Entrepreneur individuel"
        }
        
        return legal_forms.get(code, f"Forme juridique {code}")
    
    async def search_companies(
        self,
        query: str,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """Search companies using INSEE API."""
        # INSEE uses different pagination
        offset = (page - 1) * per_page
        
        params = {
            "q": query,
            "nombre": min(per_page, 100),
            "debut": offset
        }
        
        response = await self.get("/siren", params=params)
        data = response.json()
        
        results = []
        for unit in data.get("unitesLegales", []):
            parsed = self._parse_legal_unit(unit)
            results.append(parsed)
        
        # Estimate total pages (INSEE doesn't provide exact count)
        total = data.get("header", {}).get("total", 0)
        total_pages = (total + per_page - 1) // per_page if total else 1
        
        return {
            "results": results,
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages
            }
        }
    
    async def health_check(self) -> bool:
        """Check if INSEE API is healthy."""
        try:
            # Test with a known SIREN
            response = await self.get("/siren/542107651")  # INSEE's own SIREN
            return response.status_code == 200
        except Exception:
            return False