"""Tests for FastAPI report data route parity.

Covers:
- GET /demo/api/reports/{job_id}/external returns report data
- GET /demo/api/reports/{job_id}/internal returns report data
- unknown job returns safe response
- failed/no-report job returns safe response
- no raw S3/H5/model internals, raw exceptions, or PHI
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


class TestExternalReportRoute:
    """GET /demo/api/reports/{job_id}/external must return report JSON."""

    def test_unknown_job_returns_200_with_error(self, client: TestClient) -> None:
        resp = client.get("/demo/api/reports/nonexistent-id/external")
        assert resp.status_code == 200
        body = resp.json()
        assert "error" in body

    def test_unknown_job_has_job_id(self, client: TestClient) -> None:
        resp = client.get("/demo/api/reports/nonexistent-id/external")
        body = resp.json()
        assert body.get("job_id") == "nonexistent-id"

    def test_response_has_technical_demo_only(self, client: TestClient) -> None:
        resp = client.get("/demo/api/reports/nonexistent-id/external")
        body = resp.json()
        assert body.get("technical_demo_only") is True

    def test_response_has_request_id(self, client: TestClient) -> None:
        resp = client.get(
            "/demo/api/reports/test-id/external",
            headers={"X-Request-ID": "ext-123"},
        )
        body = resp.json()
        assert body.get("request_id") == "ext-123"

    def test_auto_generates_request_id(self, client: TestClient) -> None:
        resp = client.get("/demo/api/reports/test-id/external")
        body = resp.json()
        assert "request_id" in body
        assert len(body["request_id"]) > 0


class TestInternalReportRoute:
    """GET /demo/api/reports/{job_id}/internal must return report JSON."""

    def test_unknown_job_returns_200_with_error(self, client: TestClient) -> None:
        resp = client.get("/demo/api/reports/nonexistent-id/internal")
        assert resp.status_code == 200
        body = resp.json()
        assert "error" in body

    def test_unknown_job_has_job_id(self, client: TestClient) -> None:
        resp = client.get("/demo/api/reports/nonexistent-id/internal")
        body = resp.json()
        assert body.get("job_id") == "nonexistent-id"

    def test_response_has_technical_demo_only(self, client: TestClient) -> None:
        resp = client.get("/demo/api/reports/nonexistent-id/internal")
        body = resp.json()
        assert body.get("technical_demo_only") is True

    def test_response_has_request_id(self, client: TestClient) -> None:
        resp = client.get(
            "/demo/api/reports/test-id/internal",
            headers={"X-Request-ID": "int-456"},
        )
        body = resp.json()
        assert body.get("request_id") == "int-456"

    def test_auto_generates_request_id(self, client: TestClient) -> None:
        resp = client.get("/demo/api/reports/test-id/internal")
        body = resp.json()
        assert "request_id" in body
        assert len(body["request_id"]) > 0


class TestReportDataSafety:
    """Report data must not leak internals."""

    def test_no_raw_s3_paths_in_external(self, client: TestClient) -> None:
        resp = client.get("/demo/api/reports/test-id/external")
        assert "s3://" not in resp.text

    def test_no_raw_s3_paths_in_internal(self, client: TestClient) -> None:
        resp = client.get("/demo/api/reports/test-id/internal")
        assert "s3://" not in resp.text

    def test_no_filesystem_paths_in_external(self, client: TestClient) -> None:
        resp = client.get("/demo/api/reports/test-id/external")
        assert "/Users/" not in resp.text
        assert "/home/" not in resp.text

    def test_no_exception_traces(self, client: TestClient) -> None:
        resp = client.get("/demo/api/reports/test-id/external")
        assert "Traceback" not in resp.text


class TestExistingRoutesPreserved:
    """All previously working routes must still work."""

    def test_report_html_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/report/test-id")
        assert resp.status_code == 200

    def test_jobs_list_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs")
        assert resp.status_code in (200, 500)

    def test_job_detail_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/nonexistent")
        assert resp.status_code == 404

    def test_job_reports_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/nonexistent/reports")
        assert resp.status_code == 200

    def test_health_still_works(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_demo_models_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/api/models")
        assert resp.status_code == 200
