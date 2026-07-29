"""Isolated FastAPI foundation for Bremen API migration.

This module provides ``create_fastapi_app()`` — a FastAPI application
factory that registers routes:

Phase 1:
- ``GET /health``
- ``GET /model/version``

Phase 2:
- ``GET /demo/api/models``
- ``GET /demo/api/h5/containers``

Phase 3:
- ``POST /demo/api/h5/containers`` (upload)
- ``POST /demo/api/jobs`` (job creation)

These routes reuse existing business logic from ``bremen.api.app``
and ``bremen.api.server``.

Coexistence strategy
--------------------
This FastAPI app is **isolated** from the production ``http.server``
path.  It is intended for testing and future migration phases only.

- Production Dockerfile target/ENTRYPOINT/CMD remain unchanged.
- Production ``http.server`` routes remain untouched.
- No SSE or event-streaming routes are implemented here.

Safety
------
- No raw S3 bucket/key values, credentials, JWT secrets, or env values
  are exposed in route output.
- No filesystem paths are leaked.
- No raw exception traces are exposed.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import JSONResponse


def create_fastapi_app(version: str | None = None) -> FastAPI:
    """Create and return a FastAPI application with Phase 1 + Phase 2 routes.

    Parameters
    ----------
    version : Optional version string forwarded to the health endpoint.

    Returns
    -------
    A configured ``FastAPI`` instance ready for a ``TestClient`` or
    ``uvicorn``.
    """
    app = FastAPI(
        title="Bremen API (FastAPI)",
        version="0.1.0",
        description=(
            "Isolated FastAPI foundation for migration testing.  "
            "Production http.server path remains active."
        ),
        # Disable OpenAPI docs in Phase 1 — no Pydantic schemas yet
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )

    # ------------------------------------------------------------------
    # GET /health
    # ------------------------------------------------------------------
    @app.get("/health")
    async def health_route(request: Request) -> JSONResponse:
        """Return service health status.

        Reuses :func:`bremen.api.app.handle_health` for business logic.
        """
        # Lazy import to avoid circular deps at module load
        from bremen.api.app import handle_health as _handle_health  # noqa: PLC0415

        resp = _handle_health(version=version)
        return JSONResponse(content={
            "status": resp.status,
            "service": resp.service,
            "version": resp.version,
            "timestamp": resp.timestamp,
            "model_ready": resp.model_ready,
        })

    # ------------------------------------------------------------------
    # GET /model/version
    # ------------------------------------------------------------------
    @app.get("/model/version")
    async def model_version_route(request: Request) -> JSONResponse:
        """Return configured model package metadata.

        Reuses :func:`bremen.api.app.handle_model_version` for business
        logic.
        """
        from bremen.api.app import handle_model_version as _handle_model_version  # noqa: PLC0415

        resp = _handle_model_version()
        return JSONResponse(content={
            "model_configured": resp.model_configured,
            "model_version": resp.model_version,
            "model_checksum": resp.model_checksum,
            "feature_schema_version": resp.feature_schema_version,
            "threshold_version": resp.threshold_version,
            "threshold_value": resp.threshold_value,
            "qc_criteria_version": resp.qc_criteria_version,
            "model_status": resp.model_status,
        })

    # ------------------------------------------------------------------
    # GET /demo/api/models — model catalog (Phase 2)
    # ------------------------------------------------------------------
    @app.get("/demo/api/models")
    async def demo_models_route(request: Request) -> JSONResponse:
        """Return the model catalog.

        Reuses :func:`bremen.api.model_catalog.build_model_catalog`
        for business logic.
        """
        from bremen.api.model_catalog import (  # noqa: PLC0415
            build_model_catalog as _build_model_catalog,
        )
        import uuid as _uuid  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        catalog = _build_model_catalog()
        catalog["request_id"] = request_id
        catalog["technical_demo_only"] = True
        return JSONResponse(content=catalog)

    # ------------------------------------------------------------------
    # GET /demo/api/h5/containers — H5 container listing (Phase 2)
    # ------------------------------------------------------------------
    @app.get("/demo/api/h5/containers")
    async def demo_h5_containers_route(request: Request) -> JSONResponse:
        """List demo H5 containers.

        Reuses :func:`bremen.api.server._build_containers_response`
        for business logic (shared with the http.server handler).
        """
        import uuid as _uuid  # noqa: PLC0415
        from bremen.api.server import (  # noqa: PLC0415
            _build_containers_response as _build_containers,
        )

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        data = _build_containers(request_id=request_id)
        return JSONResponse(content=data)

    # ------------------------------------------------------------------
    # POST /demo/api/h5/containers — upload H5 file (Phase 3)
    # ------------------------------------------------------------------
    @app.post("/demo/api/h5/containers")
    async def demo_h5_upload_route(
        request: Request,
        file: UploadFile = File(...),
    ) -> JSONResponse:
        """Upload an H5 container file.

        Reuses :func:`bremen.api.server._handle_h5_upload_bytes`
        for validation and S3 upload logic.
        """
        import uuid as _uuid  # noqa: PLC0415
        from bremen.api.server import (  # noqa: PLC0415
            _handle_h5_upload_bytes as _upload_bytes,
        )

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        raw_filename = file.filename or ""
        raw_body = await file.read()

        status_code, data = _upload_bytes(raw_body, raw_filename, request_id)
        return JSONResponse(content=data, status_code=status_code)

    # ------------------------------------------------------------------
    # POST /demo/api/jobs — create analysis job (Phase 3)
    # ------------------------------------------------------------------
    @app.post("/demo/api/jobs")
    async def demo_jobs_create_route(request: Request) -> JSONResponse:
        """Create an analysis job.

        Reuses :func:`bremen.api.job_api_handler.create_analysis_job`
        and :func:`bremen.api.job_api_handler.resolve_source` for
        business logic.
        """
        import uuid as _uuid  # noqa: PLC0415
        from bremen.api.fastapi_contracts import JobCreateRequest  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())

        # Parse JSON body
        try:
            body_bytes = await request.body()
            if not body_bytes:
                return JSONResponse(
                    content={"error": "Invalid JSON body"},
                    status_code=400,
                )
            body_dict = __import__("json").loads(body_bytes)
        except Exception:
            return JSONResponse(
                content={"error": "Invalid JSON body"},
                status_code=400,
            )

        # Validate with Pydantic
        try:
            req = JobCreateRequest(**body_dict)
        except Exception as exc:
            return JSONResponse(
                content={"error": f"Invalid request: {exc}"},
                status_code=400,
            )

        # Action routing — delete_report is not migrated in Phase 3
        if req.action == "delete_report":
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

        source_provided = bool(source_id)
        upload_provided = bool(upload_id)
        has_legacy_path = bool(h5_path)

        # Validate: exactly one of source_id or upload_id (or legacy path)
        if source_provided and upload_provided:
            return JSONResponse(content={
                "error": "Only one of source_id or upload_id may be provided.",
                "error_code": "AMBIGUOUS_SOURCE",
            }, status_code=400)

        # Compute source_key for stable identity
        source_key = source_id or upload_id or container_id or ""
        if source_id:
            from bremen.api.source_registry import (  # noqa: PLC0415
                get_stable_source_key,
            )
            stable = get_stable_source_key(source_id)
            if stable:
                source_key = stable

        # Rerun guard: block duplicate analysis
        from bremen.api.job_api_handler import (  # noqa: PLC0415
            _find_existing_completed_report,
        )
        if source_key and workflow_id and model_id:
            existing = _find_existing_completed_report(
                source_key, workflow_id, model_id,
            )
            if existing is not None:
                return JSONResponse(content={
                    "status": "blocked",
                    "error": "report_already_exists",
                    "message": (
                        "A report already exists for this source and model. "
                        "Delete the report to run again."
                    ),
                    "job_id": existing[0],
                    "workflow_id": existing[1],
                }, status_code=409)

        try:
            # Derive effective source display name
            effective_container_id = container_id
            if source_provided:
                from bremen.api.source_registry import (  # noqa: PLC0415
                    get_source_info,
                )
                source_info = get_source_info(source_id)
                if source_info and source_info.get("filename"):
                    effective_container_id = source_info["filename"]
                else:
                    raw = source_id.split("/")[-1] if "/" in source_id else source_id
                    effective_container_id = raw if raw else "Patient"
            elif upload_provided:
                from bremen.api.job_api_handler import (  # noqa: PLC0415
                    _staged_uploads, _uploads_lock,
                )
                with _uploads_lock:
                    upload_rec = _staged_uploads.get(upload_id)
                if upload_rec is not None:
                    effective_container_id = upload_rec.filename or "Patient"
                else:
                    effective_container_id = "Patient"

            # Resolve source
            if source_provided or upload_provided:
                from bremen.api.job_api_handler import resolve_source  # noqa: PLC0415
                resolved_path = resolve_source(source_id, upload_id)
                h5_path = resolved_path
            elif not has_legacy_path and not container_id:
                return JSONResponse(content={
                    "error": "A source_id, upload_id, h5_path, or container_id "
                             "is required to create an analysis job.",
                    "error_code": "MISSING_SOURCE",
                }, status_code=400)

            # Extract patient display name (fault-tolerant)
            from bremen.api.job_api_handler import (  # noqa: PLC0415
                extract_patient_display_name,
            )
            patient_display_name = extract_patient_display_name(h5_path)

            # Clean up expired uploads periodically
            from bremen.api.job_api_handler import (  # noqa: PLC0415
                _cleanup_expired_uploads,
            )
            _cleanup_expired_uploads()

            from bremen.api.job_api_handler import (  # noqa: PLC0415
                create_analysis_job,
            )
            job = create_analysis_job(
                container_id=effective_container_id,
                workflow_id=workflow_id,
                h5_path=h5_path,
                model_id=model_id,
                source_key=source_key,
                patient_display_name=patient_display_name,
            )

            from bremen.api.job_api_handler import _event_store  # noqa: PLC0415
            return JSONResponse(content={
                "job": job.to_dict(),
                "storage_mode": _event_store.storage_mode,
            }, status_code=201)

        except ValueError as exc:
            return JSONResponse(content={
                "error": str(exc), "error_code": "SOURCE_ERROR",
            }, status_code=400)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("Failed to create analysis job")
            return JSONResponse(
                content={"error": str(exc)[:200]},
                status_code=500,
            )

    # ------------------------------------------------------------------
    # Exception handler — ensure no raw traces leak
    # ------------------------------------------------------------------
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all exception handler — never exposes raw trace details."""
        return JSONResponse(
            content={"error": "Internal error"},
            status_code=500,
        )

    return app
