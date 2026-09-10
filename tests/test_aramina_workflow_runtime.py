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
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from bremen.api import job_api_handler as jobs
from bremen.api import model_registry as registry
from bremen.api.aramina_provider import AraminaProviderRequest
from bremen.api.workflow_aramina import (
    _FINAL_FEATURE_COLUMNS,
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


@pytest.fixture(autouse=True)
def synthetic_preprocessing(monkeypatch):
    """Unit-test H5 adapter only; integration tests exercise the real worker separately."""
    def preprocess(h5_path, config_yaml):
        canonical = _normalize_h5(h5_path)
        return pd.DataFrame([
            {"patientId": "p1", "side": m.side, "age": None,
             "radial_profile_data": list(m.intensity),
             "q_range": list(np.linspace(2., 23., len(m.intensity)))}
            for m in canonical.measurements
        ])
    from bremen.api.aramina_preprocessing import preprocess_aramina
    monkeypatch.setattr("bremen.api.aramina_preprocessing.preprocess_aramina", preprocess)
    return preprocess_aramina


# ---------------------------------------------------------------------------
# Production-shaped Aramina artifact fixture helpers
# ---------------------------------------------------------------------------


def _lr1_model(n_features=10, reverse=False):
    """Synthetic lr1_model: LogisticRegression scoring profile_matrix rows."""
    rng = np.random.RandomState(42)
    X = rng.rand(4, n_features)
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
    # lr1_model expects profile_matrix rows of width 10
    lr1 = _lr1_model(n_features=10, reverse=reverse)
    final = _final_model(reverse=reverse)
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
    """Build a synthetic H5 with target/contralateral measurements.

    Each measurement has 10 intensity points to match lr1_model
    expected profile_matrix width.
    """
    path = tmp_path / "synthetic.h5"
    target_data = [float(i) for i in range(10)]
    control_data = [float(i) * 0.1 for i in range(10)]
    with h5py.File(path, "w") as f:
        f["patient/id"] = "p1"
        f["scans/target/measurements"] = target_data
        f["scans/contralateral/measurements"] = control_data
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
    # PR0139 permits only the opt-in private diagnostic switch.
    env_calls = [node for node in ast.walk(ast.parse(text))
                 if isinstance(node, ast.Call)
                 and ast.unparse(node.func) == "os.environ.get"]
    assert env_calls
    assert all(ast.literal_eval(node.args[0]) == "BREMEN_ARAMINA_DEBUG_TRACE"
               for node in env_calls)
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


@pytest.fixture
def catalog_provider_trace(monkeypatch):
    """Observe real resolution/registration; fail if fallback is attempted."""
    from bremen.api import workflow_orchestrator as orchestrator
    from bremen.api.workflow_registry import WorkflowRegistry

    resolve = MagicMock(wraps=orchestrator.get_provider_for_model)
    register = MagicMock(side_effect=WorkflowRegistry.register)
    default = MagicMock(side_effect=AssertionError("Unexpected default registry"))
    scaffold = MagicMock(side_effect=AssertionError("Unexpected scaffold"))
    monkeypatch.setattr(orchestrator, "get_provider_for_model", resolve)
    monkeypatch.setattr(orchestrator, "get_default_registry", default)
    monkeypatch.setattr(
        "bremen.api.workflow_aramina_scaffold.AraminaProvider", scaffold,
    )
    monkeypatch.setattr(
        WorkflowRegistry, "register", lambda self, provider: register(self, provider),
    )
    return resolve, register, default, scaffold


def test_catalog_job_registers_real_aramina_provider(tmp_path, source, catalog_provider_trace):
    entry = _entry(tmp_path)
    _install(entry)
    job = jobs.create_analysis_job(
        model_id=entry.model_id, h5_path=source[0], aramina_request=_request(),
    )
    resolve, register, default, scaffold = catalog_provider_trace
    resolve.assert_called_once_with(entry.model_id)
    assert register.call_count == 1
    workflow_registry, provider = register.call_args.args
    assert type(provider) is AraminaWorkflowProvider
    assert provider._entry is entry
    assert workflow_registry.resolve("aramina") is provider
    assert provider.readiness().model_ready is True
    assert job.overall_status == "completed"
    default.assert_not_called()
    scaffold.assert_not_called()


@pytest.mark.parametrize("bremen_loaded", [False, True])
def test_default_registry_uses_real_aramina_and_preserves_bremen(
    tmp_path, monkeypatch, bremen_loaded,
):
    from bremen.api.model_state import ModelState
    from bremen.api.workflow_bremen import BremenProvider
    from bremen.api.workflow_orchestrator import get_default_registry

    entry = _entry(tmp_path)
    bremen_entry = replace(
        entry, model_id="bremen-a", workflow_id="bremen", artifact_type="portable_logreg",
    )
    _install(bremen_entry, entry)
    package = {"portable_logreg": {}} if bremen_loaded else None
    monkeypatch.setattr(ModelState, "get_model", lambda: package)
    monkeypatch.setattr(ModelState, "get_instance", lambda: MagicMock(
        _model_checksum="checksum", _model_version="version",
    ))
    constructor = MagicMock(wraps=BremenProvider)
    monkeypatch.setattr("bremen.api.workflow_bremen.BremenProvider", constructor)
    workflow_registry = get_default_registry()
    provider = workflow_registry.resolve("aramina")
    assert type(provider) is AraminaWorkflowProvider
    assert provider._entry is entry
    assert provider.readiness().model_ready is True
    assert type(get_provider_for_model(entry.model_id)) is AraminaWorkflowProvider
    constructor.assert_called_once_with(
        model_package=package,
        model_checksum="checksum" if bremen_loaded else "",
        model_version="version" if bremen_loaded else "",
    )
    assert type(workflow_registry.resolve("bremen")) is BremenProvider


@pytest.mark.parametrize("catalog", ["empty", "bremen", "unavailable", "wrong_type", "multiple"])
def test_default_registry_leaves_aramina_unregistered(tmp_path, catalog):
    from bremen.api.workflow_orchestrator import get_default_registry
    from bremen.api.workflow_registry import WorkflowNotFoundError

    if catalog != "empty":
        entry = _entry(tmp_path)
        entries = {
            "bremen": (replace(entry, workflow_id="bremen"),),
            "unavailable": (replace(entry, availability="unavailable"),),
            "wrong_type": (replace(entry, artifact_type="portable_logreg"),),
            "multiple": (entry, replace(entry, model_id="aramina-b")),
        }[catalog]
        _install(*entries)
    workflow_registry = get_default_registry()
    assert workflow_registry.list_workflow_ids() == ["bremen"]
    with pytest.raises(WorkflowNotFoundError):
        workflow_registry.resolve("aramina")


def test_default_registry_never_imports_or_constructs_scaffold(tmp_path, monkeypatch):
    import builtins

    from bremen.api.workflow_orchestrator import get_default_registry

    original_import = builtins.__import__

    def reject_scaffold(name, *args, **kwargs):
        assert "workflow_aramina_scaffold" not in name
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_scaffold)
    assert get_default_registry().list_workflow_ids() == ["bremen"]
    _install(_entry(tmp_path))
    assert type(get_default_registry().resolve("aramina")) is AraminaWorkflowProvider


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

    @pytest.mark.parametrize("unsupported", [False, True])
    def test_model_id_post_uses_real_provider_without_scaffold(
        self, tmp_path, source, monkeypatch, catalog_provider_trace, unsupported,
    ):
        package = {"kind": "unsupported"} if unsupported else _package()
        entry = _entry(tmp_path, package)
        _install(entry)
        monkeypatch.setattr(jobs, "resolve_source", lambda sid, uid: source[0])
        response = _fastapi_client().post(
            "/demo/api/jobs", json=_valid_aramina_body(patient_id="p1"),
        )
        assert response.status_code == 201
        resolve, register, default, scaffold = catalog_provider_trace
        resolve.assert_called_once_with(entry.model_id)
        assert register.call_count == 1
        workflow_registry, provider = register.call_args.args
        assert type(provider) is AraminaWorkflowProvider
        assert provider._entry is entry
        assert workflow_registry.resolve("aramina") is provider
        default.assert_not_called()
        scaffold.assert_not_called()
        job = jobs.get_analysis_job(response.json()["job"]["job_id"])
        assert job.overall_status == ("failed" if unsupported else "completed")
        event_types = [e["event_type"] for e in jobs.get_job_events(job.job_id)]
        assert "runtime.normalization.completed" in event_types
        assert "runtime.workflow.started" in event_types
        if unsupported:
            assert job.workflow_runs["aramina"].failure == "ARAMINA_UNSUPPORTED_ARTIFACT"
            assert "runtime.workflow.failed" in event_types

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


# PR0139: Opt-in private runtime checkpoints; public errors stay unchanged.

def _trace_records(caplog):
    return [json.loads(record.getMessage().split("aramina.debug_trace ", 1)[1])
            for record in caplog.records
            if record.getMessage().startswith("aramina.debug_trace ")]


@pytest.mark.parametrize("enabled", [False, True])
def test_debug_trace_lr1_pipeline_feature_mismatch(tmp_path, source, monkeypatch, caplog, enabled):
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    pkg = _package()
    rng = np.random.RandomState(7)
    pipeline = make_pipeline(StandardScaler(), LogisticRegression())
    pipeline.fit(rng.rand(4, 100), [0, 0, 1, 1])
    pkg["models"]["selected_model"]["lr1_model"] = pipeline
    monkeypatch.setenv("BREMEN_ARAMINA_DEBUG_TRACE", "1" if enabled else "0")
    result = _execute(_entry(tmp_path, pkg), source)
    # PR0141: an LR1 input-width mismatch is an lr1_contract input failure.
    assert result.error == "ARAMINA_UNSUPPORTED_INPUT"
    assert result.failure_stage == "lr1_contract"
    assert result.payload is None
    records = _trace_records(caplog)
    if not enabled:
        assert records == []
        return
    merged = {key: value for record in records for key, value in record.items()}
    assert merged["artifact_loaded"] is True
    assert merged["lr1_model_type"] == "Pipeline"
    assert merged["lr1_expected_feature_count"] == 100
    assert merged["canonical_measurement_count"] == 2
    assert merged["target_side"] == "left"
    assert merged["target_measurement_count"] == 1
    assert merged["target_profile_lengths"] == [10]
    assert merged["lr1_input_shape"] == [1, 10]
    assert merged["lr1_exception_class"] == "ValueError"
    assert merged["lr1_exception_stage"] == "lr1_predict_proba"
    assert merged["final_input_shape"] is None
    assert merged["final_exception_class"] is None


@pytest.mark.parametrize("failure,stage,exception", [
    ("final", "final_predict_proba", "ValueError"),
    ("threshold", "threshold", "TypeError"),
])
def test_debug_trace_final_stages(tmp_path, source, monkeypatch, caplog, failure, stage, exception):
    monkeypatch.setenv("BREMEN_ARAMINA_DEBUG_TRACE", "1")
    pkg = _package()
    info = pkg["models"]["selected_model"]
    if failure == "final":
        info["final_model"] = _lr1_model(n_features=9)
    else:
        info["thresholds"]["threshold_target"] = "invalid"
    result = _execute(_entry(tmp_path, pkg), source)
    # PR0141: final-model input failure is final_model_contract; a bad
    # threshold value is not an input-contract failure and stays generic.
    expected_code = "ARAMINA_UNSUPPORTED_INPUT" if failure == "final" else "ARAMINA_EXECUTION_FAILED"
    assert result.error == expected_code
    merged = {key: value for record in _trace_records(caplog) for key, value in record.items()}
    assert merged["final_input_shape"] == [1, 8]
    assert merged["final_feature_columns"] == list(_FINAL_FEATURE_COLUMNS)
    assert merged["final_exception_class"] == exception
    assert merged["final_exception_stage"] == stage


def test_debug_trace_success_is_private(tmp_path, source, monkeypatch, caplog):
    monkeypatch.setenv("BREMEN_ARAMINA_DEBUG_TRACE", "1")
    result = _execute(_entry(tmp_path), source)
    assert result.status == "completed"
    assert "debug_trace" not in json.dumps(result.payload)
    merged = {key: value for record in _trace_records(caplog) for key, value in record.items()}
    assert merged["selected_model_info_keys"]
    assert merged["feature_columns"] == list(_FINAL_FEATURE_COLUMNS)
    assert merged["threshold_keys"] == ["threshold_target"]
    assert merged["final_input_shape"] == [1, 8]
    assert merged["lr1_exception_class"] is None
    assert merged["final_exception_class"] is None


def test_debug_trace_redacts_untrusted_metadata_and_exception(tmp_path, source, monkeypatch, caplog):
    monkeypatch.setenv("BREMEN_ARAMINA_DEBUG_TRACE", "1")
    secret = "s3://private/key /tmp/private token=secret ticket=secret patient-private"
    error_type = type(secret, (RuntimeError,), {})
    model_type = type(secret, (), {
        "predict_proba": lambda self, values: (_ for _ in ()).throw(error_type(secret)),
        "__repr__": lambda self: secret,
    })
    pkg = _package()
    info = pkg["models"]["selected_model"]
    info[secret] = secret
    info["thresholds"][secret] = secret
    info["feature_columns"].append(secret)
    info["lr1_model"] = model_type()
    entry = _entry(tmp_path)
    monkeypatch.setattr("bremen.api.workflow_aramina._load_selected_artifact", lambda entry: pkg)
    result = _execute(entry, source)
    assert result.error == "ARAMINA_UNSUPPORTED_INPUT"
    assert result.failure_stage == "lr1_contract"
    text = json.dumps(_trace_records(caplog))
    for forbidden in (secret, entry._artifact_path, entry._checksum, "Traceback", "patient-private"):
        assert forbidden not in text
    assert '"lr1_exception_class": "redacted"' in text
    assert all(record.exc_info is None for record in caplog.records)


def test_debug_trace_logging_failure_does_not_change_result(tmp_path, source, monkeypatch):
    monkeypatch.setenv("BREMEN_ARAMINA_DEBUG_TRACE", "1")
    monkeypatch.setattr("logging.Logger.warning", MagicMock(side_effect=RuntimeError("log failed")))
    assert _execute(_entry(tmp_path), source).status == "completed"


def test_debug_trace_failure_stays_out_of_public_job(tmp_path, source, monkeypatch, caplog):
    monkeypatch.setenv("BREMEN_ARAMINA_DEBUG_TRACE", "1")
    pkg = _package()
    pkg["models"]["selected_model"]["lr1_model"] = _lr1_model(n_features=11)
    entry = _entry(tmp_path, pkg)
    _install(entry)
    job = jobs.create_analysis_job(
        model_id=entry.model_id, h5_path=source[0], aramina_request=_request(),
    )
    assert job.workflow_runs["aramina"].failure == "ARAMINA_UNSUPPORTED_INPUT"
    assert job.workflow_runs["aramina"].failure_details["failure_stage"] == "lr1_contract"
    assert _trace_records(caplog)[-1]["lr1_exception_class"] == "ValueError"
    public = json.dumps([job.to_dict(), jobs.get_job_events(job.job_id)])
    for forbidden in ("lr1_input_shape", "lr1_exception_class", "debug_trace", "ValueError"):
        assert forbidden not in public


@pytest.mark.parametrize("release,variable", [
    ("v0.1.7-beta", "BREMEN_ARAMINA_PREPROCESS_PYTHON"),
    ("v0.1.9-beta", "BREMEN_ARAMINA_PREPROCESS_019_PYTHON"),
])
def test_artifact_preprocessing_uses_isolated_version(synthetic_preprocessing, monkeypatch, release, variable):
    import subprocess

    import yaml

    config = {"xrd_preprocessing": {"release_tag": release}, "pipeline": {"steps": [{"name": "raw"}]}}
    monkeypatch.setenv(variable, "/test/python")
    run = MagicMock(return_value=subprocess.CompletedProcess([], 0, json.dumps({"rows": [{
        "patientId": "p1", "side": "left", "age": None,
        "radial_profile_data": [2., 3.], "q_range": [2., 23.],
    }]}), ""))
    monkeypatch.setattr("bremen.api.aramina_preprocessing.subprocess.run", run)
    result = synthetic_preprocessing("private-input", yaml.safe_dump(config))
    assert result.iloc[0].radial_profile_data == [2., 3.]
    assert run.call_args.args[0][:2] == ["/test/python", "-I"]
    assert json.loads(run.call_args.kwargs["input"])["config_yaml"] == yaml.safe_dump(config)
    assert run.call_args.kwargs["capture_output"] is True


def test_preprocessing_worker_errors_are_safe(synthetic_preprocessing, monkeypatch):
    import subprocess
    run = MagicMock(return_value=subprocess.CompletedProcess([], 1, "secret", "private path"))
    monkeypatch.setattr("bremen.api.aramina_preprocessing.subprocess.run", run)
    with pytest.raises(ValueError, match="^Aramina preprocessing failed$"):
        synthetic_preprocessing("private", "xrd_preprocessing: {release_tag: v0.1.7-beta}\npipeline: {steps: [raw]}")
    # PR0142: the message is a fixed safe string; the allowlisted subdiagnostic
    # is carried on the exception instead of in the message.
    with pytest.raises(ValueError, match="^Aramina preprocessing failed$") as excinfo:
        synthetic_preprocessing("private", "{}")
    assert excinfo.value.diagnostic["preprocessing_stage"] == "worker_config"
    assert excinfo.value.diagnostic["preprocessing_reason_code"] == (
        "ARAMINA_PREPROCESSING_CONFIG_FAILED"
    )


def test_real_profile_matrix_and_named_final_features(tmp_path, source, monkeypatch):
    pkg = _package()
    info = pkg["models"]["selected_model"]
    info["lr1_model"] = _lr1_model(n_features=100)
    lr1 = MagicMock(wraps=info["lr1_model"].predict_proba)
    final = MagicMock(wraps=info["final_model"].predict_proba)
    info["lr1_model"].predict_proba = lr1
    info["final_model"].predict_proba = final
    profile = np.linspace(2., 6., 100)
    frame = pd.DataFrame([{"patientId": "p1", "side": "left", "age": 42.,
                           "radial_profile_data": profile, "q_range": np.linspace(2., 23., 100)}])
    monkeypatch.setattr("bremen.api.aramina_preprocessing.preprocess_aramina", lambda *args: frame)
    monkeypatch.setattr("bremen.api.workflow_aramina._load_selected_artifact", lambda entry: pkg)
    result = _execute(_entry(tmp_path), source)
    assert result.status == "completed"
    np.testing.assert_array_equal(lr1.call_args.args[0], profile.reshape(1, 100))
    received = final.call_args.args[0]
    assert isinstance(received, pd.DataFrame)
    assert list(received.columns) == list(_FINAL_FEATURE_COLUMNS)
    assert received["age"].iloc[0] == 42.
    assert received["age_available"].iloc[0] == 1.
    assert 0 <= received["profile_p_cancer_logit_average"].iloc[0] <= 1
    assert received["symmetry_available"].iloc[0] == 0


def test_observed_0213_pickle_symbol_and_old_bridge_unchanged(monkeypatch):
    import pickle
    import sys

    from bremen.api.aramina_artifact_compat import (
        GatedSymmetryLogistic,
        TargetBreastGatedSymmetryLogistic,
        ensure_compatibility_bridge,
    )
    monkeypatch.delitem(sys.modules, "aramina.target_breast_model", raising=False)
    ensure_compatibility_bridge()
    assert pickle.loads(b"caramina.target_breast_model\nGatedSymmetryLogistic\n.") is TargetBreastGatedSymmetryLogistic
    assert pickle.loads(b"caramina.m2q_model\nGatedSymmetryLogistic\n.") is GatedSymmetryLogistic


def test_0213_compatibility_scores_fitted_state(tmp_path, source):
    from sklearn.preprocessing import StandardScaler

    from bremen.api.aramina_artifact_compat import TargetBreastGatedSymmetryLogistic

    model = TargetBreastGatedSymmetryLogistic()
    model.base_fill_values_ = pd.Series([0., 0., 0.], index=_FINAL_FEATURE_COLUMNS[:3])
    model.base_scaler_ = StandardScaler().fit(np.array([[0., 0., 0.], [1., 1., 1.]]))
    model.symmetry_means_ = pd.Series([0., 0., 0., 0.], index=_FINAL_FEATURE_COLUMNS[3:7])
    model.symmetry_scales_ = pd.Series([1., 1., 1., 1.], index=_FINAL_FEATURE_COLUMNS[3:7])
    model.logreg_ = _lr1_model(n_features=7)
    pkg = _package(model_version="0.2.13-beta")
    pkg["models"]["selected_model"]["final_model"] = model
    result = _execute(_entry(tmp_path, pkg, model_version="0.2.13-beta"), source)
    assert result.status == "completed"
    assert result.payload["model_version"] == "0.2.13-beta"
    x = pd.DataFrame([[None, 1., 1., None, 1., 2., 3., 0.]], columns=_FINAL_FEATURE_COLUMNS)
    matrix = model._matrix(x)
    np.testing.assert_array_equal(matrix[:, 3:], np.zeros((1, 4)))
    assert np.isfinite(matrix).all()


@pytest.mark.parametrize("change,check", [("kind", "artifact_kind"), ("missing", "required_model_keys")])
def test_artifact_validation_trace_names_exact_check(tmp_path, source, monkeypatch, caplog, change, check):
    monkeypatch.setenv("BREMEN_ARAMINA_DEBUG_TRACE", "1")
    pkg = _package()
    if change == "kind":
        pkg["kind"] = "private-value"
    else:
        del pkg["models"]["selected_model"]["lr1_model"]
    assert _execute(_entry(tmp_path, pkg), source).error == "ARAMINA_UNSUPPORTED_ARTIFACT"
    assert any(record.get("validation_check") == check for record in _trace_records(caplog))
    assert "private-value" not in json.dumps(_trace_records(caplog))


def test_symmetry_uses_paired_profiles_and_declared_gate():
    from bremen.api.aramina_symmetry import CORE4, symmetry_features
    q = np.linspace(2., 23., 100)
    rows = [{"side": side, "q_range": q, "radial_profile_data": 2 + factor * np.exp(-(q - 14.) ** 2)}
            for side, factor in [("left", 2.), ("left", 3.), ("right", 1.), ("right", 1.5)]]
    frame = pd.DataFrame(rows)
    for contract in ("aramina_sk_symmetry_v0_1", "aramina_sk_symmetry_v0_2"):
        features = symmetry_features(frame, "left", contract)
        assert features["symmetry_available"] == 1
        assert all(np.isfinite(features[k]) for k in CORE4)
        assert features["sk_weightedrms1"] > 0
    gate = symmetry_features(frame.iloc[[0, 2]], "left", "aramina_sk_symmetry_v0_2")
    assert gate["symmetry_available"] == 0
    assert all(gate[k] == 0 for k in CORE4)
    with pytest.raises(ValueError, match="Unsupported symmetry contract"):
        symmetry_features(frame, "left", "unknown")


@pytest.mark.parametrize("fails", [False, True])
def test_isolated_worker_protocol(monkeypatch, capsys, fails):
    import io
    import logging
    import runpy
    import sys

    import xrd_preprocessing

    worker = runpy.run_path("src/bremen/api/aramina_preprocess_worker.py")
    monkeypatch.setattr("importlib.metadata.version", lambda name: "0.1.7b0")
    frame = pd.DataFrame([{"patientId": "p1", "side": "left", "age": None,
                           "radial_profile_data": [1., 2.], "q_range": [2., 23.]}])
    pipeline = MagicMock()
    pipeline.fit_transform.side_effect = ValueError("private-source") if fails else None
    pipeline.fit_transform.return_value = frame
    monkeypatch.setattr(xrd_preprocessing, "build_pipeline_from_config", lambda *a, **k: pipeline, raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({
        "h5": "private-source", "config_yaml": "xrd_preprocessing: {release_tag: v0.1.7-beta}",
    })))
    disabled = logging.root.manager.disable
    try:
        if fails:
            with pytest.raises(SystemExit):
                worker["main"]()
        else:
            worker["main"]()
    finally:
        logging.disable(disabled)
    out = capsys.readouterr().out
    assert "private-source" not in out
    payload = json.loads(out)
    if fails:
        assert payload == {"error": "ARAMINA_PREPROCESSING_FAILED", "diagnostic": {
            "stage": "worker_pipeline_execution", "exception_class": "ValueError", "transformer": "redacted",
        }}
    else:
        assert payload["rows"][0]["radial_profile_data"] == [1., 2.]


@pytest.mark.parametrize("missing,code,stage", [
    ("final_column", "ARAMINA_UNSUPPORTED_INPUT", "final_dataframe_contract"),
    ("threshold", "ARAMINA_EXECUTION_FAILED", None),
])
def test_no_missing_feature_or_threshold_fallback(tmp_path, source, missing, code, stage):
    pkg = _package()
    info = pkg["models"]["selected_model"]
    if missing == "final_column":
        info["feature_columns"].append("unknown_feature")
    else:
        del info["thresholds"]["threshold_target"]
    result = _execute(_entry(tmp_path, pkg), source)
    assert result.error == code
    assert result.failure_stage == stage
    assert result.payload is None


@pytest.mark.parametrize("update,reason,field", [
    ({"patient_id": ""}, "ARAMINA_INVALID_REQUEST", "patient_id"),
    ({"target_side": "invalid-private-side"}, "ARAMINA_INVALID_REQUEST", "target_side"),
    ({"analysis_author": None}, "ARAMINA_INVALID_REQUEST", "analysis_author"),
    ({"prediction_comment": None}, "ARAMINA_INVALID_REQUEST", "prediction_comment"),
    ({"source_id": {"private": "secret"}}, "INVALID_REQUEST_SCHEMA", "source_id"),
    ({"upload_id": "private-upload"}, "AMBIGUOUS_SOURCE", "upload_id"),
])
def test_job_rejection_logs_reason_without_values(monkeypatch, caplog, update, reason, field):
    monkeypatch.delenv("BREMEN_ARAMINA_DEBUG_TRACE", raising=False)
    body = _valid_aramina_body(patient_id="private-patient", analysis_author="private-author")
    body.update(update)
    response = _fastapi_client().post("/demo/api/jobs", json=body)
    assert response.status_code == 400
    records = [r for r in caplog.records if r.getMessage().startswith("runtime.job_request.rejected")]
    assert len(records) == 1
    text = records[0].getMessage()
    assert f"reason={reason}" in text
    assert field in text.split("invalid_fields=")[1]
    assert records[0].exc_info is None
    for private in ("private-patient", "private-author", "private-upload", "invalid-private-side", "secret"):
        assert private not in text


@pytest.mark.parametrize("body", [b"", b"not-json"])
def test_invalid_json_has_safe_rejection_log(caplog, body):
    assert _fastapi_client().post("/demo/api/jobs", content=body).status_code == 400
    assert "reason=INVALID_JSON" in caplog.text


def test_source_resolution_rejection_has_stage(monkeypatch, caplog):
    monkeypatch.setattr(jobs, "resolve_source", MagicMock(side_effect=ValueError("private-source-path")))
    response = _fastapi_client().post("/demo/api/jobs", json=_valid_aramina_body())
    assert response.status_code == 400
    assert response.json()["error_code"] == "SOURCE_ERROR"
    assert "stage=source_resolution" in caplog.text
    assert "reason=SOURCE_ERROR" in caplog.text
    assert "private-source-path" not in caplog.text


def test_rejection_logger_allowlist_and_failure_isolation(monkeypatch, caplog):
    from bremen.api.fastapi_app import _log_job_rejection
    _log_job_rejection("private-reason", ["private-field", "patient_id"], "private-stage")
    assert "private-" not in caplog.text
    assert "invalid_fields=patient_id" in caplog.text
    monkeypatch.setattr("logging.Logger.warning", MagicMock(side_effect=RuntimeError("private")))
    _log_job_rejection("INVALID_JSON")



def test_worker_diagnostic_log_is_safe_and_always_enabled(monkeypatch, caplog):
    from bremen.api.aramina_preprocessing import _log_preprocessing_rejection
    monkeypatch.delenv("BREMEN_ARAMINA_DEBUG_TRACE", raising=False)
    _log_preprocessing_rejection({"stage": "worker_pipeline_execution",
                                 "exception_class": "ValueError", "transformer": "SNRFilter"})
    assert "transformer=SNRFilter" in caplog.text
    assert "exception_class=ValueError" in caplog.text
    _log_preprocessing_rejection({"stage": ["private"], "exception_class": "private-path",
                                 "transformer": "private-patient"})
    assert "private" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_runtime_failure_stage_logged_without_debug(monkeypatch, caplog):
    from bremen.api.workflow_aramina import _debug_stage
    monkeypatch.delenv("BREMEN_ARAMINA_DEBUG_TRACE", raising=False)
    with pytest.raises(ValueError), _debug_stage("target_qc"):
        raise ValueError("private-source")
    assert "aramina.runtime.rejected" in caplog.text
    assert '"stage": "target_qc"' in caplog.text
    assert "private-source" not in caplog.text
    assert _trace_records(caplog) == []


@pytest.fixture(params=["fastapi", "legacy"])
def submit_api(request, monkeypatch):
    """Exercise both supported POST transports with identical request bodies."""
    def submit(body):
        if request.param == "fastapi":
            response = _fastapi_client().post("/demo/api/jobs", json=body)
            return response.status_code, response.json()
        monkeypatch.setattr(jobs, "_read_json_body", lambda handler: body)
        sent = MagicMock()
        monkeypatch.setattr(jobs, "_send_json", sent)
        jobs.handle_jobs_create(MagicMock())
        return sent.call_args.args[1:]
    return submit


@pytest.mark.parametrize("patient,side,missing", [
    (None, None, ["patient_id", "target_side"]),
    ("  ", "left", ["patient_id"]),
    ("p1", "", ["target_side"]),
    ("p1", "private-invalid-side", []),
])
def test_api_validation_details_before_job(submit_api, monkeypatch, patient, side, missing):
    create = MagicMock()
    resolve = MagicMock()
    monkeypatch.setattr(jobs, "create_analysis_job", create)
    monkeypatch.setattr(jobs, "resolve_source", resolve)
    status, data = submit_api(_valid_aramina_body(patient_id=patient, target_side=side))
    assert status == 400
    assert data["error_code"] == "ARAMINA_INVALID_REQUEST"
    assert data["missing_required_fields"] == missing
    assert data["allowed_target_side"] == ["left", "right"]
    assert data["required_fields"] == ["source_id", "model_id", "workflow_id", "patient_id", "target_side"]
    assert "/demo/api/h5/containers" in data["remediation"]
    assert data["technical_demo_only"] is True
    assert "private-invalid-side" not in json.dumps(data)
    create.assert_not_called()
    resolve.assert_not_called()


@pytest.mark.parametrize("state", ["unknown", "consumed", "expired"])
def test_api_source_unavailable_reason(submit_api, monkeypatch, state):
    from bremen.api import source_registry as sources
    monkeypatch.setenv("BREMEN_DEMO_H5_BUCKET", "private-bucket")
    monkeypatch.setenv("BREMEN_DEMO_H5_PREFIX", "")
    sid = sources.register_source("private-bucket", "private-key.h5", "sample.h5", 10, "")
    if state == "unknown":
        sources._registry.pop(sid)
    elif state == "consumed":
        sources._registry[sid].consumed = True
    else:
        sources._registry[sid].created_at = "2000-01-01T00:00:00+00:00"
    create = MagicMock()
    monkeypatch.setattr(jobs, "create_analysis_job", create)
    try:
        status, data = submit_api(_valid_aramina_body(source_id=sid))
        assert status == 400
        assert data["error_code"] == "SOURCE_ERROR"
        assert data["reason_code"] == "SOURCE_ID_NOT_AVAILABLE"
        assert "fresh source_id" in data["remediation"]
        assert "private-" not in json.dumps(data)
        create.assert_not_called()
    finally:
        sources._registry.pop(sid, None)


def test_api_patient_mismatch_before_creation(submit_api, monkeypatch, source):
    with h5py.File(source[0], "a") as f:
        f["session/sample/patient_name"] = "Nova_257"
    monkeypatch.setattr(jobs, "resolve_source", lambda *args: source[0])
    create = MagicMock()
    monkeypatch.setattr(jobs, "create_analysis_job", create)
    status, data = submit_api(_valid_aramina_body(patient_id="Nova_214"))
    assert status == 400
    assert data["error_code"] == "ARAMINA_PATIENT_MISMATCH"
    assert data["requested_patient_id"] == "Nova_214"
    assert data["resolved_patient_display_name"] == "Nova_257"
    assert source[0] not in json.dumps(data)
    create.assert_not_called()
    assert not jobs._jobs


@pytest.mark.parametrize("version", ["0.2.12-beta", "0.2.13-beta"])
def test_api_matching_patient_preserves_success(submit_api, monkeypatch, tmp_path, source, version):
    entry = _entry(tmp_path, model_version=version)
    _install(entry)
    with h5py.File(source[0], "a") as f:
        f["session/sample/patient_name"] = "p1"
    monkeypatch.setattr(jobs, "resolve_source", lambda *args: source[0])
    status, data = submit_api(_valid_aramina_body(patient_id="p1"))
    assert status == 201
    assert data["job"]["overall_status"] == "completed"
    run = data["job"]["workflow_runs"]["aramina"]
    assert run["model_identity"]["model_version"] == version
    assert "failure_detail" not in run
    assert data["job"]["reports"]["aramina"]["status"] == "available"


def test_api_unsupported_input_safe_detail(submit_api, monkeypatch, tmp_path, source):
    _install(_entry(tmp_path, model_version="0.2.13-beta"))
    monkeypatch.setattr(jobs, "resolve_source", lambda *args: source[0])
    # The real runtime rejects the absent requested patient; no inference result stub.
    status, data = submit_api(_valid_aramina_body(patient_id="absent-patient"))
    assert status == 201
    job = data["job"]
    run = job["workflow_runs"]["aramina"]
    assert run["failure"] == "ARAMINA_UNSUPPORTED_INPUT"
    # PR0141: the exact safe boundary, not a generic input_contract label.
    assert run["failure_stage"] == "h5_patient_contract"
    assert run["failure_reason_code"] == "ARAMINA_UNSUPPORTED_INPUT_H5_PATIENT_CONTRACT"
    assert run["failure_detail"]
    assert run["remediation"]
    assert run["safe_details"]["target_side"] == "left"
    assert run["safe_details"]["model_version"] == "0.2.13-beta"
    assert run["safe_details"]["requested_patient_id"] == "absent-patient"
    assert job["reports"]["aramina"]["status"] == "unavailable"
    assert jobs.get_analysis_job(job["job_id"]).to_dict()["workflow_runs"]["aramina"] == run
    for private in (source[0], "_package", "Traceback", "checksum"):
        assert private not in json.dumps(job)


@pytest.mark.parametrize("error", [ValueError("s3://private-bucket/token"), RuntimeError("/tmp/private-key")])
def test_api_aramina_exception_text_never_public(submit_api, monkeypatch, error):
    monkeypatch.setattr(jobs, "resolve_source", MagicMock(side_effect=error))
    status, data = submit_api(_valid_aramina_body())
    assert status in {400, 500}
    assert "private" not in json.dumps(data)
    assert "reason_code" not in data  # Not every source failure is a stale handle.


def test_api_bremen_source_error_unchanged(submit_api, monkeypatch):
    from bremen.api.source_registry import SourceUnavailableError
    monkeypatch.setattr(jobs, "resolve_source", MagicMock(side_effect=SourceUnavailableError("Existing safe message")))
    status, data = submit_api({"workflow_id": "bremen", "source_id": "missing"})
    assert status == 400
    assert data == {"error": "Existing safe message", "error_code": "SOURCE_ERROR"}


def test_api_diagnostic_helpers_redact_unsafe_metadata():
    from bremen.api.aramina_api_errors import (
        is_aramina_selection,
        patient_mismatch_details,
        unsupported_input_details,
    )
    assert not is_aramina_selection([])
    assert patient_mismatch_details("p1", "") is None
    assert patient_mismatch_details(" p1 ", "p1") is None
    mismatch = patient_mismatch_details("s3://private/key", "p1")
    assert mismatch["requested_patient_id"] == "redacted"
    details = unsupported_input_details("/tmp/private", "private-side", "private/version")
    assert "private" not in json.dumps(details)


def test_schema_error_uses_catalog_routing_without_leaks(tmp_path):
    _install(_entry(tmp_path))
    body = _valid_aramina_body(workflow_id="bremen", patient_id={"secret": "token-value"})
    response = _fastapi_client().post("/demo/api/jobs", json=body)
    assert response.status_code == 400
    assert response.json()["error_code"] == "ARAMINA_INVALID_REQUEST"
    assert "token-value" not in response.text


# ===================================================================
# PR0141 — Aramina target-side compatibility diagnostics
# ===================================================================


def _stage_of(result):
    """Return the public failure stage for a failed workflow result."""
    return result.failure_stage


def test_pr0141_target_side_required_and_not_inferred(tmp_path, source):
    """target_side is explicit request input and is never inferred."""
    provider = AraminaWorkflowProvider(entry=_entry(tmp_path))
    # No request at all -> invalid request, not an inferred side.
    assert provider.execute(source[1], h5_path=source[0]).error == "ARAMINA_INVALID_REQUEST"
    # Blank side -> invalid request.
    assert _execute(_entry(tmp_path), source, _request(target_side="")).error == "ARAMINA_INVALID_REQUEST"
    # The fixture contains both sides, so both explicit sides are honored
    # verbatim. The requested side is echoed, never replaced by the other.
    for side in ("left", "right"):
        result = _execute(_entry(tmp_path), source, _request(target_side=side))
        assert result.status == "completed"
        assert result.payload["external_report"]["target_side"] == side


def test_pr0141_target_side_not_inferred_from_canonical(tmp_path, source, monkeypatch):
    """A side absent from preprocessing fails instead of falling back."""
    import pandas as _pd

    # Only the contralateral side is available; the requested side is absent.
    frame = _pd.DataFrame([{
        "patientId": "p1", "side": "right", "age": None,
        "radial_profile_data": [1.0, 2.0, 3.0], "q_range": [2.0, 3.0, 4.0],
    }])
    monkeypatch.setattr("bremen.api.aramina_preprocessing.preprocess_aramina", lambda *a: frame)
    result = _execute(_entry(tmp_path), source, _request(target_side="left"))
    assert result.error == "ARAMINA_UNSUPPORTED_INPUT"
    assert result.failure_stage == "target_side_contract"
    assert result.payload is None


@pytest.mark.parametrize("side", ["left", "right", "LEFT", " Right "])
def test_pr0141_only_left_right_accepted(tmp_path, source, side):
    """Only left/right are accepted; case and whitespace are normalized."""
    payload = _build_aramina_request_json(patient_id="p1", target_side=side)
    assert payload["target_side"] in {"left", "right"}


@pytest.mark.parametrize("side", ["anterior", "l", "both", "left,right", "0"])
def test_pr0141_invalid_sides_rejected(tmp_path, source, side):
    """Non left/right values are rejected before any artifact load."""
    loader = MagicMock(side_effect=AssertionError("must not load"))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("joblib.load", loader)
        result = _execute(_entry(tmp_path), source, _request(target_side=side))
    assert result.error == "ARAMINA_INVALID_REQUEST"
    loader.assert_not_called()


@pytest.mark.parametrize("version", ["0.2.12-beta", "0.2.13-beta"])
def test_pr0141_known_good_versions_still_complete(tmp_path, source, version):
    """Both released model versions still complete on a compatible fixture."""
    entry = _entry(tmp_path, model_version=version)
    result = _execute(entry, source)
    assert result.status == "completed"
    assert result.payload["model_version"] == version
    assert result.failure_stage is None


def test_pr0141_preprocessing_failure_maps_to_preprocessing_contract(tmp_path, source, monkeypatch):
    """A preprocessing worker failure maps to preprocessing_contract."""
    def boom(h5_path, config_yaml):
        raise ValueError("Aramina preprocessing failed")

    monkeypatch.setattr("bremen.api.aramina_preprocessing.preprocess_aramina", boom)
    result = _execute(_entry(tmp_path), source)
    assert result.error == "ARAMINA_UNSUPPORTED_INPUT"
    assert result.failure_stage == "preprocessing_contract"


def test_pr0141_preprocessing_failure_leaks_nothing(tmp_path, source, monkeypatch):
    """Preprocessing diagnostics never leak stderr/stdout/path/raw exception."""
    secret = "s3://private-bucket/key /tmp/private token=secret"

    def boom(h5_path, config_yaml):
        raise RuntimeError(secret)

    monkeypatch.setattr("bremen.api.aramina_preprocessing.preprocess_aramina", boom)
    entry = _entry(tmp_path)
    _install(entry)
    job = jobs.create_analysis_job(
        model_id=entry.model_id, h5_path=source[0], aramina_request=_request(),
    )
    run = job.workflow_runs["aramina"]
    assert run.failure == "ARAMINA_UNSUPPORTED_INPUT"
    assert run.failure_details["failure_stage"] == "preprocessing_contract"
    public = json.dumps([job.to_dict(), jobs.get_job_events(job.job_id)])
    for forbidden in (secret, "private-bucket", "/tmp/", "token=", "RuntimeError", "Traceback"):
        assert forbidden not in public


def test_pr0141_missing_patient_maps_to_h5_patient_contract(tmp_path, source):
    """A patient absent from the staged H5 maps to h5_patient_contract."""
    result = _execute(_entry(tmp_path), source, _request(patient_id="absent-patient"))
    assert result.error == "ARAMINA_UNSUPPORTED_INPUT"
    assert result.failure_stage == "h5_patient_contract"


def test_pr0141_missing_target_side_maps_to_target_side_contract(tmp_path, source, monkeypatch):
    """A side with no usable measurements maps to target_side_contract."""
    import pandas as _pd

    # Preprocessing returns only the contralateral side for the requested side.
    frame = _pd.DataFrame([{
        "patientId": "p1", "side": "right", "age": None,
        "radial_profile_data": [1.0, 2.0, 3.0], "q_range": [2.0, 3.0, 4.0],
    }])
    monkeypatch.setattr("bremen.api.aramina_preprocessing.preprocess_aramina", lambda *a: frame)
    result = _execute(_entry(tmp_path), source, _request(target_side="left"))
    assert result.error == "ARAMINA_UNSUPPORTED_INPUT"
    assert result.failure_stage == "target_side_contract"


def test_pr0141_target_qc_flags_map_to_target_side_contract(tmp_path, source):
    """QC-flagged target measurements map to target_side_contract."""
    from dataclasses import replace as _replace

    canonical = source[1]
    flagged = tuple(
        _replace(m, qc_flags=("LOW_SNR",)) if m.side == "LEFT" else m
        for m in canonical.measurements
    )
    flagged_source = (source[0], _replace(canonical, measurements=flagged))
    result = _execute(_entry(tmp_path), flagged_source)
    assert result.error == "ARAMINA_UNSUPPORTED_INPUT"
    assert result.failure_stage == "target_side_contract"


@pytest.mark.parametrize("bad", ["empty", "nonfinite", "ragged"])
def test_pr0141_bad_profile_matrix_maps_to_profile_matrix_contract(
    tmp_path, source, monkeypatch, bad,
):
    """Empty/non-finite/ragged profile matrices map to profile_matrix_contract."""
    import pandas as _pd

    if bad == "empty":
        # Patient matches, but the target-side profile is empty.
        frame = _pd.DataFrame([{
            "patientId": "p1", "side": "left", "age": None,
            "radial_profile_data": [], "q_range": [],
        }])
    elif bad == "nonfinite":
        frame = _pd.DataFrame([{
            "patientId": "p1", "side": "left", "age": None,
            "radial_profile_data": [1.0, float("nan"), 3.0], "q_range": [2.0, 3.0, 4.0],
        }])
    else:
        frame = _pd.DataFrame([
            {"patientId": "p1", "side": "left", "age": None,
             "radial_profile_data": [1.0, 2.0], "q_range": [2.0, 3.0]},
            {"patientId": "p1", "side": "left", "age": None,
             "radial_profile_data": [1.0, 2.0, 3.0], "q_range": [2.0, 3.0, 4.0]},
        ])
    monkeypatch.setattr("bremen.api.aramina_preprocessing.preprocess_aramina", lambda *a: frame)
    result = _execute(_entry(tmp_path), source)
    assert result.error == "ARAMINA_UNSUPPORTED_INPUT"
    assert result.failure_stage == "profile_matrix_contract"


def test_pr0141_lr1_failure_maps_to_lr1_contract(tmp_path, source, monkeypatch):
    """An LR1 scorer failure maps to lr1_contract."""
    pkg = _package()
    bad = MagicMock()
    bad.predict_proba = MagicMock(side_effect=ValueError("private lr1 detail"))
    pkg["models"]["selected_model"]["lr1_model"] = bad
    monkeypatch.setattr("bremen.api.workflow_aramina._load_selected_artifact", lambda entry: pkg)
    result = _execute(_entry(tmp_path), source)
    assert result.error == "ARAMINA_UNSUPPORTED_INPUT"
    assert result.failure_stage == "lr1_contract"


def test_pr0141_lr1_bad_output_maps_to_lr1_contract(tmp_path, source, monkeypatch):
    """An out-of-contract LR1 output maps to lr1_contract."""
    pkg = _package()
    bad = MagicMock()
    bad.predict_proba = MagicMock(return_value=np.array([[float("nan"), 0.5]]))
    pkg["models"]["selected_model"]["lr1_model"] = bad
    monkeypatch.setattr("bremen.api.workflow_aramina._load_selected_artifact", lambda entry: pkg)
    result = _execute(_entry(tmp_path), source)
    assert result.error == "ARAMINA_UNSUPPORTED_INPUT"
    assert result.failure_stage == "lr1_contract"


def test_pr0141_symmetry_failure_maps_to_symmetry_contract(tmp_path, source, monkeypatch):
    """A symmetry feature failure maps to symmetry_contract."""
    def boom(*args, **kwargs):
        raise ValueError("private symmetry detail")

    monkeypatch.setattr("bremen.api.aramina_symmetry.symmetry_features", boom)
    result = _execute(_entry(tmp_path), source)
    assert result.error == "ARAMINA_UNSUPPORTED_INPUT"
    assert result.failure_stage == "symmetry_contract"


def test_pr0141_final_dataframe_failure_maps_to_final_dataframe_contract(tmp_path, source):
    """A missing declared feature column maps to final_dataframe_contract."""
    pkg = _package()
    pkg["models"]["selected_model"]["feature_columns"].append("unknown_feature")
    result = _execute(_entry(tmp_path, pkg), source)
    assert result.error == "ARAMINA_UNSUPPORTED_INPUT"
    assert result.failure_stage == "final_dataframe_contract"


def test_pr0141_final_model_failure_maps_to_final_model_contract(tmp_path, source, monkeypatch):
    """A final scorer failure maps to final_model_contract."""
    pkg = _package()
    bad = MagicMock()
    bad.predict_proba = MagicMock(side_effect=ValueError("private final detail"))
    pkg["models"]["selected_model"]["final_model"] = bad
    monkeypatch.setattr("bremen.api.workflow_aramina._load_selected_artifact", lambda entry: pkg)
    result = _execute(_entry(tmp_path), source)
    assert result.error == "ARAMINA_UNSUPPORTED_INPUT"
    assert result.failure_stage == "final_model_contract"


def test_pr0141_final_model_bad_output_maps_to_final_model_contract(tmp_path, source, monkeypatch):
    """An out-of-contract final output maps to final_model_contract."""
    pkg = _package()
    bad = MagicMock()
    bad.predict_proba = MagicMock(return_value=np.array([[0.5, 2.0]]))
    pkg["models"]["selected_model"]["final_model"] = bad
    monkeypatch.setattr("bremen.api.workflow_aramina._load_selected_artifact", lambda entry: pkg)
    result = _execute(_entry(tmp_path), source)
    assert result.error == "ARAMINA_UNSUPPORTED_INPUT"
    assert result.failure_stage == "final_model_contract"


def test_pr0141_unknown_stage_collapses_to_unknown_input_contract():
    """Any non-allowlisted stage collapses to unknown_input_contract."""
    from bremen.api.aramina_api_errors import unsupported_input_details
    from bremen.api.workflow_aramina import FAILURE_STAGES

    assert "input_contract" not in FAILURE_STAGES
    details = unsupported_input_details("p1", "left", "0.2.12-beta", stage="input_contract")
    assert details["failure_stage"] == "unknown_input_contract"
    details = unsupported_input_details("p1", "left", "0.2.12-beta", stage=None)
    assert details["failure_stage"] == "unknown_input_contract"
    details = unsupported_input_details("p1", "left", "0.2.12-beta", stage="private-stage")
    assert details["failure_stage"] == "unknown_input_contract"


@pytest.mark.parametrize("stage", sorted([
    "preprocessing_contract", "h5_patient_contract", "target_side_contract",
    "profile_matrix_contract", "lr1_contract", "symmetry_contract",
    "final_dataframe_contract", "final_model_contract", "report_contract",
    "unknown_input_contract",
]))
def test_pr0141_every_stage_has_detail_and_remediation(stage):
    """Every allowlisted stage has fixed public detail and remediation text."""
    from bremen.api.aramina_api_errors import unsupported_input_details

    details = unsupported_input_details("p1", "left", "0.2.12-beta", stage=stage)
    assert details["failure_stage"] == stage
    assert details["failure_reason_code"] == f"ARAMINA_UNSUPPORTED_INPUT_{stage.upper()}"
    assert details["failure_detail"]
    assert details["remediation"]
    assert details["safe_details"]["target_side"] == "left"


def test_pr0141_safe_details_allowlist_and_redaction():
    """safe_details exposes only sanitized, allowlisted values."""
    from bremen.api.aramina_api_errors import unsupported_input_details

    details = unsupported_input_details(
        "Nova_379", "left", "0.2.12-beta",
        stage="target_side_contract",
        model_id="aramina-target-breast-risk",
        requested_patient_id="Nova_379",
        resolved_container_id="Nova_379.h5",
        available_sides=["left", "right", "private-side"],
        measurement_count=3,
        preprocessing_release="v0.1.7-beta",
    )
    safe = details["safe_details"]
    assert safe["patient_display_name"] == "Nova_379"
    assert safe["requested_patient_id"] == "Nova_379"
    assert safe["target_side"] == "left"
    assert safe["model_id"] == "aramina-target-breast-risk"
    assert safe["model_version"] == "0.2.12-beta"
    assert safe["resolved_container_id"] == "Nova_379.h5"
    assert safe["available_sides"] == ["left", "right"]
    assert safe["measurement_count"] == 3
    assert safe["preprocessing_release"] == "v0.1.7-beta"


def test_pr0141_safe_details_reject_unsafe_values():
    """Unsafe identifiers, paths, releases and counts are dropped or redacted."""
    from bremen.api.aramina_api_errors import unsupported_input_details

    details = unsupported_input_details(
        "/tmp/private", "private-side", "private/version",
        stage="target_side_contract",
        model_id="s3://bucket/key",
        requested_patient_id="/home/private",
        resolved_container_id="s3://private-bucket/key.h5",
        available_sides=["private-side", 7],
        measurement_count=-1,
        preprocessing_release="v9.9.9-private",
    )
    safe = details["safe_details"]
    assert safe["patient_display_name"] == "redacted"
    assert safe["requested_patient_id"] == "redacted"
    assert safe["target_side"] == ""
    assert safe["model_id"] == "redacted"
    assert safe["model_version"] == "redacted"
    assert "resolved_container_id" not in safe
    assert "available_sides" not in safe
    assert "measurement_count" not in safe
    assert "preprocessing_release" not in safe
    assert "private" not in json.dumps(details)


def test_pr0141_optional_safe_details_omitted_when_unknown():
    """Unknown optional fields are omitted, not emitted as empty guesses."""
    from bremen.api.aramina_api_errors import unsupported_input_details

    safe = unsupported_input_details("p1", "left", "0.2.12-beta")["safe_details"]
    for optional in ("resolved_container_id", "available_sides",
                     "measurement_count", "preprocessing_release"):
        assert optional not in safe


def test_pr0141_preprocessing_release_tag_allowlist():
    """Only the two released preprocessing tags are reported."""
    from bremen.api.aramina_preprocessing import preprocessing_release_tag

    assert preprocessing_release_tag("xrd_preprocessing: {release_tag: v0.1.7-beta}") == "v0.1.7-beta"
    assert preprocessing_release_tag("xrd_preprocessing: {release_tag: v0.1.9-beta}") == "v0.1.9-beta"
    assert preprocessing_release_tag("xrd_preprocessing: {release_tag: v9.9.9}") == ""
    assert preprocessing_release_tag("not: [valid") == ""
    assert preprocessing_release_tag("{}") == ""


# ---- Rerun / duplicate guard ----


def _completed_aramina_job(tmp_path, source, monkeypatch, side, model_id="aramina-a"):
    """Create a completed Aramina job with an available report."""
    entry = _entry(tmp_path, model_id=model_id)
    _install(entry)
    monkeypatch.setattr(jobs, "resolve_source", lambda *args: source[0])
    body = _valid_aramina_body(model_id=model_id, patient_id="p1", target_side=side)
    monkeypatch.setattr(jobs, "_read_json_body", lambda handler: body)
    sent = MagicMock()
    monkeypatch.setattr(jobs, "_send_json", sent)
    jobs.handle_jobs_create(MagicMock())
    return sent


def test_pr0141_aramina_duplicate_guard_includes_target_side(tmp_path, source, monkeypatch):
    """A completed left run must not block a right run for the same source/model."""
    first = _completed_aramina_job(tmp_path, source, monkeypatch, "left")
    assert first.call_args.args[1] == 201
    job = jobs.get_analysis_job(first.call_args.args[2]["job"]["job_id"])
    assert job.overall_status == "completed"
    assert job.reports["aramina"].status == "available"
    assert job.input_summary["target_side"] == "left"

    # Same source + model, opposite side -> must NOT be blocked.
    second = _completed_aramina_job(tmp_path, source, monkeypatch, "right")
    assert second.call_args.args[1] == 201


def test_pr0141_aramina_duplicate_guard_blocks_same_side(tmp_path, source, monkeypatch):
    """A completed left run still blocks an identical left run."""
    _completed_aramina_job(tmp_path, source, monkeypatch, "left")
    second = _completed_aramina_job(tmp_path, source, monkeypatch, "left")
    assert second.call_args.args[1] == 409
    payload = second.call_args.args[2]
    assert payload["error"] == "report_already_exists"
    assert payload["existing_target_side"] == "left"
    assert payload["requested_target_side"] == "left"


def test_pr0141_aramina_duplicate_guard_side_aware_409_fields(tmp_path, source, monkeypatch):
    """The 409 carries explicit side fields for client disambiguation."""
    _completed_aramina_job(tmp_path, source, monkeypatch, "left")
    second = _completed_aramina_job(tmp_path, source, monkeypatch, "left")
    payload = second.call_args.args[2]
    assert set(payload) >= {
        "status", "error", "message", "job_id", "workflow_id",
        "existing_target_side", "requested_target_side",
    }


def test_pr0141_find_existing_completed_report_signature():
    """The guard accepts target_side and defaults to side-agnostic matching."""
    import inspect
    from bremen.api.job_api_handler import _find_existing_completed_report

    sig = inspect.signature(_find_existing_completed_report)
    assert "target_side" in sig.parameters
    assert sig.parameters["target_side"].default == ""


def test_pr0141_bremen_duplicate_guard_unchanged(tmp_path, source, monkeypatch):
    """Bremen duplicate identity is still source + workflow + model only."""
    from bremen.api.job_api_handler import _find_existing_completed_report

    from bremen.api.job_models import AnalysisJob, ReportMetadata, WorkflowRun
    from bremen.api.report_provider import REPORT_STATUS_AVAILABLE

    job = AnalysisJob(
        job_id="bremen-job", request_id="req", created_at="now",
        overall_status="completed",
        input_summary={
            "source_key": "stable-key", "model_id": "bremen-a",
            "workflow_id": "bremen", "target_side": "",
        },
        requested_workflows=("bremen",),
        workflow_runs={"bremen": WorkflowRun(workflow_id="bremen", status="completed")},
        reports={"bremen": ReportMetadata(
            report_id="r", workflow_id="bremen", report_schema_version="v0.1",
            status=REPORT_STATUS_AVAILABLE,
        )},
    )
    jobs._jobs[job.job_id] = job
    # Side-agnostic lookup still finds the Bremen job (unchanged behavior).
    assert _find_existing_completed_report("stable-key", "bremen", "bremen-a") is not None
    # A requested side must not accidentally match a Bremen job.
    assert _find_existing_completed_report("stable-key", "bremen", "bremen-a", "left") is None


def test_pr0141_bremen_job_summary_has_empty_target_side():
    """Bremen job summaries expose an empty target_side, not a guessed side."""
    from bremen.api.job_models import AnalysisJob

    job = AnalysisJob(
        job_id="bremen-job", request_id="req", created_at="now",
        overall_status="completed",
        input_summary={
            "source_key": "stable-key", "model_id": "bremen-a",
            "workflow_id": "bremen", "patient_display_name": "p1",
        },
        requested_workflows=("bremen",),
    )
    jobs._jobs[job.job_id] = job
    summaries = jobs.list_analysis_jobs(model_id="bremen-a")
    assert summaries
    assert summaries[0]["target_side"] == ""


def test_pr0141_aramina_job_summary_exposes_target_side(tmp_path, source, monkeypatch):
    """Aramina job summaries expose the requested side."""
    sent = _completed_aramina_job(tmp_path, source, monkeypatch, "right")
    job_id = sent.call_args.args[2]["job"]["job_id"]
    summaries = jobs.list_analysis_jobs(model_id="aramina-a")
    match = [s for s in summaries if s["job_id"] == job_id]
    assert match and match[0]["target_side"] == "right"


def test_pr0141_public_failure_payload_leaks_nothing(tmp_path, source, monkeypatch):
    """The full public failure payload contains no forbidden values."""
    secret = "s3://private-bucket/secret-key /tmp/private token=secret"
    pkg = _package()
    bad = MagicMock()
    bad.predict_proba = MagicMock(side_effect=RuntimeError(secret))
    pkg["models"]["selected_model"]["lr1_model"] = bad
    entry = _entry(tmp_path)
    _install(entry)
    monkeypatch.setattr("bremen.api.workflow_aramina._load_selected_artifact", lambda e: pkg)
    job = jobs.create_analysis_job(
        model_id=entry.model_id, h5_path=source[0], aramina_request=_request(),
    )
    run = job.workflow_runs["aramina"]
    assert run.failure == "ARAMINA_UNSUPPORTED_INPUT"
    assert run.failure_details["failure_stage"] == "lr1_contract"
    public = json.dumps([
        job.to_dict(),
        jobs.get_job_events(job.job_id),
        jobs.get_job_reports(job.job_id),
        jobs.list_analysis_jobs(model_id=entry.model_id),
    ])
    for forbidden in (
        secret, "private-bucket", "secret-key", "/tmp/", "token=",
        "Traceback", "RuntimeError", entry._artifact_path, entry._checksum,
        "_package", "provider_url",
    ):
        assert forbidden not in public


def test_pr0141_failure_stage_absent_on_success(tmp_path, source):
    """Successful runs do not acquire failure fields."""
    result = _execute(_entry(tmp_path), source)
    assert result.status == "completed"
    assert result.failure_stage is None


def test_pr0141_failure_stage_absent_for_non_input_failures(tmp_path, source):
    """Non-input failures keep their existing code and carry no stage."""
    pkg = _package()
    del pkg["kind"]
    result = _execute(_entry(tmp_path, pkg), source)
    assert result.error == "ARAMINA_UNSUPPORTED_ARTIFACT"
    assert result.failure_stage is None


# ===================================================================
# PR0142 — Aramina preprocessing root-cause diagnostics
# ===================================================================


def _worker_failure(stdout: str, returncode: int = 1):
    """Build a fake completed worker process result."""
    import subprocess

    return subprocess.CompletedProcess([], returncode, stdout, "private stderr")


def _run_preprocessing_with_worker(monkeypatch, stdout, returncode=1):
    """Run the real preprocess_aramina against a fake worker process.

    The autouse ``synthetic_preprocessing`` fixture replaces the module-level
    ``preprocess_aramina`` attribute, so the real implementation is recovered
    from the module source. Returns the raised exception's allowlisted
    diagnostic, or ``None`` when no exception was raised.
    """
    import bremen.api.aramina_preprocessing as preprocessing

    namespace: dict = {
        "__file__": preprocessing.__file__,
        "__name__": "bremen.api._pr0142_real",
        "__package__": "bremen.api",
    }
    source = Path(preprocessing.__file__).read_text(encoding="utf-8")
    exec(compile(source, preprocessing.__file__, "exec"), namespace)  # noqa: S102

    monkeypatch.setattr(
        preprocessing.subprocess, "run",
        MagicMock(return_value=_worker_failure(stdout, returncode)),
    )
    config = "xrd_preprocessing: {release_tag: v0.1.7-beta}\npipeline: {steps: [raw]}"
    try:
        namespace["preprocess_aramina"]("private-input", config)
    except Exception as exc:  # noqa: BLE001 -- test helper
        return getattr(exc, "diagnostic", None)
    return None


@pytest.mark.parametrize("stage,reason", [
    ("worker_imports", "ARAMINA_PREPROCESSING_WORKER_IMPORTS_FAILED"),
    ("worker_config", "ARAMINA_PREPROCESSING_CONFIG_FAILED"),
    ("worker_pipeline_build", "ARAMINA_PREPROCESSING_PIPELINE_BUILD_FAILED"),
    ("worker_pipeline_execution", "ARAMINA_PREPROCESSING_PIPELINE_EXECUTION_FAILED"),
    ("worker_output", "ARAMINA_PREPROCESSING_OUTPUT_FAILED"),
])
def test_pr0142_worker_failure_json_maps_to_subdiagnostic(monkeypatch, stage, reason):
    """A worker failure JSON maps to the allowlisted preprocessing subdiagnostic."""
    from bremen.api.aramina_preprocessing import AraminaPreprocessingError

    stdout = json.dumps({
        "error": "ARAMINA_PREPROCESSING_FAILED",
        "diagnostic": {
            "stage": stage, "exception_class": "ValueError",
            "transformer": "SNRFilter",
        },
    })
    diagnostic = _run_preprocessing_with_worker(monkeypatch, stdout)
    assert diagnostic is not None
    assert diagnostic["preprocessing_stage"] == stage
    assert diagnostic["preprocessing_reason_code"] == reason
    assert diagnostic["preprocessing_exception_class"] == "ValueError"
    assert diagnostic["preprocessing_transformer"] == "SNRFilter"
    assert diagnostic["preprocessing_release"] == "v0.1.7-beta"


def test_pr0142_empty_output_maps_to_empty_output_reason(monkeypatch):
    """A successful worker with no rows maps to worker_empty_output."""
    diagnostic = _run_preprocessing_with_worker(
        monkeypatch, json.dumps({"rows": []}), returncode=0,
    )
    assert diagnostic is not None
    assert diagnostic["preprocessing_stage"] == "worker_empty_output"
    assert diagnostic["preprocessing_reason_code"] == "ARAMINA_PREPROCESSING_EMPTY_OUTPUT"


def test_pr0142_unparseable_worker_output_maps_to_output_failed(monkeypatch):
    """Unparseable worker stdout maps to worker_output, not a raw error."""
    diagnostic = _run_preprocessing_with_worker(monkeypatch, "not-json", returncode=0)
    assert diagnostic is not None
    assert diagnostic["preprocessing_stage"] == "worker_output"
    assert diagnostic["preprocessing_reason_code"] == "ARAMINA_PREPROCESSING_OUTPUT_FAILED"


def test_pr0142_worker_spawn_failure_maps_to_process_failed(monkeypatch):
    """A missing interpreter or timeout maps to worker_process."""
    import bremen.api.aramina_preprocessing as preprocessing

    namespace: dict = {
        "__file__": preprocessing.__file__,
        "__name__": "bremen.api._pr0142_real",
        "__package__": "bremen.api",
    }
    source = Path(preprocessing.__file__).read_text(encoding="utf-8")
    exec(compile(source, preprocessing.__file__, "exec"), namespace)  # noqa: S102
    monkeypatch.setattr(
        preprocessing.subprocess, "run",
        MagicMock(side_effect=OSError("private interpreter path")),
    )
    config = "xrd_preprocessing: {release_tag: v0.1.7-beta}\npipeline: {steps: [raw]}"
    with pytest.raises(Exception) as excinfo:  # noqa: B017 -- test helper
        namespace["preprocess_aramina"]("private-input", config)
    diagnostic = excinfo.value.diagnostic
    assert diagnostic["preprocessing_stage"] == "worker_process"
    assert diagnostic["preprocessing_reason_code"] == "ARAMINA_PREPROCESSING_PROCESS_FAILED"
    assert "private" not in json.dumps(diagnostic)


@pytest.mark.parametrize("bad_stage", [
    "private-stage", "", None, 7, ["worker_imports"], "worker_unknown",
])
def test_pr0142_unknown_stage_collapses_to_worker_process(monkeypatch, bad_stage):
    """Any non-allowlisted stage collapses to worker_process."""
    from bremen.api.aramina_preprocessing import AraminaPreprocessingError

    stdout = json.dumps({
        "error": "ARAMINA_PREPROCESSING_FAILED",
        "diagnostic": {"stage": bad_stage, "exception_class": "ValueError",
                       "transformer": "SNRFilter"},
    })
    diagnostic = _run_preprocessing_with_worker(monkeypatch, stdout)
    assert diagnostic is not None
    assert diagnostic["preprocessing_stage"] == "worker_process"
    assert diagnostic["preprocessing_reason_code"] == "ARAMINA_PREPROCESSING_PROCESS_FAILED"
    assert "private" not in json.dumps(diagnostic)


@pytest.mark.parametrize("bad_class", [
    "PrivateError", "", None, 7, "s3://bucket/key", "ValueError ",
])
def test_pr0142_unknown_exception_class_redacted(monkeypatch, bad_class):
    """Any non-allowlisted exception class becomes redacted."""
    from bremen.api.aramina_preprocessing import AraminaPreprocessingError

    stdout = json.dumps({
        "error": "ARAMINA_PREPROCESSING_FAILED",
        "diagnostic": {"stage": "worker_pipeline_execution",
                       "exception_class": bad_class, "transformer": "SNRFilter"},
    })
    diagnostic = _run_preprocessing_with_worker(monkeypatch, stdout)
    assert diagnostic is not None
    assert diagnostic["preprocessing_exception_class"] == "redacted"


@pytest.mark.parametrize("bad_transformer", [
    "PrivateTransformer", "", None, 7, "/tmp/private.py", "SNRFilter ",
])
def test_pr0142_unknown_transformer_redacted(monkeypatch, bad_transformer):
    """Any non-allowlisted transformer becomes redacted."""
    from bremen.api.aramina_preprocessing import AraminaPreprocessingError

    stdout = json.dumps({
        "error": "ARAMINA_PREPROCESSING_FAILED",
        "diagnostic": {"stage": "worker_pipeline_execution",
                       "exception_class": "ValueError", "transformer": bad_transformer},
    })
    diagnostic = _run_preprocessing_with_worker(monkeypatch, stdout)
    assert diagnostic is not None
    assert diagnostic["preprocessing_transformer"] == "redacted"


def test_pr0142_allowlisted_transformer_preserved(monkeypatch):
    """An allowlisted transformer name is preserved verbatim."""
    from bremen.api.aramina_preprocessing import AraminaPreprocessingError

    stdout = json.dumps({
        "error": "ARAMINA_PREPROCESSING_FAILED",
        "diagnostic": {"stage": "worker_pipeline_execution",
                       "exception_class": "KeyError",
                       "transformer": "PatientSpecimenValidityFilter"},
    })
    diagnostic = _run_preprocessing_with_worker(monkeypatch, stdout)
    assert diagnostic is not None
    assert diagnostic["preprocessing_transformer"] == "PatientSpecimenValidityFilter"


def test_pr0142_unsupported_release_redacted(monkeypatch):
    """A non-allowlisted release tag becomes redacted."""
    from bremen.api.aramina_preprocessing import safe_preprocessing_diagnostic

    diagnostic = safe_preprocessing_diagnostic(
        {"stage": "worker_config"}, "v9.9.9-private",
    )
    assert diagnostic["preprocessing_release"] == "redacted"
    assert "private" not in json.dumps(diagnostic)


@pytest.mark.parametrize("release", ["v0.1.7-beta", "v0.1.9-beta"])
def test_pr0142_allowlisted_release_preserved(release):
    """Both released preprocessing tags are preserved."""
    from bremen.api.aramina_preprocessing import safe_preprocessing_diagnostic

    diagnostic = safe_preprocessing_diagnostic({"stage": "worker_config"}, release)
    assert diagnostic["preprocessing_release"] == release


def test_pr0142_safe_diagnostic_never_leaks(monkeypatch):
    """Raw stdout/stderr/path/traceback/message never reach the diagnostic."""
    from bremen.api.aramina_preprocessing import AraminaPreprocessingError

    secret = "s3://private-bucket/key /tmp/private token=secret traceback"
    stdout = json.dumps({
        "error": "ARAMINA_PREPROCESSING_FAILED",
        "diagnostic": {
            "stage": "worker_pipeline_execution",
            "exception_class": secret,
            "transformer": secret,
            "message": secret,
            "stderr": secret,
        },
    })
    diagnostic = _run_preprocessing_with_worker(monkeypatch, stdout)
    assert diagnostic is not None
    text = json.dumps(diagnostic)
    for forbidden in ("s3://", "private-bucket", "/tmp/", "token=", "traceback", "stderr", "message"):
        assert forbidden not in text
    assert diagnostic["preprocessing_exception_class"] == "redacted"
    assert diagnostic["preprocessing_transformer"] == "redacted"


def test_pr0142_public_failure_stays_unsupported_input(tmp_path, source, monkeypatch):
    """Public failure code and stage are unchanged by the subdiagnostic."""
    from bremen.api.aramina_preprocessing import AraminaPreprocessingError

    def boom(h5_path, config_yaml):
        raise AraminaPreprocessingError({
            "preprocessing_stage": "worker_pipeline_execution",
            "preprocessing_exception_class": "ValueError",
            "preprocessing_transformer": "SNRFilter",
            "preprocessing_release": "v0.1.7-beta",
            "preprocessing_reason_code": "ARAMINA_PREPROCESSING_PIPELINE_EXECUTION_FAILED",
        })

    monkeypatch.setattr("bremen.api.aramina_preprocessing.preprocess_aramina", boom)
    result = _execute(_entry(tmp_path), source)
    assert result.error == "ARAMINA_UNSUPPORTED_INPUT"
    assert result.failure_stage == "preprocessing_contract"
    assert result.preprocessing_diagnostic["preprocessing_stage"] == "worker_pipeline_execution"


def test_pr0142_job_failure_details_expose_subdiagnostic(tmp_path, source, monkeypatch):
    """The job-visible failure_details carry the nested preprocessing fields."""
    from bremen.api.aramina_preprocessing import AraminaPreprocessingError

    def boom(h5_path, config_yaml):
        raise AraminaPreprocessingError({
            "preprocessing_stage": "worker_pipeline_execution",
            "preprocessing_exception_class": "ValueError",
            "preprocessing_transformer": "SNRFilter",
            "preprocessing_release": "v0.1.7-beta",
            "preprocessing_reason_code": "ARAMINA_PREPROCESSING_PIPELINE_EXECUTION_FAILED",
        })

    monkeypatch.setattr("bremen.api.aramina_preprocessing.preprocess_aramina", boom)
    pkg = _package()
    pkg["prediction_preprocessing_yaml"] = (
        "xrd_preprocessing: {release_tag: v0.1.7-beta}\npipeline: {steps: [raw]}"
    )
    entry = _entry(tmp_path, pkg)
    _install(entry)
    job = jobs.create_analysis_job(
        model_id=entry.model_id, h5_path=source[0], aramina_request=_request(),
    )
    run = job.workflow_runs["aramina"]
    assert run.failure == "ARAMINA_UNSUPPORTED_INPUT"
    assert run.failure_details["failure_stage"] == "preprocessing_contract"
    safe = run.failure_details["safe_details"]
    assert safe["preprocessing_stage"] == "worker_pipeline_execution"
    assert safe["preprocessing_exception_class"] == "ValueError"
    assert safe["preprocessing_transformer"] == "SNRFilter"
    assert safe["preprocessing_release"] == "v0.1.7-beta"
    assert safe["preprocessing_reason_code"] == (
        "ARAMINA_PREPROCESSING_PIPELINE_EXECUTION_FAILED"
    )


def test_pr0142_subdiagnostic_absent_for_non_preprocessing_failures(tmp_path, source):
    """Non-preprocessing failures do not acquire preprocessing fields."""
    result = _execute(_entry(tmp_path), source, _request(patient_id="absent-patient"))
    assert result.failure_stage == "h5_patient_contract"
    assert result.preprocessing_diagnostic is None


def test_pr0142_subdiagnostic_absent_on_success(tmp_path, source):
    """Successful runs carry no preprocessing subdiagnostic."""
    result = _execute(_entry(tmp_path), source)
    assert result.status == "completed"
    assert result.preprocessing_diagnostic is None


def test_pr0142_public_payload_leaks_nothing(tmp_path, source, monkeypatch):
    """The full public payload contains no forbidden preprocessing values."""
    from bremen.api.aramina_preprocessing import AraminaPreprocessingError

    secret = "s3://private-bucket/key /tmp/private token=secret"

    def boom(h5_path, config_yaml):
        raise AraminaPreprocessingError({
            "preprocessing_stage": "worker_pipeline_execution",
            "preprocessing_exception_class": secret,
            "preprocessing_transformer": secret,
            "preprocessing_release": secret,
            "preprocessing_reason_code": secret,
        })

    monkeypatch.setattr("bremen.api.aramina_preprocessing.preprocess_aramina", boom)
    entry = _entry(tmp_path)
    _install(entry)
    job = jobs.create_analysis_job(
        model_id=entry.model_id, h5_path=source[0], aramina_request=_request(),
    )
    public = json.dumps([
        job.to_dict(),
        jobs.get_job_events(job.job_id),
        jobs.get_job_reports(job.job_id),
        jobs.list_analysis_jobs(model_id=entry.model_id),
    ])
    for forbidden in (
        secret, "private-bucket", "/tmp/", "token=", "Traceback",
        entry._artifact_path, entry._checksum, "_package",
    ):
        assert forbidden not in public
    safe = job.workflow_runs["aramina"].failure_details["safe_details"]
    assert safe["preprocessing_exception_class"] == "redacted"
    assert safe["preprocessing_transformer"] == "redacted"
    assert safe["preprocessing_release"] == "redacted"
    # The stage itself is allowlisted, so its reason code is preserved.
    assert safe["preprocessing_stage"] == "worker_pipeline_execution"
    assert safe["preprocessing_reason_code"] == (
        "ARAMINA_PREPROCESSING_PIPELINE_EXECUTION_FAILED"
    )


def test_pr0142_reason_codes_are_stage_derived():
    """Every allowlisted stage maps to exactly one stable reason code."""
    from bremen.api.aramina_preprocessing import (
        PREPROCESSING_REASON_CODES, PREPROCESSING_STAGES,
        safe_preprocessing_diagnostic,
    )

    assert set(PREPROCESSING_REASON_CODES) == set(PREPROCESSING_STAGES)
    for stage, reason in PREPROCESSING_REASON_CODES.items():
        diagnostic = safe_preprocessing_diagnostic({"stage": stage})
        assert diagnostic["preprocessing_stage"] == stage
        assert diagnostic["preprocessing_reason_code"] == reason
        assert reason.startswith("ARAMINA_PREPROCESSING_")


def test_pr0142_allowlists_are_closed():
    """The public allowlists are fixed and exclude the old generic label."""
    from bremen.api.aramina_preprocessing import (
        PREPROCESSING_EXCEPTION_CLASSES, PREPROCESSING_RELEASES,
        PREPROCESSING_STAGES,
    )

    assert PREPROCESSING_STAGES == {
        "worker_imports", "worker_config", "worker_pipeline_build",
        "worker_pipeline_execution", "worker_output", "worker_empty_output",
        "worker_process",
    }
    assert PREPROCESSING_RELEASES == {"v0.1.7-beta", "v0.1.9-beta"}
    assert "redacted" not in PREPROCESSING_EXCEPTION_CLASSES
    assert "BaseException" not in PREPROCESSING_EXCEPTION_CLASSES


def test_pr0142_successful_aramina_unchanged(tmp_path, source):
    """A successful Aramina run is byte-identical in shape to before."""
    result = _execute(_entry(tmp_path), source)
    assert result.status == "completed"
    assert set(result.payload) == {
        "workflow_id", "model_id", "model_version", "external_report",
        "scientifically_certified", "technical_demo_only", "clinical_stage",
    }
    assert result.failure_stage is None
    assert result.preprocessing_diagnostic is None


def test_pr0142_bremen_result_has_no_preprocessing_fields():
    """Bremen workflow results carry no Aramina preprocessing fields."""
    from bremen.api.workflow_provider import WorkflowResult

    result = WorkflowResult(workflow_id="bremen", status="failed", error="X")
    assert result.failure_stage is None
    assert result.preprocessing_diagnostic is None


# ===================================================================
# PR0143 — Aramina report contract: patient_id, target_side, links
# ===================================================================

# The exact Aramina report contract confirmed by production smoke. These
# fields must remain present with the same types.
_ARAMINA_REPORT_CONTRACT = {
    "report_id": str,
    "workflow_id": str,
    "job_id": str,
    "report_schema_version": str,
    "generated_at": str,
    "workflow_status": str,
    "model_id": (str, type(None)),
    "model_version": (str, type(None)),
    "scientifically_certified": bool,
    "disclaimer": str,
    "payload": dict,
}


def _aramina_report(job_id="job-1", score=0.42, side="left", patient="Nova_214"):
    """Build an Aramina report through the real provider."""
    from bremen.api.job_api_handler import _AraminaLocalReportProvider

    external = {"risk_score": score}
    if side is not None:
        external["target_side"] = side
    return _AraminaLocalReportProvider().generate_report(
        job_id,
        {"external_report": external},
        model_identity={"model_id": "aramina-a", "model_version": "0.2.12-beta"},
        job_context={"patient_id": patient, "target_side": side or ""},
    ).to_dict()


def test_pr0143_existing_contract_fields_present_and_typed():
    """Every pre-existing Aramina report field keeps its name and type."""
    report = _aramina_report()
    for field, expected in _ARAMINA_REPORT_CONTRACT.items():
        assert field in report, f"missing contract field: {field}"
        assert isinstance(report[field], expected), field


def test_pr0143_payload_fields_preserved():
    """risk_score and technical_demo_only stay exactly where they were."""
    report = _aramina_report(score=0.42)
    assert report["payload"]["risk_score"] == 0.42
    assert report["payload"]["technical_demo_only"] is True
    assert set(report["payload"]) == {"risk_score", "technical_demo_only"}


def test_pr0143_report_includes_patient_id():
    """Aramina reports expose the requested patient identifier."""
    assert _aramina_report(patient="Nova_214")["patient_id"] == "Nova_214"


def test_pr0143_report_includes_target_side():
    """Aramina reports expose the scored target side."""
    assert _aramina_report(side="left")["target_side"] == "left"
    assert _aramina_report(side="right")["target_side"] == "right"


def test_pr0143_report_includes_links_job_and_json():
    """Aramina reports expose job and json links."""
    report = _aramina_report(job_id="job-abc")
    assert report["links"]["job"] == "/demo/api/jobs/job-abc"
    assert report["links"]["json"] == "/demo/api/jobs/job-abc/reports/aramina"


def test_pr0143_no_pdf_link_without_endpoint():
    """No pdf link is advertised, because no PDF endpoint exists."""
    report = _aramina_report()
    assert "pdf" not in report["links"]
    assert set(report["links"]) == {"job", "json"}


def test_pr0143_no_pdf_endpoint_exists():
    """Guard: the pdf link must stay absent while no PDF route exists."""
    from pathlib import Path

    sources = list(Path("src/bremen").rglob("*.py"))
    text = "\n".join(p.read_text(encoding="utf-8") for p in sources)
    assert "application/pdf" not in text


def test_pr0143_links_are_relative_paths():
    """Links are relative API paths, never absolute or filesystem paths."""
    report = _aramina_report(job_id="job-abc")
    for value in report["links"].values():
        assert value.startswith("/demo/api/jobs/")
        assert "://" not in value
        assert "\\" not in value


def test_pr0143_unsafe_patient_id_omitted():
    """A path-like or free-form patient identifier is not echoed."""
    for unsafe in ("/tmp/private", "s3://bucket/key", "a" * 200, "has space"):
        report = _aramina_report(patient=unsafe)
        assert "patient_id" not in report, unsafe


def test_pr0143_unknown_target_side_omitted():
    """A non-allowlisted side is omitted rather than echoed."""
    report = _aramina_report(side="anterior")
    assert "target_side" not in report


def test_pr0143_failed_report_keeps_unavailable_behavior():
    """A failed Aramina report stays unavailable with an empty payload."""
    from bremen.api.job_api_handler import _AraminaLocalReportProvider

    report = _AraminaLocalReportProvider().generate_report(
        "job-2", {"external_report": {}},
        model_identity={"model_id": "aramina-a", "model_version": "0.2.12-beta"},
        job_context={"patient_id": "Nova_379", "target_side": "left"},
    ).to_dict()
    assert report["workflow_status"] == "unavailable"
    assert report["payload"] == {}
    # Safe links are still present and correct.
    assert report["links"]["json"] == "/demo/api/jobs/job-2/reports/aramina"


def test_pr0143_bremen_report_contract_unchanged():
    """Bremen reports gain none of the new Aramina fields."""
    from bremen.api.report_bremen import BremenReportProvider

    report = BremenReportProvider().generate_report(
        "job-1", {"status": "failed"},
        model_identity={"model_id": "bremen-a", "model_version": "v1"},
    ).to_dict()
    for field in ("patient_id", "target_side", "links"):
        assert field not in report, field


def test_pr0143_report_envelope_defaults_unchanged():
    """A default ReportEnvelope serializes exactly as before PR0143."""
    from bremen.api.report_provider import ReportEnvelope

    envelope = ReportEnvelope(
        report_id="r", workflow_id="bremen", job_id="j",
        report_schema_version="v0.1",
    )
    assert set(envelope.to_dict()) == {
        "report_id", "workflow_id", "job_id", "report_schema_version",
        "generated_at", "workflow_status", "model_id", "model_version",
        "scientifically_certified", "disclaimer", "payload",
    }


def test_pr0143_public_report_leaks_nothing(tmp_path, source, monkeypatch):
    """The public report JSON contains no private values."""
    entry = _entry(tmp_path)
    _install(entry)
    # The report patient_id comes from H5 patient metadata, so the fixture
    # must carry it for the identifier to be present.
    with h5py.File(source[0], "a") as f:
        f["session/sample/patient_name"] = "p1"
    monkeypatch.setattr(jobs, "resolve_source", lambda *args: source[0])
    body = _valid_aramina_body(model_id=entry.model_id, patient_id="p1", target_side="left")
    monkeypatch.setattr(jobs, "_read_json_body", lambda handler: body)
    sent = MagicMock()
    monkeypatch.setattr(jobs, "_send_json", sent)
    jobs.handle_jobs_create(MagicMock())
    job_id = sent.call_args.args[2]["job"]["job_id"]

    report = jobs.get_job_report(job_id, "aramina")
    public = json.dumps(report)
    for forbidden in (
        source[0], entry._artifact_path, entry._checksum, "_package",
        "source_key", "Traceback", "token", "s3://", "/tmp/",
    ):
        assert forbidden not in public
    assert report["report"]["patient_id"] == "p1"
    assert report["report"]["target_side"] == "left"
    assert report["report"]["links"]["job"] == f"/demo/api/jobs/{job_id}"


def test_pr0143_job_context_excludes_private_fields(tmp_path, source):
    """The report job context carries only patient_id and target_side."""
    from bremen.api.job_api_handler import _report_job_context

    entry = _entry(tmp_path)
    _install(entry)
    job = jobs.create_analysis_job(
        model_id=entry.model_id, h5_path=source[0], aramina_request=_request(),
        source_key="private-stable-key", patient_display_name="p1",
    )
    context = _report_job_context(job)
    assert set(context) == {"patient_id", "target_side"}
    assert "private-stable-key" not in json.dumps(context)
