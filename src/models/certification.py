"""Certification models for Firmia MCP Server."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class CertificationType(str, Enum):
    """Types of certifications."""
    RGE = "RGE"
    BIO = "BIO"
    ESS = "ESS"
    QUALIOPI = "QUALIOPI"
    ISO = "ISO"
    AUTRE = "AUTRE"


class CertificationStatus(str, Enum):
    """Certification status."""
    ACTIVE = "active"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    PENDING = "pending"


class Certification(BaseModel):
    """Company certification information."""
    type: str = Field(..., description="Certification type (RGE, BIO, etc.)")
    code: str = Field(..., description="Certification code")
    name: str = Field(..., description="Certification name")
    certifying_body: str = Field(..., description="Certifying organization")
    validity_start: Optional[str] = Field(None, description="Start date of validity")
    validity_end: Optional[str] = Field(None, description="End date of validity")
    is_valid: bool = Field(..., description="Whether certification is currently valid")
    domain: Optional[str] = Field(None, description="Certification domain")
    competencies: List[Dict[str, str]] = Field(default_factory=list, description="List of competencies")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class CheckCertificationsInput(BaseModel):
    """Input parameters for certification check."""
    siren: str = Field(..., pattern="^[0-9]{9}$", description="Company SIREN")
    force_refresh: bool = Field(False, description="Force refresh from source")


class CheckCertificationsOutput(BaseModel):
    """Output for certification check."""
    siren: str = Field(..., description="Company SIREN")
    has_certifications: bool = Field(..., description="Whether company has any certifications")
    certifications: List[Certification] = Field(..., description="List of certifications")
    certification_summary: Dict[str, Any] = Field(..., description="Summary by certification type")
    metadata: Dict[str, Any] = Field(..., description="Check metadata")


class CertificationSearchInput(BaseModel):
    """Input parameters for certification search."""
    query: Optional[str] = Field(None, description="Search query")
    postal_code: Optional[str] = Field(None, description="Filter by postal code")
    certification_type: Optional[CertificationType] = Field(None, description="Filter by type")
    domain: Optional[str] = Field(None, description="Filter by domain")
    only_valid: bool = Field(True, description="Only show valid certifications")
    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(20, ge=1, le=100, description="Results per page")


class CertificationSearchOutput(BaseModel):
    """Output for certification search."""
    total_results: int = Field(..., description="Total number of results")
    companies: List[Dict[str, Any]] = Field(..., description="List of certified companies")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Results per page")
    total_pages: int = Field(..., description="Total number of pages")
    filters_applied: Dict[str, Any] = Field(..., description="Applied filters")
    metadata: Dict[str, Any] = Field(..., description="Search metadata")