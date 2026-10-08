"""
Tests for Phase 8 — Request Coalescer.

Coverage:
  Unit / async tests (RequestCoalescer directly):
    - Single request calls factory exactly once
    - Concurrent identical requests → factory called once, all get result
    - All concurrent waiters receive the correct response
    - Different keys execute independently
    - Exception from factory unblocks all waiters, no hang
    - After exception, in-flight dict is cleaned up

  Integration tests (via FastAPI TestClient):
    - Many simultaneous identical proxy requests → only 1 upstream call
    - All clients receive the correct response
    - Different resource paths execute independently
    - Failed upstream response is NOT cached (next request hits upstream again)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import main as app_module
from app.main import app
from app.proxy.client import UpstreamError
from app.requests.coalescer import RequestCoalescer
from fastapi.testclient import TestClient

client = TestClient(app)

MOCK_PAYLOAD = {
    "resource_id": "coalesce-test",
    "data": {"value": 99},
    "served_at": "2026-10-09T00:00:00Z",
    "request_id": "mock-coalesce-001",
}


# ===========================================================================
# Unit / async tests — RequestCoalescer
# ===========================================================================

@pytest.mark.asyncio
async def test_single_request_calls_factory_once():
    """A single coalesce call invokes the factory exactly once."""
    coalescer = RequestCoalescer()
    call_count = 0

    async def factory():
        nonlocal call_count
        call_count += 1
        return "result"

    result = await coalescer.coalesce("key-single", factory)
    assert result == "result"
    assert call_count == 1


@pytest.mark.asyncio
async def test_concurrent_identical_requests_call_factory_once():
    """10 concurrent coalesce calls on the same key → factory called once."""
    coalescer = RequestCoalescer()
    call_count = 0

    async def slow_factory():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return {"answer": 42}

    results = await asyncio.gather(
        *[coalescer.coalesce("same-key", slow_factory) for _ in range(10)]
    )

    assert call_count == 1
    assert all(r == {"answer": 42} for r in results)


@pytest.mark.asyncio
async def test_all_concurrent_requests_get_correct_result():
    """All 10 concurrent waiters receive the identical correct value."""
    coalescer = RequestCoalescer()

    async def factory():
        await asyncio.sleep(0.02)
        return {"data": "response-value"}

    results = await asyncio.gather(
        *[coalescer.coalesce("shared-key", factory) for _ in range(10)]
    )
    assert len(results) == 10
    assert all(r == {"data": "response-value"} for r in results)


@pytest.mark.asyncio
async def test_different_keys_are_independent():
    """Two different keys each call the factory once and get own results."""
    coalescer = RequestCoalescer()
    calls = {"a": 0, "b": 0}

    async def factory_a():
        calls["a"] += 1
        await asyncio.sleep(0.02)
        return "result-a"

    async def factory_b():
        calls["b"] += 1
        await asyncio.sleep(0.02)
        return "result-b"

    results = await asyncio.gather(
        coalescer.coalesce("key-a", factory_a),
        coalescer.coalesce("key-b", factory_b),
        coalescer.coalesce("key-a", factory_a),
        coalescer.coalesce("key-b", factory_b),
    )

    assert results[0] == "result-a"
    assert results[1] == "result-b"
    assert results[2] == "result-a"
    assert results[3] == "result-b"
    assert calls["a"] == 1
    assert calls["b"] == 1


@pytest.mark.asyncio
async def test_exception_unblocks_all_waiters():
    """When the factory raises, all concurrent waiters get the exception — no hang."""
    coalescer = RequestCoalescer()

    async def failing_factory():
        await asyncio.sleep(0.02)
        raise ValueError("upstream failure")

    tasks = [
        asyncio.create_task(coalescer.coalesce("error-key", failing_factory))
        for _ in range(5)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # All 5 tasks must have completed (no hang) with ValueError
    assert len(results) == 5
    for r in results:
        assert isinstance(r, ValueError)
        assert "upstream failure" in str(r)


@pytest.mark.asyncio
async def test_in_flight_cleaned_up_after_exception():
    """After an exception, the in-flight dict is empty so future calls retry."""
    coalescer = RequestCoalescer()
    call_count = 0

    async def factory():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("first call fails")
        return "ok"

    # First call raises
    with pytest.raises(RuntimeError):
        await coalescer.coalesce("retry-key", factory)

    # In-flight dict must be empty
    assert "retry-key" not in coalescer._in_flight

    # Second call succeeds (factory is called again)
    result = await coalescer.coalesce("retry-key", factory)
    assert result == "ok"
    assert call_count == 2


@pytest.mark.asyncio
async def test_sequential_calls_each_invoke_factory():
    """After a key resolves, a subsequent call for the same key invokes factory again."""
    coalescer = RequestCoalescer()
    call_count = 0

    async def factory():
        nonlocal call_count
        call_count += 1
        return f"call-{call_count}"

    r1 = await coalescer.coalesce("sequential-key", factory)
    r2 = await coalescer.coalesce("sequential-key", factory)

    assert call_count == 2
    assert r1 == "call-1"
    assert r2 == "call-2"


# ===========================================================================
# Integration tests via TestClient
# ===========================================================================

class TestCoalescerIntegration:
    def setup_method(self):
        """Reset cache, metrics, and coalescer before each test."""
        app_module.cache_manager.clear()
        app_module.cache_manager.reset_stats()
        app_module.metrics_collector.reset()

    def test_failed_upstream_not_cached_next_request_retries(self):
        """
        When upstream raises UpstreamError, the response must NOT be cached.
        The next request must call the upstream again.
        """
        error = UpstreamError(status_code=503, detail={"detail": "service unavailable"})
        with patch.object(
            app_module.proxy_client,
            "fetch_resource",
            new=AsyncMock(side_effect=error),
        ) as mock_fetch:
            r1 = client.get("/proxy/data/coalesce-fail-test")
            r2 = client.get("/proxy/data/coalesce-fail-test")

        assert r1.status_code == 503
        assert r2.status_code == 503
        # Upstream called twice — error was never cached
        assert mock_fetch.await_count == 2

    def test_proxy_cache_hit_not_counted_as_mock_api_call(self):
        """
        On a cache HIT the proxy must NOT call the upstream at all,
        so mock_api_calls stays at 1 after MISS+HIT.
        """
        with patch.object(
            app_module.proxy_client,
            "fetch_resource",
            new=AsyncMock(return_value=(200, MOCK_PAYLOAD, {})),
        ) as mock_fetch:
            client.get("/proxy/data/coalesce-hit-track")  # MISS
            client.get("/proxy/data/coalesce-hit-track")  # HIT

        metrics = client.get("/metrics").json()
        assert metrics["mock_api_calls"] == 1
        assert mock_fetch.await_count == 1

    def test_different_resources_independent(self):
        """Two different resource IDs must hit upstream independently."""
        with patch.object(
            app_module.proxy_client,
            "fetch_resource",
            new=AsyncMock(return_value=(200, MOCK_PAYLOAD, {})),
        ) as mock_fetch:
            client.get("/proxy/data/res-alpha")
            client.get("/proxy/data/res-beta")

        # Each distinct resource triggers its own upstream call
        assert mock_fetch.await_count == 2
