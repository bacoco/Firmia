"""DuckDB cache implementation for analytics and static data."""

import os
from typing import Optional, Any, List, Dict
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

import duckdb
from structlog import get_logger

from ..config import settings

logger = get_logger(__name__)


class DuckDBCache:
    """DuckDB cache for analytics and static data processing."""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.duckdb_path
        self._conn: Optional[duckdb.DuckDBPyConnection] = None
        self._executor = ThreadPoolExecutor(max_workers=1)  # Single thread for DuckDB
        self.logger = logger.bind(component="duckdb_cache")
    
    def _ensure_directory(self) -> None:
        """Ensure the database directory exists."""
        db_dir = Path(self.db_path).parent
        if not db_dir.exists():
            db_dir.mkdir(parents=True, exist_ok=True)
    
    def connect(self) -> None:
        """Connect to DuckDB (sync operation)."""
        if self._conn is None:
            self._ensure_directory()
            self.logger.info("connecting_to_duckdb", path=self.db_path)
            self._conn = duckdb.connect(self.db_path)
            self._initialize_schema()
            self.logger.info("duckdb_connected")
    
    def _initialize_schema(self) -> None:
        """Initialize database schema."""
        # Companies table for static data
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                siren VARCHAR PRIMARY KEY,
                denomination VARCHAR,
                sigle VARCHAR,
                naf_code VARCHAR,
                legal_form VARCHAR,
                employee_range VARCHAR,
                creation_date DATE,
                cessation_date DATE,
                last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Business events table
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS business_events (
                id VARCHAR PRIMARY KEY,
                siren VARCHAR,
                event_type VARCHAR,
                event_date DATE,
                publication_date DATE,
                details JSON,
                source VARCHAR,
                tribunal VARCHAR,
                announcement_number VARCHAR,
                FOREIGN KEY (siren) REFERENCES companies(siren)
            )
        """)
        
        # Public contracts table
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS public_contracts (
                id VARCHAR PRIMARY KEY,
                buyer_siren VARCHAR,
                supplier_siren VARCHAR,
                amount DECIMAL(15,2),
                signature_date DATE,
                object TEXT,
                cpv_codes VARCHAR[],
                last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Cache metadata table
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_metadata (
                table_name VARCHAR PRIMARY KEY,
                last_update TIMESTAMP,
                record_count INTEGER,
                source_url VARCHAR,
                etag VARCHAR,
                notes TEXT
            )
        """)
        
        self._conn.commit()
    
    async def execute(self, query: str, params: Optional[tuple] = None) -> Any:
        """Execute a query asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._execute_sync,
            query,
            params
        )
    
    def _execute_sync(self, query: str, params: Optional[tuple] = None) -> Any:
        """Execute a query synchronously."""
        if not self._conn:
            self.connect()
        
        try:
            if params:
                result = self._conn.execute(query, params)
            else:
                result = self._conn.execute(query)
            
            # For SELECT queries, fetch results
            if query.strip().upper().startswith("SELECT"):
                return result.fetchall()
            else:
                self._conn.commit()
                return result.rowcount
                
        except duckdb.Error as e:
            self.logger.error("duckdb_execute_error", query=query, error=str(e))
            raise
    
    async def load_parquet(self, file_path: str, table_name: str) -> int:
        """Load data from Parquet file into table."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self._load_parquet_sync,
            file_path,
            table_name
        )
    
    def _load_parquet_sync(self, file_path: str, table_name: str) -> int:
        """Load Parquet file synchronously."""
        if not self._conn:
            self.connect()
        
        try:
            self.logger.info("loading_parquet", file=file_path, table=table_name)
            
            # Create table from Parquet
            self._conn.execute(f"""
                CREATE OR REPLACE TABLE {table_name}_staging AS 
                SELECT * FROM parquet_scan('{file_path}')
            """)
            
            # Get row count
            count = self._conn.execute(
                f"SELECT COUNT(*) FROM {table_name}_staging"
            ).fetchone()[0]
            
            # Atomic table swap
            self._conn.execute("BEGIN")
            self._conn.execute(f"DROP TABLE IF EXISTS {table_name}_old")
            self._conn.execute(f"ALTER TABLE {table_name} RENAME TO {table_name}_old")
            self._conn.execute(f"ALTER TABLE {table_name}_staging RENAME TO {table_name}")
            self._conn.execute("COMMIT")
            
            # Update metadata
            self._conn.execute("""
                INSERT OR REPLACE INTO cache_metadata 
                (table_name, last_update, record_count, source_url)
                VALUES (?, CURRENT_TIMESTAMP, ?, ?)
            """, (table_name, count, file_path))
            
            self._conn.commit()
            
            self.logger.info("parquet_loaded", 
                           table=table_name, 
                           records=count)
            
            return count
            
        except Exception as e:
            self.logger.error("parquet_load_error", 
                            file=file_path, 
                            error=str(e))
            self._conn.rollback()
            raise
    
    async def search_companies(
        self, 
        query: str, 
        limit: int = 20, 
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Search companies in static data."""
        sql = """
            SELECT 
                siren,
                denomination,
                sigle,
                naf_code,
                legal_form,
                employee_range,
                creation_date,
                cessation_date
            FROM companies
            WHERE 
                denomination ILIKE ? OR
                siren = ? OR
                sigle ILIKE ?
            ORDER BY denomination
            LIMIT ? OFFSET ?
        """
        
        search_pattern = f"%{query}%"
        params = (search_pattern, query, search_pattern, limit, offset)
        
        results = await self.execute(sql, params)
        
        # Convert to dict format
        companies = []
        for row in results:
            companies.append({
                "siren": row[0],
                "denomination": row[1],
                "sigle": row[2],
                "naf_code": row[3],
                "legal_form": row[4],
                "employee_range": row[5],
                "creation_date": row[6],
                "cessation_date": row[7]
            })
        
        return companies
    
    async def get_company_events(
        self, 
        siren: str, 
        event_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get business events for a company."""
        if event_types:
            placeholders = ",".join(["?" for _ in event_types])
            sql = f"""
                SELECT * FROM business_events
                WHERE siren = ? AND event_type IN ({placeholders})
                ORDER BY event_date DESC
            """
            params = (siren, *event_types)
        else:
            sql = """
                SELECT * FROM business_events
                WHERE siren = ?
                ORDER BY event_date DESC
            """
            params = (siren,)
        
        results = await self.execute(sql, params)
        
        # Convert to dict format
        events = []
        for row in results:
            events.append({
                "id": row[0],
                "siren": row[1],
                "event_type": row[2],
                "event_date": row[3],
                "publication_date": row[4],
                "details": row[5],
                "source": row[6],
                "tribunal": row[7],
                "announcement_number": row[8]
            })
        
        return events
    
    async def create_health_score_view(self) -> None:
        """Create materialized view for company health scores."""
        sql = """
            CREATE OR REPLACE VIEW company_health_scores AS
            SELECT 
                c.siren,
                c.denomination,
                COUNT(DISTINCT pc.id) as public_contracts_count,
                SUM(pc.amount) as total_public_revenue,
                COUNT(DISTINCT be.id) as business_events_count,
                MAX(be.event_date) as last_event_date,
                CASE 
                    WHEN EXISTS(
                        SELECT 1 FROM business_events 
                        WHERE siren = c.siren 
                        AND event_type = 'procedure_collective' 
                        AND event_date > CURRENT_DATE - INTERVAL '2 years'
                    ) THEN 0
                    WHEN c.employee_range IN ('00', 'NN') THEN 0.3
                    ELSE 0.7 + (0.3 * LEAST(COUNT(DISTINCT pc.id) / 10.0, 1.0))
                END as health_score
            FROM companies c
            LEFT JOIN public_contracts pc 
                ON c.siren IN (pc.buyer_siren, pc.supplier_siren)
            LEFT JOIN business_events be 
                ON c.siren = be.siren
            GROUP BY c.siren, c.denomination, c.employee_range
        """
        
        await self.execute(sql)
    
    async def get_table_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all tables."""
        sql = """
            SELECT 
                table_name,
                last_update,
                record_count,
                source_url
            FROM cache_metadata
            ORDER BY table_name
        """
        
        results = await self.execute(sql)
        
        stats = {}
        for row in results:
            stats[row[0]] = {
                "last_update": row[1],
                "record_count": row[2],
                "source_url": row[3]
            }
        
        return stats
    
    def close(self) -> None:
        """Close DuckDB connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            self.logger.info("duckdb_closed")
    
    async def aclose(self) -> None:
        """Async close for compatibility."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, self.close)
        self._executor.shutdown(wait=True)