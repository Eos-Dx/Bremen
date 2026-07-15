"""Tests for the Bremen demo evidence pack.

Covers:
- DEMO_EVIDENCE_VERSION is a non-empty string
- Build synthetic feature payload — 15 columns, deterministic values
- Synthetic payload passes validate_feature_artifact
- Synthetic payload produces stable prediction with synthetic model
- Evidence bundle shape — all required keys
- technical_demo_only is True
- product is "Bremen"
- product_question is correct
- safety_notes is a non-empty list
- No Aramis references in evidence output
- No diagnosis/replacement language in evidence output
- validate_demo_evidence_bundle() passes for valid bundle
- validate_demo_evidence_bundle() rejects various invalid bundles
- JSON serializable
- Deterministic output
- No real patient data
- No H5/model/network dependencies
- import safety (stdlib only)
"""

from __future__ import annotations

import ast
import json
import math
from pathlib import Path

import pytest

from bremen.demo_evidence import (
    BREMEN_DEMO_DISCLAIMER,
    BREMEN_PRODUCT_NAME,
    BREMEN_PRODUCT_QUESTION,
    DEMO_EVIDENCE_VERSION,
    DEMO_SCENARIO_ID,
    build_demo_evidence_bundle,
    build_demo_feature_artifact_payload,
    json_dumps_evidence_bundle,
    validate_demo_evidence_bundle,
)

MODULE_PATH = Path(__file__).parents[1] / "src" / "bremen" / "demo_evidence.py"


# ===================================================================
# Helper: mini predictor for determinism tests
# ===================================================================


def _make_synthetic_predictor() -> dict:
    """Return a synthetic portable_logreg predictor matching the built-in
    synthetic model in _load_synthetic_model() (server.py)."""
    from bremen.feature_artifacts import REQUIRED_FEATURE_COLUMNS

    n = 15
    return {
        "portable_logreg": {
            "feature_columns": list(REQUIRED_FEATURE_COLUMNS),
            "imputer_statistics": [0.0] * n,
            "scaler_mean": [0.0] * n,
            "scaler_scale": [1.0] * n,
            "coef": [0.1] * n,
            "intercept": 0.0,
            "threshold": 0.5,
        }
    }


# ===================================================================
# Class 1: Constants
# ===================================================================


class TestDemoEvidenceVersion:
    def test_demo_evidence_version_is_non_empty_string(self):
        """DEMO_EVIDENCE_VERSION is a non-empty string."""
        assert isinstance(DEMO_EVIDENCE_VERSION, str)
        assert len(DEMO_EVIDENCE_VERSION) > 0

    def test_scenario_id_is_non_empty_string(self):
        """DEMO_SCENARIO_ID is a non-empty string."""
        assert isinstance(DEMO_SCENARIO_ID, str)
        assert len(DEMO_SCENARIO_ID) > 0

    def test_bremen_product_name_is_bremen(self):
        """BREMEN_PRODUCT_NAME is 'Bremen'."""
        assert BREMEN_PRODUCT_NAME == "Bremen"

    def test_bremen_product_question_is_expected(self):
        """BREMEN_PRODUCT_QUESTION is the expected string."""
        assert BREMEN_PRODUCT_QUESTION == "Should patient continue to MRI?"

    def test_bremen_demo_disclaimer_is_non_empty_string(self):
        """BREMEN_DEMO_DISCLAIMER is a non-empty string."""
        assert isinstance(BREMEN_DEMO_DISCLAIMER, str)
        assert len(BREMEN_DEMO_DISCLAIMER) > 0


# ===================================================================
# Class 2: Synthetic feature payload
# ===================================================================


class TestBuildDemoFeatureArtifactPayload:
    def test_payload_is_dict(self):
        """build_demo_feature_artifact_payload returns a dict."""
        payload = build_demo_feature_artifact_payload()
        assert isinstance(payload, dict)

    def test_payload_has_15_feature_columns(self):
        """Payload has exactly 15 feature columns."""
        payload = build_demo_feature_artifact_payload()
        assert len(payload["feature_columns"]) == 15
        assert len(payload["feature_values"]) == 15

    def test_payload_has_required_schema_fields(self):
        """Payload has schema_version, artifact_kind, feature_columns,
        feature_values, metadata."""
        payload = build_demo_feature_artifact_payload()
        assert "schema_version" in payload
        assert "artifact_kind" in payload
        assert "feature_columns" in payload
        assert "feature_values" in payload
        assert "metadata" in payload

    def test_payload_schema_version_is_expected(self):
        """Payload schema_version matches feature_artifact.v0.1."""
        payload = build_demo_feature_artifact_payload()
        assert payload["schema_version"] == "bremen.feature_artifact.v0.1"

    def test_payload_artifact_kind_is_expected(self):
        """Payload artifact_kind is bremen.precomputed_features."""
        payload = build_demo_feature_artifact_payload()
        assert payload["artifact_kind"] == "bremen.precomputed_features"

    def test_payload_metadata_contains_demo_fields(self):
        """Payload metadata contains demo_evidence_pack provenance."""
        payload = build_demo_feature_artifact_payload()
        metadata = payload["metadata"]
        assert metadata["preprocessing_source"] == "demo_evidence_pack"
        assert metadata["source_package_version"] == DEMO_EVIDENCE_VERSION
        assert metadata["configuration_label"] == "technical_demo_only"

    def test_payload_feature_columns_match_required(self):
        """Payload feature_columns match REQUIRED_FEATURE_COLUMNS."""
        from bremen.feature_artifacts import REQUIRED_FEATURE_COLUMNS

        payload = build_demo_feature_artifact_payload()
        assert payload["feature_columns"] == list(REQUIRED_FEATURE_COLUMNS)

    def test_payload_feature_values_are_finite_floats(self):
        """All feature values are finite floats."""
        payload = build_demo_feature_artifact_payload()
        for v in payload["feature_values"]:
            assert isinstance(v, float)
            assert math.isfinite(v)

    def test_payload_is_deterministic(self):
        """Two calls return identical payloads."""
        p1 = build_demo_feature_artifact_payload()
        p2 = build_demo_feature_artifact_payload()
        assert p1 == p2


# ===================================================================
# Class 3: Payload passes validate_feature_artifact
# ===================================================================


class TestPayloadPassesValidation:
    def test_payload_passes_validate_feature_artifact(self):
        """Synthetic payload passes validate_feature_artifact() from
        feature_artifacts.py."""
        from bremen.feature_artifacts import validate_feature_artifact

        payload = build_demo_feature_artifact_payload()
        # Should not raise
        validated = validate_feature_artifact(payload)
        assert isinstance(validated, dict)
        assert validated["feature_columns"] == list(
            payload["feature_columns"]
        )


# ===================================================================
# Class 4: Payload produces stable prediction
# ===================================================================


class TestPayloadStablePrediction:
    def test_payload_produces_stable_prediction_result(self):
        """Payload run through the synthetic model produces a stable
        prediction."""
        from bremen.inference import predict_proba_portable

        payload = build_demo_feature_artifact_payload()
        predictor = _make_synthetic_predictor()
        result = predict_proba_portable(
            predictor,
            payload["feature_values"],
            skip_validation=False,
        )
        assert "probability" in result
        assert 0.0 <= result["probability"] <= 1.0
        # The target probability should be approximately 0.62
        assert result["probability"] == pytest.approx(0.620, abs=0.01)
        # Above threshold 0.5 → prediction=1 (MRI_RECOMMENDED)
        assert result["prediction"] == 1
        assert result["threshold_applied"] == 0.5

    def test_payload_prediction_is_deterministic(self):
        """Two predictions with the same payload produce identical results."""
        from bremen.inference import predict_proba_portable

        payload = build_demo_feature_artifact_payload()
        predictor = _make_synthetic_predictor()
        r1 = predict_proba_portable(predictor, payload["feature_values"])
        r2 = predict_proba_portable(predictor, payload["feature_values"])
        assert r1["probability"] == pytest.approx(r2["probability"])
        assert r1["prediction"] == r2["prediction"]


# ===================================================================
# Class 5: Evidence bundle shape
# ===================================================================


class TestEvidenceBundleShape:
    def test_bundle_has_all_required_keys(self):
        """build_demo_evidence_bundle returns all mandatory keys."""
        bundle = build_demo_evidence_bundle()
        required_keys = {
            "technical_demo_only",
            "product",
            "product_question",
            "disclaimer",
            "evidence_version",
            "scenario_id",
            "safety_notes",
        }
        assert required_keys <= set(bundle.keys()), (
            f"Missing keys: {required_keys - set(bundle.keys())}"
        )

    def test_optional_fields_absent_when_not_provided(self):
        """Optional fields are not present when not provided."""
        bundle = build_demo_evidence_bundle()
        for key in (
            "base_url", "request_id", "job_id", "model_status",
            "model_version", "feature_schema_version",
            "prediction_status", "decision_support", "checks",
            "warnings",
        ):
            assert key not in bundle, (
                f"Optional field {key!r} should not be present"
            )

    def test_optional_fields_present_when_provided(self):
        """Optional fields are present when provided."""
        bundle = build_demo_evidence_bundle(
            base_url="http://example.com",
            request_id="req-001",
            job_id="job-001",
            model_status="ready",
            model_version="v0.1",
            feature_schema_version="v0.1",
            prediction_status="completed",
            decision_support={"key": "val"},
            checks={"health": "pass"},
            warnings=["warning 1"],
        )
        assert bundle["base_url"] == "http://example.com"
        assert bundle["request_id"] == "req-001"
        assert bundle["job_id"] == "job-001"
        assert bundle["model_status"] == "ready"
        assert bundle["model_version"] == "v0.1"
        assert bundle["feature_schema_version"] == "v0.1"
        assert bundle["prediction_status"] == "completed"
        assert bundle["decision_support"] == {"key": "val"}
        assert bundle["checks"] == {"health": "pass"}
        assert bundle["warnings"] == ["warning 1"]

    def test_full_bundle_has_all_keys(self):
        """Full bundle with all optional fields has all expected keys."""
        bundle = build_demo_evidence_bundle(
            base_url="http://example.com",
            request_id="req-001",
            job_id="job-001",
            model_status="ready",
            model_version="v0.1",
            feature_schema_version="v0.1",
            prediction_status="completed",
            decision_support={"report_schema_version": "v0.1"},
            checks={"health": "pass", "model_version": "pass"},
            warnings=["warning 1"],
        )
        expected_keys = {
            "technical_demo_only", "product", "product_question",
            "disclaimer", "evidence_version", "scenario_id",
            "safety_notes", "base_url", "request_id", "job_id",
            "model_status", "model_version", "feature_schema_version",
            "prediction_status", "decision_support", "checks",
            "warnings",
        }
        assert set(bundle.keys()) == expected_keys


# ===================================================================
# Class 6: technical_demo_only
# ===================================================================


class TestTechnicalDemoOnly:
    def test_technical_demo_only_is_true(self):
        """technical_demo_only is always True."""
        bundle = build_demo_evidence_bundle()
        assert bundle["technical_demo_only"] is True

    def test_technical_demo_only_present_with_optional_fields(self):
        """technical_demo_only is True with optional fields present."""
        bundle = build_demo_evidence_bundle(
            base_url="http://example.com",
            request_id="req-001",
        )
        assert bundle["technical_demo_only"] is True


# ===================================================================
# Class 7: Product identity
# ===================================================================


class TestProductIdentity:
    def test_product_is_bremen(self):
        """product is 'Bremen'."""
        bundle = build_demo_evidence_bundle()
        assert bundle["product"] == "Bremen"

    def test_product_question_is_expected(self):
        """product_question is the expected string."""
        bundle = build_demo_evidence_bundle()
        assert bundle["product_question"] == "Should patient continue to MRI?"


# ===================================================================
# Class 8: safety_notes
# ===================================================================


class TestSafetyNotes:
    def test_safety_notes_is_non_empty_list(self):
        """safety_notes is a non-empty list."""
        bundle = build_demo_evidence_bundle()
        assert isinstance(bundle["safety_notes"], list)
        assert len(bundle["safety_notes"]) > 0

    def test_safety_notes_items_are_strings(self):
        """All safety_notes items are strings."""
        bundle = build_demo_evidence_bundle()
        for note in bundle["safety_notes"]:
            assert isinstance(note, str)
            assert len(note) > 0

    def test_safety_notes_contain_expected_language(self):
        """safety_notes contain standard disclaimer language."""
        bundle = build_demo_evidence_bundle()
        combined = " ".join(bundle["safety_notes"]).lower()
        assert "not a clinical result" in combined
        assert "not clinically validated" in combined
        assert "clinician" in combined
        assert "clinical judgment" in combined


# ===================================================================
# Class 9: No Aramis references
# ===================================================================


class TestNoAramisReferences:
    def test_no_aramis_in_evidence_bundle(self):
        """Evidence bundle does not contain Aramis references."""
        bundle = build_demo_evidence_bundle(
            base_url="http://example.com",
            request_id="req-001",
            decision_support={"report": "test"},
            checks={"health": "pass"},
            warnings=["warning"],
        )
        bundle_str = json.dumps(bundle).lower()
        for pattern in ("aramis", "m2q", "benign vs cancer"):
            assert pattern not in bundle_str, (
                f"Evidence bundle contains prohibited pattern: {pattern}"
            )

    def test_no_aramis_in_build_function(self):
        """build_demo_evidence_bundle output does not contain 'Aramis'.

        The source code may reference 'Aramis' in prohibition context
        (pattern lists for detection).  This is safe — only output matters."""
        import json

        bundle = build_demo_evidence_bundle(
            base_url="http://example.com",
            request_id="req-001",
            checks={"health": "pass"},
            warnings=["test warning"],
        )
        bundle_str = json.dumps(bundle).lower()
        assert "aramis" not in bundle_str, (
            "Evidence bundle output must not contain 'aramis'"
        )


# ===================================================================
# Class 10: No diagnosis/replacement language
# ===================================================================


class TestNoClinicalReplacementLanguage:
    def test_no_diagnosis_in_evidence_bundle(self):
        """Evidence bundle does not contain diagnosis claims."""
        bundle = build_demo_evidence_bundle(
            base_url="http://example.com",
            request_id="req-001",
        )
        bundle_str = json.dumps(bundle).lower()
        # "diagnosis" appears in the disclaimer but only as negation
        # "not a clinical result. It is not clinically validated. It does not
        # replace MRI, biopsy, a radiologist, a clinician, or clinical judgment."
        assert "replaces mri" not in bundle_str
        assert "replaces biopsy" not in bundle_str
        assert "replaces radiologist" not in bundle_str
        assert "replaces clinician" not in bundle_str

    def test_disclaimer_does_not_claim_diagnosis(self):
        """disclaimer is a safety statement, not a diagnosis claim."""
        bundle = build_demo_evidence_bundle()
        assert "not a clinical result" in bundle["disclaimer"].lower()
        assert "not clinically validated" in bundle["disclaimer"].lower()
        assert "does not replace" in bundle["disclaimer"].lower()


# ===================================================================
# Class 11: validate_demo_evidence_bundle — valid bundles
# ===================================================================


class TestValidateBundleValid:
    def test_validates_minimal_bundle(self):
        """Minimal valid bundle passes validation."""
        bundle = build_demo_evidence_bundle()
        result = validate_demo_evidence_bundle(bundle)
        assert result is bundle  # pass-through

    def test_validates_full_bundle(self):
        """Full valid bundle passes validation."""
        bundle = build_demo_evidence_bundle(
            base_url="http://example.com",
            request_id="req-001",
            job_id="job-001",
            model_status="ready",
            model_version="v0.1",
            feature_schema_version="v0.1",
            prediction_status="completed",
            decision_support={"report_schema_version": "v0.1"},
            checks={"health": "pass"},
            warnings=["warn"],
        )
        result = validate_demo_evidence_bundle(bundle)
        assert result is bundle


# ===================================================================
# Class 12: validate_demo_evidence_bundle — invalid bundles
# ===================================================================


class TestValidateBundleInvalid:
    def test_rejects_non_dict(self):
        """Rejects non-dict input."""
        with pytest.raises(ValueError, match="must be a dict"):
            validate_demo_evidence_bundle("not a dict")  # type: ignore[arg-type]

    def test_rejects_missing_technical_demo_only(self):
        """Rejects bundle without technical_demo_only."""
        bundle = build_demo_evidence_bundle()
        del bundle["technical_demo_only"]
        with pytest.raises(ValueError, match="technical_demo_only"):
            validate_demo_evidence_bundle(bundle)

    def test_rejects_false_technical_demo_only(self):
        """Rejects bundle with technical_demo_only=False."""
        bundle = build_demo_evidence_bundle()
        bundle["technical_demo_only"] = False
        with pytest.raises(ValueError, match="technical_demo_only"):
            validate_demo_evidence_bundle(bundle)

    def test_rejects_wrong_product(self):
        """Rejects bundle with wrong product name."""
        bundle = build_demo_evidence_bundle()
        bundle["product"] = "Aramis"
        with pytest.raises(ValueError, match="product"):
            validate_demo_evidence_bundle(bundle)

    def test_rejects_wrong_product_question(self):
        """Rejects bundle with wrong product_question."""
        bundle = build_demo_evidence_bundle()
        bundle["product_question"] = "Wrong question"
        with pytest.raises(ValueError, match="product_question"):
            validate_demo_evidence_bundle(bundle)

    def test_rejects_empty_evidence_version(self):
        """Rejects bundle with empty evidence_version."""
        bundle = build_demo_evidence_bundle()
        bundle["evidence_version"] = ""
        with pytest.raises(ValueError, match="evidence_version"):
            validate_demo_evidence_bundle(bundle)

    def test_rejects_empty_scenario_id(self):
        """Rejects bundle with empty scenario_id."""
        bundle = build_demo_evidence_bundle()
        bundle["scenario_id"] = ""
        with pytest.raises(ValueError, match="scenario_id"):
            validate_demo_evidence_bundle(bundle)

    def test_rejects_empty_disclaimer(self):
        """Rejects bundle with empty disclaimer."""
        bundle = build_demo_evidence_bundle()
        bundle["disclaimer"] = ""
        with pytest.raises(ValueError, match="disclaimer"):
            validate_demo_evidence_bundle(bundle)

    def test_rejects_missing_safety_notes(self):
        """Rejects bundle without safety_notes."""
        bundle = build_demo_evidence_bundle()
        del bundle["safety_notes"]
        with pytest.raises(ValueError, match="safety_notes"):
            validate_demo_evidence_bundle(bundle)

    def test_rejects_empty_safety_notes(self):
        """Rejects bundle with empty safety_notes list."""
        bundle = build_demo_evidence_bundle()
        bundle["safety_notes"] = []
        with pytest.raises(ValueError, match="safety_notes"):
            validate_demo_evidence_bundle(bundle)

    def test_rejects_safety_notes_with_non_string(self):
        """Rejects bundle with non-string in safety_notes."""
        bundle = build_demo_evidence_bundle()
        bundle["safety_notes"] = ["valid", 123]  # type: ignore[list-item]
        with pytest.raises(ValueError, match="safety_notes"):
            validate_demo_evidence_bundle(bundle)

    def test_rejects_bundle_with_aramis_in_optional_field(self):
        """Rejects bundle with 'Aramis' in optional field."""
        bundle = build_demo_evidence_bundle(
            checks={"check": "Aramis check failed"},
        )
        with pytest.raises(ValueError, match="Aramis"):
            validate_demo_evidence_bundle(bundle)

    def test_rejects_bundle_with_clinical_replacement_language(self):
        """Rejects bundle with diagnosis in warnings."""
        bundle = build_demo_evidence_bundle(
            warnings=["diagnosis result available"],
        )
        with pytest.raises(ValueError, match="clinical"):
            validate_demo_evidence_bundle(bundle)


# ===================================================================
# Class 13: JSON serializability
# ===================================================================


class TestJsonSerializable:
    def test_bundle_is_json_serializable(self):
        """Evidence bundle is JSON-serializable."""
        bundle = build_demo_evidence_bundle(
            base_url="http://example.com",
            request_id="req-001",
            job_id="job-001",
            model_status="ready",
            model_version="v0.1",
            feature_schema_version="v0.1",
            prediction_status="completed",
            decision_support={"report_schema_version": "v0.1"},
            checks={"health": "pass", "model_version": "pass"},
            warnings=["warning 1"],
        )
        # Should not raise
        json_str = json.dumps(bundle)
        assert isinstance(json_str, str)
        assert len(json_str) > 0

    def test_json_dumps_helper_validates(self):
        """json_dumps_evidence_bundle validates before serializing."""
        bundle = build_demo_evidence_bundle()
        json_str = json_dumps_evidence_bundle(bundle)
        parsed = json.loads(json_str)
        assert parsed["technical_demo_only"] is True
        assert parsed["product"] == "Bremen"

    def test_json_dumps_helper_raises_on_invalid(self):
        """json_dumps_evidence_bundle raises ValueError on invalid bundle."""
        bundle = build_demo_evidence_bundle()
        bundle["product"] = "Aramis"
        with pytest.raises(ValueError, match="product"):
            json_dumps_evidence_bundle(bundle)


# ===================================================================
# Class 14: Deterministic output
# ===================================================================


class TestDeterministicOutput:
    def test_two_calls_produce_identical_output(self):
        """Two calls with same arguments produce identical output."""
        b1 = build_demo_evidence_bundle(
            base_url="http://example.com",
            request_id="req-001",
            checks={"health": "pass"},
            warnings=["warn"],
        )
        b2 = build_demo_evidence_bundle(
            base_url="http://example.com",
            request_id="req-001",
            checks={"health": "pass"},
            warnings=["warn"],
        )
        assert b1 == b2

    def test_two_payload_calls_produce_identical_output(self):
        """Two payload calls produce identical output."""
        p1 = build_demo_feature_artifact_payload()
        p2 = build_demo_feature_artifact_payload()
        assert p1 == p2


# ===================================================================
# Class 15: No real patient data
# ===================================================================


class TestNoRealPatientData:
    def test_payload_contains_no_patient_id(self):
        """Payload does not contain patient_id."""
        payload = build_demo_feature_artifact_payload()
        assert "patient_id" not in payload
        if payload.get("metadata"):
            assert "patient_id" not in payload["metadata"]

    def test_bundle_contains_no_patient_data(self):
        """Bundle does not contain patient identifiers."""
        bundle = build_demo_evidence_bundle()
        bundle_str = json.dumps(bundle).lower()
        # No patient-like identifiers
        assert "patient_id" not in bundle_str
        assert "patient_name" not in bundle_str
        assert "patient-" not in bundle_str

    def test_payload_metadata_is_synthetic(self):
        """Payload metadata clearly states synthetic origin."""
        payload = build_demo_feature_artifact_payload()
        assert "technical_demo_only" in json.dumps(
            payload["metadata"]
        ).lower()
        assert "demo_evidence_pack" in payload["metadata"]["preprocessing_source"]


# ===================================================================
# Class 16: No H5/model/network dependencies
# ===================================================================


class TestNoDependencies:
    def test_module_stdlib_only(self):
        """Module uses only standard-library imports."""
        import_names = _ast_import_names(MODULE_PATH)
        # Allow stdlib + bremen (our own package)
        prohibited = {
            "h5py", "numpy", "pandas", "joblib", "sklearn",
            "boto3", "requests", "httpx", "urllib", "aiohttp",
            "fastapi", "uvicorn", "starlette", "flask",
            "docker", "terraform", "pickle", "xrd_preprocessing",
            "eosdx_container",
        }
        found = import_names & prohibited
        assert not found, f"Module imports prohibited modules: {found}"

    def test_no_h5_references(self):
        """Module does not reference h5, hdf5, or h5py."""
        source = MODULE_PATH.read_text(encoding="utf-8").lower()
        assert ".h5" not in source
        assert ".hdf5" not in source
        assert "h5py" not in source

    def test_no_joblib_references(self):
        """Module does not reference joblib."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "joblib.load" not in source
        assert "joblib" not in source.lower()

    def test_no_pickle_references(self):
        """Module does not reference pickle."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "pickle.load" not in source

    def test_no_boto3_or_requests(self):
        """Module does not import boto3, requests, httpx."""
        import_names = _ast_import_names(MODULE_PATH)
        assert "boto3" not in import_names
        assert "botocore" not in import_names
        assert "requests" not in import_names
        assert "httpx" not in import_names

    def test_no_network_imports(self):
        """Module does not have top-level urllib import."""
        import_names = _ast_import_names(MODULE_PATH)
        assert "urllib" not in import_names


# ===================================================================
# Class 17: Product-owner demo usefulness
# ===================================================================


class TestProductOwnerDemoUsefulness:
    def test_bundle_supports_demo_story(self):
        """Bundle supports the demo story: service up, model visible,
        feature artifact accepted, decision-support returned, every
        step has request_id/status/warnings."""
        bundle = build_demo_evidence_bundle(
            base_url="http://example.com",
            request_id="req-001",
            job_id="job-001",
            model_status="ready",
            model_version="v0.1",
            feature_schema_version="v0.1",
            prediction_status="completed",
            decision_support={
                "report_schema_version": "v0.1",
                "prediction_summary": {
                    "p_mri_needed": 0.62,
                    "triage_recommendation": "MRI_RECOMMENDED",
                },
            },
            checks={"health": "pass", "model_version": "pass", "prediction": "pass"},
            warnings=[],
        )
        # Verify the demo story elements
        assert bundle["product"] == "Bremen"
        assert bundle["model_status"] == "ready"
        assert bundle["model_version"] == "v0.1"
        assert bundle["feature_schema_version"] == "v0.1"
        assert bundle["prediction_status"] == "completed"
        assert bundle["decision_support"] is not None
        assert bundle["checks"] == {
            "health": "pass",
            "model_version": "pass",
            "prediction": "pass",
        }
        assert bundle["warnings"] == []
        assert bundle["request_id"] == "req-001"
        assert bundle["technical_demo_only"] is True

    def test_disclaimer_is_present_and_visible(self):
        """disclaimer is present and states the demo-only nature."""
        bundle = build_demo_evidence_bundle()
        assert len(bundle["disclaimer"]) > 50
        assert "technical product demo" in bundle["disclaimer"].lower()
        assert "not a clinical result" in bundle["disclaimer"].lower()


# ===================================================================
# Helper: AST import names
# ===================================================================


def _ast_import_names(path: Path) -> set[str]:
    """Return all imported top-level module names from a Python file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names
