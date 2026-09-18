"""Model Runtime Contract v1 — the platform/model semantic boundary (PR0153B).

Bremen Platform orchestrates inference.  Model runtimes implement scientific
inference.  This module defines the common contract that both sides meet; it
is the authoritative boundary described by ``docs/model_runtime_contract_v1.md``
and ADR-0016.

The contract has exactly three semantic responsibilities:

- ``model_requirements()``  — describe the model-specific input contract.
- ``validate_model_input()`` — validate model-specific compatibility.
- ``predict_model()``       — execute complete model-specific inference.

Dependency direction (enforced by tests): this module must not import
platform API code or any model-specific scientific implementation.  Platform
orchestration depends on this contract; ``BremenRuntime`` and the Aramina
runtime implement it.

The contract deliberately carries no HTTP, job-persistence, registry or
serving-framework concepts.  Runtime errors use safe constant categories;
public API error codes remain owned by platform adapters (backward
compatibility is the adapters' responsibility, never the runtime's).

Ownership rule (PR0160): a model package may receive the staged raw source
(``ModelInput.container_path``).  The platform must not scientifically
interpret that source before model execution; the package owns preprocessing,
feature, gate, estimator, and source-metadata interpretation.  Platform-side
source integrity / request-source identity binding is performed by the
platform before invoking the package.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

CONTRACT_VERSION = "v1"

__all__ = [
    "CONTRACT_VERSION",
    "ModelConfigurationRequiredError",
    "ModelInferenceFailedError",
    "ModelInput",
    "ModelInputInvalidError",
    "ModelInputUnsupportedError",
    "ModelMetadata",
    "ModelMetrics",
    "ModelPreprocessingFailedError",
    "ModelRequirements",
    "ModelRuntime",
    "ModelRuntimeError",
    "ModelValidation",
    "RuntimePrediction",
    "SourceMetadata",
]


# ---------------------------------------------------------------------------
# Structured runtime input
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelInput:
    """Canonical runtime input carrier for one inference request.

    It transports the existing platform canonical input objects (the canonical
    XRD case / measurements are reused, not redesigned in PR0153B) plus the
    model-declared request parameters.  It is intentionally independent of
    FastAPI request objects, job-handler objects and workflow result envelopes.

    Model runtimes consume the parts their contract requires:
    ``BremenRuntime`` uses ``measurements`` (the exact 3+3 scientific input)
    or, for the raw-container path (PR0160), ``container_path`` plus the
    artifact-owned preprocessing; the Aramina runtime uses ``canonical``,
    ``patient_id``, ``target_side``, ``container_path`` and the model-specific
    ``parameters``.  Unused fields stay at their defaults so runtimes never
    depend on each other's shape.

    A model package may receive the staged raw source (``container_path``).
    The platform must not scientifically interpret that source before model
    execution. Source integrity and request/source identity binding remain
    platform responsibilities, performed before package invocation.
    """

    workflow_id: str
    measurements: Sequence[Any] = ()
    canonical: Any = None
    patient_id: str = ""
    target_side: str = ""
    container_path: str = ""
    parameters: Mapping[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Structured runtime outputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelRequirements:
    """Model-declared input contract returned by ``model_requirements()``.

    ``measurement_sides`` entries are ``(SIDE, required_count)`` pairs; an
    empty tuple means the model does not declare a fixed side-count contract.
    ``total_measurements`` is the required total when the model declares one.
    ``request_fields`` / ``optional_request_fields`` describe the
    model-specific request-parameter contract consumed by
    ``validate_model_input`` / ``predict_model``; they are exposed to the
    Model Requirements API so it can derive model-specific requirements from
    the runtime instead of duplicating platform knowledge.
    """

    contract_version: str = CONTRACT_VERSION
    workflow_id: str = ""
    model_id: str = ""
    model_version: str = ""
    feature_schema_version: str = ""
    measurement_sides: tuple[tuple[str, int], ...] = ()
    total_measurements: int | None = None
    requires_target_side: bool = False
    allowed_target_sides: tuple[str, ...] = ()
    request_fields: tuple[str, ...] = ()
    optional_request_fields: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    scientifically_certified: bool = False

    def to_input_requirements(self) -> dict[str, Any]:
        """Return a safe JSON-serializable view of the input contract.

        Contains only static model-declared values; never paths, checksums,
        tokens or artifact internals.
        """
        return {
            "contract_version": self.contract_version,
            "workflow_id": self.workflow_id,
            "model_version": self.model_version,
            "feature_schema_version": self.feature_schema_version,
            "measurement_sides": [
                {"side": side, "required_count": count}
                for side, count in self.measurement_sides
            ],
            "total_measurements": self.total_measurements,
            "requires_target_side": self.requires_target_side,
            "allowed_target_sides": list(self.allowed_target_sides),
            "request_fields": list(self.request_fields),
            "optional_request_fields": list(self.optional_request_fields),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class ModelValidation:
    """Structured result of model-specific input validation."""

    compatible: bool
    safe_reason: str | None = None


@dataclass(frozen=True)
class SourceMetadata:
    """Normalized patient/acquisition metadata contract (PR0159).

    Transport-neutral canonical names produced by each model package's own
    adapter from its own container/artifact representation.  The platform
    (runtime result transport, providers, mapper) depends ONLY on these
    normalized names — never on model-specific source field names.

    ``scan_date_time`` carries the raw source string; the Standard Result
    mapper normalizes it with the shared ``normalize_timestamp()``.
    Absent values use the contract's explicit absence convention
    (``None`` for the numeric age and for ``eoscan_version`` when no
    authoritative package-owned Eoscan version source exists, ``""`` for
    other strings).
    """

    patient_age: int | float | None = None
    referring_physician: str = field(default="", kw_only=True)
    scan_date_time: str = ""
    operator_id: str = ""
    hardware_version: str = ""
    eoscan_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe view of the normalized source metadata."""
        return {
            "patient_age": self.patient_age,
            "referring_physician": self.referring_physician,
            "scan_date_time": self.scan_date_time,
            "operator_id": self.operator_id,
            "hardware_version": self.hardware_version,
            "eoscan_version": self.eoscan_version,
        }


@dataclass(frozen=True)
class ModelMetadata:
    """Normalized model-level metadata contract (PR0159).

    ``model_method`` is the model package's own model-type/inference-method
    identifier, mapped inside the package from its artifact contract.  Absent
    -> ``""`` (the mapper falls back to the documented model_method rule).
    """

    model_method: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"model_method": self.model_method}


@dataclass(frozen=True)
class ModelMetrics:
    """Normalized model-owned release metrics contract (PR0159).

    Sensitivity/specificity are model-release metadata mapped inside each
    model package from its own artifact structure (e.g. held-out evaluation
    or final-fit training metrics).  Never computed by the platform; absent
    -> ``None`` (explicit absence, never fabricated).
    """

    sensitivity: float | None = None
    specificity: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"sensitivity": self.sensitivity, "specificity": self.specificity}


@dataclass(frozen=True)
class RuntimePrediction:
    """Structured internal runtime result sufficient for workflow projection.

    ``result`` carries the model-owned safe result mapping (for example
    probability/prediction/threshold or an external report payload).  The
    The platform executor copies it into the established workflow result shape
    without knowing model internals; this type never becomes a public API
    envelope by itself.

    PR0159: ``source_metadata`` / ``model_metadata`` / ``model_metrics`` carry
    the normalized metadata contract produced by the model package's own
    adapter, so the platform transports (providers, job layer, Standard Result
    mapper) consume canonical names only and never parse model-specific
    container/artifact internals.
    """

    workflow_id: str
    model_id: str = ""
    model_version: str = ""
    result: Mapping[str, Any] = field(default_factory=dict)
    safe_reason: str | None = None
    source_metadata: SourceMetadata = field(default_factory=SourceMetadata)
    model_metadata: ModelMetadata = field(default_factory=ModelMetadata)
    model_metrics: ModelMetrics = field(default_factory=ModelMetrics)


# ---------------------------------------------------------------------------
# Internal runtime error ownership categories
# ---------------------------------------------------------------------------


class ModelRuntimeError(ValueError):
    """Base for model-runtime failures with fixed safe reasons only.

    ``safe_reason`` is always a constant technical category.  Runtime errors
    must never carry source paths, S3 keys, artifact paths, raw exception
    text, tracebacks, tokens, environment variables or model package
    internals.  Public API error codes stay owned by platform adapters.
    """

    category: str = "model_runtime_error"

    def __init__(self, safe_reason: str) -> None:
        self.safe_reason = safe_reason
        super().__init__(safe_reason)


class ModelInputInvalidError(ModelRuntimeError):
    """The model-specific scientific input contract is not satisfied."""

    category = "model_input_invalid"


class ModelInputUnsupportedError(ModelRuntimeError):
    """The input is structurally parseable but unsupported by this model."""

    category = "model_input_unsupported"


class ModelConfigurationRequiredError(ModelRuntimeError):
    """Required model configuration (for example a model package) is absent."""

    category = "model_configuration_required"


class ModelPreprocessingFailedError(ModelRuntimeError):
    """Model-owned preprocessing or feature construction failed safely."""

    category = "model_preprocessing_failed"


class ModelInferenceFailedError(ModelRuntimeError):
    """Model-owned estimator execution or model-owned postprocessing failed."""

    category = "model_inference_failed"


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------


@runtime_checkable
class ModelRuntime(Protocol):
    """Common semantic runtime boundary of Model Runtime Contract v1.

    Structural protocol: implementations satisfy it by providing the three
    responsibilities below; no base class, shared behavior or identical
    internals are required (Bremen and Aramina keep their own scientific
    implementations).  Feature-stage tracing callbacks (for example
    ``on_features``) are optional runtime extensions owned by each
    implementation and are not part of the contract.
    """

    def model_requirements(self) -> ModelRequirements:
        """Describe the model-specific input contract."""
        ...

    def validate_model_input(self, input: ModelInput) -> ModelValidation:
        """Validate model-specific compatibility before scientific inference.

        Raises a ``ModelRuntimeError`` category when the runtime rejects the
        input; returns a structured ``ModelValidation`` for check-style use.
        """
        ...

    def predict_model(
        self,
        input: ModelInput,
        *,
        on_features: Callable[[Any], None] | None = None,
    ) -> RuntimePrediction:
        """Execute the complete model-specific scientific inference pipeline.

        Returns a structured internal runtime result or raises a
        ``ModelRuntimeError`` category (or an established model-specific safe
        error preserved by its platform adapter).  Never owns HTTP routing,
        authentication, public report URLs, job persistence or frontend
        behavior.
        """
        ...
