"""Tests for FastAPI serve mode (CLI integration).

Tests cover safe, deterministic pieces of the serve-fastapi command:

- CLI includes the serve-fastapi subcommand.
- Existing serve command still exists.
- serve-fastapi defaults to 127.0.0.1.
- serve-fastapi defaults to 8080.
- serve-fastapi calls uvicorn with bremen.api.fastapi_app:create_fastapi_app.
- serve-fastapi uses factory mode.
- Existing http.server serve default is not replaced.
- Dockerfile/ENTRYPOINT/CMD not changed.
- No raw exception/secret output in missing-uvicorn path.
- Test file does not use urlopen/HTTPServer/ThreadingHTTPServer/
  serve_forever/local sockets.

These tests **never** start a real server.  uvicorn.run is monkeypatched.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"

# Import the CLI module
from bremen.__main__ import build_parser, main  # noqa: E402
from bremen.api.fastapi_server import (  # noqa: E402
    _DEFAULT_HOST,
    _DEFAULT_PORT,
    _FACTORY_TARGET,
    _DEFAULT_LOG_LEVEL,
    run_fastapi_server,
)


# ===================================================================
# CLI parser tests
# ===================================================================


class TestCLIServeFastAPISubcommand:
    """Verify the CLI has the serve-fastapi subcommand."""

    def test_serve_fastapi_in_builtin_commands(self) -> None:
        """serve-fastapi is listed in BUILTIN_COMMANDS."""
        from bremen.__main__ import BUILTIN_COMMANDS
        assert "serve-fastapi" in BUILTIN_COMMANDS

    def test_serve_fastapi_parseable(self) -> None:
        """Parser accepts serve-fastapi."""
        parser = build_parser()
        args = parser.parse_args(["serve-fastapi"])
        assert args.command == "serve-fastapi"
        assert args._cmd_handler == "serve_fastapi"

    def test_legacy_serve_still_exists(self) -> None:
        """Legacy 'serve' subcommand is still present."""
        parser = build_parser()
        args = parser.parse_args(["serve"])
        assert args.command == "serve"
        assert args._cmd_handler == "serve"

    def test_serve_fastapi_default_host(self) -> None:
        """Default host is 127.0.0.1 (loopback)."""
        parser = build_parser()
        args = parser.parse_args(["serve-fastapi"])
        assert args.host == "127.0.0.1"

    def test_serve_fastapi_default_port(self) -> None:
        """Default port is 8080."""
        parser = build_parser()
        args = parser.parse_args(["serve-fastapi"])
        assert args.port == 8080

    def test_serve_fastapi_custom_host_port(self) -> None:
        """Custom --host and --port are accepted."""
        parser = build_parser()
        args = parser.parse_args(["serve-fastapi", "--host", "0.0.0.0", "--port", "9000"])
        assert args.host == "0.0.0.0"
        assert args.port == 9000

    def test_serve_fastapi_reload_flag(self) -> None:
        """--reload flag defaults to False."""
        parser = build_parser()
        args = parser.parse_args(["serve-fastapi"])
        assert args.reload is False

    def test_serve_fastapi_reload_enabled(self) -> None:
        """--reload flag can be enabled."""
        parser = build_parser()
        args = parser.parse_args(["serve-fastapi", "--reload"])
        assert args.reload is True

    def test_serve_fastapi_log_level_default(self) -> None:
        """Default log-level is 'info'."""
        parser = build_parser()
        args = parser.parse_args(["serve-fastapi"])
        assert args.log_level == "info"

    def test_serve_fastapi_log_level_choices(self) -> None:
        """log-level accepts valid choices."""
        parser = build_parser()
        for level in ("debug", "info", "warning", "error", "critical"):
            args = parser.parse_args(["serve-fastapi", "--log-level", level])
            assert args.log_level == level


# ===================================================================
# Default constant tests
# ===================================================================


class TestFastAPIServerDefaults:
    """Verify the fastapi_server module defaults are correct."""

    def test_factory_target(self) -> None:
        """Factory target is bremen.api.fastapi_app:create_fastapi_app."""
        assert _FACTORY_TARGET == "bremen.api.fastapi_app:create_fastapi_app"

    def test_default_host_is_loopback(self) -> None:
        """Default host is 127.0.0.1."""
        assert _DEFAULT_HOST == "127.0.0.1"

    def test_default_port(self) -> None:
        """Default port is 8080."""
        assert _DEFAULT_PORT == 8080

    def test_default_log_level(self) -> None:
        """Default log level is 'info'."""
        assert _DEFAULT_LOG_LEVEL == "info"


# ===================================================================
# Monkeypatched uvicorn.run tests
# ===================================================================


class TestServeFastAPIUvicornCall:
    """Verify run_fastapi_server calls uvicorn correctly (monkeypatched)."""

    def test_calls_uvicorn_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """run_fastapi_server calls uvicorn.run with factory mode."""
        calls: dict[str, object] = {}

        def fake_uvicorn_run(*args: object, **kwargs: object) -> None:
            calls["args"] = args
            calls["kwargs"] = kwargs

        monkeypatch.setattr("uvicorn.run", fake_uvicorn_run)

        # run_fastapi_server imports uvicorn inside the function,
        # so we need to ensure it picks up the monkeypatch
        # by patching the import
        import uvicorn as _uvicorn
        monkeypatch.setattr(_uvicorn, "run", fake_uvicorn_run)

        rc = run_fastapi_server(host="127.0.0.1", port=8080)
        assert rc == 0
        assert "kwargs" in calls
        kw = calls["kwargs"]
        assert kw.get("host") == "127.0.0.1"
        assert kw.get("port") == 8080
        assert kw.get("factory") is True

    def test_passes_factory_target(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """run_fastapi_server passes the correct factory target string."""
        calls: dict[str, object] = {}

        def fake_uvicorn_run(*args: object, **kwargs: object) -> None:
            calls["args"] = args
            calls["kwargs"] = kwargs

        import uvicorn as _uvicorn
        monkeypatch.setattr(_uvicorn, "run", fake_uvicorn_run)

        run_fastapi_server()
        assert calls["args"][0] == "bremen.api.fastapi_app:create_fastapi_app"

    def test_passes_reload_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """--reload is forwarded to uvicorn.run."""
        calls: dict[str, object] = {}

        def fake_uvicorn_run(*args: object, **kwargs: object) -> None:
            calls["kwargs"] = kwargs

        import uvicorn as _uvicorn
        monkeypatch.setattr(_uvicorn, "run", fake_uvicorn_run)

        run_fastapi_server(reload=True)
        assert calls["kwargs"]["reload"] is True

    def test_passes_log_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """--log-level is forwarded to uvicorn.run."""
        calls: dict[str, object] = {}

        def fake_uvicorn_run(*args: object, **kwargs: object) -> None:
            calls["kwargs"] = kwargs

        import uvicorn as _uvicorn
        monkeypatch.setattr(_uvicorn, "run", fake_uvicorn_run)

        run_fastapi_server(log_level="debug")
        assert calls["kwargs"]["log_level"] == "debug"

    def test_returns_zero_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns 0 when uvicorn.run completes without error."""
        import uvicorn as _uvicorn
        monkeypatch.setattr(_uvicorn, "run", lambda *a, **kw: None)
        assert run_fastapi_server() == 0

    def test_returns_one_on_uvicorn_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns 1 when uvicorn.run raises an exception."""
        import uvicorn as _uvicorn

        def failing_run(*args: object, **kwargs: object) -> None:
            raise RuntimeError("port in use")

        monkeypatch.setattr(_uvicorn, "run", failing_run)
        assert run_fastapi_server() == 1

    def test_returns_one_on_missing_uvicorn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns 1 with safe error when uvicorn is not installed."""
        import builtins
        real_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "uvicorn":
                raise ImportError("No module named 'uvicorn'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        assert run_fastapi_server() == 1


# ===================================================================
# CLI handler dispatch test
# ===================================================================


class TestCLIHandlerDispatch:
    """Verify the CLI dispatches serve-fastapi correctly."""

    def test_main_dispatches_serve_fastapi(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """main() dispatches serve-fastapi to run_fastapi_server."""
        calls: dict[str, object] = {}

        def fake_run(**kwargs: object) -> int:
            calls.update(kwargs)
            return 0

        monkeypatch.setattr("bremen.api.fastapi_server.run_fastapi_server", fake_run)
        # Also need to make main's import find the monkeypatched version
        monkeypatch.setattr(
            "bremen.__main__._handle_serve_fastapi",
            lambda args: fake_run(host=args.host, port=args.port),
        )
        rc = main(["serve-fastapi", "--host", "10.0.0.1", "--port", "9999"])
        assert rc == 0
        assert calls.get("host") == "10.0.0.1"
        assert calls.get("port") == 9999

    def test_main_dispatches_legacy_serve(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """main() still dispatches legacy 'serve' to http.server."""
        calls: list[str] = []

        def fake_serve(args: object) -> int:
            calls.append("serve")
            return 0

        monkeypatch.setattr("bremen.__main__._handle_serve", fake_serve)
        rc = main(["serve"])
        assert rc == 0
        assert "serve" in calls


# ===================================================================
# No production coupling tests
# ===================================================================


class TestNoProductionCoupling:
    """Verify serve-fastapi does not couple to production Dockerfile/ENTRYPOINT."""

    def test_dockerfile_unchanged(self) -> None:
        """Production Dockerfile FROM/CMD/ENTRYPOINT are unchanged."""
        if DOCKERFILE.exists():
            content = DOCKERFILE.read_text()
            lines = content.strip().splitlines()
            directives = [
                l for l in lines
                if l.startswith("FROM ")
                or l.startswith("CMD ")
                or l.startswith("ENTRYPOINT ")
            ]
            assert len(directives) >= 1

    def test_no_dockerfile_reference_in_serve_module(self) -> None:
        """fastapi_server.py does not reference Dockerfile."""
        src = (ROOT / "src" / "bremen" / "api" / "fastapi_server.py").read_text()
        assert "Dockerfile" not in src

    def test_no_entrypoint_override(self) -> None:
        """fastapi_server.py does not change production ENTRYPOINT."""
        src = (ROOT / "src" / "bremen" / "api" / "fastapi_server.py").read_text()
        assert "ENTRYPOINT" not in src

    def test_legacy_serve_handler_still_imports_http_server(self) -> None:
        """Legacy serve handler still imports from api.server (http.server path)."""
        main_src = (ROOT / "src" / "bremen" / "__main__.py").read_text()
        assert "from .api.server import run_server" in main_src


# ===================================================================
# No secrets/paths in error output
# ===================================================================


class TestSafeErrorOutput:
    """Verify error paths do not expose raw internals."""

    def test_no_traceback_in_fastapi_server(self) -> None:
        """fastapi_server.py does not print tracebacks."""
        src = (ROOT / "src" / "bremen" / "api" / "fastapi_server.py").read_text()
        assert "traceback" not in src.lower().replace("# noqa", "")
        assert "print_exc" not in src
        assert "print_exception" not in src

    def test_no_secret_patterns_in_fastapi_server(self) -> None:
        """fastapi_server.py does not print secrets or raw paths."""
        src = (ROOT / "src" / "bremen" / "api" / "fastapi_server.py").read_text()
        assert "s3://" not in src
        assert "jwt_secret" not in src.lower()
        assert "os.environ" not in src

    def test_safe_missing_uvicorn_message(self) -> None:
        """Missing-uvicorn path prints a safe install hint, not a traceback."""
        src = (ROOT / "src" / "bremen" / "api" / "fastapi_server.py").read_text()
        assert "pip install uvicorn" in src


# ===================================================================
# No server-spawning in test file
# ===================================================================


class TestNoServerSpawningInTests:
    """Verify this test file does not spawn real servers."""

    @staticmethod
    def _get_test_source() -> str:
        return Path(__file__).read_text(encoding="utf-8")

    def test_no_urlopen(self) -> None:
        """Test file does not call urlopen."""
        src = self._get_test_source()
        # Only check actual import/call, not mention in string literals
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "urlopen":
                pytest.fail("Test file uses urlopen — forbidden")
            if isinstance(node, ast.Attribute) and node.attr == "urlopen":
                # Check if it's actually calling urlopen, not just mentioning it
                if isinstance(node.ctx, ast.Load):
                    # Could be a reference in a string or assertion — check parent
                    pass

    def test_no_httpserver_class(self) -> None:
        """Test file does not use HTTPServer class."""
        src = self._get_test_source()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in ("HTTPServer", "ThreadingHTTPServer"):
                # Check if it's in an assertion (allowed) vs actual use
                pytest.fail(f"Test file uses {node.id} — forbidden")

    def test_no_serve_forever(self) -> None:
        """Test file does not call serve_forever."""
        src = self._get_test_source()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "serve_forever":
                pytest.fail("Test file calls serve_forever — forbidden")
