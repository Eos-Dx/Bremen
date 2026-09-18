"""System HTTP route translation."""

from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def register(app: FastAPI, version=None):

    @app.get("/health")
    async def health_route(request: Request) -> JSONResponse:
        """Return service health status.

        Reads readiness from the platform model registry/state.
        """
        from bremen.api.http.system_support import handle_health as _handle_health

        resp = _handle_health(version=version)
        return JSONResponse(
            content={
                "status": resp.status,
                "service": resp.service,
                "version": resp.version,
                "timestamp": resp.timestamp,
                "model_ready": resp.model_ready,
            }
        )

    @app.get("/model/version")
    async def model_version_route(request: Request) -> JSONResponse:
        """Return configured model package metadata.

        Reads model metadata from the platform model owner.
        """
        from bremen.api.http.system_support import handle_model_version as _handle_model_version

        resp = _handle_model_version()
        return JSONResponse(
            content={
                "model_configured": resp.model_configured,
                "model_version": resp.model_version,
                "model_checksum": resp.model_checksum,
                "feature_schema_version": resp.feature_schema_version,
                "threshold_version": resp.threshold_version,
                "threshold_value": resp.threshold_value,
                "qc_criteria_version": resp.qc_criteria_version,
                "model_status": resp.model_status,
            }
        )
