"""Fast tests for the unified Bremen CLI entrypoint.

Covers:
- ``python -m bremen`` exits 0 and prints Bremen help
- One real stub invocation preserves the subprocess exit-code contract
- Main, stub, demo-run, and serve parser contracts
- No active Aramis identity in help output
- ``__main__.py`` has no heavy top-level imports

Most checks load ``src/bremen/__main__.py`` directly by file path. This avoids
executing ``bremen/__init__.py`` and importing the ML/preprocessing stack for
every assertion. Two subprocess smoke tests retain end-to-end coverage of the
real ``python -m bremen`` entrypoint.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[1]
SRC = ROOT / "src"
MAIN_PATH = SRC / "bremen" / "__main__.py"

STUB_COMMANDS = ("preflight", "run", "report")
REQUIRED_COMMANDS = (
    "preprocess",
    *STUB_COMMANDS,
    "serve",
    "demo-run",
)


@pytest.fixture(scope="module")
def cli_module() -> ModuleType:
    """Load ``__main__.py`` without importing the ``bremen`` package."""
    spec = importlib.util.spec_from_file_location(
        "_bremen_cli_entrypoint_under_test",
        MAIN_PATH,
    )
    if spec is None or spec.loader is None:
        pytest.fail(f"Could not load CLI module from {MAIN_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def parser(cli_module: ModuleType) -> argparse.ArgumentParser:
    """Build one reusable parser for all in-process contract checks."""
    return cli_module.build_parser()


def _subcommand_names(parser: argparse.ArgumentParser) -> tuple[str, ...]:
    """Return the command names registered on an argparse parser."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return tuple(action.choices)

    pytest.fail("Bremen CLI parser has no subcommands")


def _run_bremen(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the current checkout as a real child process.

    ``src`` is prepended to ``PYTHONPATH`` so the child cannot accidentally
    execute a stale non-editable installation from site-packages.
    """
    env = os.environ.copy()
    src_path = str(SRC)
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{src_path}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else src_path
    )

    return subprocess.run(
        [sys.executable, "-m", "bremen", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _help_output(
    parser: argparse.ArgumentParser,
    capsys: pytest.CaptureFixture[str],
    *args: str,
) -> str:
    """Return argparse help output without spawning another Python process."""
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args([*args, "--help"])

    assert exc_info.value.code == 0
    return capsys.readouterr().out


# ---------------------------------------------------------------------------
# Real process smoke tests
# ---------------------------------------------------------------------------


def test_python_m_bremen_no_args_smoke(parser: argparse.ArgumentParser):
    """The real module entrypoint exits 0 and matches the local parser."""
    result = _run_bremen()

    assert result.returncode == 0, (
        f"Exit code {result.returncode}: {result.stderr}"
    )
    assert "Bremen" in result.stdout
    assert "Not a diagnostic" in result.stdout
    assert "replacement" in result.stdout

    for command in _subcommand_names(parser):
        assert command in result.stdout, (
            f"No-arg help output must list local command {command!r}"
        )

    assert "aramis" not in result.stdout.lower()


def test_python_m_bremen_stub_smoke():
    """One real stub invocation preserves exit code and output behavior."""
    result = _run_bremen("preflight")

    assert result.returncode == 1, (
        f"Exit code {result.returncode}, expected 1: {result.stderr}"
    )
    assert "not yet implemented" in result.stdout
    assert "Planned for a future PR." in result.stdout


# ---------------------------------------------------------------------------
# Main parser contract
# ---------------------------------------------------------------------------


def test_main_help_contract(parser: argparse.ArgumentParser):
    """Main parser help contains product identity and required commands."""
    output = parser.format_help()

    assert "Bremen" in output
    assert "Not a diagnostic" in output
    assert "replacement" in output

    for command in REQUIRED_COMMANDS:
        assert command in output, (
            f"Main help output must list required command {command!r}"
        )

    assert "aramis" not in output.lower()


# ---------------------------------------------------------------------------
# Stub command contracts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", STUB_COMMANDS)
def test_stub_help_exits_0(
    parser: argparse.ArgumentParser,
    capsys: pytest.CaptureFixture[str],
    command: str,
):
    """Every stub command exposes working argparse help."""
    output = _help_output(parser, capsys, command)

    assert f"bremen {command}" in output


@pytest.mark.parametrize("command", STUB_COMMANDS)
def test_stub_invocation_contract(
    parser: argparse.ArgumentParser,
    cli_module: ModuleType,
    capsys: pytest.CaptureFixture[str],
    command: str,
):
    """Every stub resolves to the shared deferred-command handler."""
    args = parser.parse_args([command])

    assert args._cmd_handler == "stub"
    assert args._stub_name == command

    returncode = cli_module._handle_stub(args)
    output = capsys.readouterr().out

    assert returncode == 1
    assert f"'{command}' is not yet implemented." in output
    assert "Planned for a future PR." in output


# ---------------------------------------------------------------------------
# Real subcommand help contracts
# ---------------------------------------------------------------------------


def test_demo_run_help_contract(
    parser: argparse.ArgumentParser,
    capsys: pytest.CaptureFixture[str],
):
    """demo-run exposes all supported command-line options."""
    output = _help_output(parser, capsys, "demo-run")

    for option in (
        "--base-url",
        "--timeout",
        "--skip-prediction",
        "--pretty",
        "--capture-dir",
    ):
        assert option in output, (
            f"demo-run --help must list {option!r}"
        )


def test_serve_help_contract(
    parser: argparse.ArgumentParser,
    capsys: pytest.CaptureFixture[str],
):
    """serve exposes host and port options."""
    output = _help_output(parser, capsys, "serve")

    assert "--host" in output
    assert "--port" in output


# ---------------------------------------------------------------------------
# Static import-safety guard
# ---------------------------------------------------------------------------


def _top_level_imports(path: Path) -> set[str]:
    """Return imports declared directly in a module body."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()

    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
            continue

        if not isinstance(node, ast.ImportFrom):
            continue

        module = node.module or ""
        prefix = "." * node.level
        base = f"{prefix}{module}"

        if base:
            imports.add(base)

        for alias in node.names:
            if alias.name == "*":
                continue
            imports.add(f"{base}.{alias.name}" if base else alias.name)

    return imports


@pytest.mark.parametrize(
    "forbidden",
    (
        "xrd_preprocessing",
        "pipelines",
        "modeling",
        "mlflow_tracking",
    ),
)
def test_cli_has_no_heavy_top_level_imports(forbidden: str):
    """``__main__.py`` must defer heavy imports to command handlers."""
    imports = _top_level_imports(MAIN_PATH)

    offenders = sorted(
        imported
        for imported in imports
        if forbidden in imported.lstrip(".").split(".")
    )

    assert not offenders, (
        f"__main__.py must not import {forbidden!r} at top level; "
        f"found: {offenders}"
    )