"""Cache manager orchestrating Redis and DuckDB caches."""

from typing import Optional, Any, Union, Dict, List
from datetime import timedelta
from functools import lru_cache
import hashlib
import json

from structlog import get_logger

from .redis_cache import RedisCache
from .duckdb_cache import DuckDBCache
from ..config import settings

logger = get_logger(__name__)


class CacheManager:
    """Manages both Redis (hot) and DuckDB (analytics) caches."""
    
    # Cache key prefixes
    SEARCH_PREFIX = "search:"
    COMPANY_PREFIX = "company:"
    DOCUMENT_PREFIX = "doc:"
    RATE_LIMIT_PREFIX = "rl:"
    
    def __init__(self):
        self.redis = RedisCache()
        self.duckdb = DuckDBCache()
        self.logger = logger.bind(component="cache_manager")
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize cache connections."""
        if self._initialized:
            return
        
        self.logger.info("initializing_caches")
        
        # Connect to Redis
        try:
            await self.redis.connect()
        except Exception as e:
            self.logger.error("redis_init_failed", error=str(e))
            if settings.is_production:
                raise
        
        # Connect to DuckDB (sync operation wrapped)
        try:
            self.duckdb.connect()
        except Exception as e:
            self.logger.error("duckdb_init_failed", error=str(e))
            if settings.is_production:
                raise
        
        self._initialized = True
        self.logger.info("caches_initialized")
    
    def _generate_cache_key(self, prefix: str, params: Any) -> str:
        """Generate consistent cache key from parameters."""
        # Convert params to stable string representation
        if isinstance(params, dict):
            # Sort dict keys for consistency
            stable_str = json.dumps(params, sort_keys=True, default=str)
        else:
            stable_str = str(params)
        
        # Generate hash for long keys
        hash_digest = hashlib.md5(stable_str.encode()).hexdigest()[:16]
        
        return f"{prefix}{hash_digest}"
    
    # Redis cache operations (hot data)
    
    async def get_search_result(self, search_params: Dict[str, Any]) -> Optional[Any]:
        """Get cached search results."""
        key = self._generate_cache_key(self.SEARCH_PREFIX, search_params)
        return await self.redis.get(key)
    
    async def set_search_result(
        self, 
        search_params: Dict[str, Any], 
        result: Any,
        ttl: int = None
    ) -> bool:
        """Cache search results."""
        key = self._generate_cache_key(self.SEARCH_PREFIX, search_params)
        ttl = ttl or settings.cache_ttl_search
        return await self.redis.set(key, result, ttl)
    
    async def get_company_profile(self, siren: str) -> Optional[Any]:
        """Get cached company profile."""
        key = f"{self.COMPANY_PREFIX}{siren}"
        return await self.redis.get(key)
    
    async def set_company_profile(
        self, 
        siren: str, 
        profile: Any,
        ttl: int = None
    ) -> bool:
        """Cache company profile."""
        key = f"{self.COMPANY_PREFIX}{siren}"
        ttl = ttl or settings.cache_ttl_company
        return await self.redis.set(key, profile, ttl)
    
    async def get_document_info(self, siren: str, doc_type: str, year: int) -> Optional[Any]:
        """Get cached document information."""
        key = f"{self.DOCUMENT_PREFIX}{siren}:{doc_type}:{year}"
        return await self.redis.get(key)
    
    async def set_document_info(
        self, 
        siren: str, 
        doc_type: str, 
        year: int,
        info: Any,
        ttl: int = None
    ) -> bool:
        """Cache document information."""
        key = f"{self.DOCUMENT_PREFIX}{siren}:{doc_type}:{year}"
        ttl = ttl or settings.cache_ttl_document
        return await self.redis.set(key, info, ttl)
    
    # Rate limiting operations
    
    async def check_rate_limit(
        self, 
        api: str, 
        client_id: str = "default"
    ) -> tuple[bool, int]:
        """Check if rate limit allows request."""
        key = f"{self.RATE_LIMIT_PREFIX}{api}:{client_id}"
        window = settings.rate_limit_window
        
        # Get API-specific limit
        limit = getattr(settings, f"rate_limit_{api}", 100)
        
        # Get current count
        current = await self.redis.get(key)
        if current is None:
            # First request in window
            await self.redis.set(key, 1, window)
            return True, 1
        
        current_count = int(current)
        if current_count >= limit:
            # Rate limit exceeded
            ttl = await self.redis.get_ttl(key)
            return False, ttl or window
        
        # Increment counter
        new_count = await self.redis.incr(key)
        return True, limit - new_count
    
    # Cache invalidation
    
    async def invalidate_company(self, siren: str) -> int:
        """Invalidate all cached data for a company."""
        count = 0
        
        # Delete company profile
        if await self.redis.delete(f"{self.COMPANY_PREFIX}{siren}"):
            count += 1
        
        # Delete related documents
        pattern = f"{self.DOCUMENT_PREFIX}{siren}:*"
        count += await self.redis.flush_pattern(pattern)
        
        self.logger.info("company_cache_invalidated", siren=siren, count=count)
        return count
    
    async def invalidate_search_cache(self) -> int:
        """Invalidate all search results cache."""
        pattern = f"{self.SEARCH_PREFIX}*"
        count = await self.redis.flush_pattern(pattern)
        self.logger.info("search_cache_invalidated", count=count)
        return count
    
    # DuckDB operations (analytics/static data)
    
    async def search_companies_static(
        self, 
        query: str, 
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Search companies in static DuckDB data."""
        return await self.duckdb.search_companies(query, limit, offset)
    
    async def get_company_events_static(
        self, 
        siren: str,
        event_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get company events from DuckDB."""
        return await self.duckdb.get_company_events(siren, event_types)
    
    async def load_static_data(
        self, 
        file_path: str, 
        table_name: str
    ) -> int:
        """Load static data from Parquet file."""
        count = await self.duckdb.load_parquet(file_path, table_name)
        
        # Invalidate related caches
        if table_name == "companies":
            await self.invalidate_search_cache()
        
        return count
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        # DuckDB table stats
        duckdb_stats = await self.duckdb.get_table_stats()
        
        # Redis info (would need to implement redis INFO parsing)
        redis_connected = await self.redis.exists("test")
        
        return {
            "redis": {
                "connected": redis_connected is not None,
                "ttls": {
                    "search": settings.cache_ttl_search,
                    "company": settings.cache_ttl_company,
                    "document": settings.cache_ttl_document
                }
            },
            "duckdb": {
                "tables": duckdb_stats
            }
        }
    
    async def close(self) -> None:
        """Close all cache connections."""
        self.logger.info("closing_caches")
        
        await self.redis.disconnect()
        await self.duckdb.aclose()
        
        self._initialized = False


# Singleton instance
_cache_manager: Optional[CacheManager] = None


@lru_cache(maxsize=1)
def get_cache_manager() -> CacheManager:
    """Get the singleton CacheManager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager