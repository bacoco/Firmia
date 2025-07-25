"""Retry mechanism with exponential backoff."""

import asyncio
import random
from typing import Optional, Callable, Any, Type, TypeVar, Set, cast
from functools import wraps

from pydantic import BaseModel
from structlog import get_logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_not_exception_type,
    RetryCallState
)

from ..config import settings

logger = get_logger(__name__)

T = TypeVar('T')


class RetryConfig(BaseModel):
    """Configuration for retry behavior."""
    max_attempts: int = 3
    min_wait: float = 1.0  # seconds
    max_wait: float = 30.0  # seconds
    multiplier: float = 2.0
    retry_on_status: Set[int] = {500, 502, 503, 504, 429}
    dont_retry_on_status: Set[int] = {400, 401, 403, 404}
    jitter: bool = True


def get_default_retry_config() -> RetryConfig:
    """Get default retry configuration from settings."""
    return RetryConfig(
        max_attempts=3,
        min_wait=1.0,
        max_wait=30.0,
        multiplier=2.0,
        retry_on_status={500, 502, 503, 504, 429},
        dont_retry_on_status={400, 401, 403, 404}
    )


def should_retry_exception(exception: Exception, config: RetryConfig) -> bool:
    """Determine if exception should trigger retry."""
    # Check HTTP status codes if available
    if hasattr(exception, 'response') and hasattr(exception.response, 'status_code'):
        status_code = exception.response.status_code
        
        # Don't retry on specific status codes
        if status_code in config.dont_retry_on_status:
            return False
        
        # Retry on specific status codes
        if status_code in config.retry_on_status:
            return True
    
    # Retry on network-related errors
    network_errors = (
        asyncio.TimeoutError,
        ConnectionError,
        ConnectionResetError,
        ConnectionAbortedError,
    )
    
    if isinstance(exception, network_errors):
        return True
    
    # Don't retry on other exceptions by default
    return False


def log_retry_attempt(retry_state: RetryCallState) -> None:
    """Log retry attempt details."""
    attempt = retry_state.attempt_number
    
    if retry_state.outcome and retry_state.outcome.failed:
        exception = retry_state.outcome.exception()
        logger.warning(
            "retry_attempt",
            attempt=attempt,
            exception=type(exception).__name__ if exception else None,
            message=str(exception) if exception else None,
            elapsed_time=retry_state.seconds_since_start
        )


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    logger_name: Optional[str] = None
):
    """Decorator to add retry with exponential backoff to async functions."""
    if config is None:
        config = get_default_retry_config()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Create custom retry condition
        def custom_retry(retry_state: RetryCallState) -> bool:
            if retry_state.outcome and retry_state.outcome.failed:
                exception = retry_state.outcome.exception()
                if exception:
                    return should_retry_exception(exception, config)
            return False
        
        # Apply tenacity retry decorator
        @retry(
            stop=stop_after_attempt(config.max_attempts),
            wait=wait_exponential(
                multiplier=config.multiplier,
                min=config.min_wait,
                max=config.max_wait
            ),
            retry=custom_retry,
            before_sleep=log_retry_attempt
        )
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def create_jittered_backoff(
    base_delay: float,
    max_delay: float = 30.0,
    jitter_range: float = 0.1
) -> float:
    """Create a jittered backoff delay."""
    # Add jitter to prevent thundering herd
    jitter = random.uniform(-jitter_range, jitter_range)
    delay = base_delay * (1 + jitter)
    
    # Cap at max delay
    return min(delay, max_delay)


class RetryManager:
    """Manages retry logic for multiple operations."""
    
    def __init__(self, default_config: Optional[RetryConfig] = None):
        self.default_config = default_config or get_default_retry_config()
        self.logger = logger.bind(component="retry_manager")
        self._operation_configs: dict[str, RetryConfig] = {}
    
    def set_operation_config(self, operation: str, config: RetryConfig) -> None:
        """Set custom retry config for specific operation."""
        self._operation_configs[operation] = config
    
    def get_operation_config(self, operation: str) -> RetryConfig:
        """Get retry config for operation."""
        return self._operation_configs.get(operation, self.default_config)
    
    async def execute_with_retry(
        self,
        operation: str,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """Execute function with retry logic."""
        config = self.get_operation_config(operation)
        
        @retry_with_backoff(config, operation)
        async def wrapped():
            return await func(*args, **kwargs)
        
        return await wrapped()


# Global retry manager instance
_retry_manager = RetryManager()


def get_retry_manager() -> RetryManager:
    """Get the global retry manager instance."""
    return _retry_manager