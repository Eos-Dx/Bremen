"""Tests for symmetry signal computation (PR0092).

Covers:
- symmetry_signals field exists in decision support report.
- All 5 signals are always present.
- Missing reference statistics → all not_available.
- Missing per-signal ref stats → not_available for that signal.
- Only allowed difference_level values emitted.
- No raw feature values in external output.
- No raw feature values or cutoffs in internal output.
- Feature-to-signal mapping covers all 15 features.
- No mockup/sample values used.
- Backward compatibility of build_decision_support_report().
- Decision vocabulary unchanged.
- checksum_prefix is truncated.

PR0092 — Real Symmetry Difference-Level Computation.
"""

from __future__ import annotations

import json

import pytest

# ---------------------------------------------------------------------------
# Minimal valid reference statistics fixture
# ---------------------------------------------------------------------------


def _make_valid_ref_stats(
    signal_bounds: dict[str, dict[str, float]] | None = None,
) -> dict:
    """Build a minimal valid reference-statistics artifact dict."""
    bounds = signal_bounds or {}
    signals: dict = {}
    for key in (
        "profile_difference_magnitude",
        "weighted_profile_asymmetry",
        "statistical_shape_deviation",
        "distributional_divergence",
        "bilateral_profile_intensity",
    ):
        sb = bounds.get(key, {"small": 0.33, "moderate": 0.67})
        signals[key] = {
            "feature_family": [],
            "percentile_bounds": sb,
        }
    return {
        "artifact_type": "bremen_reference_statistics",
        "artifact_version": "0.1.0",
        "schema_version": "v1",
        "created_at": "2026-01-01T00:00:00Z",
        "source_training_run": "mlflow-run-test",
        "signals": signals,
    }


# ---------------------------------------------------------------------------
# Tests — compute_symmetry_signals (core logic)
# ---------------------------------------------------------------------------


class TestComputeSymmetrySignals:
    """Core computation logic tests."""

    def test_all_not_available_when_ref_stats_is_none(self):
        """When ref_stats is None, all signals are not_available."""
        from bremen.api.symmetry_signals import compute_symmetry_signals

        result = compute_symmetry_signals(
            feature_values={"sigma_l1": 0.1},
            ref_stats=None,
        )
        assert result["schema_status"] == "unavailable"
        assert len(result["signals"]) == 5
        for sig in result["signals"]:
            assert sig["difference_level"] == "not_available"

    def test_all_not_available_when_feature_values_is_none(self):
        """When feature_values is None, all signals are not_available."""
        from bremen.api.symmetry_signals import compute_symmetry_signals

        ref_stats = _make_valid_ref_stats()
        result = compute_symmetry_signals(
            feature_values=None,
            ref_stats=ref_stats,
        )
        for sig in result["signals"]:
            assert sig["difference_level"] == "not_available"

    def test_all_signals_present(self):
        """All 5 signal families are always present in the output."""
        from bremen.api.symmetry_signals import compute_symmetry_signals

        result = compute_symmetry_signals()
        assert len(result["signals"]) == 5
        labels = sorted(s["label"] for s in result["signals"])
        assert "Bilateral profile intensity" in labels
        assert "Distributional divergence" in labels
        assert "Profile difference magnitude" in labels
        assert "Statistical shape deviation" in labels
        assert "Weighted profile asymmetry" in labels

    def test_only_allowed_difference_levels(self):
        """Every difference_level is in the allowed set."""
        from bremen.api.symmetry_signals import (
            compute_symmetry_signals,
            ALLOWED_DIFFERENCE_LEVELS,
        )

        # Without ref stats
        result = compute_symmetry_signals()
        for sig in result["signals"]:
            assert sig["difference_level"] in ALLOWED_DIFFERENCE_LEVELS

        # With valid ref stats and feature values
        ref_stats = _make_valid_ref_stats()
        features = {
            "sigma_l1": 0.1, "sigma_l2": 0.1, "sigma_r1": 0.1,
            "sigma_r2": 0.1, "meanrms1": 0.1, "meanrms2": 0.1,
            "weightedrms1": 0.1, "weightedrms2": 0.1,
            "mahalanobis1": 0.1, "mahalanobis2": 0.1,
            "wasserstein_distance_muLR": 0.1,
            "cosine_distance_full_q2": 0.1,
            "wasserstein_distance_full_q2": 0.1,
            "peak14_intensity": 0.1, "mean_peak_value_raw": 0.1,
        }
        result = compute_symmetry_signals(
            feature_values=features, ref_stats=ref_stats,
        )
        for sig in result["signals"]:
            assert sig["difference_level"] in ALLOWED_DIFFERENCE_LEVELS

    def test_signal_missing_from_artifact_is_not_available(self):
        """When a signal is missing from the artifact, it is not_available."""
        from bremen.api.symmetry_signals import compute_symmetry_signals

        # Artifact missing one signal
        ref_stats = _make_valid_ref_stats()
        del ref_stats["signals"]["profile_difference_magnitude"]

        features = {"sigma_l1": 0.1}
        result = compute_symmetry_signals(
            feature_values=features, ref_stats=ref_stats,
        )
        for sig in result["signals"]:
            if sig["label"] == "Profile difference magnitude":
                assert sig["difference_level"] == "not_available"

    def test_invalid_ref_stats_schema_status_error(self):
        """Invalid artifact shape returns schema_status: error."""
        from bremen.api.symmetry_signals import compute_symmetry_signals

        result = compute_symmetry_signals(
            ref_stats={"not": "valid"},
        )
        assert result["schema_status"] == "error"
        for sig in result["signals"]:
            assert sig["difference_level"] == "not_available"

    def test_checksum_prefix_not_full(self):
        """checksum_prefix is at most 8 chars, never full checksum."""
        from bremen.api.symmetry_signals import compute_symmetry_signals

        ref_stats = _make_valid_ref_stats()
        ref_stats["_artifact_checksum"] = "a" * 64
        result = compute_symmetry_signals(
            ref_stats=ref_stats,
        )
        cprefix = result.get("checksum_prefix")
        assert cprefix is None or len(str(cprefix)) <= 8

    def test_feature_to_signal_map_covers_all_15_columns(self):
        """Every feature in BREMEN_V01_FEATURE_COLUMNS is mapped."""
        from bremen.api.preprocessing_bridge import BREMEN_V01_FEATURE_COLUMNS
        from bremen.api.symmetry_signals import FEATURE_TO_SIGNAL_MAP

        for feat in BREMEN_V01_FEATURE_COLUMNS:
            assert feat in FEATURE_TO_SIGNAL_MAP, (
                f"Feature {feat!r} not in FEATURE_TO_SIGNAL_MAP"
            )

    def test_no_mockup_sample_values_in_code(self):
        """No sample report strings in symmetry_signals module output."""
        from bremen.api.symmetry_signals import (
            _format_external, _format_internal,
        )
        result = {
            "schema_status": "unavailable",
            "measurement_summary": "test",
            "signals": [
                {"label": "Test", "feature_family": ["f1"],
                 "difference_level": "not_available"},
            ],
        }
        ext = json.dumps(_format_external(result))
        assert "SAMPLE" not in ext
        assert "example" not in ext.lower()
        assert "mockup" not in ext.lower()

        internal = json.dumps(_format_internal(result))
        assert "SAMPLE" not in internal
        assert "example" not in internal.lower()
        assert "mockup" not in internal.lower()


# ---------------------------------------------------------------------------
# Tests — decision_support.py integration
# ---------------------------------------------------------------------------


class TestDecisionSupportSymmetry:
    """Decision support report integration tests."""

    def test_symmetry_signals_field_exists(self):
        """build_decision_support_report includes symmetry_signals."""
        from bremen.api.decision_support import build_decision_support_report

        report = build_decision_support_report(
            {"model_version": "v1", "feature_schema_version": "v0.1"},
        )
        assert "symmetry_signals" in report
        assert isinstance(report["symmetry_signals"], dict)
        assert "signals" in report["symmetry_signals"]

    def test_symmetry_signals_not_available_by_default(self):
        """Without feature_values/ref_stats, all not_available."""
        from bremen.api.decision_support import build_decision_support_report

        report = build_decision_support_report({})
        ss = report["symmetry_signals"]
        assert ss["schema_status"] == "unavailable"
        for sig in ss["signals"]:
            assert sig["difference_level"] == "not_available"

    def test_backward_compatible_no_new_required_params(self):
        """Existing callers without feature_values/ref_stats still work."""
        from bremen.api.decision_support import build_decision_support_report

        report = build_decision_support_report(
            {"model_version": "v1"},
            input_mode="h5_path",
        )
        assert "report_schema_version" in report
        assert "intended_use" in report
        assert "limitations" in report
        assert "model_metadata" in report

    def test_external_output_no_raw_features(self):
        """External symmetry_signals has no raw feature values."""
        from bremen.api.decision_support import build_decision_support_report

        report = build_decision_support_report(
            {"model_version": "v1"},
            feature_values={"sigma_l1": 0.5},
            ref_stats=_make_valid_ref_stats(),
        )
        ext_str = json.dumps(report["symmetry_signals"])
        # No raw numeric feature values should leak as standalone keys
        # (signals only have label and difference_level externally)
        for sig in report["symmetry_signals"]["signals"]:
            assert "feature_value" not in sig
            assert "value" not in sig
            assert "raw" not in sig

    def test_external_no_percentile_cutoffs(self):
        """External symmetry_signals does not expose percentile cutoffs."""
        from bremen.api.decision_support import build_decision_support_report

        report = build_decision_support_report(
            {"model_version": "v1"},
            ref_stats=_make_valid_ref_stats(),
        )
        ext_str = json.dumps(report["symmetry_signals"])
        assert "percentile_bounds" not in ext_str
        assert "cutoff" not in ext_str

    def test_decision_vocabulary_unchanged(self):
        """Decision vocabulary is not modified by symmetry addition."""
        from bremen.api.decision_support import build_decision_support_report
        from bremen.api.decision_contract import (
            POSITIVE_MACHINE_CODE, NEGATIVE_MACHINE_CODE,
        )

        report = build_decision_support_report({
            "triage_recommendation": POSITIVE_MACHINE_CODE,
        })
        ds = report["decision_support"]
        assert ds["recommendation"] == POSITIVE_MACHINE_CODE
        assert "may be recommended" in ds["recommendation_label"].lower()


# ---------------------------------------------------------------------------
# Tests — internal report integration
# ---------------------------------------------------------------------------


class TestInternalReportSymmetry:
    """Internal report symmetry_signal_detail tests."""

    def test_symmetry_signal_detail_in_technical_evidence(self):
        """When workflow_result has symmetry_signal_detail, it appears."""
        from bremen.api.report_bremen import BremenReportProvider

        provider = BremenReportProvider()
        wf_result = {
            "probability": 0.5,
            "triage_recommendation": "CONTINUE_MRI",
            "threshold_applied": 0.5,
            "symmetry_signal_detail": {
                "schema_status": "populated",
                "signals": [{"label": "Test", "difference_level": "small"}],
            },
        }
        envelope = provider.generate_report(
            "job-1", wf_result,
            model_identity={"model_id": "m1"},
        )
        payload = envelope.payload
        ste = payload.get("supporting_technical_evidence", {})
        assert "symmetry_signal_detail" in ste

    def test_no_symmetry_detail_when_not_present(self):
        """When workflow_result has no symmetry_signal_detail, it's absent."""
        from bremen.api.report_bremen import BremenReportProvider

        provider = BremenReportProvider()
        wf_result = {
            "probability": 0.5,
            "triage_recommendation": "CONTINUE_MRI",
            "threshold_applied": 0.5,
        }
        envelope = provider.generate_report(
            "job-1", wf_result,
            model_identity={"model_id": "m1"},
        )
        ste = envelope.payload.get("supporting_technical_evidence", {})
        assert "symmetry_signal_detail" not in ste

    def test_internal_output_no_raw_feature_values(self):
        """Internal symmetry_signal_detail has no raw feature values."""
        from bremen.api.symmetry_signals import compute_symmetry_signals, _format_internal

        result = compute_symmetry_signals(
            feature_values={"sigma_l1": 0.5},
            ref_stats=_make_valid_ref_stats(),
        )
        internal = _format_internal(result)
        internal_str = json.dumps(internal)
        assert "raw_feature" not in internal_str
        assert "feature_value" not in internal_str

    def test_internal_output_no_percentile_cutoffs(self):
        """Internal symmetry_signal_detail has no percentile cutoffs."""
        from bremen.api.symmetry_signals import compute_symmetry_signals, _format_internal

        result = compute_symmetry_signals(
            ref_stats=_make_valid_ref_stats(),
        )
        internal = _format_internal(result)
        internal_str = json.dumps(internal)
        assert "percentile_bounds" not in internal_str
        assert "cutoff" not in internal_str

    def test_internal_output_no_full_checksum(self):
        """Internal checksum_prefix is never full checksum."""
        from bremen.api.symmetry_signals import compute_symmetry_signals, _format_internal

        ref_stats = _make_valid_ref_stats()
        ref_stats["_artifact_checksum"] = "a" * 64
        result = compute_symmetry_signals(ref_stats=ref_stats)
        internal = _format_internal(result)
        cprefix = internal.get("checksum_prefix", "")
        assert len(str(cprefix)) <= 8

    def test_internal_includes_feature_family(self):
        """Internal signals include feature_family."""
        from bremen.api.symmetry_signals import compute_symmetry_signals, _format_internal

        result = compute_symmetry_signals(ref_stats=_make_valid_ref_stats())
        internal = _format_internal(result)
        for sig in internal["signals"]:
            assert "feature_family" in sig
            assert isinstance(sig["feature_family"], list)

    def test_external_excludes_feature_family(self):
        """External signals do NOT include feature_family."""
        from bremen.api.symmetry_signals import compute_symmetry_signals, _format_external

        result = compute_symmetry_signals(ref_stats=_make_valid_ref_stats())
        external = _format_external(result)
        for sig in external["signals"]:
            assert "feature_family" not in sig


# ---------------------------------------------------------------------------
# Tests — percentile bucketing
# ---------------------------------------------------------------------------


class TestPercentileBucket:
    """Percentile bucketing logic tests."""

    def test_small_when_below(self):
        from bremen.api.symmetry_signals import _percentile_bucket
        assert _percentile_bucket(0.1, {"small": 0.33, "moderate": 0.67}) == "small"

    def test_moderate_when_between(self):
        from bremen.api.symmetry_signals import _percentile_bucket
        assert _percentile_bucket(0.5, {"small": 0.33, "moderate": 0.67}) == "moderate"

    def test_larger_when_above(self):
        from bremen.api.symmetry_signals import _percentile_bucket
        assert _percentile_bucket(0.8, {"small": 0.33, "moderate": 0.67}) == "larger"

    def test_not_available_when_bounds_is_none(self):
        from bremen.api.symmetry_signals import _percentile_bucket
        assert _percentile_bucket(0.5, None) == "not_available"

    def test_not_available_when_non_finite(self):
        from bremen.api.symmetry_signals import _percentile_bucket
        import math
        assert _percentile_bucket(float("nan"), {"small": 0.33, "moderate": 0.67}) == "not_available"
        assert _percentile_bucket(float("inf"), {"small": 0.33, "moderate": 0.67}) == "not_available"

    def test_not_available_when_not_number(self):
        from bremen.api.symmetry_signals import _percentile_bucket
        assert _percentile_bucket("string", {"small": 0.33, "moderate": 0.67}) == "not_available"


# ---------------------------------------------------------------------------
# Tests — loader boundary
# ---------------------------------------------------------------------------


class TestLoadReferenceStatistics:
    """Reference statistics loader tests."""

    def test_returns_none_when_no_arg(self):
        from bremen.api.symmetry_signals import _load_reference_statistics
        assert _load_reference_statistics() is None

    def test_returns_none_when_none(self):
        from bremen.api.symmetry_signals import _load_reference_statistics
        assert _load_reference_statistics(None) is None

    def test_returns_valid_dict(self):
        from bremen.api.symmetry_signals import _load_reference_statistics
        valid = _make_valid_ref_stats()
        result = _load_reference_statistics(valid)
        assert result is not None
        assert result["artifact_type"] == "bremen_reference_statistics"

    def test_returns_none_for_invalid_dict(self):
        from bremen.api.symmetry_signals import _load_reference_statistics
        assert _load_reference_statistics({"bad": "data"}) is None

    def test_returns_none_for_nonexistent_path(self):
        from bremen.api.symmetry_signals import _load_reference_statistics
        assert _load_reference_statistics("/nonexistent/path/ref_stats.json") is None


# ---------------------------------------------------------------------------
# Tests — no rendering/UI/PDF
# ---------------------------------------------------------------------------


class TestNoRenderingLeak:
    """Ensure no rendering routes or PDF behavior introduced."""

    def test_no_html_in_symmetry_output(self):
        """Symmetry output dicts contain no HTML."""
        from bremen.api.symmetry_signals import compute_symmetry_signals

        result = compute_symmetry_signals(ref_stats=_make_valid_ref_stats())
        result_str = json.dumps(result)
        assert "<html" not in result_str.lower()
        assert "<div" not in result_str.lower()
        assert "<pdf" not in result_str.lower()

    def test_symmetry_module_has_no_route_handlers(self):
        """symmetry_signals module has no HTTP route handler imports."""
        import ast
        from pathlib import Path

        src = Path(__file__).parents[1] / "src" / "bremen" / "api" / "symmetry_signals.py"
        tree = ast.parse(src.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "http" not in alias.name.lower()
                    assert "server" not in alias.name.lower()
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert "http" not in mod.lower()
                assert "server" not in mod.lower()
