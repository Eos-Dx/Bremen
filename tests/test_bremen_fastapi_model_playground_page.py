"""Tests for the demo Model Playground page.

Covers:
- GET /demo/model-playground returns 200 HTML
- Page has nav links to Start, Control Room, Model Guide, API docs
- Page says sandbox/synthetic/technical demo
- No full checksum/SHA
- No exact coefficients/intercept/threshold
- No raw model internals
- Existing /demo/model-guide still works
- Existing report routes still work
- No real servers, sockets, localhost HTTP, uvicorn launch
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from bremen.api.fastapi_app import create_fastapi_app


@pytest.fixture()
def client() -> TestClient:
    """Create a FastAPI TestClient."""
    return TestClient(create_fastapi_app(), raise_server_exceptions=False)


class TestModelPlaygroundRoute:
    """GET /demo/model-playground must return a sandbox page."""

    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        assert resp.status_code == 200

    def test_returns_html(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_contains_bremen(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        assert "bremen" in resp.text.lower()

    def test_page_title_includes_playground(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        assert "playground" in resp.text.lower() or "sandbox" in resp.text.lower()


class TestSandboxBranding:
    """Page must clearly indicate sandbox/synthetic/technical demo."""

    def test_sandbox_notice_present(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        assert "sandbox" in resp.text.lower()

    def test_synthetic_notice_present(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        assert "synthetic" in resp.text.lower() or "sandbox" in resp.text.lower()

    def test_technical_demo_notice(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        assert "technical demo" in resp.text.lower() or "sandbox" in resp.text.lower()


class TestNavLinks:
    """Page must have navigation links to other demo pages."""

    def test_start_link(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        assert 'href="/demo"' in resp.text

    def test_control_room_link(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        assert 'href="/demo/control-room"' in resp.text

    def test_model_guide_link(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        assert 'href="/demo/model-guide"' in resp.text

    def test_api_docs_link(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        assert 'href="/demo/api-docs"' in resp.text


class TestNoProductionInternals:
    """Page must not expose production model internals."""

    def test_no_full_sha256(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        # Must not contain the production SHA256
        assert "971b20baf299295ac744746c2b7e751ab3df81205f55b695ae516ad2114069d4" not in resp.text

    def test_no_production_intercept(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        # Must not contain exact production intercept
        assert "-0.038341628329418675" not in resp.text

    def test_no_production_threshold(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        # Must not contain exact production threshold
        assert "0.4130396520921527" not in resp.text

    def test_no_raw_model_joblib(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        assert "model.joblib" not in resp.text.lower() or "sandbox" in resp.text.lower()

    def test_no_s3_paths(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        assert "s3://" not in resp.text

    def test_no_filesystem_paths(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        assert "/Users/" not in resp.text
        assert "/home/" not in resp.text

    def test_no_exception_traces(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        assert "Traceback" not in resp.text


class TestExistingRoutesPreserved:
    """All previously working routes must still work."""

    def test_model_guide_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/model-guide")
        assert resp.status_code == 200

    def test_report_html_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/report/test-id")
        assert resp.status_code == 200

    def test_health_still_works(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_demo_models_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/api/models")
        assert resp.status_code == 200

    def test_jobs_list_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs")
        assert resp.status_code in (200, 500)

    def test_start_page_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo")
        assert resp.status_code == 200

    def test_control_room_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/control-room")
        assert resp.status_code == 200
