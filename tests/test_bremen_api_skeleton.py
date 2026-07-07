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
# Submit prediction (async)
# ---------------------------------------------------------------------------


class TestSubmitPrediction:

    @staticmethod
    def _mock_run_inference(h5_path, patient_id=None):
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
                {"control_scan_ref": "scan:ctl/001"}, store
            )

    def test_submit_requires_control_scan_ref(self):
        """submit_prediction fails if control_scan_ref is missing."""
        _load_synthetic_model(Path("/tmp"))
        store = InMemoryJobStore()
        with pytest.raises(ValueError, match="control_scan_ref"):
            handle_submit_prediction(
                {"target_scan_ref": "scan:tgt/001"}, store
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
    def _mock_run_inference(h5_path, patient_id=None):
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
        """Valid request passes validation."""
        request = validate_prediction_request({
            "target_scan_ref": "scan:tgt/001",
            "control_scan_ref": "scan:ctl/001",
        })
        assert isinstance(request, PredictionRequest)
        assert request.target_scan_ref == "scan:tgt/001"
        assert request.control_scan_ref == "scan:ctl/001"

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
                "preflight.py",
                "preprocessing_bridge.py",
                "inference_handler.py",
                "model_state.py",
            ):
                continue  # H5 preflight gate (PR 0037)
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
