"""Legal announcement models for Firmia MCP Server."""

from typing import Optional, List, Dict, Any
from datetime import date, datetime
from enum import Enum
from pydantic import BaseModel, Field


class AnnouncementType(str, Enum):
    """Types of legal announcements."""
    VENTE_CESSION = "vente_cession"
    CREATION_ETABLISSEMENT = "creation_etablissement"
    PROCEDURE_COLLECTIVE = "procedure_collective"
    DEPOT_COMPTES = "depot_comptes"
    RECTIFICATIF = "rectificatif"
    AUTRE = "autre"


class LegalAnnouncement(BaseModel):
    """Legal announcement from BODACC."""
    id: str = Field(..., description="Unique announcement ID")
    type: AnnouncementType = Field(..., description="Type of announcement")
    type_label: str = Field(..., description="Human-readable type label")
    publication_date: str = Field(..., description="Publication date in BODACC")
    bodacc_number: Optional[str] = Field(None, description="BODACC bulletin number")
    court: Optional[str] = Field(None, description="Court/tribunal name")
    
    # Company info
    siren: Optional[str] = Field(None, description="Company SIREN")
    company_name: Optional[str] = Field(None, description="Company name")
    
    # Content
    title: Optional[str] = Field(None, description="Announcement title")
    content: Optional[str] = Field(None, description="Full announcement text")
    
    # Document
    pdf_url: Optional[str] = Field(None, description="URL to PDF document")
    
    class Config:
        use_enum_values = True


class SearchAnnouncementsInput(BaseModel):
    """Input parameters for announcement search."""
    siren: Optional[str] = Field(None, pattern="^[0-9]{9}$", description="Company SIREN")
    company_name: Optional[str] = Field(None, description="Company name")
    announcement_type: Optional[AnnouncementType] = Field(None, description="Filter by type")
    date_from: Optional[date] = Field(None, description="Start date")
    date_to: Optional[date] = Field(None, description="End date")
    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(20, ge=1, le=100, description="Results per page")
    force_refresh: bool = Field(False, description="Force refresh from API")


class SearchAnnouncementsOutput(BaseModel):
    """Output for announcement search."""
    total_results: int = Field(..., description="Total number of results")
    announcements: List[LegalAnnouncement] = Field(..., description="List of announcements")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Results per page")
    total_pages: int = Field(..., description="Total number of pages")
    filters_applied: Dict[str, Any] = Field(..., description="Applied filters")
    metadata: Dict[str, Any] = Field(..., description="Search metadata")