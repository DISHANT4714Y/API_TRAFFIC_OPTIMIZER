"""
Mock External API application.

Simulates a slow, external third-party API with configurable latency,
probabilistic/deterministic failures, request logging, and observability metrics.
"""

import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Response

from mock_api import config
from mock_api.models import (
    DataResponse,
    HealthResponse,
    ResetResponse,
    StatsResponse,
)
from mock_api.state import state

# Setup lightweight structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("mock_api")

app = FastAPI(
    title="Mock External API",
    description="Controllable mock API simulating external third-party endpoints for optimization benchmarking.",
    version="0.2.0",
)


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    tags=["System"],
)
async def health() -> HealthResponse:
    """Returns the operational status of the mock API."""
    return HealthResponse(status="mock-api-ok")


@app.get(
    "/api/data/{resource_id}",
    response_model=DataResponse,
    summary="Fetch Resource Data",
    tags=["Resources"],
)
async def get_data(
    resource_id: str,
    response: Response,
    delay_ms: Optional[int] = Query(
        default=None,
        ge=0,
        description="Optional request-specific delay override in milliseconds",
    ),
) -> DataResponse:
    """
    Returns deterministic data for a given resource_id.

    Simulates network / upstream latency using asyncio.sleep.
    Tracks external request count for benchmark measurement.
    """
    # 1. Deterministic failure mode for explicit testing
    if resource_id == "fail-test":
        logger.warning("[MOCK API] Deterministic failure triggered for resource: %s", resource_id)
        raise HTTPException(status_code=500, detail="Simulated external API failure")

    # 2. Probabilistic failure mode
    if config.MOCK_API_FAILURE_RATE > 0:
        if random.uniform(0, 100) < config.MOCK_API_FAILURE_RATE:
            logger.warning("[MOCK API] Probabilistic failure triggered (rate: %s%%)", config.MOCK_API_FAILURE_RATE)
            raise HTTPException(status_code=500, detail="Simulated external API failure")

    # 3. Increment request counter and generate request ID
    req_count = state.increment_requests()
    request_id = f"mock-{req_count:06d}"

    # 4. Determine and apply latency
    effective_delay_ms = delay_ms if delay_ms is not None else config.MOCK_API_DELAY_MS
    if effective_delay_ms > 0:
        await asyncio.sleep(effective_delay_ms / 1000.0)

    # 5. Log request details
    logger.info(
        "[MOCK API] GET /api/data/%s | req_id=%s | delay=%sms | count=%s",
        resource_id,
        request_id,
        effective_delay_ms,
        req_count,
    )

    # 6. Response headers
    response.headers["X-Request-Id"] = request_id
    response.headers["X-Mock-Delay-Ms"] = str(effective_delay_ms)

    # 7. Generate deterministic payload
    sample_data = {
        "temperature": 30,
        "condition": "clear",
        "details": f"Data payload for {resource_id}",
    }

    return DataResponse(
        resource_id=resource_id,
        data=sample_data,
        served_at=datetime.now(timezone.utc).isoformat(),
        request_id=request_id,
    )


@app.get(
    "/stats",
    response_model=StatsResponse,
    summary="Get API Statistics",
    tags=["Observability"],
)
async def get_stats() -> StatsResponse:
    """Returns runtime statistics, including the total external requests served."""
    stats_data = state.get_stats()
    return StatsResponse(
        total_requests=stats_data["total_requests"],
        uptime_seconds=stats_data["uptime_seconds"],
    )


@app.post(
    "/stats/reset",
    response_model=ResetResponse,
    summary="Reset API Statistics",
    tags=["Observability"],
)
async def reset_stats() -> ResetResponse:
    """Resets runtime request counters to zero for clean benchmark runs."""
    reset_data = state.reset()
    logger.info("[MOCK API] Statistics reset to zero")
    return ResetResponse(
        status=reset_data["status"],
        total_requests=reset_data["total_requests"],
    )
