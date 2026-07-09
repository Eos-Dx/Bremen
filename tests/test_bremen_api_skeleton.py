"""Tests for the API microservice skeleton (``src/bremen/api/``).

Covers:
- handle_health returns service health shape
- handle_model_version returns safe not_configured response
- handle_submit_prediction returns job_id and accepted status
- submit_prediction requires explicit target_scan_ref
- submit_prediction requires explicit control_scan_ref
- handle_get_prediction returns status for known job_id
- handle_get_prediction returns not_found for unknown job_id
- InMemoryJobStore.create_job creates distinct job_ids
- InMemoryJobStore.get_job returns None for unknown IDs
- CompletedResult includes all mandatory fields
- No joblib/pickle imports
- No H5/HDF5 references
- No AWS/S3/network calls
- No training/inference calls
- Import safety
"""

from __future__ import annotations

import sys
import ast
import re
from pathlib import Path

import pytest

from bremen.api import (
    app,
    jobs,
    schemas,
)
from bremen.api.schemas import (
    COMPLETED_RESULT_FIELDS,
    ALL_STATUSES,
    CompletedResult,
    HealthResponse,
    ModelVersionResponse,
    PredictionRequest,
    PredictionResponse,
    PredictionStatusResponse,
    build_health_response,
    build_not_configured_model_response,
    build_accepted_response,
    build_not_found_response,
    validate_prediction_request,
    validate_status,
)
from bremen.api.jobs import (
    InMemoryJobStore,
    JobRecord,
)
from bremen.api.app import (
    handle_health,
    handle_model_version,
    handle_submit_prediction,
    handle_get_prediction,
)
from bremen.api.model_state import ModelState

API_SRC = Path(__file__).parents[1] / "src" / "bremen" / "api"
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


# ---------------------------------------------------------------------------
# Synthetic model loader for submit/get prediction tests
# ---------------------------------------------------------------------------


def _load_synthetic_model(tmp_path: Path | None = None) -> None:
    """Load a minimal synthetic model so prediction submit tests pass."""
    import hashlib, tempfile
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


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_response(self):
        """handle_health returns a HealthResponse with model_ready."""
        ModelState.reset_for_tests()
        response = handle_health()
        assert isinstance(response, HealthResponse)
        assert response.status == "ok"
        assert response.service == "bremen"
        assert response.model_ready is False

    def test_health_has_timestamp(self):
        """HealthResponse contains a timestamp."""
        ModelState.reset_for_tests()
        response = handle_health()
        assert response.timestamp is not None
        assert "T" in response.timestamp  # ISO-8601 format

    def test_health_accepts_version(self):
        """handle_health accepts an optional version parameter."""
        ModelState.reset_for_tests()
        response = handle_health(version="1.0.0")
        assert response.version == "1.0.0"


# ---------------------------------------------------------------------------
# Model version
# ---------------------------------------------------------------------------


class TestModelVersion:
    def test_model_version_returns_safe_not_configured(self):
        """handle_model_version returns not_configured by default with no env."""
        from bremen.config import read_cloud_config

        cloud = read_cloud_config(env={})
        response = handle_model_version(cloud=cloud)
        assert isinstance(response, ModelVersionResponse)
        assert response.model_configured is False
        assert response.model_status == "not_configured"
        assert response.model_version is None

    def test_model_version_configured_with_cloud_env(self):
        """handle_model_version with configured cloud returns configured."""
        from bremen.config import read_cloud_config

        cloud = read_cloud_config(
            env={"BREMEN_MODEL_BUCKET": "my-bucket"}
        )
        response = handle_model_version(cloud=cloud)
        assert response.model_configured is True
        assert response.model_status == "configured"
        assert response.model_version is None

    def test_model_version_does_not_load_model(self):
        """handle_model_version does not call model_package validation."""
        from bremen.config import read_cloud_config

        # Even when configured, no model loading happens
        cloud = read_cloud_config(
            env={"BREMEN_MODEL_BUCKET": "my-bucket"}
        )
        response = handle_model_version(cloud=cloud)
        assert response.model_status == "configured"
        # All content fields are None (no model fetched)
        assert response.model_checksum is None
        assert response.feature_schema_version is None


# ---------------------------------------------------------------------------
# Model version readiness (PR 0050)
# ---------------------------------------------------------------------------


class TestModelVersionReadiness:
    """Tests for PR 0050 model/version readiness cleanup.

    Covers all four status values: not_configured, configured, ready, error.
    """

    def test_model_version_ready_after_load(self, tmp_path):
        """After successful model load, model_status is ready."""
        import hashlib
        from joblib import dump
        from bremen.api.preprocessing_bridge import BREMEN_V01_FEATURE_COLUMNS

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
        model_path = tmp_path / "ready_model.joblib"
        dump(package, model_path)
        checksum = hashlib.sha256(model_path.read_bytes()).hexdigest()
        result = ModelState.load_at_startup(
            model_uri=str(model_path),
            model_version="ready-v0.1",
            model_checksum=checksum,
        )
        assert result is True

        response = handle_model_version()
        assert response.model_status == "ready"
        assert response.model_configured is True
        assert response.error_category is None
        assert response.model_uri_configured is True
        assert response.checksum_configured is True
        assert response.model_version is not None
        assert response.model_checksum is not None
        assert response.threshold_value is not None

        ModelState.reset_for_tests()

    def test_model_version_error_after_failed_load(self, tmp_path):
        """After failed model load, model_status is error with safe category."""
        import hashlib

        ModelState.reset_for_tests()

        # Create a corrupt file and use a mismatched checksum
        bad_file = tmp_path / "bad_model.joblib"
        bad_file.write_bytes(b"not a valid model package")
        model_checksum = hashlib.sha256(b"different content").hexdigest()

        result = ModelState.load_at_startup(
            model_uri=str(bad_file),
            model_version="bad-v0.1",
            model_checksum=model_checksum,
        )
        assert result is False

        response = handle_model_version()
        assert response.model_status == "error"
        assert response.model_configured is True
        assert response.error_category is not None
        assert isinstance(response.error_category, str)
        assert len(response.error_category) > 0
        assert response.model_uri_configured is True
        # error_category must be a safe enum string, not raw exception
        assert response.error_category in (
            "s3_staging_failure", "local_file_not_found",
            "checksum_mismatch", "joblib_load_failure",
            "package_validation_failure",
        )
        # Verify health agrees
        health = handle_health()
        assert health.model_ready is False

        ModelState.reset_for_tests()

    def test_model_version_configured_not_loaded(self):
        """Configured but not loaded returns configured and not ready."""
        from bremen.config import read_cloud_config

        ModelState.reset_for_tests()
        cloud = read_cloud_config(
            env={"BREMEN_MODEL_BUCKET": "my-bucket"}
        )
        response = handle_model_version(cloud=cloud)
        assert response.model_status == "configured"
        assert response.model_configured is True
        assert response.error_category is None
        assert response.model_uri_configured is True
        assert response.checksum_configured is False

        health = handle_health()
        assert health.model_ready is False

    def test_model_version_not_configured(self):
        """No env vars set returns not_configured."""
        from bremen.config import read_cloud_config

        ModelState.reset_for_tests()
        cloud = read_cloud_config(env={})
        response = handle_model_version(cloud=cloud)
        assert response.model_status == "not_configured"
        assert response.model_configured is False
        assert response.error_category is None
        assert response.model_uri_configured is False
        assert response.checksum_configured is False

    def test_health_model_ready_consistency(self, tmp_path):
        """Health model_ready and version model_status are consistent.

        After load: health model_ready=True, version status=ready.
        After failed load: health model_ready=False, version status=error.
        Not configured: health model_ready=False, version status=not_configured.
        """
        import hashlib
        from joblib import dump
        from bremen.api.preprocessing_bridge import BREMEN_V01_FEATURE_COLUMNS

        ModelState.reset_for_tests()

        # Not configured consistency
        from bremen.config import read_cloud_config
        cloud = read_cloud_config(env={})
        version_resp = handle_model_version(cloud=cloud)
        health_resp = handle_health()
        assert health_resp.model_ready is False
        assert version_resp.model_status == "not_configured"
        # model_ready is True iff model_status == "ready"
        assert health_resp.model_ready == (version_resp.model_status == "ready")

        # Ready consistency
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
        model_path = tmp_path / "consistency_ready.joblib"
        dump(package, model_path)
        checksum = hashlib.sha256(model_path.read_bytes()).hexdigest()
        ModelState.load_at_startup(
            model_uri=str(model_path),
            model_version="consistency-v0.1",
            model_checksum=checksum,
        )
        version_resp = handle_model_version()
        health_resp = handle_health()
        assert health_resp.model_ready is True
        assert version_resp.model_status == "ready"
        assert health_resp.model_ready == (version_resp.model_status == "ready")

        ModelState.reset_for_tests()

        # Error consistency (checksum mismatch)
        bad_file = tmp_path / "consistency_bad.joblib"
        bad_file.write_bytes(b"not a model")
        wrong_checksum = hashlib.sha256(b"different content").hexdigest()
        ModelState.load_at_startup(
            model_uri=str(bad_file),
            model_version="bad-v0.1",
            model_checksum=wrong_checksum,
        )
        version_resp = handle_model_version()
        health_resp = handle_health()
        assert health_resp.model_ready is False
        assert version_resp.model_status == "error"
        assert health_resp.model_ready == (version_resp.model_status == "ready")

        ModelState.reset_for_tests()

    def test_no_raw_uri_or_checksum_leakage_in_model_version(self):
        """model_uri_configured and checksum_configured are bools, not strings.
        error_category is a safe enum string, not raw exception.
        """
        from bremen.config import read_cloud_config

        ModelState.reset_for_tests()

        # not_configured — all safe
        cloud = read_cloud_config(env={})
        response = handle_model_version(cloud=cloud)
        assert isinstance(response.model_uri_configured, bool)
        assert isinstance(response.checksum_configured, bool)
        assert response.error_category is None or isinstance(response.error_category, str)

        # After error state — safe
        import hashlib
        bad_file = Path("/tmp") / "leak_check_bad.joblib"
        bad_file.write_bytes(b"not a model")
        wrong_checksum = hashlib.sha256(b"different").hexdigest()
        ModelState.load_at_startup(
            model_uri=str(bad_file),
            model_version="leak-v0.1",
            model_checksum=wrong_checksum,
        )
        response = handle_model_version()
        assert isinstance(response.model_uri_configured, bool)
        assert isinstance(response.checksum_configured, bool)
        assert response.error_category is None or isinstance(response.error_category, str)
        # error_category must not contain raw S3 URI pattern
        if response.error_category:
            assert "s3://" not in response.error_category
            assert "sha256:" not in response.error_category

        ModelState.reset_for_tests()
        import os
        try:
            os.remove(str(bad_file))
        except OSError:
            pass

    def test_prediction_rejected_on_error_state(self, tmp_path, monkeypatch):
        """After failed model load, prediction submit raises ModelNotReadyError."""
        import hashlib

        ModelState.reset_for_tests()

        # Failed checksum → error state
        bad_file = tmp_path / "pred_reject_bad.joblib"
        bad_file.write_bytes(b"not a model")
        wrong_checksum = hashlib.sha256(b"different").hexdigest()
        ModelState.load_at_startup(
            model_uri=str(bad_file),
            model_version="bad-v0.1",
            model_checksum=wrong_checksum,
        )

        store = InMemoryJobStore()
        with pytest.raises(app.ModelNotReadyError):
            handle_submit_prediction(
                {
                    "h5_path": "/tmp/test.h5",
                    "target_scan_ref": "target",
                    "control_scan_ref": "control",
                },
                store,
            )

        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# Submit prediction (async)
# ---------------------------------------------------------------------------


class TestSubmitPrediction:

    @staticmethod
    def _mock_run_inference(
        h5_path, patient_id=None, target_scan_ref=None, control_scan_ref=None,
        input_mode=None,
    ):
        """Fake run_inference that returns a valid result dict."""
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

    def test_submit_returns_accepted_with_job_id(self, monkeypatch):
        """handle_submit_prediction returns accepted response with UUID job_id."""
        monkeypatch.setattr(
            "bremen.api.inference_handler.run_inference",
            self._mock_run_inference,
        )
        _load_synthetic_model(Path("/tmp"))
        store = InMemoryJobStore()
        request = {
            "target_scan_ref": "scan:tgt/001",
            "control_scan_ref": "scan:ctl/001",
            "h5_path": "/tmp/test.h5",
        }
        response = handle_submit_prediction(request, store)
        assert isinstance(response, PredictionResponse)
        assert response.status == "accepted"
        assert UUID_PATTERN.match(response.job_id), (
            f"job_id is not a valid UUID: {response.job_id}"
        )

    def test_submit_requires_target_scan_ref(self):
        """submit_prediction fails if target_scan_ref is missing."""
        _load_synthetic_model(Path("/tmp"))
        store = InMemoryJobStore()
        with pytest.raises(ValueError, match="target_scan_ref"):
            handle_submit_prediction(
                {
                    "control_scan_ref": "scan:ctl/001",
                    "h5_path": "/tmp/test.h5",
                }, store
            )

    def test_submit_requires_control_scan_ref(self):
        """submit_prediction fails if control_scan_ref is missing."""
        _load_synthetic_model(Path("/tmp"))
        store = InMemoryJobStore()
        with pytest.raises(ValueError, match="control_scan_ref"):
            handle_submit_prediction(
                {
                    "target_scan_ref": "scan:tgt/001",
                    "h5_path": "/tmp/test.h5",
                }, store
            )

    def test_submit_stores_job(self, monkeypatch):
        """The submitted job is stored in the job store."""
        monkeypatch.setattr(
            "bremen.api.inference_handler.run_inference",
            self._mock_run_inference,
        )
        _load_synthetic_model(Path("/tmp"))
        store = InMemoryJobStore()
        request = {
            "target_scan_ref": "scan:tgt/001",
            "control_scan_ref": "scan:ctl/001",
            "h5_path": "/tmp/test.h5",
        }
        response = handle_submit_prediction(request, store)
        job = store.get_job(response.job_id)
        assert job is not None
        assert job.status in ("accepted", "completed"), f"Expected accepted or completed, got {job.status}"

    def test_submit_has_poll_link(self, monkeypatch):
        """The accepted response includes a poll link."""
        monkeypatch.setattr(
            "bremen.api.inference_handler.run_inference",
            self._mock_run_inference,
        )
        _load_synthetic_model(Path("/tmp"))
        store = InMemoryJobStore()
        request = {
            "target_scan_ref": "scan:tgt/001",
            "control_scan_ref": "scan:ctl/001",
            "h5_path": "/tmp/test.h5",
        }
        response = handle_submit_prediction(request, store)
        assert response.links is not None
        assert "poll" in response.links
        assert response.job_id in response.links["poll"]


# ---------------------------------------------------------------------------
# Get prediction (poll)
# ---------------------------------------------------------------------------


class TestGetPrediction:

    @staticmethod
    def _mock_run_inference(
        h5_path, patient_id=None, target_scan_ref=None, control_scan_ref=None,
        input_mode=None,
    ):
        """Fake run_inference that returns a valid result dict."""
        return {
            "prediction_id": "mock-pred-002",
            "model_version": "test-v0.1",
            "model_checksum": "b" * 64,
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

    def test_get_known_job_returns_status(self, monkeypatch):
        """get_prediction for a known job_id returns the job status."""
        monkeypatch.setattr(
            "bremen.api.inference_handler.run_inference",
            self._mock_run_inference,
        )
        _load_synthetic_model(Path("/tmp"))
        store = InMemoryJobStore()
        request = {
            "target_scan_ref": "scan:tgt/001",
            "control_scan_ref": "scan:ctl/001",
            "h5_path": "/tmp/test.h5",
        }
        submit_response = handle_submit_prediction(request, store)
        status_response = handle_get_prediction(submit_response.job_id, store)
        assert isinstance(status_response, PredictionStatusResponse)
        assert status_response.status in ("accepted", "completed"), f"Expected accepted or completed, got {status_response.status}"

    def test_get_unknown_job_returns_not_found(self):
        """get_prediction for an unknown job_id returns not_found."""
        store = InMemoryJobStore()
        response = handle_get_prediction("00000000-0000-0000-0000-000000000000", store)
        assert response.status == "not_found"

    def test_get_returns_request_metadata(self, monkeypatch):
        """get_prediction preserves the original request metadata."""
        monkeypatch.setattr(
            "bremen.api.inference_handler.run_inference",
            self._mock_run_inference,
        )
        _load_synthetic_model(Path("/tmp"))
        store = InMemoryJobStore()
        raw_request = {
            "target_scan_ref": "scan:tgt/002",
            "control_scan_ref": "scan:ctl/002",
            "request_id": "idem-123",
            "h5_path": "/tmp/test.h5",
        }
        submit_response = handle_submit_prediction(raw_request, store)
        job = store.get_job(submit_response.job_id)
        assert job is not None
        assert job.request is not None
        assert job.request.target_scan_ref == "scan:tgt/002"
        assert job.request.control_scan_ref == "scan:ctl/002"
        assert job.request.request_id == "idem-123"


# ---------------------------------------------------------------------------
# InMemoryJobStore
# ---------------------------------------------------------------------------


class TestInMemoryJobStore:
    def test_create_job_returns_distinct_ids(self):
        """create_job produces distinct UUIDs for separate calls."""
        store = InMemoryJobStore()
        job1 = store.create_job()
        job2 = store.create_job()
        assert job1.job_id != job2.job_id
        assert UUID_PATTERN.match(job1.job_id)
        assert UUID_PATTERN.match(job2.job_id)

    def test_get_job_returns_none_for_unknown(self):
        """get_job returns None for an unknown job ID."""
        store = InMemoryJobStore()
        assert store.get_job("nonexistent") is None

    def test_job_count(self):
        """job_count reflects the number of stored jobs."""
        store = InMemoryJobStore()
        assert store.job_count == 0
        store.create_job()
        assert store.job_count == 1
        store.create_job()
        assert store.job_count == 2

    def test_update_status(self):
        """update_status changes the job status and sets updated_at."""
        store = InMemoryJobStore()
        record = store.create_job()
        assert record.status == "accepted"
        assert record.updated_at is None
        store.update_status(record.job_id, "running")
        updated = store.get_job(record.job_id)
        assert updated is not None
        assert updated.status == "running"
        assert updated.updated_at is not None


# ---------------------------------------------------------------------------
# CompletedResult schema
# ---------------------------------------------------------------------------


class TestCompletedResultFields:
    def test_all_mandatory_fields_present(self):
        """COMPLETED_RESULT_FIELDS contains all 8 project_contract fields."""
        expected = {
            "prediction_id",
            "model_version",
            "model_checksum",
            "feature_schema_version",
            "threshold_version",
            "threshold_value",
            "qc_status",
            "qc_flags",
        }
        assert set(COMPLETED_RESULT_FIELDS) == expected

    def test_completed_result_dataclass(self):
        """CompletedResult dataclass includes all mandatory fields."""
        result = CompletedResult(
            prediction_id="pid-001",
            model_version="1.0.0",
            model_checksum="a" * 64,
            feature_schema_version="1.0",
            threshold_version="v1",
            threshold_value=0.5,
            qc_status="passed",
            qc_flags=["flag1"],
        )
        assert result.prediction_id == "pid-001"
        assert result.qc_status == "passed"


# ---------------------------------------------------------------------------
# PredictionRequest validation
# ---------------------------------------------------------------------------


class TestPredictionRequestValidation:
    def test_valid_request(self):
        """Valid request with h5_path passes validation."""
        request = validate_prediction_request({
            "target_scan_ref": "scan:tgt/001",
            "control_scan_ref": "scan:ctl/001",
            "h5_path": "/tmp/test.h5",
        })
        assert isinstance(request, PredictionRequest)
        assert request.target_scan_ref == "scan:tgt/001"
        assert request.control_scan_ref == "scan:ctl/001"
        assert request.h5_path == "/tmp/test.h5"

    def test_missing_target_scan_ref(self):
        """Missing target_scan_ref raises ValueError."""
        with pytest.raises(ValueError, match="target_scan_ref"):
            validate_prediction_request({
                "control_scan_ref": "scan:ctl/001",
            })

    def test_empty_target_scan_ref(self):
        """Empty target_scan_ref raises ValueError."""
        with pytest.raises(ValueError, match="target_scan_ref"):
            validate_prediction_request({
                "target_scan_ref": "",
                "control_scan_ref": "scan:ctl/001",
            })

    def test_valid_with_h5_path(self):
        """Valid request with h5_path passes validation."""
        request = validate_prediction_request({
            "target_scan_ref": "scan:tgt/001",
            "control_scan_ref": "scan:ctl/001",
            "h5_path": "/tmp/input.h5",
        })
        assert isinstance(request, PredictionRequest)
        assert request.h5_path == "/tmp/input.h5"
        assert request.h5_uri is None
        assert request.h5_checksum is None

    def test_valid_with_h5_uri(self):
        """Valid request with h5_uri passes validation."""
        request = validate_prediction_request({
            "target_scan_ref": "scan:tgt/001",
            "control_scan_ref": "scan:ctl/001",
            "h5_uri": "s3://bucket/test.h5",
        })
        assert isinstance(request, PredictionRequest)
        assert request.h5_uri == "s3://bucket/test.h5"
        assert request.h5_path is None

    def test_valid_with_h5_uri_and_checksum(self):
        """Valid request with h5_uri and h5_checksum passes."""
        request = validate_prediction_request({
            "target_scan_ref": "scan:tgt/001",
            "control_scan_ref": "scan:ctl/001",
            "h5_uri": "s3://bucket/test.h5",
            "h5_checksum": "sha256:" + "a" * 64,
        })
        assert isinstance(request, PredictionRequest)
        assert request.h5_checksum == "sha256:" + "a" * 64

    def test_valid_with_h5_uri_and_uppercase_checksum(self):
        """Upper-case hex in checksum is accepted."""
        # Generate exactly 64 uppercase hex chars
        upper_hex = "A" * 60 + "B" * 4
        request = validate_prediction_request({
            "target_scan_ref": "scan:tgt/001",
            "control_scan_ref": "scan:ctl/001",
            "h5_uri": "s3://bucket/test.h5",
            "h5_checksum": "sha256:" + upper_hex.upper(),
        })
        assert request.h5_checksum == "sha256:" + upper_hex.upper()

    def test_rejects_both_h5_path_and_h5_uri(self):
        """Both h5_path and h5_uri raises ValueError."""
        with pytest.raises(ValueError, match="not both"):
            validate_prediction_request({
                "target_scan_ref": "scan:tgt/001",
                "control_scan_ref": "scan:ctl/001",
                "h5_path": "/tmp/a.h5",
                "h5_uri": "s3://bucket/b.h5",
            })

    def test_rejects_missing_h5_input(self):
        """Missing both h5_path and h5_uri raises ValueError."""
        with pytest.raises(ValueError, match="must be provided"):
            validate_prediction_request({
                "target_scan_ref": "scan:tgt/001",
                "control_scan_ref": "scan:ctl/001",
            })

    def test_rejects_non_s3_h5_uri(self):
        """Non-s3 URI raises ValueError."""
        with pytest.raises(ValueError, match="must start with 's3://'"):
            validate_prediction_request({
                "target_scan_ref": "scan:tgt/001",
                "control_scan_ref": "scan:ctl/001",
                "h5_uri": "https://example.com/file.h5",
            })

    def test_rejects_bad_checksum_pattern(self):
        """Malformed checksum raises ValueError."""
        with pytest.raises(ValueError, match="sha256:"):
            validate_prediction_request({
                "target_scan_ref": "scan:tgt/001",
                "control_scan_ref": "scan:ctl/001",
                "h5_uri": "s3://bucket/test.h5",
                "h5_checksum": "md5:abc",
            })


# ---------------------------------------------------------------------------
# Status validation
# ---------------------------------------------------------------------------


class TestStatusValidation:
    def test_valid_status(self):
        """Known statuses pass validation."""
        for status in ALL_STATUSES:
            assert validate_status(status) == status

    def test_invalid_status(self):
        """Unknown status raises ValueError."""
        with pytest.raises(ValueError, match="Unknown status"):
            validate_status("bogus_status")


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


class TestResponseBuilders:
    def test_build_health_response(self):
        """build_health_response returns expected shape."""
        response = build_health_response(version="test")
        assert response.status == "ok"
        assert response.service == "bremen"
        assert response.version == "test"

    def test_build_not_configured(self):
        """build_not_configured_model_response returns safe stub."""
        response = build_not_configured_model_response()
        assert response.model_configured is False
        assert response.model_status == "not_configured"

    def test_build_accepted_response(self):
        """build_accepted_response returns accepted shape with poll link."""
        response = build_accepted_response(
            job_id="job-001",
            submitted_at="2026-01-01T00:00:00",
        )
        assert response.status == "accepted"
        assert response.job_id == "job-001"
        assert response.links is not None
        assert "job-001" in response.links["poll"]

    def test_build_not_found_response(self):
        """build_not_found_response returns not_found status."""
        response = build_not_found_response("job-999")
        assert response.status == "not_found"
        assert response.job_id == "job-999"
        assert response.submitted_at is None


# ---------------------------------------------------------------------------
# Import safety (AST-based)
# ---------------------------------------------------------------------------


class TestImportSafety:
    def test_no_joblib_import(self):
        """No API source file imports joblib.

        Note: ``model_state.py`` and ``server.py`` intentionally
        import ``joblib`` — ``model_state.py`` for controlled startup
        model loading (PR 0039), ``server.py`` for synthetic model
        loading in dev/smoke mode.
        """
        for py_file in API_SRC.rglob("*.py"):
            if py_file.name in ("model_state.py", "server.py"):
                continue  # PR 0039: controlled startup model loading
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "joblib" in alias.name.lower():
                            pytest.fail(
                                f"{py_file} imports joblib"
                            )
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if "joblib" in module.lower():
                        pytest.fail(
                            f"{py_file} imports joblib via {module}"
                        )

    def test_no_pickle_import(self):
        """No API source file imports pickle."""
        for py_file in API_SRC.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "pickle" in alias.name.lower():
                            pytest.fail(
                                f"{py_file} imports pickle"
                            )
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if "pickle" in module.lower():
                        pytest.fail(
                            f"{py_file} imports pickle via {module}"
                        )

    def test_no_joblib_load_string(self):
        """No API source file contains 'joblib.load(' or 'pickle.load('.

        Note: ``model_state.py`` intentionally calls ``joblib.load()``
        for controlled startup model loading (PR 0039).
        """
        for py_file in API_SRC.rglob("*.py"):
            if py_file.name in ("model_state.py", "server.py"):
                continue  # PR 0039: controlled startup/loading
            content = py_file.read_text(encoding="utf-8")
            if "joblib.load(" in content:
                pytest.fail(f"{py_file} contains 'joblib.load('")
            if "pickle.load(" in content:
                pytest.fail(f"{py_file} contains 'pickle.load('")

    def test_no_h5_references(self):
        """No API source file references .h5, .hdf5, or h5py.

        Note: ``preflight.py``, ``preprocessing_bridge.py``, ``inference_handler.py``,
        and ``model_state.py`` are the H5/non-standard-library exceptions —
        they implement the H5 preflight gate (PR 0037), preprocessing bridge
        (PR 0038), and inference integration (PR 0039) respectively.
        """
        for py_file in API_SRC.rglob("*.py"):
            if py_file.name in (
                "app.py",
                "h5_layouts.py",
                "preflight.py",
                "preprocessing_bridge.py",
                "inference_handler.py",
                "model_state.py",
            ):
                continue  # H5-related modules (PR 0037, PR 0044, PR 0045)
            content = py_file.read_text(encoding="utf-8")
            for ref in [".h5", ".hdf5", "h5py"]:
                if ref in content:
                    pytest.fail(f"{py_file} contains H5 reference: {ref}")

    def test_no_boto3_or_requests(self):
        """No API source file imports boto3, requests, or httpx."""
        prohibited = {"boto3", "requests", "httpx", "urllib"}
        for py_file in API_SRC.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in prohibited:
                            pytest.fail(
                                f"{py_file} imports {alias.name}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    top = module.split(".")[0]
                    if top in prohibited:
                        pytest.fail(
                            f"{py_file} imports {module}"
                        )

    def test_import_succeeds(self):
        """Importing bremen.api does not cause ImportError."""
        import importlib

        if "bremen.api" in sys.modules:
            del sys.modules["bremen.api"]
        for key in list(sys.modules):
            if key.startswith("bremen.api"):
                del sys.modules[key]

        mod = importlib.import_module("bremen.api")
        assert mod is not None
