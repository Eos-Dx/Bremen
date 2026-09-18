"""PR0158a — Standard Model Result Contract hardening tests.

Two narrow platform-contract fixes:

1. Stable Standard Model Result identity: ``get_job_report`` sources
   ``standard_result.report_id``/``created_at`` from the ALREADY-STORED
   ``job.reports[workflow_id]`` ReportMetadata so repeated identical GETs return
   byte-identical canonical identity (both Bremen and Aramina), while legacy
   envelope/payload fields are untouched.

2. Aramina requirements preflight: ``ModelRequirementsValidateRequest`` now
   preserves ``patient_id``/``target_side`` (and ``analysis_author``/
   ``prediction_comment``) through ``model_dump(exclude_none=True)`` so an
   Aramina ``/requirements/validate`` no longer spuriously reports them missing;
   Bremen validation behavior is unchanged.

Synthetic data only; no real patients; no scientific change.
"""
from __future__ import annotations

import bremen.platform.reports.service as _owner_reports_service



import copy

import pytest

from bremen.platform.reports.mapper import normalize_timestamp
from bremen.contracts.results import RISK_LEVEL_HIGH


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

ARAMINA_SUMMARY = {
    "workflow_id": "aramina",
    "model_id": "aramina-a",
    "model_version": "0.2.13-beta",
    "technical_demo_only": True,
    "scientifically_certified": False,
    "external_report": {
        "risk_probability": 0.869387073973647,
        "risk_score": 0.869387073973647,
        "target_class_risk_level": 1,
        "decision_threshold": 0.24665932038818544,
        "target_side": "left",
        "model_name": "aramina_target_breast_risk",
        "model_version": "0.2.13-beta",
        "reliability": "research_draft",
        "reliability_reason": "Technical demo only. Requires clinical review.",
    },
}


def _register_providers():

    _owner_reports_service._register_default_providers()


def _bremen_report():
    """Run a completed Bremen job through create_analysis_job + report read."""
    from bremen.platform.models import registry
    from bremen.platform.jobs import service as jobs
    import os
    import tempfile
    from tests.bremen_3x3_helpers import MODEL, make_case, write_session_h5

    jobs.reset_for_tests()
    registry.reset_for_tests()
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
        return jobs, job


def _insert_completed_aramina_job():
    """Insert a synthetic completed Aramina job + populate stored reports."""
    from bremen.platform.models import registry
    from bremen.platform.jobs import service as jobs
    from bremen.platform.jobs.models import AnalysisJob, WorkflowRun

    jobs.reset_for_tests()
    registry.reset_for_tests()
    _register_providers()
    wf = WorkflowRun(
        workflow_id="aramina", status="completed",
        model_identity={"model_id": "aramina-a", "model_version": "0.2.13-beta"},
        readiness_snapshot={}, result_summary=copy.deepcopy(ARAMINA_SUMMARY),
    )
    job = AnalysisJob(
        job_id="hjob", request_id="hreq", created_at="2026-09-16T12:29:53.320768+00:00",
        overall_status="completed",
        input_summary={
            "patient_display_name": "Nova_Synth", "target_side": "left",
            "analysis_author": "Aramina Author", "prediction_comment": "am note",
            "model_id": "aramina-a",
        },
        requested_workflows=("aramina",),
        workflow_runs={"aramina": wf},
    )
    # Mirror the completed-job path: generate + STORE report metadata.
    _owner_reports_service._generate_job_reports(job)
    with jobs._jobs_lock:
        jobs._jobs[job.job_id] = job
    return jobs, job


# ---------------------------------------------------------------------------
# 1. Standard Model Result identity stability — Bremen
# ---------------------------------------------------------------------------


def test_bremen_standard_result_identity_stable_across_gets():
    jobs, job = _bremen_report()
    try:
        first = _owner_reports_service.get_job_report(job.job_id, "bremen")["report"]
        second = _owner_reports_service.get_job_report(job.job_id, "bremen")["report"]
        s1, s2 = first["standard_result"], second["standard_result"]
        assert s1["report_id"] == s2["report_id"]
        assert s1["created_at"] == s2["created_at"]
    finally:
        jobs.reset_for_tests()


def test_bremen_standard_result_identity_from_stored_report_metadata():
    jobs, job = _bremen_report()
    try:
        stored = job.reports["bremen"]
        report = _owner_reports_service.get_job_report(job.job_id, "bremen")["report"]
        std = report["standard_result"]
        assert std["report_id"] == stored.report_id
        assert std["created_at"] == normalize_timestamp(stored.generated_at)
        # canonical created_at is seconds precision, no fractional, tz preserved
        assert "." not in std["created_at"]
        assert std["created_at"].endswith(("+00:00",)) or "+" in std["created_at"]
    finally:
        jobs.reset_for_tests()


def test_bremen_scientific_fields_unchanged_after_hardening():
    jobs, job = _bremen_report()
    try:
        report = _owner_reports_service.get_job_report(job.job_id, "bremen")["report"]
        std = report["standard_result"]
        # authoritative golden values flow through unchanged
        assert std["risk_probability"] == pytest.approx(0.7388733541967353, abs=1e-10)
        assert std["threshold_value"] == pytest.approx(0.3585907282566089, abs=1e-12)
        assert std["target_class_risk_level"] == RISK_LEVEL_HIGH
        # legacy nested payload field still present & identical
        assert (
            report["payload"]["score_and_threshold"]["p_mri_needed"]
            == pytest.approx(0.7388733541967353, abs=1e-10)
        )
    finally:
        jobs.reset_for_tests()


# ---------------------------------------------------------------------------
# 2. Standard Model Result identity stability — Aramina
# ---------------------------------------------------------------------------


def test_aramina_standard_result_identity_stable_across_gets():
    jobs, job = _insert_completed_aramina_job()
    try:
        first = _owner_reports_service.get_job_report(job.job_id, "aramina")["report"]
        second = _owner_reports_service.get_job_report(job.job_id, "aramina")["report"]
        s1, s2 = first["standard_result"], second["standard_result"]
        assert s1["report_id"] == s2["report_id"]
        assert s1["created_at"] == s2["created_at"]
    finally:
        jobs.reset_for_tests()


def test_aramina_standard_result_identity_from_stored_report_metadata():
    jobs, job = _insert_completed_aramina_job()
    try:
        stored = job.reports["aramina"]
        report = _owner_reports_service.get_job_report(job.job_id, "aramina")["report"]
        std = report["standard_result"]
        assert std["report_id"] == stored.report_id
        assert std["created_at"] == normalize_timestamp(stored.generated_at)
        assert "." not in std["created_at"]
        # scientific + request fields unchanged by the identity fix
        assert std["risk_probability"] == 0.869387073973647
        assert std["threshold_value"] == 0.24665932038818544
        assert std["target_class_risk_level"] == RISK_LEVEL_HIGH
        assert std["specific_output"] == {
            "target_side": "left", "mammography_suspicious_field": "",
        }
        assert std["patient_id"] == "Nova_Synth"
        # legacy report payload contract untouched
        assert report["payload"]["risk_score"] == 0.869387073973647
        assert report["payload"]["technical_demo_only"] is True
    finally:
        jobs.reset_for_tests()


def test_legacy_envelope_report_id_still_freshly_generated():
    """The hardening changed only standard_result identity sourcing; the legacy
    envelope report_id keeps its previous fresh-per-GET behavior."""
    jobs, job = _insert_completed_aramina_job()
    try:
        first = _owner_reports_service.get_job_report(job.job_id, "aramina")["report"]
        second = _owner_reports_service.get_job_report(job.job_id, "aramina")["report"]
        # legacy envelope report_id is regenerated each read (unchanged behavior)
        assert first["report_id"] != second["report_id"]
        # standard_result identity is stable (the fix)
        assert (
            first["standard_result"]["report_id"]
            == second["standard_result"]["report_id"]
        )
    finally:
        jobs.reset_for_tests()


# ---------------------------------------------------------------------------
# 3. Timestamp normalization contract
# ---------------------------------------------------------------------------


def test_normalize_timestamp_fractional_seconds_with_tz():
    assert (
        normalize_timestamp("2026-09-16T12:29:53.320768+00:00")
        == "2026-09-16T12:29:53+00:00"
    )


def test_normalize_timestamp_preserves_offset_no_utc_conversion():
    # +02:00 stays +02:00; not forced to Z, not shifted to UTC
    assert (
        normalize_timestamp("2026-09-16T12:29:53.320768+02:00")
        == "2026-09-16T12:29:53+02:00"
    )


# ---------------------------------------------------------------------------
# 4. Aramina requirements preflight request contract
# ---------------------------------------------------------------------------


def test_requirements_request_model_preserves_aramina_fields():
    from bremen.api.fastapi_contracts import ModelRequirementsValidateRequest

    body = {
        "container_id": "Nova_Synth.h5",
        "source_id": "fresh-src",
        "patient_id": "Nova_Synth",
        "target_side": "left",
        "analysis_author": "Aramina Author",
        "prediction_comment": "preflight note",
    }
    req = ModelRequirementsValidateRequest(**body)
    dumped = req.model_dump(exclude_none=True)
    for field in ("patient_id", "target_side", "analysis_author", "prediction_comment"):
        assert dumped.get(field) == body[field]


def test_requirements_request_model_bremen_absence_unchanged():
    """Bremen-style body without patient/side stays a valid no-op payload."""
    from bremen.api.fastapi_contracts import ModelRequirementsValidateRequest

    dumped = ModelRequirementsValidateRequest(
        container_id="c", source_id="s",
    ).model_dump(exclude_none=True)
    assert dumped["container_id"] == "c"
    assert "patient_id" not in dumped
    assert "target_side" not in dumped


# ---------------------------------------------------------------------------
# 5. Requirements validation route — Aramina no longer loses patient_id/target_side
# ---------------------------------------------------------------------------

try:
    from fastapi.testclient import TestClient
    from bremen.api.http.app import create_app
except Exception:  # pragma: no cover
    TestClient = None

_AUTH_PWD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$c2FsdHNhbHRzYWx0$testhashplaceholder"
)
_JWT_SECRET = "r" * 48


def _enable_auth(monkeypatch):
    from bremen.api.http.auth_config import _reset_auth_config
    from bremen.auth import create_access_token
    from bremen.config import read_auth_config

    monkeypatch.setenv("BREMEN_AUTH_ENABLED", "true")
    monkeypatch.setenv("BREMEN_AUTH_USERNAME", "testuser")
    monkeypatch.setenv("BREMEN_AUTH_PASSWORD_HASH", _AUTH_PWD_HASH)
    monkeypatch.setenv("BREMEN_AUTH_JWT_SECRET", _JWT_SECRET)
    _reset_auth_config()
    token = create_access_token(read_auth_config(), "testuser")
    return {"Authorization": f"Bearer {token}"}


def _install_aramina_requirements_entry():
    from bremen.platform.models import registry

    registry.reset_for_tests()
    entry = registry.RegistryModelEntry(
        model_id="aramina-test", display_name="Aramina", workflow_id="aramina",
        model_version="0.2.13-beta", artifact_type="aramina.joblib.model_package",
        feature_schema_version="v0.1",
        decision_policy_id="aramina_policy", decision_policy_version="v0.1",
        technical_ready=True, scientifically_certified=False,
        technical_demo_only=True, availability="available",
        _package={}, _checksum="",
        _container_requirements={
            "schema_version": "bremen.container_requirements.v1",
            "requirements_id": "aramina-test-container.v0.1",
            "workflow_id": "aramina",
            "request_requirements": {
                "required_fields": [
                    "container_id", "source_id", "patient_id", "target_side",
                ],
                "optional_fields": ["analysis_author", "prediction_comment"],
            },
        },
    )
    registry.initialize_registry(registry.ModelRegistry(
        entries=(entry,), catalog_status="available", available_count=1,
        candidate_count=1,
    ))


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_aramina_requirements_validate_preserves_patient_and_side(monkeypatch):
    """Route-level proof: /requirements/validate keeps patient_id/target_side."""
    from bremen.platform.models import registry
    from bremen.platform.jobs import service as jobs
    from bremen.api.http.auth_config import _reset_auth_config

    headers = _enable_auth(monkeypatch)
    _install_aramina_requirements_entry()
    jobs.reset_for_tests()
    # Force the read-only dry run to fail at source resolution so we assert the
    # *request_payload* stage specifically (the dry run is not our concern).
    monkeypatch.setattr(
        __import__("bremen.platform.sources.service", fromlist=["resolve_source"]), "resolve_source",
        lambda *a, **k: (_ for _ in ()).throw(ValueError("no such source")),
    )
    try:
        client = TestClient(create_app())
        resp = client.post(
            "/demo/api/models/aramina-test/requirements/validate",
            headers=headers,
            json={
                "container_id": "Nova_Synth.h5",
                "source_id": "fresh-source-id",
                "patient_id": "Nova_Synth",
                "target_side": "left",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        missing = data.get("missing_required_fields", [])
        assert "patient_id" not in missing
        assert "target_side" not in missing
        # The payload stage now passes; any failure is a downstream dry-run
        # stage, never request_payload.
        assert data.get("failure_stage") != "request_payload"
    finally:
        registry.reset_for_tests()
        jobs.reset_for_tests()
        _reset_auth_config()


@pytest.mark.skipif(TestClient is None, reason="fastapi not installed")
def test_bremen_requirements_validate_behavior_unchanged(monkeypatch):
    """A Bremen entry requiring only container_id+source_id is unaffected."""
    from bremen.platform.models import registry
    from bremen.platform.jobs import service as jobs
    from bremen.api.http.auth_config import _reset_auth_config

    headers = _enable_auth(monkeypatch)
    registry.reset_for_tests()
    jobs.reset_for_tests()
    entry = registry.RegistryModelEntry(
        model_id="bremen-test", display_name="Bremen", workflow_id="bremen",
        model_version="0.2.0-paper-reference", artifact_type="portable_logreg",
        feature_schema_version="v0.1",
        decision_policy_id="bremen_mri_continuation_threshold",
        decision_policy_version="0.1.0", technical_ready=True,
        scientifically_certified=False, technical_demo_only=True, availability="available",
        _package={}, _checksum="",
        _container_requirements={
            "schema_version": "bremen.container_requirements.v1",
            "workflow_id": "bremen",
            "request_requirements": {
                "required_fields": ["container_id", "source_id"],
            },
        },
    )
    registry.initialize_registry(registry.ModelRegistry(
        entries=(entry,), catalog_status="available", available_count=1,
        candidate_count=1,
    ))
    monkeypatch.setattr(
        __import__("bremen.platform.sources.service", fromlist=["resolve_source"]), "resolve_source",
        lambda *a, **k: (_ for _ in ()).throw(ValueError("no such source")),
    )
    try:
        client = TestClient(create_app())
        resp = client.post(
            "/demo/api/models/bremen-test/requirements/validate",
            headers=headers,
            json={"container_id": "b.h5", "source_id": "s1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # container_id+source_id present -> no request_payload failure
        assert data.get("failure_stage") != "request_payload"
        assert data.get("missing_required_fields") == []
    finally:
        registry.reset_for_tests()
        jobs.reset_for_tests()
        _reset_auth_config()
