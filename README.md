# Intelligent API Traffic Optimizer

> Adaptive middleware designed to reduce redundant API traffic, latency, and backend load.

`🚧 Status: Phase 3 Complete — Basic API Proxy`

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

| Phase   | Component                  | Status      |
| ------- | -------------------------- | ----------- |
| Phase 1 | Project setup & foundation | ✅ Complete  |
| Phase 1 | FastAPI foundation         | ✅ Complete  |
| Phase 1 | Mock API foundation        | ✅ Complete  |
| Phase 1 | Test environment           | ✅ Complete  |
| Phase 2 | Mock external API behavior | ✅ Complete  |
| Phase 3 | Basic API proxy            | ✅ Complete  |
| Phase 4 | Request normalization      | ⏳ Next      |
| Phase 5 | In-memory cache            | ⏳ Planned   |
| Phase 6 | TTL & cache metrics        | ⏳ Planned   |
| Phase 7 | Request deduplication      | ⏳ Planned   |
| Phase 8 | Request coalescing         | ⏳ Planned   |
| Phase 9 | Metrics & benchmarking     | ⏳ Planned   |

## Current Working Architecture

With Phase 3 complete, the Optimizer acts as a transparent proxy middleware forwarding requests to the upstream Mock API without optimization:

```text
                     CLIENT
                        │
                        │ HTTP Request (GET /proxy/data/{id})
                        ▼
              ┌────────────────────────┐
              │ Intelligent API        │
              │ Traffic Optimizer      │
              │ (Port 8000)            │
              │                        │
              │ • /health              │
              │ • /proxy/data/{id}     │
              └─────────┬──────────────┘
                        │
                        │ Asynchronous HTTP Forwarding (GET /api/data/{id})
                        ▼
              ┌────────────────────────┐
              │   Mock External API    │
              │   (Port 8001)          │
              │                        │
              │ • /health              │
              │ • /api/data/{id}       │
              │ • /stats               │
              │ • /stats/reset         │
              └─────────┬──────────────┘
                        │
                        │ Response + Headers
                        ▼
              ┌────────────────────────┐
              │ Intelligent API        │
              │ Traffic Optimizer      │
              │ (Proxy Client)         │
              └─────────┬──────────────┘
                        │
                        │ Forwarded Response
                        ▼
                     CLIENT
```

> **Note:** The proxy currently forwards requests transparently without optimization. This intentionally establishes the experimental **baseline** for future optimization phases.

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
│   ├── main.py
│   ├── proxy/
│   │   ├── __init__.py
│   │   └── client.py
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── entry.py
│   │   └── manager.py
│   ├── requests/
│   │   ├── __init__.py
│   │   ├── coalescer.py
│   │   └── normalizer.py
│   └── metrics/
│       ├── __init__.py
│       └── collector.py
│
├── mock_api/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   └── state.py
│
├── tests/
│   ├── __init__.py
│   ├── test_mock_api.py
│   ├── test_proxy.py
│   ├── test_cache.py
│   ├── test_normalizer.py
│   └── test_optimizer.py
│
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

## Running the Services

To run the complete system, start both services in separate terminal windows:

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
  GET /proxy/data/{resource_id}?delay_ms=0
  ```
  Transparently forwards request to upstream Mock API. Forwards query parameters and returns upstream JSON payload.
  - Connection failures to upstream return HTTP `502 Bad Gateway` (`{"error": "Upstream API unavailable"}`).
  - Upstream request timeouts return HTTP `504 Gateway Timeout` (`{"error": "Upstream API timeout"}`).

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
* `CACHE_TTL_SECONDS`: Reserved for future caching phases (default: `30`).

## Testing

Run the automated test suite:
```bash
pytest
```

The test suite validates:
* Project foundation and imports
* Mock API endpoints (health, resource data, stats, reset, failure mode, latency override)
* Optimizer health check
* Proxy forwarding success and payload preservation
* Correct upstream request routing and query parameter forwarding
* Upstream HTTP error propagation (e.g. 500)
* Upstream connection failure handling (502 Bad Gateway)
* Upstream timeout handling (504 Gateway Timeout)
* End-to-end integration test (Client → Optimizer → Mock API → Optimizer → Client)

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

### Phase 4 — Request Normalization
Convert logically equivalent requests into a consistent canonical representation.

### Phase 5 — In-Memory Cache
Implement:
* cache storage
* cache lookup
* cache hit
* cache miss

### Phase 6 — TTL
Implement:
* expiration
* freshness control
* TTL testing

### Phase 7 — Request Deduplication
Prevent unnecessary duplicate processing.

### Phase 8 — Request Coalescing
Multiple simultaneous requests for the same resource share one in-flight external request.

### Phase 9 — Metrics & Benchmarking
Compare:
```text
Baseline
vs.
Optimized
```
Metrics will include:
* External API calls
* Cache hit ratio
* API call reduction
* Average latency
* P95 latency
* Throughput

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
