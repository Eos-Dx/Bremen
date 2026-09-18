"""Architecture boundaries and executable public baseline for PR0162."""

from __future__ import annotations

import ast
import json
from importlib.util import resolve_name
from pathlib import Path
import subprocess
import sys

import pytest

from bremen.contracts.execution import WorkflowResult
from bremen.contracts.model_runtime import ModelValidation, RuntimePrediction
from bremen.platform.runtime.executor import ExecutionRequest, execute
from bremen.platform.runtime.registry import (
    ModelDescriptor,
    RuntimeRegistry,
    DuplicateModelError,
    ModelNotFoundError,
)

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / ".project-memory/pr/0162-refactor-baseline-and-import-hygiene"


def test_imports_do_not_load_scientific_dependencies():
    code = """import sys
import bremen
from bremen.api.http.app import create_app
assert not any(x in sys.modules for x in (
    "numpy", "scipy", "sklearn", "h5py", "pandas", "joblib", "mlflow")), sorted(sys.modules)
"""
    subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True, text=True
    )


def test_import_direction():
    boundaries = {
        "contracts": ("bremen.api", "bremen.platform", "bremen.model_packages", "fastapi"),
        "model_packages": ("bremen.api", "bremen.platform", "fastapi"),
        "platform": ("bremen.api", "fastapi"),
    }
    for folder, forbidden in boundaries.items():
        for path in sorted((ROOT / "src/bremen" / folder).rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text())):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    package = ".".join(path.relative_to(ROOT / "src").parts[:-1])
                    module = resolve_name("." * node.level + (node.module or ""), package)
                    modules = [module, *(module + "." + a.name for a in node.names)]
                assert not any(
                    m == p or m.startswith(p + ".") for m in modules for p in forbidden
                ), (path, node.lineno)


def test_executor_has_no_workflow_specific_dispatch():
    path = ROOT / "src/bremen/platform/runtime/executor.py"
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Compare):
            assert not any(
                isinstance(n, ast.Constant) and n.value in ("bremen", "aramina")
                for n in ast.walk(node)
            )
    assert "build_features(" not in path.read_text()
    assert "run_inference(" not in path.read_text()

    import inspect
    from dataclasses import MISSING, fields
    from bremen.platform.jobs.service import create_analysis_job
    from bremen.platform.runtime.executor import run_workflow_request

    field = next(f for f in fields(ExecutionRequest) if f.name == "workflow_id")
    assert field.default is MISSING
    from bremen.platform.models.catalog import resolve_model

    for operation in (create_analysis_job, run_workflow_request, resolve_model):
        parameter = inspect.signature(operation).parameters["workflow_id"]
        assert parameter.default is inspect.Parameter.empty


def test_third_runtime_uses_same_executor_once(tmp_path):
    calls = []

    class Runtime:
        def validate_model_input(self, model_input):
            calls.append(("validate", model_input))
            return ModelValidation(compatible=True)

        def predict_model(self, model_input, *, on_features=None):
            calls.append(("predict", model_input))
            return RuntimePrediction(workflow_id="third", result={"value": 7})

    descriptor = ModelDescriptor(
        "third",
        Runtime(),
        lambda d, p, i: WorkflowResult(d.workflow_id, "completed", dict(p.result)),
        lambda e: WorkflowResult("third", "failed", error="safe_failure"),
    )
    registry = RuntimeRegistry()
    registry.register(descriptor)
    source = tmp_path / "opaque.bin"
    source.write_bytes(b"package input, not platform science")
    outcome = execute(
        ExecutionRequest(
            str(source),
            "third",
            patient_id="p1",
            target_side="left",
            parameters={"parameter": "kept"},
        ),
        registry=registry,
    )
    assert outcome.overall_status == "completed"
    assert outcome.workflows["third"].payload == {"value": 7}
    assert [c[0] for c in calls] == ["validate", "predict"]
    assert calls[0][1] is calls[1][1]
    assert calls[0][1].container_path == str(source)
    assert calls[0][1].parameters == {"parameter": "kept"}
    assert calls[0][1].canonical is None
    with pytest.raises(DuplicateModelError):
        registry.register(descriptor)
    with pytest.raises(ModelNotFoundError):
        registry.resolve("missing")


def test_all_public_routes_equal_baseline():
    from bremen.api.http.app import create_app

    routes = sorted(
        [
            {"method": m, "path": r.path}
            for r in create_app().routes
            for m in getattr(r, "methods", ())
            if m not in ("HEAD", "OPTIONS")
        ],
        key=lambda r: (r["path"], r["method"]),
    )
    assert routes == json.loads((BASELINE / "public_routes.json").read_text())


def test_result_projection_equal_baseline():
    from tests.test_bremen_standard_model_result_v1 import (
        BREMEN_SUMMARY,
        ARAMINA_SUMMARY,
        CONTEXT,
    )
    from bremen.platform.reports.mapper import build_standard_result

    actual = {
        w: build_standard_result(
            w,
            s,
            job_context=CONTEXT,
            report_id="baseline",
            created_at="2026-09-18T00:00:00Z",
        )
        for w, s in [("bremen", BREMEN_SUMMARY), ("aramina", ARAMINA_SUMMARY)]
    }
    assert actual == json.loads((BASELINE / "public_results.json").read_text())


def test_removed_internal_architecture_is_not_reintroduced():
    for name in (
        "workflow_provider",
        "workflow_registry",
        "workflow_orchestrator",
        "workflow_bremen",
        "workflow_aramina",
        "workflow_aramina_scaffold",
        "aramina_provider",
        "aramina_artifact_compat",
        "aramina_preprocessing",
        "aramina_symmetry",
        "report_aramina",
        "runtime_plugin",
        "preprocessing_bridge",
        "job_models",
        "inference_handler",
    ):
        assert not (ROOT / "src/bremen/api" / f"{name}.py").exists()


def test_cut3_has_one_http_runtime_and_platform_discovery_owner():
    source_root = ROOT / "src/bremen"
    assert not (source_root / "api/server.py").exists()
    production = "\n".join(p.read_text() for p in source_root.rglob("*.py"))
    assert "bremen.api.server" not in production
    assert "bremen.api.s3_model_discovery" not in production
    assert "from http.server" not in production
    assert "BaseHTTPRequestHandler" not in production
    assert (source_root / "platform/models/discovery.py").exists()
    assert not (source_root / "api/s3_model_discovery.py").exists()
    factories = []
    for path in (source_root / "api").rglob("*.py"):
        tree = ast.parse(path.read_text())
        if any(isinstance(n, ast.FunctionDef) and n.name == "create_app" for n in tree.body):
            factories.append(path.relative_to(source_root).as_posix())
    assert factories == ["api/http/app.py"]


def test_cut4_removes_application_facades_and_uses_one_lifespan():
    source_root = ROOT / "src/bremen"
    assert not (source_root / "api/http/legacy_jobs.py").exists()
    assert not (source_root / "api/app.py").exists()
    production = "\n".join(p.read_text() for p in source_root.rglob("*.py"))
    assert "legacy_jobs" not in production
    assert "bremen.api.app" not in production
    assert ".on_event(" not in production
    assert production.count("async def lifespan(") == 1


def test_cut5_removes_test_compatibility_copies_and_deleted_facades():
    source_root = ROOT / "src/bremen"
    tests_root = ROOT / "tests"
    assert not (tests_root / "_legacy_jobs_support.py").exists()
    assert not (tests_root / "_api_app_support.py").exists()
    production = "\n".join(p.read_text() for p in source_root.rglob("*.py"))
    for forbidden in (
        "bremen.api.app",
        "bremen.api.http.legacy_jobs",
        "from http.server",
        "WorkflowProvider",
        "WorkflowRuntimePlugin",
    ):
        assert forbidden not in production


def test_bremen_event_fields_and_order_survive_provider_removal(tmp_path):
    from bremen.platform.events.store import BoundedEventStore
    from bremen.platform.runtime.registry import bremen_descriptor
    from tests.bremen_3x3_helpers import MODEL, write_session_h5

    source = tmp_path / "source.h5"
    write_session_h5(source)
    registry = RuntimeRegistry()
    registry.register(bremen_descriptor(MODEL))
    store = BoundedEventStore()
    result = execute(
        ExecutionRequest(str(source), job_id="trace", workflow_id="bremen"),
        registry=registry,
        event_store=store,
    )
    assert result.overall_status == "completed"
    events = store.get_events("trace")
    by_type = {event.event_type: event for event in events}
    stages = [event.event_type for event in events]
    assert stages.index("runtime.artifact.verification.completed") < stages.index(
        "runtime.input.preparation.completed"
    )
    assert stages.index("runtime.features.completed") < stages.index(
        "runtime.inference.completed"
    )
    details = by_type["runtime.input.preparation.completed"].details
    assert details["left_measurement_count"] == 3
    assert details["right_measurement_count"] == 3
    assert details["compatible"] is True
    assert (
        by_type["runtime.features.validation.completed"].details["produced_count"] == 15
    )
    assert by_type["runtime.decision.completed"].details["decision_policy_id"]


def test_failure_event_keeps_registered_safe_reason(tmp_path):
    from bremen.platform.events.store import BoundedEventStore

    class FailingRuntime:
        def validate_model_input(self, model_input):
            return ModelValidation(compatible=True)

        def predict_model(self, model_input, *, on_features=None):
            raise ValueError("/private/input token=secret")

    descriptor = ModelDescriptor(
        "third",
        FailingRuntime(),
        None,
        lambda exc: WorkflowResult("third", "failed", error="SAFE_FAILURE"),
        failure_event_reason=True,
    )
    registry = RuntimeRegistry()
    registry.register(descriptor)
    source = tmp_path / "source"
    source.write_bytes(b"opaque")
    store = BoundedEventStore()
    result = execute(
        ExecutionRequest(str(source), "third", job_id="failure"),
        registry=registry,
        event_store=store,
    )
    events = [event.to_dict() for event in store.get_events("failure")]
    assert result.workflows["third"].error == "SAFE_FAILURE"
    failure = next(e for e in events if e["event_type"] == "runtime.workflow.failed")
    assert failure["details"]["reason"] == "SAFE_FAILURE"
    assert "private" not in json.dumps(events)
    assert "secret" not in json.dumps(events)


def test_job_values_have_one_authoritative_owner():
    names = {"AnalysisJob", "WorkflowRun", "ReportMetadata"}
    definitions = {name: [] for name in names}
    for path in (ROOT / "src/bremen").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ClassDef) and node.name in names:
                definitions[node.name].append(path.relative_to(ROOT).as_posix())
    assert definitions == {
        name: ["src/bremen/platform/jobs/models.py"] for name in names
    }
