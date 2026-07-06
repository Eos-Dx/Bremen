"""Tests for v0.1 model package publication."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from bremen.model_package import EXPECTED_ARTIFACT_TYPE, validate_model_package
from bremen.training.publish_v01 import _sha256, _build_manifest, MANIFEST_FILENAME


def _create_synthetic_joblib(tmp_path: Path) -> Path:
    """Create a minimal synthetic .joblib file and return its path."""
    import joblib
    path = tmp_path / "bremen_v0.1.joblib"
    data = {"coef": [0.1, 0.2, 0.3], "intercept": 0.0}
    joblib.dump(data, path)
    return path


class TestV01Publish:
    def test_v01_publish_dry_run_does_not_write_files(self, tmp_path: Path):
        """Dry-run does not write output files."""
        joblib_path = _create_synthetic_joblib(tmp_path)
        output_dir = tmp_path / "staged"

        result = subprocess.run(
            [
                sys.executable, "-m", "bremen.training.publish_v01",
                "--joblib-path", str(joblib_path),
                "--output-dir", str(output_dir),
                "--feature-schema-version", "v0.1",
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "DRY RUN" in result.stdout
        assert not output_dir.exists(), "Output dir must not exist in dry-run"

    def test_v01_publish_stages_files(self, tmp_path: Path):
        """--no-dry-run writes manifest.json and model file."""
        joblib_path = _create_synthetic_joblib(tmp_path)
        output_dir = tmp_path / "staged"

        result = subprocess.run(
            [
                sys.executable, "-m", "bremen.training.publish_v01",
                "--joblib-path", str(joblib_path),
                "--output-dir", str(output_dir),
                "--feature-schema-version", "v0.1",
                "--no-dry-run",
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert (output_dir / "manifest.json").is_file()
        assert (output_dir / "bremen_v0.1.joblib").is_file()

    def test_v01_manifest_has_correct_artifact_type(self, tmp_path: Path):
        """Manifest artifact_type is bremen.joblib.model_package."""
        joblib_path = _create_synthetic_joblib(tmp_path)
        output_dir = tmp_path / "staged"

        subprocess.run(
            [
                sys.executable, "-m", "bremen.training.publish_v01",
                "--joblib-path", str(joblib_path),
                "--output-dir", str(output_dir),
                "--feature-schema-version", "v0.1",
                "--no-dry-run",
            ],
            capture_output=True, text=True,
        )

        manifest = json.loads(
            (output_dir / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["artifact_type"] == EXPECTED_ARTIFACT_TYPE

    def test_v01_checksum_matches_staged_file(self, tmp_path: Path):
        """SHA-256 of staged joblib matches manifest checksum."""
        joblib_path = _create_synthetic_joblib(tmp_path)
        expected_checksum = hashlib.sha256(joblib_path.read_bytes()).hexdigest()
        output_dir = tmp_path / "staged"

        subprocess.run(
            [
                sys.executable, "-m", "bremen.training.publish_v01",
                "--joblib-path", str(joblib_path),
                "--output-dir", str(output_dir),
                "--feature-schema-version", "v0.1",
                "--no-dry-run",
            ],
            capture_output=True, text=True,
        )

        manifest = json.loads(
            (output_dir / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["model_checksum"] == expected_checksum

    def test_v01_model_filename_is_relative(self, tmp_path: Path):
        """model_filename must not be absolute."""
        joblib_path = _create_synthetic_joblib(tmp_path)
        output_dir = tmp_path / "staged"

        subprocess.run(
            [
                sys.executable, "-m", "bremen.training.publish_v01",
                "--joblib-path", str(joblib_path),
                "--output-dir", str(output_dir),
                "--feature-schema-version", "v0.1",
                "--no-dry-run",
            ],
            capture_output=True, text=True,
        )

        manifest = json.loads(
            (output_dir / "manifest.json").read_text(encoding="utf-8")
        )
        assert not manifest["model_filename"].startswith("/")

    def test_v01_missing_joblib_file_rejected(self, tmp_path: Path):
        """Non-existent joblib path exits non-zero."""
        result = subprocess.run(
            [
                sys.executable, "-m", "bremen.training.publish_v01",
                "--joblib-path", str(tmp_path / "nonexistent.joblib"),
                "--output-dir", str(tmp_path / "staged"),
                "--feature-schema-version", "v0.1",
            ],
            capture_output=True, text=True,
        )
        assert result.returncode != 0

    def test_v01_requires_feature_schema_version(self, tmp_path: Path):
        """Missing --feature-schema-version exits non-zero."""
        joblib_path = _create_synthetic_joblib(tmp_path)
        result = subprocess.run(
            [
                sys.executable, "-m", "bremen.training.publish_v01",
                "--joblib-path", str(joblib_path),
                "--output-dir", str(tmp_path / "staged"),
            ],
            capture_output=True, text=True,
        )
        assert result.returncode != 0

    def test_v01_cli_help_works(self):
        """--help exits 0."""
        result = subprocess.run(
            [sys.executable, "-m", "bremen.training.publish_v01", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "--joblib-path" in result.stdout

    def test_v01_validate_model_package_accepts_staged(self, tmp_path: Path):
        """Staged package passes validate_model_package()."""
        joblib_path = _create_synthetic_joblib(tmp_path)
        output_dir = tmp_path / "staged"

        subprocess.run(
            [
                sys.executable, "-m", "bremen.training.publish_v01",
                "--joblib-path", str(joblib_path),
                "--output-dir", str(output_dir),
                "--feature-schema-version", "v0.1",
                "--no-dry-run",
            ],
            capture_output=True, text=True,
        )

        result = validate_model_package(output_dir)
        assert result["artifact_type"] == EXPECTED_ARTIFACT_TYPE
        assert result["model_version"] == "v0.1"


# ---------------------------------------------------------------------------
# Real artifact smoke test (opt-in, skipped by default)
# ---------------------------------------------------------------------------

REAL_JOBLIB_VAR = "BREMEN_V01_JOBLIB_PATH"


@pytest.mark.skipif(
    not bool(__import__("os").environ.get(REAL_JOBLIB_VAR)),
    reason="Set BREMEN_V01_JOBLIB_PATH to run real artifact smoke test",
)
def test_v01_real_artifact_smoke():
    """Smoke test for the real v0.1 artifact. Skipped by default.

    Set BREMEN_V01_JOBLIB_PATH=/path/to/bremen_v0.1.joblib to enable.
    Requires a real artifact file provided by a human outside the repo.
    """
    import os as _os  # noqa: PLC0415

    joblib_path = _os.environ[REAL_JOBLIB_VAR]
    assert Path(joblib_path).is_file(), f"Artifact not found: {joblib_path}"

    result = subprocess.run(
        [
            sys.executable, "-m", "bremen.training.publish_v01",
            "--joblib-path", joblib_path,
            "--output-dir", "/tmp/bremen-v01-smoke",
            "--feature-schema-version", "v0.1",
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert "Checksum" in result.stdout
    assert "DRY RUN" in result.stdout
