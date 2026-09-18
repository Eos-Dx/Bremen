"""PR0159 — Standard Result metadata completion integration tests.

Proves end-to-end (task §8, §9) that for BOTH Bremen and Aramina:

- the model package's own adapter parses its container metadata into the
  normalized contract;
- the normalized contract travels through ModelRuntime result -> workflow
  payload -> Standard Result mapper;
- ``standard_result`` receives patient_age / scan_date_time / operator_id /
  hardware_version (eoscan_version is explicit ``None`` because no
  authoritative package-owned Eoscan version source exists — the
  omniscan-backfill ``producer_version`` is never promoted);
- ``standard_result.model_metrics.sensitivity/specificity`` equal the
  authoritative model-owned runtime values (source-to-canonical equality, not
  duplicated literals);
- ``model_method`` comes from the model package's own model-type/inference-method
  field when the active package provides one.

PR0158a repeated-GET identity stability is retained (asserted at the end).

Synthetic deterministic H5 fixtures only; no supplied patient H5 binaries.
"""
from __future__ import annotations

import bremen.platform.reports.service as _owner_reports_service

import copy
import hashlib
import json
from pathlib import Path

import h5py
import joblib
import numpy as np
import pandas as pd
import pytest

from bremen.platform.jobs import service as jobs
from bremen.platform.models import registry
from bremen.contracts.request import AnalysisParameters
from bremen.model_packages.aramina_v0213 import manifest as aramina_manifest
from tests.bremen_3x3_helpers import MODEL, make_case, write_session_h5


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _bremen_h5(path: Path, *, age: int = 44, started_at: str = "2025-05-28 10:19:55") -> str:
    """Session-layout H5 with full canonical source metadata (Bremen path)."""
    write_session_h5(path, make_case().measurements)
    with h5py.File(path, "a") as f:
        f["/session/sample"].attrs["age"] = age
        f["/session"].attrs["started_at"] = started_at
        f["/session"].attrs["operator_username"] = "backfill"
        f["/session"].attrs["producer_version"] = "0.1.0"
        f["/session"].attrs["producer_software"] = "omniscan-backfill"
        f["/session"].attrs["schema_version"] = "0.3"
        for key in f["/session/sets"].keys():
            g = f["/session/sets"][key]
            g.create_dataset(
                "metadata",
                data=json.dumps({"backfill_provenance": {"human1_version": "v1.0.1"}}),
            )
    return str(path)


def _aramina_h5(path: Path) -> str:
    """Canonical-layout H5 (width-10 profiles) + full source metadata.

    The canonical layout is detected first (Bremen canonical adapter) and the
    ``/session`` metadata subtree is present for the Aramina package adapter.
    """
    with h5py.File(path, "w") as f:
        f["patient/id"] = "p1"
        f["scans/target/measurements"] = [float(i) for i in range(10)]
        f["scans/contralateral/measurements"] = [float(i) * 0.1 for i in range(10)]
        f["scans/target/side"] = "LEFT"
        f["scans/contralateral/side"] = "RIGHT"
        f["session/sample/patient_name"] = "p1"
        f["/session/sample"].attrs["age"] = 44
        f["/session"].attrs["started_at"] = "2025-05-28 10:19:55"
        f["/session"].attrs["operator_username"] = "backfill"
        f["/session"].attrs["producer_version"] = "0.1.0"
        f["/session"].attrs["producer_software"] = "omniscan-backfill"
        f["/session"].attrs["schema_version"] = "0.3"
        sets = f.create_group("/session/sets")
        for name in ("set_001_sample_main", "contralateral_set_001_sample_main"):
            g = sets.create_group(name)
            g.create_dataset(
                "metadata",
                data=json.dumps({"backfill_provenance": {"human1_version": "v1.0.1"}}),
            )
    return str(path)


@pytest.fixture(autouse=True)
def _synthetic_aramina_preprocessing(monkeypatch):
    """Deterministic frame for the Aramina package pipeline (test-only)."""

    def preprocess(h5_path, config_yaml):
        from bremen.platform.sources.legacy_input import normalize_legacy_input as _normalize_h5
        canonical = _normalize_h5(h5_path)
        return pd.DataFrame([
            {"patientId": "p1", "side": m.side, "age": None,
             "radial_profile_data": list(m.intensity),
             "q_range": list(np.linspace(2., 23., len(m.intensity)))}
            for m in canonical.measurements
        ])

    monkeypatch.setattr(
        "bremen.model_packages.aramina_v0213.preprocessing.preprocess_aramina",
        preprocess,
    )


def _reset():
    jobs.reset_for_tests()
    registry.reset_for_tests()


# ---------------------------------------------------------------------------
# Shared assertions
# ---------------------------------------------------------------------------


def _assert_standard_metadata(std: dict) -> None:
    assert std["patient_age"] == 44
    assert std["scan_date_time"] == "2025-05-28T10:19:55"
    assert std["operator_id"] == "backfill"
    assert std["hardware_version"] == "v1.0.1"
    # No authoritative package-owned Eoscan version source exists: the
    # producer_version (omniscan-backfill) is never promoted, so the
    # canonical field is explicit null.
    assert std["eoscan_version"] is None


# ---------------------------------------------------------------------------
# Bremen integration + metrics
# ---------------------------------------------------------------------------


def _bremen_package():
    package = copy.deepcopy(MODEL)
    package["model_definition"] = {
        "architecture": "median_imputer_standard_scaler_balanced_logistic_regression",
    }
    package["final_fit_training_metrics"] = {
        "sensitivity": 0.9516129032258065,
        "specificity": 0.391304347826087,
    }
    return package


def _bremen_entry(package=None):
    return registry.RegistryModelEntry(
        model_id="bremen-meta", display_name="Bremen", workflow_id="bremen",
        model_version="0.2.0-paper-reference", artifact_type="portable_logreg",
        feature_schema_version="v0.1",
        decision_policy_id="bremen_mri_continuation_threshold",
        decision_policy_version="0.1.0", technical_ready=True,
        _package=package if package is not None else _bremen_package(),
        _checksum="",
    )


def _bremen_job(tmp_path, package=None):
    registry.reset_for_tests()
    jobs.reset_for_tests()
    entry = _bremen_entry(package)
    registry.initialize_registry(registry.ModelRegistry(
        entries=(entry,), catalog_status="available", available_count=1,
        candidate_count=1,
    ))
    h5_path = _bremen_h5(tmp_path / "bremen.h5")
    job = jobs.create_analysis_job(
        h5_path=h5_path, workflow_id="bremen", model_id="bremen-meta",
        patient_display_name="Nova_227",
    )
    assert job.overall_status == "completed"
    return job


def test_bremen_standard_result_receives_extracted_h5_metadata(tmp_path):
    job = _bremen_job(tmp_path)
    try:
        std = _owner_reports_service.get_job_report(job.job_id, "bremen")["report"]["standard_result"]
        _assert_standard_metadata(std)
    finally:
        _reset()


def test_bremen_metrics_source_to_canonical_equality(tmp_path):
    job = _bremen_job(tmp_path)
    try:
        std = _owner_reports_service.get_job_report(job.job_id, "bremen")["report"]["standard_result"]
        runtime_metrics = job.workflow_runs["bremen"].result_summary["model_metrics"]
        # Source-to-canonical equality through the ModelRuntime result transport.
        assert std["model_metrics"]["sensitivity"] == runtime_metrics["sensitivity"]
        assert std["model_metrics"]["specificity"] == runtime_metrics["specificity"]
        assert std["model_metrics"]["sensitivity"] == 0.9516129032258065
        assert std["model_metrics"]["specificity"] == 0.391304347826087
        # The normalized metadata rides the runtime result, not job context.
        assert job.workflow_runs["bremen"].result_summary["source_metadata"]["patient_age"] == 44
    finally:
        _reset()


def test_bremen_model_method_from_package_architecture(tmp_path):
    job = _bremen_job(tmp_path)
    try:
        std = _owner_reports_service.get_job_report(job.job_id, "bremen")["report"]["standard_result"]
        assert std["model_method"] == (
            "median_imputer_standard_scaler_balanced_logistic_regression"
        )
        assert std["model_method"] != std["model_version"]
    finally:
        _reset()


def test_bremen_metrics_absent_preserves_none(tmp_path):
    """A package without metrics keeps explicit absence (null)."""
    job = _bremen_job(tmp_path, package=copy.deepcopy(MODEL))
    try:
        std = _owner_reports_service.get_job_report(job.job_id, "bremen")["report"]["standard_result"]
        assert std["model_metrics"] == {"sensitivity": None, "specificity": None}
        # model_method falls back to the documented model_method rule.
        assert std["model_method"] == std["model_version"]
    finally:
        _reset()


def test_bremen_scan_date_time_offset_preserved_no_fabrication(tmp_path):
    _reset()
    entry = _bremen_entry()
    registry.initialize_registry(registry.ModelRegistry(
        entries=(entry,), catalog_status="available", available_count=1,
        candidate_count=1,
    ))
    h5_path = _bremen_h5(
        tmp_path / "bremen_tz.h5", started_at="2025-05-28T10:19:55.123+02:00",
    )
    try:
        job = jobs.create_analysis_job(
            h5_path=h5_path, workflow_id="bremen", model_id="bremen-meta",
            patient_display_name="Nova_227",
        )
        std = _owner_reports_service.get_job_report(job.job_id, "bremen")["report"]["standard_result"]
        assert std["scan_date_time"] == "2025-05-28T10:19:55+02:00"
    finally:
        _reset()


# ---------------------------------------------------------------------------
# Aramina integration + metrics
# ---------------------------------------------------------------------------


def _aramina_entry(tmp_path):
    from sklearn.linear_model import LogisticRegression

    def _lr1(n_features=10):
        rng = np.random.RandomState(42)
        return LogisticRegression(random_state=0).fit(
            rng.rand(4, n_features), [0, 0, 1, 1],
        )

    X = np.array([
        [0.1, 0., 0., 1., 2., 3., 1., 1.],
        [0.8, 0., 0., 2., 4., 6., 2., 1.],
        [0.3, 0., 0., 0.5, 1., 1.5, 0.5, 0.],
        [0.9, 0., 0., 3., 6., 9., 3., 1.],
    ])
    final = LogisticRegression(random_state=0).fit(X, [0, 0, 1, 1])

    package = {
        "kind": aramina_manifest.ARTIFACT_KIND,
        "version": "0.3",
        "model_type": "m2q_gated_target_case",
        "model_columns": [],
        "model_identity": {"name": aramina_manifest.MODEL_NAME, "version": "0.2.13-beta"},
        "models": {
            "selected_model": {
                "lr1_model": _lr1(),
                "final_model": final,
                "thresholds": {"threshold_target": 0.5},
                "feature_columns": list(aramina_manifest.FINAL_FEATURE_COLUMNS),
                "class_definition": {"0": "low_risk", "1": "high_risk"},
                "symmetry_policy": "mirror_contralateral",
                "prediction_reference_scores": {},
                "tissue_risk_assessment": {},
                "final_fit_training_metrics": {},
            },
        },
        "model_descriptions": {},
        "feature_schema": {},
        "warnings": [],
        "dataset_summary": {},
        "training_config_yaml": "",
        "prediction_preprocessing_yaml": "steps: []",
        "prediction_contract_yaml": "output: risk_score",
        "model_definition_yaml": "",
        # Active artifact's held-out evaluation (PR0159 authoritative source).
        "model_performance": {
            "evaluation_available": True,
            "evaluation_method": "repeated_stratified_kfold",
            "held_out_metrics": {
                "sensitivity": {"mean": 0.8175, "std": 0.099},
                "specificity": {"mean": 0.3763, "std": 0.13254},
            },
        },
        "final_fit_training_metrics": {},
        "evaluation": {},
        "metadata": {},
        "reproducibility": {},
    }
    path = tmp_path / "aramina.joblib"
    joblib.dump(package, path)
    return registry.RegistryModelEntry(
        model_id="aramina-meta", display_name="Aramina", workflow_id="aramina",
        model_version="0.2.13-beta", artifact_type=aramina_manifest.ARTIFACT_TYPE,
        feature_schema_version="v0.1", decision_policy_id="aramina_policy",
        decision_policy_version="v0.1", technical_ready=True, _package={},
        _artifact_path=str(path),
        _checksum=hashlib.sha256(path.read_bytes()).hexdigest(),
        _clinical_stage="research draft",
    )


def test_aramina_standard_result_receives_extracted_h5_metadata(tmp_path):
    _reset()
    entry = _aramina_entry(tmp_path)
    registry.initialize_registry(registry.ModelRegistry(
        entries=(entry,), catalog_status="available", available_count=1,
        candidate_count=1,
    ))
    h5_path = _aramina_h5(tmp_path / "aramina.h5")
    job = jobs.create_analysis_job(
        model_id=entry.model_id, h5_path=h5_path,
        aramina_request=AnalysisParameters(
            container_id="c", source_id="s", patient_id="p1", target_side="left",
            analysis_author="Aramina Author", prediction_comment="",
        ),
        patient_display_name="p1",
    workflow_id="bremen")
    try:
        assert job.overall_status == "completed"
        std = _owner_reports_service.get_job_report(job.job_id, "aramina")["report"]["standard_result"]
        _assert_standard_metadata(std)
        assert std["patient_id"] == "p1"
    finally:
        _reset()


def test_aramina_metrics_source_to_canonical_equality(tmp_path):
    _reset()
    entry = _aramina_entry(tmp_path)
    registry.initialize_registry(registry.ModelRegistry(
        entries=(entry,), catalog_status="available", available_count=1,
        candidate_count=1,
    ))
    h5_path = _aramina_h5(tmp_path / "aramina.h5")
    job = jobs.create_analysis_job(
        model_id=entry.model_id, h5_path=h5_path,
        aramina_request=AnalysisParameters(
            container_id="c", source_id="s", patient_id="p1", target_side="left",
            analysis_author="Aramina Author", prediction_comment="",
        ),
        patient_display_name="p1",
    workflow_id="bremen")
    try:
        std = _owner_reports_service.get_job_report(job.job_id, "aramina")["report"]["standard_result"]
        runtime_metrics = job.workflow_runs["aramina"].result_summary["model_metrics"]
        assert std["model_metrics"]["sensitivity"] == runtime_metrics["sensitivity"]
        assert std["model_metrics"]["specificity"] == runtime_metrics["specificity"]
        assert std["model_metrics"]["sensitivity"] == 0.8175
        assert std["model_metrics"]["specificity"] == 0.3763
        # model_method from the active artifact's model_type field.
        assert std["model_method"] == "m2q_gated_target_case"
    finally:
        _reset()


# ---------------------------------------------------------------------------
# PR0158a stability retained
# ---------------------------------------------------------------------------


def test_pr0158a_repeated_get_stability_retained(tmp_path):
    job = _bremen_job(tmp_path)
    try:
        first = _owner_reports_service.get_job_report(job.job_id, "bremen")["report"]
        second = _owner_reports_service.get_job_report(job.job_id, "bremen")["report"]
        assert first["standard_result"]["report_id"] == second["standard_result"]["report_id"]
        assert first["standard_result"]["created_at"] == second["standard_result"]["created_at"]
        assert first["standard_result"] == second["standard_result"]
    finally:
        _reset()
