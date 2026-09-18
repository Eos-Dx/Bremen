"""Frozen Bremen event projection. Observes execution; never computes predictions."""

import math
from bremen.contracts.model_runtime import (
    ModelInputInvalidError,
    ModelConfigurationRequiredError,
    ModelInferenceFailedError,
    ModelRuntimeError,
)


def bremen_events(phase, descriptor, context, value=None):
    if context is None:
        return
    if phase == "prepared":
        checksum_status = "verified" if descriptor.checksum else "not_configured"
        identity = {
            "model_id": descriptor.model_id,
            "model_version": descriptor.model_version or "unknown",
            "model_schema_version": "v0.1",
            "checksum_status": checksum_status,
        }
        context.emit(
            "runtime.artifact.verification.completed",
            "artifact",
            "completed",
            details={
                **identity,
                "adaptation_applied": descriptor.model_ready,
                "validation_status": "completed"
                if descriptor.model_ready
                else "failed",
            },
        )
        context.emit(
            "runtime.artifact.load.completed",
            "artifact",
            "completed",
            details={k: v for k, v in identity.items() if k != "model_schema_version"},
        )
        context.emit(
            "runtime.artifact.adaptation.completed",
            "artifact",
            "completed",
            details={
                "model_id": descriptor.model_id,
                "adaptation_applied": descriptor.model_ready,
            },
        )
        if descriptor.model_ready:
            context.emit(
                "runtime.model.validation.completed",
                "model",
                "completed",
                details=identity,
            )
    elif phase == "input":
        canonical = value.canonical
        details = {"layout": "raw_container", "compatible": True}
        if canonical is not None:
            measurements = value.measurements
            details = {
                "layout": canonical.source_layout,
                "compatible": True,
                "measurement_count": len(measurements),
                "left_measurement_count": sum(m.side == "LEFT" for m in measurements),
                "right_measurement_count": sum(m.side == "RIGHT" for m in measurements),
                "side_count": len({m.side for m in measurements}),
                "position_count": len({m.position for m in measurements}),
            }
        context.emit(
            "runtime.input.preparation.completed", "input", "completed", details=details
        )
    elif phase == "failed":
        if isinstance(value, (ModelInputInvalidError, ModelConfigurationRequiredError)):
            config = isinstance(value, ModelConfigurationRequiredError)
            context.emit(
                "runtime.input.preparation.failed",
                "input",
                "failed",
                details={
                    "reason": "workflow_configuration_required"
                    if config
                    else value.safe_reason,
                    "workflow_configuration_required": config,
                },
            )
        elif isinstance(value, ModelInferenceFailedError):
            context.emit("runtime.model.execution.failed", "model", "failed")
        else:
            reason = (
                value.safe_reason
                if isinstance(value, ModelRuntimeError)
                else "invalid_scientific_profiles"
            )
            context.emit(
                "runtime.features.failed",
                "features",
                "failed",
                details={"reason": reason},
            )
    elif phase == "features":
        values = value.feature_values
        names = value.feature_names
        expected_names = descriptor.runtime.feature_names
        context.emit(
            "runtime.features.completed",
            "features",
            "completed",
            details={"feature_schema_version": "v0.1", "produced_count": len(values)},
        )
        context.emit(
            "runtime.features.validation.completed",
            "features",
            "completed",
            details={
                "feature_schema_version": "v0.1",
                "expected_count": len(expected_names),
                "produced_count": len(values),
                "missing_count": sum(math.isnan(v) for v in values),
                "non_finite_count": sum(
                    not math.isfinite(v) and not math.isnan(v) for v in values
                ),
                "feature_order_valid": list(names) == list(expected_names),
                "schema_matched": len(values) == len(expected_names),
            },
        )
    elif phase == "completed":
        payload = value.payload
        context.emit(
            "runtime.inference.completed",
            "inference",
            "completed",
            details={
                "model_id": descriptor.model_id,
                "model_version": descriptor.model_version or "unknown",
                "output_schema": "bremen_logreg_output_v1",
                "output_names": ["probability", "prediction", "triage_recommendation"],
                "output_count": 3,
            },
        )
        probability = payload.get("probability")
        context.emit(
            "runtime.output.validation.completed",
            "output",
            "completed",
            details={
                "schema_valid": True,
                "output_count": 3,
                "all_finite": isinstance(probability, (int, float))
                and 0 <= probability <= 1,
            },
        )
        context.emit(
            "runtime.decision.completed",
            "decision",
            "completed",
            details={
                "decision_policy_id": payload.get("decision_policy_id"),
                "decision_policy_version": payload.get("decision_policy_version"),
                "decision_code": payload.get("decision_code"),
                "scientifically_certified": False,
            },
        )
