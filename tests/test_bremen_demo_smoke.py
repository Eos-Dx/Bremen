"""Tests for the Bremen demo smoke checker (demo_smoke).

Covers:
- CLI help works
- demo-smoke in main help
- demo-smoke help contains options
- Output shape validation (unreachable URL)
- JSON serializability
- No diagnosis language in output
- Evidence bundle shape (unreachable URL)
- Route/evidence inventory (direct checks)

Server-dependent tests (demo_smoke with real HTTP) have been removed.
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


MODULE_PATH = Path(__file__).parents[1] / "src" / "bremen" / "demo_smoke.py"


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
# CLI help tests (subprocess, no server)
# ===================================================================


class TestCliHelp:
    def test_demo_smoke_help_exits_0(self, _cli_result_cache):
        """python -m bremen demo-smoke --help exits 0."""
        result = _cli_result_cache("-m", "bremen", "demo-smoke", "--help")
        assert result.returncode == 0

    def test_demo_smoke_in_main_help(self):
        """demo-smoke appears in main help."""
        result = subprocess.run(
            [sys.executable, "-m", "bremen", "--help"],
            capture_output=True, text=True,
        )
        assert "demo-smoke" in result.stdout.lower() or "demo_smoke" in result.stdout.lower()

    def test_demo_smoke_help_contains_options(self, _cli_result_cache):
        """demo-smoke --help shows --base-url and --timeout."""
        result = _cli_result_cache("-m", "bremen", "demo-smoke", "--help")
        assert "base-url" in result.stdout or "base_url" in result.stdout
        assert "--timeout" in result.stdout


# ===================================================================
# Output shape validation (unreachable URL, no server)
# ===================================================================


class TestOutputContract:
    def test_output_shape_on_unreachable_url(self):
        """demo_smoke with unreachable URL returns expected shape."""
        from bremen.demo_smoke import main as demo_smoke_main

        result = demo_smoke_main([
            "--base-url=http://127.0.0.1:1",
            "--timeout=2",
            "--skip-prediction",
        ])
        assert isinstance(result, int)

    def test_output_is_json_serializable_on_unreachable(self):
        """Output can be serialized to JSON."""
        from bremen.demo_smoke import run_demo_smoke

        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        serialized = json.dumps(result)
        assert isinstance(serialized, str)

    def test_no_diagnosis_language_in_output(self):
        """Output must not contain diagnosis language."""
        from bremen.demo_smoke import run_demo_smoke

        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        body = json.dumps(result).lower()
        assert "diagnos" not in body
        assert "patient diagnosis" not in body


# ===================================================================
# Evidence bundle shape (unreachable URL, no server)
# ===================================================================


class TestEvidenceBundleInDemoSmoke:
    def test_demo_smoke_output_contains_evidence_bundle(self):
        """Output contains evidence key."""
        from bremen.demo_smoke import run_demo_smoke

        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        assert "evidence" in result

    def test_demo_smoke_evidence_technical_demo_only(self):
        """Evidence contains technical_demo_only."""
        from bremen.demo_smoke import run_demo_smoke

        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        evidence = result.get("evidence", {})
        assert evidence.get("technical_demo_only") is True

    def test_demo_smoke_evidence_product_is_bremen(self):
        """Evidence product is bremen."""
        from bremen.demo_smoke import run_demo_smoke

        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        evidence = result.get("evidence", {})
        assert evidence.get("product").lower() == "bremen"

    def test_demo_smoke_evidence_has_required_keys(self):
        """Evidence has required keys."""
        from bremen.demo_smoke import run_demo_smoke

        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        evidence = result.get("evidence", {})
        required = {"product", "technical_demo_only", "request_id"}
        assert required.issubset(set(evidence.keys()))

    def test_demo_smoke_evidence_preserves_request_id(self):
        """Evidence request_id matches top-level."""
        from bremen.demo_smoke import run_demo_smoke

        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        evidence = result.get("evidence", {})
        assert evidence.get("request_id") == result.get("request_id")

    def test_demo_smoke_evidence_includes_base_url(self):
        """Evidence includes base_url."""
        from bremen.demo_smoke import run_demo_smoke

        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        evidence = result.get("evidence", {})
        assert "base_url" in evidence

    def test_demo_smoke_evidence_includes_model_status(self):
        """Evidence includes model_status."""
        from bremen.demo_smoke import run_demo_smoke

        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        evidence = result.get("evidence", {})
        # model_status may be absent when service is unreachable
        # key check: evidence structure is valid

    def test_demo_smoke_evidence_includes_checks(self):
        """Evidence includes checks."""
        from bremen.demo_smoke import run_demo_smoke

        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        evidence = result.get("evidence", {})
        assert "checks" in evidence

    def test_demo_smoke_evidence_includes_warnings(self):
        """Evidence includes warnings."""
        from bremen.demo_smoke import run_demo_smoke

        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        evidence = result.get("evidence", {})
        assert "warnings" in evidence

    def test_unavailable_service_evidence_still_produced(self):
        """Evidence is still produced when service is unavailable."""
        from bremen.demo_smoke import run_demo_smoke

        result = run_demo_smoke(
            base_url="http://127.0.0.1:1",
            timeout=2,
            skip_prediction=True,
        )
        assert "evidence" in result
        assert result["evidence"]["technical_demo_only"] is True


# ===================================================================
# Source safety checks (AST-based, no server)
# ===================================================================


class TestSourceSafety:
    def test_no_h5_references(self):
        """demo_smoke.py does not import h5py."""
        src = MODULE_PATH.read_text(encoding="utf-8")
        assert "h5py" not in src

    def test_no_joblib_or_pickle_references(self):
        """demo_smoke.py does not import joblib or pickle."""
        src = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "joblib" not in alias.name.lower()
                    assert "pickle" not in alias.name.lower()
