"""RGE (Reconnu Garant de l'Environnement) API client."""

from typing import Optional, List, Dict, Any
from datetime import datetime, date

from .base import BaseAPIClient, APIError
from ..resilience import circuit_breaker


class RGEAPI(BaseAPIClient):
    """Client for RGE API (environmental certifications)."""
    
    def __init__(self):
        super().__init__(
            base_url="https://data.ademe.fr/data-fair/api/v1/datasets/liste-des-entreprises-rge-2",
            api_name="rge",
            rate_limit=600  # 600 req/min
        )
        # No authentication required for RGE
    
    async def get_headers(self) -> Dict[str, str]:
        """Get headers for RGE API."""
        return {
            "Accept": "application/json",
            "User-Agent": "Firmia MCP Server/0.1.0"
        }
    
    @circuit_breaker(
        name="rge",
        failure_threshold=5,
        recovery_timeout=60
    )
    async def search_certified_companies(
        self,
        query: Optional[str] = None,
        siren: Optional[str] = None,
        postal_code: Optional[str] = None,
        certification_domain: Optional[str] = None,
        certification_type: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Search RGE certified companies."""
        # Build query parameters
        params = {
            "size": limit,
            "skip": offset,
            "qs": ""  # Query string parts
        }
        
        qs_parts = []
        
        if siren:
            qs_parts.append(f'siret:"{siren}*"')  # Match any SIRET starting with SIREN
        
        if query:
            qs_parts.append(f'("{query}")')
        
        if postal_code:
            qs_parts.append(f'code_postal:"{postal_code}"')
        
        if certification_domain:
            qs_parts.append(f'domaine_travaux:"{certification_domain}"')
        
        if certification_type:
            qs_parts.append(f'certificat:"{certification_type}"')
        
        if qs_parts:
            params["qs"] = " AND ".join(qs_parts)
        
        # Make request
        response = await self._make_request(
            "GET",
            "/lines",
            params=params
        )
        
        return self._parse_search_response(response)
    
    def _parse_search_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse RGE search response."""
        companies = []
        
        for result in response.get("results", []):
            company = {
                "siret": result.get("siret"),
                "siren": result.get("siret", "")[:9] if result.get("siret") else None,
                "name": result.get("nom_entreprise"),
                "commercial_name": result.get("nom_commercial"),
                
                # Address
                "address": {
                    "street": result.get("adresse"),
                    "postal_code": result.get("code_postal"),
                    "city": result.get("commune"),
                    "department": result.get("departement"),
                    "region": result.get("region")
                },
                
                # Contact
                "phone": result.get("telephone"),
                "email": result.get("email"),
                "website": result.get("site_internet"),
                
                # Certifications
                "certifications": self._parse_certifications(result),
                
                # Meta
                "last_update": result.get("date_mise_a_jour"),
                "data_source": "ADEME"
            }
            
            companies.append(company)
        
        return {
            "total": response.get("total", 0),
            "companies": companies,
            "limit": limit,
            "offset": offset
        }
    
    def _parse_certifications(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse certification details from result."""
        certifications = []
        
        # RGE data structure has certification info in various fields
        cert_data = {
            "certificate": result.get("certificat"),
            "certificate_name": result.get("nom_certificat"),
            "certifying_body": result.get("organisme"),
            "validity_date": result.get("date_validite"),
            "domain": result.get("domaine_travaux"),
            "meta_domain": result.get("meta_domaine"),
            "work_codes": result.get("code_travaux", "").split(",") if result.get("code_travaux") else [],
            "work_labels": result.get("libelle_travaux", "").split("|") if result.get("libelle_travaux") else []
        }
        
        # Create certification entry
        if cert_data["certificate"]:
            certifications.append({
                "type": "RGE",
                "code": cert_data["certificate"],
                "name": cert_data["certificate_name"],
                "certifying_body": cert_data["certifying_body"],
                "validity_date": cert_data["validity_date"],
                "domain": cert_data["domain"],
                "meta_domain": cert_data["meta_domain"],
                "competencies": self._format_competencies(
                    cert_data["work_codes"],
                    cert_data["work_labels"]
                ),
                "is_valid": self._check_validity(cert_data["validity_date"])
            })
        
        return certifications
    
    def _format_competencies(
        self,
        codes: List[str],
        labels: List[str]
    ) -> List[Dict[str, str]]:
        """Format work competencies."""
        competencies = []
        
        # Pair codes with labels
        for i, code in enumerate(codes):
            if code:
                competency = {
                    "code": code.strip(),
                    "label": labels[i].strip() if i < len(labels) else ""
                }
                competencies.append(competency)
        
        return competencies
    
    def _check_validity(self, validity_date_str: str) -> bool:
        """Check if certification is still valid."""
        if not validity_date_str:
            return False
        
        try:
            validity_date = datetime.fromisoformat(validity_date_str.replace("Z", "+00:00"))
            return validity_date > datetime.utcnow()
        except:
            return False
    
    async def get_company_certifications(self, siren: str) -> List[Dict[str, Any]]:
        """Get all RGE certifications for a company."""
        result = await self.search_certified_companies(
            siren=siren,
            limit=100  # Get all certifications
        )
        
        # Aggregate all certifications
        all_certifications = []
        for company in result["companies"]:
            all_certifications.extend(company["certifications"])
        
        # Remove duplicates and sort by validity
        seen = set()
        unique_certs = []
        for cert in all_certifications:
            cert_key = f"{cert['code']}_{cert['domain']}"
            if cert_key not in seen:
                seen.add(cert_key)
                unique_certs.append(cert)
        
        # Sort by validity date
        unique_certs.sort(
            key=lambda x: x.get("validity_date", ""),
            reverse=True
        )
        
        return unique_certs
    
    async def check_certification_status(self, siren: str) -> Dict[str, Any]:
        """Check RGE certification status for a company."""
        certifications = await self.get_company_certifications(siren)
        
        # Analyze certifications
        active_certs = [c for c in certifications if c["is_valid"]]
        expired_certs = [c for c in certifications if not c["is_valid"]]
        
        # Group by domain
        domains = {}
        for cert in active_certs:
            domain = cert["meta_domain"] or cert["domain"]
            if domain not in domains:
                domains[domain] = []
            domains[domain].append(cert)
        
        return {
            "siren": siren,
            "is_rge_certified": len(active_certs) > 0,
            "total_certifications": len(certifications),
            "active_certifications": len(active_certs),
            "expired_certifications": len(expired_certs),
            "certification_domains": list(domains.keys()),
            "certifications": active_certs,
            "next_expiry": min(
                [c["validity_date"] for c in active_certs],
                default=None
            ) if active_certs else None
        }
    
    async def search_by_competency(
        self,
        competency_code: str,
        postal_code: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Search companies by specific RGE competency."""
        # Search using work code
        return await self.search_certified_companies(
            query=competency_code,
            postal_code=postal_code,
            limit=limit,
            offset=offset
        )
    
    async def get_certification_statistics(
        self,
        department: Optional[str] = None,
        region: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get RGE certification statistics for a geographic area."""
        # This would require additional endpoints or data processing
        # For now, return a placeholder
        return {
            "department": department,
            "region": region,
            "total_certified_companies": None,
            "by_domain": {},
            "by_certification_type": {},
            "message": "Statistics endpoint not yet implemented"
        }
    
    def get_domain_labels(self) -> Dict[str, str]:
        """Get human-readable labels for RGE domains."""
        return {
            "ENR": "Énergies renouvelables",
            "ISOLATION": "Isolation thermique",
            "CHAUFFAGE": "Chauffage et eau chaude",
            "MENUISERIE": "Menuiseries extérieures",
            "GLOBAL": "Rénovation globale",
            "VENTILATION": "Ventilation",
            "AUDIT": "Audit énergétique"
        }
    
    def get_certification_types(self) -> Dict[str, str]:
        """Get RGE certification types and their descriptions."""
        return {
            "QUALIBAT": "Qualification des entreprises du bâtiment",
            "QUALIT'ENR": "Installations d'énergies renouvelables",
            "QUALIFELEC": "Installations électriques",
            "QUALIBOIS": "Installations de chauffage au bois",
            "QUALISOL": "Installations solaires thermiques",
            "QUALIPAC": "Pompes à chaleur",
            "QUALIPV": "Installations photovoltaïques",
            "ECO_ARTISAN": "Éco-artisan (CAPEB)",
            "PRO_PAILLE": "Construction en paille",
            "CERTIBAT": "Rénovation énergétique",
            "CEQUAMI": "Maisons individuelles",
            "CERQUAL": "Logements collectifs",
            "OPQIBI": "Ingénierie"
        }