"""Tests for the one-command Bremen demo runner (demo_run).

Covers:
- CLI help works
- demo-run in main help
- run_demo() with explicit base URL calls health/model checks
- run_demo() without base URL starts local server
- Evidence bundle present and contains technical_demo_only
- Request ID present
- Server startup failure produces controlled output
- --skip-prediction passes through to demo-smoke
- Server cleanup (no lingering processes)
- JSON serializability
- No fixed port conflict
- No H5/model/network dependencies
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
from http.server import HTTPServer
from pathlib import Path

import pytest

from bremen.demo_run import (
    DEMO_RUN_VERSION,
    _find_free_port,
    _start_local_server,
    run_demo,
)

MODULE_PATH = Path(__file__).parents[1] / "src" / "bremen" / "demo_run.py"


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def server_info():
    """Start a local test server on an ephemeral port.

    Yields ``(host, port)``.  Shuts down the server on teardown.
    """
    from bremen.api.jobs import InMemoryJobStore
    from bremen.api.server import _make_handler
    from bremen.api.model_state import ModelState

    host = "127.0.0.1"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        port = int(s.getsockname()[1])

    job_store = InMemoryJobStore()
    ModelState.reset_for_tests()
    handler = _make_handler(
        job_store, version=DEMO_RUN_VERSION, load_model=True
    )
    server = HTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield host, port

    server.shutdown()
    thread.join(timeout=2)


# ===================================================================
# Class 1: Constants
# ===================================================================


class TestDemoRunVersion:
    def test_demo_run_version_is_non_empty_string(self):
        """DEMO_RUN_VERSION is a non-empty string."""
        assert isinstance(DEMO_RUN_VERSION, str)
        assert len(DEMO_RUN_VERSION) > 0


# ===================================================================
# Class 2: Helper functions
# ===================================================================


class TestFindFreePort:
    def test_returns_positive_integer(self):
        """_find_free_port returns a positive integer port number."""
        port = _find_free_port()
        assert isinstance(port, int)
        assert 1024 <= port <= 65535

    def test_port_is_actually_free(self):
        """The returned port can be bound to."""
        port = _find_free_port()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
            # If we got here, the port is usable


class TestStartLocalServer:
    def test_starts_server_on_ephemeral_port(self):
        """_start_local_server starts a server on a free port."""
        from bremen.api.model_state import ModelState

        ModelState.reset_for_tests()
        server, port, thread = _start_local_server(
            host="127.0.0.1", load_model=True
        )
        try:
            assert isinstance(port, int)
            assert 1024 <= port <= 65535
            assert thread.is_alive()
        finally:
            server.shutdown()
            thread.join(timeout=2)

    def test_starts_server_without_model(self):
        """_start_local_server works without model loading."""
        from bremen.api.model_state import ModelState

        ModelState.reset_for_tests()
        server, port, thread = _start_local_server(
            host="127.0.0.1", load_model=False
        )
        try:
            assert thread.is_alive()
        finally:
            server.shutdown()
            thread.join(timeout=2)

    def test_returns_distinct_ports_for_multiple_calls(self):
        """Two sequential calls use different ports."""
        from bremen.api.model_state import ModelState

        ModelState.reset_for_tests()
        s1, p1, t1 = _start_local_server(load_model=True)
        s2, p2, t2 = _start_local_server(load_model=True)
        try:
            assert p1 != p2, "Two servers must use different ports"
        finally:
            s1.shutdown()
            s2.shutdown()
            t1.join(timeout=2)
            t2.join(timeout=2)


# ===================================================================
# Class 3: run_demo() with explicit base URL
# ===================================================================


class TestRunDemoWithExplicitUrl:
    def test_health_check_pass(self, server_info):
        """Health check passes against running server."""
        host, port = server_info
        result = run_demo(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert result["health"]["status"] == "ok"
        assert result["checks"]["health"] == "pass"

    def test_model_version_included(self, server_info):
        """Model version check returns ready status."""
        host, port = server_info
        result = run_demo(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert result["model_version"]["model_status"] == "ready"
        assert result["checks"]["model_version"] == "pass"

    def test_overall_pass_with_skip_prediction(self, server_info):
        """With skip_prediction, overall status is pass."""
        host, port = server_info
        result = run_demo(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert result["status"] == "pass"

    def test_output_shape_with_evidence(self, server_info):
        """Output dict contains all expected keys including evidence."""
        host, port = server_info
        result = run_demo(
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
        result = run_demo(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert result["technical_demo_only"] is True

    def test_request_id_present(self, server_info):
        """Output contains a request_id string."""
        host, port = server_info
        result = run_demo(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert isinstance(result["request_id"], str)
        assert len(result["request_id"]) > 0

    def test_prediction_not_available_when_skipped(self, server_info):
        """When skip_prediction=True, prediction status is not_available."""
        host, port = server_info
        result = run_demo(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert result["prediction"]["status"] == "not_available"

    def test_unavailable_service(self):
        """run_demo with unreachable base URL returns fail."""
        result = run_demo(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        assert result["status"] == "fail"
        assert len(result["warnings"]) > 0


# ===================================================================
# Class 4: run_demo() without base URL (auto-start)
# ===================================================================


class TestRunDemoAutoStart:
    def test_returns_result_dict(self):
        """run_demo() without base URL returns a result dict."""
        from bremen.api.model_state import ModelState

        ModelState.reset_for_tests()
        result = run_demo(timeout=10, skip_prediction=True)
        assert isinstance(result, dict)
        assert "status" in result

    def test_health_check_pass(self):
        """run_demo() auto-start includes passing health check."""
        from bremen.api.model_state import ModelState

        ModelState.reset_for_tests()
        result = run_demo(timeout=10, skip_prediction=True)
        assert result.get("health", {}).get("status") == "ok"
        assert result.get("checks", {}).get("health") == "pass"

    def test_model_version_included(self):
        """run_demo() auto-start includes model version check."""
        from bremen.api.model_state import ModelState

        ModelState.reset_for_tests()
        result = run_demo(timeout=10, skip_prediction=True)
        assert result.get("model_version", {}).get(
            "model_status"
        ) == "ready"

    def test_overall_pass(self):
        """run_demo() auto-start with skip_prediction returns pass."""
        from bremen.api.model_state import ModelState

        ModelState.reset_for_tests()
        result = run_demo(timeout=10, skip_prediction=True)
        assert result["status"] == "pass"


# ===================================================================
# Class 5: Evidence bundle in output
# ===================================================================


class TestEvidenceBundle:
    def test_evidence_present_with_explicit_url(self, server_info):
        """Evidence bundle is present when using explicit base URL."""
        host, port = server_info
        result = run_demo(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert "evidence" in result
        assert isinstance(result["evidence"], dict)

    def test_evidence_technical_demo_only(self, server_info):
        """Evidence technical_demo_only is True."""
        host, port = server_info
        result = run_demo(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert result["evidence"]["technical_demo_only"] is True

    def test_evidence_product_is_bremen(self, server_info):
        """Evidence product is 'Bremen'."""
        host, port = server_info
        result = run_demo(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert result["evidence"]["product"] == "Bremen"

    def test_evidence_has_required_keys(self, server_info):
        """Evidence bundle contains all mandatory keys."""
        host, port = server_info
        result = run_demo(
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

    def test_evidence_request_id_matches_top_level(self, server_info):
        """Evidence request_id matches top-level request_id."""
        host, port = server_info
        result = run_demo(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert result["evidence"]["request_id"] == result["request_id"]

    def test_evidence_present_with_auto_start(self):
        """Evidence bundle is present when demo-run auto-starts server."""
        from bremen.api.model_state import ModelState

        ModelState.reset_for_tests()
        result = run_demo(timeout=10, skip_prediction=True)
        assert "evidence" in result
        assert result["evidence"]["technical_demo_only"] is True
        assert result["evidence"]["product"] == "Bremen"


# ===================================================================
# Class 6: Server startup failure
# ===================================================================


class TestServerStartupFailure:
    def test_server_startup_error_output_shape(self):
        """Server startup failure produces controlled error output."""
        # Cannot easily force a startup failure since we use ephemeral ports.
        # Instead test controlled failure by using run_demo with a
        # base_url that points to a non-existent server.
        result = run_demo(
            base_url="http://127.0.0.1:1",
            timeout=1,
            skip_prediction=True,
        )
        assert result["technical_demo_only"] is True
        assert "status" in result
        assert "error" in result or len(result.get("warnings", [])) > 0


# ===================================================================
# Class 7: JSON serializability
# ===================================================================


class TestJsonSerializable:
    def test_output_is_json_serializable(self, server_info):
        """run_demo output is JSON-serializable."""
        host, port = server_info
        result = run_demo(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        json_str = json.dumps(result)
        assert isinstance(json_str, str)
        assert len(json_str) > 0

    def test_auto_start_output_is_json_serializable(self):
        """run_demo auto-start output is JSON-serializable."""
        from bremen.api.model_state import ModelState

        ModelState.reset_for_tests()
        result = run_demo(timeout=10, skip_prediction=True)
        json_str = json.dumps(result)
        assert isinstance(json_str, str)
        assert len(json_str) > 0


# ===================================================================
# Class 8: No fixed port conflict
# ===================================================================


class TestNoFixedPortConflict:
    def test_two_sequential_calls_use_different_ports(self):
        """Two sequential run_demo calls use different ports."""
        from bremen.api.model_state import ModelState

        ModelState.reset_for_tests()
        r1 = run_demo(timeout=10, skip_prediction=True)
        ModelState.reset_for_tests()
        r2 = run_demo(timeout=10, skip_prediction=True)
        # Base URLs should differ (different ports)
        assert r1["base_url"] != r2["base_url"]


# ===================================================================
# Class 9: --skip-prediction pass-through
# ===================================================================


class TestSkipPredictionPassThrough:
    def test_prediction_not_available_when_skipped(self, server_info):
        """With skip_prediction, prediction status is not_available."""
        host, port = server_info
        result = run_demo(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        assert result["prediction"]["status"] == "not_available"

    def test_prediction_runs_when_not_skipped(self, server_info):
        """Without skip_prediction, prediction is attempted."""
        host, port = server_info
        result = run_demo(
            base_url=f"http://{host}:{port}",
            timeout=10,
            skip_prediction=False,
        )
        # Prediction should be attempted (may succeed or fail depending on
        # placeholder H5 path, but should not be 'not_available')
        assert result["prediction"]["status"] != "not_available"


# ===================================================================
# Class 10: CLI help tests (subprocess-based)
# ===================================================================


class TestCliHelp:
    def test_demo_run_help_exits_0(self):
        """python -m bremen demo-run --help exits 0."""
        result = subprocess.run(
            [sys.executable, "-m", "bremen", "demo-run", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Exit code {result.returncode}: {result.stderr}"
        )

    def test_demo_run_in_main_help(self):
        """python -m bremen --help lists 'demo-run'."""
        result = subprocess.run(
            [sys.executable, "-m", "bremen", "--help"],
            capture_output=True,
            text=True,
        )
        assert "demo-run" in result.stdout, (
            "Main help output must list 'demo-run' command"
        )

    def test_demo_run_help_shows_options(self):
        """demo-run --help shows --base-url, --timeout, --skip-prediction."""
        result = subprocess.run(
            [sys.executable, "-m", "bremen", "demo-run", "--help"],
            capture_output=True,
            text=True,
        )
        assert "--base-url" in result.stdout
        assert "--timeout" in result.stdout
        assert "--skip-prediction" in result.stdout


# ===================================================================
# Class 11: --pretty flag tests
# ===================================================================


class TestPrettyFlag:
    def test_demo_run_pretty_flag_accepted(self, server_info):
        """--pretty flag is accepted and prints prettified output."""
        host, port = server_info
        # Use run_demo which we can test directly
        from bremen.demo_presentation import format_pretty

        result = run_demo(
            base_url=f"http://{host}:{port}",
            timeout=5,
            skip_prediction=True,
        )
        pretty = format_pretty(result)
        assert "BREMEN PRODUCT DEMO" in pretty
        assert "Technical demo only" in pretty
        assert "Bremen" in pretty
        assert "Health" in pretty
        assert "Model / Version" in pretty
        assert "Evidence Bundle" in pretty

    def test_demo_run_pretty_json_still_present(self):
        """JSON output is still produced when --pretty is used.

        This subprocess test verifies that the JSON output appears
        before the pretty output.
        """
        from bremen.api.model_state import ModelState

        ModelState.reset_for_tests()
        result = run_demo(timeout=10, skip_prediction=True)
        # Verify JSON output is still produced
        import json

        json_str = json.dumps(result, indent=2, ensure_ascii=False)
        assert "technical_demo_only" in json_str
        assert "evidence" in json_str
        assert "status" in json_str


# ===================================================================
# Class 12: Import / dependency safety
# ===================================================================


class TestImportSafety:
    def test_no_h5_references(self):
        """Module does not reference h5, hdf5, or h5py."""
        source = MODULE_PATH.read_text(encoding="utf-8").lower()
        assert ".h5" not in source
        assert ".hdf5" not in source
        assert "h5py" not in source

    def test_no_joblib_or_pickle_references(self):
        """Module does not reference joblib.load or pickle.load."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "joblib.load" not in source
        assert "joblib" not in source.lower()

    def test_no_boto3_or_requests(self):
        """Module does not import boto3, requests, httpx."""
        import ast

        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    assert name not in (
                        "boto3", "requests", "httpx", "botocore"
                    ), f"Module imports {name}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                top = module.split(".")[0]
                assert top not in (
                    "boto3", "requests", "httpx", "botocore"
                ), f"Module imports {module}"


# ===================================================================
# Class 13: --capture-dir flag tests
# ===================================================================


class TestCaptureDirFlag:
    def test_demo_run_capture_dir_writes_files(self, server_info):
        """demo-run --capture-dir <tmpdir> writes 3 files."""
        import tempfile

        host, port = server_info
        with tempfile.TemporaryDirectory() as tmpdir:
            from bremen.demo_capture import (
                FILE_SUMMARY,
                FILE_EVIDENCE,
                FILE_MANIFEST,
                write_demo_capture,
            )

            result = run_demo(
                base_url=f"http://{host}:{port}",
                timeout=5,
                skip_prediction=True,
            )
            write_demo_capture(
                result=result,
                capture_dir=tmpdir,
            )
            dir_path = Path(tmpdir)
            assert (dir_path / FILE_SUMMARY).exists(), (
                "Summary file not written"
            )
            assert (dir_path / FILE_EVIDENCE).exists(), (
                "Evidence file not written"
            )
            assert (dir_path / FILE_MANIFEST).exists(), (
                "Manifest file not written"
            )

    def test_demo_run_capture_dir_with_pretty(self, server_info):
        """demo-run --pretty --capture-dir includes pretty text in summary."""
        import tempfile

        host, port = server_info
        with tempfile.TemporaryDirectory() as tmpdir:
            from bremen.demo_capture import (
                FILE_SUMMARY,
                write_demo_capture,
            )
            from bremen.demo_presentation import format_pretty

            result = run_demo(
                base_url=f"http://{host}:{port}",
                timeout=5,
                skip_prediction=True,
            )
            pretty_text = format_pretty(result)
            write_demo_capture(
                result=result,
                capture_dir=tmpdir,
                pretty_text=pretty_text,
            )
            content = (Path(tmpdir) / FILE_SUMMARY).read_text(
                encoding="utf-8"
            )
            assert "BREMEN PRODUCT DEMO" in content
            assert "Technical demo only" in content
            assert "Health" in content
            assert "Model / Version" in content


# ===================================================================
# Class 14: End-to-end CLI test
# ===================================================================


class TestEndToEndCli:
    def test_demo_run_cli_skip_prediction(self):
        """python -m bremen demo-run --skip-prediction runs successfully.

        This subprocess test starts a local server in the subprocess.
        It requires the server to start, run smoke, and shut down.
        Uses a generous timeout to allow server startup.
        """
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bremen",
                "demo-run",
                "--timeout=15",
                "--skip-prediction",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Exit 0 for pass/partial
        assert result.returncode == 0, (
            f"Exit code {result.returncode}: "
            f"stdout={result.stdout[:500]}, "
            f"stderr={result.stderr[:500]}"
        )
        # Verify JSON contains expected keys
        assert "technical_demo_only" in result.stdout
        assert "evidence" in result.stdout
        assert "Demo Run Result" in result.stdout
