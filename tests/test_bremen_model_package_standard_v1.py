"""Model Package Standard v1 conformance tests (PR0156).

Verifies the *semantic* package ownership standard against BOTH reference
packages (Bremen v0.1 and Aramina v0.2.13) without forcing identical internals
or file layouts.  For each package it asserts:

- the package exposes a Model Runtime Contract v1-compatible runtime entry
  point (``bremen.contracts.model_runtime.ModelRuntime``);
- requirements are available (model-declared input contract);
- validation is callable;
- prediction is callable;
- identity / provenance metadata exists (package manifest authoritative);
- the package never imports platform orchestration modules
  (workflow providers, jobs, FastAPI, reports, auth, source registry);
- the platform provider routes through the package runtime.

Scientific equality (golden probability, report parity, etc.) is asserted by
the dedicated direct-package suites
(``test_bremen_v01_package.py``, ``test_aramina_v0213_package.py``); this file
is about the boundary, not the numbers.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from bremen.contracts.model_runtime import (
    ModelInput,
    ModelRequirements,
    ModelRuntime,
    ModelValidation,
)
from tests.bremen_3x3_helpers import MODEL, make_case

SRC = Path(__file__).parents[1] / "src" / "bremen"
BREMEN_PKG = SRC / "model_packages" / "bremen_v01"
ARAMINA_PKG = SRC / "model_packages" / "aramina_v0213"

# Platform orchestration modules that NO model package may import.
FORBIDDEN_ORCHESTRATION = {
    "workflow_bremen", "workflow_aramina", "workflow_provider", "workflow_registry",
    "job_api_handler", "jobs", "fastapi_app", "fastapi_server", "fastapi_contracts",
    "report_bremen", "report_aramina", "report_provider", "auth", "source_registry",
    "model_state", "model_requirements", "event_store", "execution_context",
}


def _module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mods.add(("." * node.level) + (node.module or ""))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name)
    return mods


def _aramina_runtime():
    from bremen.model_packages.aramina_v0213.runtime import AraminaRuntime
    entry = SimpleNamespace(
        model_id="aramina-a", model_version="0.2.13-beta",
        feature_schema_version="v0.1",
    )
    return AraminaRuntime(entry=entry)


# ---------------------------------------------------------------------------
# Parametrized conformance matrix
# ---------------------------------------------------------------------------


@pytest.fixture
def bremen_runtime():
    from bremen.model_packages.bremen_v01.runtime import BremenRuntime
    return BremenRuntime(MODEL)


@pytest.fixture
def aramina_runtime():
    return _aramina_runtime()


RUNTIMES = ("bremen_runtime", "aramina_runtime")


@pytest.mark.parametrize("fixture_name", RUNTIMES)
def test_runtime_satisfies_contract(request, fixture_name):
    runtime = request.getfixturevalue(fixture_name)
    assert isinstance(runtime, ModelRuntime)


@pytest.mark.parametrize("fixture_name", RUNTIMES)
def test_requirements_available(request, fixture_name):
    runtime = request.getfixturevalue(fixture_name)
    req = runtime.model_requirements()
    assert isinstance(req, ModelRequirements)
    assert req.workflow_id in {"bremen", "aramina"}
    assert req.contract_version == "v1"
    # a real model declares SOME input contract
    assert req.request_fields


@pytest.mark.parametrize("fixture_name", RUNTIMES)
def test_validation_callable(request, fixture_name):
    runtime = request.getfixturevalue(fixture_name)
    if fixture_name == "bremen_runtime":
        out = runtime.validate_model_input(
            ModelInput(workflow_id="bremen", measurements=make_case().measurements),
        )
        assert isinstance(out, ModelValidation)
        assert out.compatible is True
    else:
        out = runtime.validate_model_input(
            ModelInput(workflow_id="aramina", canonical=SimpleNamespace(measurements=()),
                       patient_id="p1", target_side="left"),
        )
        assert isinstance(out, ModelValidation)


@pytest.mark.parametrize("fixture_name", RUNTIMES)
def test_prediction_callable(request, fixture_name):
    runtime = request.getfixturevalue(fixture_name)
    assert callable(runtime.predict_model)


@pytest.mark.parametrize("name,pkg", [("bremen", BREMEN_PKG), ("aramina", ARAMINA_PKG)])
def test_manifest_identity_provenance(name, pkg):
    from bremen.model_packages import bremen_v01, aramina_v0213
    module = bremen_v01.manifest if name == "bremen" else aramina_v0213.manifest
    assert module.WORKFLOW_ID == name
    assert module.MODEL_ID
    assert module.MODEL_VERSION
    assert module.FEATURE_SCHEMA_VERSION
    assert getattr(module, "RUNTIME_DEPENDENCIES")


@pytest.mark.parametrize("pkg", [BREMEN_PKG, ARAMINA_PKG])
def test_package_never_imports_orchestration(pkg):
    for path in sorted(pkg.glob("*.py")):
        for module in _module_imports(path):
            leaf = module.split(".")[-1]
            assert leaf not in FORBIDDEN_ORCHESTRATION, (
                f"{path.name} imports forbidden orchestration module {module!r}"
            )


@pytest.mark.parametrize(
    "provider_factory,runtime_class_path",
    [
        (
            lambda: _bremen_provider(),
            "bremen.model_packages.bremen_v01.runtime.BremenRuntime",
        ),
        (
            lambda: _aramina_provider(),
            "bremen.model_packages.aramina_v0213.runtime.AraminaRuntime",
        ),
    ],
)
def test_provider_routes_through_package_runtime(provider_factory, runtime_class_path):
    provider = provider_factory()
    runtime = provider.runtime
    assert isinstance(runtime, ModelRuntime)
    klass = type(runtime)
    full = f"{klass.__module__}.{klass.__name__}"
    assert full == runtime_class_path
    assert provider.runtime is runtime


def _bremen_provider():
    from bremen.platform.runtime.registry import bremen_descriptor
    return bremen_descriptor(model_package=MODEL)


def _aramina_provider():
    from bremen.platform.runtime.registry import aramina_descriptor
    entry = SimpleNamespace(
        model_id="aramina-a", model_version="0.2.13-beta",
        feature_schema_version="v0.1", artifact_type="aramina.joblib.model_package",
        _artifact_path="x", _checksum="", _clinical_stage="",
    )
    return aramina_descriptor(entry=entry)


# ---------------------------------------------------------------------------
# Structural: a model package exposes a documented entry point module
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("pkg", [BREMEN_PKG, ARAMINA_PKG])
def test_package_entry_point_module_has_runtime(pkg):
    entry = (pkg / "__init__.py").read_text(encoding="utf-8")
    assert "BremenRuntime" in entry or "AraminaRuntime" in entry
    assert (pkg / "manifest.py").is_file()
    assert (pkg / "runtime.py").is_file()
