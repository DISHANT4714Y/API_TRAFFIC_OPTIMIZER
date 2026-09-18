"""
Phase 3 — Request Normalization.

Provides low-level helper functions that clean and standardize individual
components of an incoming HTTP request (method, path, query parameters,
headers, body).

These normalized components are consumed by the Phase 4 cache-key generator
(app/requests/key_generator.py) to build a deterministic cache key.

Design principle:
    Each function handles exactly one request component.
    The key generator is responsible for assembling them.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# Type alias: query params are a list of (name, value) pairs.
# Using a list of tuples (not a dict) so repeated parameter names are
# preserved correctly. Example: [("id", "1"), ("id", "2")]
QueryParamList = List[Tuple[str, str]]


# ---------------------------------------------------------------------------
# 1. HTTP Method Normalization
# ---------------------------------------------------------------------------

def normalize_method(method: str) -> str:
    """
    Normalizes the HTTP method to uppercase.

    Why uppercase? HTTP methods are case-insensitive per RFC 7231, but
    conventionally written in uppercase. Normalizing ensures "get" and "GET"
    produce the same cache key.

    Args:
        method: Raw HTTP method string, e.g. "get", "POST".

    Returns:
        Uppercase method string, e.g. "GET", "POST".

    Example:
        >>> normalize_method("get")
        'GET'
        >>> normalize_method("Post")
        'POST'
    """
    return method.upper().strip()


# ---------------------------------------------------------------------------
# 2. Path Normalization
# ---------------------------------------------------------------------------

def normalize_path(path: str) -> str:
    """
    Normalizes the request path to a consistent form.

    Design decisions for this prototype:
    - Ensure the path starts with a leading slash.
    - Strip surrounding whitespace.
    - Do NOT lowercase the path because paths can be case-sensitive
      (e.g., /UserProfile vs /userprofile may be different routes).
    - Do NOT strip trailing slashes automatically. The FastAPI router may
      treat /weather and /weather/ as different endpoints.
    - Do NOT perform URL decoding here; that is handled separately.

    If the path is empty or None, return "/" as the root path.

    Args:
        path: Raw URL path string, e.g. "/weather" or "weather".

    Returns:
        Normalized path string, e.g. "/weather".

    Example:
        >>> normalize_path("/weather")
        '/weather'
        >>> normalize_path("weather")
        '/weather'
        >>> normalize_path("")
        '/'
    """
    if not path:
        return "/"

    path = path.strip()

    # Ensure there is always a leading slash.
    if not path.startswith("/"):
        path = "/" + path

    return path


# ---------------------------------------------------------------------------
# 3. Query Parameter Normalization
# ---------------------------------------------------------------------------

def normalize_query_params(
    params: Sequence[Tuple[str, str]],
) -> QueryParamList:
    """
    Normalizes query parameters into a deterministic canonical form.

    Normalization rules:
    1. Sort parameters by name (alphabetically, case-sensitive).
    2. For parameters with the same name (repeated params), preserve their
       original relative order. Example: id=1&id=2 stays as [(id,1),(id,2)].
    3. Parameter names and values are preserved as-is (no case folding).
       Lowercasing values would be incorrect because "Delhi" != "delhi" in
       most APIs.

    Why sort? The same logical request may arrive with different param orders:
        /weather?city=Delhi&units=metric
        /weather?units=metric&city=Delhi
    Both are semantically identical. Sorting ensures they produce the same
    canonical representation and therefore the same cache key.

    Why preserve repeated-param order?
    Consider: /items?id=1&id=2 vs /items?id=2&id=1
    Some APIs treat the order of repeated params as significant. Preserving
    relative order is the safe default. We only sort by *name*, not by value.

    Args:
        params: Sequence of (name, value) tuples, in any order.

    Returns:
        Sorted list of (name, value) tuples.

    Example:
        >>> normalize_query_params([("units", "metric"), ("city", "Delhi")])
        [('city', 'Delhi'), ('units', 'metric')]
    """
    if not params:
        return []

    # Python's sort is stable: equal keys keep their original relative order.
    # This means repeated params like [("id","1"), ("id","2")] stay in order
    # even after sorting by name.
    return sorted(params, key=lambda pair: pair[0])


# ---------------------------------------------------------------------------
# 4. Header Normalization
# ---------------------------------------------------------------------------

def normalize_headers(
    headers: Dict[str, str],
    include_keys: Optional[List[str]] = None,
) -> Dict[str, str]:
    """
    Extracts and normalizes only the request headers that should affect the
    cache key.

    Why not include all headers?
    Many headers change with every request but do not affect the API response:
        - User-Agent (varies by browser/client)
        - Accept-Encoding (gzip, br, etc.)
        - Connection, Content-Length, Date
        - Trace-ID, correlation IDs

    Including these would cause cache fragmentation: the same logical request
    would produce a different key on every call.

    Headers that CAN affect the response (and should be included if present):
        - Accept            (JSON vs XML)
        - Accept-Language   (en vs hi)
        - X-Tenant-ID       (multi-tenant SaaS APIs)

    Headers that are sensitive and must NOT be logged or included carelessly:
        - Authorization     (contains bearer tokens, API keys)

    For this MVP prototype, `include_keys` defaults to None, meaning NO
    headers are included in the cache key. The caller can explicitly opt in.

    Args:
        headers: Raw request headers dict with arbitrary casing.
        include_keys: List of lowercase header names to include.
                      Example: ["accept", "accept-language"]

    Returns:
        Dict of normalized (lowercase key → value) headers, containing
        only the headers in include_keys that were present in the request.

    Example:
        >>> normalize_headers(
        ...     {"Accept": "application/json", "User-Agent": "curl"},
        ...     include_keys=["accept"]
        ... )
        {'accept': 'application/json'}
    """
    if not include_keys:
        return {}

    # Normalize header keys to lowercase for consistent matching.
    lowercased = {k.lower(): v for k, v in headers.items()}

    result: Dict[str, str] = {}
    for key in include_keys:
        normalized_key = key.lower()
        # IMPORTANT: Never include Authorization tokens in the cache key.
        # Tokens are long, sensitive, and user-specific. They belong in the
        # caching policy layer (Phase 5), not in the key itself.
        if normalized_key == "authorization":
            logger.warning(
                "[NORMALIZER] 'authorization' header was requested for key "
                "inclusion but is excluded for security. Use a user-scoped "
                "cache strategy in Phase 5 instead."
            )
            continue
        if normalized_key in lowercased:
            result[normalized_key] = lowercased[normalized_key]

    return result


# ---------------------------------------------------------------------------
# 5. Request Body Normalization
# ---------------------------------------------------------------------------

def normalize_body(
    body: Optional[Any],
) -> Optional[str]:
    """
    Normalizes the request body into a deterministic string form.

    For GET requests, body is always None (GET requests have no body by
    convention). Pass None and this function returns None.

    For POST/PUT requests with a JSON body, the raw body dict may arrive
    with keys in any order. We serialize it with sort_keys=True so that
    logically equivalent JSON objects produce the same string:

        {"user_id": 10, "currency": "INR"}
        {"currency": "INR", "user_id": 10}
        → both serialize to: '{"currency":"INR","user_id":10}'

    For non-JSON bodies (plain text, bytes), the body is converted to a
    string directly. Binary blobs are not deeply parsed.

    Limitations:
    - Form-encoded bodies are not handled in this prototype.
    - Large binary bodies will be stringified naively.
    - These limitations are documented and acceptable for Phase 4.

    Args:
        body: The request body, which may be:
              - None (GET request or no body)
              - dict/list (already parsed JSON)
              - str (raw text)
              - bytes (raw binary)

    Returns:
        Canonical string representation, or None if body is absent.

    Example:
        >>> normalize_body({"user_id": 10, "currency": "INR"})
        '{"currency":"INR","user_id":10}'
        >>> normalize_body(None)
        None
    """
    if body is None:
        return None

    if isinstance(body, (dict, list)):
        # Canonical JSON: sorted keys, no extra whitespace.
        return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    if isinstance(body, bytes):
        # Attempt UTF-8 decode; fall back to a hex representation for binary.
        try:
            return body.decode("utf-8")
        except UnicodeDecodeError:
            return body.hex()

    # For plain strings and other types, convert directly.
    return str(body)
