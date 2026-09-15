"""No duplicate active scientific implementations (PR0156 search test).

Guards the deduplication rule: each scientific concern has exactly one
authoritative active implementation in production source.  Compatibility shims
are re-export-only (no def/class bodies) so they hold no second copy.

Test/reference implementations (tests/reference_0151) and offline training
(bremen.training) are explicitly out of scope and allowed to keep evidence.
"""
from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).parents[1] / "src" / "bremen"

# The single authoritative definitions expected for each scientific symbol.
# Paths are relative to src/bremen (the search root).
AUTHORITATIVE_DEFINITIONS = {
    "build_bremen_features": {"model_packages/bremen_v01/features.py"},
    "predict_proba_portable": {"model_packages/bremen_v01/predictor.py"},
    "validate_bremen_shape": {"model_packages/bremen_v01/features.py"},
    "symmetry_features": {"model_packages/aramina_v0213/symmetry.py"},
    "preprocess_aramina": {"model_packages/aramina_v0213/preprocessing.py"},
    "ensure_compatibility_bridge": {
        "model_packages/aramina_v0213/artifact_compat.py",
    },
    "load_staged_artifact": {"model_packages_bridge.py"},
}

OFFLINE_PREFIXES = ("training/",)


def _relative(path: Path) -> str:
    return str(path.relative_to(SRC))


def _function_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
    }


def test_single_authoritative_scientific_definitions():
    found: dict[str, set[str]] = {k: set() for k in AUTHORITATIVE_DEFINITIONS}
    for path in SRC.rglob("*.py"):
        rel = _relative(path)
        if any(rel.startswith(p) for p in OFFLINE_PREFIXES):
            continue
        names = _function_names(path)
        for target, homes in AUTHORITATIVE_DEFINITIONS.items():
            if target in names:
                found[target].add(rel)
    for target, homes in AUTHORITATIVE_DEFINITIONS.items():
        assert found[target] == homes, (
            f"duplicate/missing active definition for {target!r}: {found[target]!r}"
        )


def test_compatibility_shims_have_no_function_or_class_bodies():
    shims = [
        "bremen_features.py", "bremen_runtime.py", "inference.py",
        "api/aramina_preprocessing.py", "api/aramina_symmetry.py",
        "api/aramina_artifact_compat.py",
    ]
    for rel in shims:
        tree = ast.parse((SRC / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            assert not isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ), f"shim {rel} must contain no logic, found {type(node).__name__}"


def test_no_reverse_import_from_aramina_package_to_platform_workflow():
    forbidden = {
        "workflow_aramina", "workflow_bremen", "workflow_provider",
        "job_api_handler", "jobs", "report_aramina", "report_bremen",
        "report_provider", "fastapi_app", "auth", "source_registry",
        "model_state", "model_requirements",
    }
    for path in (SRC / "model_packages" / "aramina_v0213").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                leaf = (node.module or "").split(".")[-1]
                assert leaf not in forbidden, (
                    f"{path.name} reverse-imports platform orchestration {leaf}"
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    leaf = alias.name.split(".")[-1]
                    assert leaf not in forbidden, (
                        f"{path.name} reverse-imports platform orchestration {leaf}"
                    )


def test_no_reverse_import_from_bremen_package_to_platform_workflow():
    forbidden = {
        "workflow_bremen", "workflow_aramina", "workflow_provider",
        "job_api_handler", "jobs", "report_bremen", "report_aramina",
        "fastapi_app", "auth", "source_registry", "model_state",
        "model_requirements",
    }
    for path in (SRC / "model_packages" / "bremen_v01").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                leaf = (node.module or "").split(".")[-1]
                assert leaf not in forbidden, (
                    f"{path.name} reverse-imports platform orchestration {leaf}"
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    leaf = alias.name.split(".")[-1]
                    assert leaf not in forbidden, (
                        f"{path.name} reverse-imports platform orchestration {leaf}"
                    )
