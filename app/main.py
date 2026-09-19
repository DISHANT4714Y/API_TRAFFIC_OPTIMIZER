"""
Intelligent API Traffic Optimizer - Main Application.

Exposes proxy endpoints to transparently route incoming client requests
to upstream APIs while tracking performance and establishing baseline metrics.

Phase 4 addition:
    Cache-key generation is integrated into the proxy route. Every incoming
    GET request produces a deterministic SHA-256 cache key.

Phase 5 addition:
    In-memory cache lookup is now performed before calling the upstream API.
    - CACHE HIT  → return cached response immediately (no upstream call).
    - CACHE MISS → call upstream, store 2xx responses, return response.
    Failed upstream responses (4xx/5xx) are never stored in the cache.
    Two new endpoints expose cache observability and control:
        GET  /cache/stats  — hit/miss statistics
        POST /cache/clear  — flush all cached entries (useful for testing)
"""

import logging
import time
from typing import Any, Dict

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.cache.manager import CacheManager
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
    version="0.5.0",  # Phase 5: Basic In-Memory Cache
)

# Module-level singletons — replaced in tests via patch.object
proxy_client = ProxyClient()
cache_manager = CacheManager()


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------

@app.get("/health", summary="Health Check", tags=["System"])
async def health() -> Dict[str, str]:
    """Returns the operational status of the optimizer."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Cache Observability & Control
# ---------------------------------------------------------------------------

@app.get(
    "/cache/stats",
    summary="Cache Statistics",
    tags=["Cache"],
)
async def cache_stats() -> Dict[str, Any]:
    """
    Returns current in-memory cache statistics.

    Includes total get() calls, hits, misses, hit ratio, and number
    of entries currently stored.
    """
    return cache_manager.get_stats()


@app.post(
    "/cache/clear",
    summary="Clear Cache",
    tags=["Cache"],
)
async def cache_clear() -> Dict[str, Any]:
    """
    Flushes all entries from the in-memory cache.

    Useful for benchmark resets and integration testing.
    Does NOT reset hit/miss statistics.
    """
    cleared = cache_manager.clear()
    return {"status": "cleared", "entries_removed": cleared}


# ---------------------------------------------------------------------------
# Debug (Phase 4 — development only)
# ---------------------------------------------------------------------------

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

    Remove or restrict access to this endpoint before production deployment.

    Example:
        GET /debug/cache-key?resource_id=weather&city=Delhi&units=metric
    """
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


# ---------------------------------------------------------------------------
# Proxy
# ---------------------------------------------------------------------------

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
    Transparently forwards a resource request to the upstream Mock API
    with an in-memory cache layer (Phase 5).

    Flow:
        1. Generate deterministic cache key from resource_id + query params.
        2. Check cache:
           - HIT  → return cached payload immediately (no upstream call).
           - MISS → continue to upstream.
        3. Call upstream Mock API.
        4. On success (2xx): store response in cache, then return.
        5. On error (4xx/5xx / timeout / unavailable): return error, do not cache.
    """
    query_params = dict(request.query_params)

    # --- Phase 4 + 5: Generate deterministic cache key ---
    cache_key = generate_key_from_request(
        resource_id=resource_id,
        query_params=query_params if query_params else None,
    )
    logger.info("[OPTIMIZER] Incoming request: GET /proxy/data/%s", resource_id)
    logger.info("[OPTIMIZER] Cache key: %s", cache_key)

    # --- Phase 5: Cache lookup ---
    cached_value = cache_manager.get(cache_key)
    if cached_value is not None:
        # Cache HIT — serve without calling upstream
        response.headers["X-Cache"] = "HIT"
        return cached_value

    # Cache MISS — call upstream
    target_url = f"{proxy_client.base_url}/api/data/{resource_id}"
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

        # --- Phase 5: Cache successful responses only ---
        if 200 <= status_code < 300:
            cache_manager.set(cache_key, data)

        response.headers["X-Cache"] = "MISS"
        return data

    except UpstreamError as err:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.warning(
            "[OPTIMIZER] Upstream returned error %s (%s ms)",
            err.status_code,
            elapsed_ms,
        )
        # Do NOT cache error responses
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
