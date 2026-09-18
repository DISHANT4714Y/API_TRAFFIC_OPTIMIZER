# Intelligent API Traffic Optimizer

> Adaptive middleware designed to reduce redundant API traffic, latency, and backend load.

`🚧 Status: Phase 2 Complete — Mock External API`

## Project Overview

Modern applications frequently make repeated requests to APIs. Many of these requests may ask for identical or nearly identical data, causing unnecessary network traffic, increased latency, and additional load on backend services.

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
* combined with an existing request
* forwarded directly
* delayed according to priority
* retried after failure
* handled through fallback mechanisms

For the current prototype, development is intentionally incremental. The first objective is to establish a clean foundation and a realistic, controllable mock external API before implementing optimization algorithms.

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
| Phase 1 | Project setup              | ✅ Complete  |
| Phase 1 | FastAPI foundation         | ✅ Complete  |
| Phase 1 | Mock API foundation        | ✅ Complete  |
| Phase 1 | Test environment           | ✅ Complete  |
| Phase 2 | Mock external API behavior | ✅ Complete  |
| Phase 3 | API proxy                  | ⏳ Next      |
| Phase 4 | Request normalization      | ⏳ Planned   |
| Phase 5 | In-memory cache            | ⏳ Planned   |
| Phase 6 | TTL & cache metrics        | ⏳ Planned   |
| Phase 7 | Request deduplication      | ⏳ Planned   |
| Phase 8 | Request coalescing         | ⏳ Planned   |
| Phase 9 | Benchmarking               | ⏳ Planned   |

## Current Architecture

With Phase 2 complete, the Mock API provides a realistic, slow external service with configurable latency, deterministic failure simulation, request logging, and observability counters:

```text
                    CLIENT
                       │
                       ▼
              ┌────────────────────────┐
              │   Mock External API    │
              │   (Port 8001)          │
              │                        │
              │ • /health              │
              │ • /api/data/{id}       │
              │ • /stats               │
              │ • /stats/reset         │
              └────────────────────────┘

              ┌────────────────────────┐
              │   FastAPI App (Proxy)  │
              │   (Port 8000)          │
              │                        │
              │ • /health              │
              └────────────────────────┘
```

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

## The Core Idea

Suppose 100 clients request the same resource:

```text
GET /weather?city=Ahmedabad
```

Without optimization:

```text
100 client requests
        ↓
100 external API calls
```

The eventual optimizer should aim for:

```text
100 client requests
        ↓
1 external API request
        ↓
100 responses
```

This is the fundamental behavior that later features such as caching and request coalescing will investigate. *(Planned prototype behavior, not a current result)*

## Technology Stack

| Technology     | Purpose                       |
| -------------- | ----------------------------- |
| Python         | Core implementation           |
| FastAPI        | HTTP API framework            |
| Uvicorn        | ASGI server                   |
| httpx          | Async HTTP client             |
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
│   ├── test_cache.py
│   ├── test_normalizer.py
│   └── test_optimizer.py
│
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Installation

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

## Running the Backend

```bash
uvicorn app.main:app --reload
```

Backend:
`http://127.0.0.1:8000`

Health endpoint:
```text
GET /health
```

Expected response:
```json
{
  "status": "ok"
}
```

## Running the Mock External API

```bash
uvicorn mock_api.main:app --port 8001 --reload
```

Mock API:
`http://127.0.0.1:8001`

### Endpoints Implemented

#### 1. Health Check
```text
GET /health
```
Response:
```json
{
  "status": "mock-api-ok"
}
```

#### 2. Resource Data Endpoint
```text
GET /api/data/{resource_id}
GET /api/data/{resource_id}?delay_ms=100
```
Response:
```json
{
  "resource_id": "weather-ahmedabad",
  "data": {
    "temperature": 30,
    "condition": "clear",
    "details": "Data payload for weather-ahmedabad"
  },
  "served_at": "2026-09-18T19:18:00.306701+00:00",
  "request_id": "mock-000001"
}
```
* Response Headers: `X-Request-Id: mock-000001`, `X-Mock-Delay-Ms: 500`
* Deterministic Failure Mode: Requesting `GET /api/data/fail-test` returns HTTP 500 (`"Simulated external API failure"`).

#### 3. Observability Statistics
```text
GET /stats
```
Response:
```json
{
  "total_requests": 5,
  "uptime_seconds": 12.45
}
```

#### 4. Reset Statistics
```text
POST /stats/reset
```
Response:
```json
{
  "status": "reset",
  "total_requests": 0
}
```

### Configuration Options
Configurable via environment variables (or `.env`):
* `MOCK_API_DELAY_MS`: Default artificial latency in milliseconds (default: `500`).
* `MOCK_API_FAILURE_RATE`: Simulated probabilistic failure percentage `0-100` (default: `0`).

## Testing

Run the test suite:
```bash
pytest
```

The test suite validates:
* Project foundation and import resolution
* Mock API health check (`/health`)
* Resource payload structure and deterministic behavior (`/api/data/{resource_id}`)
* In-memory request counter tracking
* Statistics reset endpoint (`/stats/reset`)
* Deterministic failure triggering (`/api/data/fail-test`)
* Latency override configuration

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

### Phase 3 — Basic API Proxy
Planned:
```text
Client
   ↓
Optimizer
   ↓
Mock API
```

### Phase 4 — Request Normalization
Convert logically equivalent requests into a consistent representation.

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
This will be one of the important prototype features. Multiple simultaneous requests for the same resource should ideally share one in-flight external request.

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

*(Note: Benchmark numbers will be measured experimentally in Phase 9; no speculative numbers are reported.)*

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
This is an essential engineering principle of the project.

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
* **Keep the prototype simple**
* **Separate components by responsibility**
* **Prefer asynchronous I/O**
* **Make optimization decisions measurable**
* **Do not over-engineer early**
* **Benchmark every major optimization**
* **Keep the system explainable**

## Project Philosophy

> **Simple interface, sophisticated core.**

The external client should not need to understand the optimizer. The optimizer should behave as middleware between the client and the external service while internally applying increasingly sophisticated traffic-management strategies.

## What This Project Demonstrates

* Backend engineering
* HTTP/REST architecture
* Asynchronous programming
* Caching
* Concurrency
* Request deduplication
* Distributed-systems concepts
* Performance engineering
* Load testing
* System design
* Observability
