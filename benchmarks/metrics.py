"""
benchmarks/metrics.py — Phase 2B

Pure statistical functions and result-schema helpers for the benchmark runner.

All functions here are side-effect-free so they are easy to unit-test.
No I/O is performed in this module.

Throughput definition:
    attempted_requests / wall_clock_duration_seconds
    (based on all attempted requests, including failures, divided by the
    total measured wall-clock time — not just the sum of individual latencies)

P99 policy:
    P99 is computed only when the sample contains >= min_n_for_p99 values
    (default 100). When unavailable it is stored as None — never as zero.

Upstream reduction formula:
    ((baseline_upstream - optimized_upstream) / baseline_upstream) x 100
    Undefined (None) when baseline_upstream == 0.
"""

from __future__ import annotations

import json
import platform
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------

def percentile(data: List[float], p: float) -> float:
    """
    Return the p-th percentile of *data* using linear interpolation
    (equivalent to numpy.percentile default method).

    Args:
        data: Non-empty list of numeric values (need not be sorted).
        p:    Percentile in the closed interval [0, 100].

    Returns:
        Interpolated percentile value.

    Raises:
        ValueError: If *data* is empty or *p* is outside [0, 100].
    """
    if not data:
        raise ValueError("Cannot compute percentile of an empty sample.")
    if not 0.0 <= p <= 100.0:
        raise ValueError(f"Percentile p must be in [0, 100]; got {p!r}.")

    sorted_data = sorted(data)
    n = len(sorted_data)
    if n == 1:
        return float(sorted_data[0])

    # Linear interpolation
    idx = (p / 100.0) * (n - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= n:
        return float(sorted_data[-1])
    frac = idx - lo
    return float(sorted_data[lo] + frac * (sorted_data[hi] - sorted_data[lo]))


def compute_latency_stats(
    latencies_ms: List[float],
    min_n_for_p99: int = 100,
) -> Dict[str, Optional[float]]:
    """
    Compute summary statistics from per-request latency samples.

    Args:
        latencies_ms:   Individual request wall-clock durations in milliseconds.
        min_n_for_p99:  Minimum number of samples before P99 is reported.
                        When n < min_n_for_p99, p99_ms is None (not zero).

    Returns:
        Dict with keys: mean_ms, p50_ms, p95_ms, p99_ms, min_ms, max_ms.
        All values are None when *latencies_ms* is empty.
    """
    if not latencies_ms:
        return {
            "mean_ms": None,
            "p50_ms":  None,
            "p95_ms":  None,
            "p99_ms":  None,
            "min_ms":  None,
            "max_ms":  None,
        }

    n = len(latencies_ms)
    return {
        "mean_ms": round(statistics.mean(latencies_ms), 3),
        "p50_ms":  round(percentile(latencies_ms, 50), 3),
        "p95_ms":  round(percentile(latencies_ms, 95), 3),
        "p99_ms":  round(percentile(latencies_ms, 99), 3) if n >= min_n_for_p99 else None,
        "min_ms":  round(min(latencies_ms), 3),
        "max_ms":  round(max(latencies_ms), 3),
    }


def compute_throughput(attempted: int, duration_s: float) -> Optional[float]:
    """
    Throughput = attempted_requests / wall_clock_duration_s.

    Returns None when duration_s <= 0 (undefined or instantaneous).
    'Attempted' includes both successful and failed requests.
    """
    if duration_s <= 0:
        return None
    return round(attempted / duration_s, 3)


def compute_error_rate(failed: int, total_attempted: int) -> Optional[float]:
    """
    Error rate = (failed / total_attempted) × 100  (percent).

    Returns None when total_attempted == 0.
    """
    if total_attempted == 0:
        return None
    return round((failed / total_attempted) * 100, 4)


def compute_upstream_reduction(
    baseline_upstream: Optional[int],
    optimized_upstream: Optional[int],
) -> Optional[float]:
    """
    Upstream request reduction percentage.

    Formula:
        ((baseline_upstream - optimized_upstream) / baseline_upstream) × 100

    Returns:
        Float percentage. A negative value means the optimized path made
        *more* upstream calls than the baseline — this is not treated as an
        error; it is reported as-is.
        None when baseline_upstream is None, 0, or optimized_upstream is None.
    """
    if baseline_upstream is None or optimized_upstream is None:
        return None
    if baseline_upstream == 0:
        return None  # denominator undefined
    return round((1 - optimized_upstream / baseline_upstream) * 100, 2)


# ---------------------------------------------------------------------------
# Result schema
# ---------------------------------------------------------------------------

def make_run_id(workload: str, mode: str, concurrency: int) -> str:
    """Generate a unique run identifier based on current UTC time."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{ts}-{workload}-{mode}-c{concurrency}"


def collect_environment() -> Dict[str, str]:
    """Collect software version metadata for the result record."""
    try:
        import httpx as _httpx
        httpx_ver = _httpx.__version__
    except Exception:
        httpx_ver = "unknown"
    try:
        import fastapi as _fa
        fastapi_ver = _fa.__version__
    except Exception:
        fastapi_ver = "unknown"
    return {
        "python_version": sys.version.split()[0],
        "platform":       platform.platform(),
        "httpx_version":  httpx_ver,
        "fastapi_version": fastapi_ver,
    }


def build_result_record(
    *,
    run_id:             str,
    workload:           str,
    mode:               str,           # "baseline" | "optimized"
    config:             Dict[str, Any],
    warm_up_info:       Dict[str, Any],
    latencies_ms:       List[float],
    attempted:          int,
    successful:         int,
    failed:             int,
    errors:             List[Dict[str, Any]],
    benchmark_duration_s: float,
    x_cache_hit_count:  Optional[int],
    x_cache_miss_count: Optional[int],
    server_metrics:     Dict[str, Any],
) -> Dict[str, Any]:
    """
    Assemble the complete JSON result record for one benchmark run.

    The raw latencies_ms list is included so any percentile can be
    recomputed from the saved file without re-running the experiment.
    """
    stats = compute_latency_stats(latencies_ms)
    throughput = compute_throughput(attempted, benchmark_duration_s)
    error_rate  = compute_error_rate(failed, attempted)

    return {
        "run_id":    run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "workload":  workload,
        "mode":      mode,
        "config":    config,
        "environment": collect_environment(),
        "warm_up":   warm_up_info,
        "results": {
            "attempted_requests":   attempted,
            "successful_requests":  successful,
            "failed_requests":      failed,
            "error_rate_pct":       error_rate,
            "mean_latency_ms":      stats["mean_ms"],
            "p50_latency_ms":       stats["p50_ms"],
            "p95_latency_ms":       stats["p95_ms"],
            "p99_latency_ms":       stats["p99_ms"],
            "min_latency_ms":       stats["min_ms"],
            "max_latency_ms":       stats["max_ms"],
            "throughput_rps":       throughput,
            "benchmark_duration_s": round(benchmark_duration_s, 3),
            "x_cache_hit_count":    x_cache_hit_count,
            "x_cache_miss_count":   x_cache_miss_count,
            # raw latency samples — preserved for reanalysis
            "latencies_ms":         [round(v, 3) for v in latencies_ms],
        },
        "server_metrics": server_metrics,
        "errors":    errors,
    }


import csv


def save_result_csv(record: Dict[str, Any], results_dir: Path) -> Path:
    """
    Append or write summary record to a CSV file in results_dir.
    Also writes a run-specific CSV file: run_{record['run_id']}.csv.
    Never overwrites previous individual run files.
    """
    results_dir.mkdir(parents=True, exist_ok=True)
    csv_file = results_dir / f"run_{record['run_id']}.csv"
    if csv_file.exists():
        i = 1
        while csv_file.exists():
            csv_file = results_dir / f"run_{record['run_id']}_{i}.csv"
            i += 1

    fieldnames = [
        "run_id",
        "timestamp",
        "workload",
        "mode",
        "n_requests",
        "concurrency",
        "warm_up_requests",
        "mock_delay_ms",
        "pool_size",
        "attempted_requests",
        "successful_requests",
        "failed_requests",
        "error_rate_pct",
        "mean_latency_ms",
        "p50_latency_ms",
        "p95_latency_ms",
        "p99_latency_ms",
        "min_latency_ms",
        "max_latency_ms",
        "throughput_rps",
        "benchmark_duration_s",
        "x_cache_hit_count",
        "x_cache_miss_count",
    ]

    row = {
        "run_id": record.get("run_id"),
        "timestamp": record.get("timestamp"),
        "workload": record.get("workload"),
        "mode": record.get("mode"),
        "n_requests": record.get("config", {}).get("n_requests"),
        "concurrency": record.get("config", {}).get("concurrency"),
        "warm_up_requests": record.get("config", {}).get("warm_up_requests"),
        "mock_delay_ms": record.get("config", {}).get("mock_delay_ms"),
        "pool_size": record.get("config", {}).get("pool_size"),
        "attempted_requests": record.get("results", {}).get("attempted_requests"),
        "successful_requests": record.get("results", {}).get("successful_requests"),
        "failed_requests": record.get("results", {}).get("failed_requests"),
        "error_rate_pct": record.get("results", {}).get("error_rate_pct"),
        "mean_latency_ms": record.get("results", {}).get("mean_latency_ms"),
        "p50_latency_ms": record.get("results", {}).get("p50_latency_ms"),
        "p95_latency_ms": record.get("results", {}).get("p95_latency_ms"),
        "p99_latency_ms": record.get("results", {}).get("p99_latency_ms"),
        "min_latency_ms": record.get("results", {}).get("min_latency_ms"),
        "max_latency_ms": record.get("results", {}).get("max_latency_ms"),
        "throughput_rps": record.get("results", {}).get("throughput_rps"),
        "benchmark_duration_s": record.get("results", {}).get("benchmark_duration_s"),
        "x_cache_hit_count": record.get("results", {}).get("x_cache_hit_count"),
        "x_cache_miss_count": record.get("results", {}).get("x_cache_miss_count"),
    }

    with open(csv_file, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)

    # Also append to cumulative summary.csv in results_dir if practical
    summary_file = results_dir / "summary.csv"
    summary_exists = summary_file.exists()
    with open(summary_file, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if not summary_exists:
            writer.writeheader()
        writer.writerow(row)

    return csv_file


def save_result(record: Dict[str, Any], results_dir: Path) -> Path:
    """
    Write *record* to a uniquely-named JSON file in *results_dir*.
    Also writes corresponding CSV summary.

    Never overwrites an existing file. The filename is derived from
    record["run_id"].

    Returns the path of the written JSON file.
    """
    results_dir.mkdir(parents=True, exist_ok=True)
    filename = results_dir / f"run_{record['run_id']}.json"
    if filename.exists():
        # Append a suffix rather than overwriting
        i = 1
        while filename.exists():
            filename = results_dir / f"run_{record['run_id']}_{i}.json"
            i += 1
    with open(filename, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, ensure_ascii=False)

    try:
        save_result_csv(record, results_dir)
    except Exception:
        pass

    return filename
