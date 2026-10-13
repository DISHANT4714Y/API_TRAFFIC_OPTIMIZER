#!/usr/bin/env python3
"""
benchmarks/run_phase2c.py  — Phase 2C master experiment runner

Executes all Phase 2C experiments in sequence:
  Exp A  — W-REP  baseline vs optimized (3 reps each)
  Exp B  — W-MIX  baseline vs optimized (3 reps each)
  Exp C  — W-UNQ  baseline vs optimized (3 reps each, timeout extended)
  Exp D  — W-WARM cold vs warm (3 reps each)
  Exp E  — TTL behavior (cold run then wait for TTL expiry and rerun)
  Exp F  — W-COL  coalescing burst (3 reps)
  Exp G  — W-CON  concurrency sweep (c=1, 5, 10, 20, 50)

Usage:
    python benchmarks/run_phase2c.py [--experiments A B C D E F G]

All output files go to benchmarks/results/.
Experiment log is appended to benchmarks/experiment_log.md.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root importable
_HERE = Path(__file__).parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_ROOT))

RESULTS_DIR = _HERE / "results"
LOG_FILE = _HERE / "experiment_log.md"

OPTIMIZER_URL = "http://127.0.0.1:8000"
MOCK_API_URL  = "http://127.0.0.1:8001"


def ts() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    line = f"[{ts()}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_benchmark(
    *,
    mode: str,
    workload: str,
    n_requests: int = 100,
    concurrency: int = 10,
    warm_up: int = 0,
    mock_delay_ms: int = 100,
    pool_size: int = 10,
    seed: int = 42,
    timeout: float = 10.0,
    repetitions: int = 1,
    results_dir: Path = RESULTS_DIR,
    label: str = "",
) -> int:
    """Run benchmark via CLI subprocess. Returns exit code."""
    cmd = [
        sys.executable,
        str(_HERE / "run_benchmark.py"),
        "--mode", mode,
        "--workload", workload,
        "--n-requests", str(n_requests),
        "--concurrency", str(concurrency),
        "--warm-up", str(warm_up),
        "--mock-delay-ms", str(mock_delay_ms),
        "--pool-size", str(pool_size),
        "--seed", str(seed),
        "--timeout", str(timeout),
        "--repetitions", str(repetitions),
        "--results-dir", str(results_dir),
        "--optimizer-url", OPTIMIZER_URL,
        "--mock-api-url", MOCK_API_URL,
    ]
    log(f"CMD: {' '.join(cmd[2:])}")  # skip python path for brevity
    t0 = time.perf_counter()
    result = subprocess.run(cmd, cwd=str(_ROOT))
    elapsed = time.perf_counter() - t0
    status = "OK" if result.returncode == 0 else f"FAILED (exit {result.returncode})"
    log(f"{label or workload}-{mode}: {status} in {elapsed:.1f}s")
    return result.returncode


def run_all_experiments(selected: List[str]) -> None:
    log("=" * 70)
    log("Phase 2C — Master Experiment Runner starting")
    log(f"Selected experiments: {selected}")
    log("=" * 70)

    # -----------------------------------------------------------------------
    # Experiment A — W-REP repeated identical
    # -----------------------------------------------------------------------
    if "A" in selected:
        log("\n--- Experiment A: Repeated identical (W-REP) ---")
        log("Control: 100 requests, concurrency=10, delay_ms=100, seed=42, 3 reps")
        log("Baseline: client -> Mock API directly (no caching)")
        run_benchmark(mode="baseline", workload="W-REP", n_requests=100,
                      concurrency=10, mock_delay_ms=100, repetitions=3,
                      label="ExpA")
        log("Optimized: client -> Optimizer proxy (cache + coalescing)")
        run_benchmark(mode="optimized", workload="W-REP", n_requests=100,
                      concurrency=10, mock_delay_ms=100, repetitions=3,
                      label="ExpA")

    # -----------------------------------------------------------------------
    # Experiment B — W-MIX mixed repeated
    # -----------------------------------------------------------------------
    if "B" in selected:
        log("\n--- Experiment B: Mixed repeated (W-MIX) ---")
        log("Control: 100 requests, pool_size=10, concurrency=10, delay_ms=100, 3 reps")
        log("NOTE: W-MIX optimized had high latency in Phase 2B due to lock serialization.")
        log("Using timeout=15s for optimized to allow legitimate completion.")
        run_benchmark(mode="baseline", workload="W-MIX", n_requests=100,
                      concurrency=10, pool_size=10, mock_delay_ms=100,
                      repetitions=3, label="ExpB")
        run_benchmark(mode="optimized", workload="W-MIX", n_requests=100,
                      concurrency=10, pool_size=10, mock_delay_ms=100,
                      timeout=15.0, repetitions=3, label="ExpB")

    # -----------------------------------------------------------------------
    # Experiment C — W-UNQ mostly unique
    # -----------------------------------------------------------------------
    if "C" in selected:
        log("\n--- Experiment C: Mostly unique (W-UNQ) ---")
        log("Control: 100 requests, each unique resource, concurrency=10, delay_ms=100")
        log("NOTE: Prior runs showed severe coalescer-lock serialization for unique keys.")
        log("Using timeout=15s for optimized. Results may show high error rates.")
        log("This is the 'optimizer adds overhead' scenario; results reported as-is.")
        run_benchmark(mode="baseline", workload="W-UNQ", n_requests=100,
                      concurrency=10, mock_delay_ms=100, repetitions=3,
                      label="ExpC")
        run_benchmark(mode="optimized", workload="W-UNQ", n_requests=100,
                      concurrency=10, mock_delay_ms=100, timeout=15.0,
                      repetitions=3, label="ExpC")

    # -----------------------------------------------------------------------
    # Experiment D — Cold vs warm cache (W-WARM)
    # -----------------------------------------------------------------------
    if "D" in selected:
        log("\n--- Experiment D: Cold vs warm cache ---")
        log("Cold: W-REP optimized without pre-population (3 reps)")
        log("Warm: W-WARM optimized with cache pre-populated (3 reps)")
        log("Control: same resource, same n_requests=100, concurrency=10")
        # Cold-cache: W-REP optimized (already no warm-up by default)
        log("D1: Cold-cache run (W-REP optimized, no warm-up)")
        run_benchmark(mode="optimized", workload="W-REP", n_requests=100,
                      concurrency=10, mock_delay_ms=100, repetitions=3,
                      label="ExpD-cold")
        # Warm-cache: W-WARM profile (pre-populates then resets counters)
        log("D2: Warm-cache run (W-WARM optimized, pre-populated)")
        run_benchmark(mode="optimized", workload="W-WARM", n_requests=100,
                      concurrency=10, mock_delay_ms=100, repetitions=3,
                      label="ExpD-warm")

    # -----------------------------------------------------------------------
    # Experiment E — TTL behavior
    # -----------------------------------------------------------------------
    if "E" in selected:
        log("\n--- Experiment E: TTL behavior ---")
        log("CACHE_TTL_SECONDS=30 (from .env). Strategy:")
        log("  E1: Single request to populate cache (1 miss).")
        log("  E2: Immediate re-request (should hit cache).")
        log("  E3: Wait 35s for TTL expiry.")
        log("  E4: Re-request (should miss cache -> new upstream call).")
        log("Using n_requests=10 for E1/E2/E4 to keep runs short.")
        # E1: Populate + E2: Immediate re-request in same W-REP run
        log("E1+E2: W-REP optimized, 10 requests (first=miss, rest=hits)")
        run_benchmark(mode="optimized", workload="W-REP", n_requests=10,
                      concurrency=1, mock_delay_ms=100, repetitions=1,
                      label="ExpE-before-ttl")
        # Wait for TTL expiry
        ttl_wait = 35
        log(f"Waiting {ttl_wait}s for TTL expiry (TTL=30s + 5s buffer)...")
        time.sleep(ttl_wait)
        log(f"TTL wait complete. Issuing post-TTL request.")
        # E4: After expiry — should miss
        run_benchmark(mode="optimized", workload="W-REP", n_requests=10,
                      concurrency=1, mock_delay_ms=100, repetitions=1,
                      label="ExpE-after-ttl")

    # -----------------------------------------------------------------------
    # Experiment F — Concurrent coalescing burst (W-COL)
    # -----------------------------------------------------------------------
    if "F" in selected:
        log("\n--- Experiment F: Concurrent coalescing burst (W-COL) ---")
        log("50 requests, all same resource, concurrency=50 (full burst), delay_ms=200ms")
        log("Expected: coalescer should reduce upstream calls. Measuring how many reach upstream.")
        log("Timeout=15s to accommodate potential serialization.")
        run_benchmark(mode="baseline", workload="W-COL", n_requests=50,
                      concurrency=50, mock_delay_ms=200, repetitions=3,
                      label="ExpF")
        run_benchmark(mode="optimized", workload="W-COL", n_requests=50,
                      concurrency=50, mock_delay_ms=200, timeout=15.0,
                      repetitions=3, label="ExpF")

    # -----------------------------------------------------------------------
    # Experiment G — Increasing concurrency (W-CON sweep)
    # -----------------------------------------------------------------------
    if "G" in selected:
        log("\n--- Experiment G: Increasing concurrency sweep (W-CON) ---")
        log("Concurrency levels: 1, 5, 10, 20, 50. Same resource, n_requests=100, delay_ms=100")
        for c in [1, 5, 10, 20, 50]:
            if c > 50:  # safety cap for local machine
                break
            log(f"G: concurrency={c}")
            run_benchmark(mode="baseline", workload="W-CON", n_requests=100,
                          concurrency=c, mock_delay_ms=100, repetitions=1,
                          label=f"ExpG-c{c}")
            run_benchmark(mode="optimized", workload="W-CON", n_requests=100,
                          concurrency=c, mock_delay_ms=100, timeout=12.0,
                          repetitions=1, label=f"ExpG-c{c}")

    log("\n" + "=" * 70)
    log("Phase 2C — All selected experiments complete.")
    log("Results saved in: benchmarks/results/")
    log("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 2C master experiment runner"
    )
    parser.add_argument(
        "--experiments", nargs="+",
        choices=["A", "B", "C", "D", "E", "F", "G"],
        default=["A", "B", "C", "D", "E", "F", "G"],
        help="Which experiments to run (default: all)",
    )
    args = parser.parse_args()
    run_all_experiments(args.experiments)


if __name__ == "__main__":
    main()
