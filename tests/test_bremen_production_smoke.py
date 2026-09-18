"""Production smoke checks use in-process FastAPI calls and synthetic inputs.

Transport lifecycle behavior is covered by the dedicated ASGI suites; this
module only keeps a small smoke contract for the current application boundary.
"""

from __future__ import annotations

from bremen.api.http.app import create_app


def test_production_app_smoke_uses_current_fastapi_composition_root():
    routes = {route.path for route in create_app().routes}
    assert "/health" in routes
    assert "/model/version" in routes
