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


def _valid_mock_mw_result() -> dict:
    """Return a valid MultiWorkflowResult mock for orchestrator tests."""
    from bremen.api.workflow_provider import MultiWorkflowResult, WorkflowResult
    return MultiWorkflowResult(
        request_id="mock-req",
        job_id="mock-job",
        normalization_status="completed",
        source_checksum="a" * 64,
        requested_workflows=("bremen",),
        workflows={
            "bremen": WorkflowResult(
                workflow_id="bremen",
                status="completed",
                payload={
                    "prediction_id": "mock-pred-001",
                    "model_version": "test-v0.1",
                    "model_checksum": "a" * 64,
                    "feature_schema_version": "v0.1",
                    "threshold_applied": 0.5,
                    "probability": 0.75,
                    "triage_recommendation": "CONTINUE_MRI",
                },
            ),
        },
        overall_status="completed",
    )


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


class TestPredictionCallsOrchestrator:
    """Verify run_inference is called with the correct h5_path argument."""

    def test_prediction_execution_calls_orchestrator_with_h5_path(
        self, tmp_path: Path, monkeypatch,
    ):
        """Monkeypatch run_workflow_request and verify it's called with h5_path."""
        _load_synthetic_model(tmp_path)

        call_args = []

        def mock_run_workflow_request(
            h5_path, workflow_id="bremen", *, target_scan_ref=None,
            control_scan_ref=None, registry=None,
        ):
            call_args.append((h5_path, workflow_id, target_scan_ref, control_scan_ref))
            return _valid_mock_mw_result()

        monkeypatch.setattr(
            "bremen.api.workflow_orchestrator.run_workflow_request",
            mock_run_workflow_request,
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
            f"run_workflow_request was called {len(call_args)} times, expected 1"
        )

        actual_h5_path, actual_wf_id, actual_target_ref, actual_control_ref = call_args[0]
        assert actual_h5_path == "/tmp/test-input.h5", (
            f"run_workflow_request received '{actual_h5_path}', "
            f"expected '/tmp/test-input.h5'"
        )
        assert actual_h5_path != "target", (
            "run_workflow_request must not receive 'target' as the H5 path"
        )
        assert actual_wf_id == "bremen"
        assert actual_target_ref == "target"
        assert actual_control_ref == "control"

        # Verify the job completed with result

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

    def test_prediction_job_completes_with_result_when_orchestrator_succeeds(
        self, tmp_path: Path, monkeypatch,
    ):
        """Monkeypatch run_workflow_request to return a valid result."""
        _load_synthetic_model(tmp_path)

        def mock_run_workflow_request(
            h5_path, workflow_id="bremen", *, target_scan_ref=None,
            control_scan_ref=None, registry=None,
        ):
            return _valid_mock_mw_result()

        monkeypatch.setattr(
            "bremen.api.workflow_orchestrator.run_workflow_request",
            mock_run_workflow_request,
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

    def test_prediction_job_fails_on_missing_h5_input(
        self, tmp_path: Path,
    ):
        """Submit prediction without h5_path or h5_uri raises ValueError."""
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

        error_lower = str(exc_info.value).lower()
        assert "must be provided" in error_lower or "either" in error_lower, (
            f"Error must mention missing input, got: {exc_info.value}"
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

        error_lower = str(exc_info.value).lower()
        assert "h5_path" in error_lower or "must be" in error_lower, (
            f"Error must mention input validation, got: {exc_info.value}"
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


# ---------------------------------------------------------------------------
# H. test_prediction_accepts_s3_h5_uri_and_stages_before_inference
# ---------------------------------------------------------------------------


class TestPredictionS3Uri:
    """Tests for S3 H5 URI input mode."""

    def test_prediction_accepts_s3_h5_uri_and_stages_before_orchestrator(
        self, tmp_path: Path, monkeypatch,
    ):
        """Submit with h5_uri: stage_h5_input returns local path,
        orchestrator is called with staged local path, not S3 URI."""
        _load_synthetic_model(tmp_path)

        expected_staged_path = "/tmp/staged-input.h5"
        call_args = []

        def mock_stage_h5_input(h5_uri, staging_dir="/tmp/bremen-inputs",
                                 expected_checksum=None, s3_client=None):
            return Path(expected_staged_path)

        def mock_run_workflow_request(
            h5_path, workflow_id="bremen", *, target_scan_ref=None,
            control_scan_ref=None, registry=None,
        ):
            call_args.append((h5_path, workflow_id, target_scan_ref, control_scan_ref))
            return _valid_mock_mw_result()

        monkeypatch.setattr(
            "bremen.h5_inputs.stage_h5_input", mock_stage_h5_input
        )
        monkeypatch.setattr(
            "bremen.api.workflow_orchestrator.run_workflow_request",
            mock_run_workflow_request,
        )

        store = InMemoryJobStore()

        response = handle_submit_prediction(
            {
                "h5_uri": "s3://bucket/test.h5",
                "h5_checksum": "sha256:" + "a" * 64,
                "target_scan_ref": "target",
                "control_scan_ref": "control",
            },
            store,
        )

        # Verify orchestrator was called
        assert len(call_args) == 1, (
            f"run_workflow_request was called {len(call_args)} times, expected 1"
        )

        actual_h5_path, actual_wf_id, actual_target_ref, actual_control_ref = call_args[0]
        assert actual_h5_path == expected_staged_path, (
            f"run_workflow_request received '{actual_h5_path}', "
            f"expected staged path '{expected_staged_path}'"
        )
        assert actual_h5_path != "s3://bucket/test.h5", (
            "run_workflow_request must not receive S3 URI directly"
        )
        assert actual_wf_id == "bremen"
        assert actual_target_ref == "target"
        assert actual_control_ref == "control"

        # Verify the job completed

        # Verify the job completed with result
        status = handle_get_prediction(response.job_id, store)
        assert status.status == STATUS_COMPLETED
        assert status.result is not None

        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# I. test_prediction_rejects_both_h5_path_and_h5_uri
# ---------------------------------------------------------------------------


class TestPredictionBothInputs:
    """Both h5_path and h5_uri must be rejected before job creation."""

    def test_prediction_rejects_both_h5_path_and_h5_uri(
        self, tmp_path: Path,
    ):
        """Both h5_path and h5_uri raises ValueError. No job created."""
        _load_synthetic_model(tmp_path)
        store = InMemoryJobStore()

        assert store.job_count == 0

        with pytest.raises(ValueError, match="not both"):
            handle_submit_prediction(
                {
                    "h5_path": "/tmp/a.h5",
                    "h5_uri": "s3://bucket/b.h5",
                    "target_scan_ref": "target",
                    "control_scan_ref": "control",
                },
                store,
            )

        # No job should have been created
        assert store.job_count == 0, (
            f"Expected 0 jobs, got {store.job_count}"
        )
        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# J. test_prediction_rejects_missing_h5_input_before_job_creation
# ---------------------------------------------------------------------------


class TestPredictionMissingInputBeforeCreation:
    """Validation errors must not create jobs."""

    def test_prediction_rejects_missing_h5_input_before_job_creation(
        self, tmp_path: Path,
    ):
        """No h5_path or h5_uri raises ValueError. No job created."""
        _load_synthetic_model(tmp_path)
        store = InMemoryJobStore()

        assert store.job_count == 0

        with pytest.raises(ValueError, match="must be provided"):
            handle_submit_prediction(
                {
                    "target_scan_ref": "target",
                    "control_scan_ref": "control",
                },
                store,
            )

        assert store.job_count == 0, (
            f"Expected 0 jobs, got {store.job_count}"
        )
        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# K. test_prediction_rejects_non_s3_h5_uri
# ---------------------------------------------------------------------------


class TestPredictionNonS3Uri:
    """Non-S3 h5_uri must be rejected."""

    def test_prediction_rejects_non_s3_h5_uri(
        self, tmp_path: Path,
    ):
        """h5_uri that doesn't start with s3:// raises ValueError."""
        _load_synthetic_model(tmp_path)
        store = InMemoryJobStore()

        assert store.job_count == 0

        with pytest.raises(ValueError, match="must start with 's3://'"):
            handle_submit_prediction(
                {
                    "h5_uri": "https://example.com/file.h5",
                    "target_scan_ref": "target",
                    "control_scan_ref": "control",
                },
                store,
            )

        assert store.job_count == 0, (
            f"Expected 0 jobs, got {store.job_count}"
        )
        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# L. Optional real S3 smoke test (skipped by default)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    "BREMEN_SMOKE_H5_URI" not in os.environ
    or "BREMEN_SMOKE_H5_SHA" not in os.environ,
    reason="Set BREMEN_SMOKE_H5_URI and BREMEN_SMOKE_H5_SHA to run real S3 smoke",
)
class TestPredictionRealS3Smoke:
    """Optional real S3 smoke test.

    Skipped by default.  Requires both env vars.
    """

    def test_prediction_with_real_s3_h5_opt_in(self, tmp_path: Path):
        """Submit with real S3 URI and checksum, poll for completed."""
        _load_synthetic_model(tmp_path)
        store = InMemoryJobStore()
        s3_uri = os.environ["BREMEN_SMOKE_H5_URI"]
        s3_sha = os.environ["BREMEN_SMOKE_H5_SHA"]

        response = handle_submit_prediction(
            {
                "h5_uri": s3_uri,
                "h5_checksum": s3_sha,
                "target_scan_ref": "target",
                "control_scan_ref": "control",
                "patient_id": "smoke_test",
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
