"""API Entreprise client implementation."""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base import BaseAPIClient, APIError, RateLimitError
from ..config import settings
from ..auth import get_auth_manager

class APIEntrepriseAPI(BaseAPIClient):
    """Client for API Entreprise endpoints."""
    
    def __init__(self):
        super().__init__(
            base_url="https://entreprise.api.gouv.fr/v3",
            api_name="api_entreprise",
            rate_limit=250  # JSON endpoints
        )
        self.auth_manager = get_auth_manager()
        self.pdf_rate_limit = 50  # Lower rate limit for PDF endpoints
    
    async def get_headers(self) -> Dict[str, str]:
        """Get headers with API token."""
        headers = await self.auth_manager.get_headers("api_entreprise")
        headers.update({
            "Accept": "application/json",
            "X-Api-Key": settings.api_entreprise_token,
            "Context": "MCP Server",
            "Recipient": settings.api_entreprise_recipient or "13002526500013",
            "Object": "Company intelligence"
        })
        return headers
    
    async def download_document(
        self,
        endpoint: str,
        format: str = "pdf"
    ) -> Dict[str, Any]:
        """Download a document from API Entreprise."""
        # Check PDF rate limit for PDF downloads
        if format == "pdf":
            allowed, retry_after = await self.cache_manager.check_rate_limit(
                f"{self.api_name}_pdf"
            )
            if not allowed:
                raise RateLimitError(f"PDF rate limit exceeded. Retry after {retry_after}s")
        
        headers = await self.get_headers()
        if format == "pdf":
            headers["Accept"] = "application/pdf"
        
        # Make request
        response = await self._make_request(
            "GET",
            endpoint,
            headers=headers,
            timeout=30  # Longer timeout for documents
        )
        
        if format == "pdf":
            # For PDF, return raw content
            return {
                "content": response,  # Raw bytes
                "mime_type": "application/pdf",
                "filename": f"document_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
            }
        
        return response
    
    async def get_document_url(self, endpoint: str) -> Dict[str, str]:
        """Get a temporary download URL for a document."""
        headers = await self.get_headers()
        headers["Accept"] = "application/json"
        
        # Request URL generation
        response = await self._make_request(
            "GET",
            f"{endpoint}/url",
            headers=headers
        )
        
        return {
            "url": response.get("url"),
            "expires_at": response.get("expires_at")
        }
    
    async def check_document_availability(self, endpoint: str) -> bool:
        """Check if a document is available."""
        try:
            headers = await self.get_headers()
            response = await self._make_request(
                "HEAD",
                endpoint,
                headers=headers
            )
            return True
        except APIError as e:
            if e.status_code == 404:
                return False
            raise
    
    async def list_available_documents(self, siren: str) -> List[Dict[str, Any]]:
        """List available documents for a company."""
        documents = []
        
        # Check each document type
        doc_types = [
            ("extrait_kbis", "kbis", "Extrait KBIS"),
            ("bilans_bdf", "bilan", "Bilans Banque de France"),
            ("attestations_fiscales_dgfip", "attestation_fiscale", "Attestation fiscale DGFIP"),
            ("attestations_sociales_acoss", "attestation_sociale", "Attestation sociale ACOSS"),
            ("liasses_fiscales_dgfip", "liasse_fiscale", "Liasse fiscale DGFIP")
        ]
        
        for endpoint_part, doc_type, name in doc_types:
            if await self.check_document_availability(f"/entreprises/{siren}/{endpoint_part}"):
                doc_info = {
                    "type": doc_type,
                    "id": f"{doc_type}_{siren}",
                    "name": name,
                    "available": True
                }
                
                # For bilans, check multiple years
                if doc_type == "bilan":
                    for year in range(datetime.utcnow().year - 1, datetime.utcnow().year - 5, -1):
                        year_available = await self.check_document_availability(
                            f"/entreprises/{siren}/{endpoint_part}/{year}"
                        )
                        if year_available:
                            documents.append({
                                **doc_info,
                                "id": f"{doc_type}_{siren}_{year}",
                                "name": f"{name} {year}",
                                "year": year
                            })
                else:
                    documents.append(doc_info)
        
        return documents
    
    async def get_company_info(self, siren: str) -> Dict[str, Any]:
        """Get basic company information."""
        endpoint = f"/entreprises/{siren}"
        headers = await self.get_headers()
        
        return await self._make_request("GET", endpoint, headers=headers)
    
    async def get_financial_data(self, siren: str, year: Optional[int] = None) -> Dict[str, Any]:
        """Get financial data (bilans)."""
        endpoint = f"/entreprises/{siren}/bilans_bdf"
        if year:
            endpoint += f"/{year}"
        
        headers = await self.get_headers()
        return await self._make_request("GET", endpoint, headers=headers)
    
    async def get_fiscal_attestation(self, siren: str) -> Dict[str, Any]:
        """Get fiscal attestation."""
        endpoint = f"/entreprises/{siren}/attestations_fiscales_dgfip"
        headers = await self.get_headers()
        
        return await self._make_request("GET", endpoint, headers=headers)
    
    async def get_social_attestation(self, siren: str) -> Dict[str, Any]:
        """Get social attestation."""
        endpoint = f"/entreprises/{siren}/attestations_sociales_acoss"
        headers = await self.get_headers()
        
        return await self._make_request("GET", endpoint, headers=headers)