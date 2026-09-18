"""Model Runtime Contract v1 conformance tests (PR0153B).

Proves that Bremen and Aramina satisfy the same common semantic boundary
(requirements / validate / predict), that WorkflowProviders delegate
scientific inference to a runtime rather than reimplementing it, and that
model-specific requirements coexist behind one platform-level contract.

Research decision support requiring radiologist review; no clinical claim.

Aramina symbols are fetched through ``_aramina_symbols()`` inside each test.
Some suites (test_bremen_api_skeleton) delete and reimport ``bremen.api``
modules; binding Aramina classes at this file's import time could capture a
stale module whose function globals differ from the instance monkeypatch
targets later in the session.  Fetching the current module keeps the patch
target and the code under test identical regardless of ordering.
"""
from __future__ import annotations

from tests.runtime_inputs import execute_case

import math
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest

from bremen.platform.models.registry import (
    ModelRegistry, RegistryModelEntry, initialize_registry, reset_for_tests,
)
from bremen.platform.runtime.registry import bremen_descriptor
from bremen.platform.runtime.registry import get_descriptor_for_model
from bremen.model_packages.bremen_v01.runtime import BremenRuntime
from bremen.contracts.model_runtime import (
    CONTRACT_VERSION,
    ModelConfigurationRequiredError,
    ModelInferenceFailedError,
    ModelInput,
    ModelInputInvalidError,
    ModelInputUnsupportedError,
    ModelMetadata,
    ModelMetrics,
    ModelPreprocessingFailedError,
    ModelRequirements,
    ModelRuntime,
    ModelRuntimeError,
    ModelValidation,
    RuntimePrediction,
    SourceMetadata,
)
from tests.bremen_3x3_helpers import GOLD, MODEL, make_case


# ---------------------------------------------------------------------------
# Reload-safe symbol access
# ---------------------------------------------------------------------------


def _aramina():
    """Return the current Aramina runtime module symbols."""
    import bremen.model_packages.aramina_v0213.runtime as wa

    return wa


def _aramina_entry(**over: Any) -> RegistryModelEntry:
    base = dict(
        model_id="aramina-test", display_name="Aramina", workflow_id="aramina",
        model_version="0.2.12-beta", artifact_type="aramina.joblib.model_package",
        feature_schema_version="v0.1",
        decision_policy_id="bremen_mri_triage_policy",
        decision_policy_version="v0.1", technical_ready=True,
        _package=None, _checksum="", _artifact_path="x",
    )
    base.update(over)
    return RegistryModelEntry(**base)


# ---------------------------------------------------------------------------
# Minimal fake runtime (proves providers delegate, not reimplement)
# ---------------------------------------------------------------------------


class _FakeModelRuntime:
    """A contract-satisfying runtime that records delegation calls."""

    def __init__(self) -> None:
        self.predict_calls: list[ModelInput] = []
        self.validate_calls: list[ModelInput] = []
        self.raise_on_predict: ModelRuntimeError | None = None
        self.result_mapping = {
            "probability": 0.42, "prediction": 0, "threshold_applied": 0.5,
            "decision_code": "MRI_REVIEW_DEFER",
            "decision_display_name": "Defer MRI pending clinician review",
            "decision_policy_id": "bremen_mri_continuation_threshold",
            "decision_policy_version": "0.1.0",
            "triage_recommendation": "MRI_REVIEW_DEFER",
        }

    def model_ready(self) -> bool:
        return True

    def model_requirements(self) -> ModelRequirements:
        return ModelRequirements(workflow_id="bremen", contract_version=CONTRACT_VERSION)

    def validate_model_input(self, input: ModelInput) -> ModelValidation:
        self.validate_calls.append(input)
        return ModelValidation(compatible=True)

    def predict_model(self, input: ModelInput, *, on_features=None) -> RuntimePrediction:
        self.predict_calls.append(input)
        if self.raise_on_predict is not None:
            raise self.raise_on_predict
        return RuntimePrediction(workflow_id="bremen", result=self.result_mapping)


# ---------------------------------------------------------------------------
# 1. Both runtimes satisfy the common contract structurally
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("workflow_id", ["bremen", "aramina"])
def test_runtimes_satisfy_protocol(workflow_id):
    if workflow_id == "bremen":
        runtime: Any = BremenRuntime(MODEL)
    else:
        runtime = _aramina().AraminaRuntime(entry=_aramina_entry())
    assert isinstance(runtime, ModelRuntime)
    for member in ("model_requirements", "validate_model_input", "predict_model"):
        assert callable(getattr(runtime, member))


# ---------------------------------------------------------------------------
# 2. Requirements behavior — model-specific requirements coexist and differ
# ---------------------------------------------------------------------------


def test_bremen_requirements_describe_three_plus_three():
    req = BremenRuntime(MODEL).model_requirements()
    assert req.contract_version == CONTRACT_VERSION
    assert req.workflow_id == "bremen"
    assert req.requires_target_side is False
    assert dict(req.measurement_sides) == {"LEFT": 3, "RIGHT": 3}
    assert req.total_measurements == 6
    assert req.model_version == "0.2.0-paper-reference"


def test_aramina_requirements_require_explicit_target_side():
    runtime = _aramina().AraminaRuntime(entry=_aramina_entry())
    req = runtime.model_requirements()
    assert req.contract_version == CONTRACT_VERSION
    assert req.workflow_id == "aramina"
    assert req.requires_target_side is True
    assert set(req.allowed_target_sides) == {"left", "right"}
    # Existing public request-field defaults are preserved exactly.
    assert list(req.request_fields) == [
        "container_id", "source_id", "patient_id", "target_side",
    ]
    assert list(req.optional_request_fields) == ["analysis_author", "prediction_comment"]


def test_model_specific_requirements_differ_behind_same_type():
    bremen = BremenRuntime(MODEL).model_requirements()
    aramina = _aramina().AraminaRuntime(entry=_aramina_entry()).model_requirements()
    assert type(bremen) is type(aramina) is ModelRequirements
    # Bremen 3+3 semantics vs Aramina explicit target_side semantics coexist.
    assert bremen.requires_target_side is not aramina.requires_target_side
    assert bremen.measurement_sides != aramina.measurement_sides


def test_requirements_payload_is_safe_and_serializable():
    payload = BremenRuntime(MODEL).model_requirements().to_input_requirements()
    assert payload["contract_version"] == CONTRACT_VERSION
    assert payload["total_measurements"] == 6
    text = str(payload)
    for forbidden in ("s3://", "/tmp/", ".h5", "65866f44", "joblib"):
        assert forbidden not in text


# ---------------------------------------------------------------------------
# 3. Validation routing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("left,right", [(3, 2), (2, 3), (4, 2), (1, 1), (6, 0), (0, 6)])
def test_bremen_validation_rejects_invalid_shape(left, right):
    case = make_case()
    ms = (case.measurements[0],) * left + (case.measurements[3],) * right
    validation = BremenRuntime(MODEL).validate_model_input(
        ModelInput(workflow_id="bremen", measurements=ms),
    )
    assert validation.compatible is False
    assert validation.safe_reason == "requires_exactly_3_left_3_right"


def test_bremen_validation_accepts_valid_3plus3():
    validation = BremenRuntime(MODEL).validate_model_input(
        ModelInput(workflow_id="bremen", measurements=make_case().measurements),
    )
    assert validation.compatible is True
    assert validation.safe_reason is None


def test_aramina_validation_requires_explicit_target_side():
    wa = _aramina()
    runtime = wa.AraminaRuntime(entry=_aramina_entry())
    good = ModelInput(
        workflow_id="aramina", canonical=SimpleNamespace(measurements=()),
        patient_id="P1", target_side="left",
    )
    assert runtime.validate_model_input(good).compatible is True
    for bad_side in ("", "up", "leftish"):
        with pytest.raises(ModelInputInvalidError) as exc:
            runtime.validate_model_input(
                ModelInput(
                    workflow_id="aramina", canonical=SimpleNamespace(measurements=()),
                    patient_id="P1", target_side=bad_side,
                ),
            )
        assert exc.value.safe_reason in __import__("bremen.model_packages.aramina_v0213.errors", fromlist=["_SAFE_FAILURES"])._SAFE_FAILURES
    with pytest.raises(ModelInputInvalidError):
        runtime.validate_model_input(
            ModelInput(workflow_id="aramina", canonical=None, patient_id="P1", target_side="left"),
        )


def test_bremen_validation_missing_canonical_raises():
    with pytest.raises(ModelInputInvalidError):
        BremenRuntime(MODEL).validate_model_input(
            ModelInput(workflow_id="bremen", measurements=None),
        )


# ---------------------------------------------------------------------------
# 4. Predict routing — runtime owns scientific inference
# ---------------------------------------------------------------------------


def test_bremen_predict_returns_structured_result():
    prediction = BremenRuntime(MODEL).predict_model(
        ModelInput(workflow_id="bremen", measurements=make_case().measurements),
    )
    assert isinstance(prediction, RuntimePrediction)
    assert prediction.workflow_id == "bremen"
    assert math.isclose(prediction.result["probability"], GOLD["expected_probability"], abs_tol=1e-10)
    assert prediction.result["prediction"] == 1
    assert prediction.result["threshold_applied"] == MODEL["portable_logreg"]["threshold"]


def test_bremen_predict_preserves_frozen_sequence(monkeypatch):
    # predict_model must run the exact PR0152 run() — no reimplementation.
    calls: list[str] = []
    runtime = BremenRuntime(MODEL)
    original_run = runtime.run  # bound PR0152 method captured before patching

    def fake_run(measurements, *, on_features=None):
        calls.append("run")
        return original_run(measurements, on_features=on_features)

    monkeypatch.setattr(runtime, "run", fake_run)
    runtime.predict_model(ModelInput(workflow_id="bremen", measurements=make_case().measurements))
    assert calls == ["run"]


def test_bremen_predict_maps_preprocessing_failure_to_category(monkeypatch):
    # invalid_scientific_profiles -> ModelPreprocessingFailedError (same safe reason)
    import bremen.model_packages.bremen_v01.runtime as br

    monkeypatch.setattr(br, "build_bremen_features",
                        lambda ms: (_ for _ in ()).throw(ValueError("boom")))
    with pytest.raises(ModelPreprocessingFailedError) as exc:
        BremenRuntime(MODEL).predict_model(
            ModelInput(workflow_id="bremen", measurements=make_case().measurements),
        )
    assert exc.value.safe_reason == "invalid_scientific_profiles"


def test_bremen_predict_maps_missing_model_to_configuration():
    with pytest.raises(ModelConfigurationRequiredError) as exc:
        BremenRuntime(None).predict_model(
            ModelInput(workflow_id="bremen", measurements=make_case().measurements),
        )
    assert exc.value.safe_reason == "model_not_ready"


def test_aramina_predict_delegates_to_existing_pipeline(monkeypatch):
    captured: dict[str, Any] = {}

    def fake_local(entry, canonical, request_json, h5_path):
        captured["request_json"] = request_json
        captured["h5_path"] = h5_path
        return (
            {"risk_probability": 0.11, "target_class_risk_level": 0,
             "model_version": "0.2.12-beta"},
            SourceMetadata(),
            ModelMetadata(),
            ModelMetrics(),
        )

    import bremen.model_packages.aramina_v0213.inference as inference
    wa = _aramina()
    monkeypatch.setattr(inference, "_run_local_artifact", fake_local)
    runtime = wa.AraminaRuntime(entry=_aramina_entry())
    prediction = runtime.predict_model(ModelInput(
        workflow_id="aramina", canonical=SimpleNamespace(measurements=()),
        patient_id="P1", target_side="right", container_path="/staged/x.h5",
    ))
    assert isinstance(prediction, RuntimePrediction)
    assert prediction.result["risk_probability"] == 0.11
    # Existing request semantics preserved: target_side normalized lowercase.
    assert captured["request_json"]["target_side"] == "right"
    assert captured["request_json"]["patient_id"] == "P1"
    assert captured["h5_path"] == "/staged/x.h5"


def test_aramina_predict_preserves_workflow_error_taxonomy(monkeypatch):
    import bremen.model_packages.aramina_v0213.inference as inference
    wa = _aramina()

    def boom(entry, canonical, request_json, h5_path):
        raise wa.AraminaWorkflowError("ARAMINA_UNSUPPORTED_INPUT", "preprocessing_contract")

    monkeypatch.setattr(inference, "_run_local_artifact", boom)
    runtime = wa.AraminaRuntime(entry=_aramina_entry())
    with pytest.raises(wa.AraminaWorkflowError) as exc:
        runtime.predict_model(ModelInput(
            workflow_id="aramina", canonical=SimpleNamespace(measurements=()),
            patient_id="P1", target_side="left",
        ))
    assert exc.value.code == "ARAMINA_UNSUPPORTED_INPUT"
    assert exc.value.stage == "preprocessing_contract"


# ---------------------------------------------------------------------------
# 5. WorkflowProvider delegation (no reimplementation of science)
# ---------------------------------------------------------------------------


def test_bremen_provider_returns_contract_runtime():
    provider = bremen_descriptor(model_package=MODEL)
    runtime = provider.runtime
    assert isinstance(runtime, ModelRuntime)
    assert provider.runtime is runtime


def test_bremen_provider_delegates_predict_to_runtime():
    fake = _FakeModelRuntime()
    provider = bremen_descriptor(runtime=fake)
    result = execute_case(provider, make_case())
    assert result.status == "completed"
    assert len(fake.predict_calls) == 1
    assert len(fake.validate_calls) >= 1
    # Provider projects the runtime result without doing model math itself.
    assert result.payload["probability"] == 0.42
    assert result.payload["prediction"] == 0
    assert result.payload["left_measurement_count"] == 3
    assert result.payload["right_measurement_count"] == 3
    # Adding a fake runtime required NO change to provider scientific logic.
    assert isinstance(provider.runtime, ModelRuntime)


def test_bremen_provider_preserves_incompatible_envelope_from_runtime_error():
    fake = _FakeModelRuntime()
    fake.raise_on_predict = ModelInputInvalidError("requires_exactly_3_left_3_right")
    provider = bremen_descriptor(runtime=fake)
    result = execute_case(provider, make_case())
    assert result.status == "failed"
    assert result.error == "Incompatible: requires_exactly_3_left_3_right"


def test_bremen_provider_preserves_preprocessing_envelope_from_runtime_error():
    fake = _FakeModelRuntime()
    fake.raise_on_predict = ModelPreprocessingFailedError("invalid_scientific_profiles")
    provider = bremen_descriptor(runtime=fake)
    result = execute_case(provider, make_case())
    assert result.error == "Feature construction failed: invalid_scientific_profiles"


def test_bremen_provider_preserves_configuration_envelope_from_runtime_error():
    fake = _FakeModelRuntime()
    fake.raise_on_predict = ModelConfigurationRequiredError("workflow_configuration_required")
    provider = bremen_descriptor(runtime=fake)
    result = execute_case(provider, make_case())
    assert result.error == "Workflow configuration required for multi-position input"


def test_bremen_provider_preserves_execution_envelope_from_runtime_error():
    fake = _FakeModelRuntime()
    fake.raise_on_predict = ModelInferenceFailedError("model_execution_failed")
    provider = bremen_descriptor(runtime=fake)
    result = execute_case(provider, make_case())
    assert result.error == "Model execution failed"


def test_aramina_provider_delegates_predict_to_runtime(monkeypatch):
    monkeypatch.setattr(
        "bremen.platform.runtime.executor.validate_source_binding",
        lambda *args: None,
    )
    import bremen.model_packages.aramina_v0213.inference as inference
    monkeypatch.setattr(
        inference, "_run_local_artifact",
        lambda entry, canonical, request_json, h5_path: (
            {"risk_probability": 0.5, "model_version": "0.2.12-beta"},
            SourceMetadata(),
            ModelMetadata(),
            ModelMetrics(),
        ),
    )
    provider = __import__("bremen.platform.runtime.registry", fromlist=["aramina_descriptor"]).aramina_descriptor(entry=_aramina_entry())
    assert isinstance(provider.runtime, ModelRuntime)
    result = execute_case(provider,
        SimpleNamespace(measurements=()),
        aramina_request=SimpleNamespace(
            patient_id="P1", target_side="left", analysis_author="", prediction_comment="",
            container_id="c", source_id="s",
        ),
        h5_path="/staged/x.h5",
    )
    assert result.status == "completed"
    assert result.payload["external_report"]["risk_probability"] == 0.5


# ---------------------------------------------------------------------------
# 6. Contract error category set
# ---------------------------------------------------------------------------


def test_runtime_error_categories_are_owned_and_safe():
    categories = (
        ModelInputInvalidError, ModelInputUnsupportedError,
        ModelConfigurationRequiredError, ModelPreprocessingFailedError,
        ModelInferenceFailedError,
    )
    for category in categories:
        assert issubclass(category, ModelRuntimeError)
        assert issubclass(ModelRuntimeError, ValueError)
        err = category("safe_reason_only")
        assert err.safe_reason == "safe_reason_only"
        assert err.category != ModelRuntimeError.category
    # A leaked private value cannot appear because runtimes use constants only.
    with pytest.raises(ModelRuntimeError):
        raise ModelPreprocessingFailedError("invalid_scientific_profiles")


# ---------------------------------------------------------------------------
# 7. Model Requirements API derives from the runtime (additive)
# ---------------------------------------------------------------------------


def _bremen_available_entry():
    return RegistryModelEntry(
        model_id="bremen-current-test", display_name="Bremen", workflow_id="bremen",
        model_version="0.2.0-paper-reference", artifact_type="portable_logreg",
        feature_schema_version="v0.1",
        decision_policy_id="bremen_mri_continuation_threshold",
        decision_policy_version="0.1.0", technical_ready=True,
        _package=deepcopy(MODEL), _checksum="abc",
        _container_requirements={"schema_version": "bremen.container_requirements.v1"},
    )


def test_model_requirements_runtime_derivation_available():
    reset_for_tests()
    try:
        entry = _bremen_available_entry()
        initialize_registry(ModelRegistry(entries=(entry,), catalog_status="available",
                                           available_count=1, candidate_count=1))
        from bremen.api.model_requirements import _runtime_input_requirements
        req = _runtime_input_requirements("bremen-current-test")
        assert req is not None
        assert req["contract_version"] == CONTRACT_VERSION
        assert req["total_measurements"] == 6
        assert req["request_fields"] == ["container_id", "source_id"]
    finally:
        reset_for_tests()


def test_model_requirements_response_additive_and_safe():
    reset_for_tests()
    try:
        initialize_registry(ModelRegistry(entries=(_bremen_available_entry(),),
                                          catalog_status="available", available_count=1,
                                          candidate_count=1))
        from bremen.api.model_requirements import build_model_requirements_response
        data = build_model_requirements_response("bremen-current-test")
        assert data["requirements_available"] is True
        mr = data["container_requirements"]["model_runtime"]
        assert mr["contract_version"] == CONTRACT_VERSION
        assert mr["input_requirements"]["total_measurements"] == 6
        # No private paths, checksums or artifact internals leak.
        text = str(data)
        for forbidden in ("s3://", "/tmp/", "abc", "joblib"):
            assert forbidden not in text
    finally:
        reset_for_tests()


def test_model_requirements_endpoint_paths_and_fields_unchanged():
    reset_for_tests()
    try:
        initialize_registry(ModelRegistry(entries=(_bremen_available_entry(),),
                                          catalog_status="available", available_count=1,
                                          candidate_count=1))
        from bremen.api.model_requirements import build_model_requirements_response
        data = build_model_requirements_response("bremen-current-test")
        # Existing PR0122/PR0124 public fields remain present with same types.
        assert data["schema_version"] == "bremen.model_requirements.v1"
        assert isinstance(data["required_fields"], list)
        assert isinstance(data["optional_fields"], list)
        assert isinstance(data["container_requirements"], dict)
        assert isinstance(data["technical_demo_only"], bool)
    finally:
        reset_for_tests()


def test_requirements_noop_without_manifest_unchanged():
    reset_for_tests()
    try:
        entry = _bremen_available_entry()
        # remove manifest -> no-op path (never enriched)
        object.__setattr__(entry, "_container_requirements", None)
        initialize_registry(ModelRegistry(entries=(entry,), catalog_status="available",
                                           available_count=1, candidate_count=1))
        from bremen.api.model_requirements import build_model_requirements_response
        data = build_model_requirements_response("bremen-current-test")
        assert data["requirements_available"] is False
        assert data["status"] == "requirements_not_declared"
        assert "model_runtime" not in str(data)
    finally:
        reset_for_tests()


def test_display_only_aramina_has_no_runtime_derivation():
    reset_for_tests()
    try:
        entry = _aramina_entry(availability="unavailable", artifact_type="portable_logreg",
                               technical_ready=False, _artifact_path="")
        initialize_registry(ModelRegistry(entries=(entry,), catalog_status="available",
                                           unavailable_count=1, candidate_count=1))
        from bremen.api.model_requirements import _runtime_input_requirements
        assert _runtime_input_requirements("aramina-test") is None
    finally:
        reset_for_tests()


# ---------------------------------------------------------------------------
# 8. Dependency direction — the contract must not import model science/API
# ---------------------------------------------------------------------------


def test_model_runtime_imports_no_platform_or_model_specific_code():
    import bremen.contracts.model_runtime as contract_module

    with open(contract_module.__file__, encoding="utf-8") as handle:
        source = handle.read()
    for forbidden in (
        "bremen.api", "bremen_runtime", "workflow_bremen", "workflow_aramina",
        "bremen_features", "aramina_preprocessing", "aramina_symmetry",
    ):
        assert forbidden not in source, f"contract module must not reference {forbidden}"


def test_registry_routing_selects_provider_owning_runtime():
    reset_for_tests()
    try:
        initialize_registry(ModelRegistry(entries=(_bremen_available_entry(),),
                                          catalog_status="available", available_count=1,
                                          candidate_count=1))
        provider = get_descriptor_for_model("bremen-current-test")
        assert isinstance(provider.runtime, ModelRuntime)
    finally:
        reset_for_tests()
