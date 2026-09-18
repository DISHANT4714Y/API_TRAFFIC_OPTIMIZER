"""
Intelligent API Traffic Optimizer - Main Application.

Exposes proxy endpoints to transparently route incoming client requests
to upstream APIs while tracking performance and establishing baseline metrics.
"""

import logging
import time
from typing import Any, Dict

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.proxy.client import (
    ProxyClient,
    UpstreamError,
    UpstreamTimeoutError,
    UpstreamUnavailableError,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("optimizer")

app = FastAPI(
    title="API Traffic Optimizer Prototype",
    description="Intelligent API Traffic Optimizer acting as an adaptive middleware proxy.",
    version="0.3.0",
)

# Global proxy client instance
proxy_client = ProxyClient()


@app.get("/health", summary="Health Check", tags=["System"])
async def health() -> Dict[str, str]:
    """Returns the operational status of the optimizer."""
    return {"status": "ok"}


@app.get(
    "/proxy/data/{resource_id}",
    summary="Proxy Resource Request",
    tags=["Proxy"],
)
async def proxy_data(
    resource_id: str,
    request: Request,
    response: Response,
) -> Any:
    """
    Transparently forwards a resource request to the upstream Mock API.

    - Preserves and forwards query parameters.
    - Preserves upstream status codes and response headers.
    - Handles timeouts (504 Gateway Timeout) and connection failures (502 Bad Gateway).
    """
    query_params = dict(request.query_params)
    target_url = f"{proxy_client.base_url}/api/data/{resource_id}"

    logger.info("[OPTIMIZER] Incoming request: GET /proxy/data/%s", resource_id)
    logger.info("[OPTIMIZER] Forwarding request to: %s", target_url)

    start_time = time.perf_counter()

    try:
        status_code, data, upstream_headers = await proxy_client.fetch_resource(
            resource_id=resource_id,
            params=query_params if query_params else None,
        )
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "[OPTIMIZER] Upstream response: %s (%s ms)",
            status_code,
            elapsed_ms,
        )

        # Forward upstream identifiers and debug headers
        for header_key in ["x-request-id", "x-mock-delay-ms"]:
            if header_key in upstream_headers:
                response.headers[header_key] = upstream_headers[header_key]

        return data

    except UpstreamError as err:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.warning(
            "[OPTIMIZER] Upstream returned error %s (%s ms)",
            err.status_code,
            elapsed_ms,
        )
        return JSONResponse(status_code=err.status_code, content=err.detail)

    except UpstreamTimeoutError:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error("[OPTIMIZER] Upstream request timed out (%s ms)", elapsed_ms)
        return JSONResponse(
            status_code=504,
            content={"error": "Upstream API timeout"},
        )

    except UpstreamUnavailableError:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error("[OPTIMIZER] Upstream API unavailable (%s ms)", elapsed_ms)
        return JSONResponse(
            status_code=502,
            content={"error": "Upstream API unavailable"},
        )
