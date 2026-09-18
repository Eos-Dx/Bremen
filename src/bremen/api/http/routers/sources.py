"""Sources HTTP route translation."""

from __future__ import annotations
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import JSONResponse
from bremen.api.http.http_policy import (
    _check_auth_gate,
)


def register(app: FastAPI, version=None):

    @app.get("/demo/api/h5/containers")
    async def demo_h5_containers_route(request: Request) -> JSONResponse:
        """List demo H5 containers.

        Reuses :func:`bremen.platform.sources.demo_storage._build_containers_response`
        for business logic (shared with the http.server handler).
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
        import uuid as _uuid  # noqa: PLC0415
        from bremen.platform.sources.demo_storage import (  # noqa: PLC0415
            _build_containers_response as _build_containers,
        )

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        data = _build_containers(request_id=request_id)
        return JSONResponse(content=data)

    @app.post("/demo/api/h5/containers")
    async def demo_h5_upload_route(
        request: Request,
        file: UploadFile = File(...),
    ) -> JSONResponse:
        """Upload an H5 container file.

        Reuses :func:`bremen.platform.sources.demo_storage._handle_h5_upload_bytes`
        for validation and S3 upload logic.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
        import uuid as _uuid  # noqa: PLC0415
        from bremen.platform.sources.demo_storage import (  # noqa: PLC0415
            _handle_h5_upload_bytes as _upload_bytes,
        )

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        raw_filename = file.filename or ""
        raw_body = await file.read()

        status_code, data = _upload_bytes(raw_body, raw_filename, request_id)
        return JSONResponse(content=data, status_code=status_code)
