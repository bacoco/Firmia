"""Pydantic models for Firmia MCP Server."""

from .company import (
    Company,
    CompanySearchResult,
    SearchCompaniesInput,
    SearchCompaniesOutput,
    GetCompanyProfileInput,
    GetCompanyProfileOutput,
)
from .association import Association, AssociationSearchResult
from .document import Document, DownloadDocumentInput, DownloadDocumentOutput
from .events import BusinessEvent, GetBusinessEventsInput, GetBusinessEventsOutput

__all__ = [
    # Company models
    "Company",
    "CompanySearchResult",
    "SearchCompaniesInput",
    "SearchCompaniesOutput",
    "GetCompanyProfileInput",
    "GetCompanyProfileOutput",
    # Association models
    "Association",
    "AssociationSearchResult",
    # Document models
    "Document",
    "DownloadDocumentInput",
    "DownloadDocumentOutput",
    # Event models
    "BusinessEvent",
    "GetBusinessEventsInput",
    "GetBusinessEventsOutput",
]