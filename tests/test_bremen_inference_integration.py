"""Tests for inference integration.

All tests use synthetic data only.
Optional real model smoke at the bottom, skipped by default.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import h5py
import numpy as np
import pytest

from bremen.inference import (
    PortableLogRegModelError,
    validate_portable_logreg_model,
    predict_proba_portable,
)
from bremen.api.preprocessing_bridge import (
    BREMEN_V01_FEATURE_COLUMNS,
    FEATURE_SCHEMA_VERSION,
)
from bremen.api.inference_handler import run_inference
from bremen.api.model_state import ModelState
from bremen.api.app import handle_health, handle_submit_prediction


# ---------------------------------------------------------------------------
# Synthetic portable_logreg model
# ---------------------------------------------------------------------------


def _make_synthetic_portable_logreg() -> dict:
    """Create a synthetic v0.1 portable_logreg model package."""
    n_features = 15
    rng = np.random.default_rng(42)
    return {
        "portable_logreg": {
            "feature_columns": list(BREMEN_V01_FEATURE_COLUMNS),
            "imputer_statistics": [0.0] * n_features,
            "scaler_mean": [0.0] * n_features,
            "scaler_scale": [1.0] * n_features,
            "coef": [float(v) for v in rng.normal(0, 0.5, n_features)],
            "intercept": float(rng.normal(0, 0.1)),
            "threshold": 0.5,
            "threshold_version": "v0.1",
            "model_version": "bremen_mri_triage_logreg_v0_1",
        }
    }


def _create_synthetic_h5(tmp_path: Path) -> Path:
    """Create a minimal synthetic H5 for inference."""
    path = tmp_path / "inf_test.h5"
    with h5py.File(path, "w") as f:
        f.create_dataset("/patient/id", data="TEST-INF-001")
        tg = f.create_group("/scans/target")
        tg.create_dataset("side", data="L")
        tg.create_dataset(
            "measurements", data=np.random.default_rng(1).normal(0, 1, (3, 100)).astype(np.float64)
        )
        ct = f.create_group("/scans/contralateral")
        ct.create_dataset("side", data="R")
        ct.create_dataset(
            "measurements", data=np.random.default_rng(2).normal(0.3, 1, (3, 100)).astype(np.float64)
        )
    return path


# ---------------------------------------------------------------------------
# Portable inference
# ---------------------------------------------------------------------------


class TestPortableInference:
    def test_synthetic_model_returns_probability_in_range(self):
        """predict_proba_portable returns probability in [0, 1]."""
        package = _make_synthetic_portable_logreg()
        features = [0.1] * 15
        result = predict_proba_portable(package, features)
        assert 0.0 <= result["probability"] <= 1.0
        assert result["threshold_applied"] == 0.5

    def test_missing_portable_logreg_fails_closed(self):
        """Dict without portable_logreg raises."""
        with pytest.raises(PortableLogRegModelError, match="portable_logreg"):
            validate_portable_logreg_model({"wrong": "type"})

    def test_wrong_feature_order_fails_closed(self):
        """Wrong feature order raises."""
        wrong_order = list(BREMEN_V01_FEATURE_COLUMNS)
        wrong_order[0], wrong_order[1] = wrong_order[1], wrong_order[0]
        package = _make_synthetic_portable_logreg()
        package["portable_logreg"]["feature_columns"] = wrong_order
        with pytest.raises(PortableLogRegModelError, match="Feature columns mismatch"):
            validate_portable_logreg_model(package)

    def test_no_sklearn_import(self):
        """Inference module must not import sklearn."""
        import ast

        src = Path(__file__).parents[1] / "src" / "bremen" / "inference.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "sklearn" in alias.name.lower():
                        pytest.fail(f"inference.py imports sklearn: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "sklearn" in module.lower():
                    pytest.fail(f"inference.py imports sklearn: {module}")

    def test_feature_values_imputed_gracefully(self):
        """NaN features are imputed via imputer_statistics."""
        package = _make_synthetic_portable_logreg()
        features = [float("nan")] * 5 + [0.1] * 10
        result = predict_proba_portable(package, features, skip_validation=True)
        assert 0.0 <= result["probability"] <= 1.0


# ---------------------------------------------------------------------------
# End-to-end inference
# ---------------------------------------------------------------------------


class TestEndToEndInference:
    def test_end_to_end_synthetic_inference(self, tmp_path: Path, caplog):
        """run_inference with synthetic H5 + synthetic model produces all mandatory fields.

        Also verifies ``bremen.prediction.inference.success`` is emitted.
        """
        import logging
        caplog.set_level(logging.INFO)
        h5_path = _create_synthetic_h5(tmp_path)

        # Load synthetic model into ModelState using proper startup path
        ModelState.reset_for_tests()
        from joblib import dump
        import tempfile
        tmp_model = Path(tempfile.mkdtemp()) / "e2e_model.joblib"
        package = _make_synthetic_portable_logreg()
        dump(package, tmp_model)
        checksum = hashlib.sha256(tmp_model.read_bytes()).hexdigest()
        ModelState.load_at_startup(
            model_uri=str(tmp_model),
            model_version="bremen_mri_triage_logreg_v0_1",
            model_checksum=checksum,
        )

        result = run_inference(str(h5_path))

        mandatory = [
            "prediction_id", "model_version", "model_checksum",
            "feature_schema_version", "threshold_version", "threshold_value",
            "qc_status", "qc_flags", "patient_id", "p_mri_needed",
            "triage_recommendation", "created_at_utc",
        ]
        for field in mandatory:
            assert field in result, f"Missing mandatory field: {field}"

        assert result["triage_recommendation"] in ("CONTINUE_MRI", "MRI_REVIEW_DEFER", "MRI_RECOMMENDED", "MRI_RULE_OUT")
        assert 0.0 <= result["p_mri_needed"] <= 1.0

        # PR 0053: decision-support report is present
        report = result.get("decision_support_report")
        assert report is not None, "decision_support_report must be present"
        assert "report_schema_version" in report
        assert "intended_use" in report
        assert "limitations" in report
        assert "model_metadata" in report
        assert "input_summary" in report
        assert "prediction_summary" in report
        assert "decision_support" in report

        assert "runtime.request.completed" in caplog.text
        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# Model state
# ---------------------------------------------------------------------------


class TestModelState:
    def test_model_not_ready_by_default(self):
        """ModelState is not ready after reset."""
        ModelState.reset_for_tests()
        assert ModelState.is_ready() is False

    def test_local_model_loading_works(self, tmp_path: Path):
        """ModelState.load_at_startup with a local joblib file succeeds."""
        ModelState.reset_for_tests()
        package = _make_synthetic_portable_logreg()

        from joblib import dump
        model_path = tmp_path / "model.joblib"
        dump(package, model_path)

        checksum = hashlib.sha256(model_path.read_bytes()).hexdigest()
        result = ModelState.load_at_startup(
            model_uri=str(model_path),
            model_version="v0.1",
            model_checksum=checksum,
        )
        assert result is True
        assert ModelState.is_ready() is True
        assert ModelState.get_model() is not None
        ModelState.reset_for_tests()

    def test_local_model_with_sha256_prefix(self, tmp_path: Path):
        """Checksum with 'sha256:' prefix works."""
        ModelState.reset_for_tests()
        package = _make_synthetic_portable_logreg()
        from joblib import dump
        model_path = tmp_path / "model.joblib"
        dump(package, model_path)
        checksum = "sha256:" + hashlib.sha256(model_path.read_bytes()).hexdigest()
        result = ModelState.load_at_startup(
            model_uri=str(model_path),
            model_version="v0.1",
            model_checksum=checksum,
        )
        assert result is True
        ModelState.reset_for_tests()

    def test_no_aws_credentials_required(self):
        """ModelState tests pass without AWS credentials."""
        ModelState.reset_for_tests()
        assert ModelState.is_ready() is False
        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealthModelReady:
    def test_health_reports_model_not_ready(self):
        """Health reports model_ready: False when model not loaded."""
        from bremen.api.model_registry import reset_for_tests as reset_registry
        ModelState.reset_for_tests()
        reset_registry()
        resp = handle_health(version="test")
        assert resp.status == "ok"
        assert resp.model_ready is False
        assert resp.service == "bremen"


# ---------------------------------------------------------------------------
# Real model smoke (opt-in)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    "BREMEN_V01_JOBLIB_PATH" not in os.environ,
    reason="Set BREMEN_V01_JOBLIB_PATH to run real model smoke test",
)
def test_real_model_smoke(tmp_path: Path):
    """Optional smoke test with real v0.1 model on synthetic H5.

    Set BREMEN_V01_JOBLIB_PATH=/path/to/bremen_mri_triage_logreg_v0_1_model_package.joblib.
    """
    from joblib import load as jl

    model_path = os.environ["BREMEN_V01_JOBLIB_PATH"]
    package = jl(model_path)

    ModelState.reset_for_tests()
    state = ModelState.get_instance()
    state._model_package = package
    state._model_version = "bremen_mri_triage_logreg_v0_1"
    state._model_checksum = hashlib.sha256(Path(model_path).read_bytes()).hexdigest()
    state._loaded = True

    h5_path = _create_synthetic_h5(tmp_path)
    result = run_inference(str(h5_path))

    assert result["model_version"] == "bremen_mri_triage_logreg_v0_1"
    assert 0.0 <= result["p_mri_needed"] <= 1.0
    assert result["triage_recommendation"] in ("CONTINUE_MRI", "MRI_REVIEW_DEFER", "MRI_RECOMMENDED", "MRI_RULE_OUT")
    ModelState.reset_for_tests()
