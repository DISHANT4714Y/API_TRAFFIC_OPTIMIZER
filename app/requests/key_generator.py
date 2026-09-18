"""
Phase 4 — Cache-Key Generation.

Assembles a deterministic, collision-resistant cache key from the components
of an incoming HTTP request.

Pipeline:
    1. Normalize each component (method, path, query, headers, body)
       using app.requests.normalizer.
    2. Build a structured canonical representation (a plain Python dict).
    3. Serialize the canonical dict to a deterministic JSON string.
    4. Hash the JSON string using SHA-256.
    5. Return the key with a version prefix: "api-cache:v1:<hex-digest>"

Key versioning:
    The "v1" prefix means this key was generated with Version-1 normalization
    rules. If the normalization algorithm changes in a later phase, bump to
    "v2" so that stale v1 keys are never accidentally used for v2 responses.

Security notes:
    - SHA-256 is used instead of Python's built-in hash() because built-in
      hash results are randomized per process (Python hash randomization).
    - Authorization tokens are explicitly excluded by normalize_headers().
    - Raw request bodies are never logged in their entirety.

Time complexity:
    Let k = number of query params, m = length of serialized canonical string.
    - normalize_query_params(): O(k log k)  — sorting
    - json.dumps():             O(m)         — serialization
    - sha256():                 O(m)         — hashing
    Overall: O(k log k + m), dominated by network I/O in practice.
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.requests.normalizer import (
    QueryParamList,
    normalize_body,
    normalize_headers,
    normalize_method,
    normalize_path,
    normalize_query_params,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key format constants
# ---------------------------------------------------------------------------

# Version prefix for the cache key.
# Bump to "api-cache:v2:" if normalization rules change in a future phase,
# so that existing cached entries with v1 keys are automatically invalidated.
KEY_PREFIX: str = "api-cache:v1:"

# Encoding used when converting the canonical string to bytes for hashing.
_ENCODING: str = "utf-8"


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def generate_cache_key(
    method: str,
    path: str,
    query_params: Optional[Sequence[Tuple[str, str]]] = None,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Any] = None,
    include_headers: Optional[List[str]] = None,
) -> str:
    """
    Generates a deterministic, version-prefixed cache key for a request.

    This is the main entry point for Phase 4.

    Two logically equivalent requests (same method, path, params, and
    relevant headers) will always produce the same key, regardless of
    the order in which query parameters were passed.

    Args:
        method:
            HTTP method string. Case-insensitive; normalized to uppercase.
            Example: "GET", "post"

        path:
            URL path of the request.
            Example: "/weather", "weather"

        query_params:
            Sequence of (name, value) tuples. May be in any order.
            Example: [("units", "metric"), ("city", "Delhi")]
            Defaults to None (no query parameters).

        headers:
            Raw request headers dict. Only headers listed in `include_headers`
            will affect the cache key. Defaults to None.

        body:
            Request body. For GET requests this should be None.
            For POST/PUT, pass a dict (parsed JSON) or a raw string.
            Defaults to None.

        include_headers:
            List of lowercase header names to include in the key.
            Example: ["accept", "accept-language"]
            Authorization is explicitly excluded regardless of this list.
            Defaults to None (no headers influence the key).

    Returns:
        A string in the format: "api-cache:v1:<sha256-hex-digest>"
        Example: "api-cache:v1:7f2a9c3d..."

    Example:
        >>> key = generate_cache_key(
        ...     method="GET",
        ...     path="/weather",
        ...     query_params=[("city", "Delhi"), ("units", "metric")],
        ... )
        >>> key.startswith("api-cache:v1:")
        True

        # Reversed param order → same key
        >>> key2 = generate_cache_key(
        ...     method="GET",
        ...     path="/weather",
        ...     query_params=[("units", "metric"), ("city", "Delhi")],
        ... )
        >>> key == key2
        True
    """
    # --- Step 1: Normalize each component ---
    norm_method = normalize_method(method)
    norm_path   = normalize_path(path)
    norm_params = normalize_query_params(query_params or [])
    norm_headers = normalize_headers(headers or {}, include_keys=include_headers)
    norm_body   = normalize_body(body)

    # --- Step 2: Build canonical representation ---
    canonical = _build_canonical_request(
        method=norm_method,
        path=norm_path,
        query_params=norm_params,
        headers=norm_headers,
        body=norm_body,
    )

    # --- Step 3: Serialize to a deterministic string ---
    canonical_string = _serialize_canonical(canonical)

    # --- Step 4: Hash ---
    digest = _sha256_hex(canonical_string)

    # --- Step 5: Assemble final key ---
    key = KEY_PREFIX + digest

    # Log only a short prefix of the key to help with debugging.
    # Never log the raw canonical string if it contains sensitive body data.
    logger.debug(
        "[KEY_GENERATOR] %s %s → key=%s...",
        norm_method,
        norm_path,
        key[:32],
    )

    return key


# ---------------------------------------------------------------------------
# Internal helpers (prefixed with _ to mark as private)
# ---------------------------------------------------------------------------

def _build_canonical_request(
    method: str,
    path: str,
    query_params: QueryParamList,
    headers: Dict[str, str],
    body: Optional[str],
) -> Dict[str, Any]:
    """
    Assembles all normalized components into a single canonical dict.

    This intermediate dict is what gets serialized and hashed. Making it
    an explicit dict (instead of string concatenation) makes it easy to:
      - Inspect in tests
      - Debug by printing
      - Extend with new fields in future phases

    The structure is intentionally simple:
    {
        "method":  "GET",
        "path":    "/weather",
        "query":   [["city", "Delhi"], ["units", "metric"]],
        "headers": {},
        "body":    null
    }

    Query params are stored as a list of [name, value] pairs (not a dict)
    to correctly handle repeated parameter names like id=1&id=2.

    Args:
        method:       Normalized uppercase HTTP method.
        path:         Normalized path string.
        query_params: Sorted list of (name, value) tuples.
        headers:      Filtered and lowercased headers dict.
        body:         Canonical body string or None.

    Returns:
        A plain Python dict representing the canonical request.
    """
    return {
        "method":  method,
        "path":    path,
        # Convert tuples to lists so JSON serialization is unambiguous.
        "query":   [[name, value] for name, value in query_params],
        "headers": headers,
        "body":    body,
    }


def _serialize_canonical(canonical: Dict[str, Any]) -> str:
    """
    Serializes the canonical dict to a deterministic JSON string.

    Key decisions:
    - `sort_keys=True`: Even though the top-level dict is built in a fixed
      order, this ensures nested dicts (e.g., inside `headers`) are also
      sorted. Future-proofs against dict insertion-order changes.
    - `separators=(",", ":")`: Removes all unnecessary whitespace, producing
      the most compact and consistent representation possible.
    - `ensure_ascii=False`: Allows non-ASCII values (e.g., city names like
      "Ahmedabad", "Москва") to be stored as-is instead of escape sequences.

    Args:
        canonical: The canonical request dict.

    Returns:
        A compact, deterministic JSON string.
    """
    return json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _sha256_hex(text: str) -> str:
    """
    Computes the SHA-256 hash of a UTF-8-encoded string.

    Why SHA-256?
    - Deterministic across all platforms, Python versions, and process runs.
    - 256-bit output → 2^256 possible values. Collisions are astronomically
      unlikely (birthday bound ~2^128 attempts needed to find one).
    - Not a security-critical use here, but using a proper hash avoids
      correctness bugs that plague weaker approaches (CRC32, MD5).
    - No external library needed — hashlib is in Python's standard library.

    Why not Python's built-in hash()?
    - hash("hello") returns different values in different Python processes
      because Python randomizes hash seeds (PEP 456 / PYTHONHASHSEED).
    - A cache key generated in one process would not match the same key
      generated in another process. This would break any persistent cache.

    Args:
        text: Canonical string to hash, already normalized.

    Returns:
        64-character lowercase hex string (SHA-256 digest).
    """
    return hashlib.sha256(text.encode(_ENCODING)).hexdigest()


# ---------------------------------------------------------------------------
# Convenience wrapper for use inside FastAPI route handlers
# ---------------------------------------------------------------------------

def generate_key_from_request(
    resource_id: str,
    query_params: Optional[Dict[str, str]] = None,
) -> str:
    """
    Convenience wrapper tailored to the existing optimizer proxy route.

    The proxy route in app/main.py uses:
        resource_id: str          (path component)
        query_params: dict        (from request.query_params)

    This function bridges the proxy's data shapes to generate_cache_key().

    For this phase, only GET requests are supported by the proxy, so the
    method is hardcoded to "GET" here. Headers and body are excluded from
    the key in this MVP scope (no Authorization, no POST body).

    Args:
        resource_id:  The resource path segment, e.g. "weather".
        query_params: Dict of query parameters from request.query_params.
                      Example: {"city": "Delhi", "units": "metric"}

    Returns:
        A "api-cache:v1:<sha256>" cache key string.

    Example:
        >>> generate_key_from_request("weather", {"city": "Delhi"})
        'api-cache:v1:...'
    """
    # Convert the dict to a list of tuples so normalize_query_params()
    # receives the correct type. dict.items() order is insertion-order
    # in Python 3.7+, but we normalize (sort) it regardless.
    param_pairs: List[Tuple[str, str]] = list((query_params or {}).items())

    return generate_cache_key(
        method="GET",
        path=f"/{resource_id}",
        query_params=param_pairs,
    )
