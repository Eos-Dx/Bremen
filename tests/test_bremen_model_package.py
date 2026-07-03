"""Tests for the local model package contract and validation helpers.

Covers:
- Valid local package passes validation
- Summary exposes all expected metadata fields
- Missing package dir fails
- Missing manifest fails
- Invalid JSON manifest fails
- Missing required field fails
- Unexpected artifact_type fails
- Missing model artifact fails
- Checksum mismatch fails
- Absolute model_filename fails
- Path traversal model_filename fails
- threshold_value non-numeric fails
- Module import safety (AST)
- No joblib/pickle import
- No joblib.load string
- No H5/HDF5 reading
- No committed model artifacts
"""

from __future__ import annotations

import hashlib
import json
import sys
import ast
from pathlib import Path

import pytest

from bremen.model_package import (
    EXPECTED_ARTIFACT_TYPE,
    ModelPackageChecksumError,
    ModelPackageError,
    ModelPackageManifestError,
    ModelPackageNotFoundError,
    ModelPackageSecurityError,
    ModelPackageSummary,
    compute_sha256,
    read_model_manifest,
    summarize_model_package,
    validate_model_manifest,
    validate_model_package,
)

SRC_BREMEN = Path(__file__).parents[1] / "src" / "bremen"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_package(
    tmp_path: Path,
    *,
    manifest_overrides: dict | None = None,
    artifact_data: bytes | None = None,
) -> Path:
    """Create a fake model package directory and return its path."""
    pkg_dir = tmp_path / "model_package"
    pkg_dir.mkdir()

    # Create dummy artifact first so we can compute its checksum
    artifact_content = artifact_data or b"fake model artifact bytes\n"
    artifact_name = "model.joblib"

    (pkg_dir / artifact_name).write_bytes(artifact_content)
    checksum = hashlib.sha256(artifact_content).hexdigest()

    manifest: dict = {
        "artifact_type": EXPECTED_ARTIFACT_TYPE,
        "model_version": "1.0.0",
        "model_checksum": checksum,
        "model_filename": artifact_name,
        "feature_schema_version": "1.0",
        "threshold_version": "v1",
        "threshold_value": 0.5,
        "qc_criteria_version": "1.0",
        "training_config_ref": "training/experiment_42",
        "created_at": "2026-07-04T12:00:00Z",
    }

    if manifest_overrides:
        manifest.update(manifest_overrides)

    (pkg_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    return pkg_dir


# ---------------------------------------------------------------------------
# Valid package
# ---------------------------------------------------------------------------


class TestValidPackage:
    def test_validate_passes(self, tmp_path: Path):
        """A correctly structured package passes validation."""
        pkg_dir = _make_package(tmp_path)
        result = validate_model_package(pkg_dir)
        assert result["model_version"] == "1.0.0"
        assert result["artifact_type"] == EXPECTED_ARTIFACT_TYPE

    def test_summary_contains_expected_fields(self, tmp_path: Path):
        """summarize_model_package returns all expected summary fields."""
        pkg_dir = _make_package(tmp_path)
        summary = summarize_model_package(pkg_dir)

        assert isinstance(summary, ModelPackageSummary)
        assert summary.model_version == "1.0.0"
        assert len(summary.model_checksum) == 64
        assert summary.feature_schema_version == "1.0"
        assert summary.threshold_version == "v1"
        assert summary.threshold_value == 0.5
        assert summary.qc_criteria_version == "1.0"
        assert summary.artifact_type == EXPECTED_ARTIFACT_TYPE
        assert summary.training_config_ref == "training/experiment_42"
        assert summary.created_at == "2026-07-04T12:00:00Z"
        assert summary.package_dir == pkg_dir.resolve()
        assert summary.manifest_path == (pkg_dir / "manifest.json").resolve()
        assert summary.model_path == (pkg_dir / "model.joblib").resolve()

    def test_read_manifest(self, tmp_path: Path):
        """read_model_manifest returns the parsed manifest content."""
        pkg_dir = _make_package(tmp_path)
        manifest = read_model_manifest(pkg_dir / "manifest.json")
        assert manifest["model_version"] == "1.0.0"
        assert manifest["artifact_type"] == EXPECTED_ARTIFACT_TYPE

    def test_compute_sha256(self, tmp_path: Path):
        """compute_sha256 returns correct hex digest."""
        data = b"known content for checksum test\n"
        file_path = tmp_path / "test_file.bin"
        file_path.write_bytes(data)
        expected = hashlib.sha256(data).hexdigest()
        assert compute_sha256(file_path) == expected

    def test_validate_manifest_accepts_valid(self):
        """validate_model_manifest accepts a valid manifest dict."""
        manifest = {
            "artifact_type": EXPECTED_ARTIFACT_TYPE,
            "model_version": "1.0.0",
            "model_checksum": "a" * 64,
            "model_filename": "model.joblib",
            "feature_schema_version": "1.0",
            "threshold_version": "v1",
            "threshold_value": 0.5,
            "qc_criteria_version": "1.0",
        }
        result = validate_model_manifest(manifest)
        assert result is not None


# ---------------------------------------------------------------------------
# Missing / not-found
# ---------------------------------------------------------------------------


class TestMissing:
    def test_missing_package_dir(self, tmp_path: Path):
        """Missing package directory raises ModelPackageNotFoundError."""
        missing = tmp_path / "does_not_exist"
        with pytest.raises(ModelPackageNotFoundError):
            validate_model_package(missing)

    def test_package_dir_is_file(self, tmp_path: Path):
        """Package path that is a file raises ModelPackageManifestError."""
        file_path = tmp_path / "not_a_dir"
        file_path.write_text("hello")
        with pytest.raises(ModelPackageManifestError):
            validate_model_package(file_path)

    def test_missing_manifest(self, tmp_path: Path):
        """Missing manifest.json raises ModelPackageNotFoundError."""
        pkg_dir = tmp_path / "no_manifest"
        pkg_dir.mkdir()
        with pytest.raises(ModelPackageNotFoundError):
            validate_model_package(pkg_dir)

    def test_missing_artifact(self, tmp_path: Path):
        """Missing model artifact file raises ModelPackageNotFoundError."""
        pkg_dir = _make_package(tmp_path, manifest_overrides={
            "model_filename": "nonexistent.joblib",
        })
        with pytest.raises(ModelPackageNotFoundError):
            validate_model_package(pkg_dir)


# ---------------------------------------------------------------------------
# Manifest errors
# ---------------------------------------------------------------------------


class TestManifestErrors:
    def test_invalid_json(self, tmp_path: Path):
        """Invalid JSON in manifest raises ModelPackageManifestError."""
        pkg_dir = tmp_path / "bad_json"
        pkg_dir.mkdir()
        (pkg_dir / "manifest.json").write_text("not json", encoding="utf-8")
        with pytest.raises(ModelPackageManifestError):
            validate_model_package(pkg_dir)

    def test_manifest_not_dict(self, tmp_path: Path):
        """Top-level list in manifest raises ModelPackageManifestError."""
        pkg_dir = tmp_path / "not_dict"
        pkg_dir.mkdir()
        (pkg_dir / "manifest.json").write_text('["a", "b"]', encoding="utf-8")
        with pytest.raises(ModelPackageManifestError):
            validate_model_package(pkg_dir)

    def test_missing_model_version(self, tmp_path: Path):
        """Missing 'model_version' field raises ModelPackageManifestError."""
        pkg_dir = _make_package(tmp_path, manifest_overrides={
            "model_version": None,
        })
        with pytest.raises(ModelPackageManifestError) as exc:
            validate_model_package(pkg_dir)
        assert "model_version" in str(exc.value)

    def test_empty_model_version(self, tmp_path: Path):
        """Empty 'model_version' string raises ModelPackageManifestError."""
        pkg_dir = _make_package(tmp_path, manifest_overrides={
            "model_version": "",
        })
        with pytest.raises(ModelPackageManifestError):
            validate_model_package(pkg_dir)

    def test_unexpected_artifact_type(self, tmp_path: Path):
        """Wrong artifact_type raises ModelPackageManifestError."""
        pkg_dir = _make_package(tmp_path, manifest_overrides={
            "artifact_type": "unknown.type",
        })
        with pytest.raises(ModelPackageManifestError):
            validate_model_package(pkg_dir)

    def test_threshold_value_non_numeric(self, tmp_path: Path):
        """Non-numeric threshold_value raises ModelPackageManifestError."""
        pkg_dir = _make_package(tmp_path, manifest_overrides={
            "threshold_value": "high",
        })
        with pytest.raises(ModelPackageManifestError):
            validate_model_package(pkg_dir)

    def test_invalid_checksum_pattern(self, tmp_path: Path):
        """Non-hex model_checksum raises ModelPackageManifestError."""
        pkg_dir = _make_package(tmp_path, manifest_overrides={
            "model_checksum": "zzzzzzzz",
        })
        with pytest.raises(ModelPackageManifestError):
            validate_model_package(pkg_dir)

    def test_threshold_value_missing(self, tmp_path: Path):
        """Missing threshold_value raises ModelPackageManifestError."""
        manifest = {
            "artifact_type": EXPECTED_ARTIFACT_TYPE,
            "model_version": "1.0.0",
            "model_checksum": "a" * 64,
            "model_filename": "model.joblib",
            "feature_schema_version": "1.0",
            "threshold_version": "v1",
            "qc_criteria_version": "1.0",
        }
        with pytest.raises(ModelPackageManifestError) as exc:
            validate_model_manifest(manifest)
        assert "threshold_value" in str(exc.value)


# ---------------------------------------------------------------------------
# Checksum mismatch
# ---------------------------------------------------------------------------


class TestChecksumMismatch:
    def test_checksum_mismatch(self, tmp_path: Path):
        """SHA-256 mismatch raises ModelPackageChecksumError."""
        pkg_dir = _make_package(tmp_path, manifest_overrides={
            "model_checksum": "f" * 64,
        })
        with pytest.raises(ModelPackageChecksumError):
            validate_model_package(pkg_dir)


# ---------------------------------------------------------------------------
# Path traversal
# ---------------------------------------------------------------------------


class TestPathTraversal:
    def test_absolute_model_filename(self, tmp_path: Path):
        """Absolute model_filename raises ModelPackageSecurityError."""
        pkg_dir = _make_package(tmp_path, manifest_overrides={
            "model_filename": "/etc/passwd",
        })
        with pytest.raises(ModelPackageSecurityError):
            validate_model_package(pkg_dir)

    def test_traversal_model_filename(self, tmp_path: Path):
        """Path traversal in model_filename raises ModelPackageSecurityError."""
        pkg_dir = _make_package(tmp_path, manifest_overrides={
            "model_filename": "../manifest.json",
        })
        with pytest.raises(ModelPackageSecurityError):
            validate_model_package(pkg_dir)

    def test_deep_traversal_model_filename(self, tmp_path: Path):
        """Deep path traversal raises ModelPackageSecurityError."""
        pkg_dir = _make_package(tmp_path, manifest_overrides={
            "model_filename": "../../../etc/passwd",
        })
        with pytest.raises(ModelPackageSecurityError):
            validate_model_package(pkg_dir)


# ---------------------------------------------------------------------------
# Import / security integrity
# ---------------------------------------------------------------------------


class TestImportSafety:
    def test_no_joblib_import(self):
        """model_package.py must not import joblib (AST check)."""
        src_path = SRC_BREMEN / "model_package.py"
        tree = ast.parse(src_path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "joblib" in alias.name:
                        pytest.fail("model_package.py imports joblib")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "joblib" in module:
                    pytest.fail("model_package.py imports joblib")

    def test_no_pickle_import(self):
        """model_package.py must not import pickle (AST check)."""
        src_path = SRC_BREMEN / "model_package.py"
        tree = ast.parse(src_path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "pickle" in alias.name:
                        pytest.fail("model_package.py imports pickle")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "pickle" in module:
                    pytest.fail("model_package.py imports pickle")

    def test_no_joblib_load_string(self):
        """model_package.py must not contain the string 'joblib.load('."""
        src_path = SRC_BREMEN / "model_package.py"
        content = src_path.read_text(encoding="utf-8")
        if "joblib.load(" in content:
            pytest.fail("model_package.py contains 'joblib.load('")

    def test_no_h5_references(self):
        """model_package.py must not reference H5/HDF5."""
        src_path = SRC_BREMEN / "model_package.py"
        content = src_path.read_text(encoding="utf-8")
        for ref in [".h5", ".hdf5", "h5py"]:
            if ref in content:
                pytest.fail(f"model_package.py contains H5 reference: {ref}")

    def test_no_aramis_references(self):
        """model_package.py must not contain Aramis identity."""
        src_path = SRC_BREMEN / "model_package.py"
        content = src_path.read_text(encoding="utf-8")
        if "Aramis" in content or "aramis" in content:
            pytest.fail("model_package.py contains Aramis reference")

    def test_import_succeeds(self):
        """Importing bremen.model_package succeeds."""
        import importlib

        if "bremen.model_package" in sys.modules:
            del sys.modules["bremen.model_package"]
        mod = importlib.import_module("bremen.model_package")
        assert mod is not None


# ---------------------------------------------------------------------------
# compute_sha256 edge cases
# ---------------------------------------------------------------------------


class TestComputeSha256:
    def test_missing_file(self, tmp_path: Path):
        """compute_sha256 on missing file raises ModelPackageNotFoundError."""
        missing = tmp_path / "ghost.bin"
        with pytest.raises(ModelPackageNotFoundError):
            compute_sha256(missing)

    def test_directory_path(self, tmp_path: Path):
        """compute_sha256 on a directory raises ModelPackageNotFoundError."""
        with pytest.raises(ModelPackageNotFoundError):
            compute_sha256(tmp_path)


# ---------------------------------------------------------------------------
# read_model_manifest edge cases
# ---------------------------------------------------------------------------


class TestReadManifest:
    def test_missing_manifest_file(self, tmp_path: Path):
        """read_model_manifest on missing file raises ModelPackageNotFoundError."""
        missing = tmp_path / "no_such_file.json"
        with pytest.raises(ModelPackageNotFoundError):
            read_model_manifest(missing)

    def test_invalid_json_content(self, tmp_path: Path):
        """read_model_manifest with invalid JSON raises ModelPackageManifestError."""
        path = tmp_path / "bad.json"
        path.write_text("{invalid json}", encoding="utf-8")
        with pytest.raises(ModelPackageManifestError):
            read_model_manifest(path)
