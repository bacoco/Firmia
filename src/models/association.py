"""Association-related models for Firmia MCP Server."""

from typing import Optional, List, Dict, Any
from datetime import date
from pydantic import BaseModel, Field


class Association(BaseModel):
    """French association information."""
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
    """Single association search result."""
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