"""Ui HTTP route translation."""

from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from bremen.api.http.http_policy import (
    _check_auth_gate,
    _check_auth_gate_with_ticket,
    _browser_auth_redirect,
)


def register(app: FastAPI, version=None):

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

    @app.get("/demo/report/{job_id}")
    async def demo_report_page(job_id: str, request: Request) -> HTMLResponse:
        """Render the Bremen Report page for a specific job.

        This is a job-bound browser-navigation HTML route. It accepts a valid
        Bearer access token or a short-lived job-bound report ticket via the
        ``auth_ticket`` query parameter.

        - With a valid Bearer or valid report ticket: returns the full report.
        - With an invalid ticket (wrong purpose/job): redirects to login.
        - With no Bearer and no auth_ticket: returns a safe bootstrap shell
          (200 HTML) that mints a report ticket client-side and navigates to
          the canonical ticketed URL. No protected report data is exposed.
        """
        has_ticket = bool(request.query_params.get("auth_ticket", ""))
        gate = _check_auth_gate_with_ticket(request, job_id, "report")
        if gate is not None:
            if has_ticket:
                # Invalid ticket present → wrong ticket must not work.
                redirect = _browser_auth_redirect(gate, f"/demo/report/{job_id}")
                if redirect is not None:
                    return redirect
            else:
                # No Bearer and no ticket → safe bootstrap shell.
                import uuid as _uuid  # noqa: PLC0415
                from bremen.report_ui import build_report_bootstrap_page  # noqa: PLC0415

                request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
                host_header = request.headers.get("host", "localhost")
                forwarded_proto = request.headers.get("X-Forwarded-Proto", "http")
                base_url = f"{forwarded_proto}://{host_header}"
                html = build_report_bootstrap_page(base_url=base_url, job_id=job_id)
                return HTMLResponse(content=html, headers={"X-Request-ID": request_id})
        import uuid as _uuid  # noqa: PLC0415
        from bremen.report_ui import build_report_page  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        host_header = request.headers.get("host", "localhost")
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "http")
        base_url = f"{forwarded_proto}://{host_header}"
        html = build_report_page(base_url=base_url, job_id=job_id)
        return HTMLResponse(content=html, headers={"X-Request-ID": request_id})

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

    @app.get("/demo/login")
    async def demo_login_page(request: Request) -> HTMLResponse:
        """Render the Bremen login page.

        Mirrors ``_handle_login_route()`` from server.py.
        """
        import uuid as _uuid  # noqa: PLC0415
        from bremen.login_ui import build_login_page  # noqa: PLC0415
        from bremen.api.http.auth_config import _get_auth_config as _gac  # noqa: PLC0415

        config = _gac()
        auth_enabled = config.enabled and not config.validation_error
        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        host_header = request.headers.get("host", "localhost")
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "http")
        base_url = f"{forwarded_proto}://{host_header}"
        html = build_login_page(base_url=base_url, auth_enabled=auth_enabled)
        return HTMLResponse(content=html, headers={"X-Request-ID": request_id})

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
        html = build_workspace_page(
            base_url=base_url, request_id=request_id, job_id=None
        )
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
        html = build_workspace_page(
            base_url=base_url, request_id=request_id, job_id=job_id
        )
        return HTMLResponse(content=html, headers={"X-Request-ID": request_id})
