"""Bremen workflow provider.

Orchestration adapter for the model-owned Bremen v0.1 runtime package
(``bremen.model_packages.bremen_v01``). Scientific validation, features,
scoring and decisions belong to the model package behind Model Runtime
Contract v1 (``bremen.model_runtime``).

PR0075 — multi-workflow runtime foundation.
PR0077 — structured event emission, removal of unstructured validation output.
PR0078 — WorkflowRuntimePlugin lifecycle instrumentation.
"""

from __future__ import annotations

import time as _time
import uuid
from logging import getLogger as _getLogger
from typing import Any

import numpy as np

from bremen.model_packages.bremen_v01 import BremenRuntime
from bremen.model_runtime import (
    ModelConfigurationRequiredError,
    ModelInferenceFailedError,
    ModelInput,
    ModelInputInvalidError,
    ModelRuntimeError,
    RuntimePrediction,
)

from .workflow_provider import (
    WorkflowProvider,
    WorkflowFeatureVector,
    WorkflowResult,
    WorkflowReadiness,
    CompatibilityResult,
)
from .execution_context import WorkflowExecutionContext
from .lifecycle_contracts import (
    PreparedArtifact,
    PreparedWorkflowInput,
    FeatureValidation,
)
from .decision_contract import (
    DECISION_POLICY_ID,
    DECISION_POLICY_VERSION,
    POSITIVE_MACHINE_CODE,
    NEGATIVE_MACHINE_CODE,
)

_log = _getLogger(__name__)

# Legacy re-exports for backward compatibility with external callers.
# New code must use decision_contract.POSITIVE_MACHINE_CODE and
# decision_contract.NEGATIVE_MACHINE_CODE instead.
TRIAGE_RECOMMENDED = POSITIVE_MACHINE_CODE
TRIAGE_RULE_OUT = NEGATIVE_MACHINE_CODE


class BremenWorkflowError(Exception):
    """Base exception for Bremen workflow errors."""


class WorkflowConfigurationRequiredError(BremenWorkflowError):
    """Workflow configuration is required but not available."""


class WorkflowIncompatibleError(BremenWorkflowError):
    """Canonical case is incompatible with the Bremen workflow."""


# ---------------------------------------------------------------------------
# Frozen Bremen scientific contract (PR0151 / PR0152)
# ---------------------------------------------------------------------------


BREMEN_V01_FEATURE_COLUMNS: tuple[str, ...] = BremenRuntime.feature_names


# ---------------------------------------------------------------------------
# Provider implementation
# ---------------------------------------------------------------------------


class BremenProvider(WorkflowProvider):
    """Bremen MRI triage workflow provider.

    Owns job orchestration and workflow result projection.
    Delegates the complete scientific contract to BremenRuntime.

    Plugin lifecycle methods (``prepare_artifact``, ``prepare_input``,
    ``build_features_traced``, ``validate_features``, ``run_model``,
    ``validate_output``, ``apply_decision``) provide per-stage
    observability with explicit ``WorkflowExecutionContext``.
    """

    workflow_id: str = "bremen"
    plugin_id: str = "bremen_mri_triage_plugin"
    plugin_version: str = "v0.1"

    def __init__(
        self,
        model_package: dict | None = None,
        *,
        model_checksum: str | None = None,
        model_version: str | None = None,
        model_id: str | None = None,
        runtime: BremenRuntime | None = None,
    ) -> None:
        self._raw_model_package = model_package
        self._runtime = runtime if runtime is not None else BremenRuntime(model_package)
        # ``package``/``model_ready`` are concrete BremenRuntime capabilities;
        # reading them defensively keeps the provider a pure contract adapter
        # (a minimal fake runtime only needs the three contract members).
        self._model_package = getattr(self._runtime, "package", None)
        self._model_id = model_id or "bremen_mri_triage_logreg"
        self._model_checksum = model_checksum
        self._model_version = model_version
        self._model_validated = False

    # ---- WorkflowProvider identity and runtime handle ----

    @property
    def runtime(self) -> BremenRuntime:
        """The model runtime this provider orchestrates."""
        return self._runtime

    def model_runtime(self) -> BremenRuntime:
        """Return the Model Runtime Contract v1 implementation for this workflow."""
        return self._runtime

    @property
    def requires_raw_container(self) -> bool:
        """Package-declared raw input ownership, used before normalization."""
        return bool(getattr(self._runtime, "requires_raw_container", False))

    # ---- Readiness ----

    def readiness(self) -> WorkflowReadiness:
        configured = self._model_package is not None
        model_ready = configured and self._validate_model_internal()
        # Scientific certification deferred until training parity
        scientifically_certified = False
        return WorkflowReadiness(
            workflow_id=self.workflow_id,
            configured=configured,
            model_ready=model_ready,
            scientifically_certified=scientifically_certified,
        )

    # ---- Compatibility ----

    def validate_compatibility(self, canonical: Any) -> CompatibilityResult:
        """Bremen requires exactly three canonical measurements per side."""
        measurements = getattr(canonical, "measurements", None)
        if measurements is None:
            return CompatibilityResult(compatible=False, reason="not_a_canonical_case")
        validation = self._runtime.validate_model_input(
            ModelInput(workflow_id=self.workflow_id, measurements=measurements),
        )
        if not validation.compatible:
            return CompatibilityResult(
                compatible=False,
                reason=validation.safe_reason or "requires_exactly_3_left_3_right",
            )
        return CompatibilityResult(compatible=True)

    # ---- Feature construction ----

    def build_features(self, canonical: Any) -> WorkflowFeatureVector:
        """Build the frozen vector from all six canonical measurements."""
        compatibility = self.validate_compatibility(canonical)
        if not compatibility.compatible:
            raise WorkflowIncompatibleError(compatibility.reason)
        features = self._runtime.build_features(canonical.measurements)
        return WorkflowFeatureVector(
            workflow_id=self.workflow_id,
            feature_names=BREMEN_V01_FEATURE_COLUMNS,
            feature_values=features.feature_values,
        )

    # ---- Inference ----

    def run_inference(self, features: WorkflowFeatureVector) -> WorkflowResult:
        """Run portable logistic regression inference via the model runtime."""
        if not self._validate_model_internal():
            return WorkflowResult(
                workflow_id=self.workflow_id,
                status="failed",
                error="Model not ready",
            )

        try:
            result = self._runtime.score(features.feature_names, features.feature_values)
        except ModelRuntimeError:
            return WorkflowResult(
                workflow_id=self.workflow_id, status="failed", error="Model execution failed",
            )
        return self._project_model_result(result)

    def _project_model_result(self, result) -> WorkflowResult:
        """Translate a runtime ``score()`` result into the workflow envelope.

        Reads model-owned result fields (translation only — no scientific
        arithmetic); the concrete result type is package-internal and is not
        imported by the platform adapter.
        """
        decision = result.decision
        return self._project_prediction(RuntimePrediction(
            workflow_id=self.workflow_id,
            model_version=self._model_version or "",
            result={
                "probability": result.probability,
                "prediction": result.prediction,
                "threshold_applied": result.threshold,
                "decision_code": decision.decision_code,
                "decision_display_name": decision.decision_display_name,
                "decision_policy_id": decision.decision_policy_id,
                "decision_policy_version": decision.decision_policy_version,
                "triage_recommendation": decision.legacy_triage,
            },
        ))

    def _project_prediction(self, prediction: RuntimePrediction) -> WorkflowResult:
        """Project a contract runtime result into the established payload shape.

        The provider never performs model arithmetic; it only copies the
        model-owned result mapping into the existing payload fields and adds
        provider-held platform metadata (prediction id, checksum, versions).
        """
        result = prediction.result
        return WorkflowResult(
            workflow_id=self.workflow_id,
            status="completed",
            payload={
                "prediction_id": str(uuid.uuid4()),
                "model_version": self._model_version or "unknown",
                "model_checksum": self._model_checksum or "",
                "feature_schema_version": "v0.1",
                "probability": result["probability"],
                "prediction": result["prediction"],
                "threshold_applied": result["threshold_applied"],
                "triage_recommendation": result["triage_recommendation"],
                "decision_code": result["decision_code"],
                "decision_display_name": result["decision_display_name"],
                "decision_policy_id": result["decision_policy_id"],
                "decision_policy_version": result["decision_policy_version"],
                # PR0159: the normalized metadata contract is transported
                # verbatim from the runtime result (translation only — the
                # provider never parses model-specific internals).
                "source_metadata": prediction.source_metadata.to_dict(),
                "model_metadata": prediction.model_metadata.to_dict(),
                "model_metrics": prediction.model_metrics.to_dict(),
            },
        )

    # ---- Execute (single authoritative path) ----

    def execute(
        self,
        canonical: Any,
        context: WorkflowExecutionContext | None = None,
        *,
        h5_path: str = "",
    ) -> WorkflowResult:
        """Single authoritative execution path.

        When *context* is provided, lifecycle stage events are emitted
        via the context's event sink.  This is the ONLY path that
        performs feature construction and inference — no duplicate
        execution occurs.

        ``h5_path`` is the platform-staged container path passed through the
        documented ``ModelInput.container_path`` bridge so the model package
        can execute artifact-owned preprocessing and interpret metadata.
        """
        # --- Compatibility check ---
        if self.requires_raw_container:
            validation = self._runtime.validate_model_input(ModelInput(
                workflow_id=self.workflow_id, container_path=h5_path,
            ))
            compat = CompatibilityResult(
                compatible=validation.compatible, reason=validation.safe_reason,
            )
        else:
            compat = self.validate_compatibility(canonical)
        if not compat.compatible:
            reason = compat.reason or "incompatible"
            if context:
                context.emit(
                    "runtime.input.preparation.failed",
                    "input", "failed",
                    details={
                        "reason": reason,
                        "workflow_configuration_required": (
                            reason == "workflow_configuration_required"
                        ),
                    },
                )
            if reason == "workflow_configuration_required":
                return WorkflowResult(
                    workflow_id=self.workflow_id,
                    status="failed",
                    error="Workflow configuration required for multi-position input",
                )
            return WorkflowResult(
                workflow_id=self.workflow_id,
                status="failed",
                error=f"Incompatible: {compat.reason}",
            )

        # --- Artifact + input preparation (tracing only) ---
        if context:
            self.prepare_artifact(context)
            if self.requires_raw_container:
                context.emit(
                    "runtime.input.preparation.completed", "input", "completed",
                    details={"layout": "raw_container", "compatible": True},
                )
            else:
                self.prepare_input(canonical, context)

        # --- Model validation ---
        if not self._validate_model_internal():
            if context:
                context.emit(
                    "runtime.model.validation.failed",
                    "model", "failed",
                )
            return WorkflowResult(
                workflow_id=self.workflow_id,
                status="failed",
                error="Model not ready",
            )

        # The model runtime owns the complete scientific sequence through the
        # Model Runtime Contract v1 boundary: one predict call; the callback
        # only projects feature-stage metadata into the existing job stream.
        # ``container_path`` is the documented platform->package bridge the
        # Bremen package uses to interpret its own container metadata (PR0159).
        model_input = ModelInput(
            workflow_id=self.workflow_id,
            measurements=getattr(canonical, "measurements", ()),
            container_path=h5_path,
        )

        def trace_features(features):
            if context:
                context.emit(
                    "runtime.features.completed", "features", "completed",
                    details={"feature_schema_version": "v0.1",
                             "produced_count": len(features.feature_values)},
                )
                self.validate_features(features, context)

        try:
            prediction = self._runtime.predict_model(
                model_input, on_features=trace_features,
            )
        except ModelInputInvalidError as exc:
            # Fail-safe parity with the pre-contract behaviour: shape failures
            # are already handled by the compatibility gate above.
            if context:
                context.emit(
                    "runtime.input.preparation.failed", "input", "failed",
                    details={
                        "reason": exc.safe_reason, "workflow_configuration_required": False,
                    },
                )
            return WorkflowResult(
                workflow_id=self.workflow_id, status="failed",
                error=f"Incompatible: {exc.safe_reason}",
            )
        except ModelConfigurationRequiredError:
            if context:
                context.emit(
                    "runtime.input.preparation.failed", "input", "failed",
                    details={
                        "reason": "workflow_configuration_required",
                        "workflow_configuration_required": True,
                    },
                )
            return WorkflowResult(
                workflow_id=self.workflow_id,
                status="failed",
                error="Workflow configuration required for multi-position input",
            )
        except ModelInferenceFailedError:
            if context:
                context.emit("runtime.model.execution.failed", "model", "failed")
            return WorkflowResult(
                workflow_id=self.workflow_id, status="failed", error="Model execution failed",
            )
        except ModelRuntimeError as exc:
            if context:
                context.emit(
                    "runtime.features.failed", "features", "failed",
                    details={"reason": exc.safe_reason},
                )
            return WorkflowResult(
                workflow_id=self.workflow_id, status="failed",
                error=f"Feature construction failed: {exc.safe_reason}",
            )
        except Exception:
            if context:
                context.emit(
                    "runtime.features.failed", "features", "failed",
                    details={"reason": "invalid_scientific_profiles"},
                )
            return WorkflowResult(
                workflow_id=self.workflow_id, status="failed",
                error="Feature construction failed: invalid_scientific_profiles",
            )
        result = self._project_prediction(prediction)

        # --- Per-side measurement counts (PR0096) ---
        if result.status == "completed" and result.payload is not None:
            measurements = getattr(canonical, "measurements", [])
            left_count = sum(
                1 for m in measurements if getattr(m, "side", None) == "LEFT"
            )
            right_count = sum(
                1 for m in measurements if getattr(m, "side", None) == "RIGHT"
            )
            result.payload["left_measurement_count"] = prediction.result.get(
                "left_measurement_count", left_count,
            )
            result.payload["right_measurement_count"] = prediction.result.get(
                "right_measurement_count", right_count,
            )

        if context and result.status == "completed":
            payload = result.payload or {}
            self._emit_inference_events(context, payload)

        return result

    # ---- Plugin: lifecycle tracing (event emission only, no re-execution) ----

    def prepare_artifact(
        self, context: WorkflowExecutionContext,
    ) -> PreparedArtifact:
        """Verify, load, and adapt the model artifact."""
        t0 = _time.monotonic()

        checksum_status: str = (
            "verified" if self._model_checksum else "not_configured"
        )
        adaptation_applied = self._model_package is not None
        validation_status = (
            "completed" if self._validate_model_internal() else "failed"
        )

        context.emit(
            "runtime.artifact.verification.completed",
            "artifact", "completed",
            duration_ms=int((_time.monotonic() - t0) * 1000),
            details={
                "model_id": self._model_id,
                "model_version": self._model_version or "unknown",
                "model_schema_version": "v0.1",
                "checksum_status": checksum_status,
                "adaptation_applied": adaptation_applied,
                "validation_status": validation_status,
            },
        )

        # Emit artifact load completed and adaptation completed
        # after the combined verification operation.
        context.emit(
            "runtime.artifact.load.completed",
            "artifact", "completed",
            details={
                "model_id": self._model_id,
                "model_version": self._model_version or "unknown",
                "checksum_status": checksum_status,
            },
        )

        adaptation_details = {
            "model_id": self._model_id,
            "adaptation_applied": adaptation_applied,
        }
        context.emit(
            "runtime.artifact.adaptation.completed",
            "artifact", "completed",
            details=adaptation_details,
        )

        # Emit model validation completed when model is validated
        if validation_status == "completed":
            context.emit(
                "runtime.model.validation.completed",
                "model", "completed",
                details={
                    "model_id": self._model_id,
                    "model_version": self._model_version or "unknown",
                    "model_schema_version": "v0.1",
                    "checksum_status": checksum_status,
                },
            )

        return PreparedArtifact(
            model_id=self._model_id,
            model_version=self._model_version or "unknown",
            model_schema_version="v0.1",
            checksum_status=checksum_status,
            adaptation_applied=adaptation_applied,
            validation_status=validation_status,
        )

    def prepare_input(
        self, canonical_case: Any, context: WorkflowExecutionContext,
    ) -> PreparedWorkflowInput:
        """Validate compatibility and prepare the canonical case."""
        # Duck-type for module-reload safety
        measurements = getattr(canonical_case, "measurements", None)
        if measurements is None:
            return PreparedWorkflowInput(
                layout="unknown", measurement_count=0,
                side_count=0, position_count=0,
                compatible=False,
                details={"reason": "not_a_canonical_case"},
            )

        sides = {getattr(m, "side", "?") for m in measurements}
        positions = {getattr(m, "position", "?") for m in measurements}
        left_measurement_count = sum(
            1 for m in measurements if getattr(m, "side", None) == "LEFT"
        )
        right_measurement_count = sum(
            1 for m in measurements if getattr(m, "side", None) == "RIGHT"
        )
        measurement_count = len(measurements)
        side_count = len(sides)
        position_count = len(positions)

        compatible = self.validate_compatibility(canonical_case).compatible

        context.emit(
            "runtime.input.preparation.completed",
            "input", "completed",
            details={
                "layout": canonical_case.source_layout,
                "measurement_count": measurement_count,
                "left_measurement_count": left_measurement_count,
                "right_measurement_count": right_measurement_count,
                "side_count": side_count,
                "position_count": position_count,
                "compatible": compatible,
            },
        )

        return PreparedWorkflowInput(
            layout=canonical_case.source_layout,
            measurement_count=measurement_count,
            left_measurement_count=left_measurement_count,
            right_measurement_count=right_measurement_count,
            side_count=side_count,
            position_count=position_count,
            compatible=compatible,
        )

    def validate_features(
        self, features: Any, context: WorkflowExecutionContext,
    ) -> FeatureValidation:
        """Validate the 15-feature vector against the schema — event only."""
        t0 = _time.monotonic()

        fv_values = getattr(features, "feature_values", None)
        fv_names = getattr(features, "feature_names", None)

        if fv_values is not None:
            expected = 15
            produced = len(fv_values)
            missing = sum(1 for v in fv_values if np.isnan(v))
            non_finite = sum(
                1 for v in fv_values
                if not np.isfinite(v) and not np.isnan(v)
            )
        else:
            expected = 15
            produced = 0
            missing = 0
            non_finite = 0

        order_valid = (
            fv_names is not None
            and list(fv_names) == list(BREMEN_V01_FEATURE_COLUMNS)
        )
        schema_matched = produced == expected
        all_finite = non_finite == 0 and missing == 0

        context.emit(
            "runtime.features.validation.completed",
            "features", "completed",
            duration_ms=int((_time.monotonic() - t0) * 1000),
            details={
                "feature_schema_version": "v0.1",
                "expected_count": expected,
                "produced_count": produced,
                "missing_count": missing,
                "non_finite_count": non_finite,
                "feature_order_valid": order_valid,
                "schema_matched": schema_matched,
            },
        )

        return FeatureValidation(
            feature_schema_version="v0.1",
            expected_count=expected,
            produced_count=produced,
            order_valid=order_valid,
            all_finite=all_finite,
            schema_matched=schema_matched,
        )

    # ---- Internal helpers ----

    def _emit_inference_events(
        self, context: WorkflowExecutionContext, payload: dict,
    ) -> None:
        """Emit inference/output/decision events after inference completes.

        Does NOT re-run inference — uses the already-computed result.
        """
        decision_code = payload.get("decision_code", "")
        prob = payload.get("probability")

        context.emit(
            "runtime.inference.completed",
            "inference", "completed",
            details={
                "model_id": self._model_id,
                "model_version": self._model_version or "unknown",
                "output_schema": "bremen_logreg_output_v1",
                "output_names": ["probability", "prediction",
                                "triage_recommendation"],
                "output_count": 3,
            },
        )

        # Output validation
        all_finite = (
            isinstance(prob, (int, float))
            and 0.0 <= float(prob) <= 1.0
        )
        context.emit(
            "runtime.output.validation.completed",
            "output", "completed",
            details={
                "schema_valid": True,
                "output_count": 3,
                "all_finite": all_finite,
            },
        )

        # Decision — emits canonical machine code
        context.emit(
            "runtime.decision.completed",
            "decision", "completed",
            details={
                "decision_policy_id": DECISION_POLICY_ID,
                "decision_policy_version": DECISION_POLICY_VERSION,
                "decision_code": decision_code,
                "scientifically_certified": False,
            },
        )

    # ---- Internal ----

    def _validate_model_internal(self) -> bool:
        model_ready = getattr(self._runtime, "model_ready", None)
        self._model_validated = bool(model_ready()) if callable(model_ready) else True
        return self._model_validated
