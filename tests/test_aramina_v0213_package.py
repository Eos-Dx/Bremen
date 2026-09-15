"""Direct Aramina v0.2.13 model-package tests (PR0156).

Invoke the inference-complete Aramina package runtime WITHOUT the
WorkflowProvider and prove:

- runtime construction + ModelRuntime contract satisfaction,
- model requirements (explicit target_side) and identity/provenance,
- input validation (missing canonical / invalid target_side),
- direct package prediction reproduces the provider-level scientific report
  bit-for-bit (same pipeline, same thresholds — no provider involvement),
- model-owned threshold/decision boundary,
- safe diagnostics never leak private text,
- import-direction guarantees for the package.

Only synthetic estimator artifacts generated at test time are used.  No real
model weights, private H5, patient data or clinical claims.  Research decision
support requiring radiologist review.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace

import h5py
import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

import bremen.model_packages.aramina_v0213 as aramina_pkg
from bremen.model_packages.aramina_v0213 import manifest
from bremen.model_packages.aramina_v0213.errors import AraminaWorkflowError
from bremen.model_packages.aramina_v0213.inference import _build_aramina_request_json
from bremen.model_packages.aramina_v0213.runtime import AraminaRuntime
from bremen.model_runtime import (
    ModelInput,
    ModelInputInvalidError,
    ModelRequirements,
    ModelRuntime,
    RuntimePrediction,
)

SRC = Path(__file__).parents[1] / "src" / "bremen"
PKG = SRC / "model_packages" / "aramina_v0213"

_FINAL_COLS = list(manifest.FINAL_FEATURE_COLUMNS)


# ---------------------------------------------------------------------------
# Synthetic artifacts (test-only; nothing committed)
# ---------------------------------------------------------------------------


def _lr1(width=10):
    rng = np.random.RandomState(42)
    return LogisticRegression(random_state=0).fit(rng.rand(4, width), [0, 0, 1, 1])


def _final():
    X = np.array([
        [0.1, 0., 0., 1., 2., 3., 1., 1.],
        [0.8, 0., 0., 2., 4., 6., 2., 1.],
        [0.3, 0., 0., 0.5, 1., 1.5, 0.5, 0.],
        [0.9, 0., 0., 3., 6., 9., 3., 1.],
    ])
    return LogisticRegression(random_state=0).fit(X, [0, 0, 1, 1])


def _package(model_version="0.2.13-beta", threshold=0.5):
    return {
        "kind": manifest.ARTIFACT_KIND,
        "version": "0.3",
        "model_identity": {"name": manifest.MODEL_NAME, "version": model_version},
        "models": {"selected_model": {
            "lr1_model": _lr1(), "final_model": _final(),
            "thresholds": {"threshold_target": threshold},
            "feature_columns": _FINAL_COLS,
            "class_definition": {"0": "low_risk", "1": "high_risk"},
        }},
        "prediction_preprocessing_yaml": "pipeline: {steps: [raw]}",
        "prediction_contract_yaml": "output: risk_score",
    }


def _entry(tmp_path, package=None, model_version="0.2.13-beta", name="aramina-a"):
    package = package if package is not None else _package(model_version)
    path = tmp_path / f"{name}.joblib"
    joblib.dump(package, path)
    return SimpleNamespace(
        model_id="aramina-a", model_version=model_version,
        feature_schema_version="v0.1", artifact_type=manifest.ARTIFACT_TYPE,
        _artifact_path=str(path),
        _checksum=hashlib.sha256(path.read_bytes()).hexdigest(),
        _clinical_stage="research draft",
    )


def _canonical():
    q = np.linspace(2., 23., 10)
    meas = []
    for side in ("LEFT", "RIGHT"):
        meas.append(SimpleNamespace(side=side, position="P1", q=q, intensity=q / 2,
                                    qc_flags=()))
    return SimpleNamespace(measurements=tuple(meas), source_checksum="x")


def _h5(tmp_path):
    path = tmp_path / "synthetic.h5"
    with h5py.File(path, "w") as f:
        f["patient/id"] = "p1"
    return str(path)


def _deterministic_frame(h5_path, config_yaml):
    profile = np.linspace(1., 10., 10)
    q = np.linspace(2., 23., 10)
    return pd.DataFrame([
        {"patientId": "p1", "side": "left", "age": 42.0,
         "radial_profile_data": profile, "q_range": q},
        {"patientId": "p1", "side": "right", "age": 42.0,
         "radial_profile_data": profile * 0.5, "q_range": q},
    ])


@pytest.fixture
def wired(monkeypatch):
    """Patch the platform source-binding seam and artifact preprocessing so the
    package pipeline is fully exercisable without real S3/xrd services."""
    import bremen.model_packages.aramina_v0213.inference as inference
    import bremen.model_packages.aramina_v0213.preprocessing as preprocessing

    monkeypatch.setattr(inference, "_validate_aramina_source",
                        lambda h5, canonical, patient_id: None)
    monkeypatch.setattr(preprocessing, "preprocess_aramina", _deterministic_frame)
    return inference


def _model_input(h5_path):
    return ModelInput(
        workflow_id="aramina", measurements=(), canonical=_canonical(),
        patient_id="p1", target_side="left", container_path=h5_path,
        parameters={"analysis_author": "Bremen Platform", "prediction_comment": ""},
    )


# ---------------------------------------------------------------------------
# Contract + entry point (no provider)
# ---------------------------------------------------------------------------


def test_package_runtime_satisfies_contract_without_provider():
    assert isinstance(aramina_pkg.AraminaRuntime, type)
    runtime = AraminaRuntime(entry=SimpleNamespace(
        model_id="aramina-a", model_version="0.2.13-beta",
        feature_schema_version="v0.1",
    ))
    assert isinstance(runtime, ModelRuntime)
    for member in ("model_requirements", "validate_model_input", "predict_model"):
        assert callable(getattr(runtime, member))


def test_package_requirements_explicit_target_side():
    runtime = AraminaRuntime(entry=SimpleNamespace(
        model_id="aramina-a", model_version="0.2.13-beta",
        feature_schema_version="v0.1",
    ))
    req = runtime.model_requirements()
    assert isinstance(req, ModelRequirements)
    assert req.workflow_id == "aramina"
    assert req.requires_target_side is True
    assert set(req.allowed_target_sides) == {"left", "right"}
    assert list(req.request_fields) == [
        "container_id", "source_id", "patient_id", "target_side",
    ]
    # Static contract is manifest-owned.
    assert req.allowed_target_sides == manifest.ALLOWED_TARGET_SIDES
    # Per-selection identity remains entry-driven (public model_id unchanged).
    assert req.model_id == "aramina-a"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validate_missing_canonical_raises():
    runtime = AraminaRuntime(entry=SimpleNamespace(
        model_id="a", model_version="v", feature_schema_version="v0.1",
    ))
    with pytest.raises(ModelInputInvalidError):
        runtime.validate_model_input(
            ModelInput(workflow_id="aramina", canonical=None, patient_id="p1",
                       target_side="left"),
        )


@pytest.mark.parametrize("bad_side", ["", "anterior", "up"])
def test_validate_invalid_target_side(bad_side):
    runtime = AraminaRuntime(entry=SimpleNamespace(
        model_id="a", model_version="v", feature_schema_version="v0.1",
    ))
    with pytest.raises(ModelInputInvalidError) as exc:
        runtime.validate_model_input(
            ModelInput(workflow_id="aramina", canonical=_canonical(),
                       patient_id="p1", target_side=bad_side),
        )
    assert exc.value.safe_reason == "ARAMINA_INVALID_REQUEST"


def test_validate_valid_request():
    runtime = AraminaRuntime(entry=SimpleNamespace(
        model_id="a", model_version="v", feature_schema_version="v0.1",
    ))
    assert runtime.validate_model_input(
        ModelInput(workflow_id="aramina", canonical=_canonical(),
                   patient_id="p1", target_side="right"),
    ).compatible is True


# ---------------------------------------------------------------------------
# Direct package prediction — golden scientific report
# ---------------------------------------------------------------------------


def test_direct_package_prediction_matches_provider_route(tmp_path, wired):
    from bremen.api.workflow_aramina import AraminaWorkflowProvider
    from bremen.api.aramina_provider import AraminaProviderRequest

    entry = _entry(tmp_path)
    h5 = _h5(tmp_path)
    package_report = dict(
        AraminaRuntime(entry=entry).predict_model(_model_input(h5)).result
    )

    provider = AraminaWorkflowProvider(entry=entry)
    result = provider.execute(
        _canonical(),
        aramina_request=AraminaProviderRequest(
            container_id="c", source_id="s", patient_id="p1", target_side="left",
            analysis_author="Bremen Platform", prediction_comment="",
        ),
        h5_path=h5,
    )
    assert result.status == "completed"
    provider_report = dict(result.payload["external_report"])
    # Direct package execution and the provider route are identical.
    assert package_report == provider_report


def test_direct_package_prediction_fields_and_threshold(tmp_path, wired):
    entry = _entry(tmp_path)
    prediction = AraminaRuntime(entry=entry).predict_model(_model_input(_h5(tmp_path)))
    assert isinstance(prediction, RuntimePrediction)
    report = prediction.result
    for key in ("risk_probability", "risk_score", "target_class_risk_level",
                "decision_threshold", "target_side", "model_name", "model_version",
                "reliability", "reliability_reason"):
        assert key in report
    # risk_score is the backward-compatible alias for risk_probability.
    assert report["risk_score"] == report["risk_probability"]
    # target_side normalized lowercase (unchanged semantics).
    assert report["target_side"] == "left"
    # model-owned threshold + decision boundary.
    thr = report["decision_threshold"]
    prob = report["risk_probability"]
    assert report["target_class_risk_level"] == (1 if prob >= thr else 0)
    assert report["reliability"] == "research_draft"
    assert prediction.model_version == "0.2.13-beta"
    assert prediction.model_id == "aramina-a"


def test_direct_package_threshold_flips_decision(tmp_path, wired):
    # A high threshold must push the decision to class 0 with the SAME
    # probability; only the model-owned threshold moves the boundary.
    low = _entry(tmp_path, _package(threshold=0.0), name="lo")
    high = _entry(tmp_path, _package(threshold=1.0), name="hi")
    h5 = _h5(tmp_path)
    lo = AraminaRuntime(entry=low).predict_model(_model_input(h5)).result
    hi = AraminaRuntime(entry=high).predict_model(_model_input(h5)).result
    assert lo["risk_probability"] == pytest.approx(hi["risk_probability"])
    assert lo["target_class_risk_level"] == 1
    assert hi["target_class_risk_level"] == 0


# ---------------------------------------------------------------------------
# Safe diagnostics — never leak private text (model-owned taxonomy)
# ---------------------------------------------------------------------------


def test_package_scientific_failure_taxonomy_and_no_leak(tmp_path, monkeypatch):
    import bremen.model_packages.aramina_v0213.inference as inference

    monkeypatch.setattr(inference, "_validate_aramina_source",
                        lambda h5, canonical, patient_id: None)

    def boom(h5_path, config_yaml):
        raise ValueError("/private/model.joblib s3://bucket/key token=abc patient-private")

    monkeypatch.setattr(
        "bremen.model_packages.aramina_v0213.preprocessing.preprocess_aramina", boom,
    )
    entry = _entry(tmp_path)
    with pytest.raises(AraminaWorkflowError) as exc:
        AraminaRuntime(entry=entry).predict_model(_model_input(_h5(tmp_path)))
    err = exc.value
    assert err.code == "ARAMINA_UNSUPPORTED_INPUT"
    assert err.stage == "preprocessing_contract"
    blob = json_blob(err)
    for forbidden in ("/private", "s3://", "token", "patient-private", "joblib"):
        assert forbidden not in blob


def json_blob(exc):
    import json
    return json.dumps({
        "code": exc.code, "stage": exc.stage,
        "diag": getattr(exc, "preprocessing_diagnostic", None),
        "original": getattr(exc, "original_exception_class", None),
    })


# ---------------------------------------------------------------------------
# Request validation is package-owned
# ---------------------------------------------------------------------------


def test_request_validation_normalizes_and_rejects():
    payload = _build_aramina_request_json(patient_id=" p1 ", target_side=" LEFT ")
    assert payload == {
        "patient_id": "p1", "target_side": "left",
        "analysis_author": "Bremen Platform", "prediction_comment": "",
    }
    with pytest.raises(AraminaWorkflowError) as exc:
        _build_aramina_request_json(patient_id="p1", target_side="anterior")
    assert exc.value.code == "ARAMINA_INVALID_REQUEST"


# ---------------------------------------------------------------------------
# Identity / provenance / dependencies
# ---------------------------------------------------------------------------


def test_manifest_authoritative_identity_and_contract():
    assert manifest.WORKFLOW_ID == "aramina"
    assert manifest.ARTIFACT_TYPE == "aramina.joblib.model_package"
    assert manifest.ARTIFACT_KIND == "aramina_training_artifact"
    assert manifest.REQUIRES_TARGET_SIDE is True
    assert manifest.ALLOWED_TARGET_SIDES == ("left", "right")
    assert manifest.TOTAL_MEASUREMENTS is None  # no fixed per-side count
    assert manifest.ALLOWED_PREPROCESSING_RELEASES == {"v0.1.7-beta", "v0.1.9-beta"}
    assert "scikit-learn" in manifest.RUNTIME_DEPENDENCIES


# ---------------------------------------------------------------------------
# Import-direction guarantees (package never depends on orchestration)
# ---------------------------------------------------------------------------


def _module_imports(rel: str) -> set[str]:
    tree = ast.parse((PKG / rel).read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mods.add(("." * node.level) + (node.module or ""))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name)
    return mods


@pytest.mark.parametrize("rel", [
    "manifest.py", "errors.py", "trace.py", "artifact_compat.py",
    "preprocessing.py", "symmetry.py",
])
def test_aramina_pure_science_has_no_platform_orchestration_imports(rel):
    mods = _module_imports(rel)
    for module in mods:
        assert "workflow_aramina" not in module
        assert "workflow_orchestrator" not in module
        assert "job_api_handler" not in module
        assert "fastapi" not in module.lower()
        assert "report_" not in module
        assert "auth" not in module.split(".")[-1]


def test_aramina_inference_only_documented_platform_edges():
    # inference.py: the only allowed platform imports are the registry type-free
    # data (via canonical_input/manifest) and the two documented narrow seams
    # (canonical_input + workflow_orchestrator lazy source binding).  It must
    # NOT import the provider / jobs / fastapi / reports / storage catalog.
    mods = _module_imports("inference.py")
    for module in mods:
        leaf = module.split(".")[-1]
        assert leaf not in {
            "workflow_aramina", "workflow_provider", "job_api_handler", "jobs",
            "fastapi_app", "report_aramina", "report_provider", "s3_model_discovery",
            "source_registry", "model_registry", "model_state",
        }
    # canonical_input + narrow bridge are the expected generic/platform-neutral edges
    assert "bremen.canonical_input" in mods or any("canonical_input" in m for m in mods)
    assert "bremen.model_packages_bridge" in mods


def test_package_entry_imports_no_workflow_modules(tmp_path):
    import subprocess
    import sys

    code = (
        "import sys; import bremen.model_packages.aramina_v0213; "
        "bad=[m for m in sys.modules if any(t in m for t in "
        "('workflow_aramina','workflow_bremen','fastapi_app','job_api_handler',"
        "'report_aramina','report_provider','source_registry'))]; "
        "print(','.join(bad)); sys.exit(1 if bad else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"package import pulled in platform modules: {result.stdout}"
