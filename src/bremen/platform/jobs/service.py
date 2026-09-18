"""Job submission, lifecycle and event-query application operations."""

from __future__ import annotations
from bremen.platform.jobs.values import _clean_metadata_field
from bremen.platform.reports.service import _generate_job_reports
from bremen.platform.reports.service import _register_default_providers
from bremen.platform.jobs.values import _utc_now

import logging
import uuid as _uuid
from typing import Any


from bremen.contracts.events import (
    JobEvent,
)
from bremen.platform.jobs.models import (
    AnalysisJob,
    WorkflowRun,
)
from bremen.contracts.reports import (
    REPORT_STATUS_AVAILABLE,
)
from bremen.platform.runtime.executor import run_workflow_request
from bremen.platform.runtime.registry import RuntimeRegistry


# ---------------------------------------------------------------------------
# Shared in-memory state (process-local, ephemeral)
# ---------------------------------------------------------------------------

# Store persistent state on ``bremen`` package so it survives
# ``bremen.api.*`` module reload (same strategy as PR0076 ModelState fix).
from bremen.platform.jobs.repository import (
    _event_store,
    _jobs,
    _report_providers,
    _staged_uploads,
    _jobs_lock,
    _providers_lock,
    _uploads_lock,
)

_log = logging.getLogger(__name__)

# Staged uploads registry
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Job creation and management
# ---------------------------------------------------------------------------


def _selected_aramina_request(
    model_id: str | None,
    workflow_id: str,
    payload: dict[str, Any],
) -> tuple[str, Any]:
    """Resolve selected model routing and validate only its local input fields."""
    from bremen.platform.models.registry import get_model_entry
    from bremen.contracts.request import AnalysisParameters
    from bremen.model_packages.aramina_v0213.inference import (
        _build_aramina_request_json,
    )

    entry = get_model_entry(model_id) if model_id else None
    selected_workflow = entry.workflow_id if entry is not None else workflow_id
    if selected_workflow != "aramina":
        return workflow_id, None
    fields = _build_aramina_request_json(
        patient_id=payload.get("patient_id", ""),
        target_side=payload.get("target_side", ""),
        analysis_author=payload.get("analysis_author", ""),
        prediction_comment=payload.get("prediction_comment", ""),
    )
    return "aramina", AnalysisParameters(
        container_id="",
        source_id="",
        **fields,
    )


def create_analysis_job(
    container_id: str = "",
    *,
    workflow_id: str,
    h5_path: str = "",
    model_id: str | None = None,
    registry: RuntimeRegistry | None = None,
    source_key: str = "",
    patient_display_name: str = "",
    aramina_request: Any = None,
    target_side: str = "",
    analysis_author: str = "",
    prediction_comment: str = "",
) -> AnalysisJob:
    """Create and execute an analysis job synchronously.

    The job runs through the orchestrator and events are captured
    in the shared ``_event_store``.

    Parameters
    ----------
    container_id : Legacy container_id for backward compatibility.
    workflow_id : The explicitly selected workflow to execute.
    h5_path : Legacy explicit filesystem path.  For the new Control Room
        contract, use model_id with resolve_source() instead.
    model_id : Optional model_id for model selection.  If not provided
        and exactly one model is available, the default is used.
    registry : Optional pre-built workflow registry.
    """
    job_id = str(_uuid.uuid4())
    request_id = str(_uuid.uuid4())
    created_at = _utc_now()

    # Resolve model_id if not provided
    if model_id is None:
        from bremen.platform.models.catalog import resolve_model  # noqa: PLC0415

        try:
            model_id = resolve_model(None, workflow_id=workflow_id)
        except Exception as exc:
            # Cannot determine model — fail closed
            job = AnalysisJob(
                job_id=job_id,
                request_id=request_id,
                created_at=created_at,
                started_at=_utc_now(),
                overall_status="failed",
                input_summary={
                    "container_id": container_id or "synthetic",
                    "workflow_id": workflow_id,
                    "error": str(exc),
                },
                normalization_summary={},
                requested_workflows=(workflow_id,),
            )
            with _jobs_lock:
                _jobs[job_id] = job
            return job

    from bremen.platform.models.registry import get_model_entry

    selected_entry = get_model_entry(model_id) if model_id else None
    if selected_entry is not None and selected_entry.workflow_id == "aramina":
        workflow_id = "aramina"
    if workflow_id == "aramina":
        from bremen.model_packages.aramina_v0213.errors import AraminaWorkflowError
        from bremen.model_packages.aramina_v0213.inference import (
            _build_aramina_request_json,
        )

        if aramina_request is None:
            raise AraminaWorkflowError("ARAMINA_INVALID_REQUEST")
        _build_aramina_request_json(
            patient_id=aramina_request.patient_id,
            target_side=aramina_request.target_side,
            analysis_author=aramina_request.analysis_author,
            prediction_comment=aramina_request.prediction_comment,
        )

    # Aramina path: analysis_author/prediction_comment are already validated
    # and normalized into aramina_request above.  For the Standard Model Result
    # mapping (PR0157), we capture the request metadata on the job regardless
    # of workflow so the report mapper can surface it.  Missing values remain
    # "" per the contract's explicit absence convention (never fabricated).
    if aramina_request is not None:
        analysis_author = _clean_metadata_field(
            getattr(aramina_request, "analysis_author", ""),
        )
        prediction_comment = _clean_metadata_field(
            getattr(aramina_request, "prediction_comment", ""),
        )
    else:
        analysis_author = _clean_metadata_field(analysis_author)
        prediction_comment = _clean_metadata_field(prediction_comment)

    input_summary = {
        "container_id": container_id or "",
        "workflow_id": workflow_id,
        "model_id": model_id,
        "source_key": source_key or "",
        "patient_display_name": patient_display_name or "",
        # PR0141: Aramina inference identity includes the requested side.
        # Bremen leaves this empty so its duplicate identity is unchanged.
        "target_side": target_side if target_side in {"left", "right"} else "",
        # PR0157: additive request metadata consumed by the Standard Model
        # Result mapper.  Absent values stay empty strings (never fabricated).
        # Existing consumers ignore unknown input_summary keys; job identity is
        # keyed by source_key/workflow_id/model_id/target_side (unchanged).
        "analysis_author": analysis_author,
        "prediction_comment": prediction_comment,
    }

    job = AnalysisJob(
        job_id=job_id,
        request_id=request_id,
        created_at=created_at,
        started_at=_utc_now(),
        overall_status="running",
        input_summary=input_summary,
        normalization_summary={},
        requested_workflows=(workflow_id,),
    )
    # Insert job under lock — readers see a consistent initial state
    with _jobs_lock:
        _jobs[job_id] = job

    # Run the orchestrator with event capture (no lock held — may take seconds)
    # In catalog mode, construct a fresh provider for the selected model
    from bremen.platform.models.registry import get_registry  # noqa: PLC0415

    _reg = get_registry()
    if _reg.catalog_status != "not_configured" and _reg.available_count > 0:
        # Catalog mode — use get_descriptor_for_model to bind the package
        from bremen.platform.runtime.registry import get_descriptor_for_model  # noqa: PLC0415
        from bremen.platform.runtime.registry import RuntimeRegistry  # noqa: PLC0415

        provider = get_descriptor_for_model(model_id)
        cat_registry = RuntimeRegistry()
        cat_registry.register(provider)
        mw_result = run_workflow_request(
            h5_path=h5_path,
            workflow_id=workflow_id,
            registry=cat_registry,
            event_store=_event_store,
            model_id=model_id,
            job_id=job_id,
            patient_id=getattr(aramina_request, "patient_id", ""),
            target_side=getattr(aramina_request, "target_side", ""),
            parameters={
                "analysis_author": analysis_author,
                "prediction_comment": prediction_comment,
            },
        )
    else:
        mw_result = run_workflow_request(
            h5_path=h5_path,
            workflow_id=workflow_id,
            registry=registry,
            event_store=_event_store,
            model_id=model_id,
            job_id=job_id,
            patient_id=getattr(aramina_request, "patient_id", ""),
            target_side=getattr(aramina_request, "target_side", ""),
            parameters={
                "analysis_author": analysis_author,
                "prediction_comment": prediction_comment,
            },
        )

    # Update job from result
    wf_result = mw_result.workflows.get(workflow_id)

    now = _utc_now()

    if mw_result.normalization_status == "failed":
        with _jobs_lock:
            job.overall_status = "failed"
            job.completed_at = now
        return job

    with _jobs_lock:
        job.normalization_summary = {
            "measurement_count": None,
            "layout": None,
        }

        if wf_result:
            if wf_result.status == "completed":
                job.overall_status = "completed"
            elif wf_result.status == "failed":
                # Propagate orchestrator overall_status when it is more
                # specific than plain "failed" (e.g. workflow_configuration
                # required by existing Bremen configuration gates).
                if mw_result.overall_status in ("workflow_configuration_required",):
                    job.overall_status = mw_result.overall_status
                else:
                    job.overall_status = "failed"

            # Extract model identity from result payload if available.
            # For failed workflows, payload may be None — fall back to
            # registry entry model_version so it is never empty.
            result_model_id = model_id
            result_model_version = None
            if wf_result.payload:
                result_model_version = wf_result.payload.get("model_version")
            if not result_model_version and model_id:
                from bremen.platform.models.registry import get_model_entry  # noqa: PLC0415

                _reg_entry = get_model_entry(model_id)
                if _reg_entry is not None:
                    result_model_version = _reg_entry.model_version

            job.workflow_runs[workflow_id] = WorkflowRun(
                workflow_id=workflow_id,
                status=wf_result.status,
                model_identity={
                    "model_id": result_model_id or "",
                    "model_version": result_model_version or "",
                },
                result_summary=wf_result.payload or {},
                failure=wf_result.error,
            )
            if (
                workflow_id == "aramina"
                and wf_result.error == "ARAMINA_UNSUPPORTED_INPUT"
            ):
                from bremen.platform.reports.diagnostics import unsupported_input_details

                # PR0142: the allowlisted preprocessing subdiagnostic already
                # carries the release tag, so no artifact internals are read
                # here. Aramina entries keep the artifact on disk, not in
                # _package, so reading it here would be both wrong and unsafe.
                diagnostic = getattr(wf_result, "preprocessing_diagnostic", None)
                job.workflow_runs[
                    workflow_id
                ].failure_details = unsupported_input_details(
                    patient_display_name,
                    aramina_request.target_side.strip().lower(),
                    result_model_version or "",
                    stage=getattr(wf_result, "failure_stage", None),
                    model_id=result_model_id or "",
                    requested_patient_id=aramina_request.patient_id,
                    resolved_container_id=container_id or "",
                    preprocessing_release=(
                        diagnostic.get("preprocessing_release", "")
                        if isinstance(diagnostic, dict)
                        else ""
                    ),
                    preprocessing_diagnostic=diagnostic,
                )

        job.completed_at = now

    # Generate reports (uses providers lock internally)
    _register_default_providers()
    _generate_job_reports(job)

    # Emit report-completed event only when at least one report is available
    for wid, rm in job.reports.items():
        if rm.status == REPORT_STATUS_AVAILABLE:
            evt = JobEvent(
                job_id=job_id,
                request_id=request_id,
                workflow_id=wid,
                stage="report",
                event_type="runtime.report.completed",
                status="completed",
                details={
                    "report_id": rm.report_id,
                    "report_schema_version": rm.report_schema_version,
                    "report_status": rm.status,
                },
            )
            _event_store.append(job_id, evt)
            break  # one report-completed per job

    return job


def list_analysis_jobs(
    model_id: str | None = None,
    workflow_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return safe metadata for recent jobs, optionally filtered.

    Parameters
    ----------
    model_id : If provided, return only jobs created with this model_id.
    workflow_id : If provided, return only jobs with this workflow_id.
    """
    with _jobs_lock:
        jobs_snapshot = list(_jobs.values())
    summaries = []
    for j in jobs_snapshot[-20:]:
        summary = {
            "job_id": j.job_id,
            "created_at": j.created_at,
            "overall_status": j.overall_status,
            "requested_workflows": list(j.requested_workflows),
        }

        # Add model information from input_summary
        if j.input_summary:
            summary["model_id"] = j.input_summary.get("model_id")
            summary["source_key"] = j.input_summary.get("source_key", "")
            # PR0141: expose the requested side so clients can distinguish
            # left/right runs for the same source and model. Empty for Bremen.
            summary["target_side"] = j.input_summary.get("target_side", "")
            pdn = j.input_summary.get("patient_display_name", "")
            summary["patient_display_name"] = pdn
            summary["source_display_name"] = (
                pdn
                or j.input_summary.get("filename")
                or j.input_summary.get("container_id")
                or "Patient"
            )

        # Add decision information from first workflow run
        if j.workflow_runs and isinstance(j.workflow_runs, dict):
            first_wid = next(iter(j.workflow_runs), None)
            if first_wid is not None:
                wf_run = j.workflow_runs[first_wid]
                if wf_run.result_summary:
                    summary["decision_code"] = wf_run.result_summary.get(
                        "decision_code"
                    )
                    summary["decision_display_name"] = wf_run.result_summary.get(
                        "decision_display_name"
                    )
                    summary["triage_recommendation"] = wf_run.result_summary.get(
                        "triage_recommendation"
                    )
                if wf_run.model_identity:
                    summary["model_version"] = wf_run.model_identity.get(
                        "model_version"
                    )

        # Add report availability
        has_available = any(
            rm.status == REPORT_STATUS_AVAILABLE for rm in j.reports.values()
        )
        # Failed jobs never have available reports
        is_failed = j.overall_status in ("failed", "normalization_failed")
        summary["report_available"] = has_available and not is_failed
        # Derive report_deleted: job completed but no available report
        # (soft-deleted via delete_report action)
        summary["report_deleted"] = (
            not summary["report_available"]
            and j.overall_status == "completed"
            and len(j.reports) > 0
        )

        # Apply model_id filter (server-side)
        if model_id is not None:
            job_model_id = j.input_summary.get("model_id") if j.input_summary else None
            if job_model_id != model_id:
                continue

        # Apply workflow_id filter (server-side)
        if workflow_id is not None:
            if workflow_id not in j.requested_workflows:
                continue

        summaries.append(summary)
    return summaries


def get_job_events(job_id: str, since_sequence: int = 0) -> list[dict[str, Any]]:
    """Return events for a job, optionally since a sequence cursor."""
    events = _event_store.get_events(job_id, since_sequence=since_sequence)
    return [e.to_dict() for e in events]


# ---------------------------------------------------------------------------
# Rerun guard and report deletion
# ---------------------------------------------------------------------------


def reset_for_tests() -> None:
    """Clear all jobs, events, report providers, staged uploads, and
    source registry entries (test-only).

    Does NOT remove persistent package-level references — only
    clears internal state so that subsequent test logic sees
    a clean workspace.
    """
    _event_store.reset_for_tests()
    with _jobs_lock:
        _jobs.clear()
    with _providers_lock:
        _report_providers.clear()
    with _uploads_lock:
        _staged_uploads.clear()
    from bremen.platform.sources.registry import reset_for_tests as _reset_source_registry  # noqa: PLC0415

    _reset_source_registry()
