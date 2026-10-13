# Intelligent API Traffic Optimizer

> Adaptive middleware designed to reduce redundant API traffic, latency, and backend load.

`✅ Status: prototype-v2.0 — Phase 2C Complete / Phase 2D In Progress (v1.0 Baseline Validated)`

## Project Overview

Modern applications frequently make repeated requests to APIs. Many of these requests ask for identical or nearly identical data, causing unnecessary network traffic, increased latency, and additional load on backend services.

The Intelligent API Traffic Optimizer is being developed as a middleware layer positioned between clients and external APIs.

Conceptually:

```text
Client
   │
   ▼
API Traffic Optimizer
   │
   ▼
External API
```

The optimizer will eventually analyze incoming requests and determine whether a request can be:
* served from cache
* combined with an existing in-flight request
* forwarded directly
* delayed according to priority
* retried after failure
* handled through fallback mechanisms

For the current prototype, development is intentionally incremental. The first objective was to establish a clean foundation (Phase 1), a controllable mock external API (Phase 2), and a reliable, transparent API proxy (Phase 3) before introducing optimization algorithms.

## Problem Statement

```text
Repeated API requests
        ↓
Unnecessary external calls
        ↓
More network traffic
        ↓
Higher latency
        ↓
Higher backend/API load
        ↓
Potentially higher cost
```

The project aims to investigate how middleware-level optimization can reduce this overhead while maintaining acceptable data freshness and reliability.

## Current Development Status

### Version 1 Prototype (`prototype-v1.0`) — Complete & Validated

| Phase   | Component                        | Status      |
| ------- | -------------------------------- | ----------- |
| Phase 1 | Project setup & foundation       | ✅ Complete  |
| Phase 1 | FastAPI foundation               | ✅ Complete  |
| Phase 1 | Mock API foundation              | ✅ Complete  |
| Phase 1 | Test environment                 | ✅ Complete  |
| Phase 2 | Mock external API behavior       | ✅ Complete  |
| Phase 3 | Basic API proxy                  | ✅ Complete  |
| Phase 4 | Request normalisation & cache-key generation | ✅ Complete  |
| Phase 5 | In-memory cache                  | ✅ Complete  |
| Phase 6 | TTL cache management             | ✅ Complete  |
| Phase 7 | Metrics & monitoring             | ✅ Complete  |
| Phase 8 | Request coalescing               | ✅ Complete  |
| Phase 9 | Tests & initial benchmarking     | ✅ Complete  |
| **Stabilization** | **Prototype Stabilization & Validation** | **✅ Complete — prototype-v1.0** |

### Version 2 Prototype — Performance Benchmarking & Experimental Analysis

| Phase | Component | Status |
|---|---|---|
| **Phase 2A** | **Benchmarking Framework & Protocol Design** | **✅ Complete** (`benchmarks/README.md`) |
| **Phase 2B** | **Reproducible Runner, Workloads & Metrics Engine** | **✅ Complete** (`run_benchmark.py`, 82 tests) |
| **Phase 2C** | **Controlled Performance Experiments Execution** | **✅ Complete** (`run_phase2c.py`, `summary.csv`) |
| **Phase 2D** | **Automated Analysis, Visualizations & Reporting** | **🔄 In Progress** (`analyze.py`, `REPORT.md`) |

## Current Working Architecture

With Phase 9 complete, the Optimizer normalises every incoming request, generates a deterministic SHA-256 cache key, performs an in-memory TTL cache lookup, coalesces concurrent identical requests into a single upstream call, and tracks comprehensive performance metrics. An interactive developer dashboard provides observability and real-time demonstration capabilities.

```text
                     CLIENT / BROWSER
                            │
                            ▼
               ┌─────────────────────────────┐
               │   Observability Dashboard   │
               │   (React / Vite, Port 5173) │
               └────────────┬────────────────┘
                            │
                            │ HTTP Request (GET /proxy/data/{id}?...)
                            ▼
               ┌─────────────────────────────┐
               │  Intelligent API            │
               │  Traffic Optimizer          │
               │  (Port 8000)                │
               │                             │
               │  • /health                  │
               │  • /cache/stats             │
               │  • /cache/clear             │
               │  • /cache/reset             │
               │  • /proxy/data/{id}  ──┐    │
               │  • /debug/cache-key    │    │
               └────────────────────────┼────┘
                                        │
                           ┌────────────▼────────────┐
                           │   Request Normaliser     │
                           │   normalizer.py          │
                           └────────────┬─────────────┘
                                        │
                           ┌────────────▼────────────┐
                           │   Cache-Key Generator    │
                           │   key_generator.py       │
                           └────────────┬─────────────┘
                                        │ api-cache:v1:<hex>
                                        ▼
                           ┌─────────────────────────┐
                           │     Cache Manager       │
                           │     manager.py          │
                           └────────┬────────┬───────┘
                                    │        │
                              HIT   │        │   MISS
                                    │        │
                                    ▼        ▼
                               Response  ┌─────────────────────────────┐
                                         │   Mock External API         │
                                         │   (Port 8001)               │
                                         │                             │
                                         │  • /health                  │
                                         │  • /api/data/{id}           │
                                         │  • /stats                   │
                                         │  • /stats/reset             │
                                         └─────────────┬───────────────┘
                                                       │ Response + Headers
                                                       │ (Cached if 2xx)
                                                       ▼
                                                    CLIENT
```

## Prototype Dashboard

A lightweight monitoring dashboard provides visibility into request traffic, cache behavior, API calls, latency, and system health. The dashboard communicates directly with the FastAPI optimizer and is intended primarily for experimentation and demonstration.

### Key Capabilities
- **System Health Observability**: Real-time status indicator (`● SYSTEM ONLINE` in green / `● SYSTEM OFFLINE` in red) via `GET /health`.
- **Live KPI Tracking**: Displays Total Requests, Cache Hits, Cache Misses, and External API Calls queried directly from `GET /cache/stats`.
- **Optimization Impact**: Real-time computation of **API Call Reduction (%)** and **Cache Hit Ratio (%)**.
- **Visual Request Pipeline**: Dynamic request flow diagram highlighting the exact path taken:
  - Cache Hit: Client → Optimizer → Normalizer → Cache → Instant Response
  - Cache Miss: Client → Optimizer → Normalizer → Cache → Mock API → Cache
- **Interactive Request Simulator**: Allows entering resource IDs (e.g., `weather-ahmedabad`) and sending live requests through the optimizer to observe status, headers (`X-Cache: HIT` vs `MISS`), and latency differences (e.g., 2ms vs 500ms).
- **Performance Chart**: Visual comparison of Cache Hits vs Cache Misses.
- **Recent Requests Log**: In-memory session table capturing the last 15–20 requests with timestamps, HTTP statuses, and latencies.
- **Experiment Reset**: Confirmation-backed reset that flushes in-memory cache and clears hit/miss statistics for fresh benchmark demonstrations.

### Running the System with Dashboard

**Terminal 1 — Mock External API**:
```bash
uvicorn mock_api.main:app --port 8001 --reload
```

**Terminal 2 — API Traffic Optimizer**:
```bash
uvicorn app.main:app --port 8000 --reload
```

**Terminal 3 — Frontend Dashboard**:
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

## Target Prototype Architecture

> Planned architecture — not yet implemented.

```text
                         CLIENT
                           │
                           ▼
                ┌─────────────────────┐
                │   FastAPI Optimizer │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │ Request Normalizer  │
                └──────────┬──────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ Cache Lookup │
                    └──────┬───────┘
                           │
                 ┌─────────┴─────────┐
                 │                   │
               HIT                  MISS
                 │                   │
                 ▼                   ▼
              Response       In-Flight Request
                                      │
                                      ▼
                               ┌─────────────┐
                               │  Mock API   │
                               └──────┬──────┘
                                      │
                                      ▼
                                  Cache Store
                                      │
                                      ▼
                                   Response
```
This architecture represents the intended prototype and will be implemented incrementally in future phases.

## The Core Baseline Concept

At the end of Phase 3, the baseline is established:

```text
Client Requests = External API Requests
```

Suppose 100 clients request the same resource:

```text
GET /proxy/data/weather-ahmedabad
```

In the current Phase 3 baseline:

```text
100 client requests
        ↓
100 proxy requests
        ↓
100 external API calls
```

Future phases (normalization, caching, coalescing) will attempt to optimize this relationship toward:

```text
100 client requests
        ↓
1 external API request
        ↓
100 responses
```

## Baseline Experiment

A simple verification experiment proves the 1:1 baseline:

1. Reset Mock API statistics:
   ```text
   POST http://127.0.0.1:8001/stats/reset
   ```
2. Send 5 client requests through the Optimizer proxy:
   ```text
   GET http://127.0.0.1:8000/proxy/data/weather-ahmedabad (x5)
   ```
3. Check Mock API statistics:
   ```text
   GET http://127.0.0.1:8001/stats
   ```
4. Observed relationship:
   ```text
   Client requests:   5
   External calls:    5
   ```

*(Note: Benchmark latency and throughput comparisons will be evaluated in Phase 9; no speculative numbers are reported.)*

## Technology Stack

| Technology     | Purpose                       |
| -------------- | ----------------------------- |
| Python         | Core implementation           |
| FastAPI        | HTTP API framework            |
| Uvicorn        | ASGI server                   |
| httpx          | Async HTTP client for proxy   |
| Pydantic       | Data validation/configuration |
| pytest         | Testing                       |
| pytest-asyncio | Async testing                 |
| python-dotenv  | Environment configuration     |
| Git            | Version control               |

## Project Structure

```text
intelligent-api-optimizer/
│
├── app/
│   ├── __init__.py
│   ├── main.py                    ← v0.9.0 — metrics + coalescer integrated
│   ├── proxy/
│   │   ├── __init__.py
│   │   └── client.py              ← async httpx proxy client (Phase 3)
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── entry.py               ← ✅ Phase 5/6: CacheEntry with TTL expiry
│   │   └── manager.py             ← ✅ Phase 5/6: CacheManager + TTL + stats
│   ├── requests/
│   │   ├── __init__.py
│   │   ├── normalizer.py          ← ✅ Phase 4: normalize method/path/params/headers/body
│   │   ├── key_generator.py       ← ✅ Phase 4: SHA-256 cache-key generation pipeline
│   │   └── coalescer.py           ← ✅ Phase 8: RequestCoalescer (asyncio.Future)
│   └── metrics/
│       ├── __init__.py
│       └── collector.py           ← ✅ Phase 7: MetricsCollector
│
├── mock_api/
│   ├── __init__.py
│   ├── main.py                    ← controllable mock API (Phase 2)
│   ├── config.py
│   ├── models.py
│   └── state.py
│
├── benchmarks/                    ← ✅ Phase 2: Scientific Benchmarking Framework
│   ├── README.md                  ← Phase 2A: specification & metric definitions (M01–M17)
│   ├── metrics.py                 ← Phase 2B: latency stats, P50/P95/P99, schemas
│   ├── workloads.py               ← Phase 2B: workload request generators (W-REP, W-MIX, W-UNQ, etc.)
│   ├── run_benchmark.py           ← Phase 2B: reproducible CLI benchmark runner
│   ├── run_phase2c.py             ← Phase 2C: master experiment runner
│   ├── experiment_log.md          ← Phase 2C: controlled execution log & architectural findings
│   ├── results/                   ← Phase 2C: individual run JSON/CSV records + summary.csv
│   └── charts/                    ← Phase 2D: benchmark visualization outputs
│
├── frontend/                      ← ✅ Developer Observability Dashboard (React / Vite)
│   ├── src/
│   │   ├── components/            ← MetricCard, RequestFlow, Simulator, CacheStatus, etc.
│   │   ├── pages/                 ← Dashboard.jsx
│   │   ├── services/api.js        ← backend client connector
│   │   ├── styles/index.css       ← dark-mode design system
│   │   └── App.jsx
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── README.md
│
├── tests/
│   ├── __init__.py
│   ├── test_mock_api.py           ← Phase 2 tests
│   ├── test_proxy.py              ← Phase 3 tests
│   ├── test_normalizer.py         ← Phase 4: normalizer unit tests
│   ├── test_key_generator.py      ← Phase 4: key-generation tests
│   ├── test_cache.py              ← Phase 5/6: cache + TTL expiry integration tests
│   ├── test_metrics.py            ← ✅ Phase 7: MetricsCollector unit + integration tests
│   ├── test_coalescer.py          ← ✅ Phase 8: RequestCoalescer async unit + integration
│   ├── test_benchmark_metrics.py  ← ✅ Phase 2B: benchmark metrics & workloads tests (82 tests)
│   └── test_optimizer.py          ← import smoke test
│
├── benchmark.py                   ← legacy Phase 9 smoke script (superseded by benchmarks/)
├── pytest.ini                     ← asyncio_mode = auto
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Installation & Setup

```bash
git clone <repository-url>
cd intelligent-api-optimizer
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend Dashboard Setup

```powershell
cd frontend
npm install
cd ..
```

## Running the Services

To run the complete system, start the services in separate terminal windows:

### Terminal 1 — Mock External API (Port 8001)

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn mock_api.main:app --port 8001 --reload
```

### Terminal 2 — Optimizer Proxy Application (Port 8000)

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --port 8000 --reload
```

### Terminal 3 — Developer Observability Dashboard (Port 5173)

```powershell
cd frontend
npm run dev
```

## Implemented Endpoints

### 1. Optimizer Application (`http://127.0.0.1:8000`)

* **Health Check**:
  ```text
  GET /health
  ```
  Response: `{"status": "ok"}`

* **Proxy Resource Endpoint**:
  ```text
  GET /proxy/data/{resource_id}
  GET /proxy/data/{resource_id}?city=Delhi&units=metric
  ```
  Transparently forwards request to upstream Mock API. Looks up cache key in the `CacheManager` first (Phase 5). On Cache Miss, requests upstream and caches successful (2xx) responses. Adds `X-Cache: HIT` or `X-Cache: MISS` header to response.
  - Connection failures to upstream return HTTP `502 Bad Gateway` (`{"error": "Upstream API unavailable"}`).
  - Upstream request timeouts return HTTP `504 Gateway Timeout` (`{"error": "Upstream API timeout"}`).

* **Cache Endpoints** *(Phase 5/6)*:
  ```text
  GET  /cache/stats
  POST /cache/clear
  POST /cache/reset
  ```
  Check hit ratio and live entry count, flush entries, or reset entries + stats together.

* **Metrics Endpoint** *(Phase 7)*:
  ```text
  GET  /metrics
  POST /metrics/reset
  ```
  `GET /metrics` returns a JSON snapshot of optimizer performance:
  ```json
  {
    "total_requests": 50,
    "cache_hits": 49,
    "cache_misses": 1,
    "cache_hit_ratio": 0.98,
    "mock_api_calls": 1,
    "requests_saved": 49,
    "avg_response_time_ms": 1.23
  }
  ```
  `POST /metrics/reset` zeroes all counters without affecting the cache.

* **Cache-Key Debug Endpoint** *(Phase 4 — development only)*:
  ```text
  GET /debug/cache-key?resource_id=weather&city=Delhi&units=metric
  ```
  Returns the cache key that would be generated for the given resource and query parameters, without making an upstream call. Useful for verifying that parameter-order normalisation works correctly.
  Example response:
  ```json
  {
    "resource_id": "weather",
    "query_params": "{'city': 'Delhi', 'units': 'metric'}",
    "cache_key": "api-cache:v1:7f2a9c3d...",
    "note": "Development only — remove before production deployment"
  }
  ```
  > ⚠️ Remove or restrict this endpoint before any production deployment.

* **Interactive API Docs**:
  ```text
  GET /docs
  ```
  FastAPI Swagger UI — try all endpoints from the browser.

### 2. Mock External API (`http://127.0.0.1:8001`)

* **Health Check**:
  ```text
  GET /health
  ```
  Response: `{"status": "mock-api-ok"}`

* **Resource Data Endpoint**:
  ```text
  GET /api/data/{resource_id}
  ```
  Returns deterministic payload for a given resource identifier. Supports query override `?delay_ms=...`.

* **Statistics**:
  ```text
  GET /stats
  ```
  Returns total external request counter and uptime.

* **Reset Statistics**:
  ```text
  POST /stats/reset
  ```
  Resets in-memory request counter back to `0`.

## Configuration Options

Configurable via environment variables or `.env`:
* `MOCK_API_URL`: Base URL of upstream mock API (default: `http://127.0.0.1:8001`).
* `UPSTREAM_TIMEOUT_SECONDS`: Request timeout in seconds for proxy client (default: `5.0`).
* `MOCK_API_DELAY_MS`: Default artificial upstream latency in milliseconds (default: `500`).
* `MOCK_API_FAILURE_RATE`: Simulated probabilistic failure percentage `0-100` (default: `0`).
* `CACHE_TTL_SECONDS`: How long cached entries live before expiring (default: `30` seconds). Implemented in Phase 5/6.

## Testing

### Run the full test suite

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
```

Current result: **248 tests** (166 core optimizer tests + 82 Phase 2B benchmark & workload tests).

### Run tests by phase

```powershell
# Phase 2 — Mock API
python -m pytest tests/test_mock_api.py -v

# Phase 3 — Proxy
python -m pytest tests/test_proxy.py -v

# Phase 4 — Normaliser & key generator
python -m pytest tests/test_normalizer.py tests/test_key_generator.py -v

# Phase 5/6 — Cache + TTL expiry
python -m pytest tests/test_cache.py -v

# Phase 7 — Metrics
python -m pytest tests/test_metrics.py -v

# Phase 8 — Request Coalescer
python -m pytest tests/test_coalescer.py -v

# Phase 2B — Benchmark metrics & workloads
python -m pytest tests/test_benchmark_metrics.py -v
```

## Benchmarking

The project contains two benchmarking mechanisms:
1. **Version 2 Scientific Benchmarking Framework** (`benchmarks/`) — High-precision, reproducible experimental runner with multiple workload profiles, percentiles (P50/P95/P99), error tracking, and persistent JSON/CSV logs.
2. **Phase 9 Smoke Benchmark** (`benchmark.py`) — Lightweight 50-request script for rapid local validation.

---

### 1. Version 2 Scientific Benchmarking Framework (`benchmarks/`)

Designed in **Phase 2A**, implemented in **Phase 2B**, and executed across controlled matrices in **Phase 2C**, this framework supersedes single-scenario tests by measuring the optimizer under realistic, reproducible traffic patterns.

#### Available Workload Profiles

| Workload ID | Name | Description | Concurrency | Primary Target |
|---|---|---|---|---|
| `W-REP` | Repeated Identical | All requests target the exact same resource | 10 | Cache Hit efficiency & latency reduction |
| `W-MIX` | Mixed Repeated | Requests cycle across a pool of $K=10$ resources | 10 | Realistic multi-endpoint cache behavior |
| `W-UNQ` | Mostly Unique | Each request requests a unique resource ID | 10 | Cache miss overhead & lock stress |
| `W-WARM` | Warm Cache | Workload executed after pre-populating cache | 10 | Pure cache lookup performance |
| `W-COL` | Concurrent Coalescing | All requests launched simultaneously | 50 | In-flight request deduplication |
| `W-CON` | Concurrency Sweep | `W-REP` across varying concurrency levels | 1, 5, 10, 20, 50 | Scalability & queueing behavior |

#### Prerequisites

Both services must be running:
- Mock External API on `http://127.0.0.1:8001`
- Optimizer Proxy on `http://127.0.0.1:8000`

#### Running Individual Benchmarks (`benchmarks/run_benchmark.py`)

```powershell
# Optimized path (through optimizer proxy)
python benchmarks/run_benchmark.py --mode optimized --workload W-REP --n-requests 100 --concurrency 10

# Baseline path (direct Mock API calls)
python benchmarks/run_benchmark.py --mode baseline --workload W-REP --n-requests 100 --concurrency 10
```

#### Running Full Controlled Experiment Matrices (`benchmarks/run_phase2c.py`)

To run the automated suite executing 3 repetitions each of `W-REP`, `W-MIX`, and `W-UNQ` across both baseline and optimized paths:

```powershell
python benchmarks/run_phase2c.py
```

#### Output Artifacts & Persistence

Every execution automatically resets server state (`/stats/reset`, `/cache/reset`, `/metrics/reset`) and writes structured outputs to `benchmarks/results/`:
- `run_<TIMESTAMP>-<WORKLOAD>-<MODE>-c<CONCURRENCY>.json`: Full latency distribution, individual sample timings, server metrics snapshots, and environment details.
- `run_<TIMESTAMP>-<WORKLOAD>-<MODE>-c<CONCURRENCY>.csv`: Per-run tabular metrics.
- `summary.csv`: Cumulative log appending all benchmark executions.
- `benchmarks/experiment_log.md`: Detailed audit log of execution runs and observations.

#### Key Phase 2C Empirical Findings

1. **Upstream Call Reduction**: Under `W-REP`, the optimizer achieved a **90% cache hit ratio**, reducing upstream calls by 90% and protecting backend infrastructure.
2. **Coalescer Lock Serialization Discovery**: Testing with `W-UNQ` under high concurrency uncovered that `RequestCoalescer`'s global `asyncio.Lock` serializes leader registrations during cache misses even when keys are independent. Documented in [experiment_log.md](file:///c:/Documents/API_Traffic_Optimizer/benchmarks/experiment_log.md) as a key architectural insight driving planned v2.1 per-key lock striping.

---

### 2. Legacy Phase 9 Smoke Script (`benchmark.py`)

A quick, 50-request CLI comparison over concurrency 10:

```powershell
.venv\Scripts\python.exe benchmark.py
```

Sample output:
```text
==============================================================
  API Traffic Optimizer -- Phase 9 Benchmark Results
==============================================================
  Metric                         Direct Mock API    Via Optimizer
  ------------------------------------------------------------
  Total Requests                          50                50
  Elapsed Time (s)                    5.041s             2.214s
  Avg Latency (ms)                  500.83ms           220.27ms
  Mock API Calls                          50                 1
  Cache Hit Ratio                        N/A            98.00%
  Requests Saved                         N/A                49
  ------------------------------------------------------------
  Optimizer avg latency speedup:  2.27x
==============================================================
```

### What the test suite validates

**Phase 2 — Mock API** (`test_mock_api.py`)
* Health check endpoint
* Resource data endpoint and deterministic payload
* Request counter increment
* Statistics reset
* Deterministic failure mode (`fail-test`)
* Latency override via `?delay_ms=`

**Phase 3 — Proxy** (`test_proxy.py`)
* Proxy forwarding success and payload preservation
* Correct upstream resource routing
* Query parameter forwarding
* Upstream HTTP error propagation (500)
* Upstream connection failure (502 Bad Gateway)
* Upstream timeout handling (504 Gateway Timeout)
* End-to-end integration test (Client → Optimizer → Mock API → Client)

**Phase 4 — Normaliser** (`test_normalizer.py`)
* Method normalisation (lowercase → uppercase, whitespace stripping)
* Path normalisation (leading slash, empty path, case preservation)
* Query-parameter sorting (alphabetical, stable repeated-param order)
* Header filtering (selected keys only, Authorization always excluded)
* Body canonicalisation (JSON sort_keys, bytes decode, None handling)

**Phase 4 — Cache-Key Generator** (`test_key_generator.py`)
* Same request → same key (determinism)
* Reversed query-param order → same key
* All 6 orderings of 3 params → same key
* Different query values → different keys
* Different HTTP methods → different keys
* Different paths → different keys
* Empty and None params treated consistently
* Repeated params — safe conservative ordering
* Equivalent JSON bodies → same key
* Different JSON body values → different keys
* Selected headers affect key; non-selected headers do not
* Authorization never included in key
* Key format: `api-cache:v1:<64-char SHA-256 hex>`
* Key contains no raw path or param values

**Phase 5 & 6 — Cache & TTL Management** (`test_cache.py`)
* `CacheEntry` dataclass instantiation and expiration (`is_expired()`) logic with mocked time
* `CacheManager` unit tests: get/set/delete/exists/clear/reset flow
* `CacheManager` TTL correctness: entry naturally expires and is deleted on access
* `CacheManager` statistics calculations (total requests, hits, misses, hit ratio)
* Zero-division avoidance logic for hit ratio
* Proxy integration: First request results in `X-Cache: MISS` + upstream call
* Proxy integration: Second request results in `X-Cache: HIT` + no upstream call
* Proxy integration: Upstream 5xx errors are verified to bypass caching
* Observability endpoints: `/cache/stats`, `/cache/clear`, and `/cache/reset` correctness

**Phase 7 — Performance Metrics** (`test_metrics.py`)
* `MetricsCollector` counter increments for total requests, hits, misses, mock API calls, saved requests
* Dynamic calculation of hit ratio and running mean latency
* `GET /metrics` and `POST /metrics/reset` endpoint behavior

**Phase 8 — Request Coalescing** (`test_coalescer.py`)
* Concurrent identical requests collapsed into a single upstream invocation
* Follower propagation of leader response data and status codes
* Upstream exception propagation to all in-flight waiters
* Clean teardown of in-flight future table on completion or failure

**Phase 2B — Benchmark Metrics & Workloads** (`test_benchmark_metrics.py`)
* Arithmetic mean, min, max, and duration computations
* P50, P95, and P99 percentile interpolation accuracy
* P99 sample threshold constraint ($N \ge 100$)
* Derived metrics: error rate %, throughput RPS, upstream reduction %
* Deterministic workload generation with fixed random seed ($42$)
* Serialization and schema compliance for JSON and CSV exports

## Development Roadmap

### Phase 1 — Foundation ✅
* Python environment & project structure
* FastAPI application & Mock API foundation
* Test environment & Git configuration

### Phase 2 — Mock External API ✅
* Deterministic resource endpoint (`/api/data/{resource_id}`)
* Configurable artificial latency (`MOCK_API_DELAY_MS` / query override)
* Deterministic (`fail-test`) and probabilistic failure modes
* In-memory request counter and observability endpoints (`/stats`, `/stats/reset`)
* Request ID generation and lightweight request logging

### Phase 3 — Basic API Proxy ✅
* Asynchronous proxy client (`app/proxy/client.py`) using `httpx.AsyncClient`
* Transparent proxy route (`GET /proxy/data/{resource_id}`)
* Upstream status code, error, and timeout preservation
* Query parameter forwarding
* Baseline verification: 1:1 client-to-external request relationship

### Phase 4 — Request Normalisation & Cache-Key Generation ✅

---

#### Objective

Build a reliable, deterministic cache-key generation component that produces the **same key for logically equivalent requests** and **different keys for meaningfully different requests**, regardless of superficial formatting differences such as query-parameter order.

This is a prerequisite for Phase 5. Without a stable key, the cache cannot determine whether a stored response can serve a new incoming request.

---

#### What Is a Cache Key?

A cache key is a unique string identifier for a specific logical API request. It answers the question: *"Have I seen this exact request before?"*

The key must be:

| Property | Why it matters |
|---|---|
| **Deterministic** | Same input always produces the same key |
| **Stable** | Does not change between process restarts |
| **Collision-resistant** | Different inputs must produce different keys |
| **Order-independent** | `?a=1&b=2` and `?b=2&a=1` must yield the same key |
| **Value-sensitive** | `?city=Delhi` and `?city=Mumbai` must yield different keys |

---

#### Why Is Cache-Key Generation Necessary?

Without proper normalisation, the same logical request can appear as different strings, causing the cache to miss entries that should have been hits.

**Problem A — Query-parameter order**

```text
GET /weather?city=Delhi&units=metric
GET /weather?units=metric&city=Delhi
```

These are semantically identical. A naive string comparison would treat them as different requests and create two separate cache entries — wasting memory and making an unnecessary upstream call.

**Problem B — Different values**

```text
GET /weather?city=Delhi
GET /weather?city=Mumbai
```

These must produce different keys. A cache hit for Delhi must never be served for a Mumbai request.

**Problem C — Different HTTP methods**

```text
GET  /users/10   → reads a user record
POST /users/10   → may modify or create a record
```

Same path, completely different semantics. They must have different keys.

**Problem D — JSON body key order**

```json
{ "user_id": 10, "currency": "INR" }
{ "currency": "INR", "user_id": 10 }
```

Logically identical JSON objects. A canonical serialiser ensures they produce the same key.

---

#### New Files

| File | Responsibility |
|---|---|
| `app/requests/normalizer.py` | Low-level helpers — clean individual request components |
| `app/requests/key_generator.py` | Pipeline — assemble, serialise, hash, return final key |
| `tests/test_normalizer.py` | 37 unit tests for all five normalisation helpers |
| `tests/test_key_generator.py` | 43 tests covering all 10 spec examples + format + regression |

`app/main.py` was updated to version `0.4.0`:
- Imports `generate_key_from_request` and calls it at the start of every proxy request.
- Logs the generated key at `INFO` level.
- Adds the `/debug/cache-key` development endpoint.

---

#### Normalisation Rules (`app/requests/normalizer.py`)

Five helper functions, each handling one request component:

**1. `normalize_method(method)`**

Converts the HTTP method to uppercase and strips whitespace.

```text
"get"  → "GET"
"Post" → "POST"
```

*Rationale:* HTTP methods are case-insensitive per RFC 7231, but must be consistent in the key.

---

**2. `normalize_path(path)`**

Ensures a leading slash, strips surrounding whitespace, preserves case, preserves trailing slashes.

```text
"weather"   → "/weather"
""          → "/"
"/Weather"  → "/Weather"   ← case preserved
```

*Rationale:* Paths are case-sensitive. Lowercasing would be incorrect. Trailing slashes are preserved because FastAPI routing may treat `/weather` and `/weather/` as different routes.

---

**3. `normalize_query_params(params)`**

Sorts query-parameter pairs alphabetically by name. Uses Python's stable sort so that repeated parameter names (e.g. `id=1&id=2`) preserve their original relative order.

```text
[("units", "metric"), ("city", "Delhi")]
→ [("city", "Delhi"), ("units", "metric")]
```

For repeated parameters:

```text
[("b", "B"), ("a", "1"), ("a", "2")]
→ [("a", "1"), ("a", "2"), ("b", "B")]
```

*Rationale:* Some APIs treat `id=1&id=2` and `id=2&id=1` as different. Preserving relative order is the safe default.

---

**4. `normalize_headers(headers, include_keys)`**

Selectively includes only headers explicitly listed in `include_keys`. All other headers are discarded. Header keys in the result are lowercased.

`Authorization` is **always excluded** regardless of `include_keys`, to prevent tokens from appearing in logs or being used as dict keys.

```text
{"Accept": "application/json", "User-Agent": "curl"}
include_keys=["accept"]
→ {"accept": "application/json"}
```

*Rationale:* Most headers (User-Agent, Accept-Encoding, Connection) change frequently but do not affect the API response. Including them causes cache fragmentation.

---

**5. `normalize_body(body)`**

Converts the request body to a deterministic string.

| Input type | Output |
|---|---|
| `None` | `None` |
| `dict` or `list` | `json.dumps(sort_keys=True, separators=(",",":"))` |
| `str` | returned as-is |
| `bytes` (UTF-8) | decoded to string |
| `bytes` (binary) | hex representation |

```python
normalize_body({"user_id": 10, "currency": "INR"})
→ '{"currency":"INR","user_id":10}'

normalize_body({"currency": "INR", "user_id": 10})
→ '{"currency":"INR","user_id":10}'   # identical
```

*Rationale:* JSON object keys have no guaranteed insertion order. `sort_keys=True` makes logically equivalent dicts produce the same serialised string.

---

#### Key-Generation Pipeline (`app/requests/key_generator.py`)

```text
Incoming Request
       │
       ▼
normalize_method()      →  "GET"
normalize_path()        →  "/weather"
normalize_query_params()→  [["city","Delhi"],["units","metric"]]
normalize_headers()     →  {}
normalize_body()        →  null
       │
       ▼
_build_canonical_request()
       │
       ▼
{
  "method":  "GET",
  "path":    "/weather",
  "query":   [["city","Delhi"],["units","metric"]],
  "headers": {},
  "body":    null
}
       │
       ▼
json.dumps(sort_keys=True, separators=(",",":"))
       │
       ▼
'{"body":null,"headers":{},"method":"GET","path":"/weather","query":[["city","Delhi"],["units","metric"]]}'
       │
       ▼
hashlib.sha256(...).hexdigest()
       │
       ▼
"7f2a9c3d..."   (64-character lowercase hex)
       │
       ▼
"api-cache:v1:7f2a9c3d..."   (final cache key)
```

---

#### Key Format

```text
api-cache:v1:<64-character SHA-256 hex digest>
```

Example:

```text
api-cache:v1:7f2a9c3db1e4f28a95c06d3e17b2a4f8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4
```

**Why SHA-256 instead of Python's `hash()`?**

Python's built-in `hash("hello")` is randomised per process (PYTHONHASHSEED). The same string produces different values in different runs. SHA-256 always produces the same output for the same input, across any machine, any run, forever.

**Why the `v1:` prefix?**

If the normalisation algorithm changes in Phase 6 (e.g., headers are now included), all existing stored keys become stale. By prefixing `v1:`, a simple bump to `v2:` invalidates all old entries automatically — no manual cache flush required.

---

#### Concrete Examples

**Example 1 — Same request, same key**

```text
GET /weather?city=Delhi&units=metric   →  api-cache:v1:XXXX
GET /weather?city=Delhi&units=metric   →  api-cache:v1:XXXX  ✅ identical
```

**Example 2 — Reversed param order, same key**

```text
GET /weather?city=Delhi&units=metric   →  api-cache:v1:XXXX
GET /weather?units=metric&city=Delhi   →  api-cache:v1:XXXX  ✅ identical
```

**Example 3 — Different value, different key**

```text
GET /weather?city=Delhi    →  api-cache:v1:XXXX
GET /weather?city=Mumbai   →  api-cache:v1:YYYY  ✅ different
```

**Example 4 — Different method, different key**

```text
GET  /users?id=10   →  api-cache:v1:XXXX
POST /users?id=10   →  api-cache:v1:YYYY  ✅ different
```

**Example 5 — Equivalent JSON bodies, same key**

```text
POST /convert  body={"user_id":10,"currency":"INR"}   →  api-cache:v1:XXXX
POST /convert  body={"currency":"INR","user_id":10}   →  api-cache:v1:XXXX  ✅ identical
```

**Example 6 — Different JSON value, different key**

```text
POST /convert  body={"currency":"INR"}   →  api-cache:v1:XXXX
POST /convert  body={"currency":"USD"}   →  api-cache:v1:YYYY  ✅ different
```

---

#### Time Complexity

| Operation | Complexity | Notes |
|---|---|---|
| `normalize_method` | O(n) | n = method string length |
| `normalize_path` | O(n) | n = path string length |
| `normalize_query_params` | O(k log k) | k = number of query params |
| `normalize_body` | O(m) | m = body size |
| `json.dumps` | O(m) | m = canonical dict size |
| `sha256` | O(m) | m = serialised string length |

The overall complexity is **O(k log k + m)**, dominated by query-parameter sorting. In practice the bottleneck is always network I/O on upstream API calls, not any of these in-memory operations.

---

#### Security & Correctness Considerations

| Concern | How it is handled |
|---|---|
| **Cache poisoning** | Strict normalisation ensures two different URLs cannot share a key |
| **Authorization tokens** | Explicitly excluded from key and never written to logs |
| **Sensitive body data** | Only a short prefix of the key is logged, not the raw request |
| **Hash collisions** | SHA-256 has 2²⁵⁶ possible outputs; collisions are astronomically unlikely |
| **User-specific responses** | MVP scope is public GET requests only; private data isolation is deferred to Phase 5 |
| **Algorithm changes** | Version prefix `v1:` allows safe migration to updated key formats |

---

#### What Phase 4 Does NOT Implement

The following are intentionally deferred:

* Cache storage or retrieval — Phase 5
* TTL or expiry — Phase 6
* LRU eviction — Phase 6
* Request coalescing — Phase 8
* Distributed cache — future phase
* Full HTTP Cache-Control semantics — future phase
* Adaptive or ML-based caching decisions — future phase

---

#### Integration Point in `app/main.py`

```python
# Every incoming proxy request now does this before calling upstream:
cache_key = generate_key_from_request(
    resource_id=resource_id,
    query_params=query_params if query_params else None,
)
logger.info("[OPTIMIZER] Cache key (Phase 4): %s", cache_key)

# Phase 5 will insert:
#   cached = cache_manager.get(cache_key)
#   if cached:
#       return cached_response
# here, between key generation and the upstream call.
```

---

#### Test Coverage Summary

| Test file | Tests | What is verified |
|---|---|---|
| `test_normalizer.py` | 37 | All five normalisation helpers, edge cases, type handling |
| `test_key_generator.py` | 43 | All 10 spec examples, key format, regression, convenience wrapper |
| **Total Phase 4** | **80** | — |
| **Full suite** | **108** | Zero failures |

### Phase 5 — In-Memory Cache ✅
* In-memory cache storage using `CacheManager` and `CacheEntry` dataclass
* Cache lookup using deterministic SHA-256 cache key before upstream dispatch
* Cache hit: immediate return with `X-Cache: HIT` header without upstream call
* Cache miss: upstream dispatch, storage of 2xx responses with `X-Cache: MISS` header
* Error responses (4xx, 5xx) strictly bypass caching
* Observability endpoints: `GET /cache/stats`, `POST /cache/clear`, and `POST /cache/reset`

### Phase 6 — TTL & Cache Expiry ✅
* Monotonic clock timestamping (`time.monotonic()`) preventing system clock drift issues
* Per-entry TTL validation (`entry.is_expired()`) with lazy eviction on lookup
* Configurable expiration window via `CACHE_TTL_SECONDS` (default: 30s)

### Phase 7 — Metrics & Monitoring ✅
* Server-side `MetricsCollector` tracking real-time traffic statistics
* Aggregate counts: `total_requests`, `cache_hits`, `cache_misses`, `mock_api_calls`, `requests_saved`
* Running mean latency (`avg_response_time_ms`) and cache hit ratio calculations
* Endpoints: `GET /metrics` snapshot and `POST /metrics/reset`

### Phase 8 — Request Coalescing ✅
* `RequestCoalescer` using `asyncio.Future` dictionary table
* Deduplicates simultaneous identical requests targeting the same cache key
* Leader-follower pattern: first request fetches from upstream, subsequent concurrent requests wait and receive the leader's response
* Robust cleanup on success, timeout, or upstream exceptions

### Phase 9 — Tests & Baseline Benchmarking ✅
* End-to-end test suite and initial smoke benchmark (`benchmark.py`)
* React / Vite developer observability dashboard (`frontend/` on Port 5173)
* Demonstrated 2.3x latency improvement on repeated sequential requests

---

## Version 2 Prototype — Performance Benchmarking & Experimental Analysis

Building upon the validated v1.0 baseline, Version 2 focuses on scientific, reproducible performance evaluation across multi-workload stress testing.

### Phase 2A — Framework & Protocol Design ✅
* Defined 17 formal benchmark metrics (**M01–M17**) including P50, P95, P99, error rates, and throughput
* Standardized state-reset protocol (`/stats/reset` → `/cache/reset` → `/metrics/reset`)
* Designed 6 workload profiles (`W-REP`, `W-MIX`, `W-UNQ`, `W-WARM`, `W-COL`, `W-CON`)
* Full specification recorded in [benchmarks/README.md](file:///c:/Documents/API_Traffic_Optimizer/benchmarks/README.md)

### Phase 2B — Benchmark Runner Implementation & Metrics Engine ✅
* Async multi-concurrency benchmark runner CLI ([benchmarks/run_benchmark.py](file:///c:/Documents/API_Traffic_Optimizer/benchmarks/run_benchmark.py))
* Mathematical metrics engine ([benchmarks/metrics.py](file:///c:/Documents/API_Traffic_Optimizer/benchmarks/metrics.py))
* Deterministic workload generators with fixed seed ([benchmarks/workloads.py](file:///c:/Documents/API_Traffic_Optimizer/benchmarks/workloads.py))
* Comprehensive test suite ([tests/test_benchmark_metrics.py](file:///c:/Documents/API_Traffic_Optimizer/tests/test_benchmark_metrics.py)) adding 82 tests

### Phase 2C — Controlled Performance Experiments Execution ✅
* Master automated experiment runner ([benchmarks/run_phase2c.py](file:///c:/Documents/API_Traffic_Optimizer/benchmarks/run_phase2c.py))
* Matrix execution across `W-REP`, `W-MIX`, and `W-UNQ` with 3 repetitions per scenario
* Structured JSON/CSV run records stored in `benchmarks/results/` and appended to `summary.csv`
* Documented findings in [benchmarks/experiment_log.md](file:///c:/Documents/API_Traffic_Optimizer/benchmarks/experiment_log.md)
* Identified key architectural insight regarding coalescer lock serialization under high-concurrency unique cache misses

### Phase 2D — Performance Analysis, Visualizations & Reporting 🔄
* Automated results analysis script (`benchmarks/analyze.py`)
* Comparative latency distribution and throughput visualizations (`benchmarks/charts/`)
* Comprehensive experimental report (`benchmarks/REPORT.md`)

## Benchmarking Philosophy

The project will not assume that an optimization is effective simply because it sounds theoretically useful. Each optimization will be evaluated experimentally:

```text
Baseline
   ↓
Measure
   ↓
Implement optimization
   ↓
Measure again
   ↓
Compare
```
Without establishing the Phase 3 baseline, we cannot meaningfully claim that caching or request coalescing improves the system.

## Future Extensions
* LRU cache
* Redis-backed distributed cache
* Adaptive TTL
* Request priority scheduling
* Token-bucket rate limiting
* Retry engine
* Exponential backoff
* Circuit breaker
* Stale-while-revalidate
* Real-time monitoring dashboard
* Load testing
* Advanced optimization policies

## Engineering Principles
* **Measure before optimizing**
* **Establish a clear baseline first**
* **Keep the prototype simple**
* **Separate components by responsibility**
* **Prefer asynchronous I/O**
* **Make optimization decisions measurable**
* **Do not over-engineer early**
* **Benchmark every major optimization**
* **Keep the system explainable**

## Project Philosophy

> **Simple interface, sophisticated core.**

The external client should not need to understand the optimizer. The optimizer behaves as transparent middleware between the client and the external service while internally applying increasingly sophisticated traffic-management strategies.

## What This Project Demonstrates

* Backend engineering
* HTTP/REST architecture & reverse proxy design
* Asynchronous programming
* Caching & coalescing
* Concurrency management
* Distributed-systems concepts
* Performance engineering & benchmarking
* System design & observability

---

## Prototype Stabilization — Validation Summary

> Completed as part of the post-prototype Phase 1 Stabilization effort.

### Validated Features

All of the following were confirmed by the automated test suite (166 tests, 0 failures):

| Feature | Validation Status |
|---|---|
| Mock API health, resource, stats, reset, failure endpoints | ✅ PASS |
| Proxy forwarding, error handling (502/504), no stack-trace leaks | ✅ PASS |
| Request normalization (method, path, params, headers, body) | ✅ PASS |
| Cache-key generation (determinism, collision avoidance, SHA-256 format) | ✅ PASS |
| Cache miss → upstream call → store | ✅ PASS |
| Cache hit → no upstream call | ✅ PASS |
| TTL expiration → re-fetch (clock patched in tests) | ✅ PASS |
| Failed upstream not cached; next request retries | ✅ PASS |
| Request coalescing: N concurrent identical → 1 upstream call | ✅ PASS |
| Coalescer cleanup on success and failure | ✅ PASS |
| Metrics accuracy (hits, misses, ratio, mock_api_calls, avg_latency) | ✅ PASS |
| CORS headers (allow-origin, expose X-Cache) | ✅ PASS |
| End-to-end in-process integration test | ✅ PASS |

### Bugs Fixed During Stabilization

| # | Defect | Fix |
|---|---|---|
| 1 | `asyncio.get_event_loop()` deprecated in Python 3.10+; raises in 3.12+ | Changed to `asyncio.get_running_loop()` in `coalescer.py` |
| 2 | "Future exception was never retrieved" spurious stderr noise | Added `future.exception()` after `set_exception()` in coalescer leader path |
| 3 | `node_modules/` not in `.gitignore` | Added `node_modules/` entry to `.gitignore` |

### Known Limitations

- **No true concurrent HTTP-level coalescing test**: `TestClient` is synchronous; concurrent coalescing is validated only at the async unit level and via `benchmark.py` (requires live services).
- **`httpx`/Starlette deprecation advisory**: Starlette's `TestClient` recommends `httpx2`. Not upgraded in this phase to avoid dependency churn.
- **`debug/cache-key` endpoint**: Exposes key-generation details without authentication. Appropriate for a development prototype; must be removed before any production deployment.
- **No persistence**: Cache and metrics state are in-memory only. Restarting the optimizer resets everything.
- **Single-process only**: No Redis, no distributed caching, no horizontal scaling.

### Release Identifiers & Milestone Progression

* **`prototype-v1.0`** — Stabilized & validated baseline release (Phase 1–9 complete, 166 core tests passing).
* **`prototype-v2.0`** — Active performance benchmarking & experimental evaluation release:
  * **Phase 2A**: Framework & protocol design complete ([benchmarks/README.md](file:///c:/Documents/API_Traffic_Optimizer/benchmarks/README.md))
  * **Phase 2B**: Runner CLI & metrics engine implemented, 82 tests added ([tests/test_benchmark_metrics.py](file:///c:/Documents/API_Traffic_Optimizer/tests/test_benchmark_metrics.py))
  * **Phase 2C**: Controlled experiments executed across `W-REP`, `W-MIX`, `W-UNQ` ([benchmarks/experiment_log.md](file:///c:/Documents/API_Traffic_Optimizer/benchmarks/experiment_log.md), [benchmarks/results/summary.csv](file:///c:/Documents/API_Traffic_Optimizer/benchmarks/results/summary.csv))
  * **Phase 2D**: Analysis, visualizations, and comprehensive experimental report (in progress)

### Immediate Next Milestone

**Phase 2D — Automated Analysis, Visualizations & Reporting**

- Implement automated analysis script (`benchmarks/analyze.py`) to parse and tabulate `benchmarks/results/*.json`.
- Generate comparative latency distribution and throughput charts (`benchmarks/charts/`).
- Publish consolidated experimental report (`benchmarks/REPORT.md`) detailing caching speedups, upstream load reduction, and coalescer concurrency characteristics.

