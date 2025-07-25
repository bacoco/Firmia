"""Circuit breaker pattern implementation."""

import asyncio
from typing import Optional, Callable, Any, Type, Union, TypeVar, cast
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps

from structlog import get_logger

from ..config import settings

logger = get_logger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """Circuit breaker implementation to prevent cascading failures."""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception,
        half_open_max_calls: int = 3
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.half_open_max_calls = half_open_max_calls
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.success_count = 0
        self.half_open_calls = 0
        
        self._lock = asyncio.Lock()
        self.logger = logger.bind(circuit_breaker=name)
    
    async def call(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Execute function through circuit breaker."""
        async with self._lock:
            # Check if we should attempt recovery
            if self.state == CircuitState.OPEN:
                if self._should_attempt_recovery():
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    self.logger.info("circuit_entering_half_open")
                else:
                    self.logger.warning("circuit_open_rejecting_call")
                    raise Exception(f"Circuit breaker {self.name} is OPEN")
            
            # Check half-open limit
            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_calls >= self.half_open_max_calls:
                    # Decide based on success rate during half-open
                    if self.success_count > 0:
                        self._close_circuit()
                    else:
                        self._open_circuit()
                    
                    # Retry the check
                    return await self.call(func, *args, **kwargs)
                
                self.half_open_calls += 1
        
        # Execute the function
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except self.expected_exception as e:
            await self._on_failure(e)
            raise
        except Exception as e:
            # Unexpected exceptions don't trigger circuit breaker
            self.logger.warning("unexpected_exception", 
                              exception=type(e).__name__,
                              message=str(e))
            raise
    
    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if not self.last_failure_time:
            return True
        
        elapsed = datetime.utcnow() - self.last_failure_time
        return elapsed.total_seconds() >= self.recovery_timeout
    
    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                self.logger.debug("half_open_success", 
                                count=self.success_count,
                                total=self.half_open_calls)
            
            # Reset failure count on success in closed state
            if self.state == CircuitState.CLOSED:
                self.failure_count = 0
    
    async def _on_failure(self, exception: Exception) -> None:
        """Handle failed call."""
        async with self._lock:
            self.last_failure_time = datetime.utcnow()
            
            if self.state == CircuitState.CLOSED:
                self.failure_count += 1
                self.logger.warning("circuit_failure", 
                                  count=self.failure_count,
                                  threshold=self.failure_threshold,
                                  exception=str(exception))
                
                if self.failure_count >= self.failure_threshold:
                    self._open_circuit()
            
            elif self.state == CircuitState.HALF_OPEN:
                # Failure during recovery attempt
                self.logger.warning("half_open_failure")
                self._open_circuit()
    
    def _open_circuit(self) -> None:
        """Open the circuit breaker."""
        self.state = CircuitState.OPEN
        self.logger.error("circuit_opened", 
                        recovery_timeout=self.recovery_timeout)
    
    def _close_circuit(self) -> None:
        """Close the circuit breaker."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.logger.info("circuit_closed")
    
    def get_state(self) -> dict:
        """Get current circuit breaker state."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None
        }


# Global circuit breaker registry
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: Optional[int] = None,
    recovery_timeout: Optional[int] = None,
    expected_exception: Type[Exception] = Exception
) -> CircuitBreaker:
    """Get or create a circuit breaker instance."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold or settings.circuit_breaker_failure_threshold,
            recovery_timeout=recovery_timeout or settings.circuit_breaker_recovery_timeout,
            expected_exception=expected_exception
        )
    return _circuit_breakers[name]


def circuit_breaker(
    name: Optional[str] = None,
    failure_threshold: Optional[int] = None,
    recovery_timeout: Optional[int] = None,
    expected_exception: Type[Exception] = Exception
):
    """Decorator to apply circuit breaker to async functions."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        breaker_name = name or f"{func.__module__}.{func.__name__}"
        
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            breaker = get_circuit_breaker(
                breaker_name,
                failure_threshold,
                recovery_timeout,
                expected_exception
            )
            return cast(T, await breaker.call(func, *args, **kwargs))
        
        # Attach circuit breaker instance for inspection
        wrapper.circuit_breaker = get_circuit_breaker(breaker_name)  # type: ignore
        
        return wrapper
    
    return decorator


def get_all_circuit_states() -> dict[str, dict]:
    """Get state of all circuit breakers."""
    return {
        name: breaker.get_state() 
        for name, breaker in _circuit_breakers.items()
    }