# Phase 2A — Benchmarking Framework Design

**Project:** Intelligent API Traffic Optimizer  
**Stage:** Phase 2A — Design Only (no benchmark code written yet)  
**Date:** 2026-10-10  
**Author note:** All claims in this document are design decisions, not measurements.
No results exist yet. This document is the pre-execution design record.

---

## 1. Architecture Summary (Benchmarking-Relevant Facts)

The following is confirmed by repository inspection, not assumed from prior documentation.

### 1.1 Services

| Service | Module | Default Port | Start Command |
|---|---|---|---|
| Mock External API | `mock_api/main.py` | 8001 | `uvicorn mock_api.main:app --port 8001` |
| API Traffic Optimizer | `app/main.py` | 8000 | `uvicorn app.main:app --port 8000` |

Both are FastAPI/ASGI applications served by Uvicorn. All I/O is async (httpx, asyncio).

### 1.2 Confirmed Implemented Features

| Feature | File | Benchmarking Relevance |
|---|---|---|
| Async proxy forwarding | `app/proxy/client.py` | Core optimized path |
| Request normalization | `app/requests/normalizer.py` | Ensures cache-key correctness |
| SHA-256 cache key | `app/requests/key_generator.py` | Cache identity determination |
| In-memory TTL cache | `app/cache/manager.py`, `entry.py` | Primary optimization mechanism |
| Request coalescer | `app/requests/coalescer.py` | Concurrent-request optimization |
| Metrics collector | `app/metrics/collector.py` | Server-reported aggregate counts |
| Mock API latency control | `mock_api/config.py` | `MOCK_API_DELAY_MS` env var |
| Mock API failure rate | `mock_api/config.py` | `MOCK_API_FAILURE_RATE` env var |
| Mock API request counter | `mock_api/state.py` | Upstream call ground-truth |

### 1.3 Relevant Endpoints

**Optimizer (port 8000):**
- `GET  /proxy/data/{resource_id}[?param=val]` — optimized proxy route
- `GET  /metrics`        — aggregate: total_requests, cache_hits, cache_misses, mock_api_calls, avg_response_time_ms
- `GET  /cache/stats`    — hits, misses, hit_ratio, current_entries
- `POST /cache/clear`    — flush entries (keeps hit/miss stats)
- `POST /cache/reset`    — flush entries AND reset stats
- `POST /metrics/reset`  — reset metrics counters only

**Mock API (port 8001):**
- `GET  /api/data/{resource_id}[?delay_ms=N]` — direct upstream endpoint
- `GET  /stats`          — total_requests (ground-truth upstream counter)
- `POST /stats/reset`    — reset upstream counter

### 1.4 Configuration (`.env` / `.env.example`)

| Variable | Default | Benchmark Impact |
|---|---|---|
| `MOCK_API_URL` | `http://127.0.0.1:8001` | Must match running Mock API |
| `UPSTREAM_TIMEOUT_SECONDS` | `5.0` | Determines timeout behaviour |
| `MOCK_API_DELAY_MS` | `500` | Dominant latency driver |
| `MOCK_API_FAILURE_RATE` | `0` | Set to 0 for baseline experiments |
| `CACHE_TTL_SECONDS` | `30` | Entry lifetime; affects TTL experiment |

### 1.5 Existing `benchmark.py` (Root Level)

A simple Phase 9 script exists that sends N requests in batches of concurrency C and
prints a summary table. It does **not**:
- Save results to JSON or CSV.
- Record per-request latency distributions.
- Separate warm-up from measured requests.
- Collect P50/P95/P99.
- Record errors individually.
- Run multiple workload profiles.

It will **not** be used for Phase 2 experiments. The new `benchmarks/` module supersedes it.

### 1.6 No Bypass Route

There is no "uncached optimizer" route. The natural comparison is:
- **Baseline**: client → Mock API directly (`/api/data/{id}`)
- **Optimized**: client → Optimizer proxy (`/proxy/data/{id}`)

This is the architecturally correct comparison: it evaluates the optimizer as a whole
(normalization + cache + coalescing) against direct upstream calls.

---

## 2. Experiment Design

### 2.1 Comparison Structure

```
BASELINE path:
  Client ──GET /api/data/{id}──► Mock API (port 8001)
  ↳ No caching, no normalization, no coalescing
  ↳ Every request hits upstream

OPTIMIZED path:
  Client ──GET /proxy/data/{id}──► Optimizer (port 8000)
                                      │
                          ┌───────────┴──────────┐
                          │ Cache HIT             │ Cache MISS
                          ▼                       ▼
                     Return cached          Coalescer ──► Mock API
                     response                           (port 8001)
```

### 2.2 State Reset Protocol (per run)

Every experiment run must execute this sequence **before** issuing measured requests:

```
1. POST http://127.0.0.1:8001/stats/reset   → reset Mock API upstream counter
2. POST http://127.0.0.1:8000/cache/reset   → flush cache + reset cache stats
3. POST http://127.0.0.1:8000/metrics/reset → reset optimizer metrics
4. [Optional warm-up: issue warm_up_requests, then repeat steps 1-3]
5. Issue measured requests
6. GET  http://127.0.0.1:8000/metrics       → read aggregate server stats
7. GET  http://127.0.0.1:8001/stats         → read upstream call count
```

Warm-up requests (if any) are isolated from measured data by resetting counters again
after warm-up but before the measured phase.

### 2.3 Fairness Rules

- Same `MOCK_API_DELAY_MS` value within a paired baseline/optimized comparison.
- Same total measured request count and concurrency level per pair.
- Same resource ID distribution per pair.
- `MOCK_API_FAILURE_RATE=0` for all latency/throughput experiments.
- Failure-rate experiments documented separately.
- The optimizer's cache is explicitly reset before every cold-cache experiment.
- Warm-cache experiments pre-populate by running the workload once, resetting only
  the counters (not the cache), then running the measured phase.

---

## 3. Metric Definitions

| # | Metric | Unit | Source | Definition |
|---|---|---|---|---|
| M01 | total_client_requests | count | client-side | Number of GET requests issued during the measured phase |
| M02 | successful_responses | count | client-side | Responses with HTTP 2xx status |
| M03 | failed_responses | count | client-side | Responses with HTTP 4xx/5xx or connection error/timeout |
| M04 | error_rate | % | derived | (M03 / M01) × 100 |
| M05 | mean_latency_ms | ms | client-side | Arithmetic mean of per-request wall-clock durations |
| M06 | p50_latency_ms | ms | client-side | 50th percentile of per-request durations |
| M07 | p95_latency_ms | ms | client-side | 95th percentile of per-request durations |
| M08 | p99_latency_ms | ms | client-side | 99th percentile — only reported when M01 ≥ 100 |
| M09 | throughput_rps | req/s | client-side | M01 / total_wall_clock_duration_s |
| M10 | upstream_requests | count | Mock API `/stats` | `total_requests` after measured phase (ground truth) |
| M11 | cache_hits | count | Optimizer `/metrics` | `cache_hits` field |
| M12 | cache_misses | count | Optimizer `/metrics` | `cache_misses` field |
| M13 | cache_hit_ratio | ratio 0–1 | Optimizer `/metrics` | M11 / (M11 + M12); not meaningful for baseline path |
| M14 | upstream_reduction_pct | % | derived | (1 − M10_opt / M10_base) × 100 when M10_base > 0 |
| M15 | benchmark_duration_s | s | client-side | Wall-clock seconds for entire measured phase |
| M16 | x_cache_hit_count | count | client-side headers | Number of responses with `X-Cache: HIT` header |
| M17 | x_cache_miss_count | count | client-side headers | Number of responses with `X-Cache: MISS` header |

**Important distinctions:**
- M11 (cache_hits) and M16 (X-Cache HIT header count) should agree; discrepancy flags a bug.
- M10 (upstream_requests from Mock API) is the ground-truth upstream call count.
  The optimizer's `mock_api_calls` field (from `/metrics`) should equal M10 after reset;
  discrepancy should be documented.
- M14 is undefined when M10_base = 0 (e.g., baseline path was not run or counters were not reset).
- P99 (M08) is only computed and reported when the run contains ≥ 100 individual latency samples.

---

## 4. Workload Profiles

| ID | Name | Description | Resource pool | Warm cache? | Coalescing? |
|---|---|---|---|---|---|
| W-REP | Repeated identical | All N requests use the same resource_id and query params | 1 resource | No (cold) | Possible at high concurrency |
| W-MIX | Mixed repeated | Requests cycle through a fixed pool of K resources (K ≪ N) | 10 resources | No (cold) | No |
| W-UNQ | Mostly unique | Each request uses a distinct resource_id | N resources | No | No |
| W-WARM | Warm cache | Same as W-REP but cache is pre-populated before measured phase | 1 resource | Yes | No |
| W-COL | Concurrent coalescing | All requests issued simultaneously for same resource | 1 resource | No | Yes — primary test |
| W-CON | Concurrency sweep | W-REP repeated at concurrency C ∈ {1, 5, 10, 20, 50} | 1 resource | No | At high C |

**Scope for Phase 2B (implementation):**  
Implement W-REP, W-MIX, W-UNQ, W-WARM, W-CON.  
W-COL (coalescing verification) is a separate async-specific test; implement separately.

**Excluded from initial implementation:**  
- TTL expiration experiment (requires waiting 30+ seconds per run; add in Phase 2D if time permits).
- Failure-rate experiment (use `MOCK_API_FAILURE_RATE > 0`; separate config needed).

**Request count and concurrency:**

| Workload | Measured requests | Concurrency | Mock delay |
|---|---|---|---|
| W-REP | 100 | 10 | 100 ms |
| W-MIX | 100 | 10 | 100 ms |
| W-UNQ | 100 | 10 | 100 ms |
| W-WARM | 100 | 10 | 100 ms |
| W-CON | 100 | 1, 5, 10, 20, 50 | 100 ms |
| W-COL | 50 | 50 (all simultaneous) | 200 ms |

Rationale for `MOCK_API_DELAY_MS=100` (not the default 500 ms):
- 500 ms × 100 sequential requests = 50 seconds minimum; impractical.
- 100 ms provides measurable latency while keeping each run under ~30 seconds.
- The delay value is recorded in every result file so comparisons remain valid.

**Random seed:** `RANDOM_SEED = 42` for all workloads that shuffle or sample resource IDs.

---

## 5. Proposed Directory Structure

```
benchmarks/
├── README.md                  ← this document + usage instructions
├── run_benchmark.py           ← main entry point: runs all workloads, saves JSON
├── workloads.py               ← workload definitions and request generators
├── metrics.py                 ← latency stats (mean, P50, P95, P99), result schema
├── analyze.py                 ← reads JSON results, generates tables + charts
├── results/
│   ├── .gitkeep
│   └── run_<RUN_ID>.json      ← one file per benchmark execution (never overwritten)
└── charts/
    ├── .gitkeep
    └── <chart_name>.png       ← regenerated by analyze.py (not committed)
```

**Result file schema (per run):**

```json
{
  "run_id": "20261010T182300-W-REP-c10",
  "phase": "2B",
  "workload": "W-REP",
  "path": "optimized",
  "config": {
    "mock_api_delay_ms": 100,
    "cache_ttl_seconds": 30,
    "n_requests": 100,
    "concurrency": 10,
    "resource_pool_size": 1,
    "random_seed": 42,
    "warm_cache": false
  },
  "environment": {
    "python_version": "3.13.0",
    "platform": "Windows-11",
    "httpx_version": "0.28.1",
    "fastapi_version": "0.141.1"
  },
  "warm_up": {
    "requests": 0,
    "note": "no warm-up for cold-cache run"
  },
  "results": {
    "total_client_requests": 100,
    "successful": 98,
    "failed": 2,
    "error_rate_pct": 2.0,
    "latencies_ms": [10.2, 11.4, ...],   // all N individual measurements
    "mean_latency_ms": 12.3,
    "p50_latency_ms": 11.8,
    "p95_latency_ms": 18.4,
    "p99_latency_ms": null,              // null when n < 100
    "throughput_rps": 45.2,
    "benchmark_duration_s": 2.21,
    "x_cache_hit_count": 89,
    "x_cache_miss_count": 11
  },
  "server_metrics": {
    "optimizer": { ... },   // raw /metrics JSON after measured phase
    "cache_stats": { ... }, // raw /cache/stats JSON after measured phase
    "mock_api_stats": { ... } // raw /stats JSON after measured phase
  }
}
```

Key design decisions:
- Raw `latencies_ms` array is stored so any percentile can be recomputed from saved data.
- `p99_latency_ms` is `null` when sample size < 100 (not zero, not omitted — explicitly null).
- Server metrics are stored verbatim; analysis script derives M10–M14 from them.
- `run_id` encodes timestamp + workload + concurrency; files are never overwritten.

---

## 6. Missing Integration Points and Measurement Limitations

| # | Limitation | Impact | Mitigation |
|---|---|---|---|
| L1 | No per-request server-side timing | Can't compare client vs server latency | Record client-side only; document difference |
| L2 | No cache-bypass mode in optimizer | Can't measure "optimized path without cache hit" | Use W-UNQ (all unique IDs) as proxy for this case |
| L3 | `MOCK_API_DELAY_MS` is global, not per-resource | All resources have same upstream latency | Fixed delay is sufficient for controlled comparison |
| L4 | TestClient is synchronous; real concurrency needs live services | Concurrent coalescing can't be unit-tested easily | Use live Uvicorn processes for all Phase 2 benchmarks |
| L5 | Single-process, single-machine setup | No network overhead; results are localhost-only | Document clearly; never generalize to distributed deployments |
| L6 | `asyncio_mode=auto` in pytest conflicts with some async benchmark patterns | Benchmark runner must be a standalone script, not a pytest test | Run via `python benchmarks/run_benchmark.py` |
| L7 | Default `CACHE_TTL_SECONDS=30` means entries expire mid-run if a run takes >30 s | TTL experiment only; standard runs keep delay_ms=100 so runs are <10 s | Document TTL in result file; verify run duration < TTL |
| L8 | httpx `0.28.1` / starlette deprecation warning | Visual noise in benchmark output | Use `warnings.filterwarnings` in runner |
| L9 | No statistical test built in | Can't claim significance from a single run | Run each workload ≥ 3 times; report mean ± std across runs |
| L10 | Coalescing is asyncio-internal | Concurrent requests via `asyncio.gather` through live HTTP are subject to OS scheduler and TCP stack | Use asyncio-based HTTP client (httpx.AsyncClient) for coalescing tests |

---

## 7. Implementation Plan (ordered by dependency)

| Step | Task | Dependency | Target Phase |
|---|---|---|---|
| S1 | Write `benchmarks/metrics.py`: latency stats, result schema, JSON serializer | None | 2B |
| S2 | Write `benchmarks/workloads.py`: request generators for W-REP, W-MIX, W-UNQ | S1 | 2B |
| S3 | Write `benchmarks/run_benchmark.py`: state reset, workload dispatch, result save | S1, S2 | 2B |
| S4 | Manual smoke test: start both services, run one workload, verify JSON output | S3 | 2B |
| S5 | Run full experiment matrix (W-REP, W-MIX, W-UNQ, W-WARM, W-CON) × 3 repeats | S4 | 2C |
| S6 | Run W-COL coalescing experiment (all-concurrent, same resource) | S4 | 2C |
| S7 | Write `benchmarks/analyze.py`: load JSON, compute tables, generate charts | S5, S6 | 2D |
| S8 | Write `benchmarks/REPORT.md`: full experimental report | S7 | 2D |
| S9 | Update root `README.md` with benchmark instructions and findings | S8 | 2D |
| S10 | Final regression: run `pytest tests/` to confirm no regressions | S3 | 2D |
