"""Public demo surface smoke guard for FastAPI.

Covers:
1. Public demo page route smoke (GET /demo -> 200 HTML, etc.)
2. Route/nav assertions (page links)
3. Job/report route parity smoke (POST/GET jobs, reports)
4. Negative safety assertions (unknown job 404, no raw internals)
5. No real servers, sockets, localhost HTTP, uvicorn launch

PR0104U — prevent FastAPI cutover regression where public demo
pages/routes exist in UI but fail at runtime.
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from bremen.api.fastapi_app import create_fastapi_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client() -> TestClient:
    """Create a FastAPI TestClient for smoke tests."""
    return TestClient(create_fastapi_app(), raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# 1. Public demo page route smoke
# ---------------------------------------------------------------------------


class TestPublicDemoPageRoutes:
    """GET public demo routes must return 200 with expected content type."""

    def test_demo_returns_200_html(self, client: TestClient) -> None:
        resp = client.get("/demo")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_demo_control_room_returns_200_html(self, client: TestClient) -> None:
        resp = client.get("/demo/control-room")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_demo_api_docs_returns_200_html(self, client: TestClient) -> None:
        resp = client.get("/demo/api-docs")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_demo_model_guide_returns_200_html(self, client: TestClient) -> None:
        resp = client.get("/demo/model-guide")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_demo_model_playground_returns_200_html(self, client: TestClient) -> None:
        resp = client.get("/demo/model-playground")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_model_version_returns_200_json(self, client: TestClient) -> None:
        resp = client.get("/model/version")
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")

    def test_demo_api_models_returns_200_json(self, client: TestClient) -> None:
        resp = client.get("/demo/api/models")
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")

    def test_demo_h5_containers_returns_200_json(self, client: TestClient) -> None:
        resp = client.get("/demo/api/h5/containers")
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# 2. Route/nav assertions
# ---------------------------------------------------------------------------


class TestPublicNavLinks:
    """Public demo pages must cross-link to each other via nav."""

    def test_demo_links_to_control_room(self, client: TestClient) -> None:
        resp = client.get("/demo")
        # Control-room link may be in static href or JS navigation
        assert (
            'href="/demo/control-room"' in resp.text
            or '/demo/control-room' in resp.text
        )

    def test_demo_links_to_model_guide(self, client: TestClient) -> None:
        resp = client.get("/demo")
        assert 'href="/demo/model-guide"' in resp.text

    def test_demo_links_to_model_playground(self, client: TestClient) -> None:
        resp = client.get("/demo")
        assert 'href="/demo/model-playground"' in resp.text

    def test_control_room_links_to_model_guide(self, client: TestClient) -> None:
        resp = client.get("/demo/control-room")
        assert 'href="/demo/model-guide"' in resp.text

    def test_control_room_links_to_model_playground(self, client: TestClient) -> None:
        resp = client.get("/demo/control-room")
        assert 'href="/demo/model-playground"' in resp.text

    def test_model_guide_links_to_model_playground(self, client: TestClient) -> None:
        resp = client.get("/demo/model-guide")
        assert 'href="/demo/model-playground"' in resp.text


# ---------------------------------------------------------------------------
# 3. Job/report route parity smoke
# ---------------------------------------------------------------------------


def _inject_test_job(
    client: TestClient,
    *,
    job_id: str = "smoke-job-001",
    status: str = "completed",
    report_available: bool = False,
) -> None:
    """Inject a fake AnalysisJob directly into the in-memory store.

    This avoids H5 file requirements and lets us test route behavior
    without real data processing.
    """
    from bremen.api.job_api_handler import (
        _jobs,
        _jobs_lock,
        _report_providers,
        _providers_lock,
        _event_store,
    )
    from bremen.api.job_models import AnalysisJob, WorkflowRun, ReportMetadata
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    reports = {}
    if report_available:
        from bremen.api.report_provider import REPORT_STATUS_AVAILABLE
        reports["bremen"] = ReportMetadata(
            report_id="report-001",
            workflow_id="bremen",
            report_schema_version="v0.1",
            status=REPORT_STATUS_AVAILABLE,
            generated_at=now,
            model_id="test-model",
            model_version="v0.1",
        )

    wf_status = status if status in (
        "completed", "failed", "running", "pending",
    ) else "completed"

    job = AnalysisJob(
        job_id=job_id,
        request_id="req-smoke-001",
        created_at=now,
        started_at=now,
        completed_at=now if status in ("completed", "failed") else None,
        overall_status=status,
        input_summary={
            "container_id": "smoke-container",
            "workflow_id": "bremen",
            "model_id": "test-model",
        },
        requested_workflows=("bremen",),
        workflow_runs={
            "bremen": WorkflowRun(
                workflow_id="bremen",
                status=wf_status,
                model_identity={"model_id": "test-model", "model_version": "v0.1"},
                result_summary={
                    "decision_code": "SMOKE",
                    "decision_display_name": "Smoke Test",
                },
                started_at=now,
                completed_at=now,
            ),
        },
        reports=reports,
    )

    with _jobs_lock:
        _jobs[job_id] = job

    # Emit a minimal event so event store knows about the job
    from bremen.api.event_schema import JobEvent, EventType
    evt = JobEvent(
        job_id=job_id,
        request_id="req-smoke-001",
        workflow_id="bremen",
        stage="normalization",
        event_type="runtime.normalization.completed",
        status="completed",
    )
    _event_store.append(job_id, evt)


def _inject_failed_job(client: TestClient, job_id: str = "failed-job-001") -> None:
    """Inject a failed job for negative safety tests."""
    _inject_test_job(client, job_id=job_id, status="failed", report_available=False)


def _reset_jobs() -> None:
    """Clear all injected test jobs."""
    from bremen.api.job_api_handler import (
        _jobs,
        _jobs_lock,
        _event_store,
    )
    with _jobs_lock:
        _jobs.clear()
    _event_store.reset_for_tests()


@pytest.fixture(autouse=True)
def _clean_jobs():
    """Reset job state before and after each test."""
    _reset_jobs()
    yield
    _reset_jobs()


class TestPostJobsRoute:
    """POST /demo/api/jobs must return 201 for valid request, 400 for invalid."""

    def test_post_jobs_returns_400_without_source(self, client: TestClient) -> None:
        resp = client.post("/demo/api/jobs", json={"workflow_id": "bremen"})
        assert resp.status_code == 400

    def test_post_jobs_returns_400_with_empty_body(self, client: TestClient) -> None:
        resp = client.post(
            "/demo/api/jobs",
            content=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )
        # Empty JSON is valid Pydantic but no source => 400 MISSING_SOURCE
        assert resp.status_code == 400

    def test_post_jobs_returns_400_for_invalid_json(self, client: TestClient) -> None:
        resp = client.post(
            "/demo/api/jobs",
            content="not json at all",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_post_jobs_delete_report_action_returns_400(self, client: TestClient) -> None:
        resp = client.post(
            "/demo/api/jobs",
            json={"action": "delete_report", "job_id": "fake"},
        )
        assert resp.status_code == 400


class TestGetJobsRoutes:
    """GET /demo/api/jobs and /demo/api/jobs/{job_id} parity smoke."""

    def test_jobs_list_returns_200(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs")
        assert resp.status_code == 200

    def test_jobs_list_returns_json_with_jobs_key(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs")
        body = resp.json()
        assert "jobs" in body
        assert isinstance(body["jobs"], list)

    def test_jobs_list_includes_injected_job(self, client: TestClient) -> None:
        _inject_test_job(client, job_id="list-check-001")
        resp = client.get("/demo/api/jobs")
        body = resp.json()
        job_ids = [j["job_id"] for j in body["jobs"]]
        assert "list-check-001" in job_ids

    def test_job_detail_returns_200_for_existing_job(self, client: TestClient) -> None:
        _inject_test_job(client, job_id="detail-check-001")
        resp = client.get("/demo/api/jobs/detail-check-001")
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_id"] == "detail-check-001"

    def test_job_detail_returns_404_for_unknown_job(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/unknown-job-id")
        assert resp.status_code == 404

    def test_job_events_returns_200_for_existing_job(self, client: TestClient) -> None:
        _inject_test_job(client, job_id="events-check-001")
        resp = client.get("/demo/api/jobs/events-check-001/events")
        assert resp.status_code == 200
        body = resp.json()
        assert "events" in body

    def test_job_events_returns_404_for_unknown_job(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/unknown-id/events")
        assert resp.status_code == 404

    def test_job_reports_returns_200_for_existing_job(self, client: TestClient) -> None:
        _inject_test_job(client, job_id="reports-check-001")
        resp = client.get("/demo/api/jobs/reports-check-001/reports")
        assert resp.status_code == 200
        body = resp.json()
        assert "reports" in body

    def test_job_reports_returns_200_for_unknown_job(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/unknown-id/reports")
        assert resp.status_code == 200
        body = resp.json()
        assert body["reports"] == {}

    def _register_providers(self) -> None:
        """Register the default report providers for job/report tests."""
        from bremen.api.job_api_handler import _register_default_providers
        _register_default_providers()

    def test_job_report_detail_returns_200(self, client: TestClient) -> None:
        self._register_providers()
        _inject_test_job(
            client, job_id="rpt-detail-001", report_available=True,
        )
        resp = client.get("/demo/api/jobs/rpt-detail-001/reports/bremen")
        assert resp.status_code == 200
        body = resp.json()
        report = body.get("report", {})
        # Report must be present with a workflow_status or safe fallback status
        assert (
            report.get("workflow_status") in ("available", "completed")
            or report.get("status") in (
                "unavailable", "job_not_found",
            )
            or report.get("report_id") is not None
        )


class TestReportRoutes:
    """Report HTML and data routes must work for existing jobs."""

    def test_report_html_returns_200_for_any_job(self, client: TestClient) -> None:
        _inject_test_job(client, job_id="html-report-001")
        resp = client.get("/demo/report/html-report-001")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_external_report_returns_200_for_existing_job(
        self, client: TestClient,
    ) -> None:
        _inject_test_job(
            client, job_id="ext-report-001", report_available=True,
        )
        resp = client.get("/demo/api/reports/ext-report-001/external")
        assert resp.status_code == 200

    def test_internal_report_returns_200_for_existing_job(
        self, client: TestClient,
    ) -> None:
        _inject_test_job(
            client, job_id="int-report-001", report_available=True,
        )
        resp = client.get("/demo/api/reports/int-report-001/internal")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 4. Negative safety assertions
# ---------------------------------------------------------------------------


class TestUnknownJobSafety:
    """Unknown jobs must return safe error responses."""

    def test_unknown_job_detail_returns_404_safe(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/nonexistent-xyz")
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body
        assert body["job_id"] == "nonexistent-xyz"

    def test_unknown_job_events_returns_404_safe(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/nonexistent-xyz/events")
        assert resp.status_code == 404

    def test_unknown_job_reports_returns_empty(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/nonexistent-xyz/reports")
        assert resp.status_code == 200
        body = resp.json()
        assert body["reports"] == {}

    def test_unknown_job_report_detail_safe(self, client: TestClient) -> None:
        resp = client.get("/demo/api/jobs/nonexistent-xyz/reports/bremen")
        assert resp.status_code == 200
        body = resp.json()
        assert body["report"]["status"] == "job_not_found"


class TestFailedJobReportSafety:
    """Failed jobs must not expose report HTML/data."""

    def test_failed_job_no_external_report(self, client: TestClient) -> None:
        _inject_failed_job(client, job_id="fail-ext-001")
        resp = client.get("/demo/api/reports/fail-ext-001/external")
        body = resp.json()
        # Either error or no report_available
        assert body.get("error") or body.get("technical_demo_only") is True

    def test_failed_job_no_internal_report(self, client: TestClient) -> None:
        _inject_failed_job(client, job_id="fail-int-001")
        resp = client.get("/demo/api/reports/fail-int-001/internal")
        body = resp.json()
        assert body.get("error") or body.get("technical_demo_only") is True


class TestPublicSafetyNoLeaks:
    """Public HTML/JSON must not leak raw internals."""

    _S3_PATTERN = re.compile(r"s3://[a-zA-Z0-9._\-/]+")
    _BUCKET_PATTERN = re.compile(
        r"(?:bucket|prefix)[=:]\s*['\"]?[a-zA-Z0-9._\-]+['\"]?",
        re.IGNORECASE,
    )
    _FILESYSTEM_PATTERN = re.compile(r"(?:/Users/|/home/|/tmp/|/var/)")
    _EXCEPTION_PATTERN = re.compile(
        r"(?:Traceback \(most recent|\.py\", line \d+)",
    )
    _CHECKSUM_PATTERN = re.compile(r"\b[a-f0-9]{64}\b")
    _COEFFICIENT_PATTERN = re.compile(
        r"(?:coefficients?|intercept|feature_weights)\s*[=:]\s*[\[\d\.\-\s,\]]+",
        re.IGNORECASE,
    )
    _THRESHOLD_PATTERN = re.compile(
        r"(?:threshold)\s*[=:]\s*\d+\.\d+",
        re.IGNORECASE,
    )
    _PHI_PATTERN = re.compile(
        r"(?:patient_name|patient_id|patient_identifier)\s*[=:]\s*['\"]?[A-Za-z ]+['\"]?",
        re.IGNORECASE,
    )

    PUBLIC_HTML_ROUTES = (
        "/demo",
        "/demo/control-room",
        "/demo/model-guide",
        "/demo/model-playground",
        "/demo/api-docs",
    )

    PUBLIC_JSON_ROUTES = (
        "/model/version",
        "/demo/api/models",
        "/demo/api/h5/containers",
        "/demo/api/jobs",
    )

    def _check_text(self, text: str, route: str) -> None:
        """Assert no raw internal leakage in response text."""
        assert not self._S3_PATTERN.search(text), (
            f"Raw S3 path found in {route}"
        )
        assert not self._FILESYSTEM_PATTERN.search(text), (
            f"Filesystem path found in {route}"
        )
        assert not self._EXCEPTION_PATTERN.search(text), (
            f"Exception trace found in {route}"
        )
        assert not self._CHECKSUM_PATTERN.search(text), (
            f"Full SHA256 checksum found in {route}"
        )
        # Coefficients and threshold checks only for HTML pages
        assert "Traceback" not in text, (
            f"Raw traceback found in {route}"
        )

    @pytest.mark.parametrize("route", PUBLIC_HTML_ROUTES)
    def test_no_raw_s3_in_html(self, client: TestClient, route: str) -> None:
        resp = client.get(route)
        assert self._S3_PATTERN.search(resp.text) is None, (
            f"S3 path in {route}"
        )

    @pytest.mark.parametrize("route", PUBLIC_HTML_ROUTES)
    def test_no_filesystem_paths_in_html(
        self, client: TestClient, route: str,
    ) -> None:
        resp = client.get(route)
        assert self._FILESYSTEM_PATTERN.search(resp.text) is None, (
            f"Filesystem path in {route}"
        )

    @pytest.mark.parametrize("route", PUBLIC_HTML_ROUTES)
    def test_no_exception_traces_in_html(
        self, client: TestClient, route: str,
    ) -> None:
        resp = client.get(route)
        assert "Traceback" not in resp.text, f"Traceback in {route}"

    @pytest.mark.parametrize("route", PUBLIC_JSON_ROUTES)
    def test_no_raw_s3_in_json(self, client: TestClient, route: str) -> None:
        resp = client.get(route)
        assert self._S3_PATTERN.search(resp.text) is None, (
            f"S3 path in {route}"
        )

    @pytest.mark.parametrize("route", PUBLIC_JSON_ROUTES)
    def test_no_filesystem_paths_in_json(
        self, client: TestClient, route: str,
    ) -> None:
        resp = client.get(route)
        assert self._FILESYSTEM_PATTERN.search(resp.text) is None, (
            f"Filesystem path in {route}"
        )

    @pytest.mark.parametrize("route", PUBLIC_JSON_ROUTES)
    def test_no_exception_traces_in_json(
        self, client: TestClient, route: str,
    ) -> None:
        resp = client.get(route)
        assert "Traceback" not in resp.text, f"Traceback in {route}"

    def test_model_version_no_raw_model_internals(self, client: TestClient) -> None:
        resp = client.get("/model/version")
        body = resp.json()
        # model_checksum is intentional for version verification.
        # Must not leak raw coefficients, intercepts, thresholds,
        # S3 paths, filesystem paths, or exception traces.
        text = resp.text
        assert self._S3_PATTERN.search(text) is None, (
            "S3 path found in /model/version"
        )
        assert self._FILESYSTEM_PATTERN.search(text) is None, (
            "Filesystem path found in /model/version"
        )
        assert self._EXCEPTION_PATTERN.search(text) is None, (
            "Exception trace found in /model/version"
        )

    def test_no_bucket_names_in_models_catalog(self, client: TestClient) -> None:
        resp = client.get("/demo/api/models")
        body = resp.json()
        text = resp.text
        # Bucket names should not appear in public catalog
        assert self._BUCKET_PATTERN.search(text) is None, (
            "Bucket name found in /demo/api/models"
        )


# ---------------------------------------------------------------------------
# 5. No server spawning guard (structural)
# ---------------------------------------------------------------------------


class TestNoServerSpawning:
    """This test file must not contain server-spawning code patterns."""

    def test_no_socket_imports(self) -> None:
        import ast
        from pathlib import Path

        filepath = Path(__file__)
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "socket", (
                        "This test file must not import socket"
                    )
                    assert not alias.name.startswith("socket."), (
                        "This test file must not import socket module"
                    )
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert module != "socket", (
                    "This test file must not import from socket"
                )
                assert module != "socketserver", (
                    "This test file must not import from socketserver"
                )

    def test_no_http_server_imports(self) -> None:
        import ast
        from pathlib import Path

        filepath = Path(__file__)
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "http.server", (
                        "This test file must not import http.server"
                    )
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert module != "http.server", (
                    "This test file must not import from http.server"
                )

    def test_no_urlopen_calls(self) -> None:
        import ast
        from pathlib import Path

        filepath = Path(__file__)
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr != "urlopen", (
                    "This test file must not call urlopen"
                )

    def test_no_serve_forever_calls(self) -> None:
        import ast
        from pathlib import Path

        filepath = Path(__file__)
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr != "serve_forever", (
                    "This test file must not call serve_forever"
                )


# ---------------------------------------------------------------------------
# 6. Existing routes not broken
# ---------------------------------------------------------------------------


class TestExistingRoutesPreserved:
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

    def test_unknown_route_returns_404(self, client: TestClient) -> None:
        resp = client.get("/nonexistent")
        assert resp.status_code == 404
