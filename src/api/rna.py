"""RNA (Répertoire National des Associations) API client."""

from typing import Optional, List, Dict, Any
from datetime import datetime

from .base import BaseAPIClient, APIError
from ..resilience import circuit_breaker


class RNAAPI(BaseAPIClient):
    """Client for RNA API (associations registry)."""
    
    def __init__(self):
        super().__init__(
            base_url="https://entreprise.data.gouv.fr/api/rna/v1",
            api_name="rna",
            rate_limit=10  # Conservative rate limit
        )
        # No authentication required for RNA
    
    async def get_headers(self) -> Dict[str, str]:
        """Get headers for RNA API."""
        return {
            "Accept": "application/json",
            "User-Agent": "Firmia MCP Server/0.1.0"
        }
    
    @circuit_breaker(
        name="rna",
        failure_threshold=3,
        recovery_timeout=60
    )
    async def search_associations(
        self,
        query: str,
        postal_code: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """Search associations by name or RNA/SIREN."""
        # Build search params
        params = {
            "q": query,
            "page": page,
            "per_page": per_page
        }
        
        if postal_code:
            params["postal_code"] = postal_code
        
        # Make request
        response = await self._make_request(
            "GET",
            "/full_text",
            params=params
        )
        
        return self._parse_search_response(response)
    
    def _parse_search_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse RNA search response."""
        associations = []
        
        for assoc in response.get("association", []):
            association = {
                "rna_id": assoc.get("id_association"),
                "siren": assoc.get("siret", "")[:9] if assoc.get("siret") else None,
                "siret": assoc.get("siret"),
                "name": assoc.get("titre"),
                "short_name": assoc.get("titre_court"),
                "object": assoc.get("objet"),
                
                # Legal info
                "creation_date": assoc.get("date_creation"),
                "declaration_date": assoc.get("date_declaration"),
                "publication_date": assoc.get("date_publication_jo"),
                "dissolution_date": assoc.get("date_dissolution"),
                "is_active": assoc.get("actif", True),
                
                # Type info
                "type": assoc.get("nature"),
                "is_public_utility": assoc.get("utilite_publique", False),
                "regime": assoc.get("regime"),
                
                # Address
                "address": {
                    "street": assoc.get("adresse_gestion_libelle_voie"),
                    "postal_code": assoc.get("adresse_gestion_code_postal"),
                    "city": assoc.get("adresse_gestion_commune"),
                    "country": "France"
                },
                
                # Administrative info
                "prefecture": assoc.get("prefecture"),
                "sub_prefecture": assoc.get("sous_prefecture"),
                
                # Financial info
                "has_ccp": assoc.get("compte_ccp", False),
                "has_bank_account": assoc.get("compte_banque", False),
                
                # Contact
                "email": assoc.get("email"),
                "website": assoc.get("site_web"),
                "phone": assoc.get("telephone")
            }
            
            associations.append(association)
        
        return {
            "total": response.get("total_results", len(associations)),
            "associations": associations,
            "page": response.get("page", page),
            "per_page": response.get("per_page", per_page)
        }
    
    async def get_association_by_rna(self, rna_id: str) -> Optional[Dict[str, Any]]:
        """Get association details by RNA ID."""
        try:
            response = await self._make_request(
                "GET",
                f"/id/{rna_id}"
            )
            
            if response.get("association"):
                return self._parse_association_details(response["association"])
            
            return None
            
        except APIError as e:
            if e.status_code == 404:
                return None
            raise
    
    async def get_association_by_siren(self, siren: str) -> Optional[Dict[str, Any]]:
        """Get association details by SIREN."""
        try:
            response = await self._make_request(
                "GET",
                f"/siret/{siren}*"  # Use wildcard to match any SIRET starting with SIREN
            )
            
            if response.get("association"):
                return self._parse_association_details(response["association"])
            
            return None
            
        except APIError as e:
            if e.status_code == 404:
                return None
            raise
    
    def _parse_association_details(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse detailed association data."""
        return {
            "rna_id": data.get("id_association"),
            "siren": data.get("siret", "")[:9] if data.get("siret") else None,
            "siret": data.get("siret"),
            "name": data.get("titre"),
            "short_name": data.get("titre_court"),
            "object": data.get("objet"),
            "object_social": data.get("objet_social"),
            
            # Detailed legal info
            "creation_date": data.get("date_creation"),
            "declaration_date": data.get("date_declaration"),
            "publication_date": data.get("date_publication_jo"),
            "dissolution_date": data.get("date_dissolution"),
            "last_update": data.get("date_derniere_maj"),
            "is_active": data.get("actif", True),
            
            # Classification
            "type": data.get("nature"),
            "type_label": self._get_type_label(data.get("nature")),
            "is_public_utility": data.get("utilite_publique", False),
            "is_alsace_moselle": data.get("alsace_moselle", False),
            "regime": data.get("regime"),
            "is_recognized": data.get("reconnue", False),
            
            # Addresses
            "headquarters_address": {
                "street": data.get("adresse_siege_libelle_voie"),
                "postal_code": data.get("adresse_siege_code_postal"),
                "city": data.get("adresse_siege_commune"),
                "country": "France"
            },
            "management_address": {
                "street": data.get("adresse_gestion_libelle_voie"),
                "postal_code": data.get("adresse_gestion_code_postal"),
                "city": data.get("adresse_gestion_commune"),
                "country": "France"
            },
            
            # Administrative
            "prefecture": data.get("prefecture"),
            "sub_prefecture": data.get("sous_prefecture"),
            "declaration_prefecture": data.get("prefecture_declaration"),
            
            # Financial
            "has_ccp": data.get("compte_ccp", False),
            "has_bank_account": data.get("compte_banque", False),
            "accepts_donations": data.get("dons", False),
            
            # Contact
            "email": data.get("email"),
            "website": data.get("site_web"),
            "phone": data.get("telephone"),
            
            # Members
            "members_count": data.get("nombre_adherents"),
            "volunteers_count": data.get("nombre_benevoles"),
            "employees_count": data.get("nombre_salaries"),
            
            # Activities
            "main_activity": data.get("activite_principale"),
            "secondary_activities": data.get("activites_secondaires", []),
            
            # RNA specific
            "rna_data": {
                "waldec": data.get("numero_waldec"),
                "old_rna": data.get("ancien_id"),
                "grouping": data.get("groupement"),
                "position": data.get("position_activite")
            }
        }
    
    def _get_type_label(self, type_code: str) -> str:
        """Get human-readable label for association type."""
        type_labels = {
            "D": "Déclarée",
            "S": "Simplement déclarée",
            "R": "Reconnue d'utilité publique",
            "F": "Fondation",
            "E": "Entreprise d'insertion",
            "C": "Congrégation",
            "A": "Association de droit local (Alsace-Moselle)"
        }
        return type_labels.get(type_code, type_code)
    
    async def check_if_association(self, siren: str) -> bool:
        """Check if a SIREN belongs to an association."""
        association = await self.get_association_by_siren(siren)
        return association is not None
    
    async def get_association_financial_info(self, rna_id: str) -> Dict[str, Any]:
        """Get financial information for an association."""
        association = await self.get_association_by_rna(rna_id)
        
        if not association:
            return None
        
        return {
            "rna_id": rna_id,
            "name": association["name"],
            "accepts_donations": association.get("accepts_donations", False),
            "is_public_utility": association.get("is_public_utility", False),
            "has_bank_account": association.get("has_bank_account", False),
            "has_ccp": association.get("has_ccp", False),
            "employees_count": association.get("employees_count"),
            "can_issue_tax_receipts": association.get("is_public_utility", False),  # Simplified
            "financial_transparency": {
                "required": association.get("is_public_utility", False),
                "last_published": None  # Would need additional data source
            }
        }
    
    async def search_by_activity(
        self,
        activity_code: str,
        postal_code: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """Search associations by activity code."""
        # RNA doesn't have direct activity search, so we search and filter
        # This is a simplified implementation
        results = await self.search_associations(
            query=activity_code,
            postal_code=postal_code,
            page=page,
            per_page=per_page
        )
        
        # Filter by activity
        filtered_associations = []
        for assoc in results["associations"]:
            if activity_code in str(assoc.get("main_activity", "")):
                filtered_associations.append(assoc)
        
        results["associations"] = filtered_associations
        results["total"] = len(filtered_associations)
        
        return results