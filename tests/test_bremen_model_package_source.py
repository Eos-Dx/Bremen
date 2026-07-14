"""Tests for the model package source resolver.

Covers:
- not_configured source status (no env vars)
- Local valid package source uses existing manifest/checksum validation
- Local invalid package fails closed (missing dir, missing manifest, checksum)
- Local package source does not load model (AST import safety)
- Cloud metadata source from env/config returns metadata-only configured status
- Cloud source does not call S3/AWS/network (AST import safety)
- Source precedence: explicit path > env var > cloud > not_configured
- BREMEN_MODEL_PACKAGE_DIR env var validation
- Import safety (no joblib/pickle/boto3/h5py)
"""

from __future__ import annotations

import hashlib
import json
import os
import ast
from pathlib import Path

import pytest

from bremen.model_package_source import (
    ModelPackageSource,
    ModelPackageSourceError,
    resolve_model_package_source,
)
from bremen.model_package import EXPECTED_ARTIFACT_TYPE

SRC_BREMEN = Path(__file__).parents[1] / "src" / "bremen"
MPS_SRC = SRC_BREMEN / "model_package_source.py"


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
    pkg_dir.mkdir(parents=True, exist_ok=True)

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

    (pkg_dir / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )

    return pkg_dir


# ---------------------------------------------------------------------------
# not_configured
# ---------------------------------------------------------------------------


class TestNotConfigured:
    def test_no_explicit_path_no_env_returns_not_configured(self):
        """No explicit path and no env vars -> not_configured."""
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {}, clear=True):
            source = resolve_model_package_source()
        assert source.source_type == "not_configured"
        assert source.model_configured is False
        assert source.model_status == "not_configured"
        assert source.model_version is None
        assert source.model_checksum is None
        assert source.error is None


# ---------------------------------------------------------------------------
# Local package source
# ---------------------------------------------------------------------------


class TestLocalValid:
    def test_explicit_valid_package_returns_metadata(self, tmp_path: Path):
        """Explicit path to valid package -> configured with full metadata."""
        pkg_dir = _make_package(tmp_path)
        source = resolve_model_package_source(explicit_path=pkg_dir)
        assert source.source_type == "local"
        assert source.model_configured is True
        assert source.model_status == "configured"
        assert source.model_version == "1.0.0"
        assert source.feature_schema_version == "1.0"
        assert source.threshold_version == "v1"
        assert source.threshold_value == 0.5
        assert source.qc_criteria_version == "1.0"
        assert len(source.model_checksum) == 64
        assert source.error is None

    def test_env_var_valid_package_returns_metadata(self, tmp_path: Path):
        """BREMEN_MODEL_PACKAGE_DIR env var -> configured with metadata."""
        import os
        from unittest.mock import patch

        pkg_dir = _make_package(tmp_path)
        with patch.dict(
            os.environ,
            {"BREMEN_MODEL_PACKAGE_DIR": str(pkg_dir)},
            clear=True,
        ):
            source = resolve_model_package_source()
        assert source.source_type == "local"
        assert source.model_configured is True
        assert source.model_version == "1.0.0"

    def test_explicit_path_wins_over_env_var(self, tmp_path: Path):
        """Explicit path takes precedence over BREMEN_MODEL_PACKAGE_DIR."""
        import os
        from unittest.mock import patch

        # Create two packages: one for env var, one for explicit path
        env_pkg = _make_package(
            tmp_path / "env_pkg",
            manifest_overrides={"model_version": "from_env"},
        )
        explicit_pkg = _make_package(
            tmp_path / "explicit_pkg",
            manifest_overrides={"model_version": "from_explicit"},
        )

        with patch.dict(
            os.environ,
            {"BREMEN_MODEL_PACKAGE_DIR": str(env_pkg)},
            clear=True,
        ):
            source = resolve_model_package_source(explicit_path=explicit_pkg)
        assert source.source_type == "local"
        assert source.model_version == "from_explicit"


# ---------------------------------------------------------------------------
# Local invalid / fail-closed
# ---------------------------------------------------------------------------


class TestLocalInvalid:
    def test_missing_directory_fails_closed(self):
        """Non-existent path -> invalid with error."""
        source = resolve_model_package_source(
            explicit_path="/nonexistent/path/package"
        )
        assert source.source_type == "local"
        assert source.model_configured is False
        assert source.model_status == "invalid"
        assert source.error is not None
        assert "not found" in source.error.lower()

    def test_path_is_file_fails_closed(self, tmp_path: Path):
        """Path that is a file (not a directory) -> invalid with error."""
        file_path = tmp_path / "not_a_dir"
        file_path.write_text("hello")
        source = resolve_model_package_source(explicit_path=file_path)
        assert source.model_status == "invalid"
        assert "not a directory" in source.error.lower()

    def test_missing_manifest_fails_closed(self, tmp_path: Path):
        """Directory without manifest -> invalid with error."""
        pkg_dir = tmp_path / "no_manifest"
        pkg_dir.mkdir()
        source = resolve_model_package_source(explicit_path=pkg_dir)
        assert source.model_status == "invalid"
        assert "manifest" in source.error.lower()

    def test_checksum_mismatch_fails_closed(self, tmp_path: Path):
        """Manifest checksum doesn't match artifact -> invalid with error."""
        pkg_dir = _make_package(
            tmp_path, manifest_overrides={"model_checksum": "f" * 64}
        )
        source = resolve_model_package_source(explicit_path=pkg_dir)
        assert source.model_status == "invalid"
        assert "SHA-256" in source.error or "checksum" in source.error.lower()

    def test_path_traversal_fails_closed(self, tmp_path: Path):
        """Path traversal in manifest -> invalid with error."""
        pkg_dir = _make_package(
            tmp_path,
            manifest_overrides={"model_filename": "../manifest.json"},
        )
        source = resolve_model_package_source(explicit_path=pkg_dir)
        assert source.model_status == "invalid"
        assert "escapes" in source.error.lower()

    def test_env_var_invalid_dir_fails_closed(self, tmp_path: Path):
        """BREMEN_MODEL_PACKAGE_DIR pointing to invalid dir -> invalid, not fallthrough."""
        import os
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {
                "BREMEN_MODEL_PACKAGE_DIR": str(tmp_path / "nonexistent"),
                "BREMEN_MODEL_BUCKET": "my-bucket",
            },
            clear=True,
        ):
            source = resolve_model_package_source()
        # Must NOT fall through to cloud config
        assert source.source_type == "local"
        assert source.model_status == "invalid"


# ---------------------------------------------------------------------------
# Cloud metadata-only source
# ---------------------------------------------------------------------------


class TestCloudMetadata:
    def test_cloud_configured_returns_status(self):
        """BREMEN_MODEL_BUCKET set -> configured with content fields None."""
        import os
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {"BREMEN_MODEL_BUCKET": "my-bucket"},
            clear=True,
        ):
            source = resolve_model_package_source()
        assert source.source_type == "cloud"
        assert source.model_configured is True
        assert source.model_status == "configured"
        # All content fields are None (not fetched)
        assert source.model_checksum is None
        assert source.feature_schema_version is None
        assert source.threshold_version is None
        assert source.threshold_value is None
        assert source.qc_criteria_version is None

    def test_cloud_version_populated(self):
        """BREMEN_MODEL_VERSION is reflected in source metadata."""
        import os
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {
                "BREMEN_MODEL_BUCKET": "my-bucket",
                "BREMEN_MODEL_VERSION": "2.0.0",
            },
            clear=True,
        ):
            source = resolve_model_package_source()
        assert source.source_type == "cloud"
        assert source.model_version == "2.0.0"

    def test_cloud_no_model_version_by_default(self):
        """Without BREMEN_MODEL_VERSION, model_version is None."""
        import os
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {"BREMEN_MODEL_BUCKET": "my-bucket"},
            clear=True,
        ):
            source = resolve_model_package_source()
        assert source.model_version is None


# ---------------------------------------------------------------------------
# Source precedence
# ---------------------------------------------------------------------------


class TestPrecedence:
    def test_explicit_path_over_env_var(self, tmp_path: Path):
        """Explicit path > BREMEN_MODEL_PACKAGE_DIR."""
        import os
        from unittest.mock import patch

        # Create a valid explicit package
        explicit_pkg = _make_package(tmp_path / "explicit")

        with patch.dict(
            os.environ,
            {
                "BREMEN_MODEL_PACKAGE_DIR": str(tmp_path / "nonexistent"),
            },
            clear=True,
        ):
            source = resolve_model_package_source(explicit_path=explicit_pkg)
        assert source.source_type == "local"
        assert source.model_configured is True

    def test_env_var_over_cloud(self, tmp_path: Path):
        """BREMEN_MODEL_PACKAGE_DIR > cloud config."""
        import os
        from unittest.mock import patch

        pkg_dir = _make_package(tmp_path / "env_pkg")

        with patch.dict(
            os.environ,
            {
                "BREMEN_MODEL_PACKAGE_DIR": str(pkg_dir),
                "BREMEN_MODEL_BUCKET": "my-bucket",
            },
            clear=True,
        ):
            source = resolve_model_package_source()
        # Must resolve to local (env var takes precedence over cloud)
        assert source.source_type == "local"
        assert source.model_configured is True

    def test_cloud_over_not_configured(self):
        """Cloud config > not_configured."""
        import os
        from unittest.mock import patch

        with patch.dict(
            os.environ,
            {"BREMEN_MODEL_BUCKET": "my-bucket"},
            clear=True,
        ):
            source = resolve_model_package_source()
        assert source.source_type == "cloud"
        assert source.model_configured is True


# ---------------------------------------------------------------------------
# handle_model_version integration (through app.py)
# ---------------------------------------------------------------------------


class TestHandleModelVersionIntegration:
    def test_handle_model_version_with_explicit_path(self, tmp_path: Path):
        """handle_model_version with explicit path returns metadata."""
        from bremen.api.app import handle_model_version

        pkg_dir = _make_package(tmp_path)
        resp = handle_model_version(explicit_path=pkg_dir)
        assert resp.model_configured is True
        assert resp.model_status == "configured"
        assert resp.model_version == "1.0.0"
        assert resp.feature_schema_version == "1.0"

    def test_handle_model_version_without_args_not_configured(self):
        """handle_model_version() without args with empty env -> not_configured."""
        import os
        from unittest.mock import patch

        from bremen.api.app import handle_model_version

        with patch.dict(os.environ, {}, clear=True):
            resp = handle_model_version()
        assert resp.model_configured is False
        assert resp.model_status == "not_configured"

    def test_handle_model_version_cloud_configured(self):
        """handle_model_version() with cloud env -> configured."""
        import os
        from unittest.mock import patch

        from bremen.api.app import handle_model_version

        with patch.dict(
            os.environ,
            {"BREMEN_MODEL_BUCKET": "my-bucket"},
            clear=True,
        ):
            resp = handle_model_version()
        assert resp.model_configured is True
        assert resp.model_status == "configured"


# ---------------------------------------------------------------------------
# Import safety (AST-based) for model_package_source.py
# ---------------------------------------------------------------------------


class TestImportSafety:
    def test_no_joblib_import(self):
        """model_package_source.py must not import joblib."""
        tree = ast.parse(MPS_SRC.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "joblib" in alias.name.lower():
                        pytest.fail("model_package_source.py imports joblib")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "joblib" in module.lower():
                    pytest.fail(
                        f"model_package_source.py imports joblib via {module}"
                    )

    def test_no_pickle_import(self):
        """model_package_source.py must not import pickle."""
        tree = ast.parse(MPS_SRC.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "pickle" in alias.name.lower():
                        pytest.fail("model_package_source.py imports pickle")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "pickle" in module.lower():
                    pytest.fail(
                        f"model_package_source.py imports pickle via {module}"
                    )

    def test_no_boto3_or_network(self):
        """model_package_source.py must not import boto3, requests, httpx."""
        tree = ast.parse(MPS_SRC.read_text(encoding="utf-8"))
        prohibited = {"boto3", "botocore", "requests", "httpx", "urllib"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in prohibited:
                        pytest.fail(
                            f"model_package_source.py imports {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                top = module.split(".")[0]
                if top in prohibited:
                    pytest.fail(
                        f"model_package_source.py imports {module}"
                    )

    def test_no_h5_references(self):
        """model_package_source.py must not reference .h5, .hdf5, or h5py."""
        content = MPS_SRC.read_text(encoding="utf-8")
        for ref in [".h5", ".hdf5", "h5py"]:
            if ref in content:
                pytest.fail(
                    f"model_package_source.py contains H5 reference: {ref}"
                )

    def test_no_joblib_load_string(self):
        """model_package_source.py must not contain 'joblib.load(' or 'pickle.load('."""
        content = MPS_SRC.read_text(encoding="utf-8")
        if "joblib.load(" in content:
            pytest.fail("model_package_source.py contains 'joblib.load('")
        if "pickle.load(" in content:
            pytest.fail("model_package_source.py contains 'pickle.load('")
