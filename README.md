# Intelligent API Traffic Optimizer

> Adaptive middleware designed to reduce redundant API traffic, latency, and backend load.

`🚧 Status: Phase 1 Complete — Foundation Setup`

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

For the current prototype, development is intentionally incremental. The first objective is to establish a clean foundation before implementing optimization algorithms.

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

| Phase   | Component                  | Status     |
| ------- | -------------------------- | ---------- |
| Phase 1 | Project setup              | ✅ Complete |
| Phase 1 | FastAPI foundation         | ✅ Complete |
| Phase 1 | Mock API foundation        | ✅ Complete |
| Phase 1 | Test environment           | ✅ Complete |
| Phase 2 | Mock external API behavior | ⏳ Next     |
| Phase 3 | API proxy                  | ⏳ Planned  |
| Phase 4 | Request normalization      | ⏳ Planned  |
| Phase 5 | In-memory cache            | ⏳ Planned  |
| Phase 6 | TTL & cache metrics        | ⏳ Planned  |
| Phase 7 | Request deduplication      | ⏳ Planned  |
| Phase 8 | Request coalescing         | ⏳ Planned  |
| Phase 9 | Benchmarking               | ⏳ Planned  |

## Current Architecture

Because Phase 1 is only the foundation, the current architecture consists of two independent services:

```text
                    ┌──────────────────────┐
                    │       Client         │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │    FastAPI App       │
                    │    /health           │
                    └──────────────────────┘


                    ┌──────────────────────┐
                    │     Mock API         │
                    │     /health          │
                    └──────────────────────┘
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
This architecture represents the intended prototype and will be implemented incrementally.

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
│   ├── main.py
│   ├── proxy/
│   ├── cache/
│   ├── requests/
│   └── metrics/
│
├── mock_api/
│   └── main.py
│
├── tests/
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

## Running the Mock API

```bash
uvicorn mock_api.main:app --port 8001 --reload
```

Mock API:
`http://127.0.0.1:8001`

Health endpoint:
```text
GET /health
```

Expected response:
```json
{
  "status": "mock-api-ok"
}
```

## Testing

Run:
```bash
pytest
```
Phase 1 tests currently focus on validating the project foundation and imports.

## Development Roadmap

### Phase 1 — Foundation ✅
* Python environment
* FastAPI application
* Mock API foundation
* Project structure
* Test environment
* Git configuration

### Phase 2 — Mock External API
Planned:
* configurable response
* artificial latency
* simulated failures
* request counter

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

## Benchmarking Philosophy

The project will not assume that an optimization is effective simply because it sounds theoretically useful. Each optimization will be evaluated experimentally.

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
This should become an important engineering principle of the project.

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
