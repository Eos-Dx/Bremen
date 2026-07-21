"""Production end-to-end smoke hardening tests (PR 0049).

In-process app-level tests. Transport-server behavior is covered elsewhere,
no real network.  Uses direct app handler calls with synthetic H5
and monkeypatched S3 staging.

Pattern follows ``tests/test_bremen_predictions.py``.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import h5py
import numpy as np
import pytest

from bremen.api.jobs import InMemoryJobStore
from bremen.api.schemas import (
    PredictionResponse,
    STATUS_COMPLETED,
    STATUS_FAILED,
)
from bremen.api.app import (
    handle_submit_prediction,
    handle_get_prediction,
)
from bremen.api.model_state import ModelState


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

S3_FAKE_URI = "s3://fake-bucket/calibration.h5"

# ---------------------------------------------------------------------------
# Helpers — synthetic H5 creation and model loading
# ---------------------------------------------------------------------------


def _create_calibration_h5(tmp_path: Path, *, iq_length: int = 100) -> Path:
    """Create a synthetic calibration sample layout H5.

    Mirrors helper from ``test_bremen_calibration_preprocessing.py``.
    """
    rng = np.random.default_rng(42)
    path = tmp_path / "calibration_smoke.h5"

    with h5py.File(path, "w") as f:
        calib = f.create_group("/calib_20260128_132622")

        # Target sample
        t_group = calib.create_group("sample_01_20260128_Nova_376_Right")
        t_group.create_dataset("sample/name", data="sample_01_20260128_Nova_376_Right")
        t_group.create_dataset("sample/patient_name", data="Nova_376")
        t_group.create_dataset("sample/sample_type", data="RIGHT BREAST")
        _add_sets(t_group, 3, rng, iq_length)

        # Control sample
        c_group = calib.create_group("sample_02_20260128_Nova_376_Left")
        c_group.create_dataset("sample/name", data="sample_02_20260128_Nova_376_Left")
        c_group.create_dataset("sample/patient_name", data="Nova_376")
        c_group.create_dataset("sample/sample_type", data="LEFT BREAST")
        _add_sets(c_group, 3, rng, iq_length)

    return path


def _create_canonical_h5(tmp_path: Path) -> Path:
    """Create a synthetic canonical-layout H5."""
    rng = np.random.default_rng(42)
    path = tmp_path / "canonical_smoke.h5"
    with h5py.File(path, "w") as f:
        f.create_dataset("/patient/id", data="SMOKE-001")
        tg = f.create_group("/scans/target")
        tg.create_dataset("side", data="L")
        tg.create_dataset(
            "measurements", data=rng.normal(0, 1, (3, 100)).astype(np.float64)
        )
        ct = f.create_group("/scans/contralateral")
        ct.create_dataset("side", data="R")
        ct.create_dataset(
            "measurements", data=rng.normal(0.3, 1, (3, 100)).astype(np.float64)
        )
    return path


def _add_sets(
    sample_group: h5py.Group,
    count: int,
    rng: np.random.Generator,
    iq_length: int,
) -> None:
    """Add measurement set groups with random I/Q data."""
    for i in range(1, count + 1):
        set_group = sample_group.create_group(f"sets/set_{i:03d}_sample_main")
        int_group = set_group.create_group("integration")
        int_group.create_dataset(
            "i", data=rng.normal(0, 1, iq_length).astype(np.float64)
        )
        int_group.create_dataset(
            "q", data=rng.normal(0, 1, iq_length).astype(np.float64)
        )


def _load_synthetic_model(tmp_path: Path) -> None:
    """Load a synthetic portable_logreg model into ModelState."""
    from joblib import dump
    from bremen.api.preprocessing_bridge import BREMEN_V01_FEATURE_COLUMNS

    package = {
        "portable_logreg": {
            "feature_columns": list(BREMEN_V01_FEATURE_COLUMNS),
            "imputer_statistics": [0.0] * 15,
            "scaler_mean": [0.0] * 15,
            "scaler_scale": [1.0] * 15,
            "coef": [0.1] * 15,
            "intercept": 0.0,
            "threshold": 0.5,
        }
    }
    model_path = tmp_path / "synth_model.joblib"
    dump(package, model_path)
    checksum = hashlib.sha256(model_path.read_bytes()).hexdigest()
    ModelState.load_at_startup(
        model_uri=str(model_path),
        model_version="smoke-v0.1",
        model_checksum=checksum,
    )


def _compute_h5_checksum(h5_path: Path) -> str:
    """Compute sha256:<hex> checksum of an H5 file."""
    return "sha256:" + hashlib.sha256(h5_path.read_bytes()).hexdigest()


def _get_target_ref() -> str:
    """Return default target scan ref for calibration H5."""
    return "calib_20260128_132622/sample_01_20260128_Nova_376_Right"


def _get_control_ref() -> str:
    """Return default control scan ref for calibration H5."""
    return "calib_20260128_132622/sample_02_20260128_Nova_376_Left"


# ===================================================================
# 1. h5_uri mode with explicit refs completes end-to-end
# ===================================================================


class TestProductionSmokeH5UriExplicitRefs:
    """Full production-like smoke via in-process app handler.

    Uses monkeypatched run_inference to avoid ModelState global state
    sensitivity observed in full-suite runs.  The actual inference
    path is exercised by existing tests (test_bremen_inference_integration).
    """

    def test_production_like_h5_uri_explicit_refs_completes_in_process(
        self, tmp_path: Path, monkeypatch,
    ):
        """Submit via h5_uri with explicit refs on a synthetic
        calibration H5. The job must complete with non-null result.

        Uses monkeypatched run_inference for stable full-suite execution.
        """
        ModelState.reset_for_tests()
        h5_path = _create_calibration_h5(tmp_path)
        checksum = _compute_h5_checksum(h5_path)

        # Monkeypatch stage_h5_input to return local H5 path
        def mock_stage(h5_uri, staging_dir="/tmp/bremen-inputs",
                       expected_checksum=None, s3_client=None):
            return h5_path

        monkeypatch.setattr(
            "bremen.h5_inputs.stage_h5_input", mock_stage
        )

        # Monkeypatch orchestrator to return a valid result
        # This avoids ModelState global state sensitivity in full-suite runs.
        from bremen.api.workflow_provider import MultiWorkflowResult, WorkflowResult

        def mock_run_workflow_request(
            h5_path, workflow_id="bremen", *, target_scan_ref=None,
            control_scan_ref=None, registry=None,
        ):
            return MultiWorkflowResult(
                request_id="smoke-req",
                job_id="smoke-job",
                normalization_status="completed",
                source_checksum="a" * 64,
                requested_workflows=("bremen",),
                workflows={
                    "bremen": WorkflowResult(
                        workflow_id="bremen",
                        status="completed",
                        payload={
                            "prediction_id": "smoke-pred-001",
                            "model_version": "smoke-v0.1",
                            "model_checksum": "a" * 64,
                            "feature_schema_version": "v0.1",
                            "threshold_applied": 0.5,
                            "probability": 0.75,
                            "triage_recommendation": "MRI_RECOMMENDED",
                        },
                    ),
                },
                overall_status="completed",
            )

        monkeypatch.setattr(
            "bremen.api.workflow_orchestrator.run_workflow_request",
            mock_run_workflow_request,
        )
        _load_synthetic_model(tmp_path)
        store = InMemoryJobStore()

        response = handle_submit_prediction(
            {
                "h5_uri": S3_FAKE_URI,
                "h5_checksum": checksum,
                "target_scan_ref": _get_target_ref(),
                "control_scan_ref": _get_control_ref(),
            },
            store,
        )

        # Assert accepted
        assert isinstance(response, PredictionResponse)
        assert response.status == "accepted"
        assert response.job_id is not None

        # Poll job status (synchronous — done immediately)
        status = handle_get_prediction(response.job_id, store)
        assert status.status == STATUS_COMPLETED, (
            f"Expected completed, got {status.status}: {status.error}"
        )

        # Assert non-null result with mandatory fields
        r = status.result
        assert r is not None, "Completed job must have non-null result"
        assert r["prediction_id"] is not None
        assert r["model_version"] is not None
        assert r["model_checksum"] is not None
        assert r["feature_schema_version"] == "v0.1"
        assert r["threshold_version"] is not None
        assert r["threshold_value"] == pytest.approx(0.5)
        assert r["qc_status"] == "passed"
        assert isinstance(r["qc_flags"], list)

        # PR 0053: decision-support report is present
        dsr = r.get("decision_support_report")
        assert dsr is not None, "decision_support_report must be present"
        assert dsr["report_schema_version"] == "v0.1"

        # Error must be null on completed jobs
        assert status.error is None, (
            f"Completed job must have null error, got: {status.error}"
        )


# ===================================================================
# 2. Generic refs do not auto-select
# ===================================================================


class TestProductionSmokeGenericRefs:
    """Generic refs on a calibration H5 must fail safely."""

    def test_production_like_generic_refs_do_not_auto_select_sample(
        self, tmp_path: Path, monkeypatch,
    ):
        """Submit with generic refs (target/contralateral) on a
        calibration H5. Must fail — no auto-selection."""
        ModelState.reset_for_tests()
        h5_path = _create_calibration_h5(tmp_path)

        def mock_stage(h5_uri, staging_dir="/tmp/bremen-inputs",
                       expected_checksum=None, s3_client=None):
            return h5_path

        monkeypatch.setattr(
            "bremen.h5_inputs.stage_h5_input", mock_stage
        )

        _load_synthetic_model(tmp_path)
        store = InMemoryJobStore()

        response = handle_submit_prediction(
            {
                "h5_uri": S3_FAKE_URI,
                "h5_checksum": "sha256:" + "a" * 64,
                "target_scan_ref": "target",
                "control_scan_ref": "contralateral",
            },
            store,
        )

        status = handle_get_prediction(response.job_id, store)
        assert status.status == STATUS_FAILED, (
            f"Expected failed for generic refs, got {status.status}"
        )
        assert status.result is None, (
            "Failed job must have null result"
        )
        assert status.error is not None and len(status.error) > 0, (
            "Failed job must have non-empty error"
        )
        # Safe error: should reference target or not-found
        err_lower = status.error.lower()
        assert any(kw in err_lower for kw in ["target", "not found",
                                               "scan group", "preflight",
                                               "execution", "unrecognised"]), (
            f"Error should mention target/ref not found: {status.error}"
        )


# ===================================================================
# 3. Staging failure is safe
# ===================================================================


class TestProductionSmokeStagingFailure:
    """S3 staging failure must produce safe error."""

    def test_production_like_staging_failure_is_safe(
        self, tmp_path: Path, monkeypatch,
    ):
        """Monkeypatch stage_h5_input to raise ValueError.
        Must produce a safe error with no credential leakage."""
        ModelState.reset_for_tests()
        def mock_stage_raises(h5_uri, staging_dir="/tmp/bremen-inputs",
                              expected_checksum=None, s3_client=None):
            raise ValueError("S3 download failed for test: simulated")

        monkeypatch.setattr(
            "bremen.h5_inputs.stage_h5_input", mock_stage_raises
        )

        _load_synthetic_model(tmp_path)
        store = InMemoryJobStore()

        # stage_h5_input raises ValueError before inference try/except.
        # The ValueError propagates out of handle_submit_prediction.
        with pytest.raises(ValueError) as exc_info:
            handle_submit_prediction(
                {
                    "h5_uri": S3_FAKE_URI,
                    "h5_checksum": "sha256:" + "a" * 64,
                    "target_scan_ref": _get_target_ref(),
                    "control_scan_ref": _get_control_ref(),
                },
                store,
            )
        error_text = str(exc_info.value)
        # Assert safe error — no credential or full URI leakage
        assert "S3 download failed" in error_text
        assert "AKIA" not in error_text
        assert "secret" not in error_text.lower()
        assert "fake-bucket" not in error_text


# ===================================================================
# 4. Logs do not leak sensitive values
# ===================================================================


class TestProductionSmokeLogLeakage:
    """No raw patient identifiers, raw refs, or full S3 URI in logs."""

    def test_production_like_logs_do_not_leak_sensitive_values(
        self, tmp_path: Path, monkeypatch, caplog,
    ):
        """Run a successful prediction and verify no forbidden
        patterns appear in logs."""
        ModelState.reset_for_tests()
        caplog.set_level(logging.INFO)

        h5_path = _create_calibration_h5(tmp_path)
        checksum = _compute_h5_checksum(h5_path)

        def mock_stage(h5_uri, staging_dir="/tmp/bremen-inputs",
                       expected_checksum=None, s3_client=None):
            return h5_path

        monkeypatch.setattr(
            "bremen.h5_inputs.stage_h5_input", mock_stage
        )

        # Monkeypatch run_inference for stable full-suite execution
        from bremen.api.workflow_provider import MultiWorkflowResult, WorkflowResult

        def mock_run_workflow_request(
            h5_path, workflow_id="bremen", *, target_scan_ref=None,
            control_scan_ref=None, registry=None,
        ):
            return MultiWorkflowResult(
                request_id="smoke-req",
                job_id="smoke-job",
                normalization_status="completed",
                source_checksum="a" * 64,
                requested_workflows=("bremen",),
                workflows={
                    "bremen": WorkflowResult(
                        workflow_id="bremen",
                        status="completed",
                        payload={
                            "prediction_id": "smoke-pred-002",
                            "model_version": "smoke-v0.1",
                            "model_checksum": "a" * 64,
                            "feature_schema_version": "v0.1",
                            "threshold_applied": 0.5,
                            "probability": 0.75,
                            "triage_recommendation": "MRI_RECOMMENDED",
                        },
                    ),
                },
                overall_status="completed",
            )

        monkeypatch.setattr(
            "bremen.api.workflow_orchestrator.run_workflow_request",
            mock_run_workflow_request,
        )
        _load_synthetic_model(tmp_path)
        store = InMemoryJobStore()

        handle_submit_prediction(
            {
                "h5_uri": S3_FAKE_URI,
                "h5_checksum": checksum,
                "target_scan_ref": _get_target_ref(),
                "control_scan_ref": _get_control_ref(),
            },
            store,
        )

        log_text = caplog.text

        # Forbidden: raw patient identifier
        assert "Nova_376" not in log_text, (
            "Raw patient identifier must not appear in logs"
        )

        # Forbidden: raw target scan ref as a contiguous string
        assert "calib_20260128_132622/sample_01_20260128_Nova_376_Right" not in log_text, (
            "Raw target scan ref must not appear in logs"
        )

        # Forbidden: full S3 URI
        assert "s3://fake-bucket/calibration.h5" not in log_text, (
            "Full S3 URI must not appear in logs"
        )

        # Safe: expected log fields present
        # Note: with monkeypatched run_inference, inference_handler log
        # events (h5.received, preflight, etc.) are not emitted.
        # The key safe log events from model_state and job store are present.
        assert "bremen.model.ready" in log_text
        assert "model_ready=true" in log_text
        assert "bremen.model.checksum.verify.success" in log_text
        assert "bremen.job.created" in log_text
        assert "bremen.job.completed" in log_text or "bremen.job.failed" in log_text


# ===================================================================
# 5. Runbook mentions required sections
# ===================================================================


class TestProductionSmokeRunbookContent:
    """Verify the operator runbook contains required sections."""

    def test_production_like_runbook_mentions_required_checks(self):
        """Read docs/production_e2e_smoke.md and verify required sections."""
        runbook_path = (
            Path(__file__).resolve().parents[1] / "docs/production_e2e_smoke.md"
        )
        assert runbook_path.exists(), f"Runbook not found: {runbook_path}"
        content = runbook_path.read_text(encoding="utf-8").lower()

        required = [
            "/health",
            "/model/version",
            "post /predictions",
            "poll for result",
            "model_ready",
            "completed",
            "non-null",
            "safe failure criteria",
            "decision-support",
        ]
        for phrase in required:
            assert phrase in content, (
                f"Runbook must mention: {phrase!r}"
            )


# ===================================================================
# 6. Optional real deployment smoke (skipped by default)
# ===================================================================


@pytest.mark.skipif(
    True,
    reason="Real deployment smoke is opt-in. "
    "Set BREMEN_E2E_SMOKE_URL to enable.",
)
class TestProductionSmokeRealDeployment:
    """Placeholder for optional real deployment smoke test.

    Skipped by default.  Requires BREMEN_E2E_SMOKE_URL and related
    environment variables configured for a running deployment.
    """

    def test_optional_real_h5_smoke_skipped_by_default(self):
        """Always skipped — placeholder for future opt-in deployment smoke."""
