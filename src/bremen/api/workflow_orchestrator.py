"""Workflow orchestrator — single authoritative runtime entry point.

Connects canonical XRD normalization, workflow registry, and
per-workflow provider execution into one public execution path.

PR0076 — wire multi-workflow runtime into public inference paths.
PR0077 — structured event emission and job model integration.
"""

from __future__ import annotations

import hashlib
import logging
import time as _time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import h5py

from .h5_layouts import detect_layout
from .workflow_provider import (
    MultiWorkflowResult,
    WorkflowResult,
)
from .workflow_registry import WorkflowRegistry, WorkflowNotFoundError
from .xrd_normalization import (
    CanonicalXRDCase,
    NormalizationError,
)
from .event_schema import (
    JobEvent,
    EventType,
)
from .execution_context import WorkflowExecutionContext

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry bootstrap
# ---------------------------------------------------------------------------

_DEFAULT_REGISTRY: WorkflowRegistry | None = None


def get_default_registry() -> WorkflowRegistry:
    """Return the default workflow registry with all configured providers.

    Registers ``bremen`` and ``aramis``.  The registry is rebuilt
    on every call to pick up current ``ModelState`` (needed for
    test suites where model state changes between tests).
    """
    from .workflow_bremen import BremenProvider  # noqa: PLC0415
    from .workflow_aramis import AramisProvider  # noqa: PLC0415
    from .model_state import ModelState  # noqa: PLC0415

    registry = WorkflowRegistry()

    # --- Bremen provider ---
    bremen_model = ModelState.get_model()
    bremen_checksum = ""
    bremen_version = ""
    bremen_state = ModelState.get_instance()
    if bremen_model is not None:
        bremen_checksum = bremen_state._model_checksum or ""
        bremen_version = bremen_state._model_version or ""

    bremen_provider = BremenProvider(
        model_package=bremen_model,
        model_checksum=bremen_checksum,
        model_version=bremen_version,
    )
    registry.register(bremen_provider)

    # --- Aramis provider (scaffold) ---
    aramis_provider = AramisProvider()
    registry.register(aramis_provider)

    return registry


def _reset_default_registry() -> None:
    """Reset the default registry (for test isolation).

    This is automatically called when ModelState is reset.
    """
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = None


def _ensure_default_registry() -> WorkflowRegistry:
    """Return (and rebuild if needed) the default workflow registry.

    The registry is rebuilt whenever it is None (e.g., after
    ``_reset_default_registry`` or after ``ModelState`` changes).
    """
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = None  # Always rebuild to pick up current ModelState
    return get_default_registry()


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_workflow_request(
    h5_path: str,
    workflow_id: str = "bremen",
    *,
    target_scan_ref: str | None = None,
    control_scan_ref: str | None = None,
    registry: WorkflowRegistry | None = None,
    event_store: Any = None,  # BoundedEventStore | None
) -> MultiWorkflowResult:
    """Normalize an H5 container once, then execute the requested workflow.

    This is the single authoritative runtime entry point for all public
    inference paths.  It is NOT a permanent two-branch ``if/elif`` —
    workflow dispatch goes through the registry.

    Parameters
    ----------
    h5_path : Filesystem path to the staged H5 container.
    workflow_id : Explicit workflow selection.  Default ``"bremen"``
        exists only for backward API compatibility.
    target_scan_ref : Optional explicit target scan reference.
    control_scan_ref : Optional explicit control scan reference.
    registry : Optional pre-built registry.  When ``None``, the
        default registry is built via ``get_default_registry()``.
    event_store : Optional ``BoundedEventStore`` for structured event
        emission.  When ``None``, no job events are emitted (only
        application logging).

    Returns
    -------
    A ``MultiWorkflowResult`` with normalization status, per-workflow
    results, and overall status.
    """
    request_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    t_start = _time.monotonic()

    _log.info(
        "runtime.orchestration.started\t"
        "stage=orchestration\tstatus=started\t"
        "workflow_id=%s\trequest_id=%s\tjob_id=%s",
        workflow_id, request_id, job_id,
    )

    # --- Emit: request accepted ---
    _emit(event_store, job_id, request_id,
          EventType.REQUEST_ACCEPTED, "request", "accepted")

    # 1. Normalize the H5 exactly once
    _emit(event_store, job_id, request_id,
          EventType.NORMALIZATION_STARTED, "normalization", "started")

    try:
        canonical = _normalize_h5(h5_path, request_id=request_id)
    except NormalizationError:
        _log.warning(
            "runtime.normalization.failed\t"
            "stage=normalization\tstatus=failed\t"
            "workflow_id=%s\trequest_id=%s\tjob_id=%s",
            workflow_id, request_id, job_id,
        )
        _emit(event_store, job_id, request_id,
              EventType.NORMALIZATION_FAILED, "normalization", "failed")
        return MultiWorkflowResult(
            request_id=request_id,
            job_id=job_id,
            normalization_status="failed",
            source_checksum="",
            requested_workflows=(workflow_id,),
            workflows={},
            overall_status="normalization_failed",
        )
    except Exception:
        _log.exception(
            "runtime.normalization.failed\t"
            "stage=normalization\tstatus=failed\t"
            "workflow_id=%s\trequest_id=%s\tjob_id=%s",
            workflow_id, request_id, job_id,
        )
        _emit(event_store, job_id, request_id,
              EventType.NORMALIZATION_FAILED, "normalization", "failed")
        return MultiWorkflowResult(
            request_id=request_id,
            job_id=job_id,
            normalization_status="failed",
            source_checksum="",
            requested_workflows=(workflow_id,),
            workflows={},
            overall_status="normalization_failed",
        )

    _log.info(
        "runtime.normalization.completed\t"
        "stage=normalization\tstatus=completed\t"
        "measurement_count=%s\tworkflow_id=%s\trequest_id=%s\tjob_id=%s",
        len(canonical.measurements), workflow_id, request_id, job_id,
    )

    _emit(event_store, job_id, request_id,
          EventType.NORMALIZATION_COMPLETED, "normalization", "completed",
          details={
              "measurement_count": len(canonical.measurements),
              "layout": canonical.source_layout,
          })

    # 2. Resolve provider through registry
    resolved_registry = registry or get_default_registry()
    try:
        provider = resolved_registry.resolve(workflow_id)
    except WorkflowNotFoundError:
        _log.warning(
            "runtime.workflow.not_found\t"
            "stage=workflow\tstatus=failed\t"
            "workflow_id=%s\trequest_id=%s\tjob_id=%s",
            workflow_id, request_id, job_id,
        )
        _emit(event_store, job_id, request_id,
              EventType.WORKFLOW_NOT_FOUND, "workflow", "failed",
              workflow_id=workflow_id)
        return MultiWorkflowResult(
            request_id=request_id,
            job_id=job_id,
            normalization_status="completed",
            source_checksum=canonical.source_checksum,
            requested_workflows=(workflow_id,),
            workflows={
                workflow_id: WorkflowResult(
                    workflow_id=workflow_id,
                    status="failed",
                    error=f"Workflow '{workflow_id}' not found",
                ),
            },
            overall_status="failed",
        )

    _log.info(
        "runtime.workflow.resolved\t"
        "stage=workflow\tstatus=resolved\t"
        "workflow_id=%s\trequest_id=%s\tjob_id=%s",
        workflow_id, request_id, job_id,
    )

    _emit(event_store, job_id, request_id,
          EventType.WORKFLOW_RESOLVED, "workflow", "resolved",
          workflow_id=workflow_id,
          details={"workflow_id": workflow_id})

    # --- Emit: workflow started ---
    _emit(event_store, job_id, request_id,
          EventType.WORKFLOW_STARTED, "workflow", "started",
          workflow_id=workflow_id)

    # 3. Execute the provider with execution context for tracing
    # Build event sink if store is provided
    event_sink = None
    if event_store is not None:
        event_sink = lambda ev: event_store.append(job_id, ev)

    context = WorkflowExecutionContext(
        job_id=job_id,
        request_id=request_id,
        workflow_id=workflow_id,
        event_sink=event_sink,
        runtime_build_version="dev",
    )

    try:
        # Generic readiness check — any provider that reports model_ready=False
        # returns workflow_unavailable.  No workflow-id-specific branches.
        readiness = provider.readiness()
        if not readiness.model_ready:
            _emit(event_store, job_id, request_id,
                  EventType.WORKFLOW_FAILED, "workflow", "failed",
                  workflow_id=workflow_id,
                  details={"reason": "workflow_unavailable",
                           "model_ready": False})
            return MultiWorkflowResult(
                request_id=request_id, job_id=job_id,
                normalization_status="completed",
                source_checksum=canonical.source_checksum,
                requested_workflows=(workflow_id,),
                workflows={
                    workflow_id: WorkflowResult(
                        workflow_id=workflow_id,
                        status="failed",
                        error="Workflow unavailable — model not ready",
                    ),
                },
                overall_status="partial_success",
            )

        # Execute — pass context if provider accepts it
        try:
            wf_result = provider.execute(canonical, context)
        except TypeError:
            wf_result = provider.execute(canonical)
    except Exception as exc:
        _log.exception(
            "runtime.workflow.failed\t"
            "stage=workflow\tstatus=failed\t"
            "workflow_id=%s\trequest_id=%s\tjob_id=%s",
            workflow_id, request_id, job_id,
        )
        _emit(event_store, job_id, request_id,
              EventType.WORKFLOW_FAILED, "workflow", "failed",
              workflow_id=workflow_id)
        wf_result = WorkflowResult(
            workflow_id=workflow_id,
            status="failed",
            error=f"Workflow execution failed: {type(exc).__name__}",
        )

    if wf_result.status == "completed":
        _emit(event_store, job_id, request_id,
              EventType.WORKFLOW_COMPLETED, "workflow", "completed",
              workflow_id=workflow_id)
        overall_status = "completed"
    elif wf_result.error and ("configuration_required" in (wf_result.error or "") or "config" in (wf_result.error or "").lower()):
        _emit(event_store, job_id, request_id,
              EventType.WORKFLOW_FAILED, "workflow", "failed",
              workflow_id=workflow_id,
              details={"reason": "workflow_configuration_required"})
        overall_status = "workflow_configuration_required"
    else:
        _emit(event_store, job_id, request_id,
              EventType.WORKFLOW_FAILED, "workflow", "failed",
              workflow_id=workflow_id)
        overall_status = "failed"

    _log.info(
        "runtime.request.completed\t"
        "stage=request\tstatus=completed\t"
        "workflow_id=%s\toverall_status=%s\trequest_id=%s\tjob_id=%s",
        workflow_id, overall_status, request_id, job_id,
    )

    duration_ms = int((_time.monotonic() - t_start) * 1000)
    _emit(event_store, job_id, request_id,
          EventType.REQUEST_COMPLETED, "request", "completed",
          details={"overall_status": overall_status},
          duration_ms=duration_ms)

    return MultiWorkflowResult(
        request_id=request_id,
        job_id=job_id,
        normalization_status="completed",
        source_checksum=canonical.source_checksum,
        requested_workflows=(workflow_id,),
        workflows={workflow_id: wf_result},
        overall_status=overall_status,
    )


# ---------------------------------------------------------------------------
# Internal: H5 normalization
# ---------------------------------------------------------------------------


def _normalize_h5(
    h5_path: str,
    *,
    request_id: str = "",
) -> CanonicalXRDCase:
    """Open H5, detect layout, normalize to canonical.

    No patient identifiers are stored in the canonical case.
    The source H5 is opened read-only and not modified.
    """
    with h5py.File(h5_path, "r") as h5_file:
        adapter = detect_layout(h5_file)
        case = adapter.normalize_to_canonical(h5_file)

    _log.debug(
        "runtime.normalization.layout_detected\t"
        "stage=normalization\tstatus=layout_detected\t"
        "layout=%s\tlayout_version=%s\trequest_id=%s",
        case.source_layout, case.source_layout_version, request_id,
    )

    # Validate the canonical case
    from .xrd_normalization import validate_canonical_case  # noqa: PLC0415
    validate_canonical_case(case)

    return case


# ---------------------------------------------------------------------------
# Internal: event emission helper
# ---------------------------------------------------------------------------


def _emit(
    store: Any,
    job_id: str,
    request_id: str,
    event_type: EventType,
    stage: str,
    status: str,
    *,
    workflow_id: str | None = None,
    duration_ms: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Emit a structured event to *store* if it is not ``None``."""
    if store is None:
        return
    event = JobEvent(
        job_id=job_id,
        request_id=request_id,
        workflow_id=workflow_id,
        stage=stage,
        event_type=event_type.value,
        status=status,
        duration_ms=duration_ms,
        details=details or {},
    )
    try:
        store.append(job_id, event)
    except Exception:
        _log.debug(
            "runtime.event.emit.failed\t"
            "job_id=%s\tevent_type=%s",
            job_id, event_type.value,
        )
