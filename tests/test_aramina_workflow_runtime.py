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
    assert result.error == "ARAMINA_EXECUTION_FAILED"
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
    assert result.error == "ARAMINA_EXECUTION_FAILED"
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
    assert result.error == "ARAMINA_EXECUTION_FAILED"
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
    assert job.workflow_runs["aramina"].failure == "ARAMINA_EXECUTION_FAILED"
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
    with pytest.raises(ValueError, match="Missing artifact preprocessing pipeline"):
        synthetic_preprocessing("private", "{}")


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


@pytest.mark.parametrize("missing", ["final_column", "threshold"])
def test_no_missing_feature_or_threshold_fallback(tmp_path, source, missing):
    pkg = _package()
    info = pkg["models"]["selected_model"]
    if missing == "final_column":
        info["feature_columns"].append("unknown_feature")
    else:
        del info["thresholds"]["threshold_target"]
    result = _execute(_entry(tmp_path, pkg), source)
    assert result.error == "ARAMINA_EXECUTION_FAILED"
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
