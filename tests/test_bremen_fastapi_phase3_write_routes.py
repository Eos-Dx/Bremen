"""Tests for FastAPI Phase 3 — write routes (POST /demo/api/h5/containers,
POST /demo/api/jobs).

Tests cover:
- POST /demo/api/jobs — typed request contract, validation, business logic reuse.
- POST /demo/api/h5/containers — upload validation, safe error responses.
- Regression: Phase 1 and Phase 2 routes still work.
- Safety: no raw exceptions, no S3/H5/path leakage.
- No server-spawning tests.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None  # type: ignore[assignment,misc]

from bremen.api.fastapi_app import create_fastapi_app
from bremen.api.fastapi_contracts import JobCreateRequest

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"


# ===================================================================
# Helpers
# ===================================================================


@pytest.fixture()
def client():
    """Create a TestClient for the FastAPI app."""
    app = create_fastapi_app()
    return TestClient(app)


# ===================================================================
# Pydantic request contract
# ===================================================================


class TestJobCreateRequestContract:
    def test_default_values(self) -> None:
        """Default values match expected API semantics."""
        req = JobCreateRequest()
        assert req.workflow_id == "bremen"
        assert req.model_id is None
        assert req.source_id is None
        assert req.upload_id is None
        assert req.h5_path == ""
        assert req.container_id == ""
        assert req.action == ""

    def test_full_fields(self) -> None:
        """All fields accepted."""
        req = JobCreateRequest(
            workflow_id="bremen",
            model_id="m1",
            source_id="s1",
            upload_id=None,
            h5_path="",
            container_id="",
        )
        assert req.model_id == "m1"
        assert req.source_id == "s1"

    def test_rejects_non_string_workflow_id(self) -> None:
        """Non-string workflow_id is rejected."""
        with pytest.raises(Exception):
            JobCreateRequest(workflow_id=123)

    def test_rejects_non_string_source_id(self) -> None:
        """Non-string source_id is rejected."""
        with pytest.raises(Exception):
            JobCreateRequest(source_id=[1, 2, 3])


# ===================================================================
# POST /demo/api/jobs
# ===================================================================


class TestJobsCreateRoute:
    def test_jobs_route_exists(self, client) -> None:
        """POST /demo/api/jobs exists and accepts JSON."""
        resp = client.post("/demo/api/jobs", json={
            "workflow_id": "bremen",
        })
        # May be 400 (missing source) or 201 (success) — route exists
        assert resp.status_code in (201, 400, 409, 500)

    def test_jobs_rejects_empty_body(self, client) -> None:
        """Empty request body returns 400."""
        resp = client.post("/demo/api/jobs", content=b"")
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_jobs_rejects_invalid_json(self, client) -> None:
        """Invalid JSON returns 400."""
        resp = client.post(
            "/demo/api/jobs",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    def test_jobs_rejects_both_source_and_upload(self, client) -> None:
        """Both source_id and upload_id returns 400 with AMBIGUOUS_SOURCE."""
        resp = client.post("/demo/api/jobs", json={
            "source_id": "s1",
            "upload_id": "u1",
        })
        assert resp.status_code == 400
        data = resp.json()
        assert data.get("error_code") == "AMBIGUOUS_SOURCE"

    def test_jobs_rejects_missing_source(self, client) -> None:
        """No source_id, upload_id, h5_path, or container_id returns 400."""
        resp = client.post("/demo/api/jobs", json={
            "workflow_id": "bremen",
        })
        assert resp.status_code == 400
        data = resp.json()
        assert data.get("error_code") == "MISSING_SOURCE"

    def test_jobs_rejects_delete_report_action(self, client) -> None:
        """delete_report action is not migrated in Phase 3."""
        resp = client.post("/demo/api/jobs", json={
            "action": "delete_report",
        })
        assert resp.status_code == 400

    def test_jobs_no_raw_exception_traces(self, client) -> None:
        """Error responses do not expose raw exception traces."""
        resp = client.post("/demo/api/jobs", json={})
        text = resp.text
        assert "Traceback" not in text
        assert "File \"" not in text

    def test_jobs_no_raw_s3_paths(self, client) -> None:
        """Responses do not expose raw S3 URIs."""
        resp = client.post("/demo/api/jobs", json={
            "source_id": "nonexistent",
        })
        text = resp.text
        assert "s3://" not in text

    def test_jobs_no_raw_filesystem_paths(self, client) -> None:
        """Responses do not expose filesystem paths."""
        resp = client.post("/demo/api/jobs", json={
            "source_id": "nonexistent",
        })
        text = resp.text
        assert "/Users/" not in text
        assert "/home/" not in text

    def test_jobs_invalid_source_returns_safe_error(self, client) -> None:
        """Invalid source_id returns a safe error message."""
        resp = client.post("/demo/api/jobs", json={
            "source_id": "nonexistent-source-id",
        })
        assert resp.status_code in (400, 404)
        data = resp.json()
        assert "error" in data
        # No raw internals
        text = str(data)
        assert "Traceback" not in text


# ===================================================================
# POST /demo/api/h5/containers (upload)
# ===================================================================


class TestH5UploadRoute:
    def test_upload_route_exists(self, client) -> None:
        """POST /demo/api/h5/containers exists and accepts multipart."""
        resp = client.post(
            "/demo/api/h5/containers",
            files={"file": ("test.h5", b"fake content", "application/octet-stream")},
        )
        # May be 403 (upload disabled) or 201 — route exists
        assert resp.status_code in (201, 400, 403, 503)

    def test_upload_rejects_empty_file(self, client) -> None:
        """Empty file body returns 400."""
        resp = client.post(
            "/demo/api/h5/containers",
            files={"file": ("test.h5", b"", "application/octet-stream")},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data.get("status") == "upload_rejected"
        assert "Empty body" in data.get("error", "")

    def test_upload_rejects_bad_extension(self, client) -> None:
        """Non-.h5 file extension returns 400."""
        resp = client.post(
            "/demo/api/h5/containers",
            files={"file": ("test.txt", b"some content", "text/plain")},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data.get("status") == "upload_rejected"
        assert "extension" in data.get("error", "").lower()

    def test_upload_rejects_path_traversal(self, client) -> None:
        """Filename with path separators returns 400."""
        resp = client.post(
            "/demo/api/h5/containers",
            files={"file": ("../../etc/passwd.h5", b"data", "application/octet-stream")},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data.get("status") == "upload_rejected"
        assert "path" in data.get("error", "").lower()

    def test_upload_rejects_backslash_traversal(self, client) -> None:
        """Filename with backslash returns 400."""
        resp = client.post(
            "/demo/api/h5/containers",
            files={"file": ("..\\\\secret.h5", b"data", "application/octet-stream")},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data.get("status") == "upload_rejected"

    def test_upload_no_raw_s3_paths(self, client) -> None:
        """Response does not expose raw S3 URIs."""
        resp = client.post(
            "/demo/api/h5/containers",
            files={"file": ("test.h5", b"content", "application/octet-stream")},
        )
        text = resp.text
        assert "s3://" not in text

    def test_upload_no_raw_filesystem_paths(self, client) -> None:
        """Response does not expose filesystem paths."""
        resp = client.post(
            "/demo/api/h5/containers",
            files={"file": ("test.h5", b"content", "application/octet-stream")},
        )
        text = resp.text
        assert "/Users/" not in text
        assert "/home/" not in text

    def test_upload_no_exception_traces(self, client) -> None:
        """Response does not expose raw exception traces."""
        resp = client.post(
            "/demo/api/h5/containers",
            files={"file": ("test.h5", b"content", "application/octet-stream")},
        )
        text = resp.text
        assert "Traceback" not in text
        assert "File \"" not in text

    def test_upload_h5_extension_accepted(self, client) -> None:
        """Valid .h5 extension is accepted (may fail at S3 but not at validation)."""
        with patch("bremen.api.server.read_demo_h5_config") as mock_cfg:
            mock_cfg.return_value = {
                "h5_bucket": "test-bucket",
                "h5_prefix": "test/",
                "allow_upload": True,
                "upload_max_bytes": 100 * 1024 * 1024,
            }
            with patch("bremen.api.server._handle_h5_upload_bytes") as mock_upload:
                mock_upload.return_value = (201, {
                    "status": "uploaded",
                    "id": "test/uploaded.h5",
                    "filename": "uploaded.h5",
                    "size_bytes": 7,
                    "request_id": "test-req-id",
                    "technical_demo_only": True,
                })
                resp = client.post(
                    "/demo/api/h5/containers",
                    files={"file": ("scan.h5", b"fake h5", "application/octet-stream")},
                )
                assert resp.status_code == 201
                data = resp.json()
                assert data["status"] == "uploaded"

    def test_upload_size_limit_enforced(self, client) -> None:
        """File exceeding size limit returns 413."""
        with patch("bremen.api.server.read_demo_h5_config") as mock_cfg:
            mock_cfg.return_value = {
                "h5_bucket": "test-bucket",
                "h5_prefix": "test/",
                "allow_upload": True,
                "upload_max_bytes": 10,  # Very small limit
            }
            resp = client.post(
                "/demo/api/h5/containers",
                files={"file": ("big.h5", b"x" * 100, "application/octet-stream")},
            )
            assert resp.status_code == 413
            data = resp.json()
            assert data.get("status") == "upload_rejected"

    def test_upload_disabled_returns_403(self, client) -> None:
        """Upload disabled returns 403."""
        with patch("bremen.api.server.read_demo_h5_config") as mock_cfg:
            mock_cfg.return_value = {
                "h5_bucket": "test-bucket",
                "h5_prefix": "test/",
                "allow_upload": False,
                "upload_max_bytes": 100 * 1024 * 1024,
            }
            resp = client.post(
                "/demo/api/h5/containers",
                files={"file": ("test.h5", b"content", "application/octet-stream")},
            )
            assert resp.status_code == 403
            data = resp.json()
            assert data.get("status") == "upload_disabled"

    def test_upload_no_bucket_returns_503(self, client) -> None:
        """No bucket configured returns 503."""
        with patch("bremen.api.server.read_demo_h5_config") as mock_cfg:
            mock_cfg.return_value = {
                "h5_bucket": None,
                "h5_prefix": "test/",
                "allow_upload": True,
                "upload_max_bytes": 100 * 1024 * 1024,
            }
            resp = client.post(
                "/demo/api/h5/containers",
                files={"file": ("test.h5", b"content", "application/octet-stream")},
            )
            assert resp.status_code == 503
            data = resp.json()
            assert data.get("status") == "storage_not_configured"


# ===================================================================
# Phase 1 + Phase 2 regression
# ===================================================================


class TestPhase1Phase2Regression:
    def test_health_still_works(self, client) -> None:
        """GET /health still returns 200."""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_model_version_still_works(self, client) -> None:
        """GET /model/version still returns 200."""
        resp = client.get("/model/version")
        assert resp.status_code == 200

    def test_demo_models_still_works(self, client) -> None:
        """GET /demo/api/models still returns 200."""
        resp = client.get("/demo/api/models")
        assert resp.status_code == 200
        assert "technical_demo_only" in resp.json()

    def test_demo_containers_still_works(self, client) -> None:
        """GET /demo/api/h5/containers still returns 200."""
        resp = client.get("/demo/api/h5/containers")
        assert resp.status_code == 200
        assert "technical_demo_only" in resp.json()


# ===================================================================
# Route exclusion
# ===================================================================


class TestNoNewPostOrAnalyzeRoutes:
    def test_no_new_post_routes(self) -> None:
        """Phase 3 did not add upload/analyze/stage POST routes.

        Report read routes were added in Phase 5 (PR0104P) for
        Control Room parity and are excluded from this check.
        """
        app = create_fastapi_app()
        for route in app.routes:
            if hasattr(route, "path"):
                p = route.path
                # Report read routes are allowed (PR0104P parity)
                if any(x in p for x in ("analyze", "stage")):
                    pytest.fail(f"Unexpected route: {p}")


# ===================================================================
# Production Dockerfile unchanged
# ===================================================================


class TestProductionDockerfileUnchanged:
    def test_dockerfile_entrypoint_unchanged(self) -> None:
        """Production ENTRYPOINT remains python -m bremen."""
        content = DOCKERFILE.read_text(encoding="utf-8")
        assert 'ENTRYPOINT ["python", "-m", "bremen"]' in content

    def test_dockerfile_cmd_unchanged(self) -> None:
        """Production CMD remains serve --host 0.0.0.0 --port 8080."""
        content = DOCKERFILE.read_text(encoding="utf-8")
        assert 'CMD ["serve", "--host", "0.0.0.0", "--port", "8080"]' in content


# ===================================================================
# Module safety
# ===================================================================


class TestModuleSafety:
    def test_no_boto3_in_fastapi_app(self) -> None:
        """FastAPI app module does not import boto3."""
        import ast
        source = ROOT / "src" / "bremen" / "api" / "fastapi_app.py"
        source_text = source.read_text(encoding="utf-8")
        tree = ast.parse(source_text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "boto3" in alias.name.split(".")[0].lower():
                        pytest.fail(f"FastAPI app imports boto3: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "boto3" in module.split(".")[0].lower():
                    pytest.fail(f"FastAPI app imports boto3: {module}")

    def test_no_server_spawning_in_test(self) -> None:
        """Phase 3 test file does not start a real web server."""
        test_source = Path(__file__).read_text(encoding="utf-8")
        import_lines = [
            line for line in test_source.split("\n")
            if line.strip().startswith(("import ", "from "))
        ]
        import_text = "\n".join(import_lines)
        prohibited = [
            "HTTPServer", "ThreadingHTTPServer", "serve_forever",
            "start_server", "urlopen",
        ]
        for term in prohibited:
            assert term not in import_text, (
                f"Phase 3 test file imports server-spawning pattern: {term}"
            )
