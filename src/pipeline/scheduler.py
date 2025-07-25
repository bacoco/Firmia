"""Pipeline scheduler for automated ETL runs."""

import asyncio
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from functools import lru_cache
from croniter import croniter

from structlog import get_logger

from .etl import ETLPipeline, DATASET_CONFIGS
from ..config import settings

logger = get_logger(__name__)


class ScheduledJob:
    """Represents a scheduled ETL job."""
    
    def __init__(
        self,
        name: str,
        cron_schedule: str,
        task_func: Callable,
        task_args: Dict[str, Any]
    ):
        self.name = name
        self.cron_schedule = cron_schedule
        self.task_func = task_func
        self.task_args = task_args
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.is_running = False
        self.last_result: Optional[Dict[str, Any]] = None
        self.logger = logger.bind(job=name)
        
        # Calculate next run time
        self._update_next_run()
    
    def _update_next_run(self) -> None:
        """Update next run time based on cron schedule."""
        cron = croniter(self.cron_schedule, datetime.utcnow())
        self.next_run = cron.get_next(datetime)
    
    async def run(self) -> Dict[str, Any]:
        """Execute the scheduled job."""
        if self.is_running:
            self.logger.warning("job_already_running")
            return {"status": "skipped", "reason": "already_running"}
        
        self.is_running = True
        self.last_run = datetime.utcnow()
        
        try:
            self.logger.info("job_started")
            result = await self.task_func(**self.task_args)
            self.last_result = result
            self.logger.info("job_completed", result=result)
            return result
            
        except Exception as e:
            self.logger.error("job_failed", error=str(e))
            self.last_result = {"status": "failed", "error": str(e)}
            raise
            
        finally:
            self.is_running = False
            self._update_next_run()
    
    def should_run_now(self) -> bool:
        """Check if job should run now."""
        if self.is_running:
            return False
        
        if not self.next_run:
            return False
        
        return datetime.utcnow() >= self.next_run
    
    def get_status(self) -> Dict[str, Any]:
        """Get job status information."""
        return {
            "name": self.name,
            "cron_schedule": self.cron_schedule,
            "is_running": self.is_running,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_result": self.last_result
        }


class PipelineScheduler:
    """Manages scheduled ETL pipeline runs."""
    
    def __init__(self):
        self.pipeline = ETLPipeline()
        self.jobs: Dict[str, ScheduledJob] = {}
        self._scheduler_task: Optional[asyncio.Task] = None
        self._running = False
        self.logger = logger.bind(component="pipeline_scheduler")
    
    def add_job(
        self,
        name: str,
        cron_schedule: str,
        dataset_config: Dict[str, Any]
    ) -> None:
        """Add a scheduled job."""
        job = ScheduledJob(
            name=name,
            cron_schedule=cron_schedule,
            task_func=self.pipeline.process_dataset,
            task_args={
                "dataset_name": dataset_config["name"],
                "source_url": dataset_config["url"],
                "table_name": dataset_config["table"],
                "transform_func": dataset_config.get("transform"),
                "expected_hash": dataset_config.get("hash")
            }
        )
        
        self.jobs[name] = job
        self.logger.info("job_added", name=name, schedule=cron_schedule)
    
    def initialize_default_jobs(self) -> None:
        """Initialize default dataset jobs from configuration."""
        for config in DATASET_CONFIGS:
            self.add_job(
                name=config["name"],
                cron_schedule=config["schedule"],
                dataset_config=config
            )
        
        self.logger.info("default_jobs_initialized", count=len(DATASET_CONFIGS))
    
    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            self.logger.warning("scheduler_already_running")
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        self.logger.info("scheduler_started")
    
    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        await self.pipeline.close()
        self.logger.info("scheduler_stopped")
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                # Check all jobs
                for job in self.jobs.values():
                    if job.should_run_now():
                        # Run job in background
                        asyncio.create_task(self._run_job(job))
                
                # Sleep for a minute before next check
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("scheduler_loop_error", error=str(e))
                await asyncio.sleep(60)  # Continue after error
    
    async def _run_job(self, job: ScheduledJob) -> None:
        """Run a single job."""
        try:
            await job.run()
        except Exception as e:
            self.logger.error("job_execution_failed", 
                            job=job.name, 
                            error=str(e))
    
    async def run_job_now(self, job_name: str) -> Dict[str, Any]:
        """Manually trigger a job to run now."""
        if job_name not in self.jobs:
            raise ValueError(f"Unknown job: {job_name}")
        
        job = self.jobs[job_name]
        return await job.run()
    
    def get_all_jobs_status(self) -> List[Dict[str, Any]]:
        """Get status of all scheduled jobs."""
        return [job.get_status() for job in self.jobs.values()]
    
    def get_job_status(self, job_name: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific job."""
        if job_name not in self.jobs:
            return None
        return self.jobs[job_name].get_status()
    
    async def force_update_all(self) -> List[Dict[str, Any]]:
        """Force update all datasets immediately."""
        results = []
        
        for job_name, job in self.jobs.items():
            self.logger.info("forcing_update", job=job_name)
            try:
                result = await job.run()
                results.append(result)
            except Exception as e:
                results.append({
                    "job": job_name,
                    "status": "failed",
                    "error": str(e)
                })
        
        return results


# Singleton instance
_pipeline_scheduler: Optional[PipelineScheduler] = None


@lru_cache(maxsize=1)
def get_pipeline_scheduler() -> PipelineScheduler:
    """Get the singleton PipelineScheduler instance."""
    global _pipeline_scheduler
    if _pipeline_scheduler is None:
        _pipeline_scheduler = PipelineScheduler()
        _pipeline_scheduler.initialize_default_jobs()
    return _pipeline_scheduler