"""Bremen HTTP composition root. Package science loads only on execution."""

from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize existing model state/catalog once for the app lifetime."""
    import os as _os
    from bremen.platform.models.registry import initialize_registry, build_legacy_registry
    catalog_uri = _os.environ.get("BREMEN_MODEL_CATALOG_URI", "").strip()
    if catalog_uri:
        from bremen.platform.models.discovery import discover_models
        from bremen.platform.models.registry import ModelRegistry
        discovery_result = discover_models(catalog_uri)
        initialize_registry(ModelRegistry(
            entries=tuple(discovery_result.entries),
            unavailable_entries=tuple(discovery_result.unavailable_entries),
            catalog_status=discovery_result.catalog_status,
            candidate_count=discovery_result.candidate_count,
            available_count=discovery_result.available_count,
            rejected_count=discovery_result.rejected_count,
            unavailable_count=discovery_result.unavailable_count,
            last_discovery_at=discovery_result.last_discovery_at,
        ))
    else:
        try:
            from bremen.platform.models.state import ModelState
            ModelState.load_at_startup()
        except Exception:
            pass
        try:
            initialize_registry(build_legacy_registry())
        except Exception:
            pass
    yield


def create_app(version: str | None = None) -> FastAPI:
    app = FastAPI(
        lifespan=lifespan,
        title="Bremen API (FastAPI)",
        version="0.1.0",
        description="Bremen FastAPI decision-support service.",
        # Disable OpenAPI docs in Phase 1 — no Pydantic schemas yet
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )

    @app.middleware("http")
    async def _suppress_health_access_log(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Suppress uvicorn access log for /health probes.

        Tags the request so the uvicorn log filter can skip it.
        All other requests pass through unmodified.
        """
        if request.url.path == "/health":
            request.scope["access_log"] = False
        return await call_next(request)

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Catch-all exception handler — never exposes raw trace details."""
        return JSONResponse(
            content={"error": "Internal error"},
            status_code=500,
        )

    from bremen.api.http.routers import system

    system.register(app, version)
    from bremen.api.http.routers import models

    models.register(app, version)
    from bremen.api.http.routers import sources

    sources.register(app, version)
    from bremen.api.http.routers import jobs

    jobs.register(app, version)
    from bremen.api.http.routers import reports

    reports.register(app, version)
    from bremen.api.http.routers import events

    events.register(app, version)
    from bremen.api.http.routers import auth

    auth.register(app, version)
    from bremen.api.http.routers import ui

    ui.register(app, version)
    return app
