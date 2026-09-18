"""Transport model-owned values into frozen public workflow envelopes."""

import uuid
from bremen.contracts.execution import WorkflowResult
from bremen.contracts.model_runtime import (
    RuntimePrediction,
    ModelInputInvalidError,
    ModelConfigurationRequiredError,
    ModelInferenceFailedError,
    ModelRuntimeError,
)


def project_bremen(
    descriptor, prediction: RuntimePrediction, model_input
) -> WorkflowResult:
    """Project a contract runtime result into the established payload shape.

    The provider never performs model arithmetic; it only copies the
    model-owned result mapping into the existing payload fields and adds
    provider-held platform metadata (prediction id, checksum, versions).
    """
    result = prediction.result
    result_envelope = WorkflowResult(
        workflow_id=descriptor.workflow_id,
        status="completed",
        payload={
            "prediction_id": str(uuid.uuid4()),
            "model_version": descriptor.model_version or "unknown",
            "model_checksum": descriptor.checksum or "",
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

    measurements = model_input.measurements
    for side in ("left", "right"):
        key = f"{side}_measurement_count"
        result_envelope.payload[key] = prediction.result.get(
            key,
            sum(getattr(m, "side", None) == side.upper() for m in measurements),
        )
    return result_envelope


def project_aramina(descriptor, prediction, model_input):
    payload = {
        "workflow_id": descriptor.workflow_id,
        "model_id": descriptor.model_id,
        "model_version": descriptor.model_version,
        "technical_demo_only": True,
        "scientifically_certified": False,
        "external_report": dict(prediction.result),
        "source_metadata": prediction.source_metadata.to_dict(),
        "model_metadata": prediction.model_metadata.to_dict(),
        "model_metrics": prediction.model_metrics.to_dict(),
    }
    if descriptor.clinical_stage == "research draft":
        payload["clinical_stage"] = "research draft"
    return WorkflowResult(descriptor.workflow_id, "completed", payload=payload)


def bremen_failure(exc):
    if isinstance(exc, ModelInputInvalidError):
        message = f"Incompatible: {exc.safe_reason}"
    elif isinstance(exc, ModelConfigurationRequiredError):
        message = "Workflow configuration required for multi-position input"
    elif isinstance(exc, ModelInferenceFailedError):
        message = "Model execution failed"
    elif isinstance(exc, ModelRuntimeError):
        message = f"Feature construction failed: {exc.safe_reason}"
    else:
        message = "Feature construction failed: invalid_scientific_profiles"
    return WorkflowResult("bremen", "failed", error=message)


def aramina_failure(exc):
    from bremen.model_packages.aramina_v0213.errors import (
        AraminaWorkflowError,
        _safe_stage,
    )

    if isinstance(exc, ModelInputInvalidError):
        exc = AraminaWorkflowError("ARAMINA_INVALID_REQUEST")
    if not isinstance(exc, AraminaWorkflowError):
        return WorkflowResult("aramina", "failed", error="ARAMINA_EXECUTION_FAILED")
    unsupported = exc.code == "ARAMINA_UNSUPPORTED_INPUT"
    return WorkflowResult(
        "aramina",
        "failed",
        error=exc.code,
        failure_stage=_safe_stage(exc.stage) if unsupported else None,
        preprocessing_diagnostic=(
            exc.preprocessing_diagnostic
            if unsupported and exc.stage == "preprocessing_contract"
            else None
        ),
    )
