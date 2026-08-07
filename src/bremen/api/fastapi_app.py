"""Isolated FastAPI foundation for Bremen API migration.

This module provides ``create_fastapi_app()`` — a FastAPI application
factory that registers routes:

Phase 1:
- ``GET /health``
- ``GET /model/version``

Phase 2:
- ``GET /demo/api/models``
- ``GET /demo/api/h5/containers``
- ``GET /demo/model-guide``
- ``GET /demo/model-playground``

Phase 3:
- ``POST /demo/api/h5/containers`` (upload)
- ``POST /demo/api/jobs`` (job creation)

Phase 4:
- ``GET /demo/api/jobs/{job_id}/events`` (JSON polling)
- ``GET /demo/api/jobs/{job_id}/events/stream`` (SSE)

These routes reuse existing business logic from ``bremen.api.app``
and ``bremen.api.server``.

Coexistence strategy
--------------------
This FastAPI app is **isolated** from the production ``http.server``
path.  It is intended for testing and future migration phases only.

- Production Dockerfile target/ENTRYPOINT/CMD remain unchanged.
- Production ``http.server`` routes remain untouched.

Safety
------
- No raw S3 bucket/key values, credentials, JWT secrets, or env values
  are exposed in route output.
- No filesystem paths are leaked.
- No raw exception traces are exposed.
"""

from __future__ import annotations

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse


# ------------------------------------------------------------------
# Auth enforcement dependency (PR0111)
# ------------------------------------------------------------------

_AUTH_ERROR_SHAPE: dict = {
    "error": "Authentication failed",
    "token_type": "Bearer",
    "technical_demo_only": True,
}


def _check_auth_gate(request: Request) -> JSONResponse | None:
    """Check auth gate for a request.

    Returns None if request is allowed, or a JSONResponse 401 if rejected.
    When auth is disabled or has validation_error, all requests pass.
    When auth is enabled, a valid Bearer access token is required.
    """
    from bremen.api.server import _get_auth_config as _gac  # noqa: PLC0415

    config = _gac()
    if not config.enabled or config.validation_error:
        return None  # auth not active — allow

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.strip().startswith("Bearer "):
        return JSONResponse(content=_AUTH_ERROR_SHAPE, status_code=401)

    from bremen.auth import (  # noqa: PLC0415
        decode_access_token, AuthError,
    )

    token = auth_header.split(None, 1)[1].strip() if len(auth_header.split(None, 1)) == 2 else ""
    if not token:
        return JSONResponse(content=_AUTH_ERROR_SHAPE, status_code=401)

    try:
        decode_access_token(config, token)
    except AuthError:
        return JSONResponse(content=_AUTH_ERROR_SHAPE, status_code=401)

    return None  # token valid — allow


def _check_auth_gate_with_ticket(
    request: Request,
    job_id: str,
    purpose: str,
) -> JSONResponse | None:
    """Check auth gate with ticket fallback for SSE/report routes.

    Gate ordering:
    1. If auth disabled → allow (unchanged)
    2. If Authorization header present:
       a. Try Bearer access token
       b. If valid → allow
       c. If invalid → fall through to step 3
    3. If query parameter ``auth_ticket`` present:
       a. Decode as stream_ticket
       b. Validate job_id and purpose
       c. If valid → allow; if invalid → 401
    4. Otherwise → 401
    """
    from bremen.api.server import _get_auth_config as _gac  # noqa: PLC0415

    config = _gac()
    if not config.enabled or config.validation_error:
        return None  # auth not active — allow

    # Step 2: Try Bearer access token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.strip().startswith("Bearer "):
        token = auth_header.split(None, 1)[1].strip() if len(auth_header.split(None, 1)) == 2 else ""
        if token:
            try:
                from bremen.auth import decode_access_token  # noqa: PLC0415
                decode_access_token(config, token)
                return None  # valid Bearer — allow
            except Exception:  # noqa: BLE001
                pass  # invalid Bearer — fall through to ticket check

    # Step 3: Try auth_ticket query parameter
    ticket = request.query_params.get("auth_ticket", "")
    if ticket:
        try:
            from bremen.auth import decode_stream_ticket  # noqa: PLC0415
            decode_stream_ticket(config, ticket, job_id, purpose)
            return None  # valid ticket — allow
        except Exception:  # noqa: BLE001
            return JSONResponse(content=_AUTH_ERROR_SHAPE, status_code=401)

    # Step 4: No valid auth
    return JSONResponse(content=_AUTH_ERROR_SHAPE, status_code=401)


def _browser_auth_redirect(
    gate: JSONResponse | None,
    next_path: str,
) -> RedirectResponse | None:
    """Convert a JSON auth gate failure into a login redirect for browser routes.

    Browser document navigation cannot attach Authorization headers, so
    browser-navigation HTML routes must not return raw JSON Bearer errors as
    the page body. When the gate rejects a request, redirect to the login page
    with a ``next`` parameter so the user can return after authenticating.

    Returns None when the gate allowed the request, or a RedirectResponse to
    ``/demo/login?next=<next_path>`` when the gate rejected it.
    """
    if gate is None:
        return None
    # next_path is always constructed from controlled values (fixed paths and
    # UUID job IDs), which are URL-safe. Encode any remaining unsafe characters
    # manually to avoid importing urllib (prohibited in this module).
    safe_path = next_path.replace("%", "%25").replace(" ", "%20")
    return RedirectResponse(
        url=f"/demo/login?next={safe_path}",
        status_code=302,
    )


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
    # Suppress access-log noise for GET /health
    # ------------------------------------------------------------------
    @app.middleware("http")
    async def _suppress_health_access_log(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Suppress uvicorn access log for /health probes.

        Tags the request so the uvicorn log filter can skip it.
        All other requests pass through unmodified.
        """
        if request.url.path == "/health":
            request.scope["access_log"] = False
        return await call_next(request)

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
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
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
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
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
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
        from bremen.api.fastapi_contracts import JobCreateRequest  # noqa: PLC0415

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
    # Demo UI routes — parity with legacy http.server
    # ------------------------------------------------------------------

    from fastapi.responses import HTMLResponse  # noqa: PLC0415

    # ------------------------------------------------------------------
    # Startup: initialize model registry (mirrors http.server startup)
    # ------------------------------------------------------------------
    @app.on_event("startup")
    async def _initialize_model_registry() -> None:
        """Populate the process-global model registry at startup.

        Mirrors the startup behavior of ``run_server()`` in the
        legacy http.server path so that ``/demo/api/models`` returns
        configured models instead of an empty catalog.
        """
        import os as _os  # noqa: PLC0415
        from bremen.api.model_registry import (  # noqa: PLC0415
            initialize_registry, build_legacy_registry,
        )

        catalog_uri = _os.environ.get("BREMEN_MODEL_CATALOG_URI", "").strip()
        if catalog_uri:
            from bremen.api.s3_model_discovery import discover_models  # noqa: PLC0415
            from bremen.api.model_registry import ModelRegistry  # noqa: PLC0415

            discovery_result = discover_models(catalog_uri)
            registry = ModelRegistry(
                entries=tuple(discovery_result.entries),
                unavailable_entries=tuple(discovery_result.unavailable_entries),
                catalog_status=discovery_result.catalog_status,
                candidate_count=discovery_result.candidate_count,
                available_count=discovery_result.available_count,
                rejected_count=discovery_result.rejected_count,
                unavailable_count=discovery_result.unavailable_count,
                last_discovery_at=discovery_result.last_discovery_at,
            )
            initialize_registry(registry)
        else:
            try:
                from bremen.api.model_state import ModelState  # noqa: PLC0415
                ModelState.load_at_startup()
            except Exception:
                pass  # Non-fatal — catalog stays empty
            try:
                initialize_registry(build_legacy_registry())
            except Exception:
                pass  # Non-fatal

    @app.get("/demo")
    async def demo_start_page(request: Request) -> HTMLResponse:
        """Render the Bremen Start page (model selection)."""
        import uuid as _uuid  # noqa: PLC0415
        from bremen.start_page_ui import build_start_page  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        host_header = request.headers.get("host", "localhost")
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "http")
        base_url = f"{forwarded_proto}://{host_header}"
        html = build_start_page(base_url=base_url)
        return HTMLResponse(content=html, headers={"X-Request-ID": request_id})

    @app.get("/demo/control-room")
    async def demo_control_room(request: Request) -> HTMLResponse:
        """Render the Bremen Control Room page."""
        import uuid as _uuid  # noqa: PLC0415
        from bremen.control_room_ui import build_control_room_page  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        host_header = request.headers.get("host", "localhost")
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "http")
        base_url = f"{forwarded_proto}://{host_header}"
        html = build_control_room_page(base_url=base_url, request_id=request_id)
        return HTMLResponse(content=html, headers={"X-Request-ID": request_id})

    @app.get("/demo/model-guide")
    async def demo_model_guide(request: Request) -> HTMLResponse:
        """Render the sanitized Bremen Model Guide page."""
        import uuid as _uuid  # noqa: PLC0415
        from bremen.model_guide_ui import build_model_guide_page  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        html = build_model_guide_page()
        return HTMLResponse(content=html, headers={"X-Request-ID": request_id})

    # ------------------------------------------------------------------
    # GET /demo/model-playground — sandbox/playground page
    # ------------------------------------------------------------------
    @app.get("/demo/model-playground")
    async def demo_model_playground(request: Request) -> HTMLResponse:
        """Render the Bremen Model Playground sandbox page."""
        import uuid as _uuid  # noqa: PLC0415
        from bremen.model_playground_ui import build_model_playground_page  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        html = build_model_playground_page()
        return HTMLResponse(content=html, headers={"X-Request-ID": request_id})

    @app.get("/demo/model-playground/sandpit-0104t-preview")
    async def demo_model_playground_preview(request: Request) -> HTMLResponse:
        """Render the unlisted standalone Bremen Model Playground copy."""
        import uuid as _uuid  # noqa: PLC0415
        from bremen.model_playground_ui import (  # noqa: PLC0415
            build_model_playground_private_page,
        )

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        html = build_model_playground_private_page()
        return HTMLResponse(content=html, headers={"X-Request-ID": request_id})

    # ------------------------------------------------------------------
    # GET /demo/report/{job_id} — report HTML page parity
    # ------------------------------------------------------------------
    @app.get("/demo/report/{job_id}")
    async def demo_report_page(job_id: str, request: Request) -> HTMLResponse:
        """Render the Bremen Report page for a specific job.

        This is a job-bound browser-navigation HTML route. It accepts a valid
        Bearer access token or a short-lived job-bound report ticket via the
        ``auth_ticket`` query parameter. When neither is present it redirects to
        login instead of returning a raw JSON Bearer error as the page body.
        """
        gate = _check_auth_gate_with_ticket(request, job_id, "report")
        redirect = _browser_auth_redirect(gate, f"/demo/report/{job_id}")
        if redirect is not None:
            return redirect
        import uuid as _uuid  # noqa: PLC0415
        from bremen.report_ui import build_report_page  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        host_header = request.headers.get("host", "localhost")
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "http")
        base_url = f"{forwarded_proto}://{host_header}"
        html = build_report_page(base_url=base_url, job_id=job_id)
        return HTMLResponse(content=html, headers={"X-Request-ID": request_id})

    # ------------------------------------------------------------------
    # GET /demo/api-docs — API documentation page parity
    # ------------------------------------------------------------------
    @app.get("/demo/api-docs")
    async def demo_api_docs(request: Request) -> HTMLResponse:
        """Render the Bremen API documentation page."""
        import uuid as _uuid  # noqa: PLC0415
        from bremen.api_docs_ui import build_api_docs_page  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        host_header = request.headers.get("host", "localhost")
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "http")
        base_url = f"{forwarded_proto}://{host_header}"
        html = build_api_docs_page(base_url=base_url, request_id=request_id)
        return HTMLResponse(content=html, headers={"X-Request-ID": request_id})

    # ------------------------------------------------------------------
    # GET /demo/login — login page (PR0107 parity)
    # ------------------------------------------------------------------
    @app.get("/demo/login")
    async def demo_login_page(request: Request) -> HTMLResponse:
        """Render the Bremen login page.

        Mirrors ``_handle_login_route()`` from server.py.
        """
        import uuid as _uuid  # noqa: PLC0415
        from bremen.login_ui import build_login_page  # noqa: PLC0415
        from bremen.api.server import _get_auth_config as _gac  # noqa: PLC0415

        config = _gac()
        auth_enabled = config.enabled and not config.validation_error
        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        host_header = request.headers.get("host", "localhost")
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "http")
        base_url = f"{forwarded_proto}://{host_header}"
        html = build_login_page(base_url=base_url, auth_enabled=auth_enabled)
        return HTMLResponse(content=html, headers={"X-Request-ID": request_id})

    # ------------------------------------------------------------------
    # POST /demo/api/auth/token — authenticate and issue tokens (PR0107)
    # ------------------------------------------------------------------
    @app.post("/demo/api/auth/token")
    async def demo_auth_token_route(request: Request) -> JSONResponse:
        """Authenticate and issue tokens.

        Mirrors ``_handle_auth_token()`` from server.py.
        """
        from bremen.api.server import (  # noqa: PLC0415
            _get_auth_config as _gac,
            _AUTH_ERROR_SHAPE, _AUTH_DISABLED_SHAPE,
        )
        from bremen.auth import (  # noqa: PLC0415
            authenticate_credentials,
        )

        config = _gac()
        if not config.enabled or config.validation_error:
            return JSONResponse(
                content=__import__("json").loads(_AUTH_DISABLED_SHAPE),
                status_code=503,
            )

        try:
            body_bytes = await request.body()
            if not body_bytes:
                return JSONResponse(
                    content=__import__("json").loads(_AUTH_ERROR_SHAPE),
                    status_code=401,
                )
            body_dict = __import__("json").loads(body_bytes)
        except Exception:
            return JSONResponse(
                content=__import__("json").loads(_AUTH_ERROR_SHAPE),
                status_code=401,
            )

        username = body_dict.get("username", "")
        password = body_dict.get("password", "")
        if not isinstance(username, str) or not isinstance(password, str):
            return JSONResponse(
                content=__import__("json").loads(_AUTH_ERROR_SHAPE),
                status_code=401,
            )

        result = authenticate_credentials(config, username, password)
        if result is None:
            return JSONResponse(
                content=__import__("json").loads(_AUTH_ERROR_SHAPE),
                status_code=401,
            )

        return JSONResponse(content={
            "access_token": result.access_token,
            "refresh_token": result.refresh_token,
            "token_type": result.token_type,
            "expires_in": result.expires_in,
            "technical_demo_only": True,
        })

    # ------------------------------------------------------------------
    # POST /demo/api/auth/refresh — refresh access token (PR0107)
    # ------------------------------------------------------------------
    @app.post("/demo/api/auth/refresh")
    async def demo_auth_refresh_route(request: Request) -> JSONResponse:
        """Refresh access token.

        Mirrors ``_handle_auth_refresh()`` from server.py.
        """
        from bremen.api.server import (  # noqa: PLC0415
            _get_auth_config as _gac,
            _AUTH_ERROR_SHAPE, _AUTH_DISABLED_SHAPE,
        )
        from bremen.auth import (  # noqa: PLC0415
            decode_refresh_token, create_access_token,
            create_refresh_token, AuthError,
        )

        config = _gac()
        if not config.enabled or config.validation_error:
            return JSONResponse(
                content=__import__("json").loads(_AUTH_DISABLED_SHAPE),
                status_code=503,
            )

        try:
            body_bytes = await request.body()
            if not body_bytes:
                return JSONResponse(
                    content=__import__("json").loads(_AUTH_ERROR_SHAPE),
                    status_code=401,
                )
            body_dict = __import__("json").loads(body_bytes)
        except Exception:
            return JSONResponse(
                content=__import__("json").loads(_AUTH_ERROR_SHAPE),
                status_code=401,
            )

        refresh_token = body_dict.get("refresh_token", "")
        if not isinstance(refresh_token, str) or not refresh_token:
            return JSONResponse(
                content=__import__("json").loads(_AUTH_ERROR_SHAPE),
                status_code=401,
            )

        try:
            claims = decode_refresh_token(config, refresh_token)
        except AuthError:
            return JSONResponse(
                content=__import__("json").loads(_AUTH_ERROR_SHAPE),
                status_code=401,
            )

        new_access = create_access_token(config, claims.sub)
        new_refresh = create_refresh_token(config, claims.sub)

        return JSONResponse(content={
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "Bearer",
            "expires_in": config.access_ttl_seconds,
            "technical_demo_only": True,
        })

    # ------------------------------------------------------------------
    # GET /demo/workspace — multi-workflow workspace (PR0107 parity)
    # ------------------------------------------------------------------
    @app.get("/demo/workspace")
    async def demo_workspace_page(request: Request) -> HTMLResponse:
        """Render the Bremen Workspace page.

        Mirrors ``_handle_workspace_route()`` from server.py.

        This route has no job_id, so the job-bound ticket design does not map
        to it. It remains Bearer-gated for authenticated callers; when auth is
        missing it redirects to login instead of returning a raw JSON Bearer
        error as the browser page body.
        """
        gate = _check_auth_gate(request)
        redirect = _browser_auth_redirect(gate, "/demo/workspace")
        if redirect is not None:
            return redirect
        import uuid as _uuid  # noqa: PLC0415
        from bremen.workspace_ui import build_workspace_page  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        host_header = request.headers.get("host", "localhost")
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "http")
        base_url = f"{forwarded_proto}://{host_header}"
        html = build_workspace_page(base_url=base_url, request_id=request_id, job_id=None)
        return HTMLResponse(content=html, headers={"X-Request-ID": request_id})

    @app.get("/demo/workspace/{job_id}")
    async def demo_workspace_job_page(job_id: str, request: Request) -> HTMLResponse:
        """Render the Bremen Workspace page for a specific job.

        Mirrors ``_handle_workspace_route()`` from server.py.

        This is a job-bound browser-navigation HTML route. It accepts a valid
        Bearer access token or a short-lived job-bound workspace ticket via the
        ``auth_ticket`` query parameter. When neither is present it redirects to
        login instead of returning a raw JSON Bearer error as the page body.
        """
        gate = _check_auth_gate_with_ticket(request, job_id, "workspace")
        redirect = _browser_auth_redirect(gate, f"/demo/workspace/{job_id}")
        if redirect is not None:
            return redirect
        import uuid as _uuid  # noqa: PLC0415
        from bremen.workspace_ui import build_workspace_page  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        host_header = request.headers.get("host", "localhost")
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "http")
        base_url = f"{forwarded_proto}://{host_header}"
        html = build_workspace_page(base_url=base_url, request_id=request_id, job_id=job_id)
        return HTMLResponse(content=html, headers={"X-Request-ID": request_id})

    # ------------------------------------------------------------------
    # Phase 4: Event streaming routes
    # ------------------------------------------------------------------

    # Dedicated ThreadPoolExecutor for blocking wait_for_events() calls.
    # Using run_in_executor(None, ...) would exhaust the shared default
    # thread pool.  Bound to 4 workers for demo-stage concurrency.
    import concurrent.futures as _futures  # noqa: PLC0415
    _sse_executor = _futures.ThreadPoolExecutor(
        max_workers=4, thread_name_prefix="fastapi-sse",
    )

    # ------------------------------------------------------------------
    # Job read routes — parity with legacy http.server (Control Room)
    # ------------------------------------------------------------------

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
        from bremen.api.job_api_handler import (  # noqa: PLC0415
            list_analysis_jobs, _event_store,
        )

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        filter_model_id = request.query_params.get("model_id")
        filter_workflow_id = request.query_params.get("workflow_id")

        jobs = list_analysis_jobs(
            model_id=filter_model_id,
            workflow_id=filter_workflow_id,
        )
        return JSONResponse(content={
            "jobs": jobs,
            "storage_mode": _event_store.storage_mode,
            "retention_seconds": _event_store.retention_seconds,
            "max_jobs": _event_store.max_jobs,
            "request_id": request_id,
            "technical_demo_only": True,
        })

    @app.get("/demo/api/jobs/{job_id}")
    async def demo_job_detail_route(
        job_id: str, request: Request,
    ) -> JSONResponse:
        """Get job status and execution traces.

        Mirrors ``handle_job_get()`` from job_api_handler.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
        import uuid as _uuid  # noqa: PLC0415
        from bremen.api.job_api_handler import (  # noqa: PLC0415
            _jobs, _jobs_lock, _event_store,
        )
        from bremen.api.execution_trace import build_trace_from_events  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())

        with _jobs_lock:
            job = _jobs.get(job_id)

        if job is None:
            if _event_store.has_job(job_id):
                return JSONResponse(content={
                    "error": "Job has expired",
                    "job_id": job_id,
                    "storage_mode": _event_store.storage_mode,
                    "request_id": request_id,
                }, status_code=410)
            return JSONResponse(content={
                "error": "Job not found",
                "job_id": job_id,
                "request_id": request_id,
            }, status_code=404)

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

    @app.get("/demo/api/jobs/{job_id}/reports")
    async def demo_job_reports_route(
        job_id: str, request: Request,
    ) -> JSONResponse:
        """List reports for a job.

        Mirrors ``handle_job_reports()`` from job_api_handler.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
        import uuid as _uuid  # noqa: PLC0415
        from bremen.api.job_api_handler import get_job_reports  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        result = get_job_reports(job_id)
        result["request_id"] = request_id
        result["technical_demo_only"] = True
        return JSONResponse(content=result)

    @app.get("/demo/api/jobs/{job_id}/reports/{workflow_id}")
    async def demo_job_report_detail_route(
        job_id: str, workflow_id: str, request: Request,
    ) -> JSONResponse:
        """Get a specific workflow report.

        Mirrors ``handle_job_report()`` from job_api_handler.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
        import uuid as _uuid  # noqa: PLC0415
        from bremen.api.job_api_handler import get_job_report  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        result = get_job_report(job_id, workflow_id)
        result["request_id"] = request_id
        result["technical_demo_only"] = True
        return JSONResponse(content=result)

    # ------------------------------------------------------------------
    # Report data routes — parity with legacy http.server
    # ------------------------------------------------------------------

    @app.get("/demo/api/reports/{job_id}/external")
    async def demo_external_report_route(
        job_id: str, request: Request,
    ) -> JSONResponse:
        """Return external report JSON.

        Mirrors ``handle_external_report()`` from job_api_handler.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
        import uuid as _uuid  # noqa: PLC0415
        from bremen.api.job_api_handler import (  # noqa: PLC0415
            _jobs, _jobs_lock, _get_report_provider,
        )
        from bremen.report_ui import build_external_report_json  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())

        with _jobs_lock:
            job = _jobs.get(job_id)

        if job is None:
            return JSONResponse(content={
                "error": "Job not found", "job_id": job_id,
                "request_id": request_id,
                "technical_demo_only": True,
            })

        provider = _get_report_provider("bremen")
        wf_run = job.workflow_runs.get("bremen")
        if provider is None or wf_run is None:
            return JSONResponse(content={
                "error": "Report not available", "job_id": job_id,
                "request_id": request_id,
                "technical_demo_only": True,
            })

        report = provider.generate_report(
            job_id=job_id,
            workflow_result=wf_run.result_summary,
            model_identity=wf_run.model_identity,
            readiness_snapshot=wf_run.readiness_snapshot,
        )
        external = build_external_report_json(report.to_dict())
        external["request_id"] = request_id
        external["technical_demo_only"] = True
        return JSONResponse(content=external)

    @app.get("/demo/api/reports/{job_id}/internal")
    async def demo_internal_report_route(
        job_id: str, request: Request,
    ) -> JSONResponse:
        """Return internal report JSON.

        Mirrors ``handle_internal_report()`` from job_api_handler.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
        import uuid as _uuid  # noqa: PLC0415
        from bremen.api.job_api_handler import (  # noqa: PLC0415
            _jobs, _jobs_lock, _get_report_provider,
        )
        from bremen.report_ui import build_internal_report_json  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())

        with _jobs_lock:
            job = _jobs.get(job_id)

        if job is None:
            return JSONResponse(content={
                "error": "Job not found", "job_id": job_id,
                "request_id": request_id,
                "technical_demo_only": True,
            })

        provider = _get_report_provider("bremen")
        wf_run = job.workflow_runs.get("bremen")
        if provider is None or wf_run is None:
            return JSONResponse(content={
                "error": "Report not available", "job_id": job_id,
                "request_id": request_id,
                "technical_demo_only": True,
            })

        report = provider.generate_report(
            job_id=job_id,
            workflow_result=wf_run.result_summary,
            model_identity=wf_run.model_identity,
            readiness_snapshot=wf_run.readiness_snapshot,
        )
        internal = build_internal_report_json(report.to_dict())
        internal["request_id"] = request_id
        internal["technical_demo_only"] = True
        return JSONResponse(content=internal)

    # Terminal statuses — must match http.server handler exactly
    _TERMINAL_STATUSES = frozenset({
        "completed", "failed", "partial_success",
        "workflow_configuration_required",
    })

    @app.get("/demo/api/jobs/{job_id}/events")
    async def job_events_json_route(
        job_id: str, request: Request,
    ) -> JSONResponse:
        """JSON polling endpoint for job events.

        Mirrors ``handle_job_events()`` from job_api_handler.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
        import uuid as _uuid  # noqa: PLC0415
        from bremen.api.job_api_handler import (  # noqa: PLC0415
            _event_store, get_job_events,
        )
        from bremen.api.event_schema import allowed_event_details  # noqa: PLC0415

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

        return JSONResponse(content={
            "events": safe_events,
            "cursor": cursor,
            "job_id": job_id,
            "request_id": request_id,
            "technical_demo_only": True,
        })

    @app.post("/demo/api/jobs/{job_id}/auth/ticket")
    async def demo_auth_ticket_route(
        job_id: str, request: Request,
    ) -> JSONResponse:
        """Mint a short-lived ticket for SSE or report-page navigation.

        Requires a valid Bearer access token via _check_auth_gate.
        The ticket is a distinct JWT type (stream_ticket) bound to
        a specific job_id and purpose.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate

        from bremen.api.server import _get_auth_config as _gac  # noqa: PLC0415

        config = _gac()

        # Parse purpose from request body
        try:
            body_bytes = await request.body()
            body_dict = __import__("json").loads(body_bytes) if body_bytes else {}
        except Exception:  # noqa: BLE001
            body_dict = {}

        purpose = body_dict.get("purpose", "")
        if purpose not in ("stream", "report"):
            return JSONResponse(
                content={"error": "Invalid ticket purpose"},
                status_code=400,
            )

        # Verify job exists
        from bremen.api.job_api_handler import _jobs, _jobs_lock, _event_store  # noqa: PLC0415

        with _jobs_lock:
            job = _jobs.get(job_id)
        if job is None and not _event_store.has_job(job_id):
            return JSONResponse(
                content={"error": "Job not found", "job_id": job_id},
                status_code=404,
            )

        # Extract username from access token claims
        auth_header = request.headers.get("Authorization")
        token = ""
        if auth_header and auth_header.strip().startswith("Bearer "):
            token = auth_header.split(None, 1)[1].strip()

        from bremen.auth import decode_access_token  # noqa: PLC0415
        claims = decode_access_token(config, token)

        # Mint ticket
        from bremen.auth import create_stream_ticket  # noqa: PLC0415
        ticket = create_stream_ticket(config, claims.sub, job_id, purpose)

        return JSONResponse(content={
            "ticket": ticket,
            "expires_in": 60,
            "token_type": "stream_ticket",
            "job_id": job_id,
            "purpose": purpose,
            "technical_demo_only": True,
        }, status_code=201)

    @app.get("/demo/api/jobs/{job_id}/events/stream")
    async def job_events_stream_route(
        job_id: str, request: Request,
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
        from bremen.api.job_api_handler import (  # noqa: PLC0415
            _event_store, _jobs, _jobs_lock,
        )
        from bremen.api.event_schema import allowed_event_details  # noqa: PLC0415

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
                event_type: str, data: str, event_id: str = "",
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
                ev_dict["details"] = allowed_event_details(
                    ev_dict.get("details", {})
                )
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
                            job_id, since_sequence=cursor,
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
                        job_id, cursor, heartbeat_interval,
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
