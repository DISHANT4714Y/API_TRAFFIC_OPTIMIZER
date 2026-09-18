"""
Phase 4 — Cache-Key Generator Unit Tests.

Tests the complete key-generation pipeline in app/requests/key_generator.py.

These tests prove the critical invariants:
    1. Same logical request → same key (determinism)
    2. Different requests → different keys (collision avoidance)
    3. Query-parameter ORDER does not affect the key
    4. Query-parameter VALUES do affect the key
    5. HTTP methods are part of the key
    6. Key format is stable and versioned

Run Phase 4 tests only:
    pytest tests/test_key_generator.py -v

Run all tests:
    pytest -v
"""

import re

import pytest

from app.requests.key_generator import (
    KEY_PREFIX,
    _build_canonical_request,
    _serialize_canonical,
    _sha256_hex,
    generate_cache_key,
    generate_key_from_request,
)


# ===========================================================================
# Helper constants
# ===========================================================================

# Regex to validate the key format: "api-cache:v1:" + 64 hex characters
KEY_PATTERN = re.compile(r"^api-cache:v1:[0-9a-f]{64}$")


def is_valid_key(key: str) -> bool:
    """Returns True if key matches the expected format."""
    return bool(KEY_PATTERN.match(key))


# ===========================================================================
# Example 1: Same request → same key (Determinism)
# ===========================================================================

class TestDeterminism:
    """Two identical requests must always produce the same key."""

    def test_same_request_produces_same_key(self):
        """
        Example 1 from spec:
            GET /weather?city=Delhi&units=metric
            GET /weather?city=Delhi&units=metric
            → Same key
        """
        key1 = generate_cache_key(
            method="GET",
            path="/weather",
            query_params=[("city", "Delhi"), ("units", "metric")],
        )
        key2 = generate_cache_key(
            method="GET",
            path="/weather",
            query_params=[("city", "Delhi"), ("units", "metric")],
        )
        assert key1 == key2

    def test_key_is_stable_across_multiple_calls(self):
        """Calling the generator 5 times must produce the same result each time."""
        keys = [
            generate_cache_key(method="GET", path="/health")
            for _ in range(5)
        ]
        assert len(set(keys)) == 1  # all 5 must be identical


# ===========================================================================
# Example 2: Query parameter ORDER does not matter
# ===========================================================================

class TestQueryParameterOrdering:
    """
    Example 2 from spec:
        GET /weather?city=Delhi&units=metric
        GET /weather?units=metric&city=Delhi
        → Same key (order of params is irrelevant)
    """

    def test_reversed_params_produce_same_key(self):
        key1 = generate_cache_key(
            method="GET",
            path="/weather",
            query_params=[("city", "Delhi"), ("units", "metric")],
        )
        key2 = generate_cache_key(
            method="GET",
            path="/weather",
            query_params=[("units", "metric"), ("city", "Delhi")],
        )
        assert key1 == key2, (
            "Query parameter ordering should not affect the cache key. "
            f"key1={key1}, key2={key2}"
        )

    def test_three_params_all_orderings_produce_same_key(self):
        """All 6 orderings of 3 params must produce the same key."""
        params_sets = [
            [("a", "1"), ("b", "2"), ("c", "3")],
            [("a", "1"), ("c", "3"), ("b", "2")],
            [("b", "2"), ("a", "1"), ("c", "3")],
            [("b", "2"), ("c", "3"), ("a", "1")],
            [("c", "3"), ("a", "1"), ("b", "2")],
            [("c", "3"), ("b", "2"), ("a", "1")],
        ]
        keys = [
            generate_cache_key(method="GET", path="/test", query_params=p)
            for p in params_sets
        ]
        assert len(set(keys)) == 1, f"Expected one unique key, got: {set(keys)}"


# ===========================================================================
# Example 3: Different query VALUES → different keys
# ===========================================================================

class TestQueryParameterValues:
    """
    Example 3 from spec:
        GET /weather?city=Delhi  → key A
        GET /weather?city=Mumbai → key B
        key A ≠ key B
    """

    def test_different_city_value_produces_different_key(self):
        key_delhi = generate_cache_key(
            method="GET",
            path="/weather",
            query_params=[("city", "Delhi")],
        )
        key_mumbai = generate_cache_key(
            method="GET",
            path="/weather",
            query_params=[("city", "Mumbai")],
        )
        assert key_delhi != key_mumbai

    def test_same_key_different_value_produces_different_key(self):
        key1 = generate_cache_key(
            method="GET", path="/items", query_params=[("page", "1")]
        )
        key2 = generate_cache_key(
            method="GET", path="/items", query_params=[("page", "2")]
        )
        assert key1 != key2

    def test_param_value_case_sensitive(self):
        """'delhi' and 'Delhi' are different values → different keys."""
        key1 = generate_cache_key(
            method="GET", path="/weather", query_params=[("city", "delhi")]
        )
        key2 = generate_cache_key(
            method="GET", path="/weather", query_params=[("city", "Delhi")]
        )
        assert key1 != key2


# ===========================================================================
# Example 4: Different HTTP METHODS → different keys
# ===========================================================================

class TestHttpMethodDifferentiation:
    """
    Example 4 from spec:
        GET  /users?id=10 → key A
        POST /users?id=10 → key B
        key A ≠ key B
    """

    def test_get_and_post_same_path_different_keys(self):
        key_get = generate_cache_key(
            method="GET",
            path="/users",
            query_params=[("id", "10")],
        )
        key_post = generate_cache_key(
            method="POST",
            path="/users",
            query_params=[("id", "10")],
        )
        assert key_get != key_post

    def test_method_case_insensitive_normalization(self):
        """'get' and 'GET' must produce the same key (normalized to uppercase)."""
        key_lower = generate_cache_key(method="get", path="/weather")
        key_upper = generate_cache_key(method="GET", path="/weather")
        assert key_lower == key_upper

    @pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
    def test_all_methods_produce_distinct_keys_for_same_path(self, method: str):
        """Every HTTP method should create a different key for the same path."""
        keys = [
            generate_cache_key(method=m, path="/resource")
            for m in ["GET", "POST", "PUT", "PATCH", "DELETE"]
        ]
        # All 5 keys must be unique
        assert len(set(keys)) == 5


# ===========================================================================
# Example 5: Different PATHS → different keys
# ===========================================================================

class TestPathDifferentiation:
    """
    Example 5 from spec:
        GET /users/10 → key A
        GET /users/11 → key B
        key A ≠ key B
    """

    def test_different_resource_ids_produce_different_keys(self):
        key1 = generate_cache_key(method="GET", path="/users/10")
        key2 = generate_cache_key(method="GET", path="/users/11")
        assert key1 != key2

    def test_different_paths_produce_different_keys(self):
        key1 = generate_cache_key(method="GET", path="/weather")
        key2 = generate_cache_key(method="GET", path="/stocks")
        assert key1 != key2

    def test_path_without_leading_slash_matches_with_slash(self):
        """
        'weather' and '/weather' must produce the same key after normalization.
        normalize_path() adds the leading slash automatically.
        """
        key1 = generate_cache_key(method="GET", path="weather")
        key2 = generate_cache_key(method="GET", path="/weather")
        assert key1 == key2


# ===========================================================================
# Example 6: Empty query parameters
# ===========================================================================

class TestEmptyQueryParameters:
    """
    Example 6 from spec:
        GET /health        → key A
        GET /health?       → key B (empty query string)
        Discuss: should these be equal?

    Decision: We treat None params and empty params the same way.
    Both normalize to an empty list [], producing the same canonical
    representation. This is the safest default.
    """

    def test_no_params_and_none_params_produce_same_key(self):
        """Passing no params at all must equal passing None explicitly."""
        key1 = generate_cache_key(method="GET", path="/health", query_params=None)
        key2 = generate_cache_key(method="GET", path="/health", query_params=[])
        assert key1 == key2

    def test_empty_params_consistent_across_calls(self):
        """Two calls with no params must always produce the same key."""
        key1 = generate_cache_key(method="GET", path="/health")
        key2 = generate_cache_key(method="GET", path="/health")
        assert key1 == key2


# ===========================================================================
# Example 7: Repeated query parameters
# ===========================================================================

class TestRepeatedQueryParameters:
    """
    Example 7 from spec:
        GET /items?id=1&id=2  → key A
        GET /items?id=2&id=1  → key B
        Design decision: key A ≠ key B (safe default)

    We sort by PARAMETER NAME but preserve the relative order of repeated
    values. This means id=1&id=2 and id=2&id=1 produce different keys
    because some APIs treat repeated-param order as semantically significant.
    """

    def test_repeated_params_different_order_produce_different_keys(self):
        """
        id=1&id=2 and id=2&id=1 should NOT produce the same key by default.
        This is the safe conservative choice.
        """
        key1 = generate_cache_key(
            method="GET",
            path="/items",
            query_params=[("id", "1"), ("id", "2")],
        )
        key2 = generate_cache_key(
            method="GET",
            path="/items",
            query_params=[("id", "2"), ("id", "1")],
        )
        assert key1 != key2

    def test_repeated_params_same_order_produce_same_key(self):
        """The same repeated params in the same order must always match."""
        key1 = generate_cache_key(
            method="GET", path="/items",
            query_params=[("id", "1"), ("id", "2")],
        )
        key2 = generate_cache_key(
            method="GET", path="/items",
            query_params=[("id", "1"), ("id", "2")],
        )
        assert key1 == key2


# ===========================================================================
# Example 8 & 9: JSON body normalization
# ===========================================================================

class TestBodyNormalization:
    """
    Examples 8 and 9 from spec:
        {"user_id": 10, "currency": "INR"} (key order A) → same key as
        {"currency": "INR", "user_id": 10} (key order B)

        {"currency": "INR"} → different key from {"currency": "USD"}
    """

    def test_equivalent_json_bodies_produce_same_key(self):
        """
        Example 8: Same JSON content, different insertion order → same key.
        """
        key1 = generate_cache_key(
            method="POST",
            path="/convert",
            body={"user_id": 10, "currency": "INR"},
        )
        key2 = generate_cache_key(
            method="POST",
            path="/convert",
            body={"currency": "INR", "user_id": 10},
        )
        assert key1 == key2

    def test_different_body_values_produce_different_keys(self):
        """
        Example 9: Same JSON structure, different values → different key.
        """
        key_inr = generate_cache_key(
            method="POST",
            path="/convert",
            body={"user_id": 10, "currency": "INR"},
        )
        key_usd = generate_cache_key(
            method="POST",
            path="/convert",
            body={"user_id": 10, "currency": "USD"},
        )
        assert key_inr != key_usd

    def test_none_body_and_absent_body_produce_same_key(self):
        """No body (GET) and explicit None body must produce the same key."""
        key1 = generate_cache_key(method="GET", path="/weather", body=None)
        key2 = generate_cache_key(method="GET", path="/weather")
        assert key1 == key2


# ===========================================================================
# Example 10: Selected header differentiation
# ===========================================================================

class TestHeaderNormalization:
    """
    Example 10 from spec:
        Accept-Language: en  → key A
        Accept-Language: hi  → key B  (if header is included)
    """

    def test_selected_header_affects_key(self):
        """If Accept-Language is selected, en and hi must produce different keys."""
        key_en = generate_cache_key(
            method="GET",
            path="/weather",
            headers={"accept-language": "en"},
            include_headers=["accept-language"],
        )
        key_hi = generate_cache_key(
            method="GET",
            path="/weather",
            headers={"accept-language": "hi"},
            include_headers=["accept-language"],
        )
        assert key_en != key_hi

    def test_non_selected_header_does_not_affect_key(self):
        """
        User-Agent is a volatile header that must NOT be part of the key.
        Requests with different User-Agents but identical params must
        produce the same key.
        """
        key1 = generate_cache_key(
            method="GET",
            path="/weather",
            headers={"user-agent": "curl/7.x"},
            include_headers=None,  # no headers selected
        )
        key2 = generate_cache_key(
            method="GET",
            path="/weather",
            headers={"user-agent": "Mozilla/5.0"},
            include_headers=None,
        )
        assert key1 == key2

    def test_authorization_excluded_even_if_listed(self):
        """
        Authorization must never be part of the cache key.
        Tokens are sensitive and user-specific — including them risks
        leaking them in logs or causing cache entries to never hit.
        """
        key_with_auth = generate_cache_key(
            method="GET",
            path="/weather",
            headers={"authorization": "Bearer secret-token"},
            include_headers=["authorization"],
        )
        key_no_auth = generate_cache_key(
            method="GET",
            path="/weather",
            headers={},
            include_headers=["authorization"],
        )
        # Authorization is excluded → both must produce the same key
        assert key_with_auth == key_no_auth


# ===========================================================================
# Key Format Validation
# ===========================================================================

class TestKeyFormat:
    """Validate that keys have the expected structure and format."""

    def test_key_starts_with_version_prefix(self):
        """Every key must start with 'api-cache:v1:'."""
        key = generate_cache_key(method="GET", path="/test")
        assert key.startswith(KEY_PREFIX)

    def test_key_digest_is_64_hex_characters(self):
        """The digest portion must be exactly 64 lowercase hex characters."""
        key = generate_cache_key(method="GET", path="/test")
        digest = key[len(KEY_PREFIX):]
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_key_matches_expected_pattern(self):
        """The full key must match 'api-cache:v1:<64 hex chars>'."""
        key = generate_cache_key(method="GET", path="/test")
        assert is_valid_key(key), f"Key did not match expected pattern: {key}"

    def test_key_does_not_contain_raw_path(self):
        """
        The key is a hash — it must not contain the plaintext path.
        This prevents accidentally leaking sensitive URL segments.
        """
        key = generate_cache_key(method="GET", path="/very-secret-path")
        assert "/very-secret-path" not in key

    def test_key_does_not_contain_raw_param_values(self):
        """The key must not contain plaintext parameter values."""
        key = generate_cache_key(
            method="GET",
            path="/weather",
            query_params=[("city", "SuperSecretCity")],
        )
        assert "SuperSecretCity" not in key


# ===========================================================================
# Internal Helper Tests
# ===========================================================================

class TestInternalHelpers:
    """Tests for the private helper functions."""

    def test_build_canonical_request_structure(self):
        """The canonical dict must have the expected keys and structure."""
        canonical = _build_canonical_request(
            method="GET",
            path="/weather",
            query_params=[("city", "Delhi")],
            headers={},
            body=None,
        )
        assert canonical["method"] == "GET"
        assert canonical["path"] == "/weather"
        assert canonical["query"] == [["city", "Delhi"]]
        assert canonical["headers"] == {}
        assert canonical["body"] is None

    def test_serialize_canonical_is_compact(self):
        """Serialized output must have no extra whitespace."""
        canonical = _build_canonical_request(
            method="GET", path="/test",
            query_params=[], headers={}, body=None,
        )
        result = _serialize_canonical(canonical)
        assert "  " not in result   # no double spaces
        assert ": " not in result   # no "key: value" spacing
        assert ", " not in result   # no ", " spacing

    def test_sha256_returns_64_char_hex(self):
        """SHA-256 digest must be exactly 64 lowercase hex characters."""
        digest = _sha256_hex("hello")
        assert len(digest) == 64
        assert digest == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    def test_sha256_is_deterministic(self):
        """Same input must always produce the same digest."""
        assert _sha256_hex("test") == _sha256_hex("test")

    def test_sha256_different_inputs_different_digests(self):
        """Different inputs must produce different digests."""
        assert _sha256_hex("hello") != _sha256_hex("world")


# ===========================================================================
# Convenience Wrapper Tests
# ===========================================================================

class TestGenerateKeyFromRequest:
    """Tests for the FastAPI-friendly wrapper generate_key_from_request()."""

    def test_basic_call_returns_valid_key(self):
        key = generate_key_from_request(resource_id="weather")
        assert is_valid_key(key)

    def test_same_resource_id_same_key(self):
        key1 = generate_key_from_request("weather")
        key2 = generate_key_from_request("weather")
        assert key1 == key2

    def test_different_resource_ids_different_keys(self):
        key1 = generate_key_from_request("weather")
        key2 = generate_key_from_request("stocks")
        assert key1 != key2

    def test_query_param_ordering_handled(self):
        """Dict insertion order must not affect the key."""
        key1 = generate_key_from_request(
            "weather", query_params={"city": "Delhi", "units": "metric"}
        )
        key2 = generate_key_from_request(
            "weather", query_params={"units": "metric", "city": "Delhi"}
        )
        assert key1 == key2

    def test_no_params_and_none_produce_same_key(self):
        key1 = generate_key_from_request("health", query_params=None)
        key2 = generate_key_from_request("health", query_params={})
        assert key1 == key2


# ===========================================================================
# Regression: Existing proxy tests still import correctly
# ===========================================================================

class TestRegressionImports:
    """Ensure Phase 4 additions do not break existing Phase 1-3 imports."""

    def test_proxy_client_still_importable(self):
        from app.proxy.client import ProxyClient, UpstreamError  # noqa: F401

    def test_optimizer_app_still_importable(self):
        from app.main import app  # noqa: F401

    def test_mock_api_still_importable(self):
        from mock_api.main import app as mock_app  # noqa: F401

    def test_normalizer_still_importable(self):
        from app.requests.normalizer import (  # noqa: F401
            normalize_method,
            normalize_path,
            normalize_query_params,
            normalize_headers,
            normalize_body,
        )
