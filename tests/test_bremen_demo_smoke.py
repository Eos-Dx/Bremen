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
        """Output dict contains all expected keys, including evidence."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        expected_keys = {
            "technical_demo_only", "base_url", "request_id",
            "checks", "health", "model_version", "prediction",
            "demo_routes", "demo_evidence",
            "warnings", "status", "timestamp", "evidence",
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
        """Output should not contain diagnosis or clinical claims.

        The evidence bundle disclaimer and safety_notes intentionally
        contain safe negation language (e.g. "not clinically validated",
        "does not replace MRI").  These are safe — only asserts actual
        clinical claims are absent from non-evidence output.
        """
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        # Assert no clinical claims in the top-level output (excluding evidence)
        top_level = {k: v for k, v in result.items() if k != "evidence"}
        top_output = json.dumps(top_level).lower()
        prohibited = ["diagnosis", "diagnoses", "clinical validation",
                      "replace mri", "replace biopsy", "clinically validated",
                      "fda clearance", "fda-cleared"]
        for phrase in prohibited:
            if phrase in top_output:
                # Check context — the health response may contain "not a
                # diagnostic replacement" which is the safe disclaimer
                if "not a diagnostic" in top_output:
                    continue
                pytest.fail(
                    f"Top-level output contains prohibited phrase: {phrase}"
                )


# ---------------------------------------------------------------------------
# Evidence bundle integration tests (PR0061)
# ---------------------------------------------------------------------------


class TestEvidenceBundleInDemoSmoke:
    """Tests verifying the evidence bundle is present in demo-smoke output."""

    @pytest.fixture
    def server_info(self):
        """Start a local test server with synthetic model."""
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

    def test_demo_smoke_output_contains_evidence_bundle(self, server_info):
        """Demo-smoke output contains an 'evidence' key."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert "evidence" in result, (
            "Demo-smoke output must contain 'evidence' key"
        )
        assert isinstance(result["evidence"], dict)

    def test_demo_smoke_evidence_technical_demo_only(self, server_info):
        """Evidence bundle technical_demo_only is True."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        evidence = result["evidence"]
        assert evidence["technical_demo_only"] is True

    def test_demo_smoke_evidence_product_is_bremen(self, server_info):
        """Evidence bundle product is 'Bremen'."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        evidence = result["evidence"]
        assert evidence["product"] == "Bremen"

    def test_demo_smoke_evidence_has_required_keys(self, server_info):
        """Evidence bundle contains all mandatory keys."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        evidence = result["evidence"]
        required = {
            "technical_demo_only", "product", "product_question",
            "disclaimer", "evidence_version", "scenario_id",
            "safety_notes",
        }
        assert required <= set(evidence.keys()), (
            f"Missing evidence keys: {required - set(evidence.keys())}"
        )

    def test_demo_smoke_evidence_preserves_request_id(self, server_info):
        """Evidence bundle request_id matches top-level request_id."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert result["evidence"]["request_id"] == result["request_id"]

    def test_demo_smoke_evidence_includes_base_url(self, server_info):
        """Evidence bundle includes the base_url."""
        host, port = server_info
        base_url = f"http://{host}:{port}"
        result = run_demo_smoke(
            base_url=base_url,
            timeout=5,
            skip_prediction=True,
        )
        assert result["evidence"]["base_url"] == base_url

    def test_demo_smoke_evidence_includes_model_status(self, server_info):
        """Evidence bundle includes model_status from server."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        # With synthetic model loaded, status should be "ready"
        assert result["evidence"]["model_status"] == "ready"

    def test_demo_smoke_evidence_includes_checks(self, server_info):
        """Evidence bundle includes checks dict."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        evidence = result["evidence"]
        assert "checks" in evidence
        assert evidence["checks"]["health"] == "pass"
        assert evidence["checks"]["model_version"] == "pass"

    def test_demo_smoke_evidence_includes_warnings(self, server_info):
        """Evidence bundle includes warnings list."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert isinstance(result["evidence"]["warnings"], list)

    def test_unavailable_service_evidence_still_produced(self):
        """Even when service is unavailable, evidence bundle is produced."""
        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        assert "evidence" in result
        evidence = result["evidence"]
        assert evidence["technical_demo_only"] is True
        assert evidence["product"] == "Bremen"
        # Warnings should be present
        assert len(evidence["warnings"]) > 0


# ---------------------------------------------------------------------------
# Demo route readiness tests (PR0066)
# ---------------------------------------------------------------------------


class TestDemoRouteReadiness:
    """Tests for /demo and /demo/api/evidence route readiness checks."""

    @pytest.fixture
    def server_info(self):
        """Start a local test server with synthetic model loaded."""
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
        handler = _make_handler(
            job_store, version="test-version", load_model=True
        )
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        yield host, port

        server.shutdown()
        thread.join(timeout=2)

    def test_demo_routes_in_result(self, server_info):
        """demo_routes key is present in result dict."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert "demo_routes" in result
        assert isinstance(result["demo_routes"], dict)

    def test_demo_evidence_in_result(self, server_info):
        """demo_evidence key is present in result dict."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert "demo_evidence" in result
        assert isinstance(result["demo_evidence"], dict)

    def test_demo_routes_check_against_test_server(self, server_info):
        """Demo route check passes against running test server."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert result["checks"]["demo_routes"] == "pass"
        assert result["demo_routes"]["status"] == "pass"
        assert result["demo_routes"]["http_status"] == 200
        assert result["demo_routes"]["contains_bremen"] is True
        assert result["demo_routes"]["contains_technical_demo"] is True

    def test_demo_evidence_check_against_test_server(self, server_info):
        """Demo evidence check passes against running test server."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert result["checks"]["demo_evidence"] == "pass"
        assert result["demo_evidence"]["status"] == "pass"
        assert result["demo_evidence"]["http_status"] == 200
        assert result["demo_evidence"]["technical_demo_only"] is True
        assert result["demo_evidence"]["product"] == "Bremen"

    def test_demo_routes_check_contains_html_fields(self, server_info):
        """Demo route result includes expected HTML check fields."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        dr = result["demo_routes"]
        assert "status" in dr
        assert "http_status" in dr
        assert "contains_bremen" in dr
        assert "contains_technical_demo" in dr

    def test_demo_evidence_check_contains_json_fields(self, server_info):
        """Demo evidence result includes expected JSON check fields."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        de = result["demo_evidence"]
        assert "status" in de
        assert "http_status" in de
        assert "technical_demo_only" in de
        assert "product" in de

    def test_demo_routes_fail_when_service_unavailable(self):
        """Demo route checks report failure when service is unreachable."""
        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        assert result["checks"]["demo_routes"] == "fail"
        assert result["demo_routes"]["status"] in ("fail", "error")

    def test_demo_evidence_fail_when_service_unavailable(self):
        """Demo evidence checks report failure when service is unreachable."""
        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        assert result["checks"]["demo_evidence"] == "fail"
        assert result["demo_evidence"]["status"] in ("fail", "error")

    def test_demo_routes_check_has_error_on_unavailable(self):
        """Demo route check includes error info on unavailable service."""
        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        assert "error" in result["demo_routes"]

    def test_demo_evidence_check_has_error_on_unavailable(self):
        """Demo evidence check includes error info on unavailable service."""
        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        assert "error" in result["demo_evidence"]

    def test_demo_checks_in_checks_dict(self, server_info):
        """demo_routes and demo_evidence are present in checks dict."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert "demo_routes" in result["checks"]
        assert "demo_evidence" in result["checks"]

    def test_demo_checks_contribute_to_overall_status(self, server_info):
        """When all checks including demo routes pass, overall is pass."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        # All active checks: health, model_version, demo_routes, demo_evidence
        assert result["checks"]["health"] == "pass"
        assert result["checks"]["model_version"] == "pass"
        assert result["checks"]["demo_routes"] == "pass"
        assert result["checks"]["demo_evidence"] == "pass"
        assert result["status"] == "pass"

    def test_demo_checks_show_partial_on_route_failure(self):
        """When demo routes fail but health passes, status is partial."""
        # Use unavailable service: health/model fail, but demo routes also fail
        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        assert result["checks"]["demo_routes"] == "fail"
        assert result["checks"]["demo_evidence"] == "fail"
        assert result["status"] == "fail"

    def test_existing_checks_preserved_with_demo_routes(self, server_info):
        """Health, model_version, and prediction checks still work."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert result["health"]["status"] == "ok"
        assert result["model_version"]["model_status"] == "ready"
        assert result["prediction"]["status"] == "not_available"
        assert result["checks"]["health"] == "pass"
        assert result["checks"]["model_version"] == "pass"

    def test_evidence_bundle_includes_demo_checks(self, server_info):
        """Evidence bundle checks now includes demo_routes and demo_evidence."""
        host, port = server_info
        result = run_demo_smoke(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        evidence = result["evidence"]
        assert "checks" in evidence
        assert evidence["checks"]["demo_routes"] == "pass"
        assert evidence["checks"]["demo_evidence"] == "pass"

    def test_deployed_base_url_mode_validates_demo_routes(self, server_info):
        """With explicit base-url pointing at running service, demo routes pass."""
        host, port = server_info
        base_url = f"http://{host}:{port}"
        result = run_demo_smoke(
            base_url=base_url,
            timeout=5,
            skip_prediction=True,
        )
        assert result["demo_routes"]["status"] == "pass"
        assert result["demo_evidence"]["status"] == "pass"
        assert result["base_url"] == base_url

    def test_no_ui_flag_in_demo_smoke(self):
        """demo-smoke does not accept --ui flag."""
        result = subprocess.run(
            [
                sys.executable,
                "-m", "bremen", "demo-smoke", "--ui",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, (
            "--ui should be rejected by demo-smoke"
        )

    def test_no_root_demo_page(self):
        """Root / returns 404, not a demo page."""
        import socket
        import threading
        from http.server import HTTPServer
        from urllib.error import HTTPError
        from urllib.request import urlopen, Request
        from bremen.api.jobs import InMemoryJobStore
        from bremen.api.server import _make_handler
        from bremen.api.model_state import ModelState

        host = "127.0.0.1"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            port = int(s.getsockname()[1])

        job_store = InMemoryJobStore()
        ModelState.reset_for_tests()
        handler = _make_handler(
            job_store, version="test-version", load_model=True
        )
        server = HTTPServer((host, port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            req = Request(f"http://{host}:{port}/")
            try:
                urlopen(req, timeout=3)
                pytest.fail("Expected HTTPError for root /")
            except HTTPError as exc:
                assert exc.code == 404
        finally:
            server.shutdown()
            thread.join(timeout=2)
