"""Company-related models for Firmia MCP Server."""

from typing import Optional, List, Dict, Any, Literal
from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator


class Address(BaseModel):
    """Address information."""
    street: Optional[str] = None
    postal_code: str
    city: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class Executive(BaseModel):
    """Company executive/director information."""
    role: str
    name: str
    first_name: Optional[str] = None
    birth_date: Optional[str] = None  # Format: "YYYY-MM" for privacy
    nationality: Optional[str] = None


class Establishment(BaseModel):
    """Company establishment (SIRET) information."""
    siret: str
    is_headquarters: bool = False
    address: Address
    employee_range: Optional[str] = None
    activity: Optional[Dict[str, Any]] = None


class Financials(BaseModel):
    """Company financial information."""
    capital: Optional[Dict[str, Any]] = Field(None, description="Capital information")
    revenue: Optional[float] = None
    result: Optional[float] = None
    fiscal_year: Optional[int] = None


class Certifications(BaseModel):
    """Company certifications."""
    rge: Optional[Dict[str, Any]] = Field(None, description="RGE certification info")
    bio: bool = False
    ess: bool = False
    qualiopi: bool = False


class Company(BaseModel):
    """Complete company information."""
    # Identification
    siren: str = Field(..., pattern="^[0-9]{9}$")
    siret: Optional[str] = Field(None, pattern="^[0-9]{14}$")
    denomination: str
    sigle: Optional[str] = None
    
    # Legal information
    legal_form: Optional[Dict[str, str]] = None  # {code, label}
    naf_code: Optional[str] = None
    creation_date: Optional[date] = None
    cessation_date: Optional[date] = None
    is_active: bool = True
    
    # Structure
    employee_range: Optional[str] = None
    is_headquarters: Optional[bool] = None
    
    # Location
    address: Optional[Address] = None
    
    # People
    executives: List[Executive] = Field(default_factory=list)
    
    # Establishments
    establishments: List[Establishment] = Field(default_factory=list)
    
    # Financial
    financials: Optional[Financials] = None
    
    # Certifications
    certifications: Optional[Certifications] = None
    
    # Metadata
    source: List[str] = Field(default_factory=list)
    last_update: datetime = Field(default_factory=datetime.utcnow)
    privacy_status: Optional[str] = None  # "O" (open) or "P" (protected)


class CompanySearchResult(BaseModel):
    """Single company search result."""
    siren: str
    siret: Optional[str] = None
    name: str
    legal_form: Optional[str] = None
    naf_code: Optional[str] = None
    employee_range: Optional[str] = None
    address: Optional[Address] = None
    creation_date: Optional[date] = None
    is_active: bool = True
    is_headquarters: Optional[bool] = None
    source: Literal["recherche_entreprises", "rna", "sirene"]


class SearchFilters(BaseModel):
    """Search filters for company search."""
    naf_code: Optional[str] = Field(None, pattern="^[0-9]{2}\\.[0-9]{2}[A-Z]?$")
    postal_code: Optional[str] = Field(None, pattern="^[0-9]{5}$")
    department: Optional[str] = Field(None, pattern="^[0-9]{2,3}$")
    employee_range: Optional[str] = Field(None)
    legal_status: Optional[Literal["active", "ceased", "all"]] = "all"


class SearchCompaniesInput(BaseModel):
    """Input parameters for company search."""
    query: str = Field(..., min_length=2, max_length=200, description="Search query")
    filters: Optional[SearchFilters] = None
    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(20, ge=1, le=25, description="Results per page")
    include_associations: bool = Field(False, description="Include associations in search")


class Pagination(BaseModel):
    """Pagination information."""
    total: int
    page: int
    per_page: int
    total_pages: int


class SearchCompaniesOutput(BaseModel):
    """Output for company search."""
    results: List[CompanySearchResult]
    pagination: Pagination


class GetCompanyProfileInput(BaseModel):
    """Input parameters for getting company profile."""
    siren: str = Field(..., pattern="^[0-9]{9}$")
    include_establishments: bool = True
    include_documents: bool = False
    include_financials: bool = True
    include_certifications: bool = True
    include_bank_info: bool = Field(False, description="Requires special authorization")


class GetCompanyProfileOutput(BaseModel):
    """Output for company profile."""
    company: Company
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata about data sources and freshness"
    )