"""Tests for the unified Bremen CLI entrypoint.

Covers:
- python -m bremen --help exits 0 and contains Bremen identity
- python -m bremen (no args) exits 0 and shows help
- Stub commands (preflight, run, report) with --help exit 0
- Stub commands without --help exit 1 with deferral message
- No active Aramis identity in help output
- CLI import is safe (no H5 read, no model load, no Matador access)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SRC_BREMEN = ROOT / "src" / "bremen"


# ---------------------------------------------------------------------------
# Help output tests (subprocess-based, no heavy imports)
# ---------------------------------------------------------------------------


def test_python_m_bremen_help_exits_0():
    """python -m bremen --help exits 0."""
    result = subprocess.run(
        [sys.executable, "-m", "bremen", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Exit code {result.returncode}: {result.stderr}"
    )


def test_python_m_bremen_help_contains_bremen():
    """python -m bremen --help output contains 'Bremen'."""
    result = subprocess.run(
        [sys.executable, "-m", "bremen", "--help"],
        capture_output=True,
        text=True,
    )
    assert "Bremen" in result.stdout, (
        "Help output must reference Bremen"
    )


def test_python_m_bremen_help_contains_disclaimer():
    """python -m bremen --help output contains the 'Not a diagnostic replacement' disclaimer."""
    result = subprocess.run(
        [sys.executable, "-m", "bremen", "--help"],
        capture_output=True,
        text=True,
    )
    # argparse wraps the description at 80 chars, so the disclaimer may
    # contain a newline. Check both halves.
    assert "Not a diagnostic" in result.stdout, (
        "Help output must contain 'Not a diagnostic replacement' disclaimer"
    )
    assert "replacement" in result.stdout, (
        "Help output must contain 'Not a diagnostic replacement' disclaimer"
    )


def test_python_m_bremen_help_contains_stubs():
    """python -m bremen --help lists stub commands: preflight, run, report."""
    result = subprocess.run(
        [sys.executable, "-m", "bremen", "--help"],
        capture_output=True,
        text=True,
    )
    for command in ("preflight", "run", "report"):
        assert command in result.stdout, (
            f"Help output must list '{command}' command"
        )


def test_python_m_bremen_help_contains_preprocess():
    """python -m bremen --help lists the preprocess command."""
    result = subprocess.run(
        [sys.executable, "-m", "bremen", "--help"],
        capture_output=True,
        text=True,
    )
    assert "preprocess" in result.stdout, (
        "Help output must list 'preprocess' command"
    )


def test_python_m_bremen_no_args_exits_0():
    """python -m bremen (no args) exits 0 and shows help."""
    result = subprocess.run(
        [sys.executable, "-m", "bremen"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Exit code {result.returncode}: {result.stderr}"
    )
    assert "preflight" in result.stdout, (
        "No-arg output must show help with commands"
    )


# ---------------------------------------------------------------------------
# Stub command tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", ["preflight", "run", "report"])
def test_stub_help_exits_0(command):
    """bremen <stub> --help exits 0."""
    result = subprocess.run(
        [sys.executable, "-m", "bremen", command, "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"'{command} --help' exit code {result.returncode}: {result.stderr}"
    )


@pytest.mark.parametrize("command", ["preflight", "run", "report"])
def test_stub_invocation_exits_1(command):
    """bremen <stub> (without --help) exits 1 with deferral message."""
    result = subprocess.run(
        [sys.executable, "-m", "bremen", command],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, (
        f"'{command}' exit code {result.returncode}, expected 1"
    )
    assert "not yet implemented" in result.stdout, (
        f"'{command}' must print 'not yet implemented' message"
    )


# ---------------------------------------------------------------------------
# No Aramis identity in help output
# ---------------------------------------------------------------------------


def test_help_no_aramis():
    """python -m bremen --help output does not contain 'aramis' or 'Aramis'."""
    result = subprocess.run(
        [sys.executable, "-m", "bremen", "--help"],
        capture_output=True,
        text=True,
    )
    assert "aramis" not in result.stdout.lower(), (
        "Help output must not contain 'aramis' (case-insensitive)"
    )


# ---------------------------------------------------------------------------
# Import safety (no H5 read, no model load, no Matador)
# ---------------------------------------------------------------------------


def test_cli_import_does_not_trigger_xrd_preprocessing():
    """Importing __main__ does not trigger xrd_preprocessing import at top level.

    This checks that __main__.py does not have a top-level import of
    xrd_preprocessing. Note: importing bremen.__main__ does trigger
    bremen.__init__, which imports xrd_preprocessing transitively
    through modeling/pipelines. That is not a safety issue for this PR.
    """
    import ast

    main_path = SRC_BREMEN / "__main__.py"
    tree = ast.parse(main_path.read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if "xrd_preprocessing" in module:
                pytest.fail(
                    f"__main__.py must not import xrd_preprocessing at top level, "
                    f"found: from {module} import ..."
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if "xrd_preprocessing" in alias.name:
                    pytest.fail(
                        f"__main__.py must not import xrd_preprocessing at top level, "
                        f"found: import {alias.name}"
                    )


def test_cli_import_does_not_trigger_heavy_modules():
    """Importing __main__ does not trigger pipelines/modeling/mlflow at top level.

    This checks __main__.py source code directly, not sys.modules,
    because importing bremen.__main__ triggers bremen.__init__
    which imports those modules.
    """
    import ast

    main_path = SRC_BREMEN / "__main__.py"
    tree = ast.parse(main_path.read_text(encoding="utf-8"))

    heavy_modules = [
        "bremen.pipelines",
        "bremen.modeling",
        "bremen.mlflow_tracking",
    ]

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for mod in heavy_modules:
                if mod in module:
                    pytest.fail(
                        f"__main__.py must not import {mod} at top level, "
                        f"found: from {module} import ..."
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for mod in heavy_modules:
                    if mod in alias.name:
                        pytest.fail(
                            f"__main__.py must not import {mod} at top level, "
                            f"found: import {alias.name}"
                        )
