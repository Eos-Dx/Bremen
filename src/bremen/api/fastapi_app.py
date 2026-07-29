"""Isolated FastAPI foundation for Phase 1 migration.

This module provides ``create_fastapi_app()`` — a FastAPI application
factory that registers Phase 1 routes:

- ``GET /health``
- ``GET /model/version``

These routes reuse existing business logic from ``bremen.api.app``
(``handle_health``, ``handle_model_version``).

Coexistence strategy
--------------------
This FastAPI app is **isolated** from the production ``http.server``
path.  It is intended for testing and future migration phases only.

- Production Dockerfile target/ENTRYPOINT/CMD remain unchanged.
- Production ``http.server`` routes remain untouched.
- No catalog, POST, SSE, or event-streaming routes are implemented here.

Phase 1 foundation — no Pydantic request contracts, no auth integration,
no control room routes.  Those belong to later phases.

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

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def create_fastapi_app(version: str | None = None) -> FastAPI:
    """Create and return a FastAPI application with Phase 1 routes.

    Parameters
    ----------
    version : Optional version string forwarded to the health endpoint.

    Returns
    -------
    A configured ``FastAPI`` instance ready for a ``TestClient`` or
    ``uvicorn``.
    """
    app = FastAPI(
        title="Bremen API (FastAPI Phase 1)",
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
