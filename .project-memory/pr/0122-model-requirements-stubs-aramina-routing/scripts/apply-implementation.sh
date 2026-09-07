#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
from pathlib import Path

# ---------------------------------------------------------------------
# 1. Add model requirements helper module
# ---------------------------------------------------------------------

Path("src/bremen/api/model_requirements.py").write_text('''"""Model-specific container requirements API helpers.

PR0122 implements the public API shape only.

The current runner/model stack does not yet declare raw H5/container
requirement fields, so these helpers intentionally return honest
not-available/no-op contracts.

No H5 is opened here.
No inference job is created here.
No report is created here.
"""

from __future__ import annotations

from typing import Any


class ModelRequirementsNotFoundError(Exception):
    """Requested model_id does not exist in the current catalog."""


def find_model_catalog_row(
    model_id: str,
    *,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return a safe public catalog row for model_id.

    Searches both available models and display-only unavailable models.
    This lets the requirements API support future unavailable Aramina
    catalog rows without treating them as executable.
    """
    if catalog is None:
        from bremen.api.model_catalog import build_model_catalog  # noqa: PLC0415

        catalog = build_model_catalog()

    for key in ("models", "unavailable_models"):
        rows = catalog.get(key, [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("model_id") == model_id:
                return dict(row)

    return None


def build_model_requirements_response(
    model_id: str,
    *,
    catalog: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build the current no-op model requirements response."""
    row = find_model_catalog_row(model_id, catalog=catalog)
    if row is None:
        raise ModelRequirementsNotFoundError(model_id)

    response: dict[str, Any] = {
        "schema_version": "bremen.model_requirements.v1",
        "technical_demo_only": True,
        "model_id": model_id,
        "workflow_id": row.get("workflow_id"),
        "model_version": row.get("model_version"),
        "feature_schema_version": row.get("feature_schema_version"),
        "requirements_available": False,
        "status": "requirements_not_declared",
        "required_container_contract": None,
        "required_fields": [],
        "optional_fields": [],
        "notes": [
            "This endpoint is reserved for model-specific H5/container requirements.",
            "The current runner does not yet declare raw H5 requirement fields.",
            "No container is opened.",
            "No inference job is created.",
            "No report is generated.",
        ],
    }
    if request_id:
        response["request_id"] = request_id
    return response


def build_model_requirements_validation_response(
    model_id: str,
    request_payload: dict[str, Any],
    *,
    catalog: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build the current no-op model requirements validation response."""
    row = find_model_catalog_row(model_id, catalog=catalog)
    if row is None:
        raise ModelRequirementsNotFoundError(model_id)

    response: dict[str, Any] = {
        "schema_version": "bremen.model_requirements_validation.v1",
        "technical_demo_only": True,
        "model_id": model_id,
        "workflow_id": row.get("workflow_id"),
        "model_version": row.get("model_version"),
        "feature_schema_version": row.get("feature_schema_version"),
        "container_id": request_payload.get("container_id"),
        "source_id": request_payload.get("source_id"),
        "upload_id": request_payload.get("upload_id"),
        "h5_path": request_payload.get("h5_path"),
        "validation_available": False,
        "validation": {
            "status": "not_available",
            "ready_to_run": None,
            "requirements_checked": False,
            "inference_job_created": False,
            "report_created": False,
        },
        "missing_required_fields": [],
        "invalid_fields": [],
        "next_step": {
            "can_submit_job": None,
            "reason": (
                "Model-specific requirements validation is not implemented yet. "
                "Use POST /demo/api/jobs for the current production execution path."
            ),
        },
    }
    if request_id:
        response["request_id"] = request_id
    return response
''')

# ---------------------------------------------------------------------
# 2. Extend FastAPI contracts
# ---------------------------------------------------------------------

contracts = Path("src/bremen/api/fastapi_contracts.py")
text = contracts.read_text()

if "class ModelRequirementsValidateRequest" not in text:
    text = text.replace(
        "from typing import Optional\n",
        "from typing import Any, Optional\n",
    )

    text += '''


class ModelRequirementsValidateRequest(BaseModel):
    """Request body for POST /demo/api/models/{model_id}/requirements/validate.

    This is intentionally permissive in PR0122 because validation is a
    no-op/not-available contract. The endpoint echoes safe identifiers but
    must not open H5, create inference jobs, or create reports.
    """

    container_id: Optional[str] = Field(default=None, description="Catalog/display container ID")
    source_id: Optional[str] = Field(default=None, description="Fresh catalog source ID")
    upload_id: Optional[str] = Field(default=None, description="Staged upload ID")
    h5_path: Optional[str] = Field(default=None, description="Legacy explicit H5 path")
    workflow_id: Optional[str] = Field(default=None, description="Workflow routing key")
    storage: Optional[dict[str, Any]] = Field(default=None, description="Future direct storage reference")
'''
    contracts.write_text(text)

# ---------------------------------------------------------------------
# 3. Add FastAPI routes
# ---------------------------------------------------------------------

app_path = Path("src/bremen/api/fastapi_app.py")
app = app_path.read_text()

if '"/demo/api/models/{model_id}/requirements"' not in app:
    marker = '''    # ------------------------------------------------------------------
    # GET /demo/api/h5/containers — H5 container listing (Phase 2)
    # ------------------------------------------------------------------
'''
    insert = '''    # ------------------------------------------------------------------
    # GET /demo/api/models/{model_id}/requirements — no-op model requirements
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # POST /demo/api/models/{model_id}/requirements/validate — no-op validate
    # ------------------------------------------------------------------
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

        payload = req.dict(exclude_none=True)

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

'''
    if marker not in app:
        raise SystemExit("Could not find insertion marker in fastapi_app.py")
    app = app.replace(marker, insert + marker)
    app_path.write_text(app)

# ---------------------------------------------------------------------
# 4. Add focused tests
# ---------------------------------------------------------------------

Path("tests/test_bremen_model_requirements_api.py").write_text('''"""Tests for PR0122 model requirements no-op API."""

from __future__ import annotations

from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from bremen.api.fastapi_app import create_fastapi_app
from bremen.api.model_registry import (
    ModelRegistry,
    RegistryModelEntry,
    initialize_registry,
    reset_for_tests as reset_model_registry_for_tests,
)
from bremen.api.server import _reset_auth_config
from bremen.auth import create_access_token
from bremen.config import read_auth_config


_VALID_PASSWORD_HASH = PasswordHasher().hash("test-password-123")
_JWT_SECRET = "r" * 48


def _enable_auth(monkeypatch) -> None:
    monkeypatch.setenv("BREMEN_AUTH_ENABLED", "true")
    monkeypatch.setenv("BREMEN_AUTH_USERNAME", "testuser")
    monkeypatch.setenv("BREMEN_AUTH_PASSWORD_HASH", _VALID_PASSWORD_HASH)
    monkeypatch.setenv("BREMEN_AUTH_JWT_SECRET", _JWT_SECRET)
    _reset_auth_config()


def _auth_headers() -> dict[str, str]:
    config = read_auth_config()
    token = create_access_token(config, "testuser")
    return {"Authorization": f"Bearer {token}"}


def _install_test_registry() -> None:
    reset_model_registry_for_tests()
    entry = RegistryModelEntry(
        model_id="bremen-mri-triage-logreg-v0-1",
        display_name="Bremen Current",
        workflow_id="bremen",
        model_version="bremen_mri_triage_logreg_v0_1",
        artifact_type="portable_logreg",
        feature_schema_version="v0.1",
        decision_policy_id="bremen_mri_triage_policy",
        decision_policy_version="v0.1",
        technical_ready=True,
        scientifically_certified=False,
        technical_demo_only=True,
        availability="available",
        _package={"portable_logreg": {"feature_schema_version": "v0.1"}},
        _checksum="test-checksum",
    )
    initialize_registry(
        ModelRegistry(
            entries=(entry,),
            catalog_status="available",
            candidate_count=1,
            available_count=1,
            rejected_count=0,
            unavailable_count=0,
        )
    )


def _client() -> TestClient:
    return TestClient(create_fastapi_app())


def test_get_model_requirements_requires_bearer_auth(monkeypatch):
    _enable_auth(monkeypatch)
    _install_test_registry()

    response = _client().get(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements"
    )

    assert response.status_code == 401
    assert response.json()["token_type"] == "Bearer"


def test_post_model_requirements_validate_requires_bearer_auth(monkeypatch):
    _enable_auth(monkeypatch)
    _install_test_registry()

    response = _client().post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        json={"container_id": "Nova_376.h5", "source_id": "source-1"},
    )

    assert response.status_code == 401
    assert response.json()["token_type"] == "Bearer"


def test_get_model_requirements_known_model_returns_honest_noop(monkeypatch):
    _enable_auth(monkeypatch)
    _install_test_registry()

    response = _client().get(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["schema_version"] == "bremen.model_requirements.v1"
    assert data["technical_demo_only"] is True
    assert data["model_id"] == "bremen-mri-triage-logreg-v0-1"
    assert data["workflow_id"] == "bremen"
    assert data["model_version"] == "bremen_mri_triage_logreg_v0_1"
    assert data["feature_schema_version"] == "v0.1"
    assert data["requirements_available"] is False
    assert data["status"] == "requirements_not_declared"
    assert data["required_container_contract"] is None
    assert data["required_fields"] == []
    assert data["optional_fields"] == []


def test_get_model_requirements_unknown_model_returns_404(monkeypatch):
    _enable_auth(monkeypatch)
    _install_test_registry()

    response = _client().get(
        "/demo/api/models/unknown-model/requirements",
        headers=_auth_headers(),
    )

    assert response.status_code == 404
    assert response.json()["error"] == "Model not found"
    assert response.json()["model_id"] == "unknown-model"


def test_post_model_requirements_validate_known_model_returns_noop(monkeypatch):
    _enable_auth(monkeypatch)
    _install_test_registry()

    response = _client().post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={
            "container_id": "Nova_376.h5",
            "source_id": "fresh-source-id",
            "workflow_id": "bremen",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["schema_version"] == "bremen.model_requirements_validation.v1"
    assert data["technical_demo_only"] is True
    assert data["model_id"] == "bremen-mri-triage-logreg-v0-1"
    assert data["workflow_id"] == "bremen"
    assert data["container_id"] == "Nova_376.h5"
    assert data["source_id"] == "fresh-source-id"
    assert data["validation_available"] is False
    assert data["validation"]["status"] == "not_available"
    assert data["validation"]["ready_to_run"] is None
    assert data["validation"]["requirements_checked"] is False
    assert data["validation"]["inference_job_created"] is False
    assert data["validation"]["report_created"] is False
    assert data["missing_required_fields"] == []
    assert data["invalid_fields"] == []


def test_post_model_requirements_validate_unknown_model_returns_404(monkeypatch):
    _enable_auth(monkeypatch)
    _install_test_registry()

    response = _client().post(
        "/demo/api/models/unknown-model/requirements/validate",
        headers=_auth_headers(),
        json={"container_id": "Nova_376.h5", "source_id": "fresh-source-id"},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "Model not found"
    assert response.json()["model_id"] == "unknown-model"


def test_post_model_requirements_validate_does_not_create_job(monkeypatch):
    _enable_auth(monkeypatch)
    _install_test_registry()

    from bremen.api.job_api_handler import _jobs, _jobs_lock

    with _jobs_lock:
        before = set(_jobs)

    response = _client().post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={"container_id": "Nova_376.h5", "source_id": "fresh-source-id"},
    )

    assert response.status_code == 200

    with _jobs_lock:
        after = set(_jobs)

    assert after == before
    assert response.json()["validation"]["inference_job_created"] is False
    assert response.json()["validation"]["report_created"] is False
''')

print("PR0122 implementation files written")
PY
