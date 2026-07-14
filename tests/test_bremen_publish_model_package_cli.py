"""Tests for the publish_model_package CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _create_synthetic_artifact(tmp_path: Path) -> Path:
    """Create a minimal synthetic training artifact joblib at tmp_path."""
    import hashlib
    from joblib import dump

    artifact = {
        "kind": "bremen_training_artifact",
        "version": "0.1.0",
        "created_at": "2026-07-04T12:00:00Z",
        "model_type": "patient_m0_m1_m2_logistic_set",
        "models": {"M0": {"model": "LogisticRegression"}},
        "thresholds": {"M0": 0.45},
        "model_descriptions": {"M0": {"type": "LogisticRegression"}},
        "feature_schema": ["sigma_l1"],
        "warnings": [],
        "training_config": {"training": {"name": "test"}},
        "training_config_yaml": "training:\n  name: test\n",
        "training_config_text": "training:\n  name: test\n",
        "training_config_sha256": hashlib.sha256(
            b"training:\n  name: test\n"
        ).hexdigest(),
        "input_dataframe_joblib_sha256": "a" * 64,
        "dataset_summary": {"n_patients": 10},
        "feature_table": {},
        "metric_summary": {},
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

    path = tmp_path / "training_artifact.joblib"
    dump(artifact, path)
    return path


class TestCliHelp:
    def test_cli_help_works(self):
        """python -m bremen.training.publish_model_package --help exits 0."""
        result = subprocess.run(
            [sys.executable, "-m", "bremen.training.publish_model_package", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"CLI --help failed: {result.stderr}"
        )
        assert "--training-artifact" in result.stdout
        assert "--output-dir" in result.stdout
        assert "--model-version" in result.stdout
        assert "--feature-schema-version" in result.stdout
        assert "--threshold-version" in result.stdout
        assert "--qc-criteria-version" in result.stdout


class TestCliMissingFlags:
    def test_cli_missing_required_flags_errors(self):
        """Calling CLI without required flags exits non-zero."""
        result = subprocess.run(
            [sys.executable, "-m", "bremen.training.publish_model_package"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, (
            "CLI without flags should exit non-zero"
        )


class TestCliDryRun:
    def test_cli_dry_run_with_synthetic_artifact(self, tmp_path: Path):
        """CLI dry-run returns JSON summary on stdout."""
        artifact_path = _create_synthetic_artifact(tmp_path)
        output_dir = tmp_path / "staged"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bremen.training.publish_model_package",
                "--training-artifact", str(artifact_path),
                "--output-dir", str(output_dir),
                "--model-version", "1.0.0",
                "--feature-schema-version", "1.0",
                "--threshold-version", "v1",
                "--qc-criteria-version", "1.0",
                "--threshold-key", "M0",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"CLI dry-run failed: {result.stderr}"
        )

        summary = json.loads(result.stdout)
        assert "manifest_fields" in summary
        assert summary["manifest_fields"]["model_version"] == "1.0.0"
        assert summary["files_written"] is False

    def test_cli_does_not_write_files_by_default(self, tmp_path: Path):
        """Default dry-run mode does not write staged files."""
        artifact_path = _create_synthetic_artifact(tmp_path)
        output_dir = tmp_path / "staged"

        subprocess.run(
            [
                sys.executable,
                "-m",
                "bremen.training.publish_model_package",
                "--training-artifact", str(artifact_path),
                "--output-dir", str(output_dir),
                "--model-version", "1.0.0",
                "--feature-schema-version", "1.0",
                "--threshold-version", "v1",
                "--qc-criteria-version", "1.0",
            ],
            capture_output=True,
            text=True,
        )

        assert not output_dir.exists(), (
            "Output dir should not exist in dry-run mode"
        )

    def test_cli_stages_package_with_no_dry_run(self, tmp_path: Path):
        """CLI with --no-dry-run writes manifest.json and model file."""
        artifact_path = _create_synthetic_artifact(tmp_path)
        output_dir = tmp_path / "staged"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bremen.training.publish_model_package",
                "--training-artifact", str(artifact_path),
                "--output-dir", str(output_dir),
                "--model-version", "1.0.0",
                "--feature-schema-version", "1.0",
                "--threshold-version", "v1",
                "--qc-criteria-version", "1.0",
                "--no-dry-run",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"CLI --no-dry-run failed: {result.stderr}"
        )

        assert (output_dir / "manifest.json").is_file()
        manifest = json.loads(
            (output_dir / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["model_version"] == "1.0.0"
        assert manifest["artifact_type"] == "bremen.joblib.model_package"
