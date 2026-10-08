"""
Phase 7 — Metrics Collector.

Tracks performance metrics for the Intelligent API Traffic Optimizer:
  - Total incoming requests
  - Cache hits and misses
  - Cache hit ratio
  - Mock API calls (upstream fetches)
  - Average response time (ms)
  - Requests saved due to caching (= cache hits)

All counters are simple integers/floats; no thread-safety concerns in a
single-process asyncio application.  A reset() method supports benchmarking.
"""

from typing import Any, Dict


class MetricsCollector:
    """
    Collects and exposes runtime performance metrics for the optimizer.

    Usage::

        collector = MetricsCollector()

        # On every proxy request (hit OR miss):
        collector.record_request(hit=False, response_time_ms=42.3)

        # When the upstream Mock API is actually called:
        collector.record_mock_api_call()

        # Retrieve a JSON-ready snapshot:
        metrics = collector.get_metrics()
    """

    def __init__(self) -> None:
        self.total_requests: int = 0
        self.cache_hits: int = 0
        self.cache_misses: int = 0
        self.mock_api_calls: int = 0
        self.requests_saved: int = 0
        self._total_response_time_ms: float = 0.0

    # ------------------------------------------------------------------
    # Recording helpers
    # ------------------------------------------------------------------

    def record_request(self, *, hit: bool, response_time_ms: float = 0.0) -> None:
        """
        Record one completed proxy request.

        Args:
            hit:              True if the response was served from cache.
            response_time_ms: Wall-clock time to fulfil the request (ms).
        """
        self.total_requests += 1
        self._total_response_time_ms += response_time_ms

        if hit:
            self.cache_hits += 1
            self.requests_saved += 1
        else:
            self.cache_misses += 1

    def record_mock_api_call(self) -> None:
        """Increment the upstream Mock API call counter by one."""
        self.mock_api_calls += 1

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def cache_hit_ratio(self) -> float:
        """Fraction of requests served from cache (0.0 when no requests)."""
        if self.total_requests == 0:
            return 0.0
        return round(self.cache_hits / self.total_requests, 4)

    @property
    def avg_response_time_ms(self) -> float:
        """Average wall-clock latency per request in milliseconds."""
        if self.total_requests == 0:
            return 0.0
        return round(self._total_response_time_ms / self.total_requests, 2)

    # ------------------------------------------------------------------
    # Snapshot / reset
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        """
        Return a JSON-serialisable snapshot of all current metrics.

        Keys:
            total_requests      — requests received since last reset
            cache_hits          — responses served from cache
            cache_misses        — cache lookups that missed
            cache_hit_ratio     — hits / total_requests (0–1)
            mock_api_calls      — upstream fetches performed
            requests_saved      — upstream calls avoided via cache
            avg_response_time_ms — mean latency across all requests
        """
        return {
            "total_requests": self.total_requests,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_ratio": self.cache_hit_ratio,
            "mock_api_calls": self.mock_api_calls,
            "requests_saved": self.requests_saved,
            "avg_response_time_ms": self.avg_response_time_ms,
        }

    def reset(self) -> None:
        """Zero all counters. Useful for benchmarking and testing."""
        self.total_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.mock_api_calls = 0
        self.requests_saved = 0
        self._total_response_time_ms = 0.0
