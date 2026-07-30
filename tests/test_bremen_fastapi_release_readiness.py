"""Tests for FastAPI release readiness checks.

Covers the logic in scripts/check_fastapi_release_readiness.py without
starting any servers, making network calls, or using sockets.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bremen.__main__ import build_parser, resolve_backend

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_fastapi_release_readiness.py"
DOCKERFILE = ROOT / "Dockerfile"
GUARD_FILE = ROOT / "tests" / "test_bremen_no_server_spawning_tests.py"


class TestResolverDefaults:
    """Verify the resolver reflects the production cutover."""

    def test_default_is_fastapi(self) -> None:
        assert resolve_backend(None, None) == "fastapi"

    def test_cli_http_overrides_default(self) -> None:
        assert resolve_backend("http", None) == "http"

    def test_cli_fastapi_explicit(self) -> None:
        assert resolve_backend("fastapi", None) == "fastapi"

    def test_env_http_overrides_default(self) -> None:
        assert resolve_backend(None, "http") == "http"

    def test_cli_overrides_env(self) -> None:
        assert resolve_backend("http", "fastapi") == "http"

    def test_invalid_fails(self) -> None:
        with pytest.raises(ValueError, match="Invalid backend"):
            resolve_backend("grpc", None)


class TestParserDefaults:
    """Verify parser reflects the production cutover."""

    def test_serve_default_backend_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve"])
        assert args.backend is None

    def test_serve_fastapi_parseable(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve-fastapi"])
        assert args.command == "serve-fastapi"
        assert args._cmd_handler == "serve_fastapi"

    def test_serve_http_backend_parseable(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve", "--backend", "http"])
        assert args.backend == "http"

    def test_serve_fastapi_backend_parseable(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve", "--backend", "fastapi"])
        assert args.backend == "fastapi"


class TestFactoryTarget:
    """FastAPI factory target must be correct."""

    def test_factory_target(self) -> None:
        from bremen.api.fastapi_server import _FACTORY_TARGET

        assert _FACTORY_TARGET == "bremen.api.fastapi_app:create_fastapi_app"


class TestGuardFileExists:
    """Zero-server guard must exist."""

    def test_guard_exists(self) -> None:
        assert GUARD_FILE.exists()


class TestScriptExists:
    """Release readiness script must exist."""

    def test_script_exists(self) -> None:
        assert SCRIPT.exists()

    def test_script_compiles(self) -> None:
        """Script must be valid Python."""
        import py_compile

        py_compile.compile(str(SCRIPT), doraise=True)


class TestDockerfileDoesNotForceLegacy:
    """Dockerfile must not force --backend http."""

    def test_dockerfile_no_legacy_override(self) -> None:
        if not DOCKERFILE.exists():
            pytest.skip("No Dockerfile")

        content = DOCKERFILE.read_text(encoding="utf-8")
        assert "--backend http" not in content


class TestLegacyImportable:
    """Legacy http.server path must remain importable."""

    def test_legacy_run_server_importable(self) -> None:
        from bremen.api.server import run_server

        assert callable(run_server)


class TestFastAPIImportable:
    """FastAPI serving path must be importable."""

    def test_fastapi_run_server_importable(self) -> None:
        from bremen.api.fastapi_server import run_fastapi_server

        assert callable(run_fastapi_server)


class TestNoServerSpawningInScript:
    """AST check: the readiness script must not spawn servers."""
    """AST check: the readiness script must not spawn servers."""

    def test_no_http_server_in_script(self) -> None:
        if not SCRIPT.exists():
            pytest.skip("Script not present")

        import ast

        source = SCRIPT.read_text(encoding="utf-8")
        tree = ast.parse(source)

        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Name):
                    name = func.id
                elif isinstance(func, ast.Attribute):
                    name = func.attr
                if name in ("HTTPServer", "ThreadingHTTPServer", "serve_forever"):
                    violations.append(name)

        assert not violations, f"Server-spawning calls found: {violations}"

    def test_no_socket_in_script(self) -> None:
        if not SCRIPT.exists():
            pytest.skip("Script not present")

        import ast

        source = SCRIPT.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "socket", "Script imports socket"
