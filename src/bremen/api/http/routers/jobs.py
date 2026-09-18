"""Jobs HTTP route translation."""

from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from bremen.api.http.http_policy import (
    _check_auth_gate,
    _log_job_rejection,
    _invalid_aramina_fields,
)


def register(app: FastAPI, version=None):

    @app.post("/demo/api/jobs")
    async def demo_jobs_create_route(request: Request) -> JSONResponse:
        """Create an analysis job.

        Reuses :func:`bremen.platform.jobs.service.create_analysis_job`
        and :func:`bremen.platform.sources.service.resolve_source` for
        business logic.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
        from bremen.api.fastapi_contracts import JobCreateRequest  # noqa: PLC0415

        from bremen.platform.reports.diagnostics import (
            invalid_request_details,
            is_aramina_selection,
            patient_mismatch_details,
            source_error_details,
        )

        # Parse JSON body
        try:
            body_bytes = await request.body()
            if not body_bytes:
                _log_job_rejection("INVALID_JSON")
                return JSONResponse(
                    content={"error": "Invalid JSON body"},
                    status_code=400,
                )
            body_dict = __import__("json").loads(body_bytes)
        except Exception:
            _log_job_rejection("INVALID_JSON")
            return JSONResponse(
                content={"error": "Invalid JSON body"},
                status_code=400,
            )

        # Validate with Pydantic
        try:
            req = JobCreateRequest(**body_dict)
        except Exception as exc:
            from pydantic import ValidationError

            fields = []
            if isinstance(exc, ValidationError):
                fields = [
                    error["loc"][0]
                    for error in exc.errors(include_input=False)
                    if error.get("loc")
                ]
            _log_job_rejection("INVALID_REQUEST_SCHEMA", fields)
            if is_aramina_selection(body_dict):
                return JSONResponse(
                    content=invalid_request_details(body_dict), status_code=400
                )
            return JSONResponse(
                content={"error": f"Invalid request: {exc}"},
                status_code=400,
            )

        # Action routing — delete_report is not migrated in Phase 3
        if req.action == "delete_report":
            _log_job_rejection("UNSUPPORTED_ACTION", ["action"])
            return JSONResponse(
                content={"error": "delete_report not migrated in Phase 3"},
                status_code=400,
            )

        # Parse request fields
        source_id = req.source_id
        upload_id = req.upload_id
        h5_path = req.h5_path
        container_id = req.container_id
        workflow_id = req.workflow_id
        model_id = req.model_id

        # Build Aramina request from raw body fields (preserves patient_id,
        # target_side, analysis_author, prediction_comment from the JSON body).
        try:
            from bremen.platform.jobs.service import _selected_aramina_request

            workflow_id, aramina_request = _selected_aramina_request(
                model_id,
                workflow_id,
                body_dict,
            )
        except Exception:
            _log_job_rejection(
                "ARAMINA_INVALID_REQUEST", _invalid_aramina_fields(body_dict)
            )
            return JSONResponse(
                content=invalid_request_details(body_dict), status_code=400
            )

        source_provided = bool(source_id)
        upload_provided = bool(upload_id)
        has_legacy_path = bool(h5_path)

        # Validate: exactly one of source_id or upload_id (or legacy path)
        if source_provided and upload_provided:
            _log_job_rejection("AMBIGUOUS_SOURCE", ["source_id", "upload_id"])
            return JSONResponse(
                content={
                    "error": "Only one of source_id or upload_id may be provided.",
                    "error_code": "AMBIGUOUS_SOURCE",
                },
                status_code=400,
            )

        # Compute source_key for stable identity
        source_key = source_id or upload_id or container_id or ""
        if source_id:
            from bremen.platform.sources.registry import (  # noqa: PLC0415
                get_stable_source_key,
            )

            stable = get_stable_source_key(source_id)
            if stable:
                source_key = stable

        # Rerun guard: block duplicate analysis
        # PR0141: Aramina identity includes target_side; Bremen identity is unchanged.
        from bremen.platform.reports.service import _find_existing_completed_report

        requested_side = (
            aramina_request.target_side.strip().lower()
            if workflow_id == "aramina" and aramina_request is not None
            else ""
        )
        if source_key and workflow_id and model_id:
            existing = _find_existing_completed_report(
                source_key,
                workflow_id,
                model_id,
                requested_side,
            )
            if existing is not None:
                return JSONResponse(
                    content={
                        "status": "blocked",
                        "error": "report_already_exists",
                        "message": (
                            "A report already exists for this source and model. "
                            "Delete the report to run again."
                        ),
                        "job_id": existing[0],
                        "workflow_id": existing[1],
                        "existing_target_side": requested_side,
                        "requested_target_side": requested_side,
                    },
                    status_code=409,
                )

        from bremen.model_packages.aramina_v0213.errors import AraminaWorkflowError

        failure_stage = "source_resolution"
        try:
            # Derive effective source display name
            effective_container_id = container_id
            if source_provided:
                from bremen.platform.sources.registry import (  # noqa: PLC0415
                    get_source_info,
                )

                source_info = get_source_info(source_id)
                if source_info and source_info.get("filename"):
                    effective_container_id = source_info["filename"]
                else:
                    raw = source_id.split("/")[-1] if "/" in source_id else source_id
                    effective_container_id = raw if raw else "Patient"
            elif upload_provided:
                from bremen.platform.jobs.service import _staged_uploads
                from bremen.platform.jobs.service import _uploads_lock

                with _uploads_lock:
                    upload_rec = _staged_uploads.get(upload_id)
                if upload_rec is not None:
                    effective_container_id = upload_rec.filename or "Patient"
                else:
                    effective_container_id = "Patient"

            # Resolve source
            if source_provided or upload_provided:
                from bremen.platform.sources.service import resolve_source

                resolved_path = resolve_source(source_id, upload_id)
                h5_path = resolved_path
            elif not has_legacy_path and not container_id:
                _log_job_rejection(
                    "MISSING_SOURCE",
                    ["source_id", "upload_id", "h5_path", "container_id"],
                )
                return JSONResponse(
                    content={
                        "error": "A source_id, upload_id, h5_path, or container_id "
                        "is required to create an analysis job.",
                        "error_code": "MISSING_SOURCE",
                    },
                    status_code=400,
                )

            # Extract patient display name (fault-tolerant)
            from bremen.platform.sources.service import extract_patient_display_name

            patient_display_name = extract_patient_display_name(h5_path)
            if workflow_id == "aramina":
                mismatch = patient_mismatch_details(
                    aramina_request.patient_id, patient_display_name
                )
                if mismatch is not None:
                    _log_job_rejection("ARAMINA_PATIENT_MISMATCH", ["patient_id"])
                    return JSONResponse(content=mismatch, status_code=400)

            # Clean up expired uploads periodically
            from bremen.platform.sources.service import _cleanup_expired_uploads

            _cleanup_expired_uploads()

            from bremen.platform.jobs.service import create_analysis_job

            failure_stage = "job_creation"
            job = create_analysis_job(
                container_id=effective_container_id,
                workflow_id=workflow_id,
                h5_path=h5_path,
                model_id=model_id,
                source_key=source_key,
                patient_display_name=patient_display_name,
                target_side=requested_side,
                # PR0157 (additive request metadata; Aramina still sources these
                # from its validated request object, so passing them here is a
                # no-op for Aramina and enables Bremen Standard Result mapping).
                analysis_author=body_dict.get("analysis_author") or "",
                prediction_comment=body_dict.get("prediction_comment") or "",
                **(
                    {"aramina_request": aramina_request}
                    if workflow_id == "aramina"
                    else {}
                ),
            )

            from bremen.platform.jobs.service import _event_store

            return JSONResponse(
                content={
                    "job": job.to_dict(),
                    "storage_mode": _event_store.storage_mode,
                },
                status_code=201,
            )

        except ValueError as exc:
            _log_job_rejection("SOURCE_ERROR", stage=failure_stage)
            if workflow_id == "aramina":
                return JSONResponse(content=source_error_details(exc), status_code=400)
            return JSONResponse(
                content={
                    "error": str(exc),
                    "error_code": "SOURCE_ERROR",
                },
                status_code=400,
            )
        except AraminaWorkflowError:
            _log_job_rejection(
                "ARAMINA_INVALID_REQUEST",
                _invalid_aramina_fields(body_dict),
                stage=failure_stage,
            )
            return JSONResponse(
                content=invalid_request_details(body_dict), status_code=400
            )
        except Exception as exc:
            import logging as _log_mod

            if workflow_id == "aramina":
                return JSONResponse(
                    content={
                        "error": "Could not create Aramina job",
                        "error_code": "ARAMINA_EXECUTION_FAILED",
                        "technical_demo_only": True,
                    },
                    status_code=500,
                )
            _log_mod.getLogger(__name__).exception("Failed to create analysis job")
            return JSONResponse(
                content={"error": str(exc)[:200]},
                status_code=500,
            )

    @app.get("/demo/api/jobs")
    async def demo_jobs_list_route(
        request: Request,
    ) -> JSONResponse:
        """List recent analysis jobs.

        Mirrors ``handle_jobs_list()`` from job_api_handler.
        Supports optional query parameters: model_id, workflow_id.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
        import uuid as _uuid  # noqa: PLC0415
        from bremen.platform.jobs.service import list_analysis_jobs
        from bremen.platform.jobs.service import _event_store

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        filter_model_id = request.query_params.get("model_id")
        filter_workflow_id = request.query_params.get("workflow_id")

        jobs = list_analysis_jobs(
            model_id=filter_model_id,
            workflow_id=filter_workflow_id,
        )
        return JSONResponse(
            content={
                "jobs": jobs,
                "storage_mode": _event_store.storage_mode,
                "retention_seconds": _event_store.retention_seconds,
                "max_jobs": _event_store.max_jobs,
                "request_id": request_id,
                "technical_demo_only": True,
            }
        )

    @app.get("/demo/api/jobs/{job_id}")
    async def demo_job_detail_route(
        job_id: str,
        request: Request,
    ) -> JSONResponse:
        """Get job status and execution traces.

        Mirrors ``handle_job_get()`` from job_api_handler.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
        import uuid as _uuid  # noqa: PLC0415
        from bremen.platform.jobs.service import _jobs
        from bremen.platform.jobs.service import _jobs_lock
        from bremen.platform.jobs.service import _event_store
        from bremen.platform.events.trace import build_trace_from_events  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())

        with _jobs_lock:
            job = _jobs.get(job_id)

        if job is None:
            if _event_store.has_job(job_id):
                return JSONResponse(
                    content={
                        "error": "Job has expired",
                        "job_id": job_id,
                        "storage_mode": _event_store.storage_mode,
                        "request_id": request_id,
                    },
                    status_code=410,
                )
            return JSONResponse(
                content={
                    "error": "Job not found",
                    "job_id": job_id,
                    "request_id": request_id,
                },
                status_code=404,
            )

        result = job.to_dict()
        result["storage_mode"] = _event_store.storage_mode
        result["retention_seconds"] = _event_store.retention_seconds
        result["request_id"] = request_id

        # Execution traces
        result["execution_traces"] = {}
        with _jobs_lock:
            requested = list(job.requested_workflows)
        for wid in requested:
            trace = build_trace_from_events(_event_store, job_id, wid)
            if trace:
                result["execution_traces"][wid] = trace.to_dict()

        return JSONResponse(content=result)
