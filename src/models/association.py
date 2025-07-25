"""Association models for Firmia MCP Server."""

from typing import Optional, List, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, Field


class Association(BaseModel):
    """Basic association information."""
    rna_id: str = Field(..., description="RNA identifier (W + 9 digits)")
    siren: Optional[str] = Field(None, description="SIREN if applicable")
    siret: Optional[str] = Field(None, description="SIRET of headquarters")
    name: str = Field(..., description="Association name")
    short_name: Optional[str] = Field(None, description="Short name/acronym")
    object: Optional[str] = Field(None, description="Association object/purpose")
    
    # Status
    is_active: bool = Field(True, description="Whether association is active")
    creation_date: Optional[str] = Field(None, description="Creation date")
    dissolution_date: Optional[str] = Field(None, description="Dissolution date if applicable")
    is_public_utility: bool = Field(False, description="Recognized as public utility")
    
    # Address
    address: Dict[str, Optional[str]] = Field(..., description="Main address")
    
    # Contact
    email: Optional[str] = Field(None, description="Contact email")
    website: Optional[str] = Field(None, description="Website URL")
    phone: Optional[str] = Field(None, description="Phone number")


class AssociationDetails(BaseModel):
    """Detailed association information."""
    # Basic info (same as Association)
    rna_id: str = Field(..., description="RNA identifier")
    siren: Optional[str] = Field(None, description="SIREN if applicable")
    siret: Optional[str] = Field(None, description="SIRET of headquarters")
    name: str = Field(..., description="Association name")
    short_name: Optional[str] = Field(None, description="Short name/acronym")
    object: Optional[str] = Field(None, description="Association object/purpose")
    object_social: Optional[str] = Field(None, description="Social object")
    
    # Status
    is_active: bool = Field(True, description="Whether association is active")
    creation_date: Optional[str] = Field(None, description="Creation date")
    declaration_date: Optional[str] = Field(None, description="Declaration date")
    publication_date: Optional[str] = Field(None, description="Journal Officiel publication date")
    dissolution_date: Optional[str] = Field(None, description="Dissolution date if applicable")
    last_update: Optional[str] = Field(None, description="Last update in RNA")
    
    # Type and classification
    type: Optional[str] = Field(None, description="Association type code")
    type_label: Optional[str] = Field(None, description="Type label")
    is_public_utility: bool = Field(False, description="Recognized as public utility")
    is_alsace_moselle: bool = Field(False, description="Alsace-Moselle law association")
    regime: Optional[str] = Field(None, description="Legal regime")
    is_recognized: bool = Field(False, description="Officially recognized")
    
    # Addresses
    headquarters_address: Dict[str, Optional[str]] = Field(..., description="Headquarters address")
    management_address: Dict[str, Optional[str]] = Field(..., description="Management address")
    
    # Administrative
    prefecture: Optional[str] = Field(None, description="Prefecture")
    sub_prefecture: Optional[str] = Field(None, description="Sub-prefecture")
    
    # Financial
    has_ccp: bool = Field(False, description="Has postal checking account")
    has_bank_account: bool = Field(False, description="Has bank account")
    accepts_donations: bool = Field(False, description="Accepts donations")
    
    # Contact
    email: Optional[str] = Field(None, description="Contact email")
    website: Optional[str] = Field(None, description="Website URL")
    phone: Optional[str] = Field(None, description="Phone number")
    
    # Members and staff
    members_count: Optional[int] = Field(None, description="Number of members")
    volunteers_count: Optional[int] = Field(None, description="Number of volunteers")
    employees_count: Optional[int] = Field(None, description="Number of employees")
    
    # Activities
    main_activity: Optional[str] = Field(None, description="Main activity")
    secondary_activities: List[str] = Field(default_factory=list, description="Secondary activities")


class SearchAssociationsInput(BaseModel):
    """Input parameters for association search."""
    query: str = Field(..., description="Search query")
    postal_code: Optional[str] = Field(None, description="Filter by postal code")
    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(20, ge=1, le=100, description="Results per page")
    force_refresh: bool = Field(False, description="Force refresh from API")


class SearchAssociationsOutput(BaseModel):
    """Output for association search."""
    total_results: int = Field(..., description="Total number of results")
    associations: List[Association] = Field(..., description="List of associations")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Results per page")
    total_pages: int = Field(..., description="Total number of pages")
    query: str = Field(..., description="Search query used")
    filters_applied: Dict[str, Any] = Field(..., description="Applied filters")
    metadata: Dict[str, Any] = Field(..., description="Search metadata")


# Keep legacy models for backward compatibility
class AssociationLegacy(BaseModel):
    """French association information (legacy format)."""
    id_association: str = Field(..., description="RNA identifier (W + numbers)")
    siret: Optional[str] = Field(None, description="SIRET if the association has one")
    titre: str = Field(..., description="Association name")
    objet: Optional[str] = Field(None, description="Association purpose/object")
    date_creation: Optional[date] = None
    date_declaration: Optional[date] = None
    date_publication: Optional[date] = None
    
    adresse_siege: Optional[Dict[str, str]] = Field(None, description="Headquarters address")
    
    regime: str = Field("Loi 1901", description="Legal regime")
    utilite_publique: bool = Field(False, description="Public utility status")
    agrement: List[str] = Field(default_factory=list, description="Official approvals")
    
    etat: str = Field("ACTIVE", description="Current state")
    
    # Contact information
    telephone: Optional[str] = None
    email: Optional[str] = None
    site_web: Optional[str] = None
    
    # Additional info
    nb_membres: Optional[int] = Field(None, description="Number of members")
    nb_salaries: Optional[int] = Field(None, description="Number of employees")
    
    source: List[str] = Field(default_factory=list)


class AssociationSearchResult(BaseModel):
    """Single association search result (legacy format)."""
    id_association: str
    siret: Optional[str] = None
    titre: str
    objet: Optional[str] = None
    date_creation: Optional[date] = None
    
    adresse: Optional[Dict[str, str]] = None
    
    regime: str = "Loi 1901"
    utilite_publique: bool = False
    etat: str = "ACTIVE"
    
    source: str = "rna"