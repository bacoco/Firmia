"""Business event models for Firmia MCP Server."""

from typing import Optional, List, Dict, Any, Literal
from datetime import date, datetime
from pydantic import BaseModel, Field


class BusinessEvent(BaseModel):
    """Business event from BODACC or other sources."""
    id: str
    siren: str
    event_type: Literal[
        "creation", "modification", "radiation", 
        "procedure_collective", "vente", "depot_comptes"
    ]
    event_date: date
    publication_date: date
    
    # Source information
    source: Literal["BODACC_A", "BODACC_B", "BODACC_C", "RNE", "INSEE"]
    tribunal: Optional[str] = None
    announcement_number: Optional[str] = None
    
    # Event details (structure varies by type)
    details: Dict[str, Any] = Field(default_factory=dict)
    
    # Common fields
    denomination: Optional[str] = None
    forme_juridique: Optional[str] = None
    capital: Optional[Dict[str, Any]] = None
    
    # For procedure_collective
    type_procedure: Optional[str] = None
    jugement: Optional[str] = None
    
    # For modifications
    modifications: Optional[List[str]] = None
    
    # Full text of announcement
    texte_annonce: Optional[str] = None
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat()
        }


class GetBusinessEventsInput(BaseModel):
    """Input parameters for getting business events."""
    siren: str = Field(..., pattern="^[0-9]{9}$")
    event_types: Optional[List[Literal[
        "creation", "modification", "radiation",
        "procedure_collective", "vente", "depot_comptes"
    ]]] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    limit: int = Field(50, ge=1, le=100)


class TimelineSummary(BaseModel):
    """Summary of business events timeline."""
    first_event: Optional[date] = None
    last_event: Optional[date] = None
    total_events: int = 0
    events_by_type: Dict[str, int] = Field(default_factory=dict)
    
    # Key milestones
    creation_date: Optional[date] = None
    last_modification: Optional[date] = None
    has_procedures: bool = False
    last_accounts_filed: Optional[date] = None


class GetBusinessEventsOutput(BaseModel):
    """Output for business events query."""
    events: List[BusinessEvent]
    timeline_summary: TimelineSummary
    
    # Metadata
    siren: str
    sources_checked: List[str]
    query_date: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat()
        }