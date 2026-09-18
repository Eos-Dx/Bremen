"""PR0159 — model-package metadata adapters → normalized contract tests.

The corrected architecture:

    model-specific parser/preprocessing
    -> model-package adapter (Bremen / Aramina)
    -> common normalized metadata contract (bremen.contracts.model_runtime)
    -> ModelRuntime transport (RuntimePrediction)
    -> Standard Result mapper

These tests prove that each model package maps ITS OWN container/artifact
representation into the SAME normalized canonical contract, and that the API /
mapper code consumes only the normalized names (no model-specific source field
names, H5 paths, artifact paths, or preprocessing dataframe columns).

Each model package owns its parser; the platform never parses model-specific
H5 metadata.  Synthetic deterministic H5 files only; no supplied patient H5
binaries.
"""
from __future__ import annotations

import json
from pathlib import Path

import h5py

from bremen.contracts.model_runtime import (
    ModelMetadata,
    ModelMetrics,
    SourceMetadata,
)
from bremen.model_packages.aramina_v0213 import source_metadata as aramina_adapter
from bremen.model_packages.bremen_v01 import source_metadata as bremen_adapter
from bremen.model_packages.bremen_v01 import manifest as bremen_manifest
from bremen.model_packages.aramina_v0213 import manifest as aramina_manifest


# ---------------------------------------------------------------------------
# Fixture builders (deterministic temporary H5 containers)
# ---------------------------------------------------------------------------


def _write_metadata_h5(
    path: Path,
    *,
    age: object = 44,
    started_at: object = "2025-05-28 10:19:55",
    operator: object = "backfill",
    producer_version: object = "0.1.0",
    schema_version: object = "0.3",
    human1_versions: list[object] | None = None,
) -> Path:
    """Write a session-layout H5 carrying the canonical source metadata."""
    with h5py.File(path, "w") as f:
        f["/session/sample/sample_type"] = "left breast"
        f["/session/sample/patient_name"] = "Nova_Synth"
        if age is not None:
            f["/session/sample"].attrs["age"] = age
        if started_at is not None:
            f["/session"].attrs["started_at"] = started_at
        if operator is not None:
            f["/session"].attrs["operator_username"] = operator
        if producer_version is not None:
            f["/session"].attrs["producer_version"] = producer_version
        f["/session"].attrs["producer_software"] = "omniscan-backfill"
        f["/session"].attrs["schema_version"] = schema_version
        sets = f.create_group("/session/sets")
        versions = human1_versions if human1_versions is not None else ["v1.0.1"]
        for i, version in enumerate(versions, start=1):
            set_group = sets.create_group(f"set_{i:03d}_sample_main")
            if version is not None:
                payload = {"backfill_provenance": {"human1_version": version}}
                set_group.create_dataset("metadata", data=json.dumps(payload))
    return path


# ---------------------------------------------------------------------------
# Same canonical contract from different model-package adapters
# ---------------------------------------------------------------------------


def test_bremen_and_aramina_adapters_produce_identical_canonical_source(tmp_path: Path):
    """Both packages map the same container into the same canonical dict."""
    h5_path = _write_metadata_h5(tmp_path / "shared.h5")
    bremen = bremen_adapter.extract_source_metadata(str(h5_path))
    aramina = aramina_adapter.extract_source_metadata(str(h5_path))
    assert isinstance(bremen, SourceMetadata)
    assert isinstance(aramina, SourceMetadata)
    assert bremen.to_dict() == aramina.to_dict()
    assert bremen.to_dict() == {
        "patient_age": 44,
        "referring_physician": "",
        "scan_date_time": "2025-05-28 10:19:55",
        "operator_id": "backfill",
        "hardware_version": "v1.0.1",
        # No authoritative package-owned Eoscan version source exists:
        # producer_version (omniscan-backfill) is NOT promoted.
        "eoscan_version": None,
    }


def test_aramina_frame_age_is_model_owned_source(tmp_path: Path):
    """Aramina's patient_age may come from its own preprocessing output."""
    h5_path = _write_metadata_h5(tmp_path / "frame.h5", age=44)
    meta = aramina_adapter.extract_source_metadata(str(h5_path), frame_age=47)
    assert meta.patient_age == 47
    assert meta.to_dict()["patient_age"] == 47


def test_mapper_consumes_only_normalized_names():
    """API/mapper code never needs model-specific source field names."""
    import inspect

    from bremen.platform.reports import mapper
    source = inspect.getsource(mapper)
    # The mapper references only the canonical normalized keys.
    assert "source_metadata" in source
    assert "model_metadata" in source
    assert "model_metrics" in source
    for model_specific in ("operator_username", "producer_version", "started_at",
                           "backfill_provenance", "human1_version", "model_type",
                           "held_out_metrics", "final_fit_training_metrics",
                           "portable_logreg", "container_path", "h5_path"):
        assert model_specific not in source, f"mapper must not know {model_specific}"


def test_package_parsers_are_model_owned_not_api():
    """No API-level H5 metadata parser exists; parsers live in the packages."""
    from pathlib import Path as _Path
    api_sources = list(_Path("src/bremen/api").glob("*.py"))
    for src in api_sources:
        text = src.read_text(encoding="utf-8")
        assert "extract_h5_source_metadata" not in text
        assert "/session/sample\"].attrs" not in text
    assert not _Path("src/bremen/api/h5_source_metadata.py").exists()
    assert _Path("src/bremen/model_packages/bremen_v01/source_metadata.py").exists()
    assert _Path("src/bremen/model_packages/aramina_v0213/source_metadata.py").exists()


# ---------------------------------------------------------------------------
# Bremen package adapter — source metadata fields
# ---------------------------------------------------------------------------


def test_bremen_patient_age(tmp_path: Path):
    h5_path = _write_metadata_h5(tmp_path / "b_age.h5", age=44)
    assert bremen_adapter.extract_source_metadata(str(h5_path)).patient_age == 44


def test_bremen_scan_date_time_raw_and_offset(tmp_path: Path):
    naive = bremen_adapter.extract_source_metadata(
        str(_write_metadata_h5(tmp_path / "b_scan.h5", started_at="2025-05-28 10:19:55")),
    )
    assert naive.scan_date_time == "2025-05-28 10:19:55"
    offset = bremen_adapter.extract_source_metadata(
        str(_write_metadata_h5(tmp_path / "b_scan_tz.h5", started_at="2025-05-28T10:19:55+02:00")),
    )
    assert offset.scan_date_time == "2025-05-28T10:19:55+02:00"


def test_bremen_operator_id_verbatim(tmp_path: Path):
    h5_path = _write_metadata_h5(tmp_path / "b_op.h5", operator="backfill")
    assert bremen_adapter.extract_source_metadata(str(h5_path)).operator_id == "backfill"


def test_bremen_hardware_version_consensus(tmp_path: Path):
    single = bremen_adapter.extract_source_metadata(
        str(_write_metadata_h5(tmp_path / "b_hw1.h5", human1_versions=["v1.0.1"])),
    )
    assert single.hardware_version == "v1.0.1"
    repeated = bremen_adapter.extract_source_metadata(
        str(_write_metadata_h5(tmp_path / "b_hw2.h5", human1_versions=["v1.1.0", "v1.1.0"])),
    )
    assert repeated.hardware_version == "v1.1.0"
    missing = bremen_adapter.extract_source_metadata(
        str(_write_metadata_h5(tmp_path / "b_hw3.h5", human1_versions=[None, None])),
    )
    assert missing.hardware_version == ""
    conflicting = bremen_adapter.extract_source_metadata(
        str(_write_metadata_h5(tmp_path / "b_hw4.h5", human1_versions=["v1.0.1", "v1.1.0"])),
    )
    assert conflicting.hardware_version == ""


def test_bremen_eoscan_version_not_promoted_from_producer_version(tmp_path: Path):
    """producer_version (omniscan-backfill) is NOT silently used as eoscan."""
    meta = bremen_adapter.extract_source_metadata(
        str(_write_metadata_h5(
            tmp_path / "b_eos.h5", producer_version="0.1.0", schema_version="9.9.9",
        )),
    )
    assert meta.eoscan_version is None
    assert meta.eoscan_version != "0.1.0"
    assert meta.eoscan_version != "9.9.9"


def test_aramina_eoscan_version_not_promoted_from_producer_version(tmp_path: Path):
    """The Aramina adapter equally never promotes producer_version."""
    meta = aramina_adapter.extract_source_metadata(
        str(_write_metadata_h5(
            tmp_path / "a_eos.h5", producer_version="0.1.0", schema_version="9.9.9",
        )),
    )
    assert meta.eoscan_version is None
    assert meta.eoscan_version != "0.1.0"
    assert meta.eoscan_version != "9.9.9"


def test_bremen_source_metadata_fault_tolerant(tmp_path: Path):
    bare = tmp_path / "b_bare.h5"
    with h5py.File(bare, "w") as f:
        f["patient/id"] = "p1"
    meta = bremen_adapter.extract_source_metadata(str(bare))
    assert meta.patient_age is None
    assert meta.scan_date_time == ""
    assert meta.operator_id == ""
    assert meta.hardware_version == ""
    assert meta.eoscan_version is None


# ---------------------------------------------------------------------------
# Bremen package adapter — artifact metadata (model_method + metrics)
# ---------------------------------------------------------------------------


def test_bremen_model_method_from_artifact_architecture():
    package = {
        "model_definition": {
            "architecture": "median_imputer_standard_scaler_balanced_logistic_regression",
        },
    }
    assert bremen_adapter.extract_model_metadata(package).model_method == (
        "median_imputer_standard_scaler_balanced_logistic_regression"
    )


def test_bremen_model_method_absent_is_empty():
    assert bremen_adapter.extract_model_metadata({}).model_method == ""
    assert bremen_adapter.extract_model_metadata(
        {"portable_logreg": {"threshold": 0.5}},
    ).model_method == ""


def test_bremen_model_metrics_from_active_package():
    package = {
        "final_fit_training_metrics": {
            "sensitivity": 0.9516129032258065,
            "specificity": 0.391304347826087,
        },
    }
    metrics = bremen_adapter.extract_model_metrics(package)
    assert metrics.sensitivity == 0.9516129032258065
    assert metrics.specificity == 0.391304347826087


def test_bremen_model_metrics_absent_is_none():
    assert bremen_adapter.extract_model_metrics({}).to_dict() == {
        "sensitivity": None, "specificity": None,
    }
    assert bremen_adapter.extract_model_metrics(
        {"final_fit_training_metrics": {"sensitivity": "not-a-number"}},
    ).to_dict() == {"sensitivity": None, "specificity": None}


# ---------------------------------------------------------------------------
# Aramina package adapter — artifact metadata (model_type + held-out metrics)
# ---------------------------------------------------------------------------


def test_aramina_model_method_from_artifact_model_type():
    package = {"model_type": "m2q_gated_target_case"}
    assert aramina_adapter.extract_model_metadata(package).model_method == "m2q_gated_target_case"


def test_aramina_model_method_absent_is_empty():
    assert aramina_adapter.extract_model_metadata({}).model_method == ""


def test_aramina_model_metrics_from_active_held_out_evaluation():
    package = {
        "model_performance": {
            "held_out_metrics": {
                "sensitivity": {"mean": 0.8175, "std": 0.099},
                "specificity": {"mean": 0.3763, "std": 0.13254},
            },
        },
    }
    metrics = aramina_adapter.extract_model_metrics(package)
    assert metrics.sensitivity == 0.8175
    assert metrics.specificity == 0.3763


def test_aramina_model_metrics_never_hardcoded_from_other_version():
    """No metrics at all -> explicit absence (never a 0.2.12 constant)."""
    assert aramina_adapter.extract_model_metrics({}).to_dict() == {
        "sensitivity": None, "specificity": None,
    }
    assert aramina_adapter.extract_model_metrics(
        {"model_performance": {"held_out_metrics": {}}},
    ).to_dict() == {"sensitivity": None, "specificity": None}


# ---------------------------------------------------------------------------
# Neutral contract transport types
# ---------------------------------------------------------------------------


def test_normalized_contract_types_are_transport_neutral():
    assert SourceMetadata().to_dict() == {
        "patient_age": None, "referring_physician": "", "scan_date_time": "", "operator_id": "",
        "hardware_version": "", "eoscan_version": None,
    }
    assert ModelMetadata().to_dict() == {"model_method": ""}
    assert ModelMetrics().to_dict() == {"sensitivity": None, "specificity": None}


def test_manifests_still_authoritative_for_identity():
    assert bremen_manifest.MODEL_ID == "bremen-paper-reference-v0-2-0"
    assert aramina_manifest.MODEL_ID == "aramina-target-brest-risk"
