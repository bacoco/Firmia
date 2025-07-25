"""Unit tests for caching layer."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.cache.redis_cache import RedisCache
from src.cache.manager import CacheManager


class TestRedisCache:
    """Test Redis cache functionality."""
    
    @pytest.fixture
    async def redis_cache(self):
        """Create Redis cache instance for testing."""
        cache = RedisCache("redis://localhost:6379/15")  # Use test DB
        cache._client = AsyncMock()
        return cache
    
    @pytest.mark.asyncio
    async def test_get_deserializes_json(self, redis_cache):
        """Test that get() deserializes JSON values."""
        redis_cache._client.get.return_value = '{"key": "value"}'
        
        result = await redis_cache.get("test_key")
        
        assert result == {"key": "value"}
        redis_cache._client.get.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_get_returns_string_if_not_json(self, redis_cache):
        """Test that get() returns string if not valid JSON."""
        redis_cache._client.get.return_value = "plain string"
        
        result = await redis_cache.get("test_key")
        
        assert result == "plain string"
    
    @pytest.mark.asyncio
    async def test_set_serializes_dict(self, redis_cache):
        """Test that set() serializes dict to JSON."""
        await redis_cache.set("test_key", {"data": "value"}, ttl=300)
        
        redis_cache._client.setex.assert_called_once_with(
            "test_key",
            300,
            '{"data": "value"}'
        )
    
    @pytest.mark.asyncio
    async def test_set_without_ttl(self, redis_cache):
        """Test set() without TTL."""
        await redis_cache.set("test_key", "value")
        
        redis_cache._client.set.assert_called_once_with("test_key", "value")
    
    @pytest.mark.asyncio
    async def test_flush_pattern(self, redis_cache):
        """Test flush_pattern deletes matching keys."""
        # Mock scan_iter to return test keys
        redis_cache._client.scan_iter = AsyncMock()
        redis_cache._client.scan_iter.return_value.__aiter__.return_value = [
            "search:123",
            "search:456"
        ]
        
        count = await redis_cache.flush_pattern("search:*")
        
        assert count == 2
        assert redis_cache._client.delete.call_count == 2


class TestCacheManager:
    """Test cache manager orchestration."""
    
    @pytest.fixture
    def cache_manager(self):
        """Create cache manager for testing."""
        manager = CacheManager()
        manager.redis = AsyncMock()
        manager.duckdb = AsyncMock()
        manager._initialized = True
        return manager
    
    @pytest.mark.asyncio
    async def test_search_result_caching(self, cache_manager):
        """Test search result cache operations."""
        search_params = {"query": "test", "page": 1}
        result = {"results": []}
        
        # Test cache miss
        cache_manager.redis.get.return_value = None
        cached = await cache_manager.get_search_result(search_params)
        assert cached is None
        
        # Test cache set
        await cache_manager.set_search_result(search_params, result, ttl=300)
        
        # Verify cache key generation is consistent
        cache_manager.redis.set.assert_called_once()
        call_args = cache_manager.redis.set.call_args
        assert call_args[0][1] == result
        assert call_args[0][2] == 300
    
    @pytest.mark.asyncio
    async def test_rate_limit_check(self, cache_manager):
        """Test rate limiting functionality."""
        # First request - should pass
        cache_manager.redis.get.return_value = None
        cache_manager.redis.set = AsyncMock()
        
        allowed, remaining = await cache_manager.check_rate_limit("test_api", "client1")
        
        assert allowed is True
        assert remaining == 1
        
        # Subsequent request with count
        cache_manager.redis.get.return_value = "50"
        cache_manager.redis.incr.return_value = 51
        
        allowed, remaining = await cache_manager.check_rate_limit("test_api", "client1")
        
        assert allowed is True
        # Default limit is 100, so 100 - 51 = 49
        assert remaining == 49
    
    @pytest.mark.asyncio
    async def test_company_cache_invalidation(self, cache_manager):
        """Test invalidating all cache for a company."""
        siren = "123456789"
        
        cache_manager.redis.delete.return_value = True
        cache_manager.redis.flush_pattern.return_value = 3
        
        count = await cache_manager.invalidate_company(siren)
        
        assert count == 4  # 1 profile + 3 documents
        cache_manager.redis.delete.assert_called_once_with(f"company:{siren}")
        cache_manager.redis.flush_pattern.assert_called_once_with(f"doc:{siren}:*")