"""
benchmarks/workloads.py — Phase 2B

Workload profile definitions and deterministic resource-ID generators.

Each workload produces a list of resource IDs (strings) of length n_requests.
The same seed always produces the same list, so baseline and optimized runs
use an identical request sequence when the seed is fixed.

Workload profiles:
    W-REP   All requests use the same single resource ID.
            Expected cache behaviour: 1 miss then N-1 hits.
    W-MIX   Requests are sampled uniformly from a fixed pool of K IDs.
            Expected cache behaviour: K misses then (N-K) hits (approximately).
    W-UNQ   Each request uses a distinct resource ID.
            Expected cache behaviour: N misses, 0 hits — worst case for cache.
    W-WARM  Same single resource as W-REP, but the cache is pre-populated
            before the measured phase.  All measured requests expect cache hits.
    W-CON   Same single resource as W-REP, tested at varying concurrency.
            Used for the concurrency-sweep experiment.
    W-COL   All requests issued simultaneously in a single concurrent burst.
            Primary test for request-coalescing behaviour.
"""

from __future__ import annotations

import random
from enum import Enum
from typing import List


class WorkloadProfile(str, Enum):
    """Identifiers for each supported workload profile."""
    REPEATED   = "W-REP"
    MIXED      = "W-MIX"
    UNIQUE     = "W-UNQ"
    WARM       = "W-WARM"
    CONCURRENT = "W-CON"
    COALESCING = "W-COL"

    def description(self) -> str:
        return {
            "W-REP":  "Repeated identical requests (same resource ID)",
            "W-MIX":  "Mixed repeated requests (fixed resource pool)",
            "W-UNQ":  "Mostly unique requests (distinct resource IDs)",
            "W-WARM": "Warm-cache: pre-populated cache before measured phase",
            "W-CON":  "Concurrency sweep (repeated resource, varying concurrency)",
            "W-COL":  "Concurrent identical burst (coalescing test)",
        }[self.value]


# Resource IDs use a URL-safe character set so they are valid path segments.
_SINGLE_RESOURCE = "bench-resource-0"


def generate_resource_ids(
    profile: WorkloadProfile,
    n_requests: int,
    pool_size: int = 10,
    seed: int = 42,
) -> List[str]:
    """
    Return a deterministic list of ``n_requests`` resource IDs for *profile*.

    Args:
        profile:    Workload profile enum value.
        n_requests: Number of resource IDs to generate (one per request).
        pool_size:  Number of distinct IDs in the pool for W-MIX.
                    Ignored for all other profiles.
        seed:       Random seed for reproducibility.  The same seed and
                    profile always produce the same list.

    Returns:
        List[str] of length n_requests.

    Raises:
        ValueError: If n_requests < 1 or pool_size < 1.
    """
    if n_requests < 1:
        raise ValueError(f"n_requests must be >= 1, got {n_requests}")
    if pool_size < 1:
        raise ValueError(f"pool_size must be >= 1, got {pool_size}")

    if profile in (
        WorkloadProfile.REPEATED,
        WorkloadProfile.WARM,
        WorkloadProfile.CONCURRENT,
        WorkloadProfile.COALESCING,
    ):
        # All requests target the same single resource
        return [_SINGLE_RESOURCE] * n_requests

    if profile == WorkloadProfile.MIXED:
        pool = [f"bench-resource-{i}" for i in range(pool_size)]
        rng  = random.Random(seed)
        return [rng.choice(pool) for _ in range(n_requests)]

    if profile == WorkloadProfile.UNIQUE:
        # Each request gets a distinct ID; no warm-up makes sense here
        return [f"bench-unique-{i}" for i in range(n_requests)]

    raise ValueError(f"Unrecognised workload profile: {profile!r}")


def warm_up_resource_ids(
    profile: WorkloadProfile,
    pool_size: int = 10,
) -> List[str]:
    """
    Return the set of resource IDs that must be pre-cached for a warm run.

    For W-WARM and single-resource profiles this is a list of one element.
    For W-MIX it is all IDs in the pool.
    For W-UNQ no warm-up is meaningful (returns empty list).
    """
    if profile in (
        WorkloadProfile.REPEATED,
        WorkloadProfile.WARM,
        WorkloadProfile.CONCURRENT,
        WorkloadProfile.COALESCING,
    ):
        return [_SINGLE_RESOURCE]

    if profile == WorkloadProfile.MIXED:
        return [f"bench-resource-{i}" for i in range(pool_size)]

    # W-UNQ — no repeatable warm-up possible
    return []


SUPPORTED_PROFILES: List[WorkloadProfile] = [
    WorkloadProfile.REPEATED,
    WorkloadProfile.MIXED,
    WorkloadProfile.UNIQUE,
    WorkloadProfile.WARM,
    WorkloadProfile.CONCURRENT,
    WorkloadProfile.COALESCING,
]
