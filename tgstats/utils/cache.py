"""Caching utilities for frequently accessed data."""

import json
import pickle
from typing import Any, Optional, Callable
from functools import wraps
import structlog

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from ..core.config import settings

logger = structlog.get_logger()


class CacheManager:
    """Async cache manager using Redis."""
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._enabled = settings.enable_cache and REDIS_AVAILABLE
        
        if self._enabled:
            try:
                self._redis = redis.from_url(
                    settings.redis_url,
                    encoding="utf-8",
                    decode_responses=False,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
            except Exception as e:
                logger.error("cache_init_failed", error=str(e))
                self._enabled = False
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self._enabled or not self._redis:
            return None
        
        try:
            value = await self._redis.get(key)
            if value:
                return pickle.loads(value)
        except Exception as e:
            logger.error("cache_get_failed", key=key, error=str(e))
        
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL."""
        if not self._enabled or not self._redis:
            return False
        
        try:
            ttl = ttl or settings.cache_ttl
            serialized = pickle.dumps(value)
            await self._redis.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error("cache_set_failed", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self._enabled or not self._redis:
            return False
        
        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.error("cache_delete_failed", key=key, error=str(e))
            return False
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        if not self._enabled or not self._redis:
            return 0
        
        try:
            keys = await self._redis.keys(pattern)
            if keys:
                return await self._redis.delete(*keys)
        except Exception as e:
            logger.error("cache_invalidate_failed", pattern=pattern, error=str(e))
        
        return 0
    
    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()


# Global cache instance
cache = CacheManager()


def cached(key_prefix: str, ttl: Optional[int] = None):
    """
    Decorator for caching function results.
    
    Usage:
        @cached("user_stats", ttl=300)
        async def get_user_stats(user_id: int):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key from function args
            cache_key = f"{key_prefix}:{':'.join(map(str, args))}"
            if kwargs:
                cache_key += f":{json.dumps(kwargs, sort_keys=True)}"
            
            # Try to get from cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logger.debug("cache_hit", key=cache_key)
                return cached_value
            
            # Call function
            result = await func(*args, **kwargs)
            
            # Store in cache
            await cache.set(cache_key, result, ttl=ttl)
            logger.debug("cache_miss", key=cache_key)
            
            return result
        
        return wrapper
    return decorator
