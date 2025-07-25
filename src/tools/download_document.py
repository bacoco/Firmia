"""Document download MCP tool implementation."""

import asyncio
import base64
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime, timedelta

from mcp.server.fastmcp import Tool
from pydantic import Field
from structlog import get_logger

from ..models.document import (
    DownloadDocumentInput,
    DownloadDocumentOutput,
    Document
)
from ..api import APIEntrepriseAPI, INPIRNEAPI
from ..cache import get_cache_manager
from ..privacy import get_audit_logger
from ..resilience import circuit_breaker

logger = get_logger(__name__)


class DocumentDownloadService:
    """Service for downloading documents from various sources."""
    
    def __init__(self):
        self.api_entreprise = APIEntrepriseAPI()
        self.inpi_api = INPIRNEAPI()
        self.cache_manager = get_cache_manager()
        self.audit_logger = get_audit_logger()
        self.logger = logger.bind(component="document_service")
    
    async def download_document(
        self,
        params: DownloadDocumentInput,
        caller_id: str = "mcp_client",
        ip_address: Optional[str] = None
    ) -> DownloadDocumentOutput:
        """Download a document from the appropriate source."""
        start_time = datetime.utcnow()
        
        # Build cache key
        cache_key = f"doc:{params.siren}:{params.document_type}"
        if params.year:
            cache_key += f":{params.year}"
        
        # Check cache first (only for PDF format)
        if params.format == "pdf":
            cached_doc = await self.cache_manager.get_document(cache_key)
            if cached_doc:
                self.logger.info("document_cache_hit", 
                               siren=params.siren,
                               document_type=params.document_type)
                
                # Still log audit even for cached access
                await self._log_audit(
                    params,
                    caller_id,
                    ip_address,
                    "cache_hit",
                    start_time
                )
                
                return DownloadDocumentOutput(**cached_doc)
        
        # Route based on document type
        try:
            if params.document_type == "kbis":
                result = await self._download_kbis(params)
            elif params.document_type in ["acte", "statuts"]:
                result = await self._download_from_inpi(params)
            elif params.document_type in ["bilan", "attestation_fiscale", "attestation_sociale"]:
                result = await self._download_from_api_entreprise(params)
            else:
                raise ValueError(f"Unsupported document type: {params.document_type}")
            
            # Cache the result (only PDFs)
            if params.format == "pdf" and result.content:
                await self.cache_manager.set_document(
                    cache_key,
                    result.dict(),
                    ttl=86400  # 24 hours for documents
                )
            
            # Audit log
            await self._log_audit(
                params,
                caller_id,
                ip_address,
                "download",
                start_time
            )
            
            return result
            
        except Exception as e:
            self.logger.error("document_download_failed",
                            siren=params.siren,
                            document_type=params.document_type,
                            error=str(e))
            
            # Log failed attempt
            await self._log_audit(
                params,
                caller_id,
                ip_address,
                "download_failed",
                start_time,
                error=str(e)
            )
            
            raise
    
    async def _download_kbis(self, params: DownloadDocumentInput) -> DownloadDocumentOutput:
        """Download KBIS from API Entreprise."""
        try:
            endpoint = f"/entreprises/{params.siren}/extrait_kbis"
            
            if params.format == "url":
                # Get temporary URL
                url_info = await self.api_entreprise.get_document_url(endpoint)
                return DownloadDocumentOutput(
                    url=url_info["url"],
                    expires_at=datetime.utcnow() + timedelta(hours=1),
                    document_type="kbis",
                    siren=params.siren,
                    source="api_entreprise"
                )
            
            # Download PDF
            response = await self.api_entreprise.download_document(endpoint, "pdf")
            
            return DownloadDocumentOutput(
                content=base64.b64encode(response["content"]).decode(),
                filename=f"kbis_{params.siren}_{datetime.utcnow().strftime('%Y%m%d')}.pdf",
                content_type="application/pdf",
                size=len(response["content"]),
                document_type="kbis",
                siren=params.siren,
                source="api_entreprise"
            )
            
        except Exception as e:
            self.logger.error("kbis_download_failed",
                            siren=params.siren,
                            error=str(e))
            raise
    
    async def _download_from_api_entreprise(
        self,
        params: DownloadDocumentInput
    ) -> DownloadDocumentOutput:
        """Download document from API Entreprise."""
        # Map document types to endpoints
        endpoint_map = {
            "bilan": f"/entreprises/{params.siren}/bilans_bdf",
            "attestation_fiscale": f"/entreprises/{params.siren}/attestations_fiscales_dgfip",
            "attestation_sociale": f"/entreprises/{params.siren}/attestations_sociales_acoss"
        }
        
        endpoint = endpoint_map[params.document_type]
        if params.year and params.document_type == "bilan":
            endpoint += f"/{params.year}"
        
        try:
            if params.format == "url":
                # Get temporary URL
                url_info = await self.api_entreprise.get_document_url(endpoint)
                return DownloadDocumentOutput(
                    url=url_info["url"],
                    expires_at=datetime.utcnow() + timedelta(hours=1),
                    document_type=params.document_type,
                    siren=params.siren,
                    year=params.year,
                    source="api_entreprise"
                )
            
            # Download PDF
            response = await self.api_entreprise.download_document(endpoint, "pdf")
            
            # Build filename
            filename = f"{params.document_type}_{params.siren}"
            if params.year:
                filename += f"_{params.year}"
            filename += f"_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
            
            return DownloadDocumentOutput(
                content=base64.b64encode(response["content"]).decode(),
                filename=filename,
                content_type="application/pdf",
                size=len(response["content"]),
                document_type=params.document_type,
                siren=params.siren,
                year=params.year,
                source="api_entreprise"
            )
            
        except Exception as e:
            self.logger.error("api_entreprise_download_failed",
                            siren=params.siren,
                            document_type=params.document_type,
                            error=str(e))
            raise
    
    async def _download_from_inpi(
        self,
        params: DownloadDocumentInput
    ) -> DownloadDocumentOutput:
        """Download document from INPI."""
        try:
            # Get company documents list
            documents = await self.inpi_api.get_company_documents(params.siren)
            
            # Find matching document
            target_doc = None
            for doc in documents:
                if doc["type"] == params.document_type:
                    if params.year:
                        doc_year = doc.get("date_depot", datetime.utcnow()).year
                        if doc_year == params.year:
                            target_doc = doc
                            break
                    else:
                        # Get most recent
                        if not target_doc or doc.get("date_depot", datetime.min) > target_doc.get("date_depot", datetime.min):
                            target_doc = doc
            
            if not target_doc:
                raise ValueError(f"No {params.document_type} found for SIREN {params.siren}")
            
            if params.format == "url":
                # INPI provides direct URLs
                return DownloadDocumentOutput(
                    url=target_doc["url"],
                    expires_at=datetime.utcnow() + timedelta(days=7),  # INPI URLs are longer-lived
                    document_type=params.document_type,
                    siren=params.siren,
                    year=params.year,
                    source="inpi"
                )
            
            # Download the document
            content = await self.inpi_api.download_from_url(target_doc["url"])
            
            return DownloadDocumentOutput(
                content=base64.b64encode(content).decode(),
                filename=target_doc.get("filename", f"{params.document_type}_{params.siren}.pdf"),
                content_type="application/pdf",
                size=len(content),
                document_type=params.document_type,
                siren=params.siren,
                year=params.year,
                source="inpi"
            )
            
        except Exception as e:
            self.logger.error("inpi_download_failed",
                            siren=params.siren,
                            document_type=params.document_type,
                            error=str(e))
            raise
    
    async def _log_audit(
        self,
        params: DownloadDocumentInput,
        caller_id: str,
        ip_address: Optional[str],
        operation: str,
        start_time: datetime,
        error: Optional[str] = None
    ) -> None:
        """Log document access audit."""
        audit_metadata = {
            "document_type": params.document_type,
            "siren": params.siren,
            "year": params.year,
            "format": params.format,
            "error": error
        }
        
        await self.audit_logger.log_access(
            tool="download_document",
            operation=operation,
            caller_id=caller_id,
            siren=params.siren,
            ip_address=ip_address,
            response_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
            status_code=200 if not error else 500,
            metadata=audit_metadata
        )
    
    async def list_available_documents(
        self,
        siren: str
    ) -> List[Document]:
        """Get list of available documents for a company."""
        documents = []
        
        # Check API Entreprise for available documents
        try:
            # KBIS is always available
            documents.append(Document(
                siren=siren,
                type="kbis",
                name="Extrait KBIS",
                source="api_entreprise",
                url=None  # Generated on demand
            ))
            
            # Check for financial documents
            has_bilans = await self.api_entreprise.check_document_availability(
                f"/entreprises/{siren}/bilans_bdf"
            )
            if has_bilans:
                # Get available years
                for year in range(datetime.utcnow().year - 1, datetime.utcnow().year - 5, -1):
                    documents.append(Document(
                        siren=siren,
                        type="bilan",
                        name=f"Bilan {year}",
                        year=year,
                        source="api_entreprise"
                    ))
            
            # Check attestations
            for doc_type, name in [
                ("attestation_fiscale", "Attestation fiscale"),
                ("attestation_sociale", "Attestation sociale")
            ]:
                available = await self.api_entreprise.check_document_availability(
                    f"/entreprises/{siren}/{doc_type}s_dgfip"
                )
                if available:
                    documents.append(Document(
                        siren=siren,
                        type=doc_type,
                        name=name,
                        source="api_entreprise"
                    ))
                    
        except Exception as e:
            self.logger.warning("api_entreprise_list_failed",
                              siren=siren,
                              error=str(e))
        
        # Check INPI for available documents
        try:
            inpi_docs = await self.inpi_api.get_company_documents(siren)
            for doc in inpi_docs:
                documents.append(Document(
                    id=doc.get("id"),
                    siren=siren,
                    type=doc["type"],
                    name=doc["name"],
                    date_depot=doc.get("date_depot"),
                    url=doc.get("url"),
                    filename=doc.get("filename"),
                    source="inpi"
                ))
        except Exception as e:
            self.logger.warning("inpi_list_failed",
                              siren=siren,
                              error=str(e))
        
        return documents
    
    async def close(self) -> None:
        """Close API clients."""
        await self.api_entreprise.close()
        await self.inpi_api.close()


class DownloadDocumentTool(Tool):
    """MCP tool for downloading company documents."""
    
    name = "download_document"
    description = "Download official company documents (KBIS, bilans, actes, etc.)"
    
    def __init__(self):
        super().__init__()
        self.service = DocumentDownloadService()
    
    async def run(
        self,
        siren: str = Field(..., description="Company SIREN (9 digits)", pattern="^[0-9]{9}$"),
        document_type: Literal[
            "acte", "bilan", "statuts", "kbis", 
            "attestation_fiscale", "attestation_sociale"
        ] = Field(..., description="Type of document to download"),
        year: Optional[int] = Field(None, ge=2000, le=2025, description="Year for annual documents"),
        format: Literal["pdf", "url"] = Field("pdf", description="Return format (pdf content or download URL)")
    ) -> Dict[str, Any]:
        """Download a company document."""
        # Build input model
        params = DownloadDocumentInput(
            siren=siren,
            document_type=document_type,
            year=year,
            format=format
        )
        
        # Execute download
        result = await self.service.download_document(params)
        
        # Return as dict for MCP
        return result.dict()


class ListDocumentsTool(Tool):
    """MCP tool for listing available documents."""
    
    name = "list_documents"
    description = "List all available documents for a company"
    
    def __init__(self):
        super().__init__()
        self.service = DocumentDownloadService()
    
    async def run(
        self,
        siren: str = Field(..., description="Company SIREN (9 digits)", pattern="^[0-9]{9}$")
    ) -> Dict[str, Any]:
        """List available documents for a company."""
        documents = await self.service.list_available_documents(siren)
        
        return {
            "siren": siren,
            "documents": [doc.dict() for doc in documents],
            "total_count": len(documents)
        }