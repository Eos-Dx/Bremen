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
"""

from __future__ import annotations

import json as _json
import logging
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

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared in-memory state (process-local, ephemeral)
# ---------------------------------------------------------------------------

# Store persistent state on ``bremen`` package so it survives
# ``bremen.api.*`` module reload (same strategy as PR0076 ModelState fix).
_STORE_KEY = "_bremen_workspace_event_store"
_JOBS_KEY = "_bremen_workspace_jobs"
_PROVIDERS_KEY = "_bremen_workspace_report_providers"


def _get_or_create_store():
    s = getattr(bremen, _STORE_KEY, None)
    if s is None:
        s = BoundedEventStore()
        setattr(bremen, _STORE_KEY, s)
    return s


def _get_or_create_jobs():
    j = getattr(bremen, _JOBS_KEY, None)
    if j is None:
        j = {}
        setattr(bremen, _JOBS_KEY, j)
    return j


def _get_or_create_providers():
    p = getattr(bremen, _PROVIDERS_KEY, None)
    if p is None:
        p = {}
        setattr(bremen, _PROVIDERS_KEY, p)
    return p


# Module-level references that point to persistent bremen-package objects
_event_store = _get_or_create_store()
_jobs = _get_or_create_jobs()
_report_providers = _get_or_create_providers()


def register_report_provider(provider: ReportProvider) -> None:
    """Register a report provider for a workflow."""
    _report_providers[provider.workflow_id] = provider


def _get_report_provider(workflow_id: str) -> ReportProvider | None:
    return _report_providers.get(workflow_id)


def _register_default_providers() -> None:
    """Register built-in report providers."""
    from .report_bremen import BremenReportProvider  # noqa: PLC0415
    from .report_aramis import AramisReportProvider  # noqa: PLC0415

    if "bremen" not in _report_providers:
        register_report_provider(BremenReportProvider())
    if "aramis" not in _report_providers:
        register_report_provider(AramisReportProvider())


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
    registry: WorkflowRegistry | None = None,
) -> AnalysisJob:
    """Create and execute an analysis job synchronously.

    The job runs through the orchestrator and events are captured
    in the shared ``_event_store``.
    """
    job_id = str(_uuid.uuid4())
    request_id = str(_uuid.uuid4())
    created_at = _utc_now()

    job = AnalysisJob(
        job_id=job_id,
        request_id=request_id,
        created_at=created_at,
        started_at=_utc_now(),
        overall_status="running",
        input_summary={"container_id": container_id or "synthetic"},
        normalization_summary={},
        requested_workflows=(workflow_id,),
    )
    _jobs[job_id] = job

    # Run the orchestrator with event capture
    mw_result = run_workflow_request(
        h5_path=h5_path,
        workflow_id=workflow_id,
        registry=registry,
        event_store=_event_store,
    )

    # Update job from result
    wf_result = mw_result.workflows.get(workflow_id)

    now = _utc_now()

    if mw_result.normalization_status == "failed":
        job.overall_status = "failed"
        job.completed_at = now
        return job

    job.normalization_summary = {
        "measurement_count": None,
        "layout": None,
    }

    if wf_result:
        if wf_result.status == "completed":
            job.overall_status = "completed"
        elif wf_result.status == "failed":
            job.overall_status = "failed"

        job.workflow_runs[workflow_id] = WorkflowRun(
            workflow_id=workflow_id,
            status=wf_result.status,
            result_summary=wf_result.payload or {},
            failure=wf_result.error,
        )

    job.completed_at = now

    # Generate reports
    _register_default_providers()
    _generate_job_reports(job)

    return job


def get_analysis_job(job_id: str) -> AnalysisJob | None:
    """Return an analysis job by ID, or ``None``."""
    return _jobs.get(job_id)


def list_analysis_jobs() -> list[dict[str, Any]]:
    """Return safe metadata for recent jobs."""
    return [
        {
            "job_id": j.job_id,
            "created_at": j.created_at,
            "overall_status": j.overall_status,
            "requested_workflows": list(j.requested_workflows),
        }
        for j in list(_jobs.values())[-20:]  # most recent 20
    ]


def get_job_events(job_id: str, since_sequence: int = 0) -> list[dict[str, Any]]:
    """Return events for a job, optionally since a sequence cursor."""
    events = _event_store.get_events(job_id, since_sequence=since_sequence)
    return [e.to_dict() for e in events]


def get_job_reports(job_id: str) -> dict[str, Any]:
    """Return reports for a job, keyed by workflow_id."""
    job = _jobs.get(job_id)
    if job is None:
        return {"reports": {}, "job_id": job_id}
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
            for wid, rm in job.reports.items()
        },
        "job_id": job_id,
    }


def get_job_report(job_id: str, workflow_id: str) -> dict[str, Any]:
    """Return a specific workflow report, or unavailable."""
    job = _jobs.get(job_id)
    if job is None:
        return {
            "report": {"status": "job_not_found"},
            "job_id": job_id,
            "workflow_id": workflow_id,
        }

    provider = _get_report_provider(workflow_id)
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
    """Generate reports for all completed workflow runs."""
    for wid, wf_run in job.workflow_runs.items():
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
    """Handle POST /demo/api/jobs — create an analysis job."""
    body = _read_json_body(handler)
    if body is None:
        _send_json(handler, 400, {"error": "Invalid JSON body"})
        return

    h5_path = body.get("h5_path", "")
    workflow_id = body.get("workflow_id", "bremen")
    container_id = body.get("container_id", "")

    try:
        job = create_analysis_job(
            container_id=container_id,
            workflow_id=workflow_id,
            h5_path=h5_path,
        )
        _send_json(handler, 201, {
            "job": job.to_dict(),
            "storage_mode": _event_store.storage_mode,
        })
    except Exception as exc:
        _log.exception("Failed to create analysis job")
        _send_json(handler, 500, {"error": str(exc)[:200]})


def handle_job_get(handler: BaseHTTPRequestHandler, job_id: str) -> None:
    """Handle GET /demo/api/jobs/{job_id} — get job status."""
    job = get_analysis_job(job_id)
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
        # Check if job has reached a terminal state
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
    """Clear all jobs, events, and report providers (test-only).

    Does NOT remove persistent package-level references — only
    clears internal state so that subsequent test logic sees
    a clean workspace.
    """
    _event_store.reset_for_tests()
    _jobs.clear()
    _report_providers.clear()
