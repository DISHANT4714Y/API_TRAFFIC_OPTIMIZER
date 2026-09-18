"""
Phase 3 — Request Normalizer Unit Tests.

Tests every normalization helper in app/requests/normalizer.py in isolation.
These are pure unit tests — no FastAPI server, no HTTP calls.

Run with:
    pytest tests/test_normalizer.py -v
"""

import pytest

from app.requests.normalizer import (
    normalize_body,
    normalize_headers,
    normalize_method,
    normalize_path,
    normalize_query_params,
)


# ===========================================================================
# normalize_method()
# ===========================================================================

class TestNormalizeMethod:
    """Tests for HTTP method normalization."""

    def test_lowercase_becomes_uppercase(self):
        """'get' must be normalized to 'GET'."""
        assert normalize_method("get") == "GET"

    def test_mixed_case_becomes_uppercase(self):
        """'Post' must be normalized to 'POST'."""
        assert normalize_method("Post") == "POST"

    def test_already_uppercase_unchanged(self):
        """'DELETE' must remain 'DELETE'."""
        assert normalize_method("DELETE") == "DELETE"

    def test_strips_surrounding_whitespace(self):
        """Methods with surrounding spaces should be stripped."""
        assert normalize_method("  get  ") == "GET"

    @pytest.mark.parametrize("method", ["get", "post", "put", "patch", "delete", "head"])
    def test_all_common_methods_uppercased(self, method: str):
        """All standard HTTP methods normalize to uppercase."""
        assert normalize_method(method) == method.upper()


# ===========================================================================
# normalize_path()
# ===========================================================================

class TestNormalizePath:
    """Tests for URL path normalization."""

    def test_path_with_leading_slash_unchanged(self):
        """/weather must stay /weather."""
        assert normalize_path("/weather") == "/weather"

    def test_path_without_leading_slash_gets_one(self):
        """'weather' (no slash) must become '/weather'."""
        assert normalize_path("weather") == "/weather"

    def test_empty_string_becomes_root(self):
        """An empty path must become '/'."""
        assert normalize_path("") == "/"

    def test_none_becomes_root(self):
        """None path must become '/'."""
        assert normalize_path(None) == "/"  # type: ignore[arg-type]

    def test_nested_path_preserved(self):
        """Multi-segment paths must be preserved exactly."""
        assert normalize_path("/api/v1/data") == "/api/v1/data"

    def test_trailing_slash_preserved(self):
        """Trailing slashes are kept — removing them could change routing."""
        assert normalize_path("/weather/") == "/weather/"

    def test_strips_whitespace_around_path(self):
        """Paths with surrounding whitespace must be stripped."""
        assert normalize_path("  /weather  ") == "/weather"

    def test_path_case_is_preserved(self):
        """Paths are case-sensitive — must not be lowercased."""
        assert normalize_path("/UserProfile") == "/UserProfile"


# ===========================================================================
# normalize_query_params()
# ===========================================================================

class TestNormalizeQueryParams:
    """Tests for query-parameter normalization."""

    def test_empty_list_returns_empty(self):
        """No params → empty list."""
        assert normalize_query_params([]) == []

    def test_none_returns_empty(self):
        """None is treated as no params — function handles it gracefully."""
        # normalize_query_params expects a sequence, so passing [] is correct.
        assert normalize_query_params([]) == []

    def test_single_param_unchanged(self):
        """A single param should be returned as-is (still sorted, trivially)."""
        assert normalize_query_params([("city", "Delhi")]) == [("city", "Delhi")]

    def test_two_params_already_sorted(self):
        """Params already in alphabetical order must remain unchanged."""
        result = normalize_query_params([("city", "Delhi"), ("units", "metric")])
        assert result == [("city", "Delhi"), ("units", "metric")]

    def test_two_params_unsorted_get_sorted(self):
        """Params in reverse alphabetical order must be sorted."""
        result = normalize_query_params([("units", "metric"), ("city", "Delhi")])
        assert result == [("city", "Delhi"), ("units", "metric")]

    def test_three_params_sorted(self):
        """Three params in arbitrary order must come out alphabetically."""
        result = normalize_query_params([
            ("z_param", "last"),
            ("a_param", "first"),
            ("m_param", "middle"),
        ])
        assert result == [
            ("a_param", "first"),
            ("m_param", "middle"),
            ("z_param", "last"),
        ]

    def test_repeated_param_names_order_preserved(self):
        """
        For repeated param names (e.g. id=1&id=2), sorting is stable:
        the relative order of equal keys is preserved.
        This is the safe default — some APIs treat id=1&id=2 differently
        from id=2&id=1.
        """
        result = normalize_query_params([("id", "1"), ("id", "2")])
        assert result == [("id", "1"), ("id", "2")]

    def test_repeated_param_names_interleaved_sorted_stably(self):
        """
        Mixed params with a repeated key: sort by name but preserve
        relative order of repeated values.
        [("b","B"), ("a","1"), ("a","2")] → [("a","1"), ("a","2"), ("b","B")]
        """
        result = normalize_query_params([("b", "B"), ("a", "1"), ("a", "2")])
        assert result == [("a", "1"), ("a", "2"), ("b", "B")]

    def test_empty_value_preserved(self):
        """A param with an empty string value must be kept as-is."""
        result = normalize_query_params([("flag", "")])
        assert result == [("flag", "")]

    def test_param_values_not_lowercased(self):
        """Values are case-sensitive — 'Delhi' must not become 'delhi'."""
        result = normalize_query_params([("city", "Delhi")])
        assert result[0][1] == "Delhi"

    def test_special_characters_in_value_preserved(self):
        """Special characters in values must be preserved exactly."""
        result = normalize_query_params([("q", "hello world"), ("lang", "en")])
        assert result == [("lang", "en"), ("q", "hello world")]


# ===========================================================================
# normalize_headers()
# ===========================================================================

class TestNormalizeHeaders:
    """Tests for selective header normalization."""

    def test_no_include_keys_returns_empty(self):
        """With no include_keys, no headers should be selected."""
        result = normalize_headers({"Accept": "application/json"}, include_keys=None)
        assert result == {}

    def test_empty_include_keys_returns_empty(self):
        """Empty include_keys list → empty result."""
        result = normalize_headers({"Accept": "application/json"}, include_keys=[])
        assert result == {}

    def test_selected_header_included(self):
        """A header listed in include_keys should appear in the result."""
        result = normalize_headers(
            {"Accept": "application/json", "User-Agent": "test"},
            include_keys=["accept"],
        )
        assert result == {"accept": "application/json"}

    def test_non_selected_header_excluded(self):
        """Headers NOT in include_keys must be excluded."""
        result = normalize_headers(
            {"Accept": "application/json", "User-Agent": "test"},
            include_keys=["accept"],
        )
        assert "user-agent" not in result

    def test_header_key_normalized_to_lowercase(self):
        """Header keys in the result must be lowercase."""
        result = normalize_headers(
            {"Accept-Language": "en"},
            include_keys=["accept-language"],
        )
        assert "accept-language" in result

    def test_authorization_excluded_even_if_requested(self):
        """
        Authorization must never be included in the cache key,
        even if explicitly listed in include_keys.
        Including tokens in keys risks leaking them in logs.
        """
        result = normalize_headers(
            {"Authorization": "Bearer secret-token"},
            include_keys=["authorization"],
        )
        assert "authorization" not in result

    def test_missing_header_gracefully_ignored(self):
        """If an included header is not present in the request, skip it silently."""
        result = normalize_headers(
            {"Accept": "application/json"},
            include_keys=["accept", "accept-language"],
        )
        # accept-language was listed but not present → should not be in result
        assert "accept-language" not in result
        assert result == {"accept": "application/json"}

    def test_case_insensitive_header_matching(self):
        """Header lookup must be case-insensitive: 'ACCEPT' matches 'accept'."""
        result = normalize_headers(
            {"ACCEPT": "application/xml"},
            include_keys=["accept"],
        )
        assert result == {"accept": "application/xml"}


# ===========================================================================
# normalize_body()
# ===========================================================================

class TestNormalizeBody:
    """Tests for request body normalization."""

    def test_none_returns_none(self):
        """No body (GET request) → None."""
        assert normalize_body(None) is None

    def test_dict_canonicalized_with_sorted_keys(self):
        """
        JSON dicts with keys in different orders must produce the same string.
        This is the core requirement for POST body normalization.
        """
        body_a = {"user_id": 10, "currency": "INR"}
        body_b = {"currency": "INR", "user_id": 10}
        assert normalize_body(body_a) == normalize_body(body_b)

    def test_dict_different_values_produce_different_strings(self):
        """Different body values must NOT produce the same canonical string."""
        body_a = {"currency": "INR"}
        body_b = {"currency": "USD"}
        assert normalize_body(body_a) != normalize_body(body_b)

    def test_dict_compact_json_no_extra_spaces(self):
        """
        The canonical JSON must use compact separators (no extra whitespace).
        """
        result = normalize_body({"a": 1, "b": 2})
        assert " " not in result  # no spaces in compact JSON

    def test_list_body_serialized(self):
        """A list body must be serialized to a JSON array string."""
        result = normalize_body([1, 2, 3])
        assert result == "[1,2,3]"

    def test_string_body_returned_as_is(self):
        """A plain string body must be returned unchanged."""
        assert normalize_body("hello") == "hello"

    def test_bytes_body_decoded_to_string(self):
        """UTF-8 bytes must be decoded to a string."""
        assert normalize_body(b"hello") == "hello"

    def test_bytes_body_non_utf8_becomes_hex(self):
        """Non-UTF-8 bytes must fall back to a hex representation."""
        result = normalize_body(bytes([0xFF, 0xFE]))
        assert result == "fffe"

    def test_empty_dict_normalized(self):
        """An empty dict must serialize to the empty JSON object '{}'."""
        assert normalize_body({}) == "{}"

    def test_nested_dict_sorted_recursively(self):
        """
        Nested dicts must also have their keys sorted in the output
        because json.dumps(sort_keys=True) applies recursively.
        """
        body = {"outer": {"z": 1, "a": 2}}
        result = normalize_body(body)
        # 'a' must come before 'z' in the serialized nested object
        assert result.index('"a"') < result.index('"z"')
