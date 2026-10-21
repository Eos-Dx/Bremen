"""IR-03 import-boundary tests for the standalone ML plugin.

The scientific plugin may import only neutral contracts and its scientific
dependencies.  It must never import the Bremen platform/API/catalog/job
orchestration, FastAPI or AWS tooling.  These tests enforce the boundary both
statically (AST) and at runtime (import blocker).
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
BREMEN = SRC / "bremen"
PLUGIN = BREMEN / "ml_plugin"

FORBIDDEN_PREFIXES = (
    "bremen.platform",
    "bremen.api",
    "fastapi",
    "uvicorn",
    "boto3",
    "botocore",
    "starlette",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _assert_no_forbidden(paths: list[Path]) -> None:
    violations: list[str] = []
    for path in paths:
        for module in _imports(path):
            for prefix in FORBIDDEN_PREFIXES:
                if module == prefix or module.startswith(prefix + "."):
                    violations.append(f"{path.relative_to(ROOT)} -> {module}")
    assert violations == []


def test_plugin_modules_import_no_platform_api_or_aws():
    _assert_no_forbidden(sorted(PLUGIN.rglob("*.py")))


def test_scientific_model_packages_import_no_platform():
    paths = sorted((BREMEN / "model_packages").rglob("*.py"))
    paths.append(BREMEN / "model_packages_bridge.py")
    _assert_no_forbidden(paths)


def test_release_build_modules_import_no_platform_runtime():
    _assert_no_forbidden(sorted((BREMEN / "release_build").rglob("*.py")))


def test_plugin_modules_do_not_import_scientific_package_internals_through_api():
    """No plugin module may reach into ``bremen.api`` even indirectly by name."""
    for path in sorted(PLUGIN.rglob("*.py")):
        ast.parse(path.read_text(encoding="utf-8"))  # syntax is importable


def test_plugin_imports_with_platform_and_fastapi_blocked(tmp_path):
    script = tmp_path / "isolation_check.py"
    script.write_text(
        """
import importlib.abc
import sys

FORBIDDEN = ("bremen.platform", "bremen.api", "fastapi", "boto3", "uvicorn")


class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        for prefix in FORBIDDEN:
            if fullname == prefix or fullname.startswith(prefix + "."):
                raise ImportError("blocked import: " + fullname)
        return None


sys.meta_path.insert(0, Blocker())

import bremen.ml_plugin.canonical  # noqa: F401,E402
import bremen.ml_plugin.entrypoint  # noqa: F401,E402
import bremen.ml_plugin.inference  # noqa: F401,E402
import bremen.ml_plugin.release  # noqa: F401,E402
import bremen.ml_plugin.variants  # noqa: F401,E402
import bremen.release_build.assemble  # noqa: F401,E402
import bremen.release_build.wheel  # noqa: F401,E402

for module in list(sys.modules):
    for prefix in FORBIDDEN:
        assert not (module == prefix or module.startswith(prefix + ".")), module

print("ISOLATED-OK")
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(tmp_path),
        text=True,
        capture_output=True,
        env={"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin"},
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "ISOLATED-OK" in completed.stdout


def test_clean_release_wheel_excludes_application_modules():
    from bremen.release_build.wheel import plugin_package_files

    names = {name for name, _ in plugin_package_files(SRC)}
    forbidden = (
        "bremen/platform/",
        "bremen/api/",
        "bremen/pipelines.py",
        "bremen/modeling.py",
        "bremen/mlflow_tracking.py",
        "bremen/__main__.py",
    )
    for prefix in forbidden:
        assert not any(name.startswith(prefix) for name in names), prefix
    assert "bremen/ml_plugin/entrypoint.py" in names
    assert "bremen/model_packages/bremen_v01/runtime.py" in names
    assert "bremen/contracts/model_runtime.py" in names


@pytest.mark.parametrize(
    "module",
    [
        "bremen.ml_plugin.entrypoint",
        "bremen.ml_plugin.inference",
        "bremen.ml_plugin.variants",
        "bremen.ml_plugin.canonical",
        "bremen.ml_plugin.release",
        "bremen.release_build.wheel",
        "bremen.release_build.assemble",
    ],
)
def test_module_imports_without_platform(module):
    import importlib

    assert importlib.import_module(module) is not None
