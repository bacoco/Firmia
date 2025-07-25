"""Integration tests for document download functionality."""

import pytest
import asyncio
import base64
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from src.tools.download_document import DownloadDocumentTool, ListDocumentsTool


@pytest.fixture
def download_tool():
    """Create download tool instance."""
    return DownloadDocumentTool()


@pytest.fixture
def list_tool():
    """Create list documents tool instance."""
    return ListDocumentsTool()


@pytest.fixture
def mock_document_data():
    """Mock document data."""
    return {
        "kbis_pdf": b"Mock KBIS PDF content",
        "bilan_pdf": b"Mock Bilan PDF content",
        "api_entreprise_docs": [
            {
                "type": "kbis",
                "id": "kbis_123456789",
                "name": "Extrait KBIS",
                "available": True
            },
            {
                "type": "bilan",
                "id": "bilan_123456789_2023",
                "name": "Bilan 2023",
                "year": 2023,
                "available": True
            },
            {
                "type": "attestation_fiscale",
                "id": "attest_fisc_123456789",
                "name": "Attestation fiscale",
                "available": True
            }
        ],
        "inpi_docs": [
            {
                "id": "acte_001",
                "type": "acte",
                "name": "Procès-verbal d'assemblée",
                "date_depot": datetime(2024, 1, 15),
                "url": "https://inpi.fr/docs/acte_001.pdf",
                "filename": "pv_assemblee_2024.pdf"
            },
            {
                "id": "statuts_001",
                "type": "statuts",
                "name": "Statuts constitutifs",
                "date_depot": datetime(2010, 1, 15),
                "url": "https://inpi.fr/docs/statuts_001.pdf",
                "filename": "statuts_2010.pdf"
            }
        ]
    }


@pytest.mark.asyncio
async def test_download_kbis_pdf(download_tool, mock_document_data):
    """Test downloading KBIS as PDF."""
    with patch.object(download_tool.service.api_entreprise, 'download_document') as mock_download:
        mock_download.return_value = {
            "content": mock_document_data["kbis_pdf"],
            "mime_type": "application/pdf",
            "filename": "kbis_123456789.pdf"
        }
        
        result = await download_tool.run(
            siren="123456789",
            document_type="kbis",
            format="pdf"
        )
        
        assert result["document_type"] == "kbis"
        assert result["siren"] == "123456789"
        assert result["source"] == "api_entreprise"
        assert result["content"] == base64.b64encode(mock_document_data["kbis_pdf"]).decode()
        assert result["content_type"] == "application/pdf"
        assert result["size"] == len(mock_document_data["kbis_pdf"])


@pytest.mark.asyncio
async def test_download_kbis_url(download_tool):
    """Test getting KBIS download URL."""
    with patch.object(download_tool.service.api_entreprise, 'get_document_url') as mock_url:
        mock_url.return_value = {
            "url": "https://api.entreprise.fr/temp/kbis_123456789.pdf",
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat()
        }
        
        result = await download_tool.run(
            siren="123456789",
            document_type="kbis",
            format="url"
        )
        
        assert result["document_type"] == "kbis"
        assert result["url"] == "https://api.entreprise.fr/temp/kbis_123456789.pdf"
        assert result["expires_at"] is not None
        assert result["content"] is None  # No content for URL format


@pytest.mark.asyncio
async def test_download_bilan_with_year(download_tool, mock_document_data):
    """Test downloading bilan for specific year."""
    with patch.object(download_tool.service.api_entreprise, 'download_document') as mock_download:
        mock_download.return_value = {
            "content": mock_document_data["bilan_pdf"],
            "mime_type": "application/pdf",
            "filename": "bilan_123456789_2023.pdf"
        }
        
        result = await download_tool.run(
            siren="123456789",
            document_type="bilan",
            year=2023,
            format="pdf"
        )
        
        assert result["document_type"] == "bilan"
        assert result["year"] == 2023
        assert result["filename"] == "bilan_123456789_2023_20" in result["filename"]


@pytest.mark.asyncio
async def test_download_inpi_document(download_tool, mock_document_data):
    """Test downloading document from INPI."""
    with patch.object(download_tool.service.inpi_api, 'get_company_documents') as mock_list:
        with patch.object(download_tool.service.inpi_api, 'download_from_url') as mock_download:
            mock_list.return_value = mock_document_data["inpi_docs"]
            mock_download.return_value = b"Mock INPI document content"
            
            result = await download_tool.run(
                siren="123456789",
                document_type="acte",
                format="pdf"
            )
            
            assert result["document_type"] == "acte"
            assert result["source"] == "inpi"
            assert result["content"] is not None


@pytest.mark.asyncio
async def test_download_cache_hit(download_tool):
    """Test document cache hit."""
    cached_doc = {
        "content": base64.b64encode(b"Cached document").decode(),
        "filename": "cached_doc.pdf",
        "content_type": "application/pdf",
        "size": 14,
        "document_type": "kbis",
        "siren": "123456789",
        "source": "cache"
    }
    
    with patch.object(download_tool.service.cache_manager, 'get_document') as mock_cache:
        mock_cache.return_value = cached_doc
        
        result = await download_tool.run(
            siren="123456789",
            document_type="kbis",
            format="pdf"
        )
        
        assert result["source"] == "cache"
        assert result["content"] == cached_doc["content"]


@pytest.mark.asyncio
async def test_download_error_handling(download_tool):
    """Test error handling in document download."""
    with patch.object(download_tool.service.api_entreprise, 'download_document') as mock_download:
        mock_download.side_effect = Exception("API Error")
        
        with pytest.raises(Exception) as exc_info:
            await download_tool.run(
                siren="123456789",
                document_type="kbis",
                format="pdf"
            )
        
        assert "API Error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_list_all_documents(list_tool, mock_document_data):
    """Test listing all available documents."""
    with patch.object(list_tool.service.api_entreprise, 'list_available_documents') as mock_api_list:
        with patch.object(list_tool.service.inpi_api, 'get_company_documents') as mock_inpi_list:
            mock_api_list.return_value = mock_document_data["api_entreprise_docs"]
            mock_inpi_list.return_value = mock_document_data["inpi_docs"]
            
            result = await list_tool.run(siren="123456789")
            
            assert result["siren"] == "123456789"
            assert result["total_count"] >= 5  # 3 from API Entreprise + 2 from INPI
            
            # Check document types
            doc_types = [doc["type"] for doc in result["documents"]]
            assert "kbis" in doc_types
            assert "bilan" in doc_types
            assert "attestation_fiscale" in doc_types
            assert "acte" in doc_types
            assert "statuts" in doc_types


@pytest.mark.asyncio
async def test_download_rate_limiting(download_tool):
    """Test rate limiting for document downloads."""
    with patch.object(download_tool.service.cache_manager, 'check_rate_limit') as mock_rate:
        mock_rate.return_value = (False, 60)  # Rate limited, retry after 60s
        
        with pytest.raises(Exception) as exc_info:
            await download_tool.run(
                siren="123456789",
                document_type="kbis",
                format="pdf"
            )
        
        assert "rate limit" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_download_audit_logging(download_tool, mock_document_data):
    """Test audit logging for document access."""
    with patch.object(download_tool.service.api_entreprise, 'download_document') as mock_download:
        with patch.object(download_tool.service.audit_logger, 'log_access') as mock_audit:
            mock_download.return_value = {
                "content": mock_document_data["kbis_pdf"],
                "mime_type": "application/pdf",
                "filename": "kbis_123456789.pdf"
            }
            
            await download_tool.run(
                siren="123456789",
                document_type="kbis",
                format="pdf"
            )
            
            # Check audit was logged
            mock_audit.assert_called_once()
            audit_call = mock_audit.call_args[1]
            assert audit_call["tool"] == "download_document"
            assert audit_call["operation"] == "download"
            assert audit_call["siren"] == "123456789"
            assert audit_call["metadata"]["document_type"] == "kbis"


@pytest.mark.asyncio
async def test_inpi_document_selection(download_tool, mock_document_data):
    """Test selecting correct document from INPI list."""
    # Test with year selection
    with patch.object(download_tool.service.inpi_api, 'get_company_documents') as mock_list:
        with patch.object(download_tool.service.inpi_api, 'download_from_url') as mock_download:
            # Add multiple documents of same type with different dates
            docs = [
                {
                    "id": "acte_old",
                    "type": "acte",
                    "name": "Old PV",
                    "date_depot": datetime(2022, 1, 1),
                    "url": "https://inpi.fr/old.pdf"
                },
                {
                    "id": "acte_new",
                    "type": "acte",
                    "name": "New PV",
                    "date_depot": datetime(2024, 1, 1),
                    "url": "https://inpi.fr/new.pdf"
                }
            ]
            mock_list.return_value = docs
            mock_download.return_value = b"Document content"
            
            # Without year - should get most recent
            result = await download_tool.run(
                siren="123456789",
                document_type="acte",
                format="pdf"
            )
            
            # Verify it selected the newer document
            mock_download.assert_called_with("https://inpi.fr/new.pdf")