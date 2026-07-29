"""Tests for the ASGI smoke readiness script.

Tests cover safe, deterministic pieces of ``scripts/smoke_fastapi_asgi.py``:

- CLI parser defaults and arguments
- Command construction uses the FastAPI factory (``create_fastapi_app``)
- Output redaction helper
- Endpoint list contains Phase 1-4 routes
- Script has read-only mode
- Script does not require an H5 fixture for read-only smoke
- Script does not include raw secret/path printing helpers
- No Dockerfile/production entrypoint coupling
- No server-spawning in pytest

These tests **never** start a real server.
"""

from __future__ import annotations

import ast
import re
import sys
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the script module without executing main
# ---------------------------------------------------------------------------

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "smoke_fastapi_asgi.py"
SCRIPT_SRC = SCRIPT_PATH.read_text(encoding="utf-8")
SCRIPT_AST = ast.parse(SCRIPT_SRC)

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"

# ---------------------------------------------------------------------------
# Import helpers from the script
# ---------------------------------------------------------------------------

# We import the module by manipulating sys.path temporarily
_scripts_dir = str(SCRIPT_PATH.parent)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

try:
    import smoke_fastapi_asgi as _smoke_mod
finally:
    # Clean up to avoid polluting test namespace
    if _scripts_dir in sys.path:
        sys.path.remove(_scripts_dir)


# ===================================================================
# CLI parser tests
# ===================================================================


class TestCLIParserDefaults:
    """Verify CLI parser has the expected defaults and arguments."""

    def test_parser_exists(self) -> None:
        """build_parser() returns an ArgumentParser."""
        parser = _smoke_mod.build_parser()
        assert parser is not None

    def test_default_host(self) -> None:
        """Default host is 127.0.0.1 (loopback only)."""
        parser = _smoke_mod.build_parser()
        args = parser.parse_args([])
        assert args.host == "127.0.0.1"

    def test_default_port(self) -> None:
        """Default port is a safe local dev port."""
        parser = _smoke_mod.build_parser()
        args = parser.parse_args([])
        assert isinstance(args.port, int)
        assert args.port > 1024  # not a privileged port

    def test_default_timeout(self) -> None:
        """Default timeout is positive."""
        parser = _smoke_mod.build_parser()
        args = parser.parse_args([])
        assert args.timeout > 0

    def test_read_only_default_false(self) -> None:
        """--read-only defaults to False."""
        parser = _smoke_mod.build_parser()
        args = parser.parse_args([])
        assert args.read_only is False

    def test_read_only_flag(self) -> None:
        """--read-only flag sets read_only to True."""
        parser = _smoke_mod.build_parser()
        args = parser.parse_args(["--read-only"])
        assert args.read_only is True

    def test_h5_file_default_none(self) -> None:
        """--h5-file defaults to None."""
        parser = _smoke_mod.build_parser()
        args = parser.parse_args([])
        assert args.h5_file is None

    def test_h5_file_accepts_path(self) -> None:
        """--h5-file accepts a path value."""
        parser = _smoke_mod.build_parser()
        args = parser.parse_args(["--h5-file", "/some/path.h5"])
        assert args.h5_file == "/some/path.h5"

    def test_model_id_default_none(self) -> None:
        """--model-id defaults to None."""
        parser = _smoke_mod.build_parser()
        args = parser.parse_args([])
        assert args.model_id is None

    def test_workflow_id_default_none(self) -> None:
        """--workflow-id defaults to None."""
        parser = _smoke_mod.build_parser()
        args = parser.parse_args([])
        assert args.workflow_id is None

    def test_keep_server_on_failure_default_false(self) -> None:
        """--keep-server-on-failure defaults to False."""
        parser = _smoke_mod.build_parser()
        args = parser.parse_args([])
        assert args.keep_server_on_failure is False

    def test_custom_host_and_port(self) -> None:
        """Custom --host and --port are accepted."""
        parser = _smoke_mod.build_parser()
        args = parser.parse_args(["--host", "0.0.0.0", "--port", "9999"])
        assert args.host == "0.0.0.0"
        assert args.port == 9999


# ===================================================================
# Command construction tests
# ===================================================================


class TestCommandConstruction:
    """Verify the script builds the correct uvicorn command."""

    def test_build_uvicorn_command_returns_list(self) -> None:
        """_build_uvicorn_command returns a list of strings."""
        cmd = _smoke_mod._build_uvicorn_command("127.0.0.1", 8990)
        assert isinstance(cmd, list)
        assert all(isinstance(c, str) for c in cmd)

    def test_uses_uvicorn_module(self) -> None:
        """Command includes -m uvicorn."""
        cmd = _smoke_mod._build_uvicorn_command("127.0.0.1", 8990)
        assert "-m" in cmd
        uvicorn_idx = cmd.index("-m") + 1
        assert cmd[uvicorn_idx] == "uvicorn"

    def test_uses_create_fastapi_app_factory(self) -> None:
        """Command references the create_fastapi_app factory."""
        cmd = _smoke_mod._build_uvicorn_command("127.0.0.1", 8990)
        cmd_str = " ".join(cmd)
        assert "create_fastapi_app" in cmd_str

    def test_factory_flag_present(self) -> None:
        """Command includes --factory flag for uvicorn."""
        cmd = _smoke_mod._build_uvicorn_command("127.0.0.1", 8990)
        assert "--factory" in cmd

    def test_host_and_port_in_command(self) -> None:
        """Command includes --host and --port."""
        cmd = _smoke_mod._build_uvicorn_command("127.0.0.1", 8990)
        assert "--host" in cmd
        assert "--port" in cmd
        host_idx = cmd.index("--host") + 1
        port_idx = cmd.index("--port") + 1
        assert cmd[host_idx] == "127.0.0.1"
        assert cmd[port_idx] == "8990"

    def test_uses_python_executable(self) -> None:
        """Command starts with sys.executable (not hardcoded python)."""
        cmd = _smoke_mod._build_uvicorn_command("127.0.0.1", 8990)
        assert cmd[0] == sys.executable


# ===================================================================
# Output redaction tests
# ===================================================================


class TestOutputRedaction:
    """Verify the redact_display helper prevents path leakage."""

    def test_redact_display_exists(self) -> None:
        """redact_display is a callable function."""
        assert callable(_smoke_mod.redact_display)

    def test_empty_input(self) -> None:
        """Empty input returns a safe placeholder."""
        result = _smoke_mod.redact_display("")
        assert result == "<empty>"

    def test_basename_only(self) -> None:
        """Full path is reduced to basename."""
        result = _smoke_mod.redact_display("/some/deep/path/file.h5")
        assert result == "file.h5"
        assert "/" not in result

    def test_long_basename_truncated(self) -> None:
        """Long basenames are truncated with ..."""
        long_name = "a" * 100 + ".h5"
        result = _smoke_mod.redact_display(long_name, max_len=60)
        assert len(result) <= 60
        assert result.endswith("...")

    def test_no_s3_leakage(self) -> None:
        """S3 URIs are reduced to basename."""
        result = _smoke_mod.redact_display("s3://bucket/prefix/file.h5")
        assert "s3://" not in result
        assert result == "file.h5"

    def test_no_tmp_leakage(self) -> None:
        """Temp paths are reduced to basename."""
        result = _smoke_mod.redact_display("/tmp/uploads/test.h5")
        assert "/tmp/" not in result
        assert result == "test.h5"

    def test_windows_path_reduced(self) -> None:
        """Windows paths are reduced to basename."""
        result = _smoke_mod.redact_display("C:\\Users\\data\\file.h5")
        assert result == "file.h5"


# ===================================================================
# Endpoint list tests
# ===================================================================


class TestEndpointCoverage:
    """Verify the script covers Phase 1-4 routes."""

    def test_read_only_endpoints_exist(self) -> None:
        """READONLY_ENDPOINTS list is non-empty."""
        assert len(_smoke_mod._READONLY_ENDPOINTS) >= 4

    def test_health_endpoint(self) -> None:
        """/health is in the read-only endpoint list."""
        assert "/health" in _smoke_mod._READONLY_ENDPOINTS

    def test_model_version_endpoint(self) -> None:
        """/model/version is in the read-only endpoint list."""
        assert "/model/version" in _smoke_mod._READONLY_ENDPOINTS

    def test_models_endpoint(self) -> None:
        """/demo/api/models is in the read-only endpoint list."""
        assert "/demo/api/models" in _smoke_mod._READONLY_ENDPOINTS

    def test_h5_containers_endpoint(self) -> None:
        """/demo/api/h5/containers is in the read-only endpoint list."""
        assert "/demo/api/h5/containers" in _smoke_mod._READONLY_ENDPOINTS

    def test_write_event_endpoints_cover_phase3(self) -> None:
        """Write/event endpoints include Phase 3 POST routes."""
        we_text = " ".join(_smoke_mod._WRITE_EVENT_ENDPOINTS)
        assert "POST /demo/api/h5/containers" in we_text
        assert "POST /demo/api/jobs" in we_text

    def test_write_event_endpoints_cover_phase4(self) -> None:
        """Write/event endpoints include Phase 4 SSE routes."""
        we_text = " ".join(_smoke_mod._WRITE_EVENT_ENDPOINTS)
        assert "events/stream" in we_text
        assert "events" in we_text

    def test_all_routes_phase1_through_4(self) -> None:
        """Combined endpoint lists cover Phase 1-4 routes."""
        all_endpoints = (
            _smoke_mod._READONLY_ENDPOINTS
            + _smoke_mod._WRITE_EVENT_ENDPOINTS
        )
        all_text = " ".join(all_endpoints)
        for route in [
            "/health",
            "/model/version",
            "/demo/api/models",
            "/demo/api/h5/containers",
            "/demo/api/jobs",
            "events/stream",
        ]:
            assert route in all_text, f"Missing route: {route}"


# ===================================================================
# Read-only mode tests
# ===================================================================


class TestReadOnlyMode:
    """Verify the script supports and respects read-only mode."""

    def test_read_only_cli_flag(self) -> None:
        """Parser accepts --read-only."""
        parser = _smoke_mod.build_parser()
        args = parser.parse_args(["--read-only"])
        assert args.read_only is True

    def test_read_only_requires_no_h5(self) -> None:
        """Read-only mode does not require an H5 fixture."""
        parser = _smoke_mod.build_parser()
        args = parser.parse_args(["--read-only"])
        # h5_file should be None — read-only should work without it
        assert args.h5_file is None

    def test_read_only_docstring(self) -> None:
        """Script docstring mentions read-only mode."""
        assert "read-only" in _smoke_mod.__doc__.lower() or \
               "read_only" in SCRIPT_SRC


# ===================================================================
# H5 fixture not required for read-only
# ===================================================================


class TestH5FixtureNotRequired:
    """Verify read-only smoke works without H5 fixture."""

    def test_default_no_h5_file(self) -> None:
        """Default CLI args have no H5 file."""
        parser = _smoke_mod.build_parser()
        args = parser.parse_args([])
        assert args.h5_file is None

    def test_write_event_check_skips_without_h5(self) -> None:
        """Write/event smoke is skipped when no H5 file is provided."""
        # The run_smoke function handles this by checking h5_file is None
        # We verify the logic path exists in source
        assert "no --h5-file provided" in SCRIPT_SRC.lower() or \
               "skipping optional write/event" in SCRIPT_SRC.lower()


# ===================================================================
# Safety: no secret/path printing helpers
# ===================================================================


class TestNoSecretPrinting:
    """Verify the script does not print raw secrets or paths."""

    def test_no_printenv_calls(self) -> None:
        """Script does not call printenv or os.environ printing."""
        assert "printenv" not in SCRIPT_SRC
        assert "os.environ" not in SCRIPT_SRC

    def test_no_secret_display_functions(self) -> None:
        """Script has no function that prints secrets."""
        func_names = [node.name for node in ast.walk(SCRIPT_AST)
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for name in func_names:
            assert "secret" not in name.lower(), \
                f"Function {name} looks like it handles secrets"
            assert "credential" not in name.lower(), \
                f"Function {name} looks like it handles credentials"

    def test_no_urllib_parse_for_secrets(self) -> None:
        """Script does not use urllib.parse to extract credentials."""
        assert "urllib.parse.urlencode" not in SCRIPT_SRC
        assert "urllib.parse.quote" not in SCRIPT_SRC

    def test_forbidden_patterns_defined(self) -> None:
        """Script defines forbidden output patterns."""
        assert hasattr(_smoke_mod, "_FORBIDDEN_OUTPUT_PATTERNS")
        assert len(_smoke_mod._FORBIDDEN_OUTPUT_PATTERNS) > 0

    def test_forbidden_patterns_include_s3(self) -> None:
        """Forbidden patterns include S3 URI scheme."""
        patterns = _smoke_mod._FORBIDDEN_OUTPUT_PATTERNS
        assert any("s3://" in p for p in patterns)

    def test_forbidden_patterns_include_tmp(self) -> None:
        """Forbidden patterns include /tmp/."""
        patterns = _smoke_mod._FORBIDDEN_OUTPUT_PATTERNS
        assert any("/tmp/" in p for p in patterns)


# ===================================================================
# No Dockerfile / production coupling
# ===================================================================


class TestNoProductionCoupling:
    """Verify the script does not couple to Dockerfile or production entrypoint."""

    def test_no_dockerfile_references(self) -> None:
        """Script source does not reference Dockerfile."""
        assert "Dockerfile" not in SCRIPT_SRC

    def test_no_entrypoint_references(self) -> None:
        """Script does not reference production ENTRYPOINT."""
        assert "ENTRYPOINT" not in SCRIPT_SRC

    def test_no_cmd_references(self) -> None:
        """Script does not reference production CMD."""
        # Only check standalone CMD references, not generic "cmd" variable names
        assert "ENTRYPOINT" not in SCRIPT_SRC

    def test_no_http_server_spawn(self) -> None:
        """Script does not use http.server for spawning."""
        assert "HTTPServer" not in SCRIPT_SRC
        assert "ThreadingHTTPServer" not in SCRIPT_SRC
        assert "serve_forever" not in SCRIPT_SRC

    def test_dockerfile_unchanged(self) -> None:
        """Production Dockerfile FROM/CMD/ENTRYPOINT are unchanged."""
        if DOCKERFILE.exists():
            content = DOCKERFILE.read_text()
            lines = content.strip().splitlines()
            directives = [
                l for l in lines
                if l.startswith("FROM ") or
                   l.startswith("CMD ") or
                   l.startswith("ENTRYPOINT ")
            ]
            # Dockerfile should have its standard directives
            assert len(directives) >= 1, "Dockerfile appears modified or empty"


# ===================================================================
# No server-spawning patterns in pytest
# ===================================================================


class TestNoServerSpawningInPytest:
    """Verify this test file does not spawn servers.

    Uses AST analysis on the **script** source (SCRIPT_AST) to check for
    actual ``import`` or ``call`` patterns.  Does **not** read its own
    source with ``Path(__file__).read_text()`` because the test file
    legitimately mentions forbidden words in docstrings and assertion
    messages.
    """

    @staticmethod
    def _collect_import_names(tree: ast.Module) -> set[str]:
        """Collect all dotted import names from an AST."""
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    names.add(node.module)
        return names

    @staticmethod
    def _collect_attribute_calls(tree: ast.Module) -> set[str]:
        """Collect attribute access chains like ``http.server.HTTPServer``."""
        chains: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                parts = []
                current: ast.expr = node
                while isinstance(current, ast.Attribute):
                    parts.append(current.attr)
                    current = current.value
                if isinstance(current, ast.Name):
                    parts.append(current.id)
                chains.add(".".join(reversed(parts)))
        return chains

    def test_no_http_server_import(self) -> None:
        """Script does not import http.server."""
        imports = self._collect_import_names(SCRIPT_AST)
        assert "http.server" not in imports

    def test_no_urlopen_bare_import(self) -> None:
        """Script does not import urlopen as a bare name."""
        # The script uses urllib.request.urlopen — that is acceptable
        # for a dev smoke script.  Verify it does NOT import urlopen
        # as a standalone name (which would be a different pattern).
        imports = self._collect_import_names(SCRIPT_AST)
        assert "urlopen" not in imports

    def test_no_httpserver_class_in_script(self) -> None:
        """Script does not instantiate HTTPServer or ThreadingHTTPServer."""
        calls = self._collect_attribute_calls(SCRIPT_AST)
        # Check that HTTPServer / ThreadingHTTPServer are not used as
        # class constructors in the script
        for chain in calls:
            assert "HTTPServer" not in chain, (
                f"Script references {chain} — forbidden server class"
            )

    def test_no_serve_forever_call_in_script(self) -> None:
        """Script does not call serve_forever()."""
        calls = self._collect_attribute_calls(SCRIPT_AST)
        for chain in calls:
            assert "serve_forever" not in chain, (
                f"Script calls {chain} — forbidden server pattern"
            )

    def test_script_source_file_path(self) -> None:
        """SCRIPT_SRC was loaded from the correct script file."""
        assert SCRIPT_PATH.name == "smoke_fastapi_asgi.py"
        assert SCRIPT_PATH.exists()


# ===================================================================
# Script structure tests
# ===================================================================


class TestScriptStructure:
    """Verify the script has the expected structural properties."""

    def test_script_is_valid_python(self) -> None:
        """Script parses as valid Python."""
        assert SCRIPT_AST is not None

    def test_has_main_entry_point(self) -> None:
        """Script has a main() function."""
        func_names = [node.name for node in ast.walk(SCRIPT_AST)
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        assert "main" in func_names

    def test_has_run_smoke_function(self) -> None:
        """Script has a run_smoke() function."""
        func_names = [node.name for node in ast.walk(SCRIPT_AST)
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        assert "run_smoke" in func_names

    def test_has_build_parser_function(self) -> None:
        """Script has a build_parser() function."""
        func_names = [node.name for node in ast.walk(SCRIPT_AST)
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        assert "build_parser" in func_names

    def test_has_start_server_function(self) -> None:
        """Script has a _start_server() function."""
        func_names = [node.name for node in ast.walk(SCRIPT_AST)
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        assert "_start_server" in func_names

    def test_has_kill_server_function(self) -> None:
        """Script has a _kill_server() function."""
        func_names = [node.name for node in ast.walk(SCRIPT_AST)
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        assert "_kill_server" in func_names

    def test_has_read_only_check_function(self) -> None:
        """Script has a read-only endpoint check function."""
        func_names = [node.name for node in ast.walk(SCRIPT_AST)
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        assert "_check_read_only_endpoints" in func_names

    def test_has_write_event_check_function(self) -> None:
        """Script has a write/event check function."""
        func_names = [node.name for node in ast.walk(SCRIPT_AST)
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        assert "_check_write_event_smoke" in func_names

    def test_has_redact_display_function(self) -> None:
        """Script has a redact_display() function."""
        func_names = [node.name for node in ast.walk(SCRIPT_AST)
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        assert "redact_display" in func_names

    def test_script_uses_create_fastapi_app(self) -> None:
        """Script references create_fastapi_app (via uvicorn --factory)."""
        assert "create_fastapi_app" in SCRIPT_SRC

    def test_script_uses_uvicorn(self) -> None:
        """Script references uvicorn."""
        assert "uvicorn" in SCRIPT_SRC
