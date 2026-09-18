"""
Tests for Phase 3 — Basic API Proxy.
"""

from unittest.mock import AsyncMock, patch
import httpx
from fastapi.testclient import TestClient

from app import main as app_module
from app.main import app
from app.proxy.client import (
    ProxyClient,
    UpstreamError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)
from mock_api.main import app as mock_api_app

client = TestClient(app)


def test_proxy_success():
    """Test 1: Verify GET /proxy/data/{resource_id} successfully returns upstream data."""
    mock_payload = {
        "resource_id": "test",
        "data": {"temperature": 28, "condition": "sunny"},
        "served_at": "2026-09-19T00:00:00Z",
        "request_id": "mock-000001",
    }
    mock_headers = {"x-request-id": "mock-000001", "x-mock-delay-ms": "0"}

    with patch.object(
        app_module.proxy_client,
        "fetch_resource",
        new=AsyncMock(return_value=(200, mock_payload, mock_headers)),
    ):
        response = client.get("/proxy/data/test")
        assert response.status_code == 200
        assert response.json() == mock_payload
        assert response.headers.get("x-request-id") == "mock-000001"


def test_proxy_correct_upstream_request():
    """Test 2: Verify /proxy/data/test requests the correct resource from upstream."""
    mock_fetch = AsyncMock(return_value=(200, {"resource_id": "item-99"}, {}))

    with patch.object(app_module.proxy_client, "fetch_resource", new=mock_fetch):
        response = client.get("/proxy/data/item-99")
        assert response.status_code == 200
        mock_fetch.assert_awaited_once_with(resource_id="item-99", params=None)


def test_proxy_query_parameters():
    """Test 3: Verify query parameters are forwarded to upstream."""
    mock_fetch = AsyncMock(return_value=(200, {"resource_id": "weather"}, {}))

    with patch.object(app_module.proxy_client, "fetch_resource", new=mock_fetch):
        response = client.get("/proxy/data/weather?city=Ahmedabad&units=metric")
        assert response.status_code == 200
        mock_fetch.assert_awaited_once_with(
            resource_id="weather",
            params={"city": "Ahmedabad", "units": "metric"},
        )


def test_proxy_upstream_failure():
    """Test 4: Verify upstream error status code (e.g. 500) is returned cleanly."""
    error = UpstreamError(
        status_code=500,
        detail={"detail": "Simulated external API failure"},
    )

    with patch.object(
        app_module.proxy_client,
        "fetch_resource",
        new=AsyncMock(side_effect=error),
    ):
        response = client.get("/proxy/data/fail-test")
        assert response.status_code == 500
        assert response.json() == {"detail": "Simulated external API failure"}


def test_proxy_upstream_unavailable():
    """Test 5: Verify 502 Bad Gateway is returned when upstream is unreachable."""
    with patch.object(
        app_module.proxy_client,
        "fetch_resource",
        new=AsyncMock(side_effect=UpstreamUnavailableError("Upstream API unavailable")),
    ):
        response = client.get("/proxy/data/unreachable")
        assert response.status_code == 502
        assert response.json() == {"error": "Upstream API unavailable"}


def test_proxy_upstream_timeout():
    """Test 6: Verify 504 Gateway Timeout is returned when upstream times out."""
    with patch.object(
        app_module.proxy_client,
        "fetch_resource",
        new=AsyncMock(side_effect=UpstreamTimeoutError("Upstream API request timed out")),
    ):
        response = client.get("/proxy/data/slow")
        assert response.status_code == 504
        assert response.json() == {"error": "Upstream API timeout"}


def test_proxy_integration_full_flow():
    """Test 7: Integration test: Client -> Optimizer -> Mock API -> Optimizer -> Client."""
    # Connect ProxyClient directly to Mock API app via ASGITransport for in-memory integration
    transport = httpx.ASGITransport(app=mock_api_app)
    test_proxy_client = ProxyClient(
        base_url="http://testserver",
        timeout=5.0,
        transport=transport,
    )

    with patch.object(app_module, "proxy_client", test_proxy_client):
        # Reset Mock API stats
        mock_client = TestClient(mock_api_app)
        mock_client.post("/stats/reset")

        # Send request through Optimizer proxy
        resp = client.get("/proxy/data/integration-test?delay_ms=0")
        assert resp.status_code == 200
        payload = resp.json()

        assert payload["resource_id"] == "integration-test"
        assert payload["request_id"] == "mock-000001"
        assert "data" in payload

        # Check Mock API stats reflect exactly 1 request made
        stats_resp = mock_client.get("/stats")
        assert stats_resp.status_code == 200
        assert stats_resp.json()["total_requests"] == 1
