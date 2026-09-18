"""Auth HTTP route translation."""

from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from bremen.api.http.http_policy import (
    _check_auth_gate,
)


def register(app: FastAPI, version=None):

    @app.post("/demo/api/auth/token")
    async def demo_auth_token_route(request: Request) -> JSONResponse:
        """Authenticate and issue tokens.

        Mirrors ``_handle_auth_token()`` from server.py.
        """
        from bremen.api.http.auth_config import (  # noqa: PLC0415
            _get_auth_config as _gac,
            _AUTH_ERROR_SHAPE,
            _AUTH_DISABLED_SHAPE,
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

        return JSONResponse(
            content={
                "access_token": result.access_token,
                "refresh_token": result.refresh_token,
                "token_type": result.token_type,
                "expires_in": result.expires_in,
                "technical_demo_only": True,
            }
        )

    @app.post("/demo/api/auth/refresh")
    async def demo_auth_refresh_route(request: Request) -> JSONResponse:
        """Refresh access token.

        Mirrors ``_handle_auth_refresh()`` from server.py.
        """
        from bremen.api.http.auth_config import (  # noqa: PLC0415
            _get_auth_config as _gac,
            _AUTH_ERROR_SHAPE,
            _AUTH_DISABLED_SHAPE,
        )
        from bremen.auth import (  # noqa: PLC0415
            decode_refresh_token,
            create_access_token,
            create_refresh_token,
            AuthError,
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

        return JSONResponse(
            content={
                "access_token": new_access,
                "refresh_token": new_refresh,
                "token_type": "Bearer",
                "expires_in": config.access_ttl_seconds,
                "technical_demo_only": True,
            }
        )

    @app.post("/demo/api/jobs/{job_id}/auth/ticket")
    async def demo_auth_ticket_route(
        job_id: str,
        request: Request,
    ) -> JSONResponse:
        """Mint a short-lived ticket for SSE or report-page navigation.

        Requires a valid Bearer access token via _check_auth_gate.
        The ticket is a distinct JWT type (stream_ticket) bound to
        a specific job_id and purpose.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate

        from bremen.api.http.auth_config import _get_auth_config as _gac  # noqa: PLC0415

        config = _gac()

        # Parse purpose from request body
        try:
            body_bytes = await request.body()
            body_dict = __import__("json").loads(body_bytes) if body_bytes else {}
        except Exception:  # noqa: BLE001
            body_dict = {}

        purpose = body_dict.get("purpose", "")
        if purpose not in ("stream", "report", "workspace"):
            return JSONResponse(
                content={"error": "Invalid ticket purpose"},
                status_code=400,
            )

        # Verify job exists
        from bremen.platform.jobs.service import _jobs
        from bremen.platform.jobs.service import _jobs_lock
        from bremen.platform.jobs.service import _event_store

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

        return JSONResponse(
            content={
                "ticket": ticket,
                "expires_in": 60,
                "token_type": "stream_ticket",
                "job_id": job_id,
                "purpose": purpose,
                "technical_demo_only": True,
            },
            status_code=201,
        )
