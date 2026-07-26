"""Tests for decision-support report (PR0096 — measurement reliability tier).

Covers:
- _compute_measurement_reliability() tier logic (HIGH, ACCEPTABLE, LOW)
- Exact reason strings
- Counts computed from per-side values
- build_decision_support_report() wiring of measurement_reliability
- Absent-count fallback (field omitted when counts absent)
- Naming guard (no top-level reliability/reliability_reason)
"""

from __future__ import annotations

import json

from bremen.api.decision_support import (
    _compute_measurement_reliability,
    build_decision_support_report,
)


# ---------------------------------------------------------------------------
# _compute_measurement_reliability — tier logic
# ---------------------------------------------------------------------------


class TestComputeMeasurementReliability:
    """Tier logic tests for _compute_measurement_reliability."""

    def test_high_technical_left3_right3(self):
        """left >= 3 AND right >= 3 → HIGH_TECHNICAL."""
        result = _compute_measurement_reliability(3, 3)
        assert result["tier"] == "HIGH_TECHNICAL"
        assert result["reason"] == "At least three accepted measurements per breast."
        assert result["left_measurement_count"] == 3
        assert result["right_measurement_count"] == 3

    def test_high_technical_left5_right4(self):
        """left >= 3 AND right >= 3 with larger counts."""
        result = _compute_measurement_reliability(5, 4)
        assert result["tier"] == "HIGH_TECHNICAL"
        assert result["reason"] == "At least three accepted measurements per breast."

    def test_acceptable_technical_left2_right2(self):
        """left >= 2 AND right >= 2 (but < 3) → ACCEPTABLE_TECHNICAL."""
        result = _compute_measurement_reliability(2, 2)
        assert result["tier"] == "ACCEPTABLE_TECHNICAL"
        assert result["reason"] == "At least two accepted measurements per breast."
        assert result["left_measurement_count"] == 2
        assert result["right_measurement_count"] == 2

    def test_acceptable_technical_left2_right3(self):
        """left=2, right=3 → ACCEPTABLE_TECHNICAL (left < 3)."""
        result = _compute_measurement_reliability(2, 3)
        assert result["tier"] == "ACCEPTABLE_TECHNICAL"
        assert result["reason"] == "At least two accepted measurements per breast."

    def test_acceptable_technical_left3_right2(self):
        """left=3, right=2 → ACCEPTABLE_TECHNICAL (right < 3)."""
        result = _compute_measurement_reliability(3, 2)
        assert result["tier"] == "ACCEPTABLE_TECHNICAL"
        assert result["reason"] == "At least two accepted measurements per breast."

    def test_low_technical_left1_right3(self):
        """left < 2 → LOW_TECHNICAL."""
        result = _compute_measurement_reliability(1, 3)
        assert result["tier"] == "LOW_TECHNICAL"
        assert result["reason"] == "Fewer than two accepted measurements on one breast."
        assert result["left_measurement_count"] == 1
        assert result["right_measurement_count"] == 3

    def test_low_technical_left0_right0(self):
        """left=0, right=0 → LOW_TECHNICAL."""
        result = _compute_measurement_reliability(0, 0)
        assert result["tier"] == "LOW_TECHNICAL"
        assert result["reason"] == "Fewer than two accepted measurements on one breast."

    def test_low_technical_left1_right1(self):
        """left=1, right=1 → LOW_TECHNICAL."""
        result = _compute_measurement_reliability(1, 1)
        assert result["tier"] == "LOW_TECHNICAL"
        assert result["reason"] == "Fewer than two accepted measurements on one breast."

    def test_returns_dict_with_four_keys(self):
        """Result always has exactly 4 keys."""
        result = _compute_measurement_reliability(3, 3)
        assert set(result.keys()) == {
            "tier", "reason", "left_measurement_count", "right_measurement_count"
        }

    def test_integer_casting(self):
        """Float inputs are cast to int."""
        result = _compute_measurement_reliability(3.0, 3.0)
        assert result["left_measurement_count"] == 3
        assert result["right_measurement_count"] == 3
        assert isinstance(result["left_measurement_count"], int)

    def test_exact_tier_strings(self):
        """Tier strings are exactly HIGH_TECHNICAL, ACCEPTABLE_TECHNICAL, LOW_TECHNICAL."""
        high = _compute_measurement_reliability(4, 4)
        acceptable = _compute_measurement_reliability(2, 3)
        low = _compute_measurement_reliability(0, 1)
        assert high["tier"] == "HIGH_TECHNICAL"
        assert acceptable["tier"] == "ACCEPTABLE_TECHNICAL"
        assert low["tier"] == "LOW_TECHNICAL"


# ---------------------------------------------------------------------------
# build_decision_support_report — measurement_reliability wiring
# ---------------------------------------------------------------------------


class TestDecisionSupportMeasurementReliability:
    """Wiring tests for measurement_reliability in build_decision_support_report."""

    def test_measurement_reliability_present_with_counts(self):
        """When left/right counts present, measurement_reliability emitted."""
        report = build_decision_support_report({
            "model_version": "v1",
            "feature_schema_version": "v0.1",
            "triage_recommendation": "CONTINUE_MRI",
            "left_measurement_count": 3,
            "right_measurement_count": 4,
        })
        ps = report["prediction_summary"]
        assert "measurement_reliability" in ps
        assert ps["measurement_reliability"]["tier"] == "HIGH_TECHNICAL"

    def test_measurement_reliability_absent_without_counts(self):
        """When counts absent, measurement_reliability omitted."""
        report = build_decision_support_report({
            "model_version": "v1",
            "feature_schema_version": "v0.1",
            "triage_recommendation": "CONTINUE_MRI",
        })
        ps = report["prediction_summary"]
        assert "measurement_reliability" not in ps

    def test_measurement_reliability_absent_when_only_left(self):
        """When only left_measurement_count present, field omitted."""
        report = build_decision_support_report({
            "model_version": "v1",
            "left_measurement_count": 3,
        })
        ps = report["prediction_summary"]
        assert "measurement_reliability" not in ps

    def test_measurement_reliability_absent_when_only_right(self):
        """When only right_measurement_count present, field omitted."""
        report = build_decision_support_report({
            "model_version": "v1",
            "right_measurement_count": 3,
        })
        ps = report["prediction_summary"]
        assert "measurement_reliability" not in ps

    def test_measurement_reliability_acceptable_tier(self):
        """Acceptable tier wired correctly."""
        report = build_decision_support_report({
            "model_version": "v1",
            "left_measurement_count": 2,
            "right_measurement_count": 2,
        })
        assert report["prediction_summary"]["measurement_reliability"]["tier"] == "ACCEPTABLE_TECHNICAL"

    def test_measurement_reliability_low_tier(self):
        """Low tier wired correctly."""
        report = build_decision_support_report({
            "model_version": "v1",
            "left_measurement_count": 1,
            "right_measurement_count": 3,
        })
        assert report["prediction_summary"]["measurement_reliability"]["tier"] == "LOW_TECHNICAL"

    def test_existing_fields_preserved(self):
        """Existing prediction_summary fields preserved."""
        report = build_decision_support_report({
            "model_version": "v1",
            "triage_recommendation": "CONTINUE_MRI",
            "qc_status": "passed",
            "qc_flags": ["flag1"],
            "left_measurement_count": 3,
            "right_measurement_count": 3,
        })
        ps = report["prediction_summary"]
        assert ps["triage_recommendation"] == "CONTINUE_MRI"
        assert ps["qc_status"] == "passed"
        assert ps["qc_flags"] == ["flag1"]
        assert "measurement_reliability" in ps


# ---------------------------------------------------------------------------
# Naming guard — no forbidden keys
# ---------------------------------------------------------------------------


class TestNamingGuard:
    """No forbidden top-level or prediction_summary keys."""

    def test_no_top_level_reliability(self):
        """No top-level 'reliability' key in report."""
        report = build_decision_support_report({
            "model_version": "v1",
            "left_measurement_count": 3,
            "right_measurement_count": 3,
        })
        assert "reliability" not in report

    def test_no_top_level_reliability_reason(self):
        """No top-level 'reliability_reason' key in report."""
        report = build_decision_support_report({
            "model_version": "v1",
            "left_measurement_count": 3,
            "right_measurement_count": 3,
        })
        assert "reliability_reason" not in report

    def test_no_prediction_summary_reliability(self):
        """No prediction_summary.reliability key."""
        report = build_decision_support_report({
            "model_version": "v1",
            "left_measurement_count": 3,
            "right_measurement_count": 3,
        })
        ps = report["prediction_summary"]
        assert "reliability" not in ps

    def test_no_prediction_summary_reliability_reason(self):
        """No prediction_summary.reliability_reason key."""
        report = build_decision_support_report({
            "model_version": "v1",
            "left_measurement_count": 3,
            "right_measurement_count": 3,
        })
        ps = report["prediction_summary"]
        assert "reliability_reason" not in ps

    def test_only_measurement_reliability_key_used(self):
        """The only reliability-bearing key is measurement_reliability."""
        report = build_decision_support_report({
            "model_version": "v1",
            "left_measurement_count": 3,
            "right_measurement_count": 3,
        })
        ps = report["prediction_summary"]
        # Should have measurement_reliability, not plain reliability
        assert "measurement_reliability" in ps

    def test_no_clinical_reliability_term(self):
        """No 'clinical reliability' or 'diagnostic reliability' in report JSON."""
        report = build_decision_support_report({
            "model_version": "v1",
            "left_measurement_count": 3,
            "right_measurement_count": 3,
        })
        report_str = json.dumps(report).lower()
        assert "clinical reliability" not in report_str
        assert "diagnostic reliability" not in report_str
        assert "model reliability" not in report_str
        assert "scientific reliability" not in report_str
