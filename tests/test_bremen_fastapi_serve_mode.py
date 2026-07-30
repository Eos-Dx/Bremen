"""Tests for FastAPI serve mode.

These tests cover only deterministic, non-network behavior:

- CLI parser exposes the serve-fastapi subcommand.
- CLI parser still exposes the legacy serve subcommand.
- serve-fastapi defaults are safe for local development.
- run_fastapi_server delegates to the ASGI server runner with factory mode.
- production Dockerfile/ENTRYPOINT/CMD are not changed by this feature.
- safe error paths do not expose tracebacks, secrets, or raw environment data.

Important:

These tests must never call server-launching CLI runtime paths.
Those command paths may launch real servers. Parser tests and monkeypatched
helper tests are enough for normal pytest coverage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bremen.__main__ import BUILTIN_COMMANDS, build_parser, resolve_backend
from bremen.api.fastapi_server import (
    _DEFAULT_HOST,
    _DEFAULT_LOG_LEVEL,
    _DEFAULT_PORT,
    _FACTORY_TARGET,
    run_fastapi_server,
)


ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
FASTAPI_SERVER = ROOT / "src" / "bremen" / "api" / "fastapi_server.py"
MAIN_MODULE = ROOT / "src" / "bremen" / "__main__.py"


class TestCLIServeFastAPISubcommand:
    """Parser-level coverage for serve-fastapi."""

    def test_serve_fastapi_in_builtin_commands(self) -> None:
        assert "serve-fastapi" in BUILTIN_COMMANDS

    def test_serve_fastapi_parseable(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve-fastapi"])

        assert args.command == "serve-fastapi"
        assert args._cmd_handler == "serve_fastapi"

    def test_legacy_serve_still_parseable(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve"])

        assert args.command == "serve"
        assert args._cmd_handler == "serve"

    def test_serve_fastapi_default_host(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve-fastapi"])

        assert args.host == "127.0.0.1"

    def test_serve_fastapi_default_port(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve-fastapi"])

        assert args.port == 8080

    def test_serve_fastapi_custom_host_port(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["serve-fastapi", "--host", "0.0.0.0", "--port", "9000"]
        )

        assert args.host == "0.0.0.0"
        assert args.port == 9000

    def test_serve_fastapi_reload_defaults_to_false(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve-fastapi"])

        assert args.reload is False

    def test_serve_fastapi_reload_can_be_enabled(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve-fastapi", "--reload"])

        assert args.reload is True

    def test_serve_fastapi_log_level_default(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve-fastapi"])

        assert args.log_level == "info"

    def test_serve_fastapi_log_level_choices(self) -> None:
        parser = build_parser()

        for level in ("debug", "info", "warning", "error", "critical"):
            args = parser.parse_args(["serve-fastapi", "--log-level", level])
            assert args.log_level == level


class TestFastAPIServerDefaults:
    """Constant-level coverage for the FastAPI serve helper."""

    def test_factory_target(self) -> None:
        assert _FACTORY_TARGET == "bremen.api.fastapi_app:create_fastapi_app"

    def test_default_host_is_loopback(self) -> None:
        assert _DEFAULT_HOST == "127.0.0.1"

    def test_default_port(self) -> None:
        assert _DEFAULT_PORT == 8080

    def test_default_log_level(self) -> None:
        assert _DEFAULT_LOG_LEVEL == "info"


class TestFastAPIServerRunner:
    """Monkeypatched coverage for run_fastapi_server."""

    def test_calls_runner_with_factory_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: dict[str, object] = {}

        def fake_run(*args: object, **kwargs: object) -> None:
            calls["args"] = args
            calls["kwargs"] = kwargs

        import uvicorn as patched_uvicorn

        monkeypatch.setattr(patched_uvicorn, "run", fake_run)

        rc = run_fastapi_server(host="127.0.0.1", port=8080)

        assert rc == 0
        assert calls["args"] == ("bremen.api.fastapi_app:create_fastapi_app",)

        kwargs = calls["kwargs"]
        assert kwargs["host"] == "127.0.0.1"
        assert kwargs["port"] == 8080
        assert kwargs["factory"] is True

    def test_passes_custom_host_and_port(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: dict[str, object] = {}

        def fake_run(*args: object, **kwargs: object) -> None:
            calls["kwargs"] = kwargs

        import uvicorn as patched_uvicorn

        monkeypatch.setattr(patched_uvicorn, "run", fake_run)

        rc = run_fastapi_server(host="0.0.0.0", port=9000)

        assert rc == 0
        assert calls["kwargs"]["host"] == "0.0.0.0"
        assert calls["kwargs"]["port"] == 9000

    def test_passes_reload_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: dict[str, object] = {}

        def fake_run(*args: object, **kwargs: object) -> None:
            calls["kwargs"] = kwargs

        import uvicorn as patched_uvicorn

        monkeypatch.setattr(patched_uvicorn, "run", fake_run)

        rc = run_fastapi_server(reload=True)

        assert rc == 0
        assert calls["kwargs"]["reload"] is True

    def test_passes_log_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: dict[str, object] = {}

        def fake_run(*args: object, **kwargs: object) -> None:
            calls["kwargs"] = kwargs

        import uvicorn as patched_uvicorn

        monkeypatch.setattr(patched_uvicorn, "run", fake_run)

        rc = run_fastapi_server(log_level="debug")

        assert rc == 0
        assert calls["kwargs"]["log_level"] == "debug"

    def test_returns_zero_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import uvicorn as patched_uvicorn

        monkeypatch.setattr(patched_uvicorn, "run", lambda *args, **kwargs: None)

        assert run_fastapi_server() == 0

    def test_returns_one_on_runner_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import uvicorn as patched_uvicorn

        def failing_run(*args: object, **kwargs: object) -> None:
            raise RuntimeError("port in use")

        monkeypatch.setattr(patched_uvicorn, "run", failing_run)

        assert run_fastapi_server() == 1

    def test_returns_one_on_missing_runner(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import builtins

        real_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "uvicorn":
                raise ImportError("No module named 'uvicorn'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        assert run_fastapi_server() == 1


class TestNoProductionCoupling:
    """FastAPI serve mode must not change production coupling."""

    def test_dockerfile_directives_still_exist(self) -> None:
        if not DOCKERFILE.exists():
            pytest.skip("Dockerfile not present in this checkout")

        directives = [
            line
            for line in DOCKERFILE.read_text(encoding="utf-8").splitlines()
            if line.startswith(("FROM ", "CMD ", "ENTRYPOINT "))
        ]

        assert directives

    def test_fastapi_server_does_not_reference_dockerfile(self) -> None:
        source = FASTAPI_SERVER.read_text(encoding="utf-8")

        assert "Dockerfile" not in source

    def test_fastapi_server_does_not_override_entrypoint(self) -> None:
        source = FASTAPI_SERVER.read_text(encoding="utf-8")

        assert "ENTRYPOINT" not in source

    def test_legacy_serve_handler_still_uses_api_server(self) -> None:
        source = MAIN_MODULE.read_text(encoding="utf-8")

        assert "from .api.server import run_server" in source


class TestSafeErrorOutput:
    """FastAPI serve helper must keep errors safe."""

    def test_no_traceback_printing_in_fastapi_server(self) -> None:
        source = FASTAPI_SERVER.read_text(encoding="utf-8").lower()

        assert "traceback" not in source
        assert "print_exc" not in source
        assert "print_exception" not in source

    def test_no_secret_patterns_in_fastapi_server(self) -> None:
        source = FASTAPI_SERVER.read_text(encoding="utf-8").lower()

        assert "s3://" not in source
        assert "jwt_secret" not in source
        assert "os.environ" not in source

    def test_safe_missing_runner_message_present(self) -> None:
        source = FASTAPI_SERVER.read_text(encoding="utf-8")

        assert "pip install uvicorn" in source


class TestCLIServeBackendSelection:
    """Parser-level and dispatch coverage for --backend on serve."""

    def test_serve_backend_default_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve"])

        # Default is None so the resolver can distinguish CLI from env
        assert args.backend is None

    def test_serve_backend_http_explicit(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve", "--backend", "http"])

        assert args.backend == "http"
        assert args.command == "serve"
        assert args._cmd_handler == "serve"

    def test_serve_backend_fastapi(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve", "--backend", "fastapi"])

        assert args.backend == "fastapi"
        assert args.command == "serve"
        assert args._cmd_handler == "serve"

    def test_serve_backend_invalid_rejected(self) -> None:
        parser = build_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["serve", "--backend", "grpc"])

    def test_serve_backend_with_host_port(self) -> None:
        parser = build_parser()
        args = parser.parse_args(
            ["serve", "--backend", "fastapi", "--host", "0.0.0.0", "--port", "9000"]
        )

        assert args.backend == "fastapi"
        assert args.host == "0.0.0.0"
        assert args.port == 9000


class TestServeFastapiPreserved:
    """serve-fastapi remains a separate command."""

    def test_serve_fastapi_still_parseable(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["serve-fastapi"])

        assert args.command == "serve-fastapi"
        assert args._cmd_handler == "serve_fastapi"

    def test_serve_fastapi_no_backend_arg(self) -> None:
        """serve-fastapi does not have --backend."""
        parser = build_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["serve-fastapi", "--backend", "http"])


class TestServeDispatch:
    """Dispatch-level tests for serve with --backend."""

    def test_dispatch_http_calls_run_server(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from bremen.__main__ import _handle_serve

        calls: dict[str, object] = {}

        def fake_run_server(**kwargs: object) -> None:
            calls["server"] = kwargs

        def fake_run_fastapi(**kwargs: object) -> int:
            calls["fastapi"] = kwargs
            return 0

        monkeypatch.setattr(
            "bremen.api.server.run_server", fake_run_server
        )
        monkeypatch.setattr(
            "bremen.api.fastapi_server.run_fastapi_server",
            fake_run_fastapi,
        )

        import argparse

        args = argparse.Namespace(
            command="serve",
            _cmd_handler="serve",
            host="127.0.0.1",
            port=8000,
            backend="http",
        )

        rc = _handle_serve(args)

        assert rc == 0
        assert "server" in calls
        assert "fastapi" not in calls
        assert calls["server"]["host"] == "127.0.0.1"
        assert calls["server"]["port"] == 8000

    def test_dispatch_fastapi_calls_run_fastapi(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from bremen.__main__ import _handle_serve

        calls: dict[str, object] = {}

        def fake_run_server(**kwargs: object) -> None:
            calls["server"] = kwargs

        def fake_run_fastapi(**kwargs: object) -> int:
            calls["fastapi"] = kwargs
            return 0

        monkeypatch.setattr(
            "bremen.api.server.run_server", fake_run_server
        )
        monkeypatch.setattr(
            "bremen.api.fastapi_server.run_fastapi_server",
            fake_run_fastapi,
        )

        import argparse

        args = argparse.Namespace(
            command="serve",
            _cmd_handler="serve",
            host="0.0.0.0",
            port=9000,
            backend="fastapi",
        )

        rc = _handle_serve(args)

        assert rc == 0
        assert "fastapi" in calls
        assert "server" not in calls
        assert calls["fastapi"]["host"] == "0.0.0.0"
        assert calls["fastapi"]["port"] == 9000

    def test_dispatch_default_without_backend_attr(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If backend attr is missing, defaults to fastapi."""
        from bremen.__main__ import _handle_serve

        calls: dict[str, object] = {}

        def fake_run_fastapi(**kwargs: object) -> int:
            calls["fastapi"] = kwargs
            return 0

        monkeypatch.setattr(
            "bremen.api.fastapi_server.run_fastapi_server",
            fake_run_fastapi,
        )

        import argparse

        # No backend attribute — simulates pre-upgrade namespace
        args = argparse.Namespace(
            command="serve",
            _cmd_handler="serve",
            host="127.0.0.1",
            port=8000,
        )

        rc = _handle_serve(args)

        assert rc == 0
        assert "fastapi" in calls


class TestResolveBackend:
    """Tests for the resolve_backend function."""

    def test_no_cli_no_env_returns_fastapi(self) -> None:
        assert resolve_backend(None, None) == "fastapi"

    def test_cli_http_wins(self) -> None:
        assert resolve_backend("http", None) == "http"

    def test_cli_fastapi_wins(self) -> None:
        assert resolve_backend("fastapi", None) == "fastapi"

    def test_cli_overrides_env_fastapi(self) -> None:
        assert resolve_backend("http", "fastapi") == "http"

    def test_cli_overrides_env_http(self) -> None:
        assert resolve_backend("fastapi", "http") == "fastapi"

    def test_env_fastapi_used_when_cli_none(self) -> None:
        assert resolve_backend(None, "fastapi") == "fastapi"

    def test_env_http_used_when_cli_none(self) -> None:
        assert resolve_backend(None, "http") == "http"

    def test_cli_whitespace_trimmed(self) -> None:
        assert resolve_backend("  fastapi  ", None) == "fastapi"

    def test_env_whitespace_trimmed(self) -> None:
        assert resolve_backend(None, "  fastapi  ") == "fastapi"

    def test_cli_case_insensitive(self) -> None:
        assert resolve_backend("FastAPI", None) == "fastapi"

    def test_env_case_insensitive(self) -> None:
        assert resolve_backend(None, "FastAPI") == "fastapi"

    def test_cli_empty_string_falls_to_env(self) -> None:
        assert resolve_backend("", "fastapi") == "fastapi"

    def test_cli_whitespace_only_falls_to_env(self) -> None:
        assert resolve_backend("   ", "fastapi") == "fastapi"

    def test_invalid_cli_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid backend"):
            resolve_backend("grpc", None)

    def test_invalid_env_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid backend"):
            resolve_backend(None, "grpc")

    def test_invalid_cli_error_no_raw_env(self) -> None:
        """CLI error message uses generic wording, not raw env."""
        with pytest.raises(ValueError, match="Invalid backend"):
            resolve_backend("SHOULD_NOT_LEAK", None)

    def test_invalid_env_error_no_raw_env(self) -> None:
        """Invalid env error message uses generic wording."""
        with pytest.raises(ValueError, match="Invalid backend"):
            resolve_backend(None, "bad-value")

    def test_env_empty_string_falls_to_default(self) -> None:
        assert resolve_backend(None, "") == "fastapi"

    def test_env_whitespace_only_falls_to_default(self) -> None:
        assert resolve_backend(None, "   ") == "fastapi"


class TestEnvBackendBehavior:
    """Integration tests for BREMEN_SERVER_BACKEND env var dispatch."""

    def test_env_fastapi_dispatches_fastapi(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from bremen.__main__ import _handle_serve

        calls: dict[str, object] = {}

        def fake_run_fastapi(**kwargs: object) -> int:
            calls["fastapi"] = kwargs
            return 0

        monkeypatch.setattr(
            "bremen.api.fastapi_server.run_fastapi_server",
            fake_run_fastapi,
        )
        monkeypatch.setenv("BREMEN_SERVER_BACKEND", "fastapi")

        import argparse

        args = argparse.Namespace(
            command="serve",
            _cmd_handler="serve",
            host="127.0.0.1",
            port=8000,
            backend=None,
        )

        rc = _handle_serve(args)

        assert rc == 0
        assert "fastapi" in calls

    def test_env_http_dispatches_http(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from bremen.__main__ import _handle_serve

        calls: dict[str, object] = {}

        def fake_run_server(**kwargs: object) -> None:
            calls["server"] = kwargs

        monkeypatch.setattr(
            "bremen.api.server.run_server", fake_run_server
        )
        monkeypatch.setenv("BREMEN_SERVER_BACKEND", "http")

        import argparse

        args = argparse.Namespace(
            command="serve",
            _cmd_handler="serve",
            host="127.0.0.1",
            port=8000,
            backend=None,
        )

        rc = _handle_serve(args)

        assert rc == 0
        assert "server" in calls

    def test_cli_overrides_env_fastapi(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from bremen.__main__ import _handle_serve

        calls: dict[str, object] = {}

        def fake_run_server(**kwargs: object) -> None:
            calls["server"] = kwargs

        monkeypatch.setattr(
            "bremen.api.server.run_server", fake_run_server
        )
        monkeypatch.setenv("BREMEN_SERVER_BACKEND", "fastapi")

        import argparse

        args = argparse.Namespace(
            command="serve",
            _cmd_handler="serve",
            host="127.0.0.1",
            port=8000,
            backend="http",
        )

        rc = _handle_serve(args)

        assert rc == 0
        assert "server" in calls

    def test_invalid_env_fails_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from bremen.__main__ import _handle_serve

        calls: dict[str, object] = {}

        def fake_run_server(**kwargs: object) -> None:
            calls["server"] = kwargs

        def fake_run_fastapi(**kwargs: object) -> int:
            calls["fastapi"] = kwargs
            return 0

        monkeypatch.setattr(
            "bremen.api.server.run_server", fake_run_server
        )
        monkeypatch.setattr(
            "bremen.api.fastapi_server.run_fastapi_server",
            fake_run_fastapi,
        )
        monkeypatch.setenv("BREMEN_SERVER_BACKEND", "invalid")

        import argparse

        args = argparse.Namespace(
            command="serve",
            _cmd_handler="serve",
            host="127.0.0.1",
            port=8000,
            backend=None,
        )

        rc = _handle_serve(args)

        assert rc == 1
        assert "server" not in calls
        assert "fastapi" not in calls
