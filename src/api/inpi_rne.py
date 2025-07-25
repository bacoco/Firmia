"""INPI RNE (Registre National des Entreprises) API client implementation."""

from typing import Optional, List, Dict, Any
from datetime import datetime

from ..models.company import Company, Executive
from ..resilience import circuit_breaker
from .base import BaseAPIClient, APIError


class INPIRNEAPI(BaseAPIClient):
    """Client for INPI RNE API with JWT login authentication."""
    
    BASE_URL = "https://registre-national-entreprises.inpi.fr/api"
    API_NAME = "INPI RNE"
    RATE_LIMIT = 20  # 100 req/5min = 20 req/min average
    REQUIRES_AUTH = True
    AUTH_SERVICE = "inpi"
    
    @circuit_breaker(
        name="inpi_rne",
        failure_threshold=3,
        recovery_timeout=300  # 5 minutes
    )
    async def get_company_details(self, siren: str) -> Optional[Dict[str, Any]]:
        """Get detailed company information from RNE."""
        try:
            response = await self.get(f"/companies/{siren}")
            data = response.json()
            
            return self._parse_company_data(data)
            
        except APIError as e:
            if e.status_code == 404:
                return None
            raise
    
    def _parse_company_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse INPI RNE company data."""
        formality = data.get("formality", {}).get("content", {})
        
        result = {
            "siren": data.get("siren"),
            "denomination": self._extract_denomination(formality),
            "legal_form": self._parse_legal_form(formality.get("formeJuridique", {})),
            "capital": self._parse_capital(formality.get("capital", {})),
            "creation_date": formality.get("dateImmatriculation"),
            "closure_date": formality.get("dateRadiation"),
            "is_active": formality.get("dateRadiation") is None,
            "beneficial_owners": self._parse_beneficial_owners(formality.get("beneficiairesEffectifs", [])),
            "executives": self._parse_representatives(formality.get("representants", [])),
            "establishments": self._parse_establishments(formality.get("etablissements", [])),
            "activity": self._parse_activity(formality),
            "source": ["inpi_rne"]
        }
        
        # Add specific RNE data
        result["rne_specific"] = {
            "immatriculation_date": formality.get("dateImmatriculation"),
            "last_update": data.get("lastUpdate"),
            "formality_type": data.get("formality", {}).get("type"),
            "registration_number": formality.get("numeroImmatriculation")
        }
        
        return result
    
    def _extract_denomination(self, formality: Dict[str, Any]) -> str:
        """Extract company denomination from various fields."""
        # Try different fields in order of preference
        fields = [
            "denomination",
            "denominationSociale",
            "raisonSociale",
            "nom",
            "nomCommercial"
        ]
        
        for field in fields:
            if field in formality and formality[field]:
                return formality[field]
        
        return "N/A"
    
    def _parse_legal_form(self, legal_form_data: Dict[str, Any]) -> Dict[str, str]:
        """Parse legal form information."""
        return {
            "code": legal_form_data.get("code", ""),
            "label": legal_form_data.get("libelle", "")
        }
    
    def _parse_capital(self, capital_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse capital information."""
        return {
            "amount": capital_data.get("montant"),
            "currency": capital_data.get("devise", "EUR"),
            "is_variable": capital_data.get("capitalVariable", False)
        }
    
    def _parse_beneficial_owners(self, owners: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse beneficial owners information."""
        parsed_owners = []
        
        for owner in owners:
            parsed = {
                "name": owner.get("nom"),
                "first_name": owner.get("prenom"),
                "birth_date": owner.get("dateNaissance"),
                "nationality": owner.get("nationalite"),
                "control_modalities": owner.get("modalitesControle", [])
            }
            
            # Apply privacy protection
            if parsed["birth_date"]:
                # Only keep year-month for privacy
                parsed["birth_date"] = parsed["birth_date"][:7] if len(parsed["birth_date"]) >= 7 else None
            
            parsed_owners.append(parsed)
        
        return parsed_owners
    
    def _parse_representatives(self, representatives: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse company representatives/executives."""
        executives = []
        
        for rep in representatives:
            person = rep.get("personne", {})
            
            if person.get("typePersonne") == "PHYSIQUE":
                executive = {
                    "role": rep.get("qualite", ""),
                    "name": person.get("nom", ""),
                    "first_name": person.get("prenom", ""),
                    "birth_date": person.get("dateNaissance"),
                    "nationality": person.get("nationalite"),
                    "person_type": "PHYSIQUE"
                }
                
                # Privacy protection for birth date
                if executive["birth_date"]:
                    executive["birth_date"] = executive["birth_date"][:7] if len(executive["birth_date"]) >= 7 else None
                
            else:  # MORALE (company)
                executive = {
                    "role": rep.get("qualite", ""),
                    "name": person.get("denomination", ""),
                    "siren": person.get("siren"),
                    "person_type": "MORALE"
                }
            
            executives.append(executive)
        
        return executives
    
    def _parse_establishments(self, establishments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse establishment information."""
        parsed_establishments = []
        
        for estab in establishments:
            address = estab.get("adresse", {})
            
            parsed = {
                "siret": estab.get("siret"),
                "is_headquarters": estab.get("estSiege", False),
                "is_active": estab.get("etatAdministratif") == "A",
                "address": {
                    "street": address.get("voie"),
                    "postal_code": address.get("codePostal"),
                    "city": address.get("commune"),
                    "country": address.get("pays", "France")
                },
                "activity": {
                    "naf_code": estab.get("activitePrincipale"),
                    "label": estab.get("activitePrincipaleLibelle")
                }
            }
            
            parsed_establishments.append(parsed)
        
        return parsed_establishments
    
    def _parse_activity(self, formality: Dict[str, Any]) -> Dict[str, Any]:
        """Parse main activity information."""
        return {
            "naf_code": formality.get("activitePrincipale", {}).get("code"),
            "label": formality.get("activitePrincipale", {}).get("libelle"),
            "description": formality.get("objetSocial")
        }
    
    async def get_company_documents(self, siren: str) -> List[Dict[str, Any]]:
        """Get list of available documents for a company."""
        try:
            response = await self.get(f"/companies/{siren}/documents")
            data = response.json()
            
            documents = []
            for doc in data.get("documents", []):
                documents.append({
                    "id": doc.get("id"),
                    "type": doc.get("type"),
                    "name": doc.get("name"),
                    "date": doc.get("date"),
                    "size": doc.get("size"),
                    "url": doc.get("url")
                })
            
            return documents
            
        except Exception as e:
            self.logger.error("inpi_documents_fetch_failed",
                            siren=siren,
                            error=str(e))
            return []
    
    async def get_company_history(self, siren: str) -> List[Dict[str, Any]]:
        """Get company modification history."""
        try:
            response = await self.get(f"/companies/{siren}/history")
            data = response.json()
            
            history = []
            for event in data.get("events", []):
                history.append({
                    "date": event.get("date"),
                    "type": event.get("type"),
                    "description": event.get("description"),
                    "details": event.get("details", {})
                })
            
            # Sort by date descending
            history.sort(key=lambda x: x["date"] or "", reverse=True)
            
            return history
            
        except Exception as e:
            self.logger.error("inpi_history_fetch_failed",
                            siren=siren,
                            error=str(e))
            return []
    
    async def verify_company_exists(self, siren: str) -> bool:
        """Quick check if company exists in RNE."""
        try:
            response = await self.get(f"/companies/{siren}/exists")
            return response.json().get("exists", False)
        except:
            # Fallback to full fetch
            company = await self.get_company_details(siren)
            return company is not None
    
    async def health_check(self) -> bool:
        """Check if INPI RNE API is healthy."""
        try:
            response = await self.get("/health")
            return response.status_code == 200
        except Exception:
            return False
    
    async def download_from_url(self, url: str) -> bytes:
        """Download document content from INPI URL."""
        try:
            # INPI provides direct download URLs
            # We need to make a direct request with auth headers
            headers = await self.get_headers()
            
            response = await self._make_request(
                "GET",
                url,
                headers=headers,
                timeout=30  # Longer timeout for documents
            )
            
            # Response should be raw bytes for PDF
            return response
            
        except Exception as e:
            self.logger.error("inpi_document_download_failed",
                            url=url,
                            error=str(e))
            raise
    
    async def get_act_details(self, siren: str, act_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific act/document."""
        try:
            response = await self.get(f"/companies/{siren}/acts/{act_id}")
            data = response.json()
            
            return {
                "id": data.get("id"),
                "type": "acte",
                "name": data.get("name"),
                "date_depot": data.get("dateDepot"),
                "download_url": data.get("downloadUrl"),
                "filename": data.get("filename")
            }
            
        except APIError as e:
            if e.status_code == 404:
                return None
            raise
    
    async def get_document_info(self, siren: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific document."""
        try:
            response = await self.get(f"/companies/{siren}/documents/{document_id}")
            data = response.json()
            
            return {
                "id": data.get("id"),
                "type": data.get("type"),
                "name": data.get("name"),
                "date_depot": data.get("dateDepot"),
                "download_url": data.get("downloadUrl"),
                "filename": data.get("filename"),
                "size": data.get("size")
            }
            
        except APIError as e:
            if e.status_code == 404:
                return None
            raise