"""Events HTTP route translation."""

from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from bremen.api.http.http_policy import (
    _check_auth_gate,
    _check_auth_gate_with_ticket,
)


def register(app: FastAPI, version=None):
    import concurrent.futures as _futures  # noqa: PLC0415

    _sse_executor = _futures.ThreadPoolExecutor(
        max_workers=4,
        thread_name_prefix="fastapi-sse",
    )

    _TERMINAL_STATUSES = frozenset(
        {
            "completed",
            "failed",
            "partial_success",
            "workflow_configuration_required",
        }
    )

    @app.get("/demo/api/jobs/{job_id}/events")
    async def job_events_json_route(
        job_id: str,
        request: Request,
    ) -> JSONResponse:
        """JSON polling endpoint for job events.

        Mirrors ``handle_job_events()`` from job_api_handler.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
        import uuid as _uuid  # noqa: PLC0415
        from bremen.platform.jobs.service import _event_store
        from bremen.platform.jobs.service import get_job_events
        from bremen.contracts.events import allowed_event_details  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())

        if not _event_store.has_job(job_id):
            return JSONResponse(
                content={"error": "Job not found", "job_id": job_id},
                status_code=404,
            )

        since = int(request.headers.get("X-Event-Cursor", "0"))
        events = get_job_events(job_id, since_sequence=since)
        cursor = _event_store.get_job_cursor(job_id)

        # Read-time safety filter: strip prohibited detail keys
        safe_events = []
        for ev in events:
            ev_dict = ev.to_dict() if hasattr(ev, "to_dict") else dict(ev)
            ev_dict["details"] = allowed_event_details(ev_dict.get("details", {}))
            safe_events.append(ev_dict)

        return JSONResponse(
            content={
                "events": safe_events,
                "cursor": cursor,
                "job_id": job_id,
                "request_id": request_id,
                "technical_demo_only": True,
            }
        )

    @app.get("/demo/api/jobs/{job_id}/events/stream")
    async def job_events_stream_route(
        job_id: str,
        request: Request,
    ) -> StreamingResponse:
        """SSE streaming endpoint for job events.

        Mirrors ``handle_job_events_stream()`` from job_api_handler.
        Uses a dedicated ThreadPoolExecutor for blocking
        ``wait_for_events()`` calls.
        """
        gate = _check_auth_gate_with_ticket(request, job_id, "stream")
        if gate is not None:
            return gate
        import asyncio  # noqa: PLC0415
        import time as _time  # noqa: PLC0415
        import uuid as _uuid  # noqa: PLC0415
        import json as _json  # noqa: PLC0415
        import logging as _logging  # noqa: PLC0415
        from bremen.platform.jobs.service import _event_store
        from bremen.platform.jobs.service import _jobs
        from bremen.platform.jobs.service import _jobs_lock
        from bremen.contracts.events import allowed_event_details  # noqa: PLC0415

        _log = _logging.getLogger(__name__)
        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())

        # Unknown job → JSON 404, not SSE (must happen before stream starts)
        if not _event_store.has_job(job_id):
            return JSONResponse(
                content={"error": "Job not found"},
                status_code=404,
            )

        last_event_id = request.headers.get("Last-Event-ID", "0")
        cursor = int(last_event_id) if last_event_id.isdigit() else 0

        async def event_generator(_initial_cursor: int = cursor):
            """Async generator that yields SSE frames.

            Uses ``run_in_executor`` with a **dedicated** thread pool
            to bridge the blocking ``wait_for_events()`` call without
            exhausting the default executor.
            """
            loop = asyncio.get_running_loop()

            def _format_sse_frame(
                event_type: str,
                data: str,
                event_id: str = "",
            ) -> str:
                """Format a single SSE frame."""
                parts = []
                if event_id:
                    parts.append(f"id: {event_id}")
                parts.append(f"event: {event_type}")
                parts.append(f"data: {data}")
                return "\n".join(parts) + "\n\n"

            def _format_event(ev) -> str:
                """Format a JobEvent as an SSE frame with read-time safety."""
                ev_dict = ev.to_dict() if hasattr(ev, "to_dict") else dict(ev)
                ev_dict["details"] = allowed_event_details(ev_dict.get("details", {}))
                return _format_sse_frame(
                    "job_event",
                    _json.dumps(ev_dict),
                    event_id=str(ev.sequence),
                )

            _cursor = _initial_cursor
            try:
                # Send any buffered events since cursor
                buffered = _event_store.get_events(job_id, since_sequence=_cursor)
                for ev in buffered:
                    yield _format_event(ev)
                _cursor = _event_store.get_job_cursor(job_id)

                deadline = _time.monotonic() + 300  # 5-minute max
                heartbeat_interval = 15.0

                while _time.monotonic() < deadline:
                    # Check terminal status (brief lock)
                    with _jobs_lock:
                        job = _jobs.get(job_id)
                    if job and job.overall_status in _TERMINAL_STATUSES:
                        # Drain remaining events before signalling completion
                        remaining = _event_store.get_events(
                            job_id,
                            since_sequence=cursor,
                        )
                        for ev in remaining:
                            yield _format_event(ev)
                        _cursor = _event_store.get_job_cursor(job_id)
                        yield _format_sse_frame(
                            "stream_complete",
                            _json.dumps({"cursor": _cursor, "job_id": job_id}),
                        )
                        return

                    # Block on store's condition via dedicated executor
                    new_events = await loop.run_in_executor(
                        _sse_executor,
                        _event_store.wait_for_events,
                        job_id,
                        cursor,
                        heartbeat_interval,
                    )

                    if new_events:
                        for ev in new_events:
                            yield _format_event(ev)
                        _cursor = _event_store.get_job_cursor(job_id)
                        continue

                    # No events — send heartbeat
                    yield ": keepalive\n\n"

            except GeneratorExit:
                # Client disconnected — clean up silently
                _log.debug("bremen.sse.fastapi.disconnect\tjob_id=%s", job_id)
            except Exception:
                _log.exception("bremen.sse.fastapi.error\tjob_id=%s", job_id)
            finally:
                _log.debug("bremen.sse.fastapi.end\tjob_id=%s", job_id)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Request-ID": request_id,
            },
        )
