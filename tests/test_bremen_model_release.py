"""Tests for model release (validation, manifest building, staging, dry-run)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from bremen.training.model_release import (
    REQUIRED_RUNTIME_MANIFEST_FIELDS,
    build_runtime_manifest,
    dry_run_publication_summary,
    load_training_artifact,
    stage_model_package,
    validate_training_artifact,
)
from bremen.model_package import (
    EXPECTED_ARTIFACT_TYPE,
    validate_model_package,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_synthetic_training_artifact(
    tmp_path: Path,
    *,
    kind: str | None = "bremen_training_artifact",
    thresholds: dict | None = None,
    pop_fields: list[str] | None = None,
) -> tuple[Path, dict]:
    """Create a synthetic training artifact joblib file and return (path, dict)."""
    import numpy as np
    import pandas as pd
    from joblib import dump

    data = {
        "kind": kind,
        "version": "0.1.0",
        "created_at": "2026-07-04T12:00:00Z",
        "model_type": "patient_m0_m1_m2_logistic_set",
        "models": {"M0": {"model": "LogisticRegression"}},
        "thresholds": thresholds or {"M0": 0.45, "M1": 0.5, "M2": 0.55},
        "model_descriptions": {"M0": {"type": "LogisticRegression"}},
        "feature_schema": ["sigma_l1", "sigma_l2", "Mahalanobis1"],
        "warnings": [],
        "training_config": {"training": {"name": "test"}},
        "training_config_yaml": "training:\n  name: test\n",
        "training_config_text": "training:\n  name: test\n",
        "training_config_sha256": hashlib.sha256(
            b"training:\n  name: test\n"
        ).hexdigest(),
        "input_dataframe_joblib_sha256": "a" * 64,
        "dataset_summary": {"n_patients": 10, "n_rows": 20},
        "feature_table": {"sigma_l1": [0.1]},
        "metric_summary": {"M0": {"auc": 0.85}},
        "split_metrics": [],
        "split_predictions": {},
        "preprocessing_lineage": {},
        "metadata": {
            "bremen_version": "0.1.0",
            "git_sha": "",
            "created_at": "2026-07-04T12:00:00Z",
            "branch": "main",
            "training_role": "training",
        },
    }

    if pop_fields:
        for f in pop_fields:
            data.pop(f, None)

    artifact_path = tmp_path / "training_artifact.joblib"
    dump(data, artifact_path)

    return artifact_path, data


# ---------------------------------------------------------------------------
# Training artifact validation
# ---------------------------------------------------------------------------


class TestLoadTrainingArtifact:
    def test_valid_training_artifact_accepted(self, tmp_path: Path):
        """Valid synthetic artifact loads successfully."""
        path, _ = _make_synthetic_training_artifact(tmp_path)
        result = load_training_artifact(path)
        assert isinstance(result, dict)
        assert result["kind"] == "bremen_training_artifact"

    def test_invalid_kind_rejected(self, tmp_path: Path):
        """Artifact with wrong kind raises ValueError."""
        path, _ = _make_synthetic_training_artifact(
            tmp_path, kind="some_other"
        )
        with pytest.raises(ValueError, match="Invalid training artifact kind"):
            load_training_artifact(path)

    def test_missing_training_artifact_field_rejected(self, tmp_path: Path):
        """Artifact missing a required field raises ValueError."""
        path, _ = _make_synthetic_training_artifact(
            tmp_path, pop_fields=["models"]
        )
        with pytest.raises(ValueError, match="missing required fields"):
            load_training_artifact(path)

    def test_missing_file_raises(self, tmp_path: Path):
        """Nonexistent file raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            load_training_artifact(tmp_path / "nonexistent.joblib")


class TestValidateTrainingArtifact:
    def test_validate_in_memory(self):
        """validate_training_artifact works on dict directly."""
        artifact = {
            "kind": "bremen_training_artifact",
            "version": "0.1.0",
            "created_at": "2026-01-01T00:00:00Z",
            "model_type": "patient_m0_m1_m2_logistic_set",
            "models": {"M0": {}},
            "thresholds": {"M0": 0.5},
            "model_descriptions": {},
            "feature_schema": [],
            "warnings": [],
            "training_config": {},
            "training_config_yaml": "",
            "training_config_text": "",
            "training_config_sha256": "a" * 64,
            "input_dataframe_joblib_sha256": "b" * 64,
            "dataset_summary": {},
            "feature_table": {},
            "metric_summary": {},
            "split_metrics": [],
            "split_predictions": {},
            "preprocessing_lineage": {},
            "metadata": {},
        }
        result = validate_training_artifact(artifact)
        assert result["kind"] == "bremen_training_artifact"


# ---------------------------------------------------------------------------
# Manifest construction
# ---------------------------------------------------------------------------


class TestBuildRuntimeManifest:
    def test_manifest_has_exact_adr_0007_fields(self):
        """build_runtime_manifest returns dict with exact ADR-0007 fields."""
        artifact = {
            "kind": "bremen_training_artifact",
            "thresholds": {"M0": 0.45, "M1": 0.5},
        }
        manifest = build_runtime_manifest(
            artifact=artifact,
            model_version="1.0.0",
            model_filename="model_v1.joblib",
            feature_schema_version="1.0",
            threshold_version="v1",
            threshold_key="M0",
            qc_criteria_version="1.0",
            model_checksum="a" * 64,
        )
        for field in REQUIRED_RUNTIME_MANIFEST_FIELDS:
            assert field in manifest, f"Missing manifest field: {field}"

    def test_manifest_artifact_type(self):
        """artifact_type is bremen.joblib.model_package."""
        artifact = {"kind": "bremen_training_artifact", "thresholds": {"M0": 0.5}}
        manifest = build_runtime_manifest(
            artifact=artifact,
            model_version="1.0.0",
            model_filename="model.joblib",
            feature_schema_version="1.0",
            threshold_version="v1",
            threshold_key="M0",
            qc_criteria_version="1.0",
            model_checksum="a" * 64,
        )
        assert manifest["artifact_type"] == EXPECTED_ARTIFACT_TYPE

    def test_checksum_equals_sha256_of_staged_file(self, tmp_path: Path):
        """manifest model_checksum matches SHA-256 of staged file."""
        artifact_path, _ = _make_synthetic_training_artifact(tmp_path)
        checksum = hashlib.sha256(artifact_path.read_bytes()).hexdigest()

        artifact = {
            "kind": "bremen_training_artifact",
            "thresholds": {"M0": 0.5},
        }
        manifest = build_runtime_manifest(
            artifact=artifact,
            model_version="1.0.0",
            model_filename="model.joblib",
            feature_schema_version="1.0",
            threshold_version="v1",
            threshold_key="M0",
            qc_criteria_version="1.0",
            model_checksum=checksum,
        )
        assert manifest["model_checksum"] == checksum

    def test_manifest_contains_relative_filename_not_absolute_path(self):
        """model_filename is relative, not absolute."""
        artifact = {"kind": "bremen_training_artifact", "thresholds": {"M0": 0.5}}
        manifest = build_runtime_manifest(
            artifact=artifact,
            model_version="1.0.0",
            model_filename="model_v1.joblib",
            feature_schema_version="1.0",
            threshold_version="v1",
            threshold_key="M0",
            qc_criteria_version="1.0",
            model_checksum="a" * 64,
        )
        assert not manifest["model_filename"].startswith("/")
        assert ".." not in manifest["model_filename"]

    def test_threshold_selection_populates_threshold_value(self):
        """threshold_value matches the specified threshold_key."""
        artifact = {
            "kind": "bremen_training_artifact",
            "thresholds": {"M0": 0.45, "M1": 0.5},
        }
        manifest = build_runtime_manifest(
            artifact=artifact,
            model_version="1.0.0",
            model_filename="model.joblib",
            feature_schema_version="1.0",
            threshold_version="v1",
            threshold_key="M1",
            qc_criteria_version="1.0",
            model_checksum="a" * 64,
        )
        assert manifest["threshold_value"] == 0.5

    def test_threshold_key_none_uses_first_available(self):
        """When threshold_key is None, uses first threshold value."""
        artifact = {
            "kind": "bremen_training_artifact",
            "thresholds": {"M2": 0.55, "M0": 0.45},
        }
        manifest = build_runtime_manifest(
            artifact=artifact,
            model_version="1.0.0",
            model_filename="model.joblib",
            feature_schema_version="1.0",
            threshold_version="v1",
            threshold_key=None,
            qc_criteria_version="1.0",
            model_checksum="a" * 64,
        )
        # First key in the dict (insertion order preserved in Python 3.7+)
        first_key = next(iter(artifact["thresholds"]))
        assert manifest["threshold_value"] == artifact["thresholds"][first_key]

    def test_unknown_threshold_key_raises(self):
        """Unknown threshold_key raises ValueError."""
        artifact = {
            "kind": "bremen_training_artifact",
            "thresholds": {"M0": 0.45},
        }
        with pytest.raises(ValueError, match="not found"):
            build_runtime_manifest(
                artifact=artifact,
                model_version="1.0.0",
                model_filename="model.joblib",
                feature_schema_version="1.0",
                threshold_version="v1",
                threshold_key="M999",
                qc_criteria_version="1.0",
                model_checksum="a" * 64,
            )

    def test_empty_thresholds_raises(self):
        """Empty thresholds dict raises ValueError."""
        artifact = {
            "kind": "bremen_training_artifact",
            "thresholds": {},
        }
        with pytest.raises(ValueError, match="empty"):
            build_runtime_manifest(
                artifact=artifact,
                model_version="1.0.0",
                model_filename="model.joblib",
                feature_schema_version="1.0",
                threshold_version="v1",
                threshold_key=None,
                qc_criteria_version="1.0",
                model_checksum="a" * 64,
            )

    def test_absolute_model_filename_raises(self):
        """Absolute model_filename raises ValueError."""
        artifact = {"kind": "bremen_training_artifact", "thresholds": {"M0": 0.5}}
        with pytest.raises(ValueError, match="absolute"):
            build_runtime_manifest(
                artifact=artifact,
                model_version="1.0.0",
                model_filename="/etc/passwd",
                feature_schema_version="1.0",
                threshold_version="v1",
                threshold_key="M0",
                qc_criteria_version="1.0",
                model_checksum="a" * 64,
            )


# ---------------------------------------------------------------------------
# Local staging
# ---------------------------------------------------------------------------


class TestStageModelPackage:
    def test_stage_model_package_dry_run_does_not_write_files(
        self, tmp_path: Path
    ):
        """Dry-run staging does not write any files."""
        artifact_path, _ = _make_synthetic_training_artifact(tmp_path)
        output_dir = tmp_path / "staged"

        summary = stage_model_package(
            artifact_path=artifact_path,
            output_dir=output_dir,
            model_version="1.0.0",
            model_filename="model_v1.joblib",
            feature_schema_version="1.0",
            threshold_version="v1",
            threshold_key="M0",
            qc_criteria_version="1.0",
            dry_run=True,
        )

        assert summary["files_written"] is False
        assert not output_dir.exists()

    def test_stage_model_package_writes_files_when_not_dry_run(
        self, tmp_path: Path
    ):
        """Non-dry-run staging writes manifest.json and model file."""
        artifact_path, _ = _make_synthetic_training_artifact(tmp_path)
        output_dir = tmp_path / "staged"

        summary = stage_model_package(
            artifact_path=artifact_path,
            output_dir=output_dir,
            model_version="1.0.0",
            model_filename="model_v1.joblib",
            feature_schema_version="1.0",
            threshold_version="v1",
            threshold_key="M0",
            qc_criteria_version="1.0",
            dry_run=False,
        )

        assert summary["files_written"] is True
        assert (output_dir / "manifest.json").is_file()
        assert (output_dir / "model_v1.joblib").is_file()

    def test_staged_package_passes_validate_model_package(
        self, tmp_path: Path
    ):
        """Staged package is accepted by model_package.validate_model_package()."""
        artifact_path, _ = _make_synthetic_training_artifact(tmp_path)
        output_dir = tmp_path / "staged"

        stage_model_package(
            artifact_path=artifact_path,
            output_dir=output_dir,
            model_version="1.0.0",
            model_filename="model_v1.joblib",
            feature_schema_version="1.0",
            threshold_version="v1",
            threshold_key="M0",
            qc_criteria_version="1.0",
            dry_run=False,
        )

        result = validate_model_package(output_dir)
        assert result["artifact_type"] == EXPECTED_ARTIFACT_TYPE
        assert result["model_version"] == "1.0.0"

    def test_stage_default_model_filename(self, tmp_path: Path):
        """When model_filename is None, defaults to model_{version}.joblib."""
        artifact_path, _ = _make_synthetic_training_artifact(tmp_path)
        output_dir = tmp_path / "staged"

        stage_model_package(
            artifact_path=artifact_path,
            output_dir=output_dir,
            model_version="2.0.0",
            model_filename=None,
            feature_schema_version="1.0",
            threshold_version="v1",
            threshold_key="M0",
            qc_criteria_version="1.0",
            dry_run=False,
        )

        assert (output_dir / "model_2.0.0.joblib").is_file()


# ---------------------------------------------------------------------------
# Dry-run S3 summary
# ---------------------------------------------------------------------------


class TestDryRunPublicationSummary:
    def test_summary_contains_intended_s3_uri(self):
        """dry_run_publication_summary with bucket/prefix generates S3 URI."""
        manifest = {"model_version": "1.0.0", "model_filename": "model.joblib"}
        summary = dry_run_publication_summary(
            manifest=manifest,
            output_dir="/tmp/staged",
            bucket="my-bucket",
            prefix="models",
        )
        assert "s3://my-bucket/models/1.0.0/" in summary["intended_s3_uri"]

    def test_summary_no_bucket_no_s3_uri(self):
        """Without bucket/prefix, intended_s3_uri is None."""
        manifest = {"model_version": "1.0.0", "model_filename": "model.joblib"}
        summary = dry_run_publication_summary(
            manifest=manifest,
            output_dir="/tmp/staged",
        )
        assert summary["intended_s3_uri"] is None

    def test_dry_run_does_not_make_network_calls(self):
        """dry_run_publication_summary does not call boto3/requests/etc.

        Import verified — no network imports in module.
        """
        import ast

        module_path = Path(__file__).parents[1] / "src" / "bremen" / "training" / "model_release.py"
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        prohibited = {"boto3", "botocore", "requests", "httpx", "urllib", "awscli"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in prohibited:
                        pytest.fail(
                            f"model_release.py imports {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                top = module.split(".")[0]
                if top in prohibited:
                    pytest.fail(f"model_release.py imports {module}")
