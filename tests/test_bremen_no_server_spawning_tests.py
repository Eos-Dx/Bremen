"""Guard test: ensure normal pytest files do not start real servers.

Scans all Python test files using AST analysis to detect actual
server-spawning code patterns (imports, instantiations, calls).
Does NOT match string literals, comments, or docstrings.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent


def _get_python_test_files() -> list[Path]:
    """Return all .py test files under tests/."""
    return sorted(TESTS_DIR.glob("test_bremen_*.py"))


def _has_server_spawning_patterns(filepath: Path) -> list[str]:
    """AST-analyze a file for server-spawning code patterns.

    Returns list of violation descriptions, empty if clean.
    """
    content = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    violations = []

    for node in ast.walk(tree):
        # Check imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == "http.server" or name.startswith("http.server."):
                    violations.append(f"imports {name}")
                if name == "socketserver":
                    violations.append(f"imports {name}")
                if name == "socket" or name.startswith("socket."):
                    violations.append(f"imports {name}")

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == "http.server" or module.startswith("http.server."):
                names = [a.name for a in node.names]
                violations.append(f"from {module} import {', '.join(names)}")
            if module == "socketserver":
                violations.append(f"from socketserver import ...")
            if module == "urllib.request":
                names = [a.name for a in node.names]
                if "urlopen" in names:
                    violations.append(f"from urllib.request import urlopen")
                if "Request" in names and "urlopen" in names:
                    violations.append(f"from urllib.request import urlopen, Request")

        # Check function calls
        elif isinstance(node, ast.Call):
            func = node.func
            # HTTPServer() or ThreadingHTTPServer() instantiation
            if isinstance(func, ast.Name):
                if func.id in ("HTTPServer", "ThreadingHTTPServer", "_ThreadingHTTPServer"):
                    violations.append(f"calls {func.id}()")
            elif isinstance(func, ast.Attribute):
                if func.attr in ("HTTPServer", "ThreadingHTTPServer", "_ThreadingHTTPServer"):
                    violations.append(f"calls {func.attr}()")
                # serve_forever()
                if func.attr == "serve_forever":
                    violations.append(f"calls serve_forever()")
                # urlopen()
                if func.attr == "urlopen":
                    violations.append(f"calls urlopen()")
            # _find_free_port()
            if isinstance(func, ast.Name) and func.id == "_find_free_port":
                violations.append(f"calls _find_free_port()")
            elif isinstance(func, ast.Attribute) and func.attr == "_find_free_port":
                violations.append(f"calls _find_free_port()")

    return violations


class TestNoServerSpawningInPytest:
    """Ensure test files do not start real servers (AST-based)."""

    @pytest.mark.parametrize(
        "test_file",
        _get_python_test_files(),
        ids=lambda p: p.name,
    )
    def test_no_server_spawning_code(self, test_file: Path) -> None:
        """Test file must not contain server-spawning code (AST-checked)."""
        violations = _has_server_spawning_patterns(test_file)
        if violations:
            pytest.fail(
                f"{test_file.name} has server-spawning code: "
                + "; ".join(violations)
            )
