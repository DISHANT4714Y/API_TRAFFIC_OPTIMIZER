"""
Phase 5 — Cache Manager.

Manages an in-memory dict-backed cache of CacheEntry objects with:
  - TTL-based expiration checked on every get()
  - get / set / delete / clear / exists operations
  - Basic statistics: total_requests, hits, misses, hit_ratio

Default TTL is read from the environment variable CACHE_TTL_SECONDS
(default: 30 seconds).  Tests may override this by constructing a
CacheManager with an explicit default_ttl argument.

This is intentionally a simple, Phase 5-scoped implementation.
No LRU eviction, no Redis, no background expiry sweep.
"""

import logging
import os
import time
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from app.cache.entry import CacheEntry

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default TTL (seconds) – configurable via environment
# ---------------------------------------------------------------------------
_DEFAULT_TTL_SECONDS: float = float(os.getenv("CACHE_TTL_SECONDS", "30"))


class CacheManager:
    """
    In-memory cache manager backed by a plain Python dict.

    Attributes:
        default_ttl: Seconds a stored entry lives before expiring.
        _store:      Internal dict mapping cache key → CacheEntry.
        _hits:       Number of successful cache lookups.
        _misses:     Number of failed cache lookups (including expired).
        _total:      Total number of get() calls (hits + misses).
    """

    def __init__(self, default_ttl: Optional[float] = None) -> None:
        """
        Args:
            default_ttl: Override TTL in seconds. Defaults to CACHE_TTL_SECONDS
                         env var (or 30 s if not set).
        """
        self.default_ttl: float = (
            default_ttl if default_ttl is not None else _DEFAULT_TTL_SECONDS
        )
        self._store: Dict[str, CacheEntry] = {}
        self._hits: int = 0
        self._misses: int = 0
        self._total: int = 0

    # ------------------------------------------------------------------
    # Public cache operations
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieves a cached value by key.

        - Returns the stored value on a valid (non-expired) hit.
        - Returns None and increments miss counter if key is absent.
        - Returns None, logs CACHE EXPIRED, deletes the entry, and increments
          miss counter if the entry exists but has passed its TTL.

        Args:
            key: The cache key (typically the SHA-256 key from Phase 4).

        Returns:
            The cached value, or None if not found / expired.
        """
        self._total += 1

        entry = self._store.get(key)

        if entry is None:
            self._misses += 1
            logger.info("[CACHE MISS] key=%s", key[:32])
            return None

        if entry.is_expired():
            self._misses += 1
            del self._store[key]
            logger.info("[CACHE EXPIRED] key=%s", key[:32])
            return None

        self._hits += 1
        logger.info("[CACHE HIT] key=%s", key[:32])
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """
        Stores a value in the cache with an associated TTL.

        Args:
            key:   The cache key.
            value: The response payload to cache.
            ttl:   Seconds until the entry expires. Defaults to self.default_ttl.
        """
        effective_ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + effective_ttl
        self._store[key] = CacheEntry(value=value, expires_at=expires_at)
        logger.info(
            "[CACHE SET] key=%s ttl=%.1fs expires_at=%.3f",
            key[:32],
            effective_ttl,
            expires_at,
        )

    def delete(self, key: str) -> bool:
        """
        Removes a single entry from the cache.

        Args:
            key: The cache key to remove.

        Returns:
            True if the key existed and was removed, False otherwise.
        """
        existed = key in self._store
        self._store.pop(key, None)
        return existed

    def clear(self) -> int:
        """
        Removes all entries from the cache.

        Returns:
            The number of entries that were cleared.
        """
        count = len(self._store)
        self._store.clear()
        logger.info("[CACHE CLEAR] Cleared %d entries.", count)
        return count

    def exists(self, key: str) -> bool:
        """
        Checks whether a non-expired entry exists for the given key.

        Does NOT increment hit/miss counters (read-only probe).

        Args:
            key: The cache key to probe.

        Returns:
            True if a valid (non-expired) entry exists, False otherwise.
        """
        entry = self._store.get(key)
        if entry is None:
            return False
        if entry.is_expired():
            del self._store[key]
            return False
        return True

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    @property
    def total_requests(self) -> int:
        """Total number of get() calls recorded."""
        return self._total

    @property
    def hits(self) -> int:
        """Number of successful cache gets (non-expired entries found)."""
        return self._hits

    @property
    def misses(self) -> int:
        """Number of failed cache gets (missing or expired entries)."""
        return self._misses

    @property
    def hit_ratio(self) -> float:
        """
        Fraction of get() calls that returned a cached value.

        Returns 0.0 when no requests have been made yet to avoid ZeroDivisionError.
        """
        if self._total == 0:
            return 0.0
        return round(self._hits / self._total, 4)

    def get_stats(self) -> Dict[str, Any]:
        """
        Returns a snapshot of cache statistics as a plain dict.

        Suitable for direct use as a JSON response body.
        """
        return {
            "total_requests": self._total,
            "hits": self._hits,
            "misses": self._misses,
            "hit_ratio": self.hit_ratio,
            "current_entries": len(self._store),
        }

    def reset_stats(self) -> None:
        """Resets hit/miss/total counters without clearing stored entries."""
        self._hits = 0
        self._misses = 0
        self._total = 0
