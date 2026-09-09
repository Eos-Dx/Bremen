"""PR0136: Real Aramina training artifact contract alignment.

Tests validate the real production Aramina model.joblib structure:
- kind == "aramina_training_artifact"
- models dict with exactly one model
- model_identity with name/version
- lr1_model, final_model, thresholds, feature_columns, class_definition
- prediction_preprocessing_yaml, prediction_contract_yaml

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
    _FINAL_FEATURE_COLUMNS,
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


# ---------------------------------------------------------------------------
# Production-shaped Aramina artifact fixture helpers
# ---------------------------------------------------------------------------


def _lr1_model(reverse=False):
    """Synthetic lr1_model: LogisticRegression scoring a 7-feature input."""
    X = np.array([
        [1., 0.5, 2., 0., 1., 0.5, 100.],
        [3., 0.2, 4., 1., 3., 1.5, 100.],
        [5., 0.1, 6., 2., 5., 2.5, 100.],
        [0.5, 0.8, 1., 0., 0.5, 0.1, 100.],
    ])
    y = [1, 1, 0, 0] if reverse else [0, 0, 1, 1]
    return LogisticRegression(random_state=0).fit(X, y)


def _final_model(reverse=False):
    """Synthetic final_model: LogisticRegression on 8 feature columns."""
    X = np.array([
        [0.1, 0., 0., 1., 2., 3., 1., 1.],
        [0.8, 0., 0., 2., 4., 6., 2., 1.],
        [0.3, 0., 0., 0.5, 1., 1.5, 0.5, 0.],
        [0.9, 0., 0., 3., 6., 9., 3., 1.],
    ])
    y = [1, 1, 0, 0] if reverse else [0, 0, 1, 1]
    return LogisticRegression(random_state=0).fit(X, y)


def _package(model_id="aramina-a", model_version="test-v1", reverse=False):
    """Build a production-shaped Aramina training artifact."""
    lr1 = _lr1_model(reverse)
    final = _final_model(reverse)
    return {
        "kind": "aramina_training_artifact",
        "version": "0.3",
        "model_type": "logistic_regression",
        "model_columns": [],
        "model_identity": {
            "name": model_id,
            "version": model_version,
        },
        "models": {
            "selected_model": {
                "lr1_model": lr1,
                "final_model": final,
                "thresholds": {"threshold_target": 0.5},
                "feature_columns": list(_FINAL_FEATURE_COLUMNS),
                "class_definition": {"0": "low_risk", "1": "high_risk"},
                "symmetry_policy": "mirror_contralateral",
                "prediction_reference_scores": {},
                "tissue_risk_assessment": {},
                "final_fit_training_metrics": {},
            },
        },
        "model_descriptions": {},
        "feature_schema": {},
        "warnings": [],
        "dataset_summary": {},
        "training_config_yaml": "",
        "prediction_preprocessing_yaml": "steps: []",
        "prediction_contract_yaml": "output: risk_score",
        "model_definition_yaml": "",
        "model_performance": {},
        "final_fit_training_metrics": {},
        "evaluation": {},
        "metadata": {},
        "reproducibility": {},
    }


def _entry(tmp_path, package=None, model_id="aramina-a", model_version="test-v1"):
    """Create a RegistryModelEntry with a staged artifact file."""
    package = package if package is not None else _package(model_id, model_version)
    path = tmp_path / f"{model_id}.joblib"
    joblib.dump(package, path)
    return registry.RegistryModelEntry(
        model_id=model_id, display_name="Synthetic model", workflow_id="aramina",
        model_version=model_version, artifact_type=ARTIFACT_TYPE,
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
    """Build a synthetic H5 with target/contralateral measurements."""
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


# ===================================================================
# No external dependency / execution configuration
# ===================================================================


def test_no_external_dependency_or_execution_configuration():
    """No Aramina package dependency, no provider URL, no HTTP."""
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


# ===================================================================
# Request validation
# ===================================================================


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


# ===================================================================
# Real artifact contract validation
# ===================================================================


def test_valid_production_artifact_accepted(tmp_path, source):
    """Production-shaped Aramina artifact must not return ARAMINA_UNSUPPORTED_ARTIFACT."""
    entry = _entry(tmp_path)
    result = _execute(entry, source)
    # May succeed or fail at input level, but must NOT fail at artifact validation
    assert result.error != "ARAMINA_UNSUPPORTED_ARTIFACT"


def test_missing_kind_fails_safely(tmp_path, source):
    """Missing kind field fails with ARAMINA_UNSUPPORTED_ARTIFACT."""
    pkg = _package()
    del pkg["kind"]
    assert _execute(_entry(tmp_path, pkg), source).error == "ARAMINA_UNSUPPORTED_ARTIFACT"


def test_wrong_kind_fails_safely(tmp_path, source):
    """Wrong kind value fails with ARAMINA_UNSUPPORTED_ARTIFACT."""
    pkg = _package()
    pkg["kind"] = "wrong_kind"
    assert _execute(_entry(tmp_path, pkg), source).error == "ARAMINA_UNSUPPORTED_ARTIFACT"


def test_missing_models_fails_safely(tmp_path, source):
    """Missing models dict fails with ARAMINA_UNSUPPORTED_ARTIFACT."""
    pkg = _package()
    del pkg["models"]
    assert _execute(_entry(tmp_path, pkg), source).error == "ARAMINA_UNSUPPORTED_ARTIFACT"


def test_empty_models_fails_safely(tmp_path, source):
    """Empty models dict fails with ARAMINA_UNSUPPORTED_ARTIFACT."""
    pkg = _package()
    pkg["models"] = {}
    assert _execute(_entry(tmp_path, pkg), source).error == "ARAMINA_UNSUPPORTED_ARTIFACT"


def test_multiple_models_fails_safely(tmp_path, source):
    """Multiple models in models dict fails with ARAMINA_UNSUPPORTED_ARTIFACT."""
    pkg = _package()
    pkg["models"]["extra_model"] = pkg["models"]["selected_model"]
    assert _execute(_entry(tmp_path, pkg), source).error == "ARAMINA_UNSUPPORTED_ARTIFACT"


def test_missing_lr1_model_fails_safely(tmp_path, source):
    """Missing lr1_model in model_info fails safely."""
    pkg = _package()
    del pkg["models"]["selected_model"]["lr1_model"]
    assert _execute(_entry(tmp_path, pkg), source).error == "ARAMINA_UNSUPPORTED_ARTIFACT"


def test_missing_final_model_fails_safely(tmp_path, source):
    """Missing final_model in model_info fails safely."""
    pkg = _package()
    del pkg["models"]["selected_model"]["final_model"]
    assert _execute(_entry(tmp_path, pkg), source).error == "ARAMINA_UNSUPPORTED_ARTIFACT"


def test_missing_thresholds_fails_safely(tmp_path, source):
    """Missing thresholds in model_info fails safely."""
    pkg = _package()
    del pkg["models"]["selected_model"]["thresholds"]
    assert _execute(_entry(tmp_path, pkg), source).error == "ARAMINA_UNSUPPORTED_ARTIFACT"


def test_missing_feature_columns_fails_safely(tmp_path, source):
    """Missing feature_columns in model_info fails safely."""
    pkg = _package()
    del pkg["models"]["selected_model"]["feature_columns"]
    assert _execute(_entry(tmp_path, pkg), source).error == "ARAMINA_UNSUPPORTED_ARTIFACT"


def test_missing_prediction_preprocessing_yaml_fails_safely(tmp_path, source):
    """Missing prediction_preprocessing_yaml fails safely."""
    pkg = _package()
    del pkg["prediction_preprocessing_yaml"]
    assert _execute(_entry(tmp_path, pkg), source).error == "ARAMINA_UNSUPPORTED_ARTIFACT"


def test_empty_prediction_preprocessing_yaml_fails_safely(tmp_path, source):
    """Empty prediction_preprocessing_yaml fails safely."""
    pkg = _package()
    pkg["prediction_preprocessing_yaml"] = "  "
    assert _execute(_entry(tmp_path, pkg), source).error == "ARAMINA_UNSUPPORTED_ARTIFACT"


def test_missing_prediction_contract_yaml_fails_safely(tmp_path, source):
    """Missing prediction_contract_yaml fails safely."""
    pkg = _package()
    del pkg["prediction_contract_yaml"]
    assert _execute(_entry(tmp_path, pkg), source).error == "ARAMINA_UNSUPPORTED_ARTIFACT"


def test_missing_model_identity_fails_safely(tmp_path, source):
    """Missing model_identity fails safely."""
    pkg = _package()
    del pkg["model_identity"]
    assert _execute(_entry(tmp_path, pkg), source).error == "ARAMINA_UNSUPPORTED_ARTIFACT"


def test_empty_model_identity_version_fails_safely(tmp_path, source):
    """Empty model_identity.version fails safely."""
    pkg = _package()
    pkg["model_identity"]["version"] = ""
    assert _execute(_entry(tmp_path, pkg), source).error == "ARAMINA_UNSUPPORTED_ARTIFACT"


def test_model_version_identity_mismatch_fails_safely(tmp_path, source):
    """Version mismatch between registry and artifact identity fails safely."""
    pkg = _package(model_version="v1.0")
    entry = _entry(tmp_path, pkg, model_version="v2.0")
    assert _execute(entry, source).error == "ARAMINA_MODEL_IDENTITY_MISMATCH"


# ===================================================================
# Artifact integrity checks
# ===================================================================


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


# ===================================================================
# Unsupported structures
# ===================================================================


@pytest.mark.parametrize("value", [None, [], {}, {"kind": "other"}])
def test_unsupported_structure_explicit(tmp_path, source, value):
    entry = _entry(tmp_path)
    joblib.dump(value, entry._artifact_path)
    entry = replace(entry, _checksum=hashlib.sha256(Path(entry._artifact_path).read_bytes()).hexdigest())
    result = _execute(entry, source)
    assert result.status == "failed"
    assert result.error == "ARAMINA_UNSUPPORTED_ARTIFACT"


# ===================================================================
# Execution and output
# ===================================================================


def test_local_execution_completed_status(tmp_path, source):
    """Valid production artifact must reach completed status."""
    entry = _entry(tmp_path)
    result = _execute(entry, source)
    assert result.status == "completed"
    assert result.payload is not None
    assert result.payload["model_id"] == entry.model_id
    assert result.payload["model_version"] == entry.model_version
    assert result.payload["scientifically_certified"] is False
    assert result.payload["technical_demo_only"] is True
    assert result.payload["clinical_stage"] == "research draft"
    assert set(result.payload) == {
        "workflow_id", "model_id", "model_version", "external_report",
        "scientifically_certified", "technical_demo_only", "clinical_stage",
    }


def test_external_report_structure(tmp_path, source):
    """External report must contain expected safe fields."""
    entry = _entry(tmp_path)
    result = _execute(entry, source)
    report = result.payload["external_report"]
    assert "risk_probability" in report
    assert "target_class_risk_level" in report
    assert "decision_threshold" in report
    assert "target_side" in report
    assert "model_name" in report
    assert "model_version" in report
    assert "reliability" in report
    assert "reliability_reason" in report
    assert isinstance(report["risk_probability"], float)
    assert 0 <= report["risk_probability"] <= 1


def test_model_version_not_empty(tmp_path, source):
    """model_version must not be empty in payload."""
    entry = _entry(tmp_path, model_version="v1.2.3")
    result = _execute(entry, source)
    assert result.payload["model_version"] == "v1.2.3"
    report = result.payload["external_report"]
    assert report["model_version"] == "v1.2.3"


def test_deterministic_execution(tmp_path, source):
    """Same inputs must produce same output."""
    entry = _entry(tmp_path)
    first = _execute(entry, source)
    second = _execute(entry, source)
    assert first.status == second.status
    assert first.payload["external_report"]["risk_probability"] == \
        second.payload["external_report"]["risk_probability"]


def test_model_selection_uses_distinct_artifacts(tmp_path, source):
    """Different artifacts produce different scores."""
    a = _entry(tmp_path, model_id="aramina-a")
    b = _entry(tmp_path, _package("aramina-b", reverse=True), "aramina-b")
    _install(a, b)
    provider_a = get_provider_for_model(a.model_id)
    provider_b = get_provider_for_model(b.model_id)
    assert provider_a._entry is a
    assert provider_b._entry is b


def test_invalid_model_output_rejected(tmp_path, source, monkeypatch):
    """Invalid final_model output must fail safely."""
    from unittest.mock import MagicMock as _MM
    bad_final = _MM()
    bad_final.predict_proba = _MM(return_value=np.array([[float("nan"), 0.5]]))
    pkg = _package()
    pkg["models"]["selected_model"]["final_model"] = bad_final
    monkeypatch.setattr(
        "bremen.api.workflow_aramina._load_selected_artifact", lambda entry: pkg,
    )
    result = _execute(_entry(tmp_path), source)
    assert result.status == "failed"


def test_exception_and_private_metadata_never_exposed(tmp_path, source, monkeypatch):
    """Exceptions must not leak private metadata."""
    from unittest.mock import MagicMock as _MM
    bad_lr1 = _MM()
    bad_lr1.predict_proba = _MM(side_effect=RuntimeError(
        "/tmp/private/model.joblib s3://secret/key token=t ticket=x traceback password"
    ))
    pkg = _package()
    pkg["models"]["selected_model"]["lr1_model"] = bad_lr1
    monkeypatch.setattr(
        "bremen.api.workflow_aramina._load_selected_artifact", lambda entry: pkg,
    )
    result = _execute(_entry(tmp_path), source)
    assert result.status == "failed"
    assert result.payload is None


def test_allowlist_ignores_arbitrary_package_metadata(tmp_path, source):
    """Arbitrary metadata must not leak into public output."""
    pkg = _package()
    pkg.update(_package={"secret": "x"}, notes="/tmp/path", token="bad")
    entry = _entry(tmp_path, pkg)
    result = _execute(entry, source)
    if result.payload is not None:
        serialized = json.dumps(result.payload)
        for forbidden in ("_package", "secret", "token", "/tmp", entry._checksum, entry._artifact_path):
            assert forbidden not in serialized


# ===================================================================
# Bremen contract unchanged
# ===================================================================


def test_bremen_construction_unchanged(monkeypatch):
    """Bremen provider construction must be byte-for-byte equivalent."""
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


# ===================================================================
# Public job integration
# ===================================================================


def test_public_job_runs_normalization_artifact_events_and_report(tmp_path, source, monkeypatch):
    """Full public job path must emit expected events and produce a report."""
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


# ===================================================================
# Requirements
# ===================================================================


class TestAraminaRequirements:
    """Aramina model requirements include patient_id and target_side."""

    def test_aramina_requirements_includes_patient_fields(self):
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
        assert "patient_id" in resp["required_fields"]
        assert "target_side" in resp["required_fields"]
        assert "container_id" in resp["required_fields"]
        assert "source_id" in resp["required_fields"]
        assert "analysis_author" in resp["optional_fields"]
        assert "prediction_comment" in resp["optional_fields"]

    def test_bremen_requirements_unchanged(self):
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
        entry = _entry(tmp_path)
        _install(entry)
        monkeypatch.setattr(
            "bremen.api.job_api_handler.resolve_source",
            lambda sid, uid: source[0],
        )
        client = _fastapi_client()
        body = _valid_aramina_body()
        resp = client.post("/demo/api/jobs", json=body)
        assert resp.status_code != 400, (
            f"Valid Aramina request rejected: {resp.json()}"
        )
        data = resp.json()
        assert data.get("error_code") != "ARAMINA_INVALID_REQUEST"

    def test_valid_aramina_reaches_execution_path(self, tmp_path, source, monkeypatch):
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
        assert "ARAMINA_INVALID_REQUEST" not in json.dumps(job_data)
        assert "aramina" in job_data["requested_workflows"]

    def test_missing_patient_id_returns_400(self, monkeypatch):
        client = _fastapi_client()
        body = _valid_aramina_body()
        del body["patient_id"]
        resp = client.post("/demo/api/jobs", json=body)
        assert resp.status_code == 400
        data = resp.json()
        assert data.get("error_code") == "ARAMINA_INVALID_REQUEST"
        assert data.get("technical_demo_only") is True

    def test_missing_target_side_returns_400(self, monkeypatch):
        client = _fastapi_client()
        body = _valid_aramina_body()
        del body["target_side"]
        resp = client.post("/demo/api/jobs", json=body)
        assert resp.status_code == 400
        data = resp.json()
        assert data.get("error_code") == "ARAMINA_INVALID_REQUEST"

    def test_invalid_target_side_returns_400(self, monkeypatch):
        client = _fastapi_client()
        body = _valid_aramina_body(target_side="anterior")
        resp = client.post("/demo/api/jobs", json=body)
        assert resp.status_code == 400
        data = resp.json()
        assert data.get("error_code") == "ARAMINA_INVALID_REQUEST"

    def test_expected_validation_failure_no_traceback(self, monkeypatch, caplog):
        import logging
        client = _fastapi_client()
        body = _valid_aramina_body()
        del body["patient_id"]
        with caplog.at_level(logging.ERROR):
            resp = client.post("/demo/api/jobs", json=body)
        assert resp.status_code == 400
        assert "Traceback" not in resp.text
        for record in caplog.records:
            assert "Traceback" not in record.message

    def test_source_id_not_consumed_by_invalid_request(self, monkeypatch):
        resolve = MagicMock()
        monkeypatch.setattr(
            "bremen.api.job_api_handler.resolve_source", resolve,
        )
        client = _fastapi_client()
        body = _valid_aramina_body()
        del body["patient_id"]
        resp = client.post("/demo/api/jobs", json=body)
        assert resp.status_code == 400
        resolve.assert_not_called()

    def test_bremen_workflow_unchanged(self, monkeypatch):
        client = _fastapi_client()
        resp = client.post("/demo/api/jobs", json={
            "workflow_id": "bremen",
        })
        assert resp.status_code == 400
        data = resp.json()
        assert data.get("error_code") != "ARAMINA_INVALID_REQUEST"

    def test_no_aramina_provider_url_or_http_dependency(self):
        for name in ("workflow_aramina.py", "workflow_orchestrator.py",
                      "fastapi_app.py", "job_api_handler.py"):
            text = (Path("src/bremen/api") / name).read_text()
            assert "BREMEN_ARAMINA_PROVIDER_URL" not in text
            assert "provider_url" not in text

    def test_no_raw_exception_in_aramina_error_response(self, monkeypatch):
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
