"""
Benchmark — Intelligent API Traffic Optimizer (Phase 9).

Compares two scenarios for the same resource over N requests:

    A. Direct calls to the Mock API
    B. Calls through the Optimizer proxy (cache warm-up on 1st request)

Reports:
    - Request count
    - Elapsed wall-clock time (s)
    - Average latency per request (ms)
    - Cache hit ratio (from /metrics)
    - Mock API calls made

Usage (both services must be running):
    # Terminal 1 — start Mock API on port 8001:
    .venv\\Scripts\\uvicorn mock_api.main:app --port 8001

    # Terminal 2 — start Optimizer on port 8000:
    .venv\\Scripts\\uvicorn app.main:app --port 8000

    # Terminal 3 — run benchmark:
    .venv\\Scripts\\python benchmark.py
"""

import asyncio
import time
from typing import Dict, Any

import httpx

# ---------------------------------------------------------------------------
# Config — adjust these as needed
# ---------------------------------------------------------------------------
MOCK_API_BASE   = "http://127.0.0.1:8001"
OPTIMIZER_BASE  = "http://127.0.0.1:8000"
RESOURCE_ID     = "benchmark-resource"
N_REQUESTS      = 50          # requests per scenario
CONCURRENCY     = 10          # simultaneous requests per batch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def fetch_one(client: httpx.AsyncClient, url: str) -> float:
    """Fetch a URL and return elapsed milliseconds."""
    start = time.perf_counter()
    await client.get(url)
    return (time.perf_counter() - start) * 1000


async def run_scenario(
    label: str,
    base_url: str,
    path: str,
    n: int,
    concurrency: int,
) -> Dict[str, Any]:
    """
    Send *n* GET requests to *base_url + path* in batches of *concurrency*.
    Returns a dict with timing stats.
    """
    latencies = []
    wall_start = time.perf_counter()

    async with httpx.AsyncClient(timeout=10.0) as client:
        for batch_start in range(0, n, concurrency):
            batch = [
                fetch_one(client, f"{base_url}{path}")
                for _ in range(min(concurrency, n - batch_start))
            ]
            results = await asyncio.gather(*batch)
            latencies.extend(results)

    wall_elapsed = time.perf_counter() - wall_start
    avg_latency  = sum(latencies) / len(latencies) if latencies else 0.0

    return {
        "label":           label,
        "total_requests":  len(latencies),
        "elapsed_s":       round(wall_elapsed, 3),
        "avg_latency_ms":  round(avg_latency, 2),
    }


async def get_optimizer_metrics() -> Dict[str, Any]:
    """Fetch /metrics from the Optimizer."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(f"{OPTIMIZER_BASE}/metrics")
        return resp.json()


async def reset_optimizer() -> None:
    """Clear cache and reset metrics on the Optimizer."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(f"{OPTIMIZER_BASE}/cache/reset")
        await client.post(f"{OPTIMIZER_BASE}/metrics/reset")


def print_table(results_a: Dict, results_b: Dict, metrics: Dict) -> None:
    """Print a concise comparison table."""
    sep = "-" * 62
    print()
    print("=" * 62)
    print("  API Traffic Optimizer — Phase 9 Benchmark Results")
    print("=" * 62)
    headers = f"{'Metric':<30} {'Direct Mock API':>14} {'Via Optimizer':>14}"
    print(headers)
    print(sep)

    def row(label, a, b, fmt=lambda x: str(x)):
        print(f"  {label:<28} {fmt(a):>14} {fmt(b):>14}")

    row("Total Requests",     results_a["total_requests"],  results_b["total_requests"])
    row("Elapsed Time (s)",   results_a["elapsed_s"],       results_b["elapsed_s"],
        fmt=lambda x: f"{x:.3f}s")
    row("Avg Latency (ms)",   results_a["avg_latency_ms"],  results_b["avg_latency_ms"],
        fmt=lambda x: f"{x:.2f}ms")
    row("Mock API Calls",     results_a["total_requests"],  metrics.get("mock_api_calls", "N/A"))
    row("Cache Hit Ratio",    "N/A",                        f"{metrics.get('cache_hit_ratio', 0):.2%}")
    row("Requests Saved",     "N/A",                        metrics.get("requests_saved", "N/A"))

    print(sep)
    speedup = (
        results_a["avg_latency_ms"] / results_b["avg_latency_ms"]
        if results_b["avg_latency_ms"] > 0
        else float("inf")
    )
    print(f"  Optimizer avg latency speedup:  {speedup:.2f}x")
    print("=" * 62)
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    print(f"\nBenchmark config: {N_REQUESTS} requests, concurrency={CONCURRENCY}")
    print(f"Resource: {RESOURCE_ID}\n")

    # Reset Optimizer state before starting
    print("Resetting Optimizer cache and metrics ...")
    await reset_optimizer()

    # Scenario A: Direct Mock API calls
    print(f"[A] Sending {N_REQUESTS} requests directly to Mock API ...")
    results_a = await run_scenario(
        label="Direct Mock API",
        base_url=MOCK_API_BASE,
        path=f"/api/data/{RESOURCE_ID}",
        n=N_REQUESTS,
        concurrency=CONCURRENCY,
    )

    # Reset again so Optimizer starts cold
    await reset_optimizer()

    # Scenario B: Via Optimizer (cache cold on first batch)
    print(f"[B] Sending {N_REQUESTS} requests through Optimizer ...")
    results_b = await run_scenario(
        label="Via Optimizer",
        base_url=OPTIMIZER_BASE,
        path=f"/proxy/data/{RESOURCE_ID}",
        n=N_REQUESTS,
        concurrency=CONCURRENCY,
    )

    # Fetch final metrics
    metrics = await get_optimizer_metrics()

    print_table(results_a, results_b, metrics)


if __name__ == "__main__":
    asyncio.run(main())
