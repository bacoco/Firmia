"""BODACC (Bulletin Officiel Des Annonces Civiles et Commerciales) API client."""

from typing import Optional, List, Dict, Any
from datetime import datetime, date

from .base import BaseAPIClient, APIError
from ..resilience import circuit_breaker


class BODACCAPI(BaseAPIClient):
    """Client for BODACC API (legal announcements)."""
    
    def __init__(self):
        super().__init__(
            base_url="https://bodacc-datadila.opendatasoft.com/api/explore/v2.1",
            api_name="bodacc",
            rate_limit=600  # 600 req/min
        )
        # No authentication required for BODACC
    
    async def get_headers(self) -> Dict[str, str]:
        """Get headers for BODACC API."""
        return {
            "Accept": "application/json",
            "User-Agent": "Firmia MCP Server/0.1.0"
        }
    
    @circuit_breaker(
        name="bodacc",
        failure_threshold=5,
        recovery_timeout=60
    )
    async def search_announcements(
        self,
        siren: Optional[str] = None,
        denomination: Optional[str] = None,
        announcement_type: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Search BODACC announcements."""
        # Build query
        where_clauses = []
        
        if siren:
            where_clauses.append(f'registre_numero_dossier_greffe_debiteur="{siren}"')
        
        if denomination:
            # Search in multiple denomination fields
            denom_clause = f'(denomination like "{denomination}" OR ' \
                          f'nom_personne_physique like "{denomination}" OR ' \
                          f'personne_morale_denomination like "{denomination}")'
            where_clauses.append(denom_clause)
        
        if announcement_type:
            where_clauses.append(f'typeavis="{announcement_type}"')
        
        if date_from:
            where_clauses.append(f'dateparution>="{date_from.isoformat()}"')
        
        if date_to:
            where_clauses.append(f'dateparution<="{date_to.isoformat()}"')
        
        # Construct params
        params = {
            "dataset": "annonces-commerciales",
            "limit": limit,
            "offset": offset,
            "order_by": "dateparution desc"
        }
        
        if where_clauses:
            params["where"] = " AND ".join(where_clauses)
        
        # Make request
        response = await self._make_request(
            "GET",
            "/catalog/datasets/annonces-commerciales/records",
            params=params
        )
        
        return self._parse_announcements_response(response)
    
    def _parse_announcements_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse BODACC search response."""
        announcements = []
        
        for record in response.get("records", []):
            fields = record.get("fields", {})
            
            announcement = {
                "id": record.get("id"),
                "type": fields.get("typeavis"),
                "type_label": self._get_announcement_type_label(fields.get("typeavis")),
                "publication_date": fields.get("dateparution"),
                "bodacc_number": fields.get("numerobodacc"),
                "court": fields.get("tribunal"),
                "registry_number": fields.get("registre_numero_dossier_greffe_debiteur"),
                
                # Company info
                "siren": fields.get("registre_numero_dossier_greffe_debiteur"),
                "denomination": fields.get("denomination") or fields.get("personne_morale_denomination"),
                "commercial_name": fields.get("nom_commercial"),
                "legal_form": fields.get("forme_juridique"),
                
                # Address
                "address": {
                    "street": fields.get("adresse_ligne_1"),
                    "complement": fields.get("adresse_ligne_2"),
                    "postal_code": fields.get("adresse_code_postal"),
                    "city": fields.get("adresse_ville"),
                    "country": fields.get("adresse_pays", "France")
                },
                
                # Announcement content
                "title": fields.get("titre"),
                "content": fields.get("contenu") or fields.get("jugement"),
                
                # Procedure info (for collective procedures)
                "procedure_type": fields.get("type_procedure"),
                "procedure_date": fields.get("date_jugement"),
                
                # People involved
                "administrators": self._parse_administrators(fields),
                
                # URLs
                "pdf_url": fields.get("publicationavis_facette"),
                "source_url": fields.get("publicationavis")
            }
            
            announcements.append(announcement)
        
        return {
            "total": response.get("total_count", 0),
            "announcements": announcements,
            "limit": response.get("limit", limit),
            "offset": response.get("offset", offset)
        }
    
    def _get_announcement_type_label(self, type_code: str) -> str:
        """Get human-readable label for announcement type."""
        type_labels = {
            "A": "Vente et cession",
            "B": "Création d'établissement",
            "C": "Procédures collectives",
            "D": "Dépôt des comptes",
            "P": "Rectificatif ou annulation"
        }
        return type_labels.get(type_code, type_code)
    
    def _parse_administrators(self, fields: Dict[str, Any]) -> List[Dict[str, str]]:
        """Parse administrators/liquidators from announcement."""
        administrators = []
        
        # Check various administrator fields
        admin_fields = [
            ("administrateur", "Administrateur"),
            ("mandataire_judiciaire", "Mandataire judiciaire"),
            ("liquidateur", "Liquidateur"),
            ("commissaire_priseur", "Commissaire-priseur")
        ]
        
        for field_name, role in admin_fields:
            if fields.get(field_name):
                administrators.append({
                    "name": fields[field_name],
                    "role": role
                })
        
        return administrators
    
    async def get_company_timeline(
        self,
        siren: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get chronological timeline of BODACC announcements for a company."""
        # Search all announcements for this SIREN
        result = await self.search_announcements(
            siren=siren,
            limit=limit
        )
        
        # Group by type and sort chronologically
        timeline = []
        for announcement in result["announcements"]:
            timeline.append({
                "date": announcement["publication_date"],
                "type": announcement["type"],
                "type_label": announcement["type_label"],
                "title": announcement["title"],
                "court": announcement["court"],
                "content_summary": self._summarize_content(announcement),
                "bodacc_number": announcement["bodacc_number"],
                "id": announcement["id"]
            })
        
        # Sort by date
        timeline.sort(key=lambda x: x["date"] or "", reverse=True)
        
        return timeline
    
    def _summarize_content(self, announcement: Dict[str, Any]) -> str:
        """Create a brief summary of announcement content."""
        content = announcement.get("content", "")
        if not content:
            return ""
        
        # Truncate long content
        if len(content) > 200:
            return content[:197] + "..."
        
        return content
    
    async def get_collective_procedures(
        self,
        siren: str
    ) -> List[Dict[str, Any]]:
        """Get collective procedures (bankruptcy, liquidation, etc.) for a company."""
        # Search for type C announcements (collective procedures)
        result = await self.search_announcements(
            siren=siren,
            announcement_type="C",
            limit=100
        )
        
        procedures = []
        for announcement in result["announcements"]:
            procedure = {
                "date": announcement["procedure_date"] or announcement["publication_date"],
                "type": announcement["procedure_type"],
                "court": announcement["court"],
                "content": announcement["content"],
                "administrators": announcement["administrators"],
                "bodacc_reference": {
                    "number": announcement["bodacc_number"],
                    "date": announcement["publication_date"],
                    "id": announcement["id"]
                }
            }
            procedures.append(procedure)
        
        return procedures
    
    async def check_financial_health(self, siren: str) -> Dict[str, Any]:
        """Quick check of company financial health based on BODACC announcements."""
        # Get recent announcements
        announcements = await self.search_announcements(
            siren=siren,
            limit=100
        )
        
        # Analyze announcement types
        type_counts = {}
        latest_by_type = {}
        
        for ann in announcements["announcements"]:
            ann_type = ann["type"]
            type_counts[ann_type] = type_counts.get(ann_type, 0) + 1
            
            # Track latest of each type
            if ann_type not in latest_by_type or ann["publication_date"] > latest_by_type[ann_type]["date"]:
                latest_by_type[ann_type] = {
                    "date": ann["publication_date"],
                    "title": ann["title"],
                    "content_summary": self._summarize_content(ann)
                }
        
        # Calculate health indicators
        has_collective_procedures = type_counts.get("C", 0) > 0
        recent_procedures = False
        
        if has_collective_procedures and "C" in latest_by_type:
            proc_date = datetime.fromisoformat(latest_by_type["C"]["date"])
            recent_procedures = (datetime.utcnow() - proc_date).days < 365
        
        return {
            "siren": siren,
            "total_announcements": announcements["total"],
            "announcement_types": type_counts,
            "has_collective_procedures": has_collective_procedures,
            "recent_collective_procedures": recent_procedures,
            "latest_announcements": latest_by_type,
            "financial_risk": "HIGH" if recent_procedures else ("MEDIUM" if has_collective_procedures else "LOW")
        }