"""
Intelligent API Traffic Optimizer - Main Application.

Exposes proxy endpoints to transparently route incoming client requests
to upstream APIs while tracking performance and establishing baseline metrics.

Phase 4 addition:
    Cache-key generation is now integrated into the proxy route.
    Every incoming GET request produces a deterministic SHA-256 cache key,
    which is logged for debugging. Phase 5 will use this key for actual
    cache lookups.
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
from app.requests.key_generator import generate_key_from_request

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("optimizer")

app = FastAPI(
    title="API Traffic Optimizer Prototype",
    description="Intelligent API Traffic Optimizer acting as an adaptive middleware proxy.",
    version="0.4.0",  # Phase 4: Cache-Key Generation
)

# Global proxy client instance
proxy_client = ProxyClient()


@app.get("/health", summary="Health Check", tags=["System"])
async def health() -> Dict[str, str]:
    """Returns the operational status of the optimizer."""
    return {"status": "ok"}


@app.get(
    "/debug/cache-key",
    summary="Inspect Cache Key (Development Only)",
    tags=["Debug"],
)
async def debug_cache_key(
    request: Request,
    resource_id: str = "example",
) -> Dict[str, str]:
    """
    Development-only endpoint that returns the cache key that would be
    generated for a given resource_id and query parameters.

    This endpoint exists purely for Phase 4 demonstration purposes.
    Remove or restrict access to this endpoint before production deployment
    because it reveals internal cache-key structure.

    Example:
        GET /debug/cache-key?resource_id=weather&city=Delhi&units=metric
    """
    # Collect all query params except 'resource_id' (which is our own param)
    extra_params = {
        k: v for k, v in request.query_params.items() if k != "resource_id"
    }
    key = generate_key_from_request(
        resource_id=resource_id,
        query_params=extra_params if extra_params else None,
    )
    return {
        "resource_id": resource_id,
        "query_params": str(extra_params),
        "cache_key": key,
        "note": "Development only — remove before production deployment",
    }


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

    # --- Phase 4: Generate cache key for this request ---
    # The key is deterministic: identical logical requests always produce the
    # same key regardless of query-parameter ordering.
    # Phase 5 will use this key to check the in-memory cache before calling
    # the upstream API. For now, we log it and move on.
    cache_key = generate_key_from_request(
        resource_id=resource_id,
        query_params=query_params if query_params else None,
    )
    logger.info("[OPTIMIZER] Incoming request: GET /proxy/data/%s", resource_id)
    logger.info("[OPTIMIZER] Cache key (Phase 4): %s", cache_key)
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
