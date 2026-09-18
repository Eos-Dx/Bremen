"""One platform execution path for every registered ModelRuntime.

No features, estimators, scientific preprocessing or decision thresholds live here.
Legacy canonical input preparation is an explicit descriptor policy.
"""

import logging
import time
import uuid

from bremen.contracts.model_runtime import (
    ModelInput,
    ModelInputInvalidError,
    ModelConfigurationRequiredError,
)
from bremen.contracts.execution import (
    ExecutionRequest,
    MultiWorkflowResult,
    WorkflowResult,
)
from bremen.platform.sources.binding import source_checksum, validate_source_binding
from bremen.platform.runtime.registry import get_default_registry, ModelNotFoundError
from bremen.contracts.events import JobEvent, EventType
from bremen.platform.events.context import WorkflowExecutionContext


def execute_model(descriptor, model_input, context=None, checksum=""):
    """Invoke the same validate/predict contract and project only public values."""
    try:
        validation = descriptor.runtime.validate_model_input(model_input)
        if not validation.compatible:
            if validation.safe_reason == "workflow_configuration_required":
                raise ModelConfigurationRequiredError(validation.safe_reason)
            raise ModelInputInvalidError(validation.safe_reason or "incompatible")
        if descriptor.bind_patient:
            try:
                validate_source_binding(
                    model_input.container_path, checksum, model_input.patient_id
                )
            except Exception:
                raise descriptor.binding_failure() from None

        def on_features(features):
            if descriptor.telemetry:
                descriptor.telemetry("features", descriptor, context, features)

        if descriptor.telemetry:
            descriptor.telemetry("prepared", descriptor, context)
            descriptor.telemetry("input", descriptor, context, model_input)
        prediction = descriptor.runtime.predict_model(
            model_input, on_features=on_features
        )
        result = descriptor.project(descriptor, prediction, model_input)
        if descriptor.telemetry:
            descriptor.telemetry("completed", descriptor, context, result)
        if context:
            context.emit("runtime.model.execution.completed", "model", "completed")
            context.emit("runtime.output.completed", "output", "completed")
        return result
    except Exception as exc:
        result = descriptor.failure(exc)
        if descriptor.telemetry:
            descriptor.telemetry("failed", descriptor, context, exc)
        return result


def execute(request: ExecutionRequest, *, registry=None, event_store=None):
    request_id = str(uuid.uuid4())
    job_id = request.job_id or str(uuid.uuid4())
    started = time.monotonic()
    workflow_id = request.workflow_id

    def emit(kind, stage, status, *, details=None, duration_ms=None, workflow=False):
        if event_store is None:
            return
        event = JobEvent(
            job_id=job_id,
            request_id=request_id,
            workflow_id=workflow_id if workflow else None,
            event_type=kind.value,
            stage=stage,
            status=status,
            details=details or {},
            duration_ms=duration_ms,
        )
        try:
            event_store.append(job_id, event)
        except Exception:
            pass  # Event sink failure never changes scientific execution.

    def envelope(status, results, checksum="", normalization="completed"):
        return MultiWorkflowResult(
            request_id, job_id, normalization, checksum, (workflow_id,), results, status
        )

    emit(EventType.REQUEST_ACCEPTED, "request", "accepted")
    registry = registry or get_default_registry()
    try:
        descriptor = registry.resolve(workflow_id)
    except ModelNotFoundError:
        descriptor = None
    emit(EventType.NORMALIZATION_STARTED, "normalization", "started")
    try:
        checksum = source_checksum(request.container_path)
        canonical = None
        if descriptor is not None and descriptor.legacy_input:
            from bremen.platform.sources.legacy_input import normalize_legacy_input

            canonical = normalize_legacy_input(
                request.container_path, workflow_id=workflow_id
            )
        measurements = getattr(canonical, "measurements", ())
    except Exception:
        emit(EventType.NORMALIZATION_FAILED, "normalization", "failed")
        return envelope("normalization_failed", {}, normalization="failed")
    emit(
        EventType.NORMALIZATION_COMPLETED,
        "normalization",
        "completed",
        details={
            "measurement_count": len(measurements),
            "layout": getattr(canonical, "source_layout", "raw_container"),
        },
    )
    if descriptor is None:
        emit(EventType.WORKFLOW_NOT_FOUND, "workflow", "failed", workflow=True)
        return envelope(
            "failed",
            {
                workflow_id: WorkflowResult(
                    workflow_id, "failed", error=f"Workflow '{workflow_id}' not found"
                )
            },
            checksum,
        )
    emit(
        EventType.WORKFLOW_RESOLVED,
        "workflow",
        "resolved",
        workflow=True,
        details={"workflow_id": workflow_id},
    )
    emit(EventType.WORKFLOW_STARTED, "workflow", "started", workflow=True)
    if not descriptor.model_ready:
        emit(
            EventType.WORKFLOW_FAILED,
            "workflow",
            "failed",
            workflow=True,
            details={"reason": "workflow_unavailable", "model_ready": False},
        )
        return envelope(
            "partial_success",
            {
                workflow_id: WorkflowResult(
                    workflow_id,
                    "failed",
                    error="Workflow unavailable — model not ready",
                )
            },
            checksum,
        )
    context = WorkflowExecutionContext(
        job_id=job_id,
        request_id=request_id,
        workflow_id=workflow_id,
        model_id=request.model_id or None,
        event_sink=(lambda ev: event_store.append(job_id, ev)) if event_store else None,
        runtime_build_version="dev",
    )
    model_input = ModelInput(
        workflow_id=workflow_id,
        measurements=measurements,
        canonical=canonical,
        container_path=request.container_path,
        patient_id=request.patient_id,
        target_side=request.target_side,
        parameters=request.parameters,
    )
    result = execute_model(descriptor, model_input, context, checksum)
    status = "completed" if result.status == "completed" else "failed"
    if result.error and "config" in result.error.lower():
        status = "workflow_configuration_required"
    emit(
        EventType.WORKFLOW_COMPLETED
        if status == "completed"
        else EventType.WORKFLOW_FAILED,
        "workflow",
        "completed" if status == "completed" else "failed",
        workflow=True,
        details=(
            {"reason": "workflow_configuration_required"}
            if status == "workflow_configuration_required"
            else {"reason": result.error,
                  "failure_stage": result.failure_stage,
                  "reason_code": result.error}
            if status == "failed" and descriptor.failure_event_reason
            else None
        ),
    )
    emit(
        EventType.REQUEST_COMPLETED,
        "request",
        "completed",
        details={"overall_status": status},
        duration_ms=int((time.monotonic() - started) * 1000),
    )
    logging.getLogger(__name__).info(
        "runtime.request.completed\tworkflow_id=%s\toverall_status=%s",
        workflow_id,
        status,
    )
    return envelope(status, {workflow_id: result}, checksum)


def run_workflow_request(
    h5_path,
    workflow_id,
    *,
    registry=None,
    event_store=None,
    model_id=None,
    job_id=None,
    patient_id="",
    target_side="",
    parameters=None,
    target_scan_ref=None,
    control_scan_ref=None,
):
    """Explicit application request translation; all execution goes through execute()."""
    return execute(
        ExecutionRequest(
            h5_path,
            workflow_id,
            model_id or "",
            job_id or "",
            patient_id,
            target_side,
            parameters or {},
        ),
        registry=registry,
        event_store=event_store,
    )
