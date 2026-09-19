"""
Phase 5 — Cache Entry.

Defines the structure of a single in-memory cache entry.
Each entry stores the cached response value alongside an absolute expiry
timestamp (seconds since epoch) so TTL can be checked without storing the
TTL duration itself.
"""

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    """
    A single in-memory cache entry.

    Attributes:
        value:      The cached response payload (JSON-serializable dict).
        expires_at: Absolute expiry timestamp as a float (time.time() + ttl).
                    An entry is expired when time.time() > expires_at.
    """

    value: Any
    expires_at: float

    def is_expired(self) -> bool:
        """
        Returns True if the entry has passed its expiry time.

        Uses time.time() so that tests can patch it with a fixed clock.
        """
        return time.time() > self.expires_at
