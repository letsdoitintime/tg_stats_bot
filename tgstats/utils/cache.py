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
        """Invalidate all keys matching pattern."""
        if not self._enabled or not self._redis:
            return 0
        
        try:
            keys = []
            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                await self._redis.delete(*keys)
                return len(keys)
            return 0
        except Exception as e:
            logger.error("cache_invalidate_pattern_failed", pattern=pattern, error=str(e))
            return 0
    
    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()


# Global cache manager instance
cache_manager = CacheManager()


def cached(key_prefix: str, ttl: Optional[int] = None):
    """
    Decorator for caching async function results.
    
    Args:
        key_prefix: Prefix for cache keys
        ttl: Time-to-live in seconds (uses default if not specified)
    
    Usage:
        @cached("user_stats", ttl=300)
        async def get_user_stats(user_id: int) -> dict:
            # Expensive operation
            return stats
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            import hashlib
            args_str = str(args) + str(sorted(kwargs.items()))
            args_hash = hashlib.md5(args_str.encode()).hexdigest()
            cache_key = f"{key_prefix}:{func.__name__}:{args_hash}"
            
            # Try to get from cache
            result = await cache_manager.get(cache_key)
            if result is not None:
                logger.debug("cache_hit", key=cache_key)
                return result
            
            # Cache miss - call function
            logger.debug("cache_miss", key=cache_key)
            result = await func(*args, **kwargs)
            
            # Store in cache
            await cache_manager.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


def cache_invalidate(key_prefix: str, *args, **kwargs):
    """
    Invalidate cache for specific function call.
    
    Args:
        key_prefix: Same prefix used in @cached decorator
        *args, **kwargs: Same arguments as cached function
    """
    import hashlib
    args_str = str(args) + str(sorted(kwargs.items()))
    args_hash = hashlib.md5(args_str.encode()).hexdigest()
    cache_key = f"{key_prefix}:*:{args_hash}"
    return cache_manager.invalidate_pattern(cache_key)
