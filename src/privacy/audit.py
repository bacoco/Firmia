"""Audit logging for RGPD compliance and access tracking."""

import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import aiofiles
from pydantic import BaseModel
from structlog import get_logger

from ..config import settings

logger = get_logger(__name__)


class AuditEntry(BaseModel):
    """Single audit log entry."""
    id: str
    timestamp: datetime
    tool: str
    operation: str
    siren: Optional[str] = None
    doc_type: Optional[str] = None
    caller_id: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    response_time_ms: Optional[int] = None
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = {}
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AuditLogger:
    """Handles audit logging for RGPD compliance."""
    
    def __init__(self, log_dir: str = None):
        self.log_dir = Path(log_dir or "logs/audit")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger.bind(component="audit_logger")
        self._buffer: List[AuditEntry] = []
        self._buffer_size = 100
        self._flush_interval = 60  # seconds
        self._flush_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the audit logger with periodic flushing."""
        if self._flush_task is None:
            self._flush_task = asyncio.create_task(self._periodic_flush())
            self.logger.info("audit_logger_started")
    
    async def stop(self) -> None:
        """Stop the audit logger and flush remaining entries."""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None
        
        # Flush remaining entries
        if self._buffer:
            await self._flush_buffer()
        
        self.logger.info("audit_logger_stopped")
    
    async def log_access(
        self,
        tool: str,
        operation: str,
        caller_id: str,
        siren: Optional[str] = None,
        doc_type: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        response_time_ms: Optional[int] = None,
        status_code: Optional[int] = None,
        error_message: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ) -> None:
        """Log an access event."""
        entry = AuditEntry(
            id=self._generate_id(),
            timestamp=datetime.utcnow(),
            tool=tool,
            operation=operation,
            siren=siren,
            doc_type=doc_type,
            caller_id=caller_id,
            ip_address=ip_address,
            user_agent=user_agent,
            response_time_ms=response_time_ms,
            status_code=status_code,
            error_message=error_message,
            metadata=metadata or {}
        )
        
        # Add to buffer
        self._buffer.append(entry)
        
        # Log to structured logs as well
        self.logger.info(
            "audit_access",
            tool=tool,
            operation=operation,
            siren=siren,
            caller_id=caller_id,
            status_code=status_code
        )
        
        # Flush if buffer is full
        if len(self._buffer) >= self._buffer_size:
            await self._flush_buffer()
    
    async def log_document_download(
        self,
        siren: str,
        doc_type: str,
        year: Optional[int],
        caller_id: str,
        ip_address: Optional[str] = None,
        success: bool = True,
        file_size: Optional[int] = None
    ) -> None:
        """Log document download event."""
        await self.log_access(
            tool="download_official_document",
            operation="download",
            caller_id=caller_id,
            siren=siren,
            doc_type=doc_type,
            ip_address=ip_address,
            status_code=200 if success else 404,
            metadata={
                "year": year,
                "file_size": file_size,
                "success": success
            }
        )
    
    async def log_ficoba_access(
        self,
        siren: str,
        iban: Optional[str],
        caller_id: str,
        ip_address: Optional[str] = None,
        authorized: bool = True,
        found: bool = False
    ) -> None:
        """Log FICOBA (bank account) access - requires special tracking."""
        # Mask IBAN for privacy
        masked_iban = None
        if iban:
            masked_iban = f"{iban[:4]}****{iban[-4:]}" if len(iban) > 8 else "****"
        
        await self.log_access(
            tool="bank_account_verification",
            operation="verify",
            caller_id=caller_id,
            siren=siren,
            ip_address=ip_address,
            status_code=200 if authorized else 403,
            metadata={
                "iban_masked": masked_iban,
                "authorized": authorized,
                "found": found,
                "ficoba_access": True  # Flag for special handling
            }
        )
    
    async def search_audit_logs(
        self,
        siren: Optional[str] = None,
        caller_id: Optional[str] = None,
        tool: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditEntry]:
        """Search audit logs with filters."""
        # For production, this would query a database
        # For now, search in current buffer and recent files
        
        results = []
        
        # Search in buffer
        for entry in self._buffer:
            if self._matches_filters(entry, siren, caller_id, tool, start_date, end_date):
                results.append(entry)
        
        # Search in recent log files
        # (Implementation would read and parse recent log files)
        
        return results[:limit]
    
    def _matches_filters(
        self,
        entry: AuditEntry,
        siren: Optional[str],
        caller_id: Optional[str],
        tool: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> bool:
        """Check if entry matches search filters."""
        if siren and entry.siren != siren:
            return False
        if caller_id and entry.caller_id != caller_id:
            return False
        if tool and entry.tool != tool:
            return False
        if start_date and entry.timestamp < start_date:
            return False
        if end_date and entry.timestamp > end_date:
            return False
        return True
    
    async def generate_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate RGPD compliance report."""
        # This would aggregate audit logs for compliance reporting
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "total_accesses": 0,  # Would count from logs
            "unique_companies_accessed": 0,
            "document_downloads": 0,
            "ficoba_accesses": 0,
            "access_by_tool": {},
            "top_callers": [],
            "privacy_filtered_count": 0
        }
    
    def _generate_id(self) -> str:
        """Generate unique audit entry ID."""
        import uuid
        return str(uuid.uuid4())
    
    async def _flush_buffer(self) -> None:
        """Flush buffer to file."""
        if not self._buffer:
            return
        
        # Generate filename with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = self.log_dir / f"audit_{timestamp}.jsonl"
        
        try:
            # Write entries as JSON lines
            async with aiofiles.open(filename, "w") as f:
                for entry in self._buffer:
                    await f.write(entry.json() + "\n")
            
            self.logger.info("audit_buffer_flushed", 
                           count=len(self._buffer),
                           file=str(filename))
            
            # Clear buffer
            self._buffer.clear()
            
        except Exception as e:
            self.logger.error("audit_flush_failed", error=str(e))
    
    async def _periodic_flush(self) -> None:
        """Periodically flush buffer to disk."""
        while True:
            try:
                await asyncio.sleep(self._flush_interval)
                if self._buffer:
                    await self._flush_buffer()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("periodic_flush_error", error=str(e))


# Singleton instance
_audit_logger: Optional[AuditLogger] = None


@lru_cache(maxsize=1)
def get_audit_logger() -> AuditLogger:
    """Get the singleton AuditLogger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger