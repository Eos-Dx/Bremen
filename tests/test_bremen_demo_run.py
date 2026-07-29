"""Tests for the one-command Bremen demo runner (demo_run).

Covers:
- CLI help works
- demo-run in main help
- Version constant
- Source safety (no h5/joblib/boto3/requests references)
- Output shape validation (direct function call)
- JSON serializability
- Pretty flag support

Server-dependent tests (run_demo with real HTTP) have been removed.
Those tests are covered by the manual smoke script and the http.server
integration suite.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from bremen.demo_run import DEMO_RUN_VERSION

MODULE_PATH = Path(__file__).parents[1] / "src" / "bremen" / "demo_run.py"


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture(scope="module")
def _cli_result_cache():
    cache: dict[tuple[str, ...], subprocess.CompletedProcess] = {}

    def _run(*args: str) -> subprocess.CompletedProcess:
        key = tuple(args)
        if key not in cache:
            cache[key] = subprocess.run(
                [sys.executable, *args], capture_output=True, text=True,
            )
        return cache[key]

    return _run


# ===================================================================
# Constants
# ===================================================================


class TestDemoRunVersion:
    def test_demo_run_version_is_non_empty_string(self):
        """DEMO_RUN_VERSION is a non-empty string."""
        assert isinstance(DEMO_RUN_VERSION, str)
        assert len(DEMO_RUN_VERSION) > 0


# ===================================================================
# Source safety checks (AST-based, no server)
# ===================================================================


class TestSourceSafety:
    def test_no_h5_references(self):
        """demo_run.py does not import h5py."""
        src = MODULE_PATH.read_text(encoding="utf-8")
        assert "h5py" not in src

    def test_no_joblib_or_pickle_references(self):
        """demo_run.py does not import joblib or pickle."""
        src = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "joblib" not in alias.name.lower()
                    assert "pickle" not in alias.name.lower()

    def test_no_boto3_or_requests(self):
        """demo_run.py does not import boto3 or requests."""
        src = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(src)
        prohibited = {"boto3", "botocore", "requests", "httpx"}
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    assert name not in prohibited, f"demo_run imports {name}"
            elif isinstance(node, ast.ImportFrom):
                module = (node.module or "").split(".")[0]
                assert module not in prohibited, f"demo_run imports from {module}"


# ===================================================================
# CLI help tests (subprocess, no server)
# ===================================================================


class TestDemoRunCLI:
    def test_demo_run_help_exits_0(self, _cli_result_cache):
        """python -m bremen demo-run --help exits 0."""
        result = _cli_result_cache("-m", "bremen", "demo-run", "--help")
        assert result.returncode == 0
        assert "demo-run" in result.stdout.lower() or "demo_run" in result.stdout.lower()

    def test_demo_run_in_main_help(self):
        """demo-run appears in main help."""
        result = subprocess.run(
            [sys.executable, "-m", "bremen", "--help"],
            capture_output=True, text=True,
        )
        assert "demo-run" in result.stdout.lower() or "demo_run" in result.stdout.lower()

    def test_demo_run_help_shows_options(self, _cli_result_cache):
        """demo-run --help shows --base-url and --timeout options."""
        result = _cli_result_cache("-m", "bremen", "demo-run", "--help")
        assert "--base-url" in result.stdout or "--base_url" in result.stdout
        assert "--timeout" in result.stdout

    def test_demo_run_pretty_flag_accepted(self, _cli_result_cache):
        """demo-run --help shows --pretty flag."""
        result = _cli_result_cache("-m", "bremen", "demo-run", "--help")
        assert "--pretty" in result.stdout

    def test_demo_run_cli_skip_prediction(self):
        """demo-run --help shows --skip-prediction flag."""
        result = subprocess.run(
            [sys.executable, "-m", "bremen", "demo-run", "--help"],
            capture_output=True, text=True,
        )
        assert "--skip-prediction" in result.stdout


# ===================================================================
# Output shape validation (direct, no server)
# ===================================================================


class TestOutputShape:
    def test_run_demo_output_has_expected_keys(self):
        """run_demo() output dict contains all expected keys."""
        from bremen.demo_run import run_demo
        from bremen.api.model_state import ModelState

        ModelState.reset_for_tests()
        # Call with unreachable URL — should return fail with expected shape
        result = run_demo(
            base_url="http://127.0.0.1:1",
            timeout=2,
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

    def test_unavailable_service_returns_fail(self):
        """run_demo with unreachable base URL returns fail."""
        from bremen.demo_run import run_demo

        result = run_demo(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        assert result["status"] == "fail"
        assert len(result["warnings"]) > 0

    def test_technical_demo_only_field(self):
        """technical_demo_only field is present and true."""
        from bremen.demo_run import run_demo

        result = run_demo(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        assert result["technical_demo_only"] is True

    def test_request_id_present(self):
        """Output contains a request_id string."""
        from bremen.demo_run import run_demo

        result = run_demo(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        assert isinstance(result["request_id"], str)
        assert len(result["request_id"]) > 0

    def test_prediction_not_available_when_skipped(self):
        """When skip_prediction=True, prediction status is not_available."""
        from bremen.demo_run import run_demo

        result = run_demo(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        assert result["prediction"]["status"] == "not_available"

    def test_output_is_json_serializable(self):
        """Output can be serialized to JSON."""
        from bremen.demo_run import run_demo

        result = run_demo(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        serialized = json.dumps(result)
        assert isinstance(serialized, str)
        assert len(serialized) > 0
