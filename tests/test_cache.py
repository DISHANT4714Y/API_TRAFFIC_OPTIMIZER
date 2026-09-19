"""
Tests for Phase 5 — Basic In-Memory Cache.

Coverage:
  Unit tests (CacheManager directly):
    - Empty cache get
    - Set and get
    - exists() true / false
    - delete()
    - clear()
    - TTL expiration (patching time.time)
    - Expired entry counted as miss in statistics
    - Statistics: hit_ratio, reset_stats
    - Stats when no requests made (zero-division guard)

  Integration tests (via FastAPI TestClient):
    - Cache MISS on first proxy request → upstream called
    - Cache HIT on second identical proxy request → upstream NOT called
    - Failed upstream response (5xx) → not stored in cache
    - GET /cache/stats returns correct counts
    - POST /cache/clear flushes entries and returns count
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.cache.entry import CacheEntry
from app.cache.manager import CacheManager
from app import main as app_module
from app.main import app
from app.proxy.client import UpstreamError
from fastapi.testclient import TestClient

client = TestClient(app)


# ===========================================================================
# Helpers
# ===========================================================================

def fresh_cache(ttl: float = 30.0) -> CacheManager:
    """Return a new CacheManager with a predictable default TTL."""
    return CacheManager(default_ttl=ttl)


SAMPLE_KEY = "api-cache:v1:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
SAMPLE_VALUE = {"resource_id": "weather", "data": {"temperature": 30}}


# ===========================================================================
# CacheEntry unit tests
# ===========================================================================

class TestCacheEntry:
    def test_not_expired_when_future(self):
        """Entry with a far-future expiry is not expired."""
        import time
        entry = CacheEntry(value="data", expires_at=time.time() + 9999)
        assert not entry.is_expired()

    def test_expired_when_past(self):
        """Entry with a past expiry is expired."""
        entry = CacheEntry(value="data", expires_at=0.0)
        assert entry.is_expired()


# ===========================================================================
# CacheManager unit tests
# ===========================================================================

class TestCacheManagerGet:
    def test_empty_cache_get_returns_none(self):
        """get() on an empty cache returns None."""
        cache = fresh_cache()
        assert cache.get(SAMPLE_KEY) is None

    def test_empty_cache_counts_as_miss(self):
        """get() on an empty cache increments miss counter."""
        cache = fresh_cache()
        cache.get(SAMPLE_KEY)
        assert cache.misses == 1
        assert cache.hits == 0
        assert cache.total_requests == 1


class TestCacheManagerSetAndGet:
    def test_set_then_get_returns_value(self):
        """set() stores the value; get() retrieves it."""
        cache = fresh_cache()
        cache.set(SAMPLE_KEY, SAMPLE_VALUE)
        result = cache.get(SAMPLE_KEY)
        assert result == SAMPLE_VALUE

    def test_set_then_get_counts_as_hit(self):
        """A successful get() after set() increments hit counter."""
        cache = fresh_cache()
        cache.set(SAMPLE_KEY, SAMPLE_VALUE)
        cache.get(SAMPLE_KEY)
        assert cache.hits == 1
        assert cache.misses == 0
        assert cache.total_requests == 1


class TestCacheManagerExists:
    def test_exists_true_after_set(self):
        """exists() returns True for a key that has been set."""
        cache = fresh_cache()
        cache.set(SAMPLE_KEY, SAMPLE_VALUE)
        assert cache.exists(SAMPLE_KEY) is True

    def test_exists_false_for_missing_key(self):
        """exists() returns False for a key that was never set."""
        cache = fresh_cache()
        assert cache.exists(SAMPLE_KEY) is False

    def test_exists_does_not_count_as_hit_or_miss(self):
        """exists() is a read-only probe; it must not alter statistics."""
        cache = fresh_cache()
        cache.set(SAMPLE_KEY, SAMPLE_VALUE)
        cache.exists(SAMPLE_KEY)
        assert cache.total_requests == 0


class TestCacheManagerDelete:
    def test_delete_existing_key(self):
        """delete() removes an existing entry and returns True."""
        cache = fresh_cache()
        cache.set(SAMPLE_KEY, SAMPLE_VALUE)
        result = cache.delete(SAMPLE_KEY)
        assert result is True
        assert cache.get(SAMPLE_KEY) is None

    def test_delete_missing_key_returns_false(self):
        """delete() on a missing key returns False."""
        cache = fresh_cache()
        assert cache.delete(SAMPLE_KEY) is False


class TestCacheManagerClear:
    def test_clear_empties_all_entries(self):
        """clear() removes all stored entries."""
        cache = fresh_cache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_clear_returns_entry_count(self):
        """clear() returns the number of entries it removed."""
        cache = fresh_cache()
        cache.set("key1", "v1")
        cache.set("key2", "v2")
        cleared = cache.clear()
        assert cleared == 2

    def test_clear_on_empty_cache(self):
        """clear() on an already-empty cache returns 0."""
        cache = fresh_cache()
        assert cache.clear() == 0


class TestCacheManagerTTL:
    def test_get_returns_none_after_ttl_expires(self):
        """
        After the TTL window has elapsed, get() returns None.
        Uses patch to freeze time.time() at a point past expiry.
        """
        import time
        cache = fresh_cache(ttl=10.0)
        cache.set(SAMPLE_KEY, SAMPLE_VALUE)

        # Simulate 20 seconds have passed
        future_time = time.time() + 20.0
        with patch("app.cache.entry.time") as mock_time:
            mock_time.time.return_value = future_time
            result = cache.get(SAMPLE_KEY)

        assert result is None

    def test_expired_entry_counted_as_miss(self):
        """An expired entry increments the miss counter, not the hit counter."""
        import time
        cache = fresh_cache(ttl=10.0)
        cache.set(SAMPLE_KEY, SAMPLE_VALUE)

        future_time = time.time() + 20.0
        with patch("app.cache.entry.time") as mock_time:
            mock_time.time.return_value = future_time
            cache.get(SAMPLE_KEY)

        assert cache.misses == 1
        assert cache.hits == 0

    def test_expired_entry_deleted_from_store(self):
        """get() on an expired entry removes it from the internal store."""
        import time
        cache = fresh_cache(ttl=10.0)
        cache.set(SAMPLE_KEY, SAMPLE_VALUE)

        future_time = time.time() + 20.0
        with patch("app.cache.entry.time") as mock_time:
            mock_time.time.return_value = future_time
            cache.get(SAMPLE_KEY)

        # Internal store should be empty
        assert SAMPLE_KEY not in cache._store

    def test_exists_false_for_expired_entry(self):
        """exists() returns False and clears an expired entry."""
        import time
        cache = fresh_cache(ttl=10.0)
        cache.set(SAMPLE_KEY, SAMPLE_VALUE)

        future_time = time.time() + 20.0
        with patch("app.cache.entry.time") as mock_time:
            mock_time.time.return_value = future_time
            result = cache.exists(SAMPLE_KEY)

        assert result is False


class TestCacheManagerStats:
    def test_hit_ratio_zero_when_no_requests(self):
        """hit_ratio returns 0.0 when no get() calls have been made."""
        cache = fresh_cache()
        assert cache.hit_ratio == 0.0

    def test_hit_ratio_calculation(self):
        """hit_ratio = hits / total_requests."""
        cache = fresh_cache()
        cache.set(SAMPLE_KEY, SAMPLE_VALUE)
        cache.get(SAMPLE_KEY)   # HIT
        cache.get("missing")    # MISS
        assert cache.hit_ratio == 0.5

    def test_get_stats_dict_keys(self):
        """get_stats() returns a dict with the expected keys."""
        cache = fresh_cache()
        stats = cache.get_stats()
        assert "total_requests" in stats
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_ratio" in stats
        assert "current_entries" in stats

    def test_get_stats_current_entries(self):
        """current_entries in stats reflects the live store size."""
        cache = fresh_cache()
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        assert cache.get_stats()["current_entries"] == 2

    def test_reset_stats_zeroes_counters(self):
        """reset_stats() zeroes hit/miss/total without clearing entries."""
        cache = fresh_cache()
        cache.set(SAMPLE_KEY, SAMPLE_VALUE)
        cache.get(SAMPLE_KEY)   # HIT
        cache.get("missing")    # MISS
        cache.reset_stats()
        assert cache.total_requests == 0
        assert cache.hits == 0
        assert cache.misses == 0
        # Entry is still present
        assert cache.exists(SAMPLE_KEY)


# ===========================================================================
# Integration tests via TestClient (proxy endpoint + cache)
# ===========================================================================

class TestProxyCacheIntegration:
    def setup_method(self):
        """Clear cache and reset stats before each integration test."""
        app_module.cache_manager.clear()
        app_module.cache_manager.reset_stats()

    def test_first_request_is_cache_miss(self):
        """
        The first proxy request for a resource should be a CACHE MISS
        and call the upstream.
        """
        mock_payload = {
            "resource_id": "weather",
            "data": {"temperature": 28},
            "served_at": "2026-09-20T00:00:00Z",
            "request_id": "mock-000001",
        }
        with patch.object(
            app_module.proxy_client,
            "fetch_resource",
            new=AsyncMock(return_value=(200, mock_payload, {})),
        ) as mock_fetch:
            response = client.get("/proxy/data/weather")
            assert response.status_code == 200
            assert response.headers.get("x-cache") == "MISS"
            mock_fetch.assert_awaited_once()

    def test_second_request_is_cache_hit(self):
        """
        The second identical proxy request should be a CACHE HIT and
        must NOT call the upstream at all.
        """
        mock_payload = {
            "resource_id": "weather",
            "data": {"temperature": 28},
            "served_at": "2026-09-20T00:00:00Z",
            "request_id": "mock-000001",
        }
        with patch.object(
            app_module.proxy_client,
            "fetch_resource",
            new=AsyncMock(return_value=(200, mock_payload, {})),
        ) as mock_fetch:
            # First request — populates cache
            client.get("/proxy/data/weather-cache-hit-test")
            # Second request — should be served from cache
            response = client.get("/proxy/data/weather-cache-hit-test")

            assert response.status_code == 200
            assert response.headers.get("x-cache") == "HIT"
            assert response.json() == mock_payload
            # Upstream called exactly once, not twice
            assert mock_fetch.await_count == 1

    def test_failed_response_not_cached(self):
        """
        A 5xx error from upstream must NOT be stored in the cache.
        A subsequent request should still go to the upstream.
        """
        error = UpstreamError(
            status_code=500,
            detail={"detail": "Simulated failure"},
        )
        with patch.object(
            app_module.proxy_client,
            "fetch_resource",
            new=AsyncMock(side_effect=error),
        ) as mock_fetch:
            first = client.get("/proxy/data/fail-test")
            assert first.status_code == 500
            second = client.get("/proxy/data/fail-test")
            assert second.status_code == 500
            # Upstream must be called both times — error was not cached
            assert mock_fetch.await_count == 2

    def test_cache_stats_endpoint(self):
        """GET /cache/stats returns correct hit/miss counts."""
        mock_payload = {"resource_id": "stats-test", "data": {}, "served_at": "", "request_id": "x"}
        with patch.object(
            app_module.proxy_client,
            "fetch_resource",
            new=AsyncMock(return_value=(200, mock_payload, {})),
        ):
            client.get("/proxy/data/stats-test-resource")   # MISS
            client.get("/proxy/data/stats-test-resource")   # HIT

        stats_resp = client.get("/cache/stats")
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert stats["total_requests"] == 2
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_ratio"] == 0.5

    def test_cache_clear_endpoint(self):
        """POST /cache/clear flushes all entries and returns the count removed."""
        mock_payload = {"resource_id": "clear-test", "data": {}, "served_at": "", "request_id": "x"}
        with patch.object(
            app_module.proxy_client,
            "fetch_resource",
            new=AsyncMock(return_value=(200, mock_payload, {})),
        ):
            client.get("/proxy/data/clear-test-a")
            client.get("/proxy/data/clear-test-b")

        clear_resp = client.post("/cache/clear")
        assert clear_resp.status_code == 200
        body = clear_resp.json()
        assert body["status"] == "cleared"
        assert body["entries_removed"] == 2

        # Cache must now be empty
        stats = client.get("/cache/stats").json()
        assert stats["current_entries"] == 0
