"""Transport model-owned values into frozen public workflow envelopes."""

import uuid
from typing import Any, Mapping

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


def _aramina_error_from_details(details: Any):
    """Rebuild an allowlisted ``AraminaWorkflowError`` from Worker details.

    IR-05: a candidate Worker transport carries only JSON-safe, already
    sanitized fields.  Anything outside the existing public vocabulary is
    rejected here so malformed details can never reach a public projection.
    """
    from bremen.model_packages.aramina_v0213.errors import (
        FAILURE_STAGES,
        AraminaWorkflowError,
        _SAFE_FAILURES,
    )

    allowed = {"aramina_error_code", "failure_stage", "preprocessing_diagnostic"}
    if not isinstance(details, Mapping) or set(details) - allowed:
        return None
    code = details.get("aramina_error_code")
    if not isinstance(code, str) or code not in _SAFE_FAILURES:
        return None

    stage = None
    diagnostic = None
    if code == "ARAMINA_UNSUPPORTED_INPUT":
        raw_stage = details.get("failure_stage")
        if raw_stage is not None:
            if not isinstance(raw_stage, str) or raw_stage not in FAILURE_STAGES:
                return None
            stage = raw_stage
        raw_diagnostic = details.get("preprocessing_diagnostic")
        if raw_diagnostic is not None:
            from bremen.model_packages.aramina_v0213.preprocessing import (  # noqa: PLC0415
                safe_preprocessing_diagnostic,
            )

            if not isinstance(raw_diagnostic, Mapping):
                return None
            candidate = dict(raw_diagnostic)
            if any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in candidate.items()
            ):
                return None
            sanitized = safe_preprocessing_diagnostic(
                candidate, candidate.get("preprocessing_release", "")
            )
            if sanitized != candidate:
                return None
            diagnostic = sanitized

    return AraminaWorkflowError(
        code, stage=stage, preprocessing_diagnostic=diagnostic
    )


def aramina_failure(exc):
    from bremen.model_packages.aramina_v0213.errors import (
        AraminaWorkflowError,
        _safe_stage,
    )

    if isinstance(exc, ModelInputInvalidError):
        exc = AraminaWorkflowError("ARAMINA_INVALID_REQUEST")

    # IR-05 candidate path: reconstruct the allowlisted Aramina failure from
    # transported Worker details.  Details outside the existing public
    # vocabulary are ignored, so malformed/arbitrary payloads can never
    # become public fields.
    if not isinstance(exc, AraminaWorkflowError):
        exc = _aramina_error_from_details(getattr(exc, "details", None))

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
