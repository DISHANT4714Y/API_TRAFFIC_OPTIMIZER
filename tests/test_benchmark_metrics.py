"""
tests/test_benchmark_metrics.py — Phase 2B

Unit tests for benchmarks/metrics.py and benchmarks/workloads.py.

All tests use synthetic data explicitly created here.
No live services are contacted, no JSON files are read, and
no actual benchmark results are used or referenced.

Run with:
    pytest tests/test_benchmark_metrics.py -v
"""

import json
import math
import tempfile
from pathlib import Path

import pytest

from benchmarks.metrics import (
    build_result_record,
    compute_error_rate,
    compute_latency_stats,
    compute_throughput,
    compute_upstream_reduction,
    make_run_id,
    percentile,
    save_result,
)
from benchmarks.workloads import WorkloadProfile, generate_resource_ids


# ===========================================================================
# percentile()
# ===========================================================================

class TestPercentile:
    """Tests for the percentile interpolation helper."""

    def test_single_element_returns_that_element(self):
        assert percentile([42.0], 50) == 42.0

    def test_p0_returns_minimum(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert percentile(data, 0) == 1.0

    def test_p100_returns_maximum(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert percentile(data, 100) == 5.0

    def test_p50_of_sorted_odd_list(self):
        # Median of [1, 2, 3, 4, 5] is 3.0
        assert percentile([1.0, 2.0, 3.0, 4.0, 5.0], 50) == 3.0

    def test_p50_of_sorted_even_list(self):
        # Median of [1, 2, 3, 4] is 2.5
        assert percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.5

    def test_unsorted_input_gives_same_result_as_sorted(self):
        assert percentile([5.0, 1.0, 3.0], 50) == percentile([1.0, 3.0, 5.0], 50)

    def test_p95_of_100_uniform_values(self):
        # [1, 2, ..., 100] — P95 should be near 95.05
        data = [float(i) for i in range(1, 101)]
        result = percentile(data, 95)
        # numpy.percentile([1..100], 95) = 95.05 (linear interpolation)
        assert abs(result - 95.05) < 0.01

    def test_empty_raises_value_error(self):
        with pytest.raises(ValueError, match="empty"):
            percentile([], 50)

    def test_p_below_0_raises(self):
        with pytest.raises(ValueError, match="\\[0, 100\\]"):
            percentile([1.0, 2.0], -1)

    def test_p_above_100_raises(self):
        with pytest.raises(ValueError, match="\\[0, 100\\]"):
            percentile([1.0, 2.0], 101)

    def test_identical_values_return_that_value(self):
        assert percentile([7.0, 7.0, 7.0], 75) == 7.0


# ===========================================================================
# compute_latency_stats()
# ===========================================================================

class TestComputeLatencyStats:
    """Tests for summary latency statistics."""

    def test_empty_returns_all_none(self):
        stats = compute_latency_stats([])
        assert all(v is None for v in stats.values())

    def test_known_values(self):
        data = [10.0, 20.0, 30.0, 40.0, 50.0]
        stats = compute_latency_stats(data)
        assert stats["mean_ms"] == pytest.approx(30.0, abs=0.01)
        assert stats["p50_ms"]  == pytest.approx(30.0, abs=0.01)
        assert stats["min_ms"]  == 10.0
        assert stats["max_ms"]  == 50.0

    def test_p99_none_when_n_below_threshold(self):
        # Default min_n_for_p99 = 100; 5 samples → None
        stats = compute_latency_stats([float(i) for i in range(5)])
        assert stats["p99_ms"] is None

    def test_p99_present_when_n_at_threshold(self):
        # Exactly 100 samples → P99 should be computed
        data = [float(i) for i in range(1, 101)]
        stats = compute_latency_stats(data, min_n_for_p99=100)
        assert stats["p99_ms"] is not None

    def test_custom_min_n_for_p99(self):
        # With min_n_for_p99=5, a 5-element list should produce a value
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        stats = compute_latency_stats(data, min_n_for_p99=5)
        assert stats["p99_ms"] is not None

    def test_single_element(self):
        stats = compute_latency_stats([100.0])
        assert stats["mean_ms"] == 100.0
        assert stats["min_ms"]  == 100.0
        assert stats["max_ms"]  == 100.0
        assert stats["p50_ms"]  == 100.0
        assert stats["p95_ms"]  == 100.0

    def test_output_keys_present(self):
        stats = compute_latency_stats([1.0, 2.0])
        assert set(stats.keys()) == {"mean_ms", "p50_ms", "p95_ms", "p99_ms", "min_ms", "max_ms"}


# ===========================================================================
# compute_throughput()
# ===========================================================================

class TestComputeThroughput:
    """Throughput = attempted / duration_s."""

    def test_basic_calculation(self):
        # 100 requests in 10 seconds = 10.0 rps
        assert compute_throughput(100, 10.0) == pytest.approx(10.0, abs=0.001)

    def test_fractional_duration(self):
        # 50 requests in 2.5 seconds = 20.0 rps
        assert compute_throughput(50, 2.5) == pytest.approx(20.0, abs=0.001)

    def test_zero_duration_returns_none(self):
        assert compute_throughput(100, 0.0) is None

    def test_negative_duration_returns_none(self):
        assert compute_throughput(100, -1.0) is None

    def test_zero_requests(self):
        # 0 attempted in 5 s → 0.0 rps (not None)
        assert compute_throughput(0, 5.0) == 0.0


# ===========================================================================
# compute_error_rate()
# ===========================================================================

class TestComputeErrorRate:
    """Error rate = (failed / total) × 100."""

    def test_no_failures(self):
        assert compute_error_rate(0, 100) == 0.0

    def test_all_failures(self):
        assert compute_error_rate(100, 100) == 100.0

    def test_partial_failures(self):
        # 5/20 = 25%
        assert compute_error_rate(5, 20) == pytest.approx(25.0, abs=0.001)

    def test_zero_total_returns_none(self):
        assert compute_error_rate(0, 0) is None

    def test_one_failure_in_hundred(self):
        assert compute_error_rate(1, 100) == pytest.approx(1.0, abs=0.001)


# ===========================================================================
# compute_upstream_reduction()
# ===========================================================================

class TestComputeUpstreamReduction:
    """Upstream reduction = ((baseline - optimized) / baseline) × 100."""

    def test_full_reduction(self):
        # Optimized made 0 upstream calls → 100% reduction
        assert compute_upstream_reduction(100, 0) == 100.0

    def test_no_reduction(self):
        # Both made the same number → 0% reduction
        assert compute_upstream_reduction(100, 100) == 0.0

    def test_partial_reduction(self):
        # Baseline: 100, Optimized: 10 → 90% reduction
        result = compute_upstream_reduction(100, 10)
        assert result == pytest.approx(90.0, abs=0.01)

    def test_negative_reduction(self):
        # Optimized made MORE upstream calls — documented as negative, not an error
        result = compute_upstream_reduction(10, 20)
        assert result == pytest.approx(-100.0, abs=0.01)

    def test_baseline_zero_returns_none(self):
        # Denominator undefined
        assert compute_upstream_reduction(0, 0) is None
        assert compute_upstream_reduction(0, 5) is None

    def test_baseline_none_returns_none(self):
        assert compute_upstream_reduction(None, 10) is None

    def test_optimized_none_returns_none(self):
        assert compute_upstream_reduction(100, None) is None

    def test_exact_half_reduction(self):
        assert compute_upstream_reduction(100, 50) == pytest.approx(50.0, abs=0.01)


# ===========================================================================
# build_result_record()
# ===========================================================================

class TestBuildResultRecord:
    """Test the result record schema builder."""

    def _make_record(self, **overrides):
        defaults = dict(
            run_id="test-run-001",
            workload="W-REP",
            mode="optimized",
            config={"n_requests": 10, "concurrency": 2, "mock_delay_ms": 100},
            warm_up_info={"requests": 0, "note": "no warm-up"},
            latencies_ms=[10.0, 20.0, 30.0, 15.0, 25.0],
            attempted=5,
            successful=5,
            failed=0,
            errors=[],
            benchmark_duration_s=1.5,
            x_cache_hit_count=4,
            x_cache_miss_count=1,
            server_metrics={"optimizer_metrics": {}, "mock_api_stats": {}},
        )
        defaults.update(overrides)
        return build_result_record(**defaults)

    def test_required_top_level_keys(self):
        record = self._make_record()
        required = {"run_id", "timestamp", "workload", "mode", "config",
                    "environment", "warm_up", "results", "server_metrics", "errors"}
        assert required.issubset(record.keys())

    def test_results_required_keys(self):
        record = self._make_record()
        r = record["results"]
        assert "attempted_requests"  in r
        assert "successful_requests" in r
        assert "failed_requests"     in r
        assert "error_rate_pct"      in r
        assert "mean_latency_ms"     in r
        assert "p50_latency_ms"      in r
        assert "p95_latency_ms"      in r
        assert "p99_latency_ms"      in r
        assert "throughput_rps"      in r
        assert "benchmark_duration_s" in r
        assert "latencies_ms"        in r

    def test_latencies_stored_verbatim(self):
        lats = [10.0, 20.0, 30.0]
        record = self._make_record(latencies_ms=lats, attempted=3, successful=3, failed=0)
        assert record["results"]["latencies_ms"] == pytest.approx(lats, abs=0.001)

    def test_p99_none_when_sample_small(self):
        # 5 samples < 100 threshold
        record = self._make_record()
        assert record["results"]["p99_latency_ms"] is None

    def test_error_rate_calculated(self):
        record = self._make_record(attempted=10, successful=8, failed=2)
        assert record["results"]["error_rate_pct"] == pytest.approx(20.0, abs=0.001)

    def test_x_cache_fields_preserved(self):
        record = self._make_record(x_cache_hit_count=90, x_cache_miss_count=10)
        assert record["results"]["x_cache_hit_count"]  == 90
        assert record["results"]["x_cache_miss_count"] == 10

    def test_x_cache_none_preserved(self):
        # Baseline path has no X-Cache header → None
        record = self._make_record(x_cache_hit_count=None, x_cache_miss_count=None)
        assert record["results"]["x_cache_hit_count"]  is None
        assert record["results"]["x_cache_miss_count"] is None

    def test_throughput_computed(self):
        # 5 attempted in 1.5 s → ~3.333 rps
        record = self._make_record()
        assert record["results"]["throughput_rps"] == pytest.approx(5 / 1.5, abs=0.01)

    def test_zero_duration_throughput_none(self):
        record = self._make_record(benchmark_duration_s=0.0)
        assert record["results"]["throughput_rps"] is None

    def test_run_id_preserved(self):
        record = self._make_record(run_id="my-custom-id")
        assert record["run_id"] == "my-custom-id"


# ===========================================================================
# save_result()
# ===========================================================================

class TestSaveResult:
    """Test JSON serialisation and non-overwrite guarantee."""

    def _make_minimal_record(self, run_id="test-save-001"):
        return {
            "run_id": run_id,
            "timestamp": "2026-01-01T00:00:00+00:00",
            "workload": "W-REP",
            "mode": "optimized",
            "results": {"latencies_ms": [1.0, 2.0]},
        }

    def test_file_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_result(self._make_minimal_record(), Path(tmpdir))
            assert path.exists()

    def test_file_is_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = save_result(self._make_minimal_record(), Path(tmpdir))
            data = json.loads(path.read_text())
            assert data["run_id"] == "test-save-001"

    def test_no_overwrite_on_collision(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rec  = self._make_minimal_record("collision-id")
            p1   = save_result(rec, Path(tmpdir))
            p2   = save_result(rec, Path(tmpdir))
            assert p1 != p2
            assert p1.exists()
            assert p2.exists()

    def test_creates_results_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sub = Path(tmpdir) / "deep" / "nested"
            assert not sub.exists()
            save_result(self._make_minimal_record(), sub)
            assert sub.exists()


# ===========================================================================
# make_run_id()
# ===========================================================================

class TestMakeRunId:
    """Run IDs must be unique and human-readable."""

    def test_contains_workload(self):
        run_id = make_run_id("W-REP", "optimized", 10)
        assert "W-REP" in run_id

    def test_contains_mode(self):
        run_id = make_run_id("W-MIX", "baseline", 5)
        assert "baseline" in run_id

    def test_contains_concurrency(self):
        run_id = make_run_id("W-UNQ", "optimized", 20)
        assert "c20" in run_id

    def test_format_is_non_empty_string(self):
        run_id = make_run_id("W-REP", "optimized", 10)
        assert isinstance(run_id, str)
        assert len(run_id) > 10


# ===========================================================================
# generate_resource_ids() from workloads.py
# ===========================================================================

class TestGenerateResourceIds:
    """Workload resource ID generators."""

    def test_repeated_all_same(self):
        ids = generate_resource_ids(WorkloadProfile.REPEATED, 50)
        assert len(set(ids)) == 1
        assert len(ids) == 50

    def test_unique_all_distinct(self):
        ids = generate_resource_ids(WorkloadProfile.UNIQUE, 50)
        assert len(set(ids)) == 50
        assert len(ids) == 50

    def test_mixed_within_pool(self):
        pool_size = 7
        ids = generate_resource_ids(WorkloadProfile.MIXED, 100, pool_size=pool_size)
        assert len(ids) == 100
        assert all(f"bench-resource-{i}" in ids for i in range(pool_size))
        # All IDs must come from the pool
        pool = {f"bench-resource-{i}" for i in range(pool_size)}
        assert all(rid in pool for rid in ids)

    def test_same_seed_deterministic(self):
        ids1 = generate_resource_ids(WorkloadProfile.MIXED, 50, seed=99)
        ids2 = generate_resource_ids(WorkloadProfile.MIXED, 50, seed=99)
        assert ids1 == ids2

    def test_different_seeds_differ_for_mixed(self):
        ids1 = generate_resource_ids(WorkloadProfile.MIXED, 50, seed=1)
        ids2 = generate_resource_ids(WorkloadProfile.MIXED, 50, seed=2)
        assert ids1 != ids2

    def test_warm_same_as_repeated(self):
        ids = generate_resource_ids(WorkloadProfile.WARM, 20)
        assert len(set(ids)) == 1

    def test_concurrent_same_as_repeated(self):
        ids = generate_resource_ids(WorkloadProfile.CONCURRENT, 20)
        assert len(set(ids)) == 1

    def test_coalescing_same_as_repeated(self):
        ids = generate_resource_ids(WorkloadProfile.COALESCING, 20)
        assert len(set(ids)) == 1

    def test_n_requests_zero_raises(self):
        with pytest.raises(ValueError, match="n_requests"):
            generate_resource_ids(WorkloadProfile.REPEATED, 0)

    def test_pool_size_zero_raises(self):
        with pytest.raises(ValueError, match="pool_size"):
            generate_resource_ids(WorkloadProfile.MIXED, 10, pool_size=0)

    def test_length_always_equals_n_requests(self):
        for profile in WorkloadProfile:
            ids = generate_resource_ids(profile, 37)
            assert len(ids) == 37, f"Failed for {profile}"


# ===========================================================================
# Edge cases — empty / boundary inputs
# ===========================================================================

class TestEdgeCases:
    """Boundary and stress tests."""

    def test_latency_stats_single_value(self):
        stats = compute_latency_stats([500.0])
        assert stats["mean_ms"]  == 500.0
        assert stats["min_ms"]   == 500.0
        assert stats["max_ms"]   == 500.0
        assert stats["p50_ms"]   == 500.0
        assert stats["p95_ms"]   == 500.0
        assert stats["p99_ms"]   is None  # n=1 < 100

    def test_all_metrics_zero_requests(self):
        assert compute_error_rate(0, 0)         is None
        assert compute_throughput(0, 0.0)       is None
        assert compute_upstream_reduction(0, 0) is None

    def test_upstream_reduction_symmetric(self):
        # Switching baseline and optimized must produce the sign-opposite reduction
        r1 = compute_upstream_reduction(100, 10)   # 90% reduction
        r2 = compute_upstream_reduction(10, 100)   # -900% (more upstream calls)
        assert r1 == pytest.approx(90.0,   abs=0.01)
        assert r2 == pytest.approx(-900.0, abs=0.01)

    def test_percentile_two_elements_p50(self):
        # P50 of [1, 3] with linear interp = 2.0
        assert percentile([1.0, 3.0], 50) == pytest.approx(2.0, abs=0.001)


# ===========================================================================
# Configuration validation tests
# ===========================================================================

from benchmarks.run_benchmark import validate_config, summarise_request_results
from benchmarks.metrics import save_result_csv


class TestConfigValidation:
    """Tests for benchmark runner configuration validation."""

    def _valid_cfg(self):
        return {
            "mode": "optimized",
            "workload": "W-REP",
            "n_requests": 100,
            "concurrency": 10,
            "warm_up_requests": 0,
            "mock_delay_ms": 100,
            "pool_size": 10,
            "random_seed": 42,
            "timeout_s": 10.0,
            "repetitions": 1,
            "optimizer_url": "http://127.0.0.1:8000",
            "mock_api_url": "http://127.0.0.1:8001",
        }

    def test_valid_config_passes(self):
        cfg = self._valid_cfg()
        validate_config(cfg)  # Should not raise

    def test_invalid_n_requests(self):
        cfg = self._valid_cfg()
        cfg["n_requests"] = 0
        with pytest.raises(ValueError, match="--n-requests"):
            validate_config(cfg)

    def test_invalid_concurrency_zero(self):
        cfg = self._valid_cfg()
        cfg["concurrency"] = 0
        with pytest.raises(ValueError, match="--concurrency"):
            validate_config(cfg)

    def test_concurrency_exceeds_n_requests(self):
        cfg = self._valid_cfg()
        cfg["n_requests"] = 5
        cfg["concurrency"] = 10
        with pytest.raises(ValueError, match="exceeds"):
            validate_config(cfg)

    def test_invalid_warm_up_negative(self):
        cfg = self._valid_cfg()
        cfg["warm_up_requests"] = -1
        with pytest.raises(ValueError, match="--warm-up"):
            validate_config(cfg)

    def test_invalid_mock_delay_negative(self):
        cfg = self._valid_cfg()
        cfg["mock_delay_ms"] = -5
        with pytest.raises(ValueError, match="--mock-delay-ms"):
            validate_config(cfg)

    def test_invalid_pool_size(self):
        cfg = self._valid_cfg()
        cfg["pool_size"] = 0
        with pytest.raises(ValueError, match="--pool-size"):
            validate_config(cfg)

    def test_invalid_timeout(self):
        cfg = self._valid_cfg()
        cfg["timeout_s"] = 0.0
        with pytest.raises(ValueError, match="--timeout"):
            validate_config(cfg)

    def test_invalid_repetitions(self):
        cfg = self._valid_cfg()
        cfg["repetitions"] = 0
        with pytest.raises(ValueError, match="--repetitions"):
            validate_config(cfg)

    def test_invalid_mode(self):
        cfg = self._valid_cfg()
        cfg["mode"] = "invalid_mode"
        with pytest.raises(ValueError, match="--mode"):
            validate_config(cfg)

    def test_invalid_workload(self):
        cfg = self._valid_cfg()
        cfg["workload"] = "W-UNKNOWN"
        with pytest.raises(ValueError, match="--workload"):
            validate_config(cfg)


# ===========================================================================
# CSV output serialization & Error/Timeout recording tests
# ===========================================================================

class TestSerializationAndErrorRecording:
    """Tests for CSV output serialization and error/timeout recording."""

    def test_save_result_csv_creates_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            record = {
                "run_id": "test-csv-run-001",
                "timestamp": "2026-10-12T00:00:00+00:00",
                "workload": "W-REP",
                "mode": "optimized",
                "config": {"n_requests": 10, "concurrency": 2, "mock_delay_ms": 10},
                "results": {
                    "attempted_requests": 10,
                    "successful_requests": 10,
                    "failed_requests": 0,
                    "error_rate_pct": 0.0,
                    "mean_latency_ms": 15.2,
                    "p50_latency_ms": 14.8,
                    "p95_latency_ms": 18.0,
                    "p99_latency_ms": None,
                    "min_latency_ms": 12.0,
                    "max_latency_ms": 19.5,
                    "throughput_rps": 50.0,
                    "benchmark_duration_s": 0.2,
                    "x_cache_hit_count": 9,
                    "x_cache_miss_count": 1,
                },
            }
            csv_path = save_result_csv(record, out_dir)
            assert csv_path.exists()
            assert (out_dir / "summary.csv").exists()
            content = csv_path.read_text(encoding="utf-8")
            assert "test-csv-run-001" in content
            assert "W-REP" in content

    def test_summarise_request_results_with_timeouts_and_errors(self):
        raw_synthetic = [
            {"ok": True, "status": 200, "latency_ms": 12.0, "x_cache": "HIT", "error": ""},
            {"ok": True, "status": 200, "latency_ms": 14.0, "x_cache": "MISS", "error": ""},
            {"ok": False, "status": 500, "latency_ms": 50.0, "x_cache": "ABSENT", "error": "HTTP 500"},
            {"ok": False, "status": 0, "latency_ms": 1000.0, "x_cache": "ABSENT", "error": "TimeoutError: ReadTimeout"},
        ]
        lats, succ, fail, errs, hits, misses = summarise_request_results(raw_synthetic)
        assert len(lats) == 4
        assert succ == 2
        assert fail == 2
        assert len(errs) == 2
        assert errs[0]["status"] == 500
        assert errs[1]["status"] == 0
        assert "TimeoutError" in errs[1]["error"]
        assert hits == 1
        assert misses == 1

