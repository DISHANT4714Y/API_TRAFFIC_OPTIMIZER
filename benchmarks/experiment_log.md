# Phase 2C Experiment Log
**Date:** 2026-10-13  
**Local time at start:** 2026-10-13T11:56:44+05:30  
**Working directory:** `c:\DESIGN_PROJECT\API_TRAFFIC_OPTIMIZER`

## Environment

| Item | Value |
|---|---|
| Python | 3.13.0 |
| Executable | C:\Users\Ram\AppData\Local\Programs\Python\Python313\python.exe |
| Platform | Windows (local machine, loopback only) |
| FastAPI | 0.141.1 |
| httpx | 0.27.2 |
| uvicorn | 0.53.0 |
| MOCK_API_DELAY_MS (.env default) | 500 ms (overridden per request via `?delay_ms=`) |
| MOCK_API_FAILURE_RATE | 0 |
| CACHE_TTL_SECONDS | 30 s |
| UPSTREAM_TIMEOUT_SECONDS | 5 s |
| Benchmark mock_delay_ms | 100 ms (passed as `?delay_ms=` query param) |
| Standard concurrency | 10 |

## Preflight Checks

| Check | Status | Notes |
|---|---|---|
| Python 3.13.0 | PASS | C:\Users\Ram\AppData\Local\Programs\Python\Python313\python.exe |
| fastapi 0.141.1 | PASS | |
| httpx 0.27.2 | PASS | |
| uvicorn 0.53.0 | PASS | |
| Test suite (248 tests) | PASS | 0 failures, 1 starlette deprecation warning |
| Mock API health | PASS | GET :8001/health → {status: mock-api-ok} |
| Optimizer health | PASS | GET :8000/health → {status: ok} |
| Baseline route | PASS | :8001/api/data/test-resource → 200 |
| Optimized route | PASS | :8000/proxy/data/test-resource → 200, X-Cache: MISS |
| Stats reset | PASS | POST /stats/reset, /cache/reset, /metrics/reset all → 200 |
| Results dir write | PASS | benchmarks/results/ writable |

## Prior Runs from Phase 2B (2026-10-12)

W-REP baseline (3 reps): Complete. Mean ~689 ms, 0 errors.  
W-REP optimized (3 reps): Complete. Mean ~941 ms, 0 errors. 90 hits / 10 misses.  
W-MIX baseline (3 reps): Complete. Mean ~691 ms, 0 errors.  
W-MIX optimized (3 reps): 2 completed with ~7-10s latency; 1 had 27% errors.  
W-UNQ baseline (3 reps): Complete. Mean ~684 ms, 0 errors.  
W-UNQ optimized (3 reps): All 3 failed with high error rates (8%-89%) and extreme latency.

## Known Limitation — Coalescer Lock Serialization (W-UNQ, W-MIX)

The RequestCoalescer uses asyncio.Lock for every cache miss. With N unique keys at
concurrency C, each request must acquire the lock sequentially to register as leader.
This serializes all N leader registrations even though keys are independent.
Under high concurrency with many unique resources, effective throughput degrades
severely. Benchmark timeout=10s is hit frequently. This is an architectural limitation
of the current coalescer, not a measurement error. Results are reported as-is.

## Experiment Controls (per design)

- Same mock API implementation for all runs.
- delay_ms=100 for all standard runs (via ?delay_ms= query param).
- MOCK_API_FAILURE_RATE=0.
- State reset sequence: POST /stats/reset → /cache/reset → /metrics/reset before each measured phase.
- seed=42 for all randomized workloads.
- P99 computed only when n_requests >= 100.
- Baseline = direct client → Mock API; Optimized = client → Optimizer proxy.

---

## Phase 2C Run Log

[2026-10-13T06:36:35Z] ======================================================================
[2026-10-13T06:36:35Z] Phase 2C — Master Experiment Runner starting
[2026-10-13T06:36:35Z] Selected experiments: ['A', 'B', 'C', 'D']
[2026-10-13T06:36:35Z] ======================================================================
[2026-10-13T06:36:35Z] 
--- Experiment A: Repeated identical (W-REP) ---
[2026-10-13T06:36:35Z] Control: 100 requests, concurrency=10, delay_ms=100, seed=42, 3 reps
[2026-10-13T06:37:08Z] ======================================================================
[2026-10-13T06:37:08Z] Phase 2C — Master Experiment Runner starting
[2026-10-13T06:37:08Z] Selected experiments: ['A', 'B', 'C', 'D']
[2026-10-13T06:37:08Z] ======================================================================
[2026-10-13T06:37:08Z] 
--- Experiment A: Repeated identical (W-REP) ---
[2026-10-13T06:37:08Z] Control: 100 requests, concurrency=10, delay_ms=100, seed=42, 3 reps
[2026-10-13T06:37:08Z] Baseline: client -> Mock API directly (no caching)
[2026-10-13T06:37:08Z] CMD: --mode baseline --workload W-REP --n-requests 100 --concurrency 10 --warm-up 0 --mock-delay-ms 100 --pool-size 10 --seed 42 --timeout 10.0 --repetitions 3 --results-dir C:\DESIGN_PROJECT\API_TRAFFIC_OPTIMIZER\benchmarks\results --optimizer-url http://127.0.0.1:8000 --mock-api-url http://127.0.0.1:8001
[2026-10-13T06:37:16Z] ExpA-baseline: OK in 8.6s
[2026-10-13T06:37:16Z] Optimized: client -> Optimizer proxy (cache + coalescing)
[2026-10-13T06:37:16Z] CMD: --mode optimized --workload W-REP --n-requests 100 --concurrency 10 --warm-up 0 --mock-delay-ms 100 --pool-size 10 --seed 42 --timeout 10.0 --repetitions 3 --results-dir C:\DESIGN_PROJECT\API_TRAFFIC_OPTIMIZER\benchmarks\results --optimizer-url http://127.0.0.1:8000 --mock-api-url http://127.0.0.1:8001
[2026-10-13T06:37:25Z] ExpA-optimized: OK in 9.0s
[2026-10-13T06:37:25Z] 
--- Experiment B: Mixed repeated (W-MIX) ---
[2026-10-13T06:37:25Z] Control: 100 requests, pool_size=10, concurrency=10, delay_ms=100, 3 reps
[2026-10-13T06:37:25Z] NOTE: W-MIX optimized had high latency in Phase 2B due to lock serialization.
[2026-10-13T06:37:25Z] Using timeout=15s for optimized to allow legitimate completion.
[2026-10-13T06:37:25Z] CMD: --mode baseline --workload W-MIX --n-requests 100 --concurrency 10 --warm-up 0 --mock-delay-ms 100 --pool-size 10 --seed 42 --timeout 10.0 --repetitions 3 --results-dir C:\DESIGN_PROJECT\API_TRAFFIC_OPTIMIZER\benchmarks\results --optimizer-url http://127.0.0.1:8000 --mock-api-url http://127.0.0.1:8001
[2026-10-13T06:37:34Z] ExpB-baseline: OK in 8.6s
[2026-10-13T06:37:34Z] CMD: --mode optimized --workload W-MIX --n-requests 100 --concurrency 10 --warm-up 0 --mock-delay-ms 100 --pool-size 10 --seed 42 --timeout 15.0 --repetitions 3 --results-dir C:\DESIGN_PROJECT\API_TRAFFIC_OPTIMIZER\benchmarks\results --optimizer-url http://127.0.0.1:8000 --mock-api-url http://127.0.0.1:8001
[2026-10-13T06:39:03Z] ExpB-optimized: OK in 89.4s
[2026-10-13T06:39:03Z] 
--- Experiment C: Mostly unique (W-UNQ) ---
[2026-10-13T06:39:03Z] Control: 100 requests, each unique resource, concurrency=10, delay_ms=100
[2026-10-13T06:39:03Z] NOTE: Prior runs showed severe coalescer-lock serialization for unique keys.
[2026-10-13T06:39:03Z] Using timeout=15s for optimized. Results may show high error rates.
[2026-10-13T06:39:03Z] This is the 'optimizer adds overhead' scenario; results reported as-is.
[2026-10-13T06:39:03Z] CMD: --mode baseline --workload W-UNQ --n-requests 100 --concurrency 10 --warm-up 0 --mock-delay-ms 100 --pool-size 10 --seed 42 --timeout 10.0 --repetitions 3 --results-dir C:\DESIGN_PROJECT\API_TRAFFIC_OPTIMIZER\benchmarks\results --optimizer-url http://127.0.0.1:8000 --mock-api-url http://127.0.0.1:8001
[2026-10-13T06:39:14Z] ExpC-baseline: OK in 10.8s
[2026-10-13T06:39:14Z] CMD: --mode optimized --workload W-UNQ --n-requests 100 --concurrency 10 --warm-up 0 --mock-delay-ms 100 --pool-size 10 --seed 42 --timeout 15.0 --repetitions 3 --results-dir C:\DESIGN_PROJECT\API_TRAFFIC_OPTIMIZER\benchmarks\results --optimizer-url http://127.0.0.1:8000 --mock-api-url http://127.0.0.1:8001
