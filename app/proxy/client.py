"""
Responsible for communicating with the external/mock API asynchronously.
"""

import os
from typing import Any, Dict, Optional, Tuple
import httpx
from dotenv import load_dotenv

# Load environment configuration
load_dotenv()

# Upstream mock API base URL (default: http://127.0.0.1:8001)
MOCK_API_URL: str = os.getenv("MOCK_API_URL", "http://127.0.0.1:8001").rstrip("/")

# Timeout for upstream requests in seconds (default: 5.0s)
UPSTREAM_TIMEOUT_SECONDS: float = float(os.getenv("UPSTREAM_TIMEOUT_SECONDS", "5.0"))


class UpstreamError(Exception):
    """Raised when the upstream service returns an HTTP error status code (4xx, 5xx)."""

    def __init__(
        self,
        status_code: int,
        detail: Any,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.headers = headers or {}
        super().__init__(f"Upstream error {status_code}: {detail}")


class UpstreamUnavailableError(Exception):
    """Raised when the upstream service is unreachable or network connection fails."""
    pass


class UpstreamTimeoutError(Exception):
    """Raised when the upstream request exceeds the configured timeout duration."""
    pass


class ProxyClient:
    """HTTP client responsible for asynchronous communication with upstream APIs."""

    def __init__(
        self,
        base_url: str = MOCK_API_URL,
        timeout: float = UPSTREAM_TIMEOUT_SECONDS,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    async def fetch_resource(
        self,
        resource_id: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
        """
        Forwards a resource request to the upstream API.

        Args:
            resource_id: Identifier of the target resource.
            params: Optional query parameters to append.

        Returns:
            Tuple of (status_code, json_payload, response_headers).

        Raises:
            UpstreamTimeoutError: If the upstream call times out.
            UpstreamUnavailableError: If connection to upstream fails.
            UpstreamError: If upstream returns an HTTP error status.
        """
        target_url = f"{self.base_url}/api/data/{resource_id}"

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = await client.get(target_url, params=params)

                if response.is_error:
                    try:
                        error_detail = response.json()
                    except Exception:
                        error_detail = {"detail": response.text}
                    raise UpstreamError(
                        status_code=response.status_code,
                        detail=error_detail,
                        headers=dict(response.headers),
                    )

                return (
                    response.status_code,
                    response.json(),
                    dict(response.headers),
                )

        except httpx.TimeoutException as exc:
            raise UpstreamTimeoutError("Upstream API request timed out") from exc
        except httpx.RequestError as exc:
            raise UpstreamUnavailableError("Upstream API unavailable") from exc
