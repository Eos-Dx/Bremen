"""PR0134: checksum-bound local inference, safe failures, job/report integration.

Only synthetic estimator artifacts are serialized in temporary directories.
No real model weights, packages, external services or clinical claims.
"""
from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import h5py
import joblib
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from bremen.api import job_api_handler as jobs
from bremen.api import model_registry as registry
from bremen.api.aramina_provider import AraminaProviderRequest
from bremen.api.workflow_aramina import (
    ARTIFACT_TYPE,
    AraminaWorkflowError,
    AraminaWorkflowProvider,
    _build_aramina_request_json,
)
from bremen.api.workflow_orchestrator import _normalize_h5, get_provider_for_model


@pytest.fixture(autouse=True)
def reset_state():
    registry.reset_for_tests()
    jobs._event_store.reset_for_tests()
    jobs._jobs.clear()
    yield
    registry.reset_for_tests()
    jobs._event_store.reset_for_tests()
    jobs._jobs.clear()


def _package(model_id="aramina-a", model_version="test-v1", reverse=False):
    model = LogisticRegression(random_state=0).fit(
        np.array([[0., 0.], [1., 1.], [2., 2.], [3., 3.]]),
        [1, 1, 0, 0] if reverse else [0, 0, 1, 1],
    )
    return {
        "model_id": model_id, "model_version": model_version,
        "artifact_type": ARTIFACT_TYPE, "model": model, "positive_class": 1,
        "feature_schema_version": "v0.1",
        "feature_contract": {
            "schema_version": "aramina.canonical_intensity.v1",
            "position": "scan_0", "q_grid": [0., 1.], "normalization": "none",
        },
    }


def _entry(tmp_path, package=None, model_id="aramina-a"):
    package = package if package is not None else _package(model_id)
    path = tmp_path / f"{model_id}.joblib"
    joblib.dump(package, path)
    return registry.RegistryModelEntry(
        model_id=model_id, display_name="Synthetic model", workflow_id="aramina",
        model_version="test-v1", artifact_type=ARTIFACT_TYPE,
        feature_schema_version="v0.1", decision_policy_id="",
        decision_policy_version="", technical_ready=True, _package={},
        _artifact_path=str(path), _checksum=hashlib.sha256(path.read_bytes()).hexdigest(),
        _clinical_stage="research draft",
    )


def _install(*entries):
    registry.initialize_registry(registry.ModelRegistry(
        entries=entries, catalog_status="available", available_count=len(entries),
    ))


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "synthetic.h5"
    with h5py.File(path, "w") as f:
        f["patient/id"] = "p1"
        f["scans/target/measurements"] = [2., 3.]
        f["scans/contralateral/measurements"] = [0., 0.]
        f["scans/target/side"] = "LEFT"
        f["scans/contralateral/side"] = "RIGHT"
    return str(path), _normalize_h5(str(path))


def _request(**fields):
    return AraminaProviderRequest(**{
        "patient_id": "p1", "target_side": "left", "container_id": "c1",
        "source_id": "s1", **fields,
    })


def _execute(entry, source, request=None):
    return AraminaWorkflowProvider(entry=entry).execute(
        source[1], aramina_request=request or _request(), h5_path=source[0],
    )


def test_no_external_dependency_or_execution_configuration():
    import tomllib
    config = tomllib.loads(Path("pyproject.toml").read_text())
    assert not any("aramina" in dep.lower() for dep in config["project"]["dependencies"])
    for path in Path("src").rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(n.name.split(".")[0] == "aramina" for n in node.names)
            if isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] != "aramina"
    for name in ("workflow_aramina.py", "workflow_orchestrator.py"):
        text = (Path("src/bremen/api") / name).read_text()
        assert "BREMEN_ARAMINA_PROVIDER_URL" not in text
        assert "provider_url" not in text
    text = Path("src/bremen/api/workflow_aramina.py").read_text()
    assert "os.environ" not in text
    assert "_post_aramina_predict" not in text


def test_request_defaults_and_allowlist():
    payload = _build_aramina_request_json(
        patient_id=" p1 ", target_side=" LEFT ", analysis_author="   ",
    )
    assert payload == {
        "patient_id": "p1", "target_side": "left", "analysis_author": "Bremen Platform",
        "prediction_comment": "",
    }


@pytest.mark.parametrize("overrides", [
    {"patient_id": ""}, {"patient_id": "  "}, {"patient_id": None},
    {"target_side": ""}, {"target_side": "anterior"}, {"target_side": None},
])
def test_invalid_request_never_loads_artifact(tmp_path, source, monkeypatch, overrides):
    loader = MagicMock(side_effect=AssertionError("must not load"))
    monkeypatch.setattr("joblib.load", loader)
    result = _execute(_entry(tmp_path), source, _request(**overrides))
    assert result.error == "ARAMINA_INVALID_REQUEST"
    loader.assert_not_called()


def test_missing_request_fails(tmp_path, source):
    provider = AraminaWorkflowProvider(entry=_entry(tmp_path))
    assert provider.execute(source[1], h5_path=source[0]).error == "ARAMINA_INVALID_REQUEST"
    assert provider.readiness().model_ready
    assert provider.validate_compatibility(source[1]).compatible
    with pytest.raises(AraminaWorkflowError):
        provider.build_features(source[1])
    assert provider.run_inference(None).error == "ARAMINA_INVALID_REQUEST"


def test_local_execution_real_joblib_deterministic_selected_side(tmp_path, source, monkeypatch):
    monkeypatch.delenv("BREMEN_ARAMINA_PROVIDER_URL", raising=False)
    entry = _entry(tmp_path)
    first = _execute(entry, source)
    second = _execute(entry, source)
    right = _execute(entry, source, _request(target_side="right"))
    assert first.status == second.status == right.status == "completed"
    assert first.payload == second.payload
    expected = _package()["model"].predict_proba([[2., 3.]])[0, 1]
    assert first.payload["external_report"]["risk_score"] == pytest.approx(expected)
    assert right.payload["external_report"]["risk_score"] < expected
    assert first.payload["model_id"] == entry.model_id
    assert first.payload["scientifically_certified"] is False
    assert first.payload["technical_demo_only"] is True
    assert first.payload["clinical_stage"] == "research draft"
    assert set(first.payload) == {
        "workflow_id", "model_id", "model_version", "external_report",
        "scientifically_certified", "technical_demo_only", "clinical_stage",
    }


def test_model_selection_uses_distinct_artifacts(tmp_path, source):
    a = _entry(tmp_path)
    b = _entry(tmp_path, _package("aramina-b", reverse=True), "aramina-b")
    _install(a, b)
    provider_a = get_provider_for_model(a.model_id)
    provider_b = get_provider_for_model(b.model_id)
    assert provider_a._entry is a
    assert provider_b._entry is b
    first = _execute(a, source).payload["external_report"]["risk_score"]
    second = _execute(b, source).payload["external_report"]["risk_score"]
    assert first != second


def test_bremen_construction_unchanged(monkeypatch):
    entry = registry.RegistryModelEntry(
        model_id="bremen-a", display_name="Bremen", workflow_id="bremen",
        model_version="b1", artifact_type="portable_logreg", feature_schema_version="v0.1",
        decision_policy_id="d", decision_policy_version="v1", technical_ready=True,
        _package={"portable_logreg": {}}, _checksum="b" * 64,
    )
    _install(entry)
    constructor = MagicMock()
    monkeypatch.setattr("bremen.api.workflow_bremen.BremenProvider", constructor)
    get_provider_for_model(entry.model_id)
    constructor.assert_called_once_with(
        model_package=entry._package, model_checksum=entry._checksum,
        model_version=entry.model_version, model_id=entry.model_id,
    )


@pytest.mark.parametrize("value", [None, [], {}, {"model": "unsupported"}])
def test_unsupported_structure_explicit(tmp_path, source, value):
    entry = _entry(tmp_path)
    joblib.dump(value, entry._artifact_path)
    entry = replace(entry, _checksum=hashlib.sha256(Path(entry._artifact_path).read_bytes()).hexdigest())
    result = _execute(entry, source)
    assert result.status == "failed"
    assert result.error == "ARAMINA_UNSUPPORTED_ARTIFACT"


@pytest.mark.parametrize("field", [
    "model_id", "model_version", "artifact_type", "model", "positive_class", "feature_contract",
    "feature_schema_version",
])
def test_missing_required_artifact_field_rejected(tmp_path, source, field):
    pkg = _package()
    del pkg[field]
    assert _execute(_entry(tmp_path, pkg), source).error == "ARAMINA_UNSUPPORTED_ARTIFACT"


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(model_id="wrong"),
    lambda p: p.update(model_version="wrong"),
    lambda p: p.update(positive_class=17),
    lambda p: p["feature_contract"].update(normalization="invented"),
    lambda p: p["feature_contract"].update(q_grid=[1., 0.]),
    lambda p: p["feature_contract"].update(q_grid=[float("nan")]),
    lambda p: p["feature_contract"].update(q_grid=[0., 1., 2.]),
])
def test_invalid_contract_rejected(tmp_path, source, mutation):
    pkg = _package()
    mutation(pkg)
    assert _execute(_entry(tmp_path, pkg), source).error == "ARAMINA_UNSUPPORTED_ARTIFACT"


def test_integrity_checked_before_load(tmp_path, source, monkeypatch):
    entry = _entry(tmp_path)
    Path(entry._artifact_path).write_bytes(b"tampered secret token")
    loader = MagicMock()
    monkeypatch.setattr("joblib.load", loader)
    assert _execute(entry, source).error == "ARAMINA_ARTIFACT_INTEGRITY_FAILED"
    loader.assert_not_called()


def test_missing_artifact_safe(tmp_path, source):
    entry = replace(_entry(tmp_path), _artifact_path="/private/not-present/model.joblib")
    assert _execute(entry, source).error == "ARAMINA_ARTIFACT_INTEGRITY_FAILED"


@pytest.mark.parametrize("kind", ["patient", "position", "q_grid", "duplicate", "source", "qc"])
def test_unsupported_input_safe(tmp_path, source, kind):
    entry = _entry(tmp_path)
    request = _request(patient_id="wrong") if kind == "patient" else _request()
    path, case = source
    if kind == "position":
        case = replace(case, measurements=tuple(replace(m, position="other") for m in case.measurements))
    elif kind == "q_grid":
        case = replace(case, measurements=tuple(replace(m, q=np.array([4., 5.])) for m in case.measurements))
    elif kind == "duplicate":
        case = replace(case, measurements=case.measurements + (case.measurements[0],))
    elif kind == "source":
        case = replace(case, source_checksum="x" * 64)
    elif kind == "qc":
        case = replace(case, measurements=tuple(replace(m, qc_flags=("failed",)) for m in case.measurements))
    assert _execute(entry, (path, case), request).error == "ARAMINA_UNSUPPORTED_INPUT"


@pytest.mark.parametrize("probabilities", [[[float("nan"), 0.5]], [[0.9, 0.9]], [[-1, 2]], [0.2, 0.8]])
def test_invalid_model_output_rejected(tmp_path, source, monkeypatch, probabilities):
    pkg = _package()
    pkg["model"].predict_proba = MagicMock(return_value=probabilities)
    monkeypatch.setattr("bremen.api.workflow_aramina._load_selected_artifact", lambda entry: pkg)
    assert _execute(_entry(tmp_path), source).error == "ARAMINA_INVALID_RESULT"


def test_exception_and_private_metadata_never_exposed(tmp_path, source, monkeypatch):
    pkg = _package()
    pkg["model"].predict_proba = MagicMock(side_effect=RuntimeError(
        "/tmp/private/model.joblib s3://secret/key token=t ticket=x traceback password"
    ))
    monkeypatch.setattr("bremen.api.workflow_aramina._load_selected_artifact", lambda entry: pkg)
    result = _execute(_entry(tmp_path), source)
    assert result.error == "ARAMINA_EXECUTION_FAILED"
    assert result.payload is None


def test_allowlist_ignores_arbitrary_package_metadata(tmp_path, source):
    pkg = _package()
    pkg.update(_package={"secret": "x"}, notes="/tmp/path", token="bad", clinical_stage="approved")
    entry = _entry(tmp_path, pkg)
    result = _execute(entry, source)
    serialized = json.dumps(result.payload)
    for forbidden in ("_package", "secret", "token", "approved", "/tmp", entry._checksum, entry._artifact_path):
        assert forbidden not in serialized


def test_public_job_runs_normalization_artifact_events_and_report(tmp_path, source, monkeypatch):
    entry = _entry(tmp_path)
    _install(entry)
    monkeypatch.setattr(jobs, "resolve_source", lambda source_id, upload_id: source[0])
    body = {
        "model_id": entry.model_id, "workflow_id": "aramina", "source_id": "s1",
        "container_id": "c1", "patient_id": "p1", "target_side": "left",
        "auth_token": "do-not-forward", "analysis_author": " ",
    }
    monkeypatch.setattr(jobs, "_read_json_body", lambda handler: body)
    sent = MagicMock()
    monkeypatch.setattr(jobs, "_send_json", sent)
    jobs.handle_jobs_create(MagicMock())
    assert sent.call_args.args[1] == 201
    job_dict = sent.call_args.args[2]["job"]
    job = jobs.get_analysis_job(job_dict["job_id"])
    assert job.overall_status == "completed"
    events = jobs.get_job_events(job.job_id)
    types = [e["event_type"] for e in events]
    expected = [
        "runtime.request.accepted", "runtime.normalization.started",
        "runtime.normalization.completed", "runtime.workflow.resolved",
        "runtime.workflow.started", "runtime.output.completed",
        "runtime.workflow.completed", "runtime.request.completed", "runtime.report.completed",
    ]
    assert [t for t in types if t in expected] == expected
    report = jobs.get_job_report(job.job_id, "aramina")
    assert job.reports["aramina"].status == "available"
    public = json.dumps([job_dict, events, report])
    for marker in (entry._artifact_path, entry._checksum, "do-not-forward", "_package", "provider_url"):
        assert marker not in public


@pytest.mark.parametrize("field,value", [("patient_id", ""), ("target_side", "wrong")])
def test_public_job_invalid_fields_fail_before_source(tmp_path, monkeypatch, field, value):
    entry = _entry(tmp_path)
    _install(entry)
    body = {"model_id": entry.model_id, "source_id": "s1", "patient_id": "p1", "target_side": "left"}
    body[field] = value
    monkeypatch.setattr(jobs, "_read_json_body", lambda handler: body)
    resolve = MagicMock()
    monkeypatch.setattr(jobs, "resolve_source", resolve)
    sent = MagicMock()
    monkeypatch.setattr(jobs, "_send_json", sent)
    jobs.handle_jobs_create(MagicMock())
    assert sent.call_args.args[1] == 400
    assert sent.call_args.args[2]["error_code"] == "ARAMINA_INVALID_REQUEST"
    resolve.assert_not_called()


def test_job_unsupported_artifact_reports_failed_event(tmp_path, source):
    entry = _entry(tmp_path, {"unknown": "/tmp/secret"})
    _install(entry)
    job = jobs.create_analysis_job(
        model_id=entry.model_id, h5_path=source[0], aramina_request=_request(),
    )
    assert job.overall_status == "failed"
    assert job.workflow_runs["aramina"].failure == "ARAMINA_UNSUPPORTED_ARTIFACT"
    events = jobs.get_job_events(job.job_id)
    assert "runtime.workflow.failed" in [e["event_type"] for e in events]
    assert "configuration_required" not in json.dumps(events)
    assert job.reports["aramina"].status == "unavailable"


def test_direct_job_missing_fields_rejected_before_normalization(tmp_path, monkeypatch):
    entry = _entry(tmp_path)
    _install(entry)
    normalize = MagicMock()
    monkeypatch.setattr(jobs, "run_workflow_request", normalize)
    with pytest.raises(AraminaWorkflowError, match="ARAMINA_INVALID_REQUEST"):
        jobs.create_analysis_job(model_id=entry.model_id)
    normalize.assert_not_called()


class TestAraminaRequirements:
    """Aramina model requirements include patient_id and target_side."""

    def test_aramina_requirements_includes_patient_fields(self):
        """Aramina manifest-backed requirements declare patient_id and target_side."""
        from bremen.api.model_requirements import (
            _build_declared_requirements_response,
        )
        row = {
            "model_id": "aramina-test",
            "workflow_id": "aramina",
            "model_version": "1.0",
            "feature_schema_version": "v0.1",
        }
        requirements = {
            "schema_version": "bremen.container_requirements.v1",
            "workflow_id": "aramina",
        }
        resp = _build_declared_requirements_response(
            "aramina-test", row, requirements,
        )
        assert resp["requirements_available"] is True
        assert resp["workflow_id"] == "aramina"
        # Aramina default required fields
        assert "patient_id" in resp["required_fields"]
        assert "target_side" in resp["required_fields"]
        assert "container_id" in resp["required_fields"]
        assert "source_id" in resp["required_fields"]
        # Optional fields
        assert "analysis_author" in resp["optional_fields"]
        assert "prediction_comment" in resp["optional_fields"]

    def test_bremen_requirements_unchanged(self):
        """Bremen manifest-backed requirements are unchanged."""
        from bremen.api.model_requirements import (
            _build_declared_requirements_response,
        )
        row = {
            "model_id": "bremen-test",
            "workflow_id": "bremen",
            "model_version": "1.0",
            "feature_schema_version": "v0.1",
        }
        requirements = {
            "schema_version": "bremen.container_requirements.v1",
            "required_metadata": ["patient_id_or_case_id"],
            "optional_metadata": ["age"],
        }
        resp = _build_declared_requirements_response(
            "bremen-test", row, requirements,
        )
        assert resp["requirements_available"] is True
        assert resp["workflow_id"] == "bremen"
        assert "patient_id_or_case_id" in resp["required_fields"]
        assert "age" in resp["optional_fields"]


# ---------------------------------------------------------------------------


# ===================================================================
# FastAPI route-level Aramina request plumbing tests (PR0135)
# ===================================================================

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None  # type: ignore[assignment,misc]


def _fastapi_client():
    from bremen.api.fastapi_app import create_fastapi_app
    return TestClient(create_fastapi_app())


def _valid_aramina_body(*, source_id="fresh-src-001", **overrides):
    """Build a valid Aramina request body."""
    base = {
        "container_id": "Nova_376.h5",
        "source_id": source_id,
        "workflow_id": "aramina",
        "model_id": "aramina-a",
        "patient_id": "Nova_376",
        "target_side": "left",
        "analysis_author": "Bremen Platform",
        "prediction_comment": "",
    }
    base.update(overrides)
    return base


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
class TestFastAPIAraminaRoutePlumbing:
    """PR0135: FastAPI POST /demo/api/jobs Aramina field plumbing."""

    def test_valid_aramina_json_not_rejected(self, tmp_path, source, monkeypatch):
        """Valid Aramina JSON must not return ARAMINA_INVALID_REQUEST."""
        entry = _entry(tmp_path)
        _install(entry)
        monkeypatch.setattr(
            "bremen.api.job_api_handler.resolve_source",
            lambda sid, uid: source[0],
        )
        client = _fastapi_client()
        body = _valid_aramina_body()
        resp = client.post("/demo/api/jobs", json=body)
        # Must not be 400 with ARAMINA_INVALID_REQUEST
        assert resp.status_code != 400, (
            f"Valid Aramina request rejected: {resp.json()}"
        )
        # Should succeed or fail for other reasons (e.g. missing h5) but
        # not for missing patient_id/target_side
        data = resp.json()
        assert data.get("error_code") != "ARAMINA_INVALID_REQUEST"

    def test_valid_aramina_reaches_execution_path(self, tmp_path, source, monkeypatch):
        """Valid Aramina JSON must reach create_analysis_job with aramina_request.

        The job may fail later (e.g. H5 content mismatch with artifact
        feature contract), but it must not be rejected as
        ARAMINA_INVALID_REQUEST at the request validation stage.
        """
        entry = _entry(tmp_path)
        _install(entry)
        monkeypatch.setattr(
            "bremen.api.job_api_handler.resolve_source",
            lambda sid, uid: source[0],
        )
        client = _fastapi_client()
        body = _valid_aramina_body()
        resp = client.post("/demo/api/jobs", json=body)
        assert resp.status_code == 201
        job_data = resp.json()["job"]
        # Must NOT be rejected as invalid request
        assert "ARAMINA_INVALID_REQUEST" not in json.dumps(job_data)
        # Must reach aramina workflow (may succeed or fail at artifact
        # level, but the request validation passed)
        assert "aramina" in job_data["requested_workflows"]

    def test_missing_patient_id_returns_400(self, monkeypatch):
        """Missing patient_id must return 400, not 500."""
        client = _fastapi_client()
        body = _valid_aramina_body()
        del body["patient_id"]
        resp = client.post("/demo/api/jobs", json=body)
        assert resp.status_code == 400
        data = resp.json()
        assert data.get("error_code") == "ARAMINA_INVALID_REQUEST"
        assert data.get("technical_demo_only") is True

    def test_missing_target_side_returns_400(self, monkeypatch):
        """Missing target_side must return 400, not 500."""
        client = _fastapi_client()
        body = _valid_aramina_body()
        del body["target_side"]
        resp = client.post("/demo/api/jobs", json=body)
        assert resp.status_code == 400
        data = resp.json()
        assert data.get("error_code") == "ARAMINA_INVALID_REQUEST"
        assert data.get("technical_demo_only") is True

    def test_invalid_target_side_returns_400(self, monkeypatch):
        """Invalid target_side must return 400, not 500."""
        client = _fastapi_client()
        body = _valid_aramina_body(target_side="anterior")
        resp = client.post("/demo/api/jobs", json=body)
        assert resp.status_code == 400
        data = resp.json()
        assert data.get("error_code") == "ARAMINA_INVALID_REQUEST"
        assert data.get("technical_demo_only") is True

    def test_expected_validation_failure_no_traceback(self, monkeypatch, caplog):
        """Expected Aramina validation failure must not log traceback."""
        import logging
        client = _fastapi_client()
        body = _valid_aramina_body()
        del body["patient_id"]
        with caplog.at_level(logging.ERROR):
            resp = client.post("/demo/api/jobs", json=body)
        assert resp.status_code == 400
        # Must not contain traceback in response text
        assert "Traceback" not in resp.text
        assert "File \"" not in resp.text
        # Must not log traceback either (no .exception() call)
        for record in caplog.records:
            assert "Traceback" not in record.message

    def test_source_id_not_consumed_by_invalid_request(self, monkeypatch):
        """Fresh source_id must not be consumed by invalid Aramina request."""
        resolve = MagicMock()
        monkeypatch.setattr(
            "bremen.api.job_api_handler.resolve_source", resolve,
        )
        client = _fastapi_client()
        body = _valid_aramina_body()
        del body["patient_id"]  # invalid
        resp = client.post("/demo/api/jobs", json=body)
        assert resp.status_code == 400
        # resolve_source must NOT have been called
        resolve.assert_not_called()

    def test_bremen_workflow_unchanged(self, monkeypatch):
        """Bremen workflow_id=bremen is unaffected by Aramina changes."""
        client = _fastapi_client()
        resp = client.post("/demo/api/jobs", json={
            "workflow_id": "bremen",
        })
        # Should return 400 (missing source) — not a 500 or Aramina error
        assert resp.status_code == 400
        data = resp.json()
        assert data.get("error_code") != "ARAMINA_INVALID_REQUEST"

    def test_no_aramina_provider_url_or_http_dependency(self):
        """No provider URL, HTTP, or aramina package dependency added."""
        for name in ("workflow_aramina.py", "workflow_orchestrator.py",
                      "fastapi_app.py", "job_api_handler.py"):
            text = (Path("src/bremen/api") / name).read_text()
            assert "BREMEN_ARAMINA_PROVIDER_URL" not in text
            assert "provider_url" not in text

    def test_no_raw_exception_in_aramina_error_response(self, monkeypatch):
        """Aramina error response must not contain raw exception details."""
        client = _fastapi_client()
        body = _valid_aramina_body(patient_id="")
        resp = client.post("/demo/api/jobs", json=body)
        assert resp.status_code == 400
        text = resp.text
        assert "/Users/" not in text
        assert "/home/" not in text
        assert "Traceback" not in text
        assert "bucket" not in text.lower()
        assert "token" not in text.lower()
