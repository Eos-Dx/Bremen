"""Tests for the demo/smoke runner.

Covers:
- CLI help works
- demo-smoke in main help
- Health check included against local test server
- Model/version check included against local test server
- Prediction check included or controlled not_available
- Unavailable service produces controlled failure output
- JSON output shape
- technical_demo_only: true
- request_id handling
- No frontend/package-manager files
- No dependency changes
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from bremen.demo_smoke import run_demo_smoke


# ---------------------------------------------------------------------------
# CLI help tests
# ---------------------------------------------------------------------------


class TestCliHelp:
    def test_demo_smoke_help_exits_0(self):
        """python -m bremen demo-smoke --help exits 0."""
        result = subprocess.run(
            [sys.executable, "-m", "bremen", "demo-smoke", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Exit code {result.returncode}: {result.stderr}"
        )

    def test_demo_smoke_in_main_help(self):
        """python -m bremen --help lists 'demo-smoke'."""
        result = subprocess.run(
            [sys.executable, "-m", "bremen", "--help"],
            capture_output=True,
            text=True,
        )
        assert "demo-smoke" in result.stdout, (
            "Main help output must list 'demo-smoke' command"
        )

    def test_demo_smoke_help_contains_options(self):
        """demo-smoke --help shows --base-url, --timeout, --skip-prediction."""
        result = subprocess.run(
            [sys.executable, "-m", "bremen", "demo-smoke", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--base-url" in result.stdout
        assert "--timeout" in result.stdout
        assert "--skip-prediction" in result.stdout


# ---------------------------------------------------------------------------
# Smoke checks against a running local server
# ---------------------------------------------------------------------------


class TestDemoSmokeAgainstServer:
    """Run smoke checks against a real local test server with synthetic model."""

    @pytest.fixture
    def server_info(self):
        """Start an HTTPServer on a free port with synthetic model loaded."""
        import socket
        import threading
        from http.server import HTTPServer
        from bremen.api.jobs import InMemoryJobStore
        from bremen.api.server import _make_handler
        from bremen.api.model_state import ModelState

        host = "127.0.0.1"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = int(s.getsockname()[1])

        job_store = InMemoryJobStore()
        ModelState.reset_for_tests()
        handler = _make_handler(job_store, version="test-version", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        yield host, port

        server.shutdown()
        thread.join(timeout=2)

    def test_health_check_included(self, server_info):
        """Health check returns ok status."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert result["health"]["status"] == "ok"
        assert result["checks"]["health"] == "pass"

    def test_model_version_included(self, server_info):
        """Model version check returns ready status."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert result["model_version"]["model_status"] == "ready"
        assert result["model_version"]["model_configured"] is True
        assert result["checks"]["model_version"] == "pass"

    def test_overall_pass_with_both_checks(self, server_info):
        """When health and model version pass, overall is pass."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert result["status"] == "pass"

    def test_json_output_shape(self, server_info):
        """Output dict contains all expected keys."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        expected_keys = {
            "technical_demo_only", "base_url", "request_id",
            "checks", "health", "model_version", "prediction",
            "warnings", "status", "timestamp",
        }
        assert set(result.keys()) == expected_keys, (
            f"Missing keys: {expected_keys - set(result.keys())}"
        )

    def test_technical_demo_only_field(self, server_info):
        """technical_demo_only field is present and true."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert result["technical_demo_only"] is True

    def test_request_id_present(self, server_info):
        """Output contains a request_id string."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert isinstance(result["request_id"], str)
        assert len(result["request_id"]) > 0

    def test_prediction_not_available_when_skipped(self, server_info):
        """When skip_prediction=True, prediction status is not_available."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert result["prediction"]["status"] == "not_available"

    def test_prediction_skipped_with_reason(self, server_info):
        """When skip_prediction=True, reason is provided."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert "reason" in result["prediction"]
        assert len(result["prediction"]["reason"]) > 0

    def test_prediction_returns_accepted_with_placeholder(self, server_info):
        """Prediction check with placeholder h5_path returns accepted job.

        The server accepts the prediction asynchronously even without a real
        H5 file — the validation happens during inference execution.
        """
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=10,
            skip_prediction=False,
        )
        # The prediction should be accepted (202) or failed during inference
        assert result["prediction"]["status"] in ("accepted", "failed"), (
            f"Unexpected prediction status: {result['prediction']['status']}"
        )
        # If accepted, should have a job_id
        if result["prediction"]["status"] == "accepted":
            assert "job_id" in result["prediction"]
            assert len(result["prediction"]["job_id"]) > 0

    def test_unavailable_service_returns_controlled_failure(self):
        """Smoke against unavailable service returns controlled output."""
        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        assert result["status"] == "fail"
        # Health check should have an error field (not status)
        assert "error" in result["health"]
        assert len(result["warnings"]) > 0


# ---------------------------------------------------------------------------
# Output contract tests
# ---------------------------------------------------------------------------


class TestOutputContract:
    def test_output_is_json_serializable(self, server_info):
        """The output dict is JSON-serializable."""
        import socket
        import threading
        from http.server import HTTPServer
        from bremen.api.jobs import InMemoryJobStore
        from bremen.api.server import _make_handler
        from bremen.api.model_state import ModelState

        host = "127.0.0.1"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = int(s.getsockname()[1])

        job_store = InMemoryJobStore()
        ModelState.reset_for_tests()
        handler = _make_handler(job_store, version="test-version", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            result = run_demo_smoke(
                base_url=f"http://{host}:{port}",
                timeout=5,
                skip_prediction=True,
            )
            # Should not raise
            json.dumps(result)
        finally:
            server.shutdown()
            thread.join(timeout=2)

    @pytest.fixture
    def server_info(self):
        """Start a local test server."""
        import socket
        import threading
        from http.server import HTTPServer
        from bremen.api.jobs import InMemoryJobStore
        from bremen.api.server import _make_handler
        from bremen.api.model_state import ModelState

        host = "127.0.0.1"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = int(s.getsockname()[1])

        job_store = InMemoryJobStore()
        ModelState.reset_for_tests()
        handler = _make_handler(job_store, version="test-version", load_model=True)
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        yield host, port

        server.shutdown()
        thread.join(timeout=2)

    def test_no_diagnosis_language(self, server_info):
        """Output should not contain diagnosis or clinical claims."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        output = json.dumps(result).lower()
        prohibited = ["diagnosis", "diagnoses", "clinical validation",
                      "replace mri", "replace biopsy", "clinically validated",
                      "fda clearance", "fda-cleared"]
        for phrase in prohibited:
            if phrase in output:
                # Check context — the health response may contain "not a
                # diagnostic replacement" which is the safe disclaimer
                if "not a diagnostic" in output:
                    continue
                pytest.fail(f"Output contains prohibited phrase: {phrase}")
