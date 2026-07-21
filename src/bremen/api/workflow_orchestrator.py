"""Workflow orchestrator — single authoritative runtime entry point.

Connects canonical XRD normalization, workflow registry, and
per-workflow provider execution into one public execution path.

PR0076 — wire multi-workflow runtime into public inference paths.
"""

from __future__ import annotations

import hashlib
import logging
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

    Returns
    -------
    A ``MultiWorkflowResult`` with normalization status, per-workflow
    results, and overall status.
    """
    request_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    _log.info(
        "runtime.orchestration.started\t"
        "stage=orchestration\tstatus=started\t"
        "workflow_id=%s\trequest_id=%s\tjob_id=%s",
        workflow_id, request_id, job_id,
    )

    # 1. Normalize the H5 exactly once
    try:
        canonical = _normalize_h5(h5_path, request_id=request_id)
    except NormalizationError:
        _log.warning(
            "runtime.normalization.failed\t"
            "stage=normalization\tstatus=failed\t"
            "workflow_id=%s\trequest_id=%s\tjob_id=%s",
            workflow_id, request_id, job_id,
        )
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

    # 3. Execute the provider
    try:
        wf_result = provider.execute(canonical)
    except Exception as exc:
        _log.exception(
            "runtime.workflow.failed\t"
            "stage=workflow\tstatus=failed\t"
            "workflow_id=%s\trequest_id=%s\tjob_id=%s",
            workflow_id, request_id, job_id,
        )
        wf_result = WorkflowResult(
            workflow_id=workflow_id,
            status="failed",
            error=f"Workflow execution failed: {type(exc).__name__}",
        )

    overall_status = "completed" if wf_result.status == "completed" else "failed"

    _log.info(
        "runtime.request.completed\t"
        "stage=request\tstatus=completed\t"
        "workflow_id=%s\toverall_status=%s\trequest_id=%s\tjob_id=%s",
        workflow_id, overall_status, request_id, job_id,
    )

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
