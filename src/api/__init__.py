"""API client implementations for Firmia MCP Server."""

from .base import BaseAPIClient, PaginatedAPIClient, APIError, RateLimitError, AuthenticationError
from .recherche_entreprises import RechercheEntreprisesAPI
from .insee_sirene import INSEESireneAPI
from .inpi_rne import INPIRNEAPI
from .api_entreprise import APIEntrepriseAPI

__all__ = [
    # Base classes
    "BaseAPIClient",
    "PaginatedAPIClient",
    "APIError",
    "RateLimitError", 
    "AuthenticationError",
    # API implementations
    "RechercheEntreprisesAPI",
    "INSEESireneAPI",
    "INPIRNEAPI",
    "APIEntrepriseAPI",
]