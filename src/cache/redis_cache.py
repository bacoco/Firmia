"""Redis cache implementation for hot data."""

import json
from typing import Optional, Any, Union
from datetime import timedelta

import redis.asyncio as redis
from structlog import get_logger

from ..config import settings

logger = get_logger(__name__)


class RedisCache:
    """Redis cache for hot data with automatic serialization."""
    
    def __init__(self, url: str = None):
        self.url = url or settings.redis_url
        self._client: Optional[redis.Redis] = None
        self.logger = logger.bind(component="redis_cache")
    
    async def connect(self) -> None:
        """Connect to Redis."""
        if self._client is None:
            self.logger.info("connecting_to_redis", url=self.url)
            self._client = redis.from_url(
                self.url,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self._client.ping()
            self.logger.info("redis_connected")
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._client = None
            self.logger.info("redis_disconnected")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self._client:
            await self.connect()
        
        try:
            value = await self._client.get(key)
            if value is None:
                return None
            
            # Try to deserialize JSON
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                # Return as string if not JSON
                return value
                
        except redis.RedisError as e:
            self.logger.error("redis_get_error", key=key, error=str(e))
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """Set value in cache with optional TTL."""
        if not self._client:
            await self.connect()
        
        try:
            # Serialize to JSON if not string
            if isinstance(value, str):
                serialized = value
            else:
                serialized = json.dumps(value, default=str)
            
            # Convert timedelta to seconds
            if isinstance(ttl, timedelta):
                ttl = int(ttl.total_seconds())
            
            if ttl:
                await self._client.setex(key, ttl, serialized)
            else:
                await self._client.set(key, serialized)
            
            self.logger.debug("redis_set", key=key, ttl=ttl)
            return True
            
        except redis.RedisError as e:
            self.logger.error("redis_set_error", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self._client:
            await self.connect()
        
        try:
            result = await self._client.delete(key)
            self.logger.debug("redis_delete", key=key, deleted=bool(result))
            return bool(result)
            
        except redis.RedisError as e:
            self.logger.error("redis_delete_error", key=key, error=str(e))
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self._client:
            await self.connect()
        
        try:
            return bool(await self._client.exists(key))
            
        except redis.RedisError as e:
            self.logger.error("redis_exists_error", key=key, error=str(e))
            return False
    
    async def expire(self, key: str, ttl: Union[int, timedelta]) -> bool:
        """Set expiration on existing key."""
        if not self._client:
            await self.connect()
        
        try:
            if isinstance(ttl, timedelta):
                ttl = int(ttl.total_seconds())
            
            result = await self._client.expire(key, ttl)
            self.logger.debug("redis_expire", key=key, ttl=ttl, success=result)
            return result
            
        except redis.RedisError as e:
            self.logger.error("redis_expire_error", key=key, error=str(e))
            return False
    
    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment counter."""
        if not self._client:
            await self.connect()
        
        try:
            return await self._client.incr(key, amount)
            
        except redis.RedisError as e:
            self.logger.error("redis_incr_error", key=key, error=str(e))
            return None
    
    async def mget(self, keys: list[str]) -> list[Optional[Any]]:
        """Get multiple values at once."""
        if not self._client:
            await self.connect()
        
        try:
            values = await self._client.mget(keys)
            
            # Deserialize JSON values
            results = []
            for value in values:
                if value is None:
                    results.append(None)
                else:
                    try:
                        results.append(json.loads(value))
                    except json.JSONDecodeError:
                        results.append(value)
            
            return results
            
        except redis.RedisError as e:
            self.logger.error("redis_mget_error", keys=keys, error=str(e))
            return [None] * len(keys)
    
    async def mset(self, mapping: dict[str, Any]) -> bool:
        """Set multiple values at once."""
        if not self._client:
            await self.connect()
        
        try:
            # Serialize values
            serialized = {}
            for key, value in mapping.items():
                if isinstance(value, str):
                    serialized[key] = value
                else:
                    serialized[key] = json.dumps(value, default=str)
            
            await self._client.mset(serialized)
            self.logger.debug("redis_mset", count=len(mapping))
            return True
            
        except redis.RedisError as e:
            self.logger.error("redis_mset_error", error=str(e))
            return False
    
    async def flush_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        if not self._client:
            await self.connect()
        
        try:
            # Use SCAN to find matching keys
            count = 0
            async for key in self._client.scan_iter(match=pattern):
                await self._client.delete(key)
                count += 1
            
            self.logger.info("redis_flush_pattern", pattern=pattern, count=count)
            return count
            
        except redis.RedisError as e:
            self.logger.error("redis_flush_pattern_error", 
                            pattern=pattern, error=str(e))
            return 0
    
    async def get_ttl(self, key: str) -> Optional[int]:
        """Get remaining TTL for a key in seconds."""
        if not self._client:
            await self.connect()
        
        try:
            ttl = await self._client.ttl(key)
            # Redis returns -2 if key doesn't exist, -1 if no expiry
            return ttl if ttl >= 0 else None
            
        except redis.RedisError as e:
            self.logger.error("redis_ttl_error", key=key, error=str(e))
            return None