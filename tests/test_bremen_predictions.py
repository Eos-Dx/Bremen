"""Prediction job execution tests (PR 0042).

Verifies the fix for the silent completed/null bug:
- ``handle_submit_prediction`` always attempts inference
- ``h5_path`` is passed to ``run_inference`` (not ``target_scan_ref``)
- No job is ever marked completed with ``result=None, error=None``
- Failed jobs always have non-empty error and null result
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from bremen.api.jobs import InMemoryJobStore
from bremen.api.schemas import (
    CompletedResult,
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
# Fixtures
# ---------------------------------------------------------------------------


def _load_synthetic_model(tmp_path: Path | None = None) -> None:
    """Load a minimal synthetic model so prediction submit tests pass."""
    import hashlib
    import tempfile
    from joblib import dump
    from bremen.api.preprocessing_bridge import BREMEN_V01_FEATURE_COLUMNS

    if tmp_path is None:
        tmp_path = Path(tempfile.mkdtemp())

    ModelState.reset_for_tests()
    n_features = 15
    package = {
        "portable_logreg": {
            "feature_columns": list(BREMEN_V01_FEATURE_COLUMNS),
            "imputer_statistics": [0.0] * n_features,
            "scaler_mean": [0.0] * n_features,
            "scaler_scale": [1.0] * n_features,
            "coef": [0.1] * n_features,
            "intercept": 0.0,
            "threshold": 0.5,
        }
    }
    model_path = tmp_path / "synth_model.joblib"
    dump(package, model_path)
    checksum = hashlib.sha256(model_path.read_bytes()).hexdigest()
    ModelState.load_at_startup(
        model_uri=str(model_path),
        model_version="test-v0.1",
        model_checksum=checksum,
    )


def _valid_mock_result() -> dict:
    """Return a valid result dict matching what run_inference returns."""
    return {
        "prediction_id": "mock-pred-001",
        "model_version": "test-v0.1",
        "model_checksum": "a" * 64,
        "feature_schema_version": "v0.1",
        "threshold_version": "v0.1",
        "threshold_value": 0.5,
        "qc_status": "passed",
        "qc_flags": [],
        "patient_id": "mock-patient",
        "p_mri_needed": 0.75,
        "triage_recommendation": "MRI_RECOMMENDED",
        "created_at_utc": "2026-01-01T00:00:00",
    }


# ---------------------------------------------------------------------------
# A. test_prediction_job_fails_gracefully_on_missing_h5_path
# ---------------------------------------------------------------------------


class TestPredictionFailGracefully:
    """Submit with nonexistent H5 path → job fails with non-empty error."""

    def test_prediction_job_fails_gracefully_on_missing_h5_path(
        self, tmp_path: Path,
    ):
        """Submit a prediction with a nonexistent H5 path.

        The job should be accepted (202), then poll to ``failed`` with
        non-empty error and ``result=None``.
        """
        _load_synthetic_model(tmp_path)
        store = InMemoryJobStore()

        nonexistent = str(tmp_path / "nonexistent-smoke-test.h5")

        response = handle_submit_prediction(
            {
                "h5_path": nonexistent,
                "target_scan_ref": "target",
                "control_scan_ref": "control",
            },
            store,
        )
        assert isinstance(response, PredictionResponse)
        assert response.status == "accepted"

        # Job is synchronous — poll immediately
        status = handle_get_prediction(response.job_id, store)
        assert status.status == STATUS_FAILED, (
            f"Expected failed, got {status.status}"
        )
        assert status.error is not None, "error must be non-empty"
        assert len(status.error) > 0, "error must be non-empty"
        assert status.result is None, "result must be None for failed jobs"
        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# B. test_prediction_job_never_completes_with_null_result
# ---------------------------------------------------------------------------


class TestPredictionNeverCompletesNull:
    """Invariant: no job may be completed with result=None and error=None."""

    def test_prediction_job_never_completes_with_null_result(
        self, tmp_path: Path,
    ):
        """Submit a prediction that fails early. Verify the invariant."""
        _load_synthetic_model(tmp_path)
        store = InMemoryJobStore()

        nonexistent = str(tmp_path / "nonexistent-test.h5")

        response = handle_submit_prediction(
            {
                "h5_path": nonexistent,
                "target_scan_ref": "target",
                "control_scan_ref": "control",
            },
            store,
        )

        status = handle_get_prediction(response.job_id, store)

        # Invariant: never completed with result=None and error=None
        assert not (
            status.status == STATUS_COMPLETED
            and status.result is None
            and status.error is None
        ), "Job must NEVER be completed with result=None and error=None"

        # For failed jobs: error must be non-empty, result must be None
        if status.status == STATUS_FAILED:
            assert status.error is not None and len(status.error) > 0, (
                "Failed job must have non-empty error"
            )
            assert status.result is None, "Failed job must have result=None"

        # For completed jobs: result must be non-None
        if status.status == STATUS_COMPLETED:
            assert status.result is not None, (
                "Completed job must have non-None result"
            )
            assert status.error is None, "Completed job must have error=None"

        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# C. test_prediction_execution_calls_run_inference_with_h5_path
# ---------------------------------------------------------------------------


class TestPredictionCallsRunInference:
    """Verify run_inference is called with the correct h5_path argument."""

    def test_prediction_execution_calls_run_inference_with_h5_path(
        self, tmp_path: Path, monkeypatch,
    ):
        """Monkeypatch run_inference and verify it's called with h5_path."""
        _load_synthetic_model(tmp_path)

        call_args = []

        def mock_run_inference(h5_path, patient_id=None):
            call_args.append((h5_path, patient_id))
            return _valid_mock_result()

        monkeypatch.setattr(
            "bremen.api.inference_handler.run_inference", mock_run_inference
        )

        store = InMemoryJobStore()

        response = handle_submit_prediction(
            {
                "h5_path": "/tmp/test-input.h5",
                "target_scan_ref": "target",
                "control_scan_ref": "control",
            },
            store,
        )

        assert len(call_args) == 1, (
            f"run_inference was called {len(call_args)} times, expected 1"
        )

        actual_h5_path, actual_patient_id = call_args[0]
        assert actual_h5_path == "/tmp/test-input.h5", (
            f"run_inference received '{actual_h5_path}', "
            f"expected '/tmp/test-input.h5'"
        )
        assert actual_h5_path != "target", (
            "run_inference must not receive 'target' as the H5 path"
        )
        assert actual_patient_id is None  # not provided in request

        # Verify the job completed with result
        status = handle_get_prediction(response.job_id, store)
        assert status.status == STATUS_COMPLETED
        assert status.result is not None

        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# D. test_prediction_job_completes_with_result_when_run_inference_succeeds
# ---------------------------------------------------------------------------


class TestPredictionCompletesWithResult:
    """When run_inference succeeds, job should complete with result."""

    def test_prediction_job_completes_with_result_when_run_inference_succeeds(
        self, tmp_path: Path, monkeypatch,
    ):
        """Monkeypatch run_inference to return a valid result."""
        _load_synthetic_model(tmp_path)

        def mock_run_inference(h5_path, patient_id=None):
            return _valid_mock_result()

        monkeypatch.setattr(
            "bremen.api.inference_handler.run_inference", mock_run_inference
        )

        store = InMemoryJobStore()

        response = handle_submit_prediction(
            {
                "h5_path": "/tmp/test-input.h5",
                "target_scan_ref": "target",
                "control_scan_ref": "control",
            },
            store,
        )

        status = handle_get_prediction(response.job_id, store)
        assert status.status == STATUS_COMPLETED, (
            f"Expected completed, got {status.status}"
        )
        assert status.result is not None, "result must be non-None"
        assert status.error is None, "error must be None for completed jobs"

        # Verify mandatory fields in result
        mandatory_fields = [
            "prediction_id",
            "model_version",
            "model_checksum",
            "feature_schema_version",
            "threshold_version",
            "threshold_value",
            "qc_status",
            "qc_flags",
        ]
        for field in mandatory_fields:
            assert field in status.result, (
                f"Missing mandatory result field: {field}"
            )

        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# E. test_prediction_job_fails_on_missing_h5_path_field
# ---------------------------------------------------------------------------


class TestPredictionMissingH5Path:
    """Submit without h5_path should raise ValueError."""

    def test_prediction_job_fails_on_missing_h5_path_field(
        self, tmp_path: Path,
    ):
        """Submit prediction without h5_path raises ValueError."""
        _load_synthetic_model(tmp_path)
        store = InMemoryJobStore()

        with pytest.raises(ValueError) as exc_info:
            handle_submit_prediction(
                {
                    "target_scan_ref": "target",
                    "control_scan_ref": "control",
                },
                store,
            )

        assert "h5_path" in str(exc_info.value).lower(), (
            f"Error must mention 'h5_path', got: {exc_info.value}"
        )
        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# F. test_prediction_job_fails_on_empty_h5_path
# ---------------------------------------------------------------------------


class TestPredictionEmptyH5Path:
    """Submit with empty h5_path should raise ValueError."""

    def test_prediction_job_fails_on_empty_h5_path(self, tmp_path: Path):
        """Submit prediction with empty h5_path raises ValueError."""
        _load_synthetic_model(tmp_path)
        store = InMemoryJobStore()

        with pytest.raises(ValueError) as exc_info:
            handle_submit_prediction(
                {
                    "h5_path": "",
                    "target_scan_ref": "target",
                    "control_scan_ref": "control",
                },
                store,
            )

        assert "h5_path" in str(exc_info.value).lower(), (
            f"Error must mention 'h5_path', got: {exc_info.value}"
        )
        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# G. Optional real H5 test (skipped by default)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    "BREMEN_REAL_H5_PATH" not in os.environ,
    reason="Set BREMEN_REAL_H5_PATH to run real H5 smoke test",
)
class TestPredictionRealH5:
    """Optional smoke test with a real H5 file.

    Skipped by default.  Set BREMEN_REAL_H5_PATH to a compatible H5
    path to enable.
    """

    def test_prediction_job_with_real_h5_opt_in(self, tmp_path: Path):
        """Submit with real H5 path, expect completed only if compatible."""
        _load_synthetic_model(tmp_path)
        store = InMemoryJobStore()
        real_h5_path = os.environ["BREMEN_REAL_H5_PATH"]

        response = handle_submit_prediction(
            {
                "h5_path": real_h5_path,
                "target_scan_ref": "target",
                "control_scan_ref": "control",
            },
            store,
        )

        status = handle_get_prediction(response.job_id, store)

        # Must not violate the invariant
        assert not (
            status.status == STATUS_COMPLETED
            and status.result is None
            and status.error is None
        ), "Job must NEVER be completed with result=None and error=None"

        ModelState.reset_for_tests()
