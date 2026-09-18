"""Models HTTP route translation."""

from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from bremen.api.http.http_policy import (
    _check_auth_gate,
)


def register(app: FastAPI, version=None):

    @app.get("/demo/api/models")
    async def demo_models_route(request: Request) -> JSONResponse:
        """Return the model catalog.

        Reuses :func:`bremen.platform.models.catalog.build_model_catalog`
        for business logic.
        """
        from bremen.platform.models.catalog import (  # noqa: PLC0415
            build_model_catalog as _build_model_catalog,
        )
        import uuid as _uuid  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        catalog = _build_model_catalog()
        catalog["request_id"] = request_id
        catalog["technical_demo_only"] = True
        return JSONResponse(content=catalog)

    @app.get("/demo/api/models/{model_id}/requirements")
    async def demo_model_requirements_route(
        model_id: str,
        request: Request,
    ) -> JSONResponse:
        """Return model-specific container requirements.

        PR0122 exposes the API shape as an honest no-op contract.
        The current runner does not yet declare raw H5 requirement fields.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate

        import uuid as _uuid  # noqa: PLC0415
        from bremen.api.model_requirements import (  # noqa: PLC0415
            ModelRequirementsNotFoundError,
            build_model_requirements_response,
        )

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())

        try:
            data = build_model_requirements_response(
                model_id,
                request_id=request_id,
            )
        except ModelRequirementsNotFoundError:
            return JSONResponse(
                content={
                    "error": "Model not found",
                    "model_id": model_id,
                    "request_id": request_id,
                    "technical_demo_only": True,
                },
                status_code=404,
            )

        return JSONResponse(content=data, status_code=200)

    @app.post("/demo/api/models/{model_id}/requirements/validate")
    async def demo_model_requirements_validate_route(
        model_id: str,
        request: Request,
    ) -> JSONResponse:
        """Return no-op validation result for model requirements.

        This endpoint intentionally does not open H5, run inference, create
        jobs, or generate reports until the runner declares real requirements.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate

        import uuid as _uuid  # noqa: PLC0415
        from bremen.api.fastapi_contracts import (  # noqa: PLC0415
            ModelRequirementsValidateRequest,
        )
        from bremen.api.model_requirements import (  # noqa: PLC0415
            ModelRequirementsNotFoundError,
            build_model_requirements_validation_response,
        )

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())

        try:
            body_bytes = await request.body()
            body_dict = __import__("json").loads(body_bytes) if body_bytes else {}
            if not isinstance(body_dict, dict):
                raise ValueError("JSON body must be an object")
        except Exception:
            return JSONResponse(
                content={
                    "error": "Invalid JSON body",
                    "request_id": request_id,
                    "technical_demo_only": True,
                },
                status_code=400,
            )

        try:
            req = ModelRequirementsValidateRequest(**body_dict)
        except Exception as exc:
            return JSONResponse(
                content={
                    "error": f"Invalid request: {exc}",
                    "request_id": request_id,
                    "technical_demo_only": True,
                },
                status_code=400,
            )

        payload = req.model_dump(exclude_none=True)

        try:
            data = build_model_requirements_validation_response(
                model_id,
                payload,
                request_id=request_id,
            )
        except ModelRequirementsNotFoundError:
            return JSONResponse(
                content={
                    "error": "Model not found",
                    "model_id": model_id,
                    "request_id": request_id,
                    "technical_demo_only": True,
                },
                status_code=404,
            )

        return JSONResponse(content=data, status_code=200)
