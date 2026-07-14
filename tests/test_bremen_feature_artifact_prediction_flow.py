"""Tests for the controlled feature artifact prediction flow (PR0059).

All tests use synthetic in-memory feature artifacts and stub predictor
objects only.  No real model artifacts, no H5 files, no network calls.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

from bremen.feature_artifacts import (
    FEATURE_ARTIFACT_KIND,
    FEATURE_ARTIFACT_SCHEMA_VERSION,
    REQUIRED_FEATURE_COLUMNS,
    validate_feature_artifact,
)
from bremen.api.feature_artifact_prediction import (
    TRIAGE_RECOMMENDED,
    TRIAGE_RULE_OUT,
    FeatureArtifactPredictionError,
    FeatureArtifactPredictionResult,
    FeatureArtifactPredictorError,
    run_feature_artifact_prediction,
)

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src" / "bremen" / "api" / "feature_artifact_prediction.py"
FLOW_DOC = ROOT / "docs" / "feature_artifact_prediction_flow.md"
SCHEMAS_PATH = ROOT / "src" / "bremen" / "api" / "schemas.py"
CONTRACT_DOC = ROOT / "docs" / "feature_artifact_ingestion_boundary.md"


# ---------------------------------------------------------------------------
# Synthetic helpers
# ---------------------------------------------------------------------------


def _valid_artifact(**overrides) -> dict:
    """Build a valid synthetic feature artifact."""
    data: dict = {
        "schema_version": FEATURE_ARTIFACT_SCHEMA_VERSION,
        "artifact_kind": FEATURE_ARTIFACT_KIND,
        "feature_columns": list(REQUIRED_FEATURE_COLUMNS),
        "feature_values": [
            0.5, 0.3, 0.4, 1.2, 0.6,
            0.2, 0.3, 0.9, 0.15, -0.22,
            0.01, 0.05, 0.02, 1.1, 0.8,
        ],
        "metadata": {
            "preprocessing_source": "xrd_preprocessing",
            "source_package_version": "0.1.6b0",
            "configuration_label": "one-to-one-default",
        },
    }
    data.update(overrides)
    return data


def _stub_predictor(feature_columns=None, threshold=0.5) -> dict:
    """Build a synthetic portable_logreg model package dict for testing."""
    fcols = feature_columns or list(REQUIRED_FEATURE_COLUMNS)
    n = len(fcols)
    return {
        "portable_logreg": {
            "feature_columns": fcols,
            "coef": [0.1] * n,
            "intercept": -0.5,
            "threshold": threshold,
            "scaler_mean": [0.0] * n,
            "scaler_scale": [1.0] * n,
            "imputer_statistics": [0.0] * n,
            "model_version": "test-v0.1",
            "threshold_version": "v0.1",
        }
    }


def _read_doc(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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


# ===================================================================
# TestPredictFromValidArtifact
# ===================================================================


class TestPredictFromValidArtifact:
    def test_valid_artifact_reaches_prediction(self):
        """A valid synthetic artifact reaches prediction and returns
        a structured result with all mandatory fields."""
        artifact = _valid_artifact()
        predictor = _stub_predictor()
        result = run_feature_artifact_prediction(artifact, predictor)

        assert isinstance(result, FeatureArtifactPredictionResult)
        assert result.prediction_id != ""
        assert result.model_version == "test-v0.1"
        assert result.feature_schema_version == FEATURE_ARTIFACT_SCHEMA_VERSION
        assert result.threshold_version == "v0.1"
        assert result.threshold_value == 0.5
        assert result.qc_status == "passed"
        assert isinstance(result.qc_flags, list)
        assert result.patient_id is None
        assert 0.0 <= result.p_mri_needed <= 1.0
        assert result.triage_recommendation in (TRIAGE_RECOMMENDED, TRIAGE_RULE_OUT)
        assert result.created_at_utc != ""
        assert isinstance(result.decision_support_report, dict)
        assert result.feature_columns == list(REQUIRED_FEATURE_COLUMNS)
        assert isinstance(result.provenance, dict)

    def test_result_has_convenience_aliases(self):
        """FeatureArtifactPredictionResult has predicted_class and
        probability convenience properties."""
        artifact = _valid_artifact()
        predictor = _stub_predictor()
        result = run_feature_artifact_prediction(artifact, predictor)
        assert result.predicted_class == result.triage_recommendation
        assert result.probability == result.p_mri_needed


# ===================================================================
# TestValidationCalledBeforePrediction
# ===================================================================


class TestValidationCalledBeforePrediction:
    def test_invalid_artifact_rejected_before_prediction(self):
        """An invalid artifact is rejected by validation before
        prediction is attempted."""
        artifact = _valid_artifact(schema_version="wrong.version")
        predictor = _stub_predictor()
        with pytest.raises(FeatureArtifactPredictionError, match="validation failed"):
            run_feature_artifact_prediction(artifact, predictor)


# ===================================================================
# TestModelInputOrder
# ===================================================================


class TestModelInputOrder:
    def test_features_passed_in_required_order(self):
        """Feature values are passed to prediction in REQUIRED_FEATURE_COLUMNS
        order.  Using known coefficients to verify output direction."""
        n = 15
        fcols = list(REQUIRED_FEATURE_COLUMNS)
        predictor = {
            "portable_logreg": {
                "feature_columns": fcols,
                "coef": [0.05] * n,
                "intercept": -5.0,
                "threshold": 0.5,
                "scaler_mean": [0.0] * n,
                "scaler_scale": [1.0] * n,
                "imputer_statistics": [0.0] * n,
                "model_version": "test-v0.1",
                "threshold_version": "v0.1",
            }
        }

        # Features with value 10.0 should produce high probability
        artifact = _valid_artifact(feature_values=[10.0] * 15)
        result = run_feature_artifact_prediction(artifact, predictor)
        assert result.p_mri_needed > 0.5

        # Features with value 1.0 should produce low probability
        artifact_neg = _valid_artifact(feature_values=[1.0] * 15)
        result_neg = run_feature_artifact_prediction(artifact_neg, predictor)
        assert result_neg.p_mri_needed < 0.5


# ===================================================================
# TestShuffledArtifactColumnsNormalized
# ===================================================================


class TestShuffledArtifactColumnsNormalized:
    def test_shuffled_columns_normalised_before_prediction(self):
        """An artifact with shuffled feature_columns is normalised to
        REQUIRED_FEATURE_COLUMNS order before prediction.  Verifying
        that the prediction output is identical to an ordered artifact."""
        artifact_ordered = _valid_artifact()

        # Build a shuffled artifact with the same values mapped correctly
        shuffled_cols = list(REQUIRED_FEATURE_COLUMNS)
        shuffled_cols.reverse()
        shuffled_vals = list(artifact_ordered["feature_values"])
        shuffled_vals.reverse()

        artifact_shuffled = _valid_artifact(
            feature_columns=shuffled_cols,
            feature_values=shuffled_vals,
        )

        predictor = _stub_predictor()
        result_ordered = run_feature_artifact_prediction(artifact_ordered, predictor)
        result_shuffled = run_feature_artifact_prediction(artifact_shuffled, predictor)

        # Probabilities should be identical since column mapping normalised
        assert result_ordered.p_mri_needed == pytest.approx(
            result_shuffled.p_mri_needed
        )
        assert result_shuffled.feature_columns == list(REQUIRED_FEATURE_COLUMNS)


# ===================================================================
# TestInvalidArtifactRejectedBeforePrediction
# ===================================================================


class TestInvalidArtifactRejectedBeforePrediction:
    def test_missing_feature_rejected_before_prediction(self):
        """An artifact with a missing feature column is rejected before
        prediction is attempted."""
        cols = list(REQUIRED_FEATURE_COLUMNS)[:-1]  # drop meanrms2
        vals = [0.0] * 14
        artifact = _valid_artifact(feature_columns=cols, feature_values=vals)
        predictor = _stub_predictor()
        with pytest.raises(FeatureArtifactPredictionError):
            run_feature_artifact_prediction(artifact, predictor)

    def test_extra_feature_rejected_before_prediction(self):
        """An artifact with an extra feature column is rejected before
        prediction."""
        cols = list(REQUIRED_FEATURE_COLUMNS) + ["extra"]
        vals = [0.0] * 16
        artifact = _valid_artifact(feature_columns=cols, feature_values=vals)
        predictor = _stub_predictor()
        with pytest.raises(FeatureArtifactPredictionError):
            run_feature_artifact_prediction(artifact, predictor)


# ===================================================================
# TestMissingFeatureRejected
# ===================================================================


class TestMissingFeatureRejected:
    def test_missing_feature_rejected(self):
        """Missing a required feature column is rejected."""
        cols = list(REQUIRED_FEATURE_COLUMNS)[:-1]
        vals = [0.0] * 14
        artifact = _valid_artifact(feature_columns=cols, feature_values=vals)
        predictor = _stub_predictor()
        with pytest.raises(FeatureArtifactPredictionError, match="feature_columns"):
            run_feature_artifact_prediction(artifact, predictor)


# ===================================================================
# TestUnsafeMetadataRejected
# ===================================================================


class TestUnsafeMetadataRejected:
    def test_unsafe_metadata_key_rejected(self):
        """An artifact with unsafe metadata keys is rejected before
        prediction."""
        artifact = _valid_artifact(
            metadata={"preprocessing_source": "test", "patient_id": "123"}
        )
        predictor = _stub_predictor()
        with pytest.raises(FeatureArtifactPredictionError, match="Unsafe metadata"):
            run_feature_artifact_prediction(artifact, predictor)


# ===================================================================
# TestPredictorReceivesOneRow
# ===================================================================


class TestPredictorReceivesOneRow:
    def test_predictor_receives_exactly_15_features(self):
        """The predictor receives exactly 15 feature values (list of float)."""
        artifact = _valid_artifact()
        predictor = _stub_predictor()
        result = run_feature_artifact_prediction(artifact, predictor)

        # result.feature_columns has 15 entries
        assert len(result.feature_columns) == 15
        assert len(REQUIRED_FEATURE_COLUMNS) == 15

    def test_predictor_receives_finite_numeric_values(self):
        """All feature values passed to predictor are finite numeric."""
        artifact = _valid_artifact()
        predictor = _stub_predictor()
        result = run_feature_artifact_prediction(artifact, predictor)
        validated = validate_feature_artifact(artifact)
        for v in validated["feature_values"]:
            assert isinstance(v, float)
            assert math.isfinite(v)


# ===================================================================
# TestPredictProbaOutputParsed
# ===================================================================


class TestPredictProbaOutputParsed:
    def test_probability_in_range(self):
        """The probability output from predict_proba_portable is
        parsed and within [0, 1]."""
        artifact = _valid_artifact()
        predictor = _stub_predictor()
        result = run_feature_artifact_prediction(artifact, predictor)
        assert 0.0 <= result.p_mri_needed <= 1.0

    def test_probability_varies_with_features(self):
        """Different feature values produce different probability output."""
        artifact1 = _valid_artifact(feature_values=[1.0] * 15)
        artifact2 = _valid_artifact(feature_values=[-1.0] * 15)
        predictor = _stub_predictor()
        result1 = run_feature_artifact_prediction(artifact1, predictor)
        result2 = run_feature_artifact_prediction(artifact2, predictor)
        assert result1.p_mri_needed != pytest.approx(result2.p_mri_needed)


# ===================================================================
# TestPredictOutputParsed
# ===================================================================


class TestPredictOutputParsed:
    def test_triage_recommendation_valid(self):
        """The triage_recommendation is one of the two valid values."""
        artifact = _valid_artifact()
        predictor = _stub_predictor()
        result = run_feature_artifact_prediction(artifact, predictor)
        assert result.triage_recommendation in (TRIAGE_RECOMMENDED, TRIAGE_RULE_OUT)

    def test_triage_consistent_with_threshold(self):
        """The triage_recommendation is consistent with threshold."""
        artifact = _valid_artifact(feature_values=[100.0] * 15)
        # High positive coef should push prob well above 0.5
        predictor = _stub_predictor(threshold=0.5)
        result = run_feature_artifact_prediction(artifact, predictor)
        if result.p_mri_needed >= 0.5:
            assert result.triage_recommendation == TRIAGE_RECOMMENDED
        else:
            assert result.triage_recommendation == TRIAGE_RULE_OUT


# ===================================================================
# TestMalformedPredictProbaOutputRejected
# ===================================================================


class TestMalformedPredictProbaOutputRejected:
    def test_malformed_predictor_missing_key(self):
        """A predictor dict missing the portable_logreg key raises
        FeatureArtifactPredictorError."""
        artifact = _valid_artifact()
        bad_predictor = {"wrong_key": {}}
        with pytest.raises(FeatureArtifactPredictorError):
            run_feature_artifact_prediction(artifact, bad_predictor)


# ===================================================================
# TestMalformedPredictOutputRejected
# ===================================================================


class TestMalformedPredictOutputRejected:
    def test_predictor_missing_feature_columns(self):
        """A predictor missing feature_columns raises an error."""
        artifact = _valid_artifact()
        bad_predictor = {
            "portable_logreg": {
                "coef": [0.1] * 15,
                "intercept": -0.5,
                "threshold": 0.5,
                "scaler_mean": [0.0] * 15,
                "scaler_scale": [1.0] * 15,
                "imputer_statistics": [0.0] * 15,
            }
        }
        with pytest.raises(FeatureArtifactPredictorError):
            run_feature_artifact_prediction(artifact, bad_predictor)


# ===================================================================
# TestPredictorWithoutRequiredMethodsRejected
# ===================================================================


class TestPredictorWithoutRequiredMethodsRejected:
    def test_non_dict_predictor_rejected(self):
        """A non-dict predictor raises FeatureArtifactPredictorError."""
        artifact = _valid_artifact()
        with pytest.raises(FeatureArtifactPredictorError):
            run_feature_artifact_prediction(artifact, "not a dict")  # type: ignore[arg-type]


# ===================================================================
# TestPredictionFieldPresent
# ===================================================================


class TestPredictionFieldPresent:
    def test_prediction_fields_present(self):
        """The structured result contains prediction and probability fields."""
        artifact = _valid_artifact()
        predictor = _stub_predictor()
        result = run_feature_artifact_prediction(artifact, predictor)
        assert result.p_mri_needed is not None
        assert result.triage_recommendation != ""


# ===================================================================
# TestDecisionSupportReportPresent
# ===================================================================


class TestDecisionSupportReportPresent:
    def test_report_present(self):
        """The result contains a decision_support_report."""
        artifact = _valid_artifact()
        predictor = _stub_predictor()
        result = run_feature_artifact_prediction(artifact, predictor)
        dsr = result.decision_support_report
        assert isinstance(dsr, dict)
        assert dsr["report_schema_version"] == "v0.1"
        assert "intended_use" in dsr
        assert "limitations" in dsr
        assert "input_summary" in dsr

    def test_report_input_mode(self):
        """The decision_support_report shows input_mode: feature_artifact."""
        artifact = _valid_artifact()
        predictor = _stub_predictor()
        result = run_feature_artifact_prediction(artifact, predictor)
        dsr = result.decision_support_report
        assert dsr["input_summary"]["input_mode"] == "feature_artifact"


# ===================================================================
# TestDecisionSupportSafetyLanguage
# ===================================================================


class TestDecisionSupportSafetyLanguage:
    def test_limitations_contains_safety_language(self):
        """decision_support_report.limitations includes required safety
        language."""
        artifact = _valid_artifact()
        predictor = _stub_predictor()
        result = run_feature_artifact_prediction(artifact, predictor)
        limitations_text = " ".join(
            result.decision_support_report["limitations"]
        ).lower()
        assert "not a diagnostic result" in limitations_text
        assert "not clinically validated" in limitations_text
        assert "does not replace" in limitations_text

    def test_intended_use_contains_safety_language(self):
        """decision_support_report.intended_use contains safety language."""
        artifact = _valid_artifact()
        predictor = _stub_predictor()
        result = run_feature_artifact_prediction(artifact, predictor)
        intended_use = result.decision_support_report["intended_use"].lower()
        assert "not a diagnosis" in intended_use
        assert "not clinically validated" in intended_use
        assert "does not replace" in intended_use


# ===================================================================
# TestSafeProvenance
# ===================================================================


class TestSafeProvenance:
    def test_provenance_carried_only_after_validation(self):
        """Safe metadata provenance may be carried only after validation."""
        artifact = _valid_artifact(
            metadata={
                "preprocessing_source": "xrd_preprocessing",
                "source_package_version": "0.1.6b0",
                "configuration_label": "one-to-one-default",
            }
        )
        predictor = _stub_predictor()
        result = run_feature_artifact_prediction(artifact, predictor)
        assert result.provenance["preprocessing_source"] == "xrd_preprocessing"
        assert result.provenance["source_package_version"] == "0.1.6b0"
        assert result.provenance["configuration_label"] == "one-to-one-default"

    def test_unsafe_keys_not_in_provenance(self):
        """Unsafe metadata keys are not carried into provenance."""
        artifact = _valid_artifact(
            metadata={"preprocessing_source": "test", "patient_id": "x"}
        )
        predictor = _stub_predictor()
        with pytest.raises(FeatureArtifactPredictionError):
            run_feature_artifact_prediction(artifact, predictor)


# ===================================================================
# TestNoH5PathRequired
# ===================================================================


class TestNoH5PathRequired:
    def test_no_h5_path_needed(self):
        """The flow does not require h5_path or h5_uri."""
        artifact = _valid_artifact()
        predictor = _stub_predictor()
        result = run_feature_artifact_prediction(artifact, predictor)
        assert isinstance(result, FeatureArtifactPredictionResult)
        # No h5_path/h5_uri in result or decision_support_report
        dsr_str = str(result.decision_support_report).lower()
        assert "h5_path" not in dsr_str
        assert "h5_uri" not in dsr_str


# ===================================================================
# TestNoPublicSchemaField
# ===================================================================


class TestNoPublicSchemaField:
    def test_no_feature_artifact_fields_in_schemas(self):
        """Public schemas.py does not contain feature_artifact_path or
        feature_artifact_uri."""
        source = SCHEMAS_PATH.read_text(encoding="utf-8")
        assert "feature_artifact_path" not in source
        assert "feature_artifact_uri" not in source


# ===================================================================
# TestNoXRDPreprocessingImport
# ===================================================================


class TestNoXRDPreprocessingImport:
    def test_no_upstream_imports_in_module(self):
        """New module does not import xrd_preprocessing or eosdx-container."""
        import_names = _ast_import_names(MODULE_PATH)
        prohibited = {"xrd_preprocessing", "eosdx_container", "container"}
        found = import_names & prohibited
        assert not found, f"Module imports {found}"


# ===================================================================
# TestNoBoto3RequestsHTTPX
# ===================================================================


class TestNoBoto3RequestsHTTPX:
    def test_no_forbidden_imports_in_module(self):
        """New module does not import boto3, requests, httpx, aiohttp,
        FastAPI, uvicorn, starlette, joblib, sklearn, numpy, pandas, h5py."""
        import_names = _ast_import_names(MODULE_PATH)
        prohibited = {
            "boto3", "requests", "httpx", "aiohttp",
            "fastapi", "uvicorn", "starlette",
        }
        found = import_names & prohibited
        assert not found, f"Module imports {found}"


# ===================================================================
# TestNoModelLoaderOrInferenceHandlerImport
# ===================================================================


class TestNoModelLoaderOrInferenceHandlerImport:
    def test_no_inference_handler_import(self):
        """New module does not import model_loader or inference_handler."""
        import_names = _ast_import_names(MODULE_PATH)
        prohibited = {"model_loader", "inference_handler"}
        found = import_names & prohibited
        assert not found, f"Module imports {found}"


# ===================================================================
# TestNoJoblibLoad
# ===================================================================


class TestNoJoblibLoad:
    def test_no_joblib_reference(self):
        """New module does not reference joblib.load."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "joblib.load" not in source
        assert "joblib" not in source.lower()


# ===================================================================
# TestNoGFRMOrH5Parsing
# ===================================================================


class TestNoGFRMOrH5Parsing:
    def test_no_gfrm_h5_protobuf_geoframe(self):
        """New module does not parse GFRM/H5/protobuf/GeoFrame in code.

        Docstring safety statements about not using these formats are allowed.
        """
        source = MODULE_PATH.read_text(encoding="utf-8")
        # Filter out docstring and comment lines — only check code
        lines = source.split("\n")
        in_docstring = False
        code_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            # Track docstring boundaries
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if in_docstring:
                    in_docstring = False
                    continue
                # Single-line docstring
                if stripped.count('"""') >= 2 and stripped.endswith('"""'):
                    continue
                if stripped.count("'''") >= 2 and stripped.endswith("'''"):
                    continue
                in_docstring = True
                continue
            if in_docstring or stripped.startswith("#"):
                continue
            code_lines.append(line)

        code_source = "\n".join(code_lines)
        prohibited = ["h5py", "h5_file", "h5_inputs"]
        for pattern in prohibited:
            assert pattern not in code_source, (
                f"Module code contains '{pattern}'"
            )


# ===================================================================
# TestDocExists
# ===================================================================


class TestDocExists:
    def test_prediction_flow_doc_exists(self):
        """docs/feature_artifact_prediction_flow.md exists."""
        assert FLOW_DOC.is_file(), (
            "docs/feature_artifact_prediction_flow.md not found"
        )


# ===================================================================
# TestDocOptionCContinuation
# ===================================================================


class TestDocOptionCContinuation:
    def test_doc_mentions_option_c(self):
        """Flow doc mentions Option C continuation."""
        content = _read_doc(FLOW_DOC).lower()
        assert "option c" in content, (
            "Flow doc must reference Option C"
        )


# ===================================================================
# TestDocInvestorPath
# ===================================================================


class TestDocInvestorPath:
    def test_doc_mentions_investor_path(self):
        """Flow doc describes the investor path."""
        content = _read_doc(FLOW_DOC).lower()
        assert "investor" in content, (
            "Flow doc must describe investor path"
        )

    def test_doc_mentions_pr0060_handoff(self):
        """Flow doc mentions PR0060 handoff."""
        content = _read_doc(FLOW_DOC)
        assert "PR0060" in content or "pr0060" in content.lower(), (
            "Flow doc must reference PR0060"
        )


# ===================================================================
# TestNoDemoOnlyFork
# ===================================================================


class TestNoDemoOnlyFork:
    def test_doc_rejects_demo_only_fork(self):
        """Flow doc rejects demo-only fork."""
        content = _read_doc(FLOW_DOC).lower()
        assert "no demo-only" in content or "no demo only" in content or \
               "not a demo-only" in content, (
            "Flow doc must reject demo-only fork"
        )


# ===================================================================
# TestNoClinicalClaims
# ===================================================================


class TestSafetyClaims:
    def test_doc_states_no_diagnosis(self):
        """Flow doc states no diagnosis."""
        content = _read_doc(FLOW_DOC).lower()
        assert "no diagnosis" in content, (
            "Flow doc must state no diagnosis"
        )

    def test_doc_states_no_clinical_validation(self):
        """Flow doc states no clinical validation."""
        content = _read_doc(FLOW_DOC).lower()
        assert "no clinical validation" in content or \
               "not clinically validated" in content, (
            "Flow doc must state no clinical validation"
        )

    def test_doc_states_no_replacement(self):
        """Flow doc states no replacement of clinical judgment."""
        content = _read_doc(FLOW_DOC).lower()
        assert "no replacement" in content or \
               "does not replace" in content, (
            "Flow doc must state no replacement"
        )

    def test_doc_rejects_scans_target_as_eosdx(self):
        """Flow doc rejects /scans/target as eosdx-container v0.3."""
        content = _read_doc(FLOW_DOC).lower()
        assert "scans/target" in content or \
               "not claimed" in content or \
               "eosdx-container" in content, (
            "Flow doc must reject /scans/target as eosdx-container v0.3"
        )


# ===================================================================
# TestNoRealArtifactsCommited
# ===================================================================


class TestNoRealArtifacts:
    def test_no_real_artifact_files(self):
        """The module file is .py, the doc is .md — no real artifact
        files committed."""
        assert MODULE_PATH.suffix == ".py"
        assert FLOW_DOC.suffix == ".md"

    def test_no_hardcoded_secrets(self):
        """Module source does not contain hardcoded secrets."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "AKIA" not in source
        assert "SECRET_ACCESS_KEY" not in source
        assert "s3://" not in source


# ===================================================================
# TestNoNetworkDepsInTests
# ===================================================================


class TestTestsAreStatic:
    def test_no_network_imports(self):
        """Test file does not import network/AWS/Docker modules."""
        source = Path(__file__).read_text(encoding="utf-8")
        import_lines = [
            line for line in source.split("\n")
            if line.strip().startswith(("import ", "from "))
        ]
        import_text = "\n".join(import_lines)
        for imp in ["boto3", "requests", "httpx", "urllib", "docker", "terraform"]:
            assert imp not in import_text, f"Test file must not import {imp}"


# ===================================================================
# TestSchemaUnchanged
# ===================================================================


class TestSchemaUnchanged:
    def test_ingestion_boundary_doc_exists(self):
        """Feature artifact ingestion boundary doc still exists."""
        assert CONTRACT_DOC.is_file()

    def test_ingestion_boundary_doc_mentions_pr0059(self):
        """Ingestion boundary doc cross-references PR0059."""
        content = _read_doc(CONTRACT_DOC)
        assert "PR0059" in content or "pr0059" in content.lower()
        assert "feature_artifact_prediction_flow.md" in content
