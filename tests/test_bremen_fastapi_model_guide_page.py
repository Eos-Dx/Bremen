"""FastAPI tests for the sanitized Bremen model guide page.

Uses TestClient only.  No real servers, sockets, localhost HTTP, or uvicorn
runtime paths are exercised.
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


class TestModelGuideRoute:
    """GET /demo/model-guide returns safe HTML."""

    def test_model_guide_returns_200_html(self, client: TestClient) -> None:
        resp = client.get("/demo/model-guide")

        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert "How the demo model works" in resp.text
        assert "Technical demo only" in resp.text

    def test_model_guide_includes_request_id_header(self, client: TestClient) -> None:
        resp = client.get("/demo/model-guide", headers={"X-Request-ID": "guide-123"})

        assert resp.headers.get("X-Request-ID") == "guide-123"


class TestModelGuideNavigation:
    """Existing demo pages link to the model guide."""

    def test_demo_has_model_guide_link(self, client: TestClient) -> None:
        resp = client.get("/demo")

        assert resp.status_code == 200
        assert 'href="/demo/model-guide"' in resp.text
        assert "Model guide" in resp.text

    def test_control_room_has_model_guide_link(self, client: TestClient) -> None:
        resp = client.get("/demo/control-room")

        assert resp.status_code == 200
        assert 'href="/demo/model-guide"' in resp.text
        assert "Model guide" in resp.text


class TestModelGuideSanitization:
    """The public guide must not expose private model internals."""

    def test_no_raw_artifact_sha_or_checksum_exposed(
        self, client: TestClient
    ) -> None:
        text = client.get("/demo/model-guide").text
        lower = text.lower()

        assert "sha256" not in lower
        assert "checksum" not in lower
        assert re.search(r"\b[a-f0-9]{64}\b", lower) is None

    def test_no_model_coefficients_exposed(self, client: TestClient) -> None:
        lower = client.get("/demo/model-guide").text.lower()

        assert "coef" not in lower
        assert "intercept" not in lower
        assert "feature contract" not in lower

    def test_no_raw_model_internals_exposed(self, client: TestClient) -> None:
        lower = client.get("/demo/model-guide").text.lower()
        prohibited = (
            "model.joblib",
            "joblib",
            "pickle",
            "portable_logreg",
            "estimator",
            "_package",
            "model artifact keys",
            "artifact version",
        )

        for marker in prohibited:
            assert marker not in lower

    def test_no_private_paths_or_phi_exposed(self, client: TestClient) -> None:
        text = client.get("/demo/model-guide").text
        lower = text.lower()

        assert "s3://" not in lower
        assert "/users/" not in lower
        assert "/home/" not in lower
        assert re.search(r"\bpatient[_ -]?(name|id|dob|birth)\b", lower) is None
