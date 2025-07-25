"""ETL pipeline for processing static datasets."""

import os
import hashlib
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path
from datetime import datetime
import asyncio
from urllib.parse import urlparse

import httpx
import aiofiles
from structlog import get_logger

from ..cache import get_cache_manager
from ..config import settings

logger = get_logger(__name__)


class DownloadProgress:
    """Track download progress."""
    
    def __init__(self, total_size: int):
        self.total_size = total_size
        self.downloaded = 0
        self.start_time = datetime.utcnow()
    
    def update(self, chunk_size: int) -> None:
        """Update progress."""
        self.downloaded += chunk_size
    
    @property
    def percentage(self) -> float:
        """Get download percentage."""
        if self.total_size == 0:
            return 0.0
        return (self.downloaded / self.total_size) * 100
    
    @property
    def speed_mbps(self) -> float:
        """Get download speed in MB/s."""
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        if elapsed == 0:
            return 0.0
        return (self.downloaded / (1024 * 1024)) / elapsed


class ParquetLoader:
    """Loads Parquet files into DuckDB."""
    
    def __init__(self, download_dir: str = "/tmp/firmia/downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger.bind(component="parquet_loader")
        self._http_client = httpx.AsyncClient(timeout=300.0)  # 5 min timeout
    
    async def download_file(
        self,
        url: str,
        filename: Optional[str] = None,
        force: bool = False,
        progress_callback: Optional[Callable[[DownloadProgress], None]] = None
    ) -> Path:
        """Download file from URL with progress tracking."""
        if not filename:
            # Generate filename from URL
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path) or "download.parquet"
        
        filepath = self.download_dir / filename
        
        # Check if file exists and is recent
        if not force and filepath.exists():
            # Check file age (skip if less than 24 hours old)
            file_age = datetime.utcnow() - datetime.fromtimestamp(filepath.stat().st_mtime)
            if file_age.total_seconds() < 86400:  # 24 hours
                self.logger.info("using_cached_file", 
                               file=str(filepath),
                               age_hours=file_age.total_seconds() / 3600)
                return filepath
        
        self.logger.info("downloading_file", url=url, filename=filename)
        
        try:
            # Get file size first
            response = await self._http_client.head(url)
            total_size = int(response.headers.get("content-length", 0))
            
            # Download with streaming
            progress = DownloadProgress(total_size)
            
            async with self._http_client.stream("GET", url) as response:
                response.raise_for_status()
                
                async with aiofiles.open(filepath, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        await f.write(chunk)
                        progress.update(len(chunk))
                        
                        if progress_callback:
                            progress_callback(progress)
                        
                        # Log progress every 10%
                        if int(progress.percentage) % 10 == 0:
                            self.logger.debug("download_progress",
                                            percentage=progress.percentage,
                                            speed_mbps=progress.speed_mbps)
            
            self.logger.info("download_complete", 
                           file=str(filepath),
                           size_mb=total_size / (1024 * 1024),
                           duration_seconds=(datetime.utcnow() - progress.start_time).total_seconds())
            
            return filepath
            
        except Exception as e:
            self.logger.error("download_failed", url=url, error=str(e))
            # Clean up partial download
            if filepath.exists():
                filepath.unlink()
            raise
    
    async def verify_file(self, filepath: Path, expected_hash: Optional[str] = None) -> bool:
        """Verify downloaded file integrity."""
        if not filepath.exists():
            return False
        
        if expected_hash:
            # Calculate file hash
            sha256_hash = hashlib.sha256()
            
            async with aiofiles.open(filepath, "rb") as f:
                while chunk := await f.read(8192):
                    sha256_hash.update(chunk)
            
            actual_hash = sha256_hash.hexdigest()
            
            if actual_hash != expected_hash:
                self.logger.error("hash_mismatch",
                                expected=expected_hash,
                                actual=actual_hash)
                return False
        
        return True
    
    async def load_to_duckdb(self, filepath: Path, table_name: str) -> int:
        """Load Parquet file into DuckDB."""
        cache_manager = get_cache_manager()
        
        try:
            # Load into DuckDB
            count = await cache_manager.load_static_data(str(filepath), table_name)
            
            self.logger.info("parquet_loaded_to_duckdb",
                           table=table_name,
                           records=count)
            
            return count
            
        except Exception as e:
            self.logger.error("duckdb_load_failed",
                            table=table_name,
                            error=str(e))
            raise
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self._http_client.aclose()


class ETLPipeline:
    """Orchestrates ETL operations for static datasets."""
    
    def __init__(self):
        self.loader = ParquetLoader()
        self.logger = logger.bind(component="etl_pipeline")
        self._running_jobs: Dict[str, asyncio.Task] = {}
    
    async def process_dataset(
        self,
        dataset_name: str,
        source_url: str,
        table_name: str,
        transform_func: Optional[Callable] = None,
        expected_hash: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a single dataset through ETL pipeline."""
        job_id = f"{dataset_name}_{datetime.utcnow().isoformat()}"
        
        self.logger.info("etl_job_started",
                       job_id=job_id,
                       dataset=dataset_name,
                       source=source_url)
        
        result = {
            "job_id": job_id,
            "dataset": dataset_name,
            "status": "failed",
            "records": 0,
            "error": None,
            "started_at": datetime.utcnow(),
            "completed_at": None
        }
        
        try:
            # Download file
            filepath = await self.loader.download_file(
                source_url,
                filename=f"{dataset_name}.parquet"
            )
            
            # Verify integrity if hash provided
            if expected_hash:
                if not await self.loader.verify_file(filepath, expected_hash):
                    raise ValueError("File integrity check failed")
            
            # Apply transformation if provided
            if transform_func:
                self.logger.info("applying_transformation", dataset=dataset_name)
                filepath = await transform_func(filepath)
            
            # Load to DuckDB
            record_count = await self.loader.load_to_duckdb(filepath, table_name)
            
            result.update({
                "status": "success",
                "records": record_count,
                "completed_at": datetime.utcnow()
            })
            
            self.logger.info("etl_job_completed",
                           job_id=job_id,
                           records=record_count,
                           duration=(result["completed_at"] - result["started_at"]).total_seconds())
            
        except Exception as e:
            result.update({
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.utcnow()
            })
            
            self.logger.error("etl_job_failed",
                            job_id=job_id,
                            error=str(e))
        
        return result
    
    async def process_multiple_datasets(
        self,
        datasets: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Process multiple datasets in parallel."""
        tasks = []
        
        for dataset in datasets:
            task = self.process_dataset(
                dataset_name=dataset["name"],
                source_url=dataset["url"],
                table_name=dataset["table"],
                transform_func=dataset.get("transform"),
                expected_hash=dataset.get("hash")
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append({
                    "dataset": datasets[i]["name"],
                    "status": "failed",
                    "error": str(result)
                })
            else:
                final_results.append(result)
        
        return final_results
    
    def is_job_running(self, dataset_name: str) -> bool:
        """Check if ETL job is currently running."""
        return dataset_name in self._running_jobs and not self._running_jobs[dataset_name].done()
    
    async def close(self) -> None:
        """Close resources."""
        await self.loader.close()


# Dataset configurations
DATASET_CONFIGS = [
    {
        "name": "sirene_stock",
        "url": "https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/",
        "table": "companies",
        "schedule": "0 3 1 * *",  # Monthly at 3 AM on 1st
        "format": "parquet"
    },
    {
        "name": "bodacc_annonces",
        "url": "https://bodacc-datadila.opendatasoft.com/api/v2/catalog/datasets/annonces-commerciales/exports/parquet",
        "table": "business_events",
        "schedule": "0 2 * * *",  # Daily at 2 AM
        "format": "parquet"
    },
    {
        "name": "decp_marches",
        "url": "https://data.economie.gouv.fr/api/datasets/1.0/decp_augmente/exports/parquet",
        "table": "public_contracts",
        "schedule": "0 4 * * 1",  # Weekly on Monday at 4 AM
        "format": "parquet"
    }
]