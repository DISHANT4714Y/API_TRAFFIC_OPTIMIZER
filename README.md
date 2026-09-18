# Intelligent API Traffic Optimizer

> Adaptive middleware designed to reduce redundant API traffic, latency, and backend load.

`✅ Status: Phase 4 Complete — Cache-Key Generation`

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

| Phase   | Component                        | Status      |
| ------- | -------------------------------- | ----------- |
| Phase 1 | Project setup & foundation       | ✅ Complete  |
| Phase 1 | FastAPI foundation               | ✅ Complete  |
| Phase 1 | Mock API foundation              | ✅ Complete  |
| Phase 1 | Test environment                 | ✅ Complete  |
| Phase 2 | Mock external API behavior       | ✅ Complete  |
| Phase 3 | Basic API proxy                  | ✅ Complete  |
| Phase 4 | Request normalisation & cache-key generation | ✅ Complete  |
| Phase 5 | In-memory cache                  | ⏳ Next      |
| Phase 6 | TTL & cache metrics              | ⏳ Planned   |
| Phase 7 | Request deduplication            | ⏳ Planned   |
| Phase 8 | Request coalescing               | ⏳ Planned   |
| Phase 9 | Metrics & benchmarking           | ⏳ Planned   |

## Current Working Architecture

With Phase 4 complete, the Optimizer normalises every incoming request and generates a deterministic SHA-256 cache key before forwarding to the upstream Mock API. The key is logged on every request and is exposed through a development debug endpoint. Phase 5 will use this key for actual cache lookups.

```text
                     CLIENT
                        │
                        │ HTTP Request (GET /proxy/data/{id}?...)
                        ▼
              ┌─────────────────────────────┐
              │  Intelligent API            │
              │  Traffic Optimizer          │
              │  (Port 8000)               │
              │                             │
              │  • /health                  │
              │  • /proxy/data/{id}  ──┐    │
              │  • /debug/cache-key    │    │
              └────────────────────────┼────┘
                                       │
                          ┌────────────▼────────────┐
                          │   Request Normaliser     │
                          │   normalizer.py          │
                          │                          │
                          │  normalize_method()      │
                          │  normalize_path()        │
                          │  normalize_query_params()│
                          └────────────┬─────────────┘
                                       │
                          ┌────────────▼────────────┐
                          │   Cache-Key Generator    │
                          │   key_generator.py       │
                          │                          │
                          │  build_canonical_request │
                          │  → json.dumps(sort_keys) │
                          │  → SHA-256 hex digest    │
                          │  → "api-cache:v1:<hex>" │
                          └────────────┬─────────────┘
                                       │ key logged
                                       │ (Phase 5: cache lookup goes here)
                                       ▼
              ┌─────────────────────────────┐
              │   Mock External API         │
              │   (Port 8001)               │
              │                             │
              │  • /health                  │
              │  • /api/data/{id}           │
              │  • /stats                   │
              │  • /stats/reset             │
              └─────────────┬───────────────┘
                            │ Response + Headers
                            ▼
                         CLIENT
```

> **Note:** The cache key is generated and logged on every request. The proxy still calls the upstream API on every request — cache lookup and storage will be implemented in Phase 5.

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
│   ├── main.py                    ← v0.4.0 — logs cache key per request
│   ├── proxy/
│   │   ├── __init__.py
│   │   └── client.py              ← async httpx proxy client (Phase 3)
│   ├── cache/
│   │   ├── __init__.py
│   │   ├── entry.py               ← stub (Phase 5)
│   │   └── manager.py             ← stub (Phase 5)
│   ├── requests/
│   │   ├── __init__.py
│   │   ├── normalizer.py          ← ✅ Phase 3/4: normalize method/path/params/headers/body
│   │   ├── key_generator.py       ← ✅ Phase 4: SHA-256 cache-key generation pipeline
│   │   └── coalescer.py           ← stub (Phase 8)
│   └── metrics/
│       ├── __init__.py
│       └── collector.py           ← stub (Phase 9)
│
├── mock_api/
│   ├── __init__.py
│   ├── main.py                    ← controllable mock API (Phase 2)
│   ├── config.py
│   ├── models.py
│   └── state.py
│
├── tests/
│   ├── __init__.py
│   ├── test_mock_api.py           ← Phase 2 tests
│   ├── test_proxy.py              ← Phase 3 tests
│   ├── test_normalizer.py         ← ✅ Phase 4: normalizer unit tests
│   ├── test_key_generator.py      ← ✅ Phase 4: key-generation tests (10 spec examples)
│   ├── test_cache.py              ← stub (Phase 5)
│   └── test_optimizer.py          ← import smoke test
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
  GET /proxy/data/{resource_id}?city=Delhi&units=metric
  ```
  Transparently forwards request to upstream Mock API. Generates and logs a SHA-256 cache key on every request (Phase 4). Forwards query parameters and returns upstream JSON payload.
  - Connection failures to upstream return HTTP `502 Bad Gateway` (`{"error": "Upstream API unavailable"}`).
  - Upstream request timeouts return HTTP `504 Gateway Timeout` (`{"error": "Upstream API timeout"}`).

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
* `CACHE_TTL_SECONDS`: Reserved for future caching phases (default: `30`).

## Testing

### Run the full test suite

```powershell
python -m pytest tests/ -v
```

Current result: **108 tests, 0 failures.**

### Run tests by phase

```powershell
# Phase 2 — Mock API tests
python -m pytest tests/test_mock_api.py -v

# Phase 3 — Proxy tests
python -m pytest tests/test_proxy.py -v

# Phase 4 — Normaliser tests
python -m pytest tests/test_normalizer.py -v

# Phase 4 — Cache-key generator tests
python -m pytest tests/test_key_generator.py -v
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
* Regression: Phase 1–3 imports unaffected

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

### Phase 5 — In-Memory Cache
Implement:
* cache entry structure (dataclass with TTL timestamps)
* in-memory dict-based cache storage
* cache lookup using the Phase 4 key
* cache hit → return stored response
* cache miss → call upstream → store → return
* `/cache/stats` and `/cache/clear` endpoints

### Phase 6 — TTL & Cache Expiry
Implement:
* fixed TTL using `time.monotonic()` for safe elapsed-time measurement
* lazy expiry on lookup
* configurable `CACHE_TTL_SECONDS`

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
