"""Tests for caching utilities."""

import pytest

from tgstats.utils.cache import CacheManager, cache_manager, cached


@pytest.fixture(autouse=True)
async def isolate_cache():
    """Give each test a cache client bound to its own event loop, and no keys.

    `cache_manager` is a module-level singleton (cache.py:113) holding a Redis
    client bound to whichever event loop first created it. pytest-asyncio runs
    each test on a fresh loop, so from the second test onwards every call failed
    with "Event loop is closed" — and the keys an earlier test wrote survived
    into the next one, turning an expected cache MISS into a HIT so the
    decorator's wrapped function never ran (call_count stayed 0).

    Re-running __init__ rebinds the client to the current loop; clearing the
    keys these tests use removes the cross-test leak. Both are needed: the
    rebind alone still leaves stale keys in a live Redis.
    """
    CacheManager.__init__(cache_manager)
    await _clear_test_keys()
    yield
    await _clear_test_keys()
    await cache_manager.close()


async def _clear_test_keys():
    await cache_manager.invalidate_pattern("test_func:*")
    await cache_manager.delete("test_key")


@pytest.mark.asyncio
class TestCaching:
    """Test caching functionality."""

    async def test_cached_decorator_caches_result(self):
        """Test that @cached decorator caches function results."""
        call_count = 0

        @cached("test_func", ttl=60)
        async def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call - should execute
        result1 = await expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call - should use cache
        result2 = await expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Not incremented

    async def test_cached_decorator_different_args(self):
        """Test that cache is keyed by arguments."""
        call_count = 0

        @cached("test_func", ttl=60)
        async def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # Different arguments should cache separately
        result1 = await expensive_function(5)
        result2 = await expensive_function(10)

        assert result1 == 10
        assert result2 == 20
        assert call_count == 2

    async def test_cache_manager_set_get(self):
        """Test basic cache set/get operations."""
        # Mock Redis if not available
        if not cache_manager._enabled:
            pytest.skip("Cache not enabled")

        key = "test_key"
        value = {"data": "test"}

        success = await cache_manager.set(key, value, ttl=60)
        assert success is True

        retrieved = await cache_manager.get(key)
        assert retrieved == value

    async def test_cache_manager_delete(self):
        """Test cache deletion."""
        if not cache_manager._enabled:
            pytest.skip("Cache not enabled")

        key = "test_key"
        value = "test_value"

        await cache_manager.set(key, value)
        success = await cache_manager.delete(key)

        assert success is True

        result = await cache_manager.get(key)
        assert result is None
