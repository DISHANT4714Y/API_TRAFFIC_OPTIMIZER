"""
benchmarks/run_benchmark.py — Phase 2B

Asynchronous benchmark runner for the Intelligent API Traffic Optimizer.

Usage (both services must be running):
    # Terminal 1 — Mock API
    uvicorn mock_api.main:app --port 8001

    # Terminal 2 — Optimizer
    uvicorn app.main:app --port 8000

    # Terminal 3 — Run benchmark
    python benchmarks/run_benchmark.py --mode optimized --workload W-REP
    python benchmarks/run_benchmark.py --mode baseline  --workload W-REP
    python benchmarks/run_benchmark.py --help

Design notes:
  - Concurrency is bounded by asyncio.Semaphore.
  - Each request uses time.perf_counter() (monotonic, sub-millisecond).
  - Warm-up requests are excluded from all reported metrics.
  - Results are written to benchmarks/results/run_<RUN_ID>.json (never overwritten).
  - Server-side metrics (/metrics, /cache/stats, /stats) are read AFTER the
    measured phase and stored verbatim.  Client-side latency is the primary
    source for latency statistics.
  - One failed request does NOT abort the run; each error is recorded individually.
  - Timeout and connection errors are counted as failures.

Endpoint paths used (verified from source code):
  Optimizer  GET  :8000/health
  Optimizer  GET  :8000/proxy/data/{resource_id}?delay_ms=N
  Optimizer  GET  :8000/metrics
  Optimizer  GET  :8000/cache/stats
  Optimizer  POST :8000/cache/reset
  Optimizer  POST :8000/metrics/reset
  Mock API   GET  :8001/health
  Mock API   GET  :8001/api/data/{resource_id}?delay_ms=N
  Mock API   GET  :8001/stats
  Mock API   POST :8001/stats/reset
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
import traceback
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

# Suppress starlette/httpx deprecation advisory (library-level, not a project bug)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="starlette")

# Ensure benchmarks/ is importable regardless of working directory
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent))

from benchmarks.metrics import (
    build_result_record,
    make_run_id,
    save_result,
)
from benchmarks.workloads import (
    WorkloadProfile,
    generate_resource_ids,
    warm_up_resource_ids,
)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_OPTIMIZER_URL  = "http://127.0.0.1:8000"
DEFAULT_MOCK_API_URL   = "http://127.0.0.1:8001"
DEFAULT_N_REQUESTS     = 100
DEFAULT_CONCURRENCY    = 10
DEFAULT_WARM_UP        = 0
DEFAULT_MOCK_DELAY_MS  = 100   # passed as ?delay_ms= query param
DEFAULT_POOL_SIZE      = 10
DEFAULT_SEED           = 42
DEFAULT_TIMEOUT_S      = 10.0
DEFAULT_REPETITIONS    = 1
DEFAULT_RESULTS_DIR    = _HERE / "results"

# ---------------------------------------------------------------------------
# Configuration dataclass (plain dict for CLI simplicity)
# ---------------------------------------------------------------------------

def build_config(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "mode":              args.mode,
        "workload":          args.workload,
        "n_requests":        args.n_requests,
        "concurrency":       args.concurrency,
        "warm_up_requests":  args.warm_up,
        "mock_delay_ms":     args.mock_delay_ms,
        "pool_size":         args.pool_size,
        "random_seed":       args.seed,
        "timeout_s":         args.timeout,
        "repetitions":       getattr(args, "repetitions", DEFAULT_REPETITIONS),
        "optimizer_url":     args.optimizer_url,
        "mock_api_url":      args.mock_api_url,
    }


def validate_config(cfg: Dict[str, Any]) -> None:
    """Raise ValueError with a readable message for invalid settings."""
    if cfg["n_requests"] < 1:
        raise ValueError("--n-requests must be >= 1")
    if cfg["concurrency"] < 1:
        raise ValueError("--concurrency must be >= 1")
    if cfg["concurrency"] > cfg["n_requests"]:
        raise ValueError(
            f"--concurrency ({cfg['concurrency']}) exceeds "
            f"--n-requests ({cfg['n_requests']}); reduce concurrency."
        )
    if cfg["warm_up_requests"] < 0:
        raise ValueError("--warm-up must be >= 0")
    if cfg["mock_delay_ms"] < 0:
        raise ValueError("--mock-delay-ms must be >= 0")
    if cfg["pool_size"] < 1:
        raise ValueError("--pool-size must be >= 1")
    if cfg["timeout_s"] <= 0:
        raise ValueError("--timeout must be > 0")
    if cfg.get("repetitions", 1) < 1:
        raise ValueError("--repetitions must be >= 1")
    valid_modes = {"baseline", "optimized"}
    if cfg["mode"] not in valid_modes:
        raise ValueError(f"--mode must be one of {valid_modes}")
    valid_workloads = {p.value for p in WorkloadProfile}
    if cfg["workload"] not in valid_workloads:
        raise ValueError(
            f"--workload must be one of {sorted(valid_workloads)}"
        )


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

async def check_health(
    client: httpx.AsyncClient,
    url: str,
    name: str,
) -> None:
    """
    GET {url}/health and raise RuntimeError if the service is unreachable
    or returns a non-2xx status.
    """
    try:
        resp = await client.get(f"{url}/health", timeout=5.0)
        resp.raise_for_status()
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"{name} is not reachable at {url}. "
            f"Start it first.\n  Error: {exc}"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"{name} health check returned {exc.response.status_code}."
        ) from exc


async def reset_state(
    client: httpx.AsyncClient,
    optimizer_url: str,
    mock_api_url: str,
    label: str = "",
) -> List[str]:
    """
    Reset all counters and cache state before a measured run.

    Returns a list of action strings documenting what was done.
    """
    actions: List[str] = []
    prefix = f"[{label}] " if label else ""

    # 1. Reset Mock API upstream counter
    try:
        r = await client.post(f"{mock_api_url}/stats/reset", timeout=5.0)
        r.raise_for_status()
        actions.append(f"{prefix}POST {mock_api_url}/stats/reset -> {r.status_code}")
    except Exception as exc:
        actions.append(f"{prefix}POST {mock_api_url}/stats/reset -> FAILED: {exc}")

    # 2. Reset optimizer cache + cache stats
    try:
        r = await client.post(f"{optimizer_url}/cache/reset", timeout=5.0)
        r.raise_for_status()
        actions.append(f"{prefix}POST {optimizer_url}/cache/reset -> {r.status_code}")
    except Exception as exc:
        actions.append(f"{prefix}POST {optimizer_url}/cache/reset -> FAILED: {exc}")

    # 3. Reset optimizer metrics
    try:
        r = await client.post(f"{optimizer_url}/metrics/reset", timeout=5.0)
        r.raise_for_status()
        actions.append(f"{prefix}POST {optimizer_url}/metrics/reset -> {r.status_code}")
    except Exception as exc:
        actions.append(f"{prefix}POST {optimizer_url}/metrics/reset -> FAILED: {exc}")

    return actions


async def read_server_metrics(
    client: httpx.AsyncClient,
    optimizer_url: str,
    mock_api_url: str,
) -> Dict[str, Any]:
    """
    Read post-run aggregate metrics from both services.
    Stores raw JSON verbatim; analysis script derives derived metrics.
    Missing endpoints are recorded as None with an error note.
    """
    result: Dict[str, Any] = {}

    for label, url in [
        ("optimizer_metrics", f"{optimizer_url}/metrics"),
        ("cache_stats",       f"{optimizer_url}/cache/stats"),
        ("mock_api_stats",    f"{mock_api_url}/stats"),
    ]:
        try:
            r = await client.get(url, timeout=5.0)
            r.raise_for_status()
            result[label] = r.json()
        except httpx.RequestError as exc:
            result[label] = {"error": f"RequestError: {exc}"}
        except httpx.HTTPStatusError as exc:
            result[label] = {"error": f"HTTP {exc.response.status_code}"}
        except Exception as exc:
            result[label] = {"error": str(exc)}

    return result


# ---------------------------------------------------------------------------
# Per-request execution
# ---------------------------------------------------------------------------

async def execute_single_request(
    client:    httpx.AsyncClient,
    url:       str,
    params:    Dict[str, str],
    sem:       asyncio.Semaphore,
    timeout_s: float,
) -> Dict[str, Any]:
    """
    Issue one GET request and return a result dict.

    The monotonic clock is started *outside* the semaphore wait so that
    queueing time is included in the reported latency — this reflects the
    actual client-observed duration.

    Fields in the returned dict:
        ok          bool    True if HTTP 2xx
        status      int     HTTP status code (0 for connection error)
        latency_ms  float   Wall-clock ms from request start to response end
        x_cache     str     Value of X-Cache header (or "ABSENT")
        error       str     Error message (empty string on success)
    """
    t_start = time.perf_counter()
    async with sem:
        try:
            resp = await client.get(url, params=params, timeout=timeout_s)
            latency_ms = (time.perf_counter() - t_start) * 1000.0
            x_cache = resp.headers.get("x-cache", "ABSENT").upper()
            ok = resp.is_success
            return {
                "ok":         ok,
                "status":     resp.status_code,
                "latency_ms": latency_ms,
                "x_cache":    x_cache,
                "error":      "" if ok else f"HTTP {resp.status_code}",
            }
        except httpx.TimeoutException as exc:
            latency_ms = (time.perf_counter() - t_start) * 1000.0
            return {
                "ok":         False,
                "status":     0,
                "latency_ms": latency_ms,
                "x_cache":    "ABSENT",
                "error":      f"TimeoutError: {exc!r}",
            }
        except httpx.RequestError as exc:
            latency_ms = (time.perf_counter() - t_start) * 1000.0
            return {
                "ok":         False,
                "status":     0,
                "latency_ms": latency_ms,
                "x_cache":    "ABSENT",
                "error":      f"RequestError: {exc!r}",
            }


async def run_phase(
    client:      httpx.AsyncClient,
    urls:        List[str],
    delay_ms:    int,
    concurrency: int,
    timeout_s:   float,
    label:       str = "phase",
) -> List[Dict[str, Any]]:
    """
    Issue requests for every URL in *urls* with bounded concurrency.

    Requests are issued as async tasks; the semaphore keeps at most
    *concurrency* requests in flight at once.  A failed request is recorded
    but does not abort remaining requests.

    Args:
        urls:        One URL per request (resource IDs are embedded in URLs).
        delay_ms:    Value passed as ?delay_ms= query parameter.
        concurrency: Maximum simultaneous requests.
        timeout_s:   Per-request timeout in seconds.
        label:       Human-readable label for console progress.

    Returns:
        List of per-request result dicts (same order as *urls*).
    """
    sem = asyncio.Semaphore(concurrency)
    params = {"delay_ms": str(delay_ms)} if delay_ms > 0 else {}
    n = len(urls)

    tasks = [
        asyncio.create_task(
            execute_single_request(client, url, params, sem, timeout_s),
            name=f"{label}-req-{i}",
        )
        for i, url in enumerate(urls)
    ]

    results: List[Dict[str, Any]] = []
    done_count = 0
    for coro in asyncio.as_completed(tasks):
        result = await coro
        results.append(result)
        done_count += 1
        if done_count % max(1, n // 10) == 0 or done_count == n:
            pct = done_count / n * 100
            print(f"  {label}: {done_count}/{n} ({pct:.0f}%)", end="\r", flush=True)

    print()  # newline after progress
    return results


def build_request_urls(
    mode:        str,
    resource_ids: List[str],
    optimizer_url: str,
    mock_api_url:  str,
) -> List[str]:
    """Map resource IDs to full URLs based on the test mode."""
    if mode == "baseline":
        return [f"{mock_api_url}/api/data/{rid}" for rid in resource_ids]
    else:  # optimized
        return [f"{optimizer_url}/proxy/data/{rid}" for rid in resource_ids]


def summarise_request_results(
    raw: List[Dict[str, Any]],
) -> Tuple[List[float], int, int, List[Dict[str, Any]], Optional[int], Optional[int]]:
    """
    Extract summary arrays from per-request results.

    Returns:
        latencies_ms     List of all latency values (including failures)
        successful       Count of 2xx responses
        failed           Count of non-2xx + errors
        errors           List of error detail dicts
        x_cache_hits     Count of X-Cache: HIT responses (None if no header seen)
        x_cache_misses   Count of X-Cache: MISS responses
    """
    latencies_ms: List[float] = []
    successful = 0
    failed = 0
    errors: List[Dict[str, Any]] = []
    hit_count = 0
    miss_count = 0
    cache_header_seen = False

    for r in raw:
        latencies_ms.append(r["latency_ms"])
        if r["ok"]:
            successful += 1
        else:
            failed += 1
            errors.append({"status": r["status"], "error": r["error"]})

        xc = r.get("x_cache", "ABSENT")
        if xc not in ("ABSENT", ""):
            cache_header_seen = True
        if xc == "HIT":
            hit_count += 1
        elif xc == "MISS":
            miss_count += 1

    x_cache_hits   = hit_count   if cache_header_seen else None
    x_cache_misses = miss_count  if cache_header_seen else None
    return latencies_ms, successful, failed, errors, x_cache_hits, x_cache_misses


# ---------------------------------------------------------------------------
# Warm-cache setup
# ---------------------------------------------------------------------------

async def populate_cache(
    client:       httpx.AsyncClient,
    optimizer_url: str,
    resource_ids:  List[str],
    delay_ms:      int,
    timeout_s:     float,
) -> int:
    """
    Issue one request per resource ID to populate the optimizer cache.
    Returns the number of successful pre-population requests.
    """
    params = {"delay_ms": str(delay_ms)} if delay_ms > 0 else {}
    ok_count = 0
    for rid in resource_ids:
        url = f"{optimizer_url}/proxy/data/{rid}"
        try:
            r = await client.get(url, params=params, timeout=timeout_s)
            if r.is_success:
                ok_count += 1
        except Exception:
            pass
    return ok_count


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

async def run_benchmark(cfg: Dict[str, Any]) -> Path:
    """
    Execute one benchmark run according to *cfg*.

    Returns the path of the saved JSON result file.
    """
    mode          = cfg["mode"]
    workload_str  = cfg["workload"]
    n_requests    = cfg["n_requests"]
    concurrency   = cfg["concurrency"]
    warm_up_n     = cfg["warm_up_requests"]
    delay_ms      = cfg["mock_delay_ms"]
    pool_size     = cfg["pool_size"]
    seed          = cfg["random_seed"]
    timeout_s     = cfg["timeout_s"]
    optimizer_url = cfg["optimizer_url"]
    mock_api_url  = cfg["mock_api_url"]
    results_dir   = Path(cfg.get("results_dir", DEFAULT_RESULTS_DIR))

    workload = WorkloadProfile(workload_str)
    run_id   = make_run_id(workload_str, mode, concurrency)

    print(f"\n{'='*60}")
    print(f"  Run ID  : {run_id}")
    print(f"  Mode    : {mode}")
    print(f"  Workload: {workload_str} - {workload.description()}")
    print(f"  Requests: {n_requests}  Concurrency: {concurrency}  Warm-up: {warm_up_n}")
    print(f"  Delay   : {delay_ms} ms   Timeout: {timeout_s} s")
    print(f"{'='*60}")

    # Determine is this mode uses the optimizer at all (for state reset)
    uses_optimizer = (mode == "optimized")

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_s),
        limits=httpx.Limits(max_connections=concurrency + 5, max_keepalive_connections=concurrency),
    ) as client:

        # -- 1. Health checks ----------------------------------------------
        print("\n[1/5] Health checks ...")
        await check_health(client, mock_api_url,  "Mock API")
        print(f"  [OK] Mock API  ({mock_api_url}/health)")
        if uses_optimizer:
            await check_health(client, optimizer_url, "Optimizer")
            print(f"  [OK] Optimizer ({optimizer_url}/health)")

        # -- 2. State reset ------------------------------------------------
        print("\n[2/5] Resetting state ...")
        reset_actions = await reset_state(
            client, optimizer_url, mock_api_url, label="pre-run"
        )
        for action in reset_actions:
            print(f"  {action}")

        # -- 3. Warm-up phase ----------------------------------------------
        warm_up_info: Dict[str, Any] = {"requests": 0, "note": "no warm-up requested"}
        if warm_up_n > 0:
            print(f"\n[3/5] Warm-up ({warm_up_n} requests) ...")
            wu_ids  = generate_resource_ids(workload, warm_up_n, pool_size, seed)
            wu_urls = build_request_urls(mode, wu_ids, optimizer_url, mock_api_url)
            wu_raw  = await run_phase(client, wu_urls, delay_ms, concurrency, timeout_s, "warm-up")
            wu_ok   = sum(1 for r in wu_raw if r["ok"])
            print(f"  Warm-up done: {wu_ok}/{warm_up_n} successful")

            # Reset counters AFTER warm-up so warm-up traffic is excluded
            print("  Resetting counters after warm-up ...")
            post_wu_actions = await reset_state(
                client, optimizer_url, mock_api_url, label="post-warmup"
            )
            for action in post_wu_actions:
                print(f"    {action}")

            warm_up_info = {
                "requests":  warm_up_n,
                "successful": wu_ok,
                "note": "counters reset after warm-up; warm-up not in measured stats",
            }
        elif workload == WorkloadProfile.WARM:
            # W-WARM profile: pre-populate cache without counting warm-up requests
            print("\n[3/5] Pre-populating cache for W-WARM ...")
            wu_resource_ids = warm_up_resource_ids(workload, pool_size)
            ok_count = await populate_cache(
                client, optimizer_url, wu_resource_ids, delay_ms, timeout_s
            )
            print(f"  Pre-populated {ok_count}/{len(wu_resource_ids)} resource(s)")

            # Reset counters AFTER pre-population
            post_wu_actions = await reset_state(
                client, optimizer_url, mock_api_url, label="post-cache-populate"
            )
            for action in post_wu_actions:
                print(f"    {action}")

            warm_up_info = {
                "requests":   len(wu_resource_ids),
                "successful": ok_count,
                "note": (
                    "W-WARM: cache pre-populated with 1 request per resource; "
                    "counters reset after pre-population; cache NOT flushed"
                ),
            }
        else:
            print("\n[3/5] No warm-up (cold-cache run).")

        # -- 4. Measured phase ---------------------------------------------
        print(f"\n[4/5] Measured phase ({n_requests} requests, concurrency={concurrency}) ...")
        resource_ids = generate_resource_ids(workload, n_requests, pool_size, seed)
        urls         = build_request_urls(mode, resource_ids, optimizer_url, mock_api_url)

        t_wall_start = time.perf_counter()
        raw_results  = await run_phase(
            client, urls, delay_ms, concurrency, timeout_s, label=mode
        )
        benchmark_duration_s = time.perf_counter() - t_wall_start

        (
            latencies_ms, successful, failed, errors,
            x_cache_hits, x_cache_misses,
        ) = summarise_request_results(raw_results)

        attempted = len(raw_results)
        err_rate  = (failed / attempted * 100) if attempted else 0
        mean_lat  = (sum(latencies_ms) / len(latencies_ms)) if latencies_ms else 0

        print(f"  Attempted : {attempted}")
        print(f"  Successful: {successful}")
        print(f"  Failed    : {failed}  ({err_rate:.1f}% error rate)")
        print(f"  Mean lat  : {mean_lat:.1f} ms")
        print(f"  Duration  : {benchmark_duration_s:.2f} s")
        if x_cache_hits is not None:
            print(f"  X-Cache HIT/MISS: {x_cache_hits}/{x_cache_misses}")

        # -- 5. Read server metrics ----------------------------------------
        print("\n[5/5] Reading server metrics ...")
        server_metrics = await read_server_metrics(client, optimizer_url, mock_api_url)
        mock_total = (
            server_metrics.get("mock_api_stats", {}).get("total_requests")
        )
        if mock_total is not None:
            print(f"  Mock API upstream calls: {mock_total}")
        else:
            print("  Mock API upstream calls: unavailable")

    # -- Save result -------------------------------------------------------
    record = build_result_record(
        run_id=run_id,
        workload=workload_str,
        mode=mode,
        config=cfg,
        warm_up_info=warm_up_info,
        latencies_ms=latencies_ms,
        attempted=attempted,
        successful=successful,
        failed=failed,
        errors=errors,
        benchmark_duration_s=benchmark_duration_s,
        x_cache_hit_count=x_cache_hits,
        x_cache_miss_count=x_cache_misses,
        server_metrics=server_metrics,
    )

    out_path = save_result(record, results_dir)
    print(f"\n[OK] Result saved: {out_path}\n")
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_benchmark.py",
        description=(
            "Phase 2B benchmark runner for the Intelligent API Traffic Optimizer.\n"
            "Both services must be running before executing this script.\n\n"
            "Quick start:\n"
            "  python benchmarks/run_benchmark.py --mode optimized --workload W-REP\n"
            "  python benchmarks/run_benchmark.py --mode baseline  --workload W-REP"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    p.add_argument(
        "--mode", required=True, choices=["baseline", "optimized"],
        help="'baseline' = direct Mock API calls; 'optimized' = via Optimizer proxy",
    )
    p.add_argument(
        "--workload", required=True,
        choices=[pr.value for pr in WorkloadProfile],
        help=(
            "Workload profile: "
            "W-REP (repeated), W-MIX (mixed), W-UNQ (unique), "
            "W-WARM (warm cache), W-CON (concurrency sweep), W-COL (coalescing burst)"
        ),
    )
    p.add_argument(
        "--n-requests", type=int, default=DEFAULT_N_REQUESTS, dest="n_requests",
        metavar="N", help=f"Total measured requests (default {DEFAULT_N_REQUESTS})",
    )
    p.add_argument(
        "--concurrency", type=int, default=DEFAULT_CONCURRENCY,
        metavar="C", help=f"Max simultaneous requests (default {DEFAULT_CONCURRENCY})",
    )
    p.add_argument(
        "--warm-up", type=int, default=DEFAULT_WARM_UP, dest="warm_up",
        metavar="W", help=f"Warm-up requests before measured phase (default {DEFAULT_WARM_UP})",
    )
    p.add_argument(
        "--mock-delay-ms", type=int, default=DEFAULT_MOCK_DELAY_MS, dest="mock_delay_ms",
        metavar="MS",
        help=(
            f"Artificial upstream delay in ms, passed as ?delay_ms= (default {DEFAULT_MOCK_DELAY_MS}). "
            "Use the same value for paired baseline/optimized runs."
        ),
    )
    p.add_argument(
        "--pool-size", type=int, default=DEFAULT_POOL_SIZE, dest="pool_size",
        metavar="K", help=f"Resource pool size for W-MIX (default {DEFAULT_POOL_SIZE})",
    )
    p.add_argument(
        "--seed", type=int, default=DEFAULT_SEED,
        metavar="S", help=f"Random seed for reproducibility (default {DEFAULT_SEED})",
    )
    p.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT_S,
        metavar="T", help=f"Per-request timeout seconds (default {DEFAULT_TIMEOUT_S})",
    )
    p.add_argument(
        "--repetitions", type=int, default=DEFAULT_REPETITIONS,
        metavar="R", help=f"Number of benchmark repetitions to execute (default {DEFAULT_REPETITIONS})",
    )
    p.add_argument(
        "--optimizer-url", default=DEFAULT_OPTIMIZER_URL, dest="optimizer_url",
        metavar="URL", help=f"Optimizer base URL (default {DEFAULT_OPTIMIZER_URL})",
    )
    p.add_argument(
        "--mock-api-url", default=DEFAULT_MOCK_API_URL, dest="mock_api_url",
        metavar="URL", help=f"Mock API base URL (default {DEFAULT_MOCK_API_URL})",
    )
    p.add_argument(
        "--results-dir", default=str(DEFAULT_RESULTS_DIR), dest="results_dir",
        metavar="DIR", help=f"Directory for JSON result files (default {DEFAULT_RESULTS_DIR})",
    )
    return p


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()
    cfg    = build_config(args)
    cfg["results_dir"] = args.results_dir

    try:
        validate_config(cfg)
    except ValueError as exc:
        parser.error(str(exc))

    repetitions = cfg.get("repetitions", 1)
    for rep in range(1, repetitions + 1):
        if repetitions > 1:
            print(f"\n>>> Running Repetition {rep}/{repetitions} ...")
        asyncio.run(run_benchmark(cfg))


if __name__ == "__main__":
    main()
