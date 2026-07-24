"""Job API handler and SSE stream endpoint for the multi-workflow workspace.

Provides:
- ``POST /demo/api/jobs`` — create an analysis job
- ``GET /demo/api/jobs`` — list recent jobs
- ``GET /demo/api/jobs/{job_id}`` — get job status
- ``GET /demo/api/jobs/{job_id}/events`` — get job events
- ``GET /demo/api/jobs/{job_id}/events/stream`` — SSE event stream
- ``GET /demo/api/jobs/{job_id}/reports`` — list reports
- ``GET /demo/api/jobs/{job_id}/reports/{workflow_id}`` — get report

PR0077 — multi-workflow analysis workspace, event stream, and reports.
PR0082a — Control Room Data and Selection Foundation.
"""

from __future__ import annotations

import json as _json
import logging
import threading
import time as _time
import uuid as _uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from typing import Any

import bremen

from .event_store import BoundedEventStore
from .event_schema import (
    JobEvent,
    EventType,
    SCHEMA_VERSION,
    allowed_event_details,
)
from .job_models import (
    AnalysisJob,
    WorkflowRun,
    ReportMetadata,
)
from .report_provider import (
    ReportEnvelope,
    ReportProvider,
    REPORT_STATUS_AVAILABLE,
    REPORT_STATUS_UNAVAILABLE,
    REPORT_STATUS_FAILED,
)
from .workflow_orchestrator import run_workflow_request
from .workflow_registry import WorkflowRegistry
from .execution_trace import build_trace_from_events

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared in-memory state (process-local, ephemeral)
# ---------------------------------------------------------------------------

# Store persistent state on ``bremen`` package so it survives
# ``bremen.api.*`` module reload (same strategy as PR0076 ModelState fix).
_STORE_KEY = "_bremen_workspace_event_store"
_JOBS_KEY = "_bremen_workspace_jobs"
_PROVIDERS_KEY = "_bremen_workspace_report_providers"
_INIT_LOCK_KEY = "_bremen_workspace_init_lock"
_JOBS_LOCK_KEY = "_bremen_workspace_jobs_lock"
_PROVIDERS_LOCK_KEY = "_bremen_workspace_providers_lock"
_UPLOADS_KEY = "_bremen_workspace_staged_uploads"
_UPLOADS_LOCK_KEY = "_bremen_workspace_uploads_lock"


def _get_package_lock(key: str) -> threading.Lock:
    """Return (or create and store) a lock on the bremen package.

    The lock is stored on the package so it survives module reload.
    Uses a simple pattern since the inner setattr is unlikely to race
    fatally for locks (two locks are both valid), but adjacent to the
    double-checked singleton pattern for data objects.
    """
    lock = getattr(bremen, key, None)
    if lock is None:
        lock = threading.Lock()
        setattr(bremen, key, lock)
    return lock


def _get_or_create_store():
    s = getattr(bremen, _STORE_KEY, None)
    if s is not None:
        return s
    init_lock = _get_package_lock(_INIT_LOCK_KEY)
    with init_lock:
        s = getattr(bremen, _STORE_KEY, None)
        if s is not None:
            return s
        s = BoundedEventStore()
        setattr(bremen, _STORE_KEY, s)
        return s


def _get_or_create_jobs():
    j = getattr(bremen, _JOBS_KEY, None)
    if j is not None:
        return j
    init_lock = _get_package_lock(_INIT_LOCK_KEY)
    with init_lock:
        j = getattr(bremen, _JOBS_KEY, None)
        if j is not None:
            return j
        j = {}
        setattr(bremen, _JOBS_KEY, j)
        return j


def _get_or_create_providers():
    p = getattr(bremen, _PROVIDERS_KEY, None)
    if p is not None:
        return p
    init_lock = _get_package_lock(_INIT_LOCK_KEY)
    with init_lock:
        p = getattr(bremen, _PROVIDERS_KEY, None)
        if p is not None:
            return p
        p = {}
        setattr(bremen, _PROVIDERS_KEY, p)
        return p


def _get_or_create_uploads():
    u = getattr(bremen, _UPLOADS_KEY, None)
    if u is not None:
        return u
    init_lock = _get_package_lock(_INIT_LOCK_KEY)
    with init_lock:
        u = getattr(bremen, _UPLOADS_KEY, None)
        if u is not None:
            return u
        u = {}
        setattr(bremen, _UPLOADS_KEY, u)
        return u


# Module-level references that point to persistent bremen-package objects
_event_store = _get_or_create_store()
_jobs = _get_or_create_jobs()
_report_providers = _get_or_create_providers()
_staged_uploads = _get_or_create_uploads()

# Thread-safety locks for shared mutable state
_jobs_lock = _get_package_lock(_JOBS_LOCK_KEY)
_providers_lock = _get_package_lock(_PROVIDERS_LOCK_KEY)
_uploads_lock = _get_package_lock(_UPLOADS_LOCK_KEY)


# ---------------------------------------------------------------------------
# Staged uploads registry
# ---------------------------------------------------------------------------


class StagedUpload:
    """Record of a staged file upload."""

    def __init__(
        self,
        upload_id: str,
        h5_path: str,
        filename: str,
        size_bytes: int,
        created_at: str,
        consumed: bool = False,
    ) -> None:
        self.upload_id = upload_id
        self.h5_path = h5_path
        self.filename = filename
        self.size_bytes = size_bytes
        self.created_at = created_at
        self.consumed = consumed


def register_staged_upload(
    h5_path: str,
    filename: str,
    size_bytes: int,
) -> str:
    """Register a staged upload and return an opaque upload_id.

    The upload is stored in the in-memory registry and consumed
    when a job uses it.  The file is cleaned up after consumption
    or after a timeout period.
    """
    import uuid as _uuid
    upload_id = str(_uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    upload = StagedUpload(
        upload_id=upload_id,
        h5_path=h5_path,
        filename=filename,
        size_bytes=size_bytes,
        created_at=now,
    )
    with _uploads_lock:
        _staged_uploads[upload_id] = upload
    return upload_id


def resolve_upload(upload_id: str) -> str | None:
    """Resolve an upload_id to a local h5_path with ownership transfer.

    Returns None if the upload_id is unknown or already consumed.
    The upload entry is atomically removed from the registry and
    ownership of the temp file is transferred to the caller.
    """
    with _uploads_lock:
        upload = _staged_uploads.pop(upload_id, None)
        if upload is None:
            return None
        if upload.consumed:
            return None
        upload.consumed = True
        return upload.h5_path


def resolve_source(
    source_id: str | None,
    upload_id: str | None,
) -> str:
    """Resolve a source reference to a local filesystem path.

    Parameters
    ----------
    source_id : An opaque source_id for a catalog object, or None.
    upload_id : An opaque upload_id for a staged file, or None.

    Returns
    -------
    The resolved local filesystem h5_path.

    Raises
    ------
    ValueError
        If source resolution fails with a typed safe error.
    """
    from ..demo_config import read_demo_h5_config
    from ..h5_inputs import stage_h5_input
    from .source_registry import resolve_source_id as _resolve_source_id

    if source_id and upload_id:
        raise ValueError("Only one of source_id or upload_id may be provided.")

    if source_id:
        # Resolve S3 catalog source through opaque registry
        config = read_demo_h5_config()
        if config["h5_bucket"] is None:
            raise ValueError("H5 storage not configured. "
                             "Set BREMEN_DEMO_H5_BUCKET to enable catalog selection.")

        # Resolve via opaque registry — validates bucket, prefix, existence, expiry,
        # extension, and size constraints
        try:
            object_key, filename, size_bytes = _resolve_source_id(
                source_id,
                current_bucket=config["h5_bucket"],
                current_prefix=config["h5_prefix"],
            )
        except ValueError:
            # Re-raise the safe typed error from the registry
            raise

        # Validate size against current limit
        max_bytes = config["upload_max_bytes"]
        if size_bytes > max_bytes:
            raise ValueError(
                f"The selected source exceeds the maximum size limit."
            )

        # Construct S3 URI from server-side config only (no browser input)
        s3_uri = f"s3://{config['h5_bucket']}/{object_key}"
        try:
            staged_path = stage_h5_input(s3_uri)
            return str(staged_path)
        except (ValueError, OSError, IOError) as exc:
            # stage_h5_input raises ValueError on S3 download failure
            raise ValueError(
                "Could not download the selected source from storage."
            ) from exc

    elif upload_id:
        # Resolve upload from registry
        h5_path = resolve_upload(upload_id)
        if h5_path is None:
            raise ValueError(
                "The uploaded file is no longer available. "
                "Please re-upload the file."
            )
        return h5_path

    else:
        raise ValueError(
            "A source_id or upload_id is required to create an analysis job."
        )


def _cleanup_expired_uploads() -> None:
    """Remove expired uploads from the registry and clean up temp files.

    Uploads older than 1 hour are considered expired and are removed.
    File deletion is performed within the lock to prevent race conditions
    with concurrent consumption.
    """
    import os as _os
    now = datetime.now(timezone.utc)
    expiry_seconds = 3600  # 1 hour
    with _uploads_lock:
        expired_ids = []
        for uid, upload in list(_staged_uploads.items()):
            try:
                created = datetime.fromisoformat(upload.created_at)
                if (now - created).total_seconds() > expiry_seconds:
                    expired_ids.append(uid)
            except (ValueError, TypeError):
                expired_ids.append(uid)

        for uid in expired_ids:
            upload = _staged_uploads.pop(uid, None)
            if upload and upload.h5_path:
                try:
                    _os.unlink(upload.h5_path)
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# Report provider registration
# ---------------------------------------------------------------------------


def register_report_provider(provider: ReportProvider) -> None:
    """Register a report provider for a workflow."""
    with _providers_lock:
        _report_providers[provider.workflow_id] = provider


def _get_report_provider(workflow_id: str) -> ReportProvider | None:
    # Snapshot providers dict under lock for safe read
    with _providers_lock:
        providers = dict(_report_providers)
    return providers.get(workflow_id)


def _register_default_providers() -> None:
    """Register built-in report providers."""
    from .report_bremen import BremenReportProvider  # noqa: PLC0415
    from .report_aramis import AramisReportProvider  # noqa: PLC0415

    with _providers_lock:
        if "bremen" not in _report_providers:
            _report_providers["bremen"] = BremenReportProvider()
        if "aramis" not in _report_providers:
            _report_providers["aramis"] = AramisReportProvider()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Job creation and management
# ---------------------------------------------------------------------------


def create_analysis_job(
    container_id: str = "",
    workflow_id: str = "bremen",
    *,
    h5_path: str = "",
    model_id: str | None = None,
    registry: WorkflowRegistry | None = None,
) -> AnalysisJob:
    """Create and execute an analysis job synchronously.

    The job runs through the orchestrator and events are captured
    in the shared ``_event_store``.

    Parameters
    ----------
    container_id : Legacy container_id for backward compatibility.
    workflow_id : The workflow to execute (default "bremen").
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
        from .model_catalog import resolve_model  # noqa: PLC0415
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

    input_summary = {
        "container_id": container_id or "",
        "workflow_id": workflow_id,
        "model_id": model_id,
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
    from .model_registry import get_registry  # noqa: PLC0415
    _reg = get_registry()
    if _reg.catalog_status != "not_configured" and _reg.available_count > 0:
        # Catalog mode — use get_provider_for_model to bind the package
        from .workflow_orchestrator import get_provider_for_model  # noqa: PLC0415
        from .workflow_registry import WorkflowRegistry  # noqa: PLC0415
        provider = get_provider_for_model(model_id)
        cat_registry = WorkflowRegistry()
        cat_registry.register(provider)
        mw_result = run_workflow_request(
            h5_path=h5_path,
            workflow_id=workflow_id,
            registry=cat_registry,
            event_store=_event_store,
            model_id=model_id,
        )
    else:
        mw_result = run_workflow_request(
            h5_path=h5_path,
            workflow_id=workflow_id,
            registry=registry,
            event_store=_event_store,
            model_id=model_id,
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
                job.overall_status = "failed"

            # Extract model identity from result payload if available
            result_model_id = model_id
            result_model_version = None
            if wf_result.payload:
                result_model_version = wf_result.payload.get("model_version")

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


def get_analysis_job(job_id: str) -> AnalysisJob | None:
    """Return an analysis job by ID, or ``None``."""
    with _jobs_lock:
        return _jobs.get(job_id)


def list_analysis_jobs() -> list[dict[str, Any]]:
    """Return safe metadata for recent jobs."""
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
            summary["source_display_name"] = (
                j.input_summary.get("filename") or
                j.input_summary.get("container_id") or
                "Unknown"
            )

        # Add decision information from first workflow run
        if j.workflow_runs:
            first_wid = list(j.workflow_runs.keys())[0]
            wf_run = j.workflow_runs[first_wid]
            if wf_run.result_summary:
                summary["decision_code"] = wf_run.result_summary.get("decision_code")
                summary["decision_display_name"] = wf_run.result_summary.get(
                    "decision_display_name"
                )
                summary["triage_recommendation"] = wf_run.result_summary.get(
                    "triage_recommendation"
                )
            if wf_run.model_identity:
                summary["model_version"] = wf_run.model_identity.get("model_version")

        # Add report availability
        summary["report_available"] = any(
            rm.status == REPORT_STATUS_AVAILABLE
            for rm in j.reports.values()
        )

        summaries.append(summary)
    return summaries


def get_job_events(job_id: str, since_sequence: int = 0) -> list[dict[str, Any]]:
    """Return events for a job, optionally since a sequence cursor."""
    events = _event_store.get_events(job_id, since_sequence=since_sequence)
    return [e.to_dict() for e in events]


def get_job_reports(job_id: str) -> dict[str, Any]:
    """Return reports for a job, keyed by workflow_id."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return {"reports": {}, "job_id": job_id}
    # Snapshot report data under lock to avoid mutation during iteration
    with _jobs_lock:
        reports_snapshot = dict(job.reports)
    return {
        "reports": {
            wid: {
                "report_id": rm.report_id,
                "workflow_id": rm.workflow_id,
                "report_schema_version": rm.report_schema_version,
                "status": rm.status,
                "generated_at": rm.generated_at,
                "model_id": rm.model_id,
                "model_version": rm.model_version,
                "scientifically_certified": rm.scientifically_certified,
            }
            for wid, rm in reports_snapshot.items()
        },
        "job_id": job_id,
    }


def get_job_report(job_id: str, workflow_id: str) -> dict[str, Any]:
    """Return a specific workflow report, or unavailable."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return {
            "report": {"status": "job_not_found"},
            "job_id": job_id,
            "workflow_id": workflow_id,
        }

    provider = _get_report_provider(workflow_id)
    with _jobs_lock:
        wf_run = job.workflow_runs.get(workflow_id)

    if provider is None or wf_run is None:
        return {
            "report": {
                "status": REPORT_STATUS_UNAVAILABLE,
                "reason_code": "WORKFLOW_OR_REPORT_PROVIDER_NOT_CONFIGURED",
            },
            "job_id": job_id,
            "workflow_id": workflow_id,
        }

    # Generate the report fresh
    report = provider.generate_report(
        job_id=job_id,
        workflow_result=wf_run.result_summary,
        model_identity=wf_run.model_identity,
        readiness_snapshot=wf_run.readiness_snapshot,
    )
    return {
        "report": report.to_dict(),
        "job_id": job_id,
        "workflow_id": workflow_id,
    }


def _generate_job_reports(job: AnalysisJob) -> None:
    """Generate reports for all completed workflow runs.

    Caller must ensure exclusive access to *job.reports*.
    """
    for wid, wf_run in list(job.workflow_runs.items()):
        provider = _get_report_provider(wid)
        if provider is None:
            job.reports[wid] = ReportMetadata(
                report_id=str(_uuid.uuid4()),
                workflow_id=wid,
                report_schema_version="v0.1",
                status=REPORT_STATUS_UNAVAILABLE,
            )
            continue

        report = provider.generate_report(
            job_id=job.job_id,
            workflow_result=wf_run.result_summary,
            model_identity=wf_run.model_identity,
            readiness_snapshot=wf_run.readiness_snapshot,
        )

        job.reports[wid] = ReportMetadata(
            report_id=report.report_id,
            workflow_id=wid,
            report_schema_version=report.report_schema_version,
            status=report.workflow_status,
            generated_at=report.generated_at,
            model_id=report.model_id,
            model_version=report.model_version,
            scientifically_certified=report.scientifically_certified,
        )


# ---------------------------------------------------------------------------
# Job API route handlers
# ---------------------------------------------------------------------------


def handle_jobs_list(handler: BaseHTTPRequestHandler) -> None:
    """Handle GET /demo/api/jobs — list recent jobs."""
    data = {
        "jobs": list_analysis_jobs(),
        "storage_mode": _event_store.storage_mode,
        "retention_seconds": _event_store.retention_seconds,
        "max_jobs": _event_store.max_jobs,
    }
    _send_json(handler, 200, data)


def handle_jobs_create(handler: BaseHTTPRequestHandler) -> None:
    """Handle POST /demo/api/jobs — create an analysis job.

    Accepts the new Control Room contract with model_id, source_id/upload_id,
    and preserves legacy h5_path and container_id for backward compatibility.
    """
    body = _read_json_body(handler)
    if body is None:
        _send_json(handler, 400, {"error": "Invalid JSON body"})
        return

    # ---- Parse request body ----
    h5_path = body.get("h5_path", "")
    workflow_id = body.get("workflow_id", "bremen")
    container_id = body.get("container_id", "")

    # New Control Room fields
    model_id = body.get("model_id")
    source_id = body.get("source_id")
    upload_id = body.get("upload_id")

    # Validate: exactly one of source_id or upload_id (or legacy h5_path)
    source_provided = bool(source_id)
    upload_provided = bool(upload_id)
    has_legacy_path = bool(h5_path)

    if source_provided and upload_provided:
        _send_json(handler, 400, {
            "error": "Only one of source_id or upload_id may be provided.",
            "error_code": "AMBIGUOUS_SOURCE",
        })
        return

    try:
        # Resolve source — new Control Room path
        if source_provided or upload_provided:
            resolved_path = resolve_source(source_id, upload_id)
            h5_path = resolved_path
        elif not has_legacy_path and not container_id:
            _send_json(handler, 400, {
                "error": "A source_id, upload_id, h5_path, or container_id "
                         "is required to create an analysis job.",
                "error_code": "MISSING_SOURCE",
            })
            return

        # Clean up expired uploads periodically
        _cleanup_expired_uploads()

        job = create_analysis_job(
            container_id=container_id,
            workflow_id=workflow_id,
            h5_path=h5_path,
            model_id=model_id,
        )

        _send_json(handler, 201, {
            "job": job.to_dict(),
            "storage_mode": _event_store.storage_mode,
        })
    except ValueError as exc:
        # Typed safe error from resolution
        _send_json(handler, 400, {"error": str(exc), "error_code": "SOURCE_ERROR"})
    except Exception as exc:
        _log.exception("Failed to create analysis job")
        _send_json(handler, 500, {"error": str(exc)[:200]})


def handle_job_get(handler: BaseHTTPRequestHandler, job_id: str) -> None:
    """Handle GET /demo/api/jobs/{job_id} — get job status."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        # Check if job might be known to event store
        if _event_store.has_job(job_id):
            _send_json(handler, 410, {
                "error": "Job has expired",
                "job_id": job_id,
                "storage_mode": _event_store.storage_mode,
            })
        else:
            _send_json(handler, 404, {"error": "Job not found", "job_id": job_id})
        return

    result = job.to_dict()
    result["storage_mode"] = _event_store.storage_mode
    result["retention_seconds"] = _event_store.retention_seconds

    # Add execution traces per workflow (trace projection reads event store only)
    result["execution_traces"] = {}
    with _jobs_lock:
        requested = list(job.requested_workflows)
    for wid in requested:
        trace = build_trace_from_events(_event_store, job_id, wid)
        if trace:
            result["execution_traces"][wid] = trace.to_dict()

    _send_json(handler, 200, result)


def handle_job_events(handler: BaseHTTPRequestHandler, job_id: str) -> None:
    """Handle GET /demo/api/jobs/{job_id}/events — get job events."""
    if not _event_store.has_job(job_id):
        _send_json(handler, 404, {"error": "Job not found", "job_id": job_id})
        return

    since = int(handler.headers.get("X-Event-Cursor", "0"))
    events = get_job_events(job_id, since_sequence=since)
    cursor = _event_store.get_job_cursor(job_id)
    _send_json(handler, 200, {
        "events": events,
        "cursor": cursor,
        "job_id": job_id,
    })


def handle_job_events_stream(handler: BaseHTTPRequestHandler, job_id: str) -> None:
    """Handle GET /demo/api/jobs/{job_id}/events/stream — SSE stream."""
    if not _event_store.has_job(job_id):
        body = _json.dumps({"error": "Job not found"}).encode("utf-8")
        handler.send_response(404)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
        return

    request_id = handler.headers.get("X-Request-ID") or str(_uuid.uuid4())
    last_event_id = handler.headers.get("Last-Event-ID", "0")
    cursor = int(last_event_id) if last_event_id.isdigit() else 0

    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "keep-alive")
    handler.send_header("X-Request-ID", request_id)
    handler.end_headers()

    _log.info(
        "bremen.sse.connected\tjob_id=%s\tcursor=%s\trequest_id=%s",
        job_id, cursor, request_id,
    )

    # Send any events already buffered since the cursor
    _send_sse_events_to_cursor(handler, job_id, cursor)
    cursor = _event_store.get_job_cursor(job_id)

    deadline = _time.monotonic() + 300  # 5-minute max
    heartbeat_interval = 15.0
    poll_interval = 0.1  # fallback re-check after condition wakeup

    while _time.monotonic() < deadline:
        # Check if job has reached a terminal state (brief lock)
        with _jobs_lock:
            job = _jobs.get(job_id)
        if job and job.overall_status in (
            "completed", "failed", "partial_success",
            "workflow_configuration_required",
        ):
            # Drain any remaining events before signalling completion
            new_events = _event_store.get_events(job_id, since_sequence=cursor)
            if new_events:
                _send_sse_events_from_list(handler, new_events)
                cursor = _event_store.get_job_cursor(job_id)
            _send_sse_event(handler, "stream_complete",
                           _json.dumps({"cursor": cursor, "job_id": job_id}))
            break

        # Block on the store's condition until new events or heartbeat timeout.
        # This delivers events promptly rather than polling every 15 s.
        new_events = _event_store.wait_for_events(
            job_id, cursor, timeout=heartbeat_interval,
        )

        if new_events:
            _send_sse_events_from_list(handler, new_events)
            cursor = _event_store.get_job_cursor(job_id)
            continue

        # No events arrived within the heartbeat window — send keepalive
        try:
            handler.wfile.write(b": keepalive\n\n")
            handler.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            _log.debug("bremen.sse.disconnected\tjob_id=%s", job_id)
            break

    _log.debug("bremen.sse.stream_end\tjob_id=%s", job_id)


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------


def _send_sse_events_to_cursor(
    handler: BaseHTTPRequestHandler, job_id: str, since_cursor: int,
) -> None:
    """Send all events for *job_id* with sequence > *since_cursor*."""
    events = _event_store.get_events(job_id, since_sequence=since_cursor)
    _send_sse_events_from_list(handler, events)


def _send_sse_events_from_list(
    handler: BaseHTTPRequestHandler, events: list,
) -> None:
    """Send a pre-fetched list of events as SSE frames."""
    for event in events:
        data = _json.dumps(event.to_dict())
        _send_sse_event(handler, "job_event", data,
                       event_id=str(event.sequence))


def _send_sse_event(
    handler: BaseHTTPRequestHandler,
    event_type: str,
    data: str,
    event_id: str = "",
) -> None:
    try:
        if event_id:
            handler.wfile.write(f"id: {event_id}\n".encode("utf-8"))
        handler.wfile.write(f"event: {event_type}\n".encode("utf-8"))
        handler.wfile.write(f"data: {data}\n\n".encode("utf-8"))
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass


# ---------------------------------------------------------------------------
# Report API handlers
# ---------------------------------------------------------------------------


def handle_job_reports(handler: BaseHTTPRequestHandler, job_id: str) -> None:
    """Handle GET /demo/api/jobs/{job_id}/reports."""
    result = get_job_reports(job_id)
    status = 200 if result["reports"] else 200
    _send_json(handler, status, result)


def handle_job_report(
    handler: BaseHTTPRequestHandler, job_id: str, workflow_id: str,
) -> None:
    """Handle GET /demo/api/jobs/{job_id}/reports/{workflow_id}."""
    result = get_job_report(job_id, workflow_id)
    _send_json(handler, 200, result)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _send_json(
    handler: BaseHTTPRequestHandler,
    status: int,
    data: dict[str, Any],
) -> None:
    """Serialize *data* as JSON and write the response."""
    request_id = handler.headers.get("X-Request-ID") or str(_uuid.uuid4())
    data["request_id"] = request_id
    data["technical_demo_only"] = True
    body = _json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("X-Request-ID", request_id)
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any] | None:
    """Read and parse the request body as JSON."""
    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length == 0:
        return None
    raw = handler.rfile.read(content_length)
    try:
        return dict(_json.loads(raw))
    except (_json.JSONDecodeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Reset for tests
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
    from .source_registry import reset_for_tests as _reset_source_registry  # noqa: PLC0415
    _reset_source_registry()
