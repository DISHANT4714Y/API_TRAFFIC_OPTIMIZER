"""
Tests for Phase 7 — Metrics Collector.

Coverage:
  Unit tests (MetricsCollector directly):
    - All counters start at zero
    - record_request(hit=False) increments misses + total
    - record_request(hit=True) increments hits, requests_saved, total
    - record_mock_api_call() increments mock_api_calls
    - cache_hit_ratio computed correctly, 0.0 when no requests
    - avg_response_time_ms computed correctly, 0.0 when no requests
    - get_metrics() returns all required keys
    - reset() zeroes all counters

  Integration tests (via FastAPI TestClient):
    - GET /metrics endpoint returns 200 with correct keys
    - Proxy MISS → metrics reflect 0 hits, 1 miss, 1 mock_api_call
    - Proxy HIT  → metrics reflect 1 hit,  1 miss, 1 mock_api_call, 1 saved
    - POST /metrics/reset → all counters reset to 0
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app import main as app_module
from app.main import app
from app.metrics.collector import MetricsCollector
from app.proxy.client import UpstreamError

client = TestClient(app)

REQUIRED_METRIC_KEYS = {
    "total_requests",
    "cache_hits",
    "cache_misses",
    "cache_hit_ratio",
    "mock_api_calls",
    "requests_saved",
    "avg_response_time_ms",
}

MOCK_PAYLOAD = {
    "resource_id": "metrics-test",
    "data": {"value": 42},
    "served_at": "2026-10-09T00:00:00Z",
    "request_id": "mock-000001",
}


# ===========================================================================
# Unit tests — MetricsCollector
# ===========================================================================

class TestMetricsCollectorInit:
    def test_all_counters_start_at_zero(self):
        """All counters must be zero on a fresh MetricsCollector."""
        mc = MetricsCollector()
        assert mc.total_requests == 0
        assert mc.cache_hits == 0
        assert mc.cache_misses == 0
        assert mc.mock_api_calls == 0
        assert mc.requests_saved == 0
        assert mc._total_response_time_ms == 0.0

    def test_hit_ratio_zero_when_no_requests(self):
        mc = MetricsCollector()
        assert mc.cache_hit_ratio == 0.0

    def test_avg_response_time_zero_when_no_requests(self):
        mc = MetricsCollector()
        assert mc.avg_response_time_ms == 0.0


class TestMetricsCollectorRecordMiss:
    def test_miss_increments_total_and_misses(self):
        mc = MetricsCollector()
        mc.record_request(hit=False, response_time_ms=10.0)
        assert mc.total_requests == 1
        assert mc.cache_misses == 1
        assert mc.cache_hits == 0
        assert mc.requests_saved == 0

    def test_miss_does_not_increment_requests_saved(self):
        mc = MetricsCollector()
        mc.record_request(hit=False)
        assert mc.requests_saved == 0


class TestMetricsCollectorRecordHit:
    def test_hit_increments_total_hits_and_saved(self):
        mc = MetricsCollector()
        mc.record_request(hit=True, response_time_ms=2.0)
        assert mc.total_requests == 1
        assert mc.cache_hits == 1
        assert mc.requests_saved == 1
        assert mc.cache_misses == 0

    def test_hit_ratio_after_one_hit_one_miss(self):
        mc = MetricsCollector()
        mc.record_request(hit=False)
        mc.record_request(hit=True)
        assert mc.cache_hit_ratio == 0.5


class TestMetricsCollectorMockApiCall:
    def test_record_mock_api_call_increments_counter(self):
        mc = MetricsCollector()
        mc.record_mock_api_call()
        mc.record_mock_api_call()
        assert mc.mock_api_calls == 2


class TestMetricsCollectorAvgResponseTime:
    def test_avg_response_time_calculated_correctly(self):
        mc = MetricsCollector()
        mc.record_request(hit=False, response_time_ms=100.0)
        mc.record_request(hit=True, response_time_ms=10.0)
        # (100 + 10) / 2 = 55.0
        assert mc.avg_response_time_ms == 55.0


class TestMetricsCollectorGetMetrics:
    def test_get_metrics_returns_all_required_keys(self):
        mc = MetricsCollector()
        metrics = mc.get_metrics()
        assert REQUIRED_METRIC_KEYS == set(metrics.keys())

    def test_get_metrics_values_correct(self):
        mc = MetricsCollector()
        mc.record_request(hit=False, response_time_ms=50.0)
        mc.record_mock_api_call()
        metrics = mc.get_metrics()
        assert metrics["total_requests"] == 1
        assert metrics["cache_misses"] == 1
        assert metrics["cache_hits"] == 0
        assert metrics["cache_hit_ratio"] == 0.0
        assert metrics["mock_api_calls"] == 1
        assert metrics["requests_saved"] == 0
        assert metrics["avg_response_time_ms"] == 50.0


class TestMetricsCollectorReset:
    def test_reset_zeroes_all_counters(self):
        mc = MetricsCollector()
        mc.record_request(hit=True, response_time_ms=20.0)
        mc.record_mock_api_call()
        mc.reset()
        assert mc.total_requests == 0
        assert mc.cache_hits == 0
        assert mc.cache_misses == 0
        assert mc.mock_api_calls == 0
        assert mc.requests_saved == 0
        assert mc._total_response_time_ms == 0.0


# ===========================================================================
# Integration tests via TestClient
# ===========================================================================

class TestMetricsEndpoint:
    def setup_method(self):
        """Reset cache and metrics before each test."""
        app_module.cache_manager.clear()
        app_module.cache_manager.reset_stats()
        app_module.metrics_collector.reset()

    def test_get_metrics_endpoint_returns_200(self):
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_get_metrics_endpoint_returns_all_keys(self):
        resp = client.get("/metrics")
        assert REQUIRED_METRIC_KEYS == set(resp.json().keys())

    def test_metrics_after_cache_miss(self):
        """A single proxy MISS → 1 total, 0 hits, 1 miss, 1 mock_api_call."""
        with patch.object(
            app_module.proxy_client,
            "fetch_resource",
            new=AsyncMock(return_value=(200, MOCK_PAYLOAD, {})),
        ):
            client.get("/proxy/data/metrics-miss-test")

        metrics = client.get("/metrics").json()
        assert metrics["total_requests"] == 1
        assert metrics["cache_hits"] == 0
        assert metrics["cache_misses"] == 1
        assert metrics["mock_api_calls"] == 1
        assert metrics["requests_saved"] == 0
        assert metrics["cache_hit_ratio"] == 0.0

    def test_metrics_after_cache_hit(self):
        """MISS then HIT → 2 total, 1 hit, 1 miss, 1 mock_api_call, 1 saved."""
        with patch.object(
            app_module.proxy_client,
            "fetch_resource",
            new=AsyncMock(return_value=(200, MOCK_PAYLOAD, {})),
        ):
            client.get("/proxy/data/metrics-hit-test")  # MISS
            client.get("/proxy/data/metrics-hit-test")  # HIT

        metrics = client.get("/metrics").json()
        assert metrics["total_requests"] == 2
        assert metrics["cache_hits"] == 1
        assert metrics["cache_misses"] == 1
        assert metrics["mock_api_calls"] == 1
        assert metrics["requests_saved"] == 1
        assert metrics["cache_hit_ratio"] == 0.5

    def test_metrics_after_upstream_error_not_cached(self):
        """A 5xx error → 1 miss, 1 mock_api_call, not cached; second call → 2 misses."""
        error = UpstreamError(status_code=500, detail={"detail": "fail"})
        with patch.object(
            app_module.proxy_client,
            "fetch_resource",
            new=AsyncMock(side_effect=error),
        ):
            client.get("/proxy/data/metrics-error-test")
            client.get("/proxy/data/metrics-error-test")

        metrics = client.get("/metrics").json()
        assert metrics["total_requests"] == 2
        assert metrics["cache_hits"] == 0
        assert metrics["mock_api_calls"] == 2

    def test_metrics_reset_endpoint(self):
        """POST /metrics/reset → all counters back to zero."""
        with patch.object(
            app_module.proxy_client,
            "fetch_resource",
            new=AsyncMock(return_value=(200, MOCK_PAYLOAD, {})),
        ):
            client.get("/proxy/data/metrics-reset-test")

        reset_resp = client.post("/metrics/reset")
        assert reset_resp.status_code == 200
        assert reset_resp.json()["status"] == "reset"

        metrics = client.get("/metrics").json()
        assert metrics["total_requests"] == 0
        assert metrics["cache_hit_ratio"] == 0.0
