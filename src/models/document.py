"""Document-related models for Firmia MCP Server."""

from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class Document(BaseModel):
    """Official document information."""
    id: Optional[str] = None
    siren: str
    type: Literal["acte", "bilan", "statuts", "kbis", "attestation_fiscale", "attestation_sociale"]
    name: str
    year: Optional[int] = None
    date_depot: Optional[datetime] = None
    size: Optional[int] = Field(None, description="File size in bytes")
    url: Optional[str] = None
    filename: Optional[str] = None
    content_type: str = "application/pdf"
    
    # Metadata
    source: str  # Which API provided this document
    expires_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class DownloadDocumentInput(BaseModel):
    """Input parameters for document download."""
    siren: str = Field(..., pattern="^[0-9]{9}$")
    document_type: Literal[
        "acte", "bilan", "statuts", "kbis", 
        "attestation_fiscale", "attestation_sociale"
    ]
    year: Optional[int] = Field(None, ge=2000, le=2025)
    format: Literal["pdf", "url"] = Field("pdf", description="Return format")


class DownloadDocumentOutput(BaseModel):
    """Output for document download."""
    # For format="url"
    url: Optional[str] = None
    expires_at: Optional[datetime] = None
    
    # For format="pdf"
    content: Optional[str] = Field(None, description="Base64 encoded PDF content")
    filename: Optional[str] = None
    content_type: str = "application/pdf"
    size: Optional[int] = None
    
    # Metadata
    document_type: str
    siren: str
    year: Optional[int] = None
    source: str
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }