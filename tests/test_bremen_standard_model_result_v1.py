"""Standard Model Result Contract v1 implementation tests (PR0157).

Covers the mapping boundary, the canonical schema, both model mappings,
authoritative-source consumption (probability/threshold/decision never
recomputed), explicit absence (no fabricated metrics/authors/timestamps/age),
canonical high/low vocabulary, model_method==model_version rule, timestamp
normalization, legacy report-field preservation, and the frozen HTTP route /
response / auth / request compatibility contract.

Research decision support requiring radiologist review; no clinical claim.
Synthetic data only; no real patient fixtures.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bremen.api import model_result_mapper as mapper
from bremen.api.model_result_mapper import (
    build_standard_result,
    map_aramina_result,
    map_bremen_result,
    normalize_timestamp,
)
from bremen.api.standard_model_result import (
    CANONICAL_FIELDS,
    RISK_LEVEL_HIGH,
    RISK_LEVEL_LOW,
    StandardModelResult,
)
from bremen.model_packages.bremen_v01 import manifest as bremen_manifest
from bremen.model_packages.aramina_v0213 import manifest as aramina_manifest


# ---------------------------------------------------------------------------
# Synthetic authoritative inputs (mapper test fixtures)
# ---------------------------------------------------------------------------

BREMEN_SUMMARY = {
    "prediction_id": "pred-1",
    "model_version": "0.2.0-paper-reference",
    "model_checksum": "",
    "feature_schema_version": "v0.1",
    # authoritative Bremen runtime values (golden probability from PR0151)
    "probability": 0.7388733541967353,
    "prediction": 1,
    "threshold_applied": 0.3585907282566089,
    "triage_recommendation": "CONTINUE_MRI",
    "decision_code": "CONTINUE_MRI",
    "decision_display_name": "Continue MRI evaluation",
    "decision_policy_id": "bremen_mri_continuation_threshold",
    "decision_policy_version": "0.1.0",
}

ARAMINA_SUMMARY = {
    "workflow_id": "aramina",
    "model_id": "aramina-a",
    "model_version": "0.2.13-beta",
    "technical_demo_only": True,
    "scientifically_certified": False,
    "external_report": {
        "risk_probability": 0.265,
        "risk_score": 0.265,           # legacy alias — must remain untouched
        "target_class_risk_level": 1,  # model-owned decision (int 0/1)
        "decision_threshold": 0.1,     # model-owned threshold; 0.265 >= 0.1 -> high
        "target_side": "left",
        "model_name": "aramina_target_breast_risk",
        "model_version": "0.2.13-beta",
        "reliability": "research_draft",
        "reliability_reason": "Technical demo only. Requires clinical review.",
    },
}

CONTEXT = {
    "patient_id": "PAT-SYNTH-1",
    "analysis_author": "Synthetic Author",
    "prediction_comment": "synthetic note",
    "target_side": "left",
}


def _bremen_mapped():
    return map_bremen_result(
        BREMEN_SUMMARY, model_identity={"model_version": "0.2.0-paper-reference"},
        job_context=CONTEXT, report_id="report-bremen",
        created_at="2026-09-04T19:48:36.123456+02:00",
    )


def _aramina_mapped():
    return map_aramina_result(
        ARAMINA_SUMMARY, model_identity={"model_version": "0.2.13-beta"},
        job_context=CONTEXT, report_id="report-aramina",
        created_at="2026-09-04T19:48:36.123456+02:00",
    )


# ---------------------------------------------------------------------------
# Schema shape
# ---------------------------------------------------------------------------


def test_schema_field_order_and_set():
    out = _bremen_mapped().to_envelope_dict()
    assert list(out.keys()) == list(CANONICAL_FIELDS)
    assert set(out) == set(CANONICAL_FIELDS)
    assert isinstance(out["model_metrics"], dict)
    assert set(out["model_metrics"]) == {"sensitivity", "specificity"}
    assert isinstance(out["specific_output"], dict)


def test_schema_is_frozen():
    result = StandardModelResult(report_id="x")
    with pytest.raises(Exception):
        result.report_id = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Canonical probability / threshold / decision mapping — consumed, not recomputed
# ---------------------------------------------------------------------------


def test_bremen_risk_probability_authoritative():
    out = _bremen_mapped().to_envelope_dict()
    # golden probability represented unchanged through the common contract
    assert out["risk_probability"] == 0.7388733541967353
    assert out["threshold_value"] == 0.3585907282566089


def test_bremen_high_and_low_decisions():
    high = map_bremen_result(
        {**BREMEN_SUMMARY, "prediction": 1}, job_context=CONTEXT,
    ).to_envelope_dict()
    low = map_bremen_result(
        {**BREMEN_SUMMARY, "probability": 0.10, "prediction": 0}, job_context=CONTEXT,
    ).to_envelope_dict()
    assert high["target_class_risk_level"] == RISK_LEVEL_HIGH == "high"
    assert low["target_class_risk_level"] == RISK_LEVEL_LOW == "low"


def test_aramina_high_and_low_decisions():
    high = map_aramina_result(ARAMINA_SUMMARY, job_context=CONTEXT).to_envelope_dict()
    low_summary = copy.deepcopy(ARAMINA_SUMMARY)
    low_summary["external_report"]["target_class_risk_level"] = 0
    low = map_aramina_result(low_summary, job_context=CONTEXT).to_envelope_dict()
    assert high["target_class_risk_level"] == "high"
    assert low["target_class_risk_level"] == "low"
    assert high["risk_probability"] == 0.265
    assert high["threshold_value"] == 0.1


def test_risk_level_only_high_or_low():
    values = {
        _bremen_mapped().to_envelope_dict()["target_class_risk_level"],
        _aramina_mapped().to_envelope_dict()["target_class_risk_level"],
    }
    assert values <= {"high", "low"}


def test_mapper_does_not_recompute_probability():
    # Decision fallback path reproduces the model operator exactly using
    # model-owned probability+threshold; never an independent threshold.
    out = mapper._risk_level(None, probability=0.4, threshold=0.4)
    assert out == "high"  # >= (model semantics)
    assert mapper._risk_level(None, probability=0.399, threshold=0.4) == "low"


# ---------------------------------------------------------------------------
# model_method + model_metrics
# ---------------------------------------------------------------------------


def test_model_method_equals_version_single_rule():
    assert mapper._model_method("0.2.0-paper-reference") == "0.2.0-paper-reference"
    assert _bremen_mapped().to_envelope_dict()["model_method"] == "0.2.0-paper-reference"
    assert _aramina_mapped().to_envelope_dict()["model_method"] == "0.2.13-beta"


def test_model_metrics_absent_not_fabricated():
    for out in (_bremen_mapped(), _aramina_mapped()):
        metrics = out.to_envelope_dict()["model_metrics"]
        assert metrics["sensitivity"] is None
        assert metrics["specificity"] is None


def test_mapper_does_not_hardcode_aramina_threshold():
    # A different authoritative threshold flows through unchanged (not hardcoded),
    # and the canonical level honors the model-owned decision rather than applying
    # an independent threshold comparison.
    summary = copy.deepcopy(ARAMINA_SUMMARY)
    summary["external_report"]["decision_threshold"] = 0.9
    out = map_aramina_result(summary).to_envelope_dict()
    assert out["threshold_value"] == 0.9          # authoritative threshold passed through
    assert out["target_class_risk_level"] == "high"  # model-owned decision (1) honored
    # Only when the model-owned decision is 0 does it map to low (still no recompute).
    summary["external_report"]["target_class_risk_level"] = 0
    assert map_aramina_result(summary).to_envelope_dict()["target_class_risk_level"] == "low"


# ---------------------------------------------------------------------------
# specific_output
# ---------------------------------------------------------------------------


def test_bremen_specific_output_empty():
    assert _bremen_mapped().to_envelope_dict()["specific_output"] == {}


def test_aramina_specific_output_shape():
    so = _aramina_mapped().to_envelope_dict()["specific_output"]
    assert so == {"target_side": "left", "mammography_suspicious_field": ""}


# ---------------------------------------------------------------------------
# Identity / provenance sources (PKG / ART authoritative)
# ---------------------------------------------------------------------------


def test_model_name_from_authoritative_manifest_not_runtime_registry_id():
    # model_identity carries a routing id; the mapper must use PKG/ART name.
    out = map_bremen_result(
        BREMEN_SUMMARY, model_identity={"model_id": "bremen-current"},
    ).to_envelope_dict()
    assert out["model_name"] == bremen_manifest.MODEL_NAME


def test_aramina_model_name_prefers_artifact_then_manifest():
    out = map_aramina_result(ARAMINA_SUMMARY).to_envelope_dict()
    assert out["model_name"] == "aramina_target_breast_risk"
    stripped = copy.deepcopy(ARAMINA_SUMMARY)
    stripped["external_report"]["model_name"] = ""
    out2 = map_aramina_result(stripped).to_envelope_dict()
    assert out2["model_name"] == aramina_manifest.MODEL_NAME


# ---------------------------------------------------------------------------
# Timestamp normalization
# ---------------------------------------------------------------------------


def test_created_at_strips_fractional_keeps_tz():
    assert _bremen_mapped().to_envelope_dict()["created_at"] == "2026-09-04T19:48:36+02:00"


def test_normalize_timestamp_variants():
    assert normalize_timestamp("2026-09-04T19:48:36+02:00") == "2026-09-04T19:48:36+02:00"
    assert normalize_timestamp("2026-01-01T00:00:00.000Z") == "2026-01-01T00:00:00+00:00"
    assert normalize_timestamp("2026-01-01T00:00:00.123456+00:00") == "2026-01-01T00:00:00+00:00"
    assert normalize_timestamp("") == ""
    assert normalize_timestamp(None) == ""
    assert normalize_timestamp("not-a-date") == ""


def test_normalize_preserves_naive_instant_without_inventing_tz():
    # no offset present -> do NOT append a fabricated zone
    assert normalize_timestamp("2026-09-04T19:48:36.999999") == "2026-09-04T19:48:36"


def test_scan_date_time_absent_is_empty_string():
    assert _bremen_mapped().to_envelope_dict()["scan_date_time"] == ""


# ---------------------------------------------------------------------------
# Absence behavior for optional metadata
# ---------------------------------------------------------------------------


def test_absent_context_fields_empty_not_fabricated():
    out = map_bremen_result(BREMEN_SUMMARY).to_envelope_dict()
    assert out["analysis_author"] == ""
    assert out["prediction_comment"] == ""
    assert out["patient_id"] == ""
    assert out["patient_age"] is None
    assert out["operator_id"] == ""
    assert out["hardware_version"] == ""
    # No authoritative Eoscan version source -> explicit null (never a
    # promoted alias from producer provenance).
    assert out["eoscan_version"] is None


def test_no_mapper_returns_for_invalid_results():
    assert map_bremen_result({"status": "failed"}) is None
    assert map_bremen_result({}) is None
    assert map_aramina_result({"status": "failed"}) is None
    assert build_standard_result("unknown-model", {"x": 1}) is None


def test_aramina_malformed_external_report_not_mapped():
    assert map_aramina_result({"workflow_id": "aramina"}) is None
    bad = copy.deepcopy(ARAMINA_SUMMARY)
    bad["external_report"]["risk_probability"] = "not-a-number"
    assert map_aramina_result(bad) is None


# ---------------------------------------------------------------------------
# Dispatch + integration with report envelope (provider-level)
# ---------------------------------------------------------------------------


def test_build_standard_result_dispatch_bremen_and_aramina():
    b = build_standard_result("bremen", BREMEN_SUMMARY, job_context=CONTEXT,
                              report_id="r", created_at="2026-01-01T00:00:00Z")
    a = build_standard_result("aramina", ARAMINA_SUMMARY, job_context=CONTEXT,
                              report_id="r", created_at="2026-01-01T00:00:00Z")
    assert b["model_name"] == bremen_manifest.MODEL_NAME
    assert a["specific_output"] == {"target_side": "left",
                                    "mammography_suspicious_field": ""}


# ---------------------------------------------------------------------------
# Report envelope integration: additive standard_result, legacy preserved
# ---------------------------------------------------------------------------


def _run_bremen_report():
    from bremen.api import model_registry as registry
    from bremen.api import job_api_handler as jobs
    from tests.bremen_3x3_helpers import MODEL, make_case, write_session_h5
    import os
    import tempfile

    jobs.reset_for_tests()
    registry.reset_for_tests()
    try:
        with tempfile.TemporaryDirectory() as td:
            path = write_session_h5(os.path.join(td, "in.h5"), make_case().measurements)
            entry = registry.RegistryModelEntry(
                model_id="bremen-current", display_name="Bremen", workflow_id="bremen",
                model_version="0.2.0-paper-reference", artifact_type="portable_logreg",
                feature_schema_version="v0.1",
                decision_policy_id="bremen_mri_continuation_threshold",
                decision_policy_version="0.1.0", technical_ready=True,
                _package=copy.deepcopy(MODEL), _checksum="",
            )
            registry.initialize_registry(registry.ModelRegistry(
                entries=(entry,), catalog_status="available", available_count=1,
                candidate_count=1,
            ))
            job = jobs.create_analysis_job(
                h5_path=path, workflow_id="bremen", model_id="bremen-current",
                patient_display_name="PAT-INT", analysis_author="Int Author",
                prediction_comment="int note",
            )
            assert job.overall_status == "completed"
            return jobs.get_job_report(job.job_id, "bremen")
    finally:
        jobs.reset_for_tests()
        registry.reset_for_tests()


def test_bremen_report_integration_standard_and_legacy():
    result = _run_bremen_report()
    report = result["report"]
    # legacy nested report payload fields preserved (v0.2 shape)
    sat = report["payload"]["score_and_threshold"]
    assert sat["p_mri_needed"] == pytest.approx(0.7388733541967353, abs=1e-12)
    assert sat["triage_recommendation"] == "CONTINUE_MRI"
    # additive standard_result present and authoritative
    std = report["standard_result"]
    assert std["risk_probability"] == pytest.approx(0.7388733541967353, abs=1e-12)
    assert std["threshold_value"] == pytest.approx(0.3585907282566089, abs=1e-12)
    assert std["target_class_risk_level"] == "high"
    assert std["model_name"] == bremen_manifest.MODEL_NAME
    assert std["model_method"] == std["model_version"]
    assert std["patient_id"] == "PAT-INT"
    assert std["analysis_author"] == "Int Author"
    assert std["prediction_comment"] == "int note"
    assert std["specific_output"] == {}


def test_bremen_report_golden_probability_within_frozen_tolerance_and_verbatim_mapping():
    report = _run_bremen_report()["report"]
    probability = report["standard_result"]["risk_probability"]
    legacy_probability = report["payload"]["score_and_threshold"]["p_mri_needed"]

    assert probability == legacy_probability
    assert probability == pytest.approx(
        0.7388733541967353,
        abs=1e-10,
        rel=0,
    )


def _run_failed_job_report():
    from bremen.api import model_registry as registry
    from bremen.api import job_api_handler as jobs

    jobs.reset_for_tests()
    registry.reset_for_tests()
    try:
        entry = registry.RegistryModelEntry(
            model_id="bremen-current", display_name="Bremen", workflow_id="bremen",
            model_version="0.2.0-paper-reference", artifact_type="portable_logreg",
            feature_schema_version="v0.1",
            decision_policy_id="bremen_mri_continuation_threshold",
            decision_policy_version="0.1.0", technical_ready=True,
            _package={"portable_logreg": {}},  # malformed -> not ready
            _checksum="",
        )
        registry.initialize_registry(registry.ModelRegistry(
            entries=(entry,), catalog_status="available", available_count=1,
            candidate_count=1,
        ))
        from tests.bremen_3x3_helpers import make_case, write_session_h5
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = write_session_h5(os.path.join(td, "in.h5"), make_case().measurements)
            job = jobs.create_analysis_job(h5_path=path, workflow_id="bremen",
                                           model_id="bremen-current")
            return jobs.get_job_report(job.job_id, "bremen")
    finally:
        jobs.reset_for_tests()
        registry.reset_for_tests()


def test_failed_report_envelope_unchanged_no_standard_result():
    report = _run_failed_job_report()["report"]
    # Not available -> no additive standard_result key at all
    assert report.get("standard_result") is None
    assert "standard_result" not in report


def _register_providers():
    from bremen.api import job_api_handler as jobs
    jobs._register_default_providers()


def test_aramina_envelope_integration_via_get_job_report():
    """Prove the single get_job_report boundary attaches standard_result for
    Aramina too, with the legacy external_report/risk_score contract intact.

    A synthetic completed job is inserted directly (no H5 pipeline needed); the
    registered Aramina report provider + mapper boundary are exercised."""
    from bremen.api import model_registry as registry
    from bremen.api import job_api_handler as jobs
    from bremen.api.job_models import AnalysisJob, WorkflowRun

    jobs.reset_for_tests()
    registry.reset_for_tests()
    try:
        _register_providers()
        wf = WorkflowRun(
            workflow_id="aramina", status="completed",
            model_identity={"model_id": "aramina-a", "model_version": "0.2.13-beta"},
            readiness_snapshot={}, result_summary=copy.deepcopy(ARAMINA_SUMMARY),
        )
        job = AnalysisJob(
            job_id="ajob", request_id="areq", created_at="2026-09-04T19:48:36+00:00",
            overall_status="completed",
            input_summary={
                "patient_display_name": "Nova_Synth", "target_side": "left",
                "analysis_author": "Armina Author", "prediction_comment": "am note",
            },
            requested_workflows=("aramina",),
            workflow_runs={"aramina": wf},
        )
        with jobs._jobs_lock:
            jobs._jobs[job.job_id] = job
        report = jobs.get_job_report(job.job_id, "aramina")["report"]
        # legacy external_report contract untouched
        assert report["payload"]["risk_score"] == 0.265
        assert report["payload"]["technical_demo_only"] is True
        std = report["standard_result"]
        assert std["risk_probability"] == 0.265
        assert std["target_class_risk_level"] == "high"
        assert std["specific_output"] == {
            "target_side": "left", "mammography_suspicious_field": "",
        }
        assert std["patient_id"] == "Nova_Synth"
        assert std["model_name"] == aramina_manifest.MODEL_NAME
    finally:
        jobs.reset_for_tests()
        registry.reset_for_tests()


def test_metadata_sanitizer_rejects_private_content():
    from bremen.api.job_api_handler import _clean_metadata_field
    assert _clean_metadata_field("  Alexey ") == "Alexey"
    assert _clean_metadata_field("/etc/passwd") == ""
    assert _clean_metadata_field("s3://bucket/key") == ""
    assert _clean_metadata_field("aws-secret") == ""
    assert _clean_metadata_field(None) == ""
    assert _clean_metadata_field("x" * 300) == ""


# ---------------------------------------------------------------------------
# Route / response / auth freeze
# ---------------------------------------------------------------------------

try:
    from fastapi.testclient import TestClient
    from bremen.api.fastapi_app import create_fastapi_app
except Exception:  # pragma: no cover
    TestClient = None

PR0156_FROZEN_ROUTES = {
    ("GET", "/demo"), ("GET", "/demo/api-docs"), ("GET", "/demo/api/h5/containers"),
    ("GET", "/demo/api/jobs"), ("GET", "/demo/api/jobs/{job_id}"),
    ("GET", "/demo/api/jobs/{job_id}/events"),
    ("GET", "/demo/api/jobs/{job_id}/events/stream"),
    ("GET", "/demo/api/jobs/{job_id}/reports"),
    ("GET", "/demo/api/jobs/{job_id}/reports/{workflow_id}"),
    ("GET", "/demo/api/models"),
    ("GET", "/demo/api/models/{model_id}/requirements"),
    ("GET", "/demo/api/reports/{job_id}/external"),
    ("GET", "/demo/api/reports/{job_id}/internal"),
    ("GET", "/demo/control-room"), ("GET", "/demo/login"),
    ("GET", "/demo/model-guide"), ("GET", "/demo/model-playground"),
    ("GET", "/demo/model-playground/sandpit-0104t-preview"),
    ("GET", "/demo/report/{job_id}"), ("GET", "/demo/workspace"),
    ("GET", "/demo/workspace/{job_id}"), ("GET", "/health"),
    ("GET", "/model/version"), ("POST", "/demo/api/auth/refresh"),
    ("POST", "/demo/api/auth/token"), ("POST", "/demo/api/h5/containers"),
    ("POST", "/demo/api/jobs"), ("POST", "/demo/api/jobs/{job_id}/auth/ticket"),
    ("POST", "/demo/api/models/{model_id}/requirements/validate"),
}


def _live_routes():
    app = create_fastapi_app()
    routes = set()
    for route in getattr(app, "routes", []):
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or path is None:
            continue
        for m in methods:
            if m not in ("HEAD", "OPTIONS"):
                routes.add((m, path))
    return routes


def test_route_inventory_identical_to_pr0156():
    assert _live_routes() == PR0156_FROZEN_ROUTES
    assert len(_live_routes()) == 29


def test_no_standard_result_endpoint_added():
    paths = {p for _, p in _live_routes()}
    assert not any(
        frag in p.lower() for p in paths
        for frag in ("standard", "model_result", "model-result", "/mapper")
    )


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_health_and_model_version_unaffected_auth():
    client = TestClient(create_fastapi_app())
    assert client.get("/health").status_code == 200
    assert client.get("/model/version").status_code == 200


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_jobs_create_request_schema_unchanged_rejects_missing_source():
    client = TestClient(create_fastapi_app())
    resp = client.post("/demo/api/jobs", json={"workflow_id": "bremen"})
    # same rejection behavior as before PR0157 (MISSING_SOURCE)
    assert resp.status_code == 400
    assert resp.json().get("error_code") in {"MISSING_SOURCE", "SOURCE_ERROR"}


# ---------------------------------------------------------------------------
# No duplicate mapping boundary: single dispatch table
# ---------------------------------------------------------------------------


def test_single_dispatch_boundary():
    assert set(mapper._MAPPERS) == {"bremen", "aramina"}
    assert mapper._MAPPERS["bremen"] is map_bremen_result
    assert mapper._MAPPERS["aramina"] is map_aramina_result


# ---------------------------------------------------------------------------
# Frozen mapping fixtures (synthetic metadata + authoritative numbers)
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "standard_model_result"


def test_bremen_mapping_matches_frozen_fixture():
    expected = json.loads((FIXTURE_DIR / "bremen_v01_golden.json").read_text())
    assert _bremen_mapped().to_envelope_dict() == expected


def test_aramina_mapping_matches_frozen_fixture():
    expected = json.loads((FIXTURE_DIR / "aramina_v0213_golden.json").read_text())
    assert _aramina_mapped().to_envelope_dict() == expected


# ---------------------------------------------------------------------------
# Model Package Standard conformance stays intact (packages unaware of schema)
# ---------------------------------------------------------------------------


def test_package_runtime_satisfies_contract_unchanged():
    from bremen.model_runtime import ModelRuntime
    from bremen.model_packages.bremen_v01.runtime import BremenRuntime
    from tests.bremen_3x3_helpers import MODEL
    assert isinstance(BremenRuntime(MODEL), ModelRuntime)
    assert isinstance(
        _aramina_pkg_runtime(), ModelRuntime,
    )


def _aramina_pkg_runtime():
    from bremen.model_packages.aramina_v0213.runtime import AraminaRuntime
    return AraminaRuntime(entry=SimpleNamespace(
        model_id="aramina-a", model_version="0.2.13-beta",
        feature_schema_version="v0.1",
    ))


def test_mapper_does_not_import_or_depend_on_orchestration_only_consumes():
    # schema + mapper live in api/ (platform) and never import report providers
    import ast
    src = Path("src/bremen/api/model_result_mapper.py").read_text()
    tree = ast.parse(src)
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
        elif isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name)
    for m in mods:
        assert "report_bremen" not in m and "report_aramina" not in m
        assert "job_api_handler" not in m
        assert "workflow_bremen" not in m and "workflow_aramina" not in m
