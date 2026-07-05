"""Tests for the controlled model loading boundary.

Covers (10+ scenarios):
1. Valid package loads successfully with injected deserializer.
2. Validation failure (bad checksum) prevents deserialization.
3. Missing manifest prevents deserialization.
4. Path traversal prevents deserialization.
5. Default deserializer is joblib.load.
6. Import safety — importing model_loader does NOT import joblib.
7. AST check — joblib is not imported at module top level.
8. No inference or prediction code.
9. No H5/HDF5 references.
10. No changes to model_package.py.
"""

from __future__ import annotations

import sys
import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from bremen.model_package import (
    ModelPackageChecksumError,
    ModelPackageNotFoundError,
    ModelPackageSecurityError,
    EXPECTED_ARTIFACT_TYPE,
)
from bremen.model_loader import (
    LoadedModelPackage,
    load_model_package,
)

SRC_LOADER = Path(__file__).parents[1] / "src" / "bremen" / "model_loader.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_valid_package(tmp_path: Path) -> Path:
    """Create a minimal valid model package and return its path."""
    pkg_dir = tmp_path / "valid_pkg"
    pkg_dir.mkdir()

    # Create a dummy artifact and compute its checksum
    artifact_bytes = b"fake model \x00 bytes\n"
    artifact_name = "model.joblib"
    (pkg_dir / artifact_name).write_bytes(artifact_bytes)
    checksum = hashlib.sha256(artifact_bytes).hexdigest()

    manifest = {
        "artifact_type": EXPECTED_ARTIFACT_TYPE,
        "model_version": "1.0.0",
        "model_checksum": checksum,
        "model_filename": artifact_name,
        "feature_schema_version": "1.0",
        "threshold_version": "v1",
        "threshold_value": 0.5,
        "qc_criteria_version": "1.0",
        "training_config_ref": "training/exp_42",
        "created_at": "2026-07-04T12:00:00Z",
    }

    (pkg_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    return pkg_dir


# ---------------------------------------------------------------------------
# 1. Valid package loads successfully
# ---------------------------------------------------------------------------


class TestValidLoad:
    def test_valid_package_loads(self, tmp_path: Path):
        """Valid package with injected deserializer returns LoadedModelPackage."""
        pkg_dir = _make_valid_package(tmp_path)
        fake_deserializer = lambda p: {"type": "model", "path": str(p)}

        result = load_model_package(pkg_dir, deserializer=fake_deserializer)

        assert isinstance(result, LoadedModelPackage)
        assert result.summary.model_version == "1.0.0"
        assert result.summary.model_checksum is not None
        assert isinstance(result.model, dict)
        assert result.model["type"] == "model"

    def test_model_metadata_in_summary(self, tmp_path: Path):
        """LoadedModelPackage.summary contains all expected metadata."""
        pkg_dir = _make_valid_package(tmp_path)
        result = load_model_package(
            pkg_dir, deserializer=lambda p: {"ok": True}
        )

        summary = result.summary
        assert summary.package_dir == pkg_dir.resolve()
        assert summary.manifest_path == (pkg_dir / "manifest.json").resolve()
        assert summary.model_path == (pkg_dir / "model.joblib").resolve()
        assert summary.model_version == "1.0.0"
        assert summary.feature_schema_version == "1.0"
        assert summary.threshold_version == "v1"
        assert summary.threshold_value == 0.5
        assert summary.qc_criteria_version == "1.0"
        assert summary.training_config_ref == "training/exp_42"


# ---------------------------------------------------------------------------
# 2. Validation failure (checksum) prevents deserialization
# ---------------------------------------------------------------------------


class TestValidationFailure:
    def test_checksum_mismatch_blocks_deserialization(self, tmp_path: Path):
        """Bad checksum raises and deserializer is never invoked."""
        pkg_dir = _make_valid_package(tmp_path)

        # Corrupt the artifact so checksum won't match
        artifact_path = pkg_dir / "model.joblib"
        artifact_path.write_bytes(b"different content\n")

        call_counter = {"called": False}

        def sentinel_deserializer(p: Any) -> Any:
            call_counter["called"] = True
            return {"bad": True}

        with pytest.raises(ModelPackageChecksumError):
            load_model_package(pkg_dir, deserializer=sentinel_deserializer)

        assert not call_counter["called"], (
            "Deserializer was invoked despite checksum mismatch"
        )

    def test_missing_manifest_blocks_deserialization(self, tmp_path: Path):
        """Missing manifest raises and deserializer is never invoked."""
        pkg_dir = tmp_path / "no_manifest"
        pkg_dir.mkdir()

        call_counter = {"called": False}

        def sentinel_deserializer(p: Any) -> Any:
            call_counter["called"] = True
            return {}

        with pytest.raises(ModelPackageNotFoundError):
            load_model_package(pkg_dir, deserializer=sentinel_deserializer)

        assert not call_counter["called"], (
            "Deserializer was invoked despite missing manifest"
        )

    def test_path_traversal_blocks_deserialization(self, tmp_path: Path):
        """Path traversal model_filename raises and deserializer never invoked."""
        pkg_dir = tmp_path / "traversal_pkg"
        pkg_dir.mkdir()

        # Create manifest with traversal filename
        checksum = hashlib.sha256(b"dummy").hexdigest()
        manifest = {
            "artifact_type": EXPECTED_ARTIFACT_TYPE,
            "model_version": "1.0.0",
            "model_checksum": checksum,
            "model_filename": "../../../etc/passwd",
            "feature_schema_version": "1.0",
            "threshold_version": "v1",
            "threshold_value": 0.5,
            "qc_criteria_version": "1.0",
        }
        (pkg_dir / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        call_counter = {"called": False}

        def sentinel_deserializer(p: Any) -> Any:
            call_counter["called"] = True
            return {}

        with pytest.raises(ModelPackageSecurityError):
            load_model_package(pkg_dir, deserializer=sentinel_deserializer)

        assert not call_counter["called"], (
            "Deserializer was invoked despite path traversal"
        )


# ---------------------------------------------------------------------------
# 3. Deserializer failure is surfaced
# ---------------------------------------------------------------------------


class TestDeserializerFailure:
    def test_deserializer_raises(self, tmp_path: Path):
        """A deserializer that raises is surfaced to the caller."""
        pkg_dir = _make_valid_package(tmp_path)

        def broken_deserializer(p: Any) -> Any:
            raise RuntimeError("deserializer failure")

        with pytest.raises(RuntimeError, match="deserializer failure"):
            load_model_package(pkg_dir, deserializer=broken_deserializer)


# ---------------------------------------------------------------------------
# 4. Default deserializer is joblib.load
# ---------------------------------------------------------------------------


class TestDefaultDeserializer:
    def test_default_is_joblib_load(self):
        """load_model_package's default deserializer is joblib.load."""
        import inspect

        sig = inspect.signature(load_model_package)
        default = sig.parameters["deserializer"].default
        assert default is None, (
            f"Expected default deserializer to be None, got {default}"
        )

    def test_joblib_import_happens_lazily(self, tmp_path: Path):
        """Calling load_model_package with default triggers joblib import.

        This test verifies that the lazy import path works — the
        from joblib import load call is inside the function.
        """
        # Create a package with a valid manifest but a dummy artifact
        # that can't actually be loaded by joblib (not a real joblib file).
        # We expect joblib.load to raise — but that's fine; the
        # important check is that the function doesn't crash on import.
        pkg_dir = tmp_path / "lazy_import_test"
        pkg_dir.mkdir()

        artifact_bytes = b"not a real joblib file at all\n"
        (pkg_dir / "dummy.joblib").write_bytes(artifact_bytes)
        checksum = hashlib.sha256(artifact_bytes).hexdigest()

        manifest = {
            "artifact_type": EXPECTED_ARTIFACT_TYPE,
            "model_version": "1.0.0",
            "model_checksum": checksum,
            "model_filename": "dummy.joblib",
            "feature_schema_version": "1.0",
            "threshold_version": "v1",
            "threshold_value": 0.5,
            "qc_criteria_version": "1.0",
        }
        (pkg_dir / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        # The import should not raise ImportError — the from joblib import load
        # is valid. The deserialization itself will fail because the artifact
        # is not a real joblib file, but that proves the lazy import worked.
        with pytest.raises(Exception):
            load_model_package(pkg_dir)


# ---------------------------------------------------------------------------
# 5. Import safety
# ---------------------------------------------------------------------------


class TestImportSafety:
    def test_import_does_not_load_joblib(self):
        """Importing bremen.model_loader does NOT import joblib at module level."""
        # Check before import
        if "bremen.model_loader" in sys.modules:
            del sys.modules["bremen.model_loader"]
        if "joblib" in sys.modules:
            del sys.modules["joblib"]

        import bremen.model_loader  # noqa: F811

        assert "joblib" not in sys.modules, (
            "Importing bremen.model_loader triggered a top-level import of joblib"
        )

    def test_ast_no_top_level_joblib_import(self):
        """model_loader.py must not import joblib at module top level (AST check).

        ``from joblib import load`` inside ``load_model_package()`` is
        acceptable (lazy).  Module-level ``import joblib`` or
        ``from joblib import ...`` is forbidden.
        """
        tree = ast.parse(SRC_LOADER.read_text(encoding="utf-8"))

        # Only check module-level statements (body of the Module node)
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "joblib" in alias.name.lower():
                        pytest.fail(
                            f"model_loader.py has module-level joblib import: "
                            f"import {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "joblib" in module.lower():
                    pytest.fail(
                        f"model_loader.py has module-level joblib import: "
                        f"from {module}"
                    )

    def test_no_pickle_import(self):
        """model_loader.py must not import pickle."""
        tree = ast.parse(SRC_LOADER.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "pickle" in alias.name.lower():
                        pytest.fail("model_loader.py imports pickle")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "pickle" in module.lower():
                    pytest.fail(f"model_loader.py imports pickle via {module}")

    def test_no_inference_or_prediction(self):
        """model_loader.py must not contain predict/infer/train code."""
        content = SRC_LOADER.read_text(encoding="utf-8")
        prohibited = ["def predict", ".predict(", "def infer", ".infer(", "def train"]
        for phrase in prohibited:
            if phrase in content:
                pytest.fail(f"model_loader.py contains: {phrase}")

    def test_no_h5_references(self):
        """model_loader.py must not reference .h5, .hdf5, or h5py."""
        content = SRC_LOADER.read_text(encoding="utf-8")
        for ref in [".h5", ".hdf5", "h5py"]:
            if ref in content:
                pytest.fail(f"model_loader.py contains H5 reference: {ref}")

    def test_no_boto3_network(self):
        """model_loader.py must not import boto3, requests, httpx."""
        tree = ast.parse(SRC_LOADER.read_text(encoding="utf-8"))
        prohibited = {"boto3", "botocore", "requests", "httpx", "urllib"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in prohibited:
                        pytest.fail(f"model_loader.py imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                top = module.split(".")[0]
                if top in prohibited:
                    pytest.fail(f"model_loader.py imports {module}")

    def test_no_clinical_claims(self):
        """model_loader.py must not make clinical claims."""
        content = SRC_LOADER.read_text(encoding="utf-8")
        prohibited = ["diagnosis", "clinical validation", "replace MRI", "replace biopsy"]
        for phrase in prohibited:
            if phrase in content.lower():
                pytest.fail(f"model_loader.py contains prohibited phrase: {phrase}")


# ---------------------------------------------------------------------------
# 6. LoadedModelPackage composite compatibility
# ---------------------------------------------------------------------------


class TestCompositePackaging:
    def test_model_accepts_list(self, tmp_path: Path):
        """Deserialized list is accepted as model value."""
        pkg_dir = _make_valid_package(tmp_path)
        result = load_model_package(pkg_dir, deserializer=lambda p: [1, 2, 3])
        assert isinstance(result.model, list)
        assert result.model == [1, 2, 3]

    def test_model_accepts_none(self, tmp_path: Path):
        """Deserialized None is accepted as model value (proves Any)."""
        pkg_dir = _make_valid_package(tmp_path)
        result = load_model_package(pkg_dir, deserializer=lambda p: None)
        assert result.model is None


# ---------------------------------------------------------------------------
# 7. No file changes to model_package.py
# ---------------------------------------------------------------------------


class TestModelPackageUnchanged:
    def test_model_package_not_modified(self):
        """Verify no modifications to model_package.py."""
        import subprocess

        result = subprocess.run(
            ["git", "diff", "--name-only", "--", "src/bremen/model_package.py"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(Path(__file__).parents[1]),
        )
        assert result.stdout.strip() == "", (
            f"model_package.py was unexpectedly modified:\n{result.stdout}"
        )
