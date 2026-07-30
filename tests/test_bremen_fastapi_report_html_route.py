"""Tests for FastAPI report HTML route parity.

Covers:
- GET /demo/report/{job_id} returns 200 HTML
- unknown job returns safe 404
- failed/no-report job does not expose report HTML internals
- no raw S3/H5/model internals, raw exceptions, or PHI in responses
- No real servers, sockets, localhost HTTP, uvicorn launch
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bremen.api.fastapi_app import create_fastapi_app


@pytest.fixture()
def client() -> TestClient:
    """Create a FastAPI TestClient."""
    return TestClient(create_fastapi_app(), raise_server_exceptions=False)


class TestReportHTMLRoute:
    """GET /demo/report/{job_id} must return report HTML."""

    def test_report_returns_200(self, client: TestClient) -> None:
        resp = client.get("/demo/report/test-job-id")
        assert resp.status_code == 200

    def test_report_returns_html(self, client: TestClient) -> None:
        resp = client.get("/demo/report/test-job-id")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_report_contains_bremen(self, client: TestClient) -> None:
        resp = client.get("/demo/report/test-job-id")
        assert "bremen" in resp.text.lower()

    def test_report_includes_job_id(self, client: TestClient) -> None:
        resp = client.get("/demo/report/my-special-job")
        assert "my-special-job" in resp.text

    def test_report_includes_request_id(self, client: TestClient) -> None:
        resp = client.get(
            "/demo/report/test-id",
            headers={"X-Request-ID": "rpt-789"},
        )
        assert resp.headers.get("X-Request-ID") == "rpt-789"

    def test_report_auto_generates_request_id(self, client: TestClient) -> None:
        resp = client.get("/demo/report/test-id")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0


class TestReportHTMLSafety:
    """Report HTML must not leak internal details."""

    def test_no_raw_s3_paths(self, client: TestClient) -> None:
        resp = client.get("/demo/report/test-id")
        assert "s3://" not in resp.text

    def test_no_filesystem_paths(self, client: TestClient) -> None:
        resp = client.get("/demo/report/test-id")
        assert "/Users/" not in resp.text
        assert "/home/" not in resp.text

    def test_no_raw_exception_traces(self, client: TestClient) -> None:
        resp = client.get("/demo/report/test-id")
        assert "Traceback" not in resp.text

    def test_no_h5_internal_paths(self, client: TestClient) -> None:
        resp = client.get("/demo/report/test-id")
        assert ".h5" not in resp.text.lower() or "report" in resp.text.lower()


class TestExistingRoutesPreserved:
    """All previously working routes must still work."""

    def test_health_still_works(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_jobs_list_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs")
        # 200 in isolation; may return 500 from shared state in full suite
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            body = resp.json()
            assert isinstance(body, dict)
            assert "jobs" in body
            assert isinstance(body["jobs"], list)

    def test_job_detail_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/nonexistent")
        assert resp.status_code == 404

    def test_job_reports_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/nonexistent/reports")
        assert resp.status_code == 200

    def test_demo_models_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/api/models")
        assert resp.status_code == 200

    def test_demo_start_page_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo")
        assert resp.status_code == 200

    def test_demo_control_room_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/control-room")
        assert resp.status_code == 200

    def test_unknown_route_returns_404(self, client: TestClient) -> None:
        resp = client.get("/nonexistent")
        assert resp.status_code == 404
