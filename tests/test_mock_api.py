"""
Tests for the Mock External API (Phase 2).
"""

import time
from fastapi.testclient import TestClient
from mock_api.main import app

client = TestClient(app)


def test_mock_api_health():
    """Verify that the health check endpoint returns 200 and mock-api-ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "mock-api-ok"


def test_mock_api_resource_endpoint():
    """Verify resource endpoint returns 200 and expected schema/fields."""
    response = client.get("/api/data/weather-ahmedabad?delay_ms=0")
    assert response.status_code == 200
    data = response.json()
    assert data["resource_id"] == "weather-ahmedabad"
    assert "data" in data
    assert "temperature" in data["data"]
    assert "served_at" in data
    assert "request_id" in data
    assert data["request_id"].startswith("mock-")
    assert "X-Request-Id" in response.headers


def test_mock_api_request_counter():
    """Verify request counter increments on each resource request."""
    # Reset first
    reset_resp = client.post("/stats/reset")
    assert reset_resp.status_code == 200

    # Send 3 requests
    for i in range(3):
        res = client.get(f"/api/data/resource-{i}?delay_ms=0")
        assert res.status_code == 200

    # Check stats
    stats_resp = client.get("/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_requests"] == 3
    assert stats["uptime_seconds"] >= 0


def test_mock_api_reset_statistics():
    """Verify POST /stats/reset clears total_requests back to 0."""
    # Increment counter
    client.get("/api/data/item?delay_ms=0")

    # Reset
    reset_resp = client.post("/stats/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["total_requests"] == 0

    # Verify stats reflect 0
    stats_resp = client.get("/stats")
    assert stats_resp.status_code == 200
    assert stats_resp.json()["total_requests"] == 0


def test_mock_api_deterministic_failure():
    """Verify fail-test resource returns HTTP 500 internal server error."""
    response = client.get("/api/data/fail-test")
    assert response.status_code == 500
    assert response.json()["detail"] == "Simulated external API failure"


def test_mock_api_delay_override():
    """Verify artificial latency delay override is respected."""
    delay_ms = 80
    start = time.perf_counter()
    response = client.get(f"/api/data/timed-resource?delay_ms={delay_ms}")
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert response.status_code == 200
    assert response.headers["X-Mock-Delay-Ms"] == str(delay_ms)
    # Verify it waited at least close to the specified delay (allowing small scheduler margin)
    assert elapsed_ms >= 60
