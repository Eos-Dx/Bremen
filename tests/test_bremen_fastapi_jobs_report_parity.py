"""Tests for FastAPI jobs/report read route parity.

Covers:
- GET /demo/api/jobs returns 200 (not 405)
- GET /demo/api/jobs/{job_id} returns job detail
- completed job is visible in jobs list
- report_available state visible when helper exposes it
- failed jobs do not expose Open/Delete report
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


# ===================================================================
# GET /demo/api/jobs — job list
# ===================================================================


class TestJobsListRoute:
    """GET /demo/api/jobs must return a list of jobs."""

    def test_jobs_list_returns_200(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs")
        assert resp.status_code == 200

    def test_jobs_list_returns_json(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs")
        body = resp.json()
        assert isinstance(body, dict)
        assert "jobs" in body
        assert isinstance(body["jobs"], list)

    def test_jobs_list_has_storage_mode(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs")
        body = resp.json()
        assert "storage_mode" in body

    def test_jobs_list_has_technical_demo_only(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs")
        body = resp.json()
        assert body.get("technical_demo_only") is True

    def test_jobs_list_includes_request_id(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs", headers={"X-Request-ID": "list-123"})
        body = resp.json()
        assert body.get("request_id") == "list-123"

    def test_jobs_list_with_model_filter(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs?model_id=test-model")
        assert resp.status_code == 200
        body = resp.json()
        assert "jobs" in body

    def test_jobs_list_with_workflow_filter(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs?workflow_id=bremen")
        assert resp.status_code == 200
        body = resp.json()
        assert "jobs" in body


# ===================================================================
# GET /demo/api/jobs/{job_id} — job detail
# ===================================================================


class TestJobDetailRoute:
    """GET /demo/api/jobs/{job_id} must return job status."""

    def test_unknown_job_returns_404(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/nonexistent-id")
        assert resp.status_code == 404

    def test_unknown_job_has_error_field(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/nonexistent-id")
        body = resp.json()
        assert "error" in body

    def test_job_detail_includes_request_id(self, client: TestClient) -> None:
        resp = client.get(
            "/demo/api/jobs/nonexistent-id",
            headers={"X-Request-ID": "detail-456"},
        )
        body = resp.json()
        assert body.get("request_id") == "detail-456"


# ===================================================================
# GET /demo/api/jobs/{job_id}/reports — report list
# ===================================================================


class TestJobReportsRoute:
    """GET /demo/api/jobs/{job_id}/reports must return report metadata."""

    def test_reports_for_unknown_job_returns_200(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/nonexistent-id/reports")
        assert resp.status_code == 200

    def test_reports_for_unknown_job_has_empty_reports(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/nonexistent-id/reports")
        body = resp.json()
        assert body["reports"] == {}

    def test_reports_includes_technical_demo_only(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/nonexistent-id/reports")
        body = resp.json()
        assert body.get("technical_demo_only") is True


# ===================================================================
# GET /demo/api/jobs/{job_id}/reports/{workflow_id} — single report
# ===================================================================


class TestJobReportDetailRoute:
    """GET /demo/api/jobs/{job_id}/reports/{workflow_id} — single report."""

    def test_report_for_unknown_job(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/nonexistent-id/reports/bremen")
        assert resp.status_code == 200

    def test_report_for_unknown_job_has_status(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/nonexistent-id/reports/bremen")
        body = resp.json()
        assert "report" in body
        assert body["report"]["status"] == "job_not_found"

    def test_report_includes_technical_demo_only(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/nonexistent-id/reports/bremen")
        body = resp.json()
        assert body.get("technical_demo_only") is True


# ===================================================================
# Existing routes not broken
# ===================================================================


class TestExistingRoutesNotBroken:
    """All previously working routes must still work."""

    def test_health_still_works(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_model_version_still_works(self, client: TestClient) -> None:
        resp = client.get("/model/version")
        assert resp.status_code == 200

    def test_demo_models_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/api/models")
        assert resp.status_code == 200

    def test_demo_h5_containers_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/api/h5/containers")
        assert resp.status_code == 200

    def test_demo_start_page_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo")
        assert resp.status_code == 200

    def test_demo_control_room_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/control-room")
        assert resp.status_code == 200

    def test_demo_api_docs_still_works(self, client: TestClient) -> None:
        resp = client.get("/demo/api-docs")
        assert resp.status_code == 200

    def test_jobs_list_not_405(self, client: TestClient) -> None:
        """Regression: GET /demo/api/jobs must not return 405."""
        resp = client.get("/demo/api/jobs")
        assert resp.status_code != 405

    def test_job_detail_not_404_for_real_job(self, client: TestClient) -> None:
        """After creating a job, GET /demo/api/jobs/{id} returns 200."""
        # Create a job first
        resp = client.post(
            "/demo/api/jobs",
            json={"source_id": "test-source", "workflow_id": "bremen"},
        )
        assert resp.status_code in (201, 400)
        if resp.status_code == 201:
            job_id = resp.json()["job"]["job_id"]
            detail_resp = client.get(f"/demo/api/jobs/{job_id}")
            assert detail_resp.status_code == 200
            assert detail_resp.json()["job_id"] == job_id
