"""HTTP API freeze guard for PR0156 (Model Package Standard v1 refactor).

PR0156 is an internal refactor behind the provider/runtime boundary.  All
existing public HTTP endpoints are frozen: this test locks the exact route
table (method, path) exposed by the live FastAPI application and asserts the
public route surface is unchanged.  It also asserts no route was added to
expose the model-package standard or MLflow, and that externally-consumed
response schemas keep their frozen top-level keys.

If a future architectural change requires an endpoint change, it must be made
in its own reviewed PR — never bundled into an internal ownership refactor.
"""
from __future__ import annotations

import pytest

from bremen.api.fastapi_app import create_fastapi_app

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - fastapi is a hard dependency
    TestClient = None  # type: ignore[assignment]


# Frozen at PR0156 (verified against HEAD).  29 routes.
FROZEN_ROUTES: frozenset[tuple[str, str]] = frozenset({
    ("GET", "/demo"),
    ("GET", "/demo/api-docs"),
    ("GET", "/demo/api/h5/containers"),
    ("GET", "/demo/api/jobs"),
    ("GET", "/demo/api/jobs/{job_id}"),
    ("GET", "/demo/api/jobs/{job_id}/events"),
    ("GET", "/demo/api/jobs/{job_id}/events/stream"),
    ("GET", "/demo/api/jobs/{job_id}/reports"),
    ("GET", "/demo/api/jobs/{job_id}/reports/{workflow_id}"),
    ("GET", "/demo/api/models"),
    ("GET", "/demo/api/models/{model_id}/requirements"),
    ("GET", "/demo/api/reports/{job_id}/external"),
    ("GET", "/demo/api/reports/{job_id}/internal"),
    ("GET", "/demo/control-room"),
    ("GET", "/demo/login"),
    ("GET", "/demo/model-guide"),
    ("GET", "/demo/model-playground"),
    ("GET", "/demo/model-playground/sandpit-0104t-preview"),
    ("GET", "/demo/report/{job_id}"),
    ("GET", "/demo/workspace"),
    ("GET", "/demo/workspace/{job_id}"),
    ("GET", "/health"),
    ("GET", "/model/version"),
    ("POST", "/demo/api/auth/refresh"),
    ("POST", "/demo/api/auth/token"),
    ("POST", "/demo/api/h5/containers"),
    ("POST", "/demo/api/jobs"),
    ("POST", "/demo/api/jobs/{job_id}/auth/ticket"),
    ("POST", "/demo/api/models/{model_id}/requirements/validate"),
})


def _live_routes() -> set[tuple[str, str]]:
    app = create_fastapi_app()
    routes: set[tuple[str, str]] = set()
    for route in getattr(app, "routes", []):
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if path is None or not methods:
            continue
        for method in methods:
            if method in ("HEAD", "OPTIONS"):
                continue
            routes.add((method, path))
    return routes


def test_public_route_table_is_frozen():
    """No endpoint added/removed/renamed/moved/versioned by PR0156."""
    assert _live_routes() == set(FROZEN_ROUTES)


def test_no_standard_or_mlflow_endpoint_added():
    paths = {p for _, p in _live_routes()}
    for forbidden in (
        "/model-package", "/model_package", "/packages", "/mlflow",
        "/demo/api/model-packages", "/demo/api/mlflow", "/registry",
    ):
        assert not any(forbidden in p.lower() for p in paths), (
            f"PR0156 must not expose model-package/MLflow via {forbidden!r}"
        )


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_model_requirements_response_schema_frozen():
    """GET requirements keeps the bremen.model_requirements.v1 envelope."""
    from bremen.api import model_registry as registry

    registry.reset_for_tests()
    try:
        entry = registry.RegistryModelEntry(
            model_id="bremen-current-test", display_name="Bremen", workflow_id="bremen",
            model_version="0.2.0-paper-reference", artifact_type="portable_logreg",
            feature_schema_version="v0.1",
            decision_policy_id="bremen_mri_continuation_threshold",
            decision_policy_version="0.1.0", technical_ready=True,
            _package={"portable_logreg": {"feature_schema_version": "v0.1"}},
            _checksum="",
            _container_requirements={"schema_version": "bremen.container_requirements.v1"},
        )
        registry.initialize_registry(registry.ModelRegistry(
            entries=(entry,), catalog_status="available", available_count=1,
            candidate_count=1,
        ))
        from bremen.api.model_requirements import build_model_requirements_response
        data = build_model_requirements_response("bremen-current-test")
        assert data["schema_version"] == "bremen.model_requirements.v1"
        for key in ("model_id", "workflow_id", "model_version",
                    "feature_schema_version", "requirements_available",
                    "required_fields", "optional_fields", "container_requirements"):
            assert key in data
    finally:
        registry.reset_for_tests()
