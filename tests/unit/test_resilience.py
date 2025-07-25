"""Unit tests for resilience patterns."""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from src.resilience.circuit_breaker import CircuitBreaker, CircuitState, circuit_breaker
from src.resilience.retry import RetryConfig, retry_with_backoff, should_retry_exception


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    @pytest.fixture
    def breaker(self):
        """Create circuit breaker for testing."""
        return CircuitBreaker(
            name="test_breaker",
            failure_threshold=3,
            recovery_timeout=5,
            expected_exception=ValueError
        )
    
    @pytest.mark.asyncio
    async def test_circuit_closes_on_success(self, breaker):
        """Test circuit remains closed on successful calls."""
        async def success_func():
            return "success"
        
        result = await breaker.call(success_func)
        
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self, breaker):
        """Test circuit opens after failure threshold."""
        async def failing_func():
            raise ValueError("Test error")
        
        # First two failures
        for i in range(2):
            with pytest.raises(ValueError):
                await breaker.call(failing_func)
            assert breaker.state == CircuitState.CLOSED
            assert breaker.failure_count == i + 1
        
        # Third failure should open circuit
        with pytest.raises(ValueError):
            await breaker.call(failing_func)
        
        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 3
    
    @pytest.mark.asyncio
    async def test_circuit_rejects_when_open(self, breaker):
        """Test circuit rejects calls when open."""
        # Force circuit open
        breaker.state = CircuitState.OPEN
        breaker.last_failure_time = datetime.utcnow()
        
        async def test_func():
            return "should not execute"
        
        with pytest.raises(Exception) as exc_info:
            await breaker.call(test_func)
        
        assert "Circuit breaker test_breaker is OPEN" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_circuit_half_open_recovery(self, breaker):
        """Test circuit recovery through half-open state."""
        # Force circuit open with old failure time
        breaker.state = CircuitState.OPEN
        breaker.last_failure_time = datetime.utcnow() - timedelta(seconds=10)
        
        async def success_func():
            return "recovered"
        
        # Should enter half-open and succeed
        result = await breaker.call(success_func)
        assert result == "recovered"
        
        # After enough successes, should close
        breaker.success_count = breaker.half_open_max_calls
        breaker.half_open_calls = breaker.half_open_max_calls
        
        # Next call should close circuit
        result = await breaker.call(success_func)
        assert breaker.state == CircuitState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_decorator(self):
        """Test circuit breaker decorator."""
        call_count = 0
        
        @circuit_breaker(
            name="test_decorated",
            failure_threshold=2,
            expected_exception=RuntimeError
        )
        async def decorated_func(should_fail=False):
            nonlocal call_count
            call_count += 1
            if should_fail:
                raise RuntimeError("Decorated failure")
            return "success"
        
        # Successful call
        result = await decorated_func()
        assert result == "success"
        assert call_count == 1
        
        # Failures to open circuit
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await decorated_func(should_fail=True)
        
        # Circuit should be open
        with pytest.raises(Exception) as exc_info:
            await decorated_func()
        
        assert "Circuit breaker test_decorated is OPEN" in str(exc_info.value)


class TestRetry:
    """Test retry mechanism."""
    
    def test_should_retry_on_5xx_errors(self):
        """Test retry on server errors."""
        config = RetryConfig()
        
        # Mock HTTP exception with 500 status
        exception = MagicMock()
        exception.response.status_code = 500
        
        assert should_retry_exception(exception, config) is True
        
        # Should not retry on 404
        exception.response.status_code = 404
        assert should_retry_exception(exception, config) is False
    
    def test_should_retry_on_network_errors(self):
        """Test retry on network errors."""
        config = RetryConfig()
        
        # Should retry on timeout
        exception = asyncio.TimeoutError()
        assert should_retry_exception(exception, config) is True
        
        # Should retry on connection errors
        exception = ConnectionError()
        assert should_retry_exception(exception, config) is True
    
    @pytest.mark.asyncio
    async def test_retry_decorator(self):
        """Test retry decorator functionality."""
        call_count = 0
        
        @retry_with_backoff(
            config=RetryConfig(max_attempts=3, min_wait=0.1, max_wait=0.5)
        )
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                error = MagicMock()
                error.response.status_code = 500
                raise error
            return "success"
        
        # Should succeed after retries
        result = await flaky_func()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_gives_up_on_non_retryable(self):
        """Test retry gives up on non-retryable errors."""
        call_count = 0
        
        @retry_with_backoff(
            config=RetryConfig(max_attempts=3)
        )
        async def non_retryable_func():
            nonlocal call_count
            call_count += 1
            error = MagicMock()
            error.response.status_code = 404  # Non-retryable
            raise error
        
        # Should fail immediately without retries
        with pytest.raises(Exception):
            await non_retryable_func()
        
        assert call_count == 1  # No retries