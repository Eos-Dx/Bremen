"""Registration policies for package runtimes; no provider execution interface."""

from dataclasses import dataclass
from typing import Callable, Any

from bremen.contracts.model_runtime import ModelRuntime
from bremen.contracts.execution import WorkflowReadiness


@dataclass(frozen=True)
class ModelDescriptor:
    workflow_id: str
    runtime: ModelRuntime
    project: Callable
    failure: Callable
    model_id: str = ""
    model_version: str = ""
    checksum: str = ""
    clinical_stage: str = ""
    model_ready: bool = True
    legacy_input: bool = False
    configured: bool = True
    telemetry: Callable | None = None
    failure_event_reason: bool = False
    bind_patient: bool = False
    binding_failure: Callable | None = None

    def readiness(self):
        return WorkflowReadiness(
            self.workflow_id, self.configured, self.model_ready, False
        )


class ModelNotFoundError(LookupError):
    pass


class DuplicateModelError(ValueError):
    pass


class RuntimeRegistry:
    def __init__(self):
        self._models: dict[str, ModelDescriptor] = {}

    def register(self, descriptor: ModelDescriptor):
        if descriptor.workflow_id in self._models:
            raise DuplicateModelError(
                f"Workflow '{descriptor.workflow_id}' is already registered"
            )
        self._models[descriptor.workflow_id] = descriptor

    def resolve(self, workflow_id: str) -> ModelDescriptor:
        try:
            return self._models[workflow_id]
        except KeyError:
            raise ModelNotFoundError(f"Workflow '{workflow_id}' not found") from None

    def list_capabilities(self):
        return {wid: d.readiness() for wid, d in self._models.items()}

    def list_workflow_ids(self):
        return list(self._models)


def bremen_descriptor(
    model_package=None,
    *,
    model_checksum=None,
    model_version=None,
    model_id=None,
    runtime=None,
):
    from bremen.platform.reports.execution_events import bremen_events
    from bremen.platform.reports.runtime_projection import (
        project_bremen,
        bremen_failure,
    )

    if runtime is None:
        from bremen.model_packages.bremen_v01 import BremenRuntime
        runtime = BremenRuntime(model_package)
        configured = getattr(runtime, "package", None) is not None
    else:
        configured = True
    return ModelDescriptor(
        "bremen",
        runtime,
        project_bremen,
        bremen_failure,
        model_id=model_id or "bremen_mri_triage_logreg",
        model_version=model_version or "",
        checksum=model_checksum or "",
        model_ready=(
            runtime.model_ready()
            if callable(getattr(runtime, "model_ready", None))
            else True
        ),
        legacy_input=not getattr(runtime, "requires_raw_container", False),
        configured=configured,
        telemetry=bremen_events,
    )


def aramina_descriptor(*, entry, runtime=None):
    from bremen.platform.reports.runtime_projection import (
        project_aramina,
        aramina_failure,
    )

    if runtime is None:
        from bremen.model_packages.aramina_v0213 import AraminaRuntime
        from bremen.model_packages.aramina_v0213.errors import AraminaWorkflowError
        runtime = AraminaRuntime(entry=entry)
        binding_failure = lambda: AraminaWorkflowError(
            "ARAMINA_UNSUPPORTED_INPUT", "h5_patient_contract"
        )
    else:
        def binding_failure():
            from bremen.model_packages.aramina_v0213.errors import AraminaWorkflowError
            return AraminaWorkflowError(
                "ARAMINA_UNSUPPORTED_INPUT", "h5_patient_contract"
            )

    return ModelDescriptor(
        "aramina",
        runtime,
        project_aramina,
        aramina_failure,
        model_id=entry.model_id,
        model_version=entry.model_version,
        clinical_stage=entry._clinical_stage,
        legacy_input=True,
        bind_patient=True,
        failure_event_reason=True,
        binding_failure=binding_failure,
    )


def _candidate_runtime_for(entry):
    """Return a ``SubprocessRuntime`` when the entry carries a validated
    ``runtime_release``. Otherwise return ``None`` so legacy entries retain
    their existing in-process runtime.

    Lazily imported so merely importing this registry module never pulls in
    subprocess/release-cache machinery; this module itself never imports ML
    plugin code either way.
    """
    from bremen.platform.runtime.subprocess_runtime import SubprocessRuntime

    getter = getattr(entry, "get_runtime_release", None)
    if not callable(getter) or not getter():
        return None
    return SubprocessRuntime(entry=entry)


def _bremen_entry(entry):
    candidate_runtime = _candidate_runtime_for(entry)
    kwargs: dict[str, Any] = dict(
        model_package=entry._package,
        model_checksum=entry._checksum,
        model_version=entry.model_version,
        model_id=entry.model_id,
    )
    if candidate_runtime is not None:
        # Only passed when the candidate route is actually enabled, so the
        # legacy/default construction call shape is byte-for-byte unchanged
        # (HARD RULE: no deployment changes behavior merely because
        # runtime_release exists).
        kwargs["runtime"] = candidate_runtime
    return bremen_descriptor(**kwargs)


def _aramina_entry(entry):
    candidate_runtime = _candidate_runtime_for(entry)
    if candidate_runtime is not None:
        return aramina_descriptor(entry=entry, runtime=candidate_runtime)
    return aramina_descriptor(entry=entry)


# Registration is the only place that knows package identity.
_FACTORIES: dict[str, Callable[[Any], ModelDescriptor]] = {
    "bremen": _bremen_entry,
    "aramina": _aramina_entry,
}


def get_descriptor_for_model(model_id: str) -> ModelDescriptor:
    from bremen.platform.models.registry import get_model_entry

    entry = get_model_entry(model_id)
    if (
        entry is None
        or entry.workflow_id not in _FACTORIES
        or (
            entry.workflow_id == "aramina"
            and entry.artifact_type != "aramina.joblib.model_package"
        )
    ):
        raise ValueError(f"Model '{model_id}' not found in registry")
    return _FACTORIES[entry.workflow_id](entry)


def get_default_registry():
    from bremen.platform.models.registry import get_registry
    from bremen.platform.models.state import ModelState

    registry = RuntimeRegistry()
    state = ModelState.get_instance()
    package = ModelState.get_model()
    registry.register(
        bremen_descriptor(
            model_package=package,
            model_checksum=(state._model_checksum or "") if package is not None else "",
            model_version=(state._model_version or "") if package is not None else "",
        )
    )
    entries = [
        e
        for e in get_registry().available_entries
        if e.workflow_id == "aramina"
        and e.artifact_type == "aramina.joblib.model_package"
    ]
    if len(entries) == 1:
        registry.register(aramina_descriptor(entry=entries[0]))
    return registry
