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

from bremen.__main__ import BUILTIN_COMMANDS, build_parser
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
