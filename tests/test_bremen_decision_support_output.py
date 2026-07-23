"""Tests for the decision-support output wrapper (PR 0053).

All tests are synthetic and deterministic.  No AWS, Docker, Terraform,
App Runner, network, real H5, real model artifact, real Matador, or
credentials.
"""

from __future__ import annotations

from bremen.api.decision_support import (
    REPORT_SCHEMA_VERSION,
    INTENDED_USE,
    LIMITATIONS,
    CAUTION_TEXT,
    build_decision_support_report,
)


# ---------------------------------------------------------------------------
# Synthetic helper
# ---------------------------------------------------------------------------


def _minimal_inference_result(**overrides) -> dict:
    """Return a minimal valid inference result dict.

    Keyword arguments override default values.
    """
    defaults = {
        "prediction_id": "pred-001",
        "model_version": "test-v0.1",
        "model_checksum": "a" * 64,
        "feature_schema_version": "v0.1",
        "threshold_version": "v0.1",
        "threshold_value": 0.5,
        "qc_status": "passed",
        "qc_flags": [],
        "patient_id": "PID-001",
        "p_mri_needed": 0.75,
        "triage_recommendation": "CONTINUE_MRI",
        "created_at_utc": "2026-01-01T00:00:00",
    }
    defaults.update(overrides)
    return defaults


# ===================================================================
# Class A: TestReportSchema
# ===================================================================


class TestReportSchema:
    def test_report_schema_version_is_defined(self):
        """REPORT_SCHEMA_VERSION is a non-empty string."""
        assert isinstance(REPORT_SCHEMA_VERSION, str)
        assert len(REPORT_SCHEMA_VERSION) > 0

    def test_report_contains_schema_version(self):
        """build_decision_support_report returns report_schema_version."""
        result = _minimal_inference_result()
        report = build_decision_support_report(result)
        assert report["report_schema_version"] == REPORT_SCHEMA_VERSION


# ===================================================================
# Class B: TestIntendedUseAndLimitations
# ===================================================================


class TestIntendedUseAndLimitations:
    def test_report_contains_intended_use(self):
        """Report dict has intended_use with string value."""
        result = _minimal_inference_result()
        report = build_decision_support_report(result)
        assert "intended_use" in report
        assert isinstance(report["intended_use"], str)
        assert "decision support" in report["intended_use"].lower()

    def test_report_contains_limitations_list(self):
        """Report dict has limitations with non-empty list of strings."""
        result = _minimal_inference_result()
        report = build_decision_support_report(result)
        assert "limitations" in report
        assert isinstance(report["limitations"], list)
        assert len(report["limitations"]) > 0
        for item in report["limitations"]:
            assert isinstance(item, str)

    def test_limitations_mention_not_diagnosis(self):
        """At least one limitation states not a diagnosis/diagnostic."""
        result = _minimal_inference_result()
        report = build_decision_support_report(result)
        combined = " ".join(report["limitations"]).lower()
        assert "not a diagnosis" in combined or "not a diagnostic" in combined

    def test_limitations_mention_no_clinical_validation(self):
        """At least one limitation states not clinically validated."""
        result = _minimal_inference_result()
        report = build_decision_support_report(result)
        combined = " ".join(report["limitations"]).lower()
        assert "not clinically validated" in combined

    def test_limitations_mention_no_replacement(self):
        """At least one limitation states does not replace MRI, biopsy,
        radiologist, clinician, or clinical judgment."""
        result = _minimal_inference_result()
        report = build_decision_support_report(result)
        combined = " ".join(report["limitations"]).lower()
        assert "does not replace mri" in combined
        assert "biopsy" in combined
        assert "radiologist" in combined
        assert "clinician" in combined

    def test_intended_use_contains_mri_continuation(self):
        """INTENDED_USE string mentions MRI continuation."""
        assert "MRI continuation" in INTENDED_USE or \
               "MRI follow-up" in INTENDED_USE.lower()


# ===================================================================
# Class C: TestModelMetadata
# ===================================================================


class TestModelMetadata:
    def test_report_contains_model_version(self):
        """Report model_metadata includes model_version."""
        result = _minimal_inference_result(model_version="v2.0-test")
        report = build_decision_support_report(result)
        assert report["model_metadata"]["model_version"] == "v2.0-test"

    def test_report_contains_feature_schema_version(self):
        """Report model_metadata includes feature_schema_version."""
        result = _minimal_inference_result(feature_schema_version="v0.1")
        report = build_decision_support_report(result)
        assert report["model_metadata"]["feature_schema_version"] == "v0.1"

    def test_report_contains_threshold_version(self):
        """Report model_metadata includes threshold_version."""
        result = _minimal_inference_result(threshold_version="v0.1")
        report = build_decision_support_report(result)
        assert report["model_metadata"]["threshold_version"] == "v0.1"

    def test_report_contains_threshold_value(self):
        """Report model_metadata includes threshold_value."""
        result = _minimal_inference_result(threshold_value=0.5)
        report = build_decision_support_report(result)
        assert report["model_metadata"]["threshold_value"] == 0.5

    def test_report_does_not_expose_raw_checksum(self):
        """Report model_metadata does NOT contain model_checksum."""
        result = _minimal_inference_result(model_checksum="a" * 64)
        report = build_decision_support_report(result)
        assert "model_checksum" not in report["model_metadata"]

    def test_report_does_not_expose_model_uri(self):
        """Report model_metadata does NOT contain model_uri or model_path."""
        result = _minimal_inference_result()
        report = build_decision_support_report(result)
        assert "model_uri" not in report["model_metadata"]
        assert "model_path" not in report["model_metadata"]


# ===================================================================
# Class D: TestInputSummary
# ===================================================================


class TestInputSummary:
    def test_report_contains_input_mode(self):
        """Report input_summary includes input_mode matching parameter."""
        result = _minimal_inference_result()
        report = build_decision_support_report(result, input_mode="h5_uri")
        assert report["input_summary"]["input_mode"] == "h5_uri"

    def test_report_contains_explicit_refs_bool(self):
        """Report input_summary includes explicit_refs_provided boolean."""
        result = _minimal_inference_result()
        report = build_decision_support_report(result, explicit_refs=True)
        assert report["input_summary"]["explicit_refs_provided"] is True

    def test_report_input_mode_defaults_to_unknown(self):
        """When input_mode is None, report uses 'unknown'."""
        result = _minimal_inference_result()
        report = build_decision_support_report(result)
        assert report["input_summary"]["input_mode"] == "unknown"

    def test_report_contains_layout_category(self):
        """Report input_summary includes layout_category string."""
        result = _minimal_inference_result()
        report = build_decision_support_report(
            result, layout_category="calibration_sample"
        )
        assert report["input_summary"]["layout_category"] == "calibration_sample"

    def test_report_does_not_expose_raw_h5_path(self):
        """Report input_summary does NOT contain h5_path, h5_uri,
        target_scan_ref, or control_scan_ref keys."""
        result = _minimal_inference_result()
        report = build_decision_support_report(result, input_mode="h5_path")
        inp = report["input_summary"]
        assert "h5_path" not in inp
        assert "h5_uri" not in inp
        assert "target_scan_ref" not in inp
        assert "control_scan_ref" not in inp


# ===================================================================
# Class E: TestPredictionSummary
# ===================================================================


class TestPredictionSummary:
    def test_report_contains_p_mri_needed(self):
        """Report prediction_summary includes p_mri_needed float."""
        result = _minimal_inference_result(p_mri_needed=0.75)
        report = build_decision_support_report(result)
        assert report["prediction_summary"]["p_mri_needed"] == 0.75

    def test_report_contains_triage_recommendation(self):
        """Report prediction_summary includes triage_recommendation."""
        result = _minimal_inference_result(
            triage_recommendation="MRI_RECOMMENDED"
        )
        report = build_decision_support_report(result)
        assert report["prediction_summary"]["triage_recommendation"] == \
            "MRI_RECOMMENDED"

    def test_report_contains_qc_status(self):
        """Report prediction_summary includes qc_status."""
        result = _minimal_inference_result(qc_status="passed")
        report = build_decision_support_report(result)
        assert report["prediction_summary"]["qc_status"] == "passed"

    def test_report_contains_qc_flags(self):
        """Report prediction_summary includes qc_flags list."""
        result = _minimal_inference_result(qc_flags=["flag1"])
        report = build_decision_support_report(result)
        assert report["prediction_summary"]["qc_flags"] == ["flag1"]

    def test_prediction_summary_excludes_raw_feature_values(self):
        """Report prediction_summary does NOT contain raw feature values."""
        result = _minimal_inference_result()
        result["features"] = [0.1] * 15  # Not a standard key, but test safety
        report = build_decision_support_report(result)
        assert "features" not in report["prediction_summary"]
        assert "feature_vector" not in report["prediction_summary"]


# ===================================================================
# Class F: TestDecisionSupport
# ===================================================================


class TestDecisionSupport:
    def test_report_contains_recommendation(self):
        """Report decision_support includes recommendation matching triage."""
        result = _minimal_inference_result(
            triage_recommendation="CONTINUE_MRI"
        )
        report = build_decision_support_report(result)
        assert report["decision_support"]["recommendation"] == "CONTINUE_MRI"

    def test_report_contains_recommendation_label(self):
        """Report decision_support includes recommendation_label string."""
        result = _minimal_inference_result()
        report = build_decision_support_report(result)
        label = report["decision_support"]["recommendation_label"]
        assert isinstance(label, str)
        assert len(label) > 0

    def test_recommendation_label_does_not_say_diagnosis(self):
        """recommendation_label does NOT contain diagnosis, cancer, benign,
        or malignant."""
        result = _minimal_inference_result(
            triage_recommendation="MRI_RECOMMENDED"
        )
        report = build_decision_support_report(result)
        label = report["decision_support"]["recommendation_label"].lower()
        assert "diagnosis" not in label
        assert "cancer" not in label
        assert "benign" not in label
        assert "malignant" not in label

    def test_report_contains_caution(self):
        """Report decision_support includes a caution string."""
        result = _minimal_inference_result()
        report = build_decision_support_report(result)
        assert "caution" in report["decision_support"]
        assert isinstance(report["decision_support"]["caution"], str)
        assert len(report["decision_support"]["caution"]) > 0

    def test_caution_mentions_decision_support(self):
        """Caution mentions decision-support or not a clinical decision."""
        result = _minimal_inference_result()
        report = build_decision_support_report(result)
        caution = report["decision_support"]["caution"].lower()
        assert "decision-support" in caution or \
               "not a clinical decision" in caution

    def test_caution_mentions_clinician(self):
        """Caution mentions clinician."""
        result = _minimal_inference_result()
        report = build_decision_support_report(result)
        caution = report["decision_support"]["caution"].lower()
        assert "clinician" in caution

    def test_rule_out_label_is_safe(self):
        """MRI_REVIEW_DEFER recommendation_label uses 'may not be indicated'."""
        result = _minimal_inference_result(
            triage_recommendation="MRI_REVIEW_DEFER"
        )
        report = build_decision_support_report(result)
        label = report["decision_support"]["recommendation_label"].lower()
        assert "may not be indicated" in label

    def test_unknown_triage_has_fallback_label(self):
        """Unknown triage value produces a safe fallback label."""
        result = _minimal_inference_result(
            triage_recommendation="UNKNOWN_STATUS"
        )
        report = build_decision_support_report(result)
        label = report["decision_support"]["recommendation_label"].lower()
        assert "not conclusive" in label or \
               "clinician" in label


# ===================================================================
# Class G: TestBackwardCompatibility
# ===================================================================


class TestBackwardCompatibility:
    def test_report_is_additive_does_not_modify_input(self):
        """build_decision_support_report does not mutate its input dict."""
        result = _minimal_inference_result()
        original_keys = set(result.keys())
        original_values = {k: result[k] for k in result}
        build_decision_support_report(result)
        assert set(result.keys()) == original_keys
        for k in original_keys:
            assert result[k] == original_values[k], \
                f"Input key {k} was mutated"

    def test_report_parameter_defaults_are_safe(self):
        """Calling with no optional keyword arguments returns valid report."""
        result = _minimal_inference_result()
        report = build_decision_support_report(result)
        assert report["input_summary"]["input_mode"] == "unknown"
        assert report["input_summary"]["explicit_refs_provided"] is None
        assert report["input_summary"]["layout_category"] is None
        assert report["report_schema_version"] == REPORT_SCHEMA_VERSION


# ===================================================================
# Class H: TestSafetyBoundary
# ===================================================================


class TestSafetyBoundary:
    def test_report_does_not_contain_raw_feature_values(self):
        """Report prediction_summary does NOT contain feature vectors or
        raw feature values."""
        result = _minimal_inference_result()
        report = build_decision_support_report(result)
        ps = report["prediction_summary"]
        for key in ps:
            # Only allowed keys
            assert key in ("p_mri_needed", "triage_recommendation",
                           "qc_status", "qc_flags"), \
                f"Unexpected key in prediction_summary: {key}"

    def test_report_does_not_contain_patient_id_in_nested_sections(self):
        """Report input_summary and prediction_summary do not duplicate
        patient_id."""
        result = _minimal_inference_result(patient_id="PID-001")
        report = build_decision_support_report(result)
        assert "patient_id" not in report["input_summary"]
        assert "patient_id" not in report["prediction_summary"]
        assert "patient_id" not in report["model_metadata"]

    def test_report_does_not_contain_raw_checksum_in_any_section(self):
        """No section of the report exposes model_checksum."""
        result = _minimal_inference_result(model_checksum="a" * 64)
        report = build_decision_support_report(result)
        report_str = str(report)
        assert "a" * 64 not in report_str, \
            "Raw checksum must not appear anywhere in the report"

    def test_build_decision_support_report_is_deterministic(self):
        """Same inputs produce identical output (no timestamps, no randomness)."""
        result = _minimal_inference_result()
        report1 = build_decision_support_report(
            result, input_mode="h5_path", explicit_refs=True,
            layout_category="canonical",
        )
        report2 = build_decision_support_report(
            result, input_mode="h5_path", explicit_refs=True,
            layout_category="canonical",
        )
        assert report1 == report2
