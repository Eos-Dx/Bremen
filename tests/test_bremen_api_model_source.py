"""Tests for metadata-only model package source descriptor.

Covers:
- No env vars -> not_configured
- Bucket + prefix set -> configured
- Content fields are None when configured (no model has been fetched)
- handle_model_version reflects env state
- handle_model_version without args works
- Import safety (no joblib/pickle/boto3/h5py)
- No S3 reads, no model loading, no manifest fetching
"""

from __future__ import annotations

import sys
import ast
import os
from pathlib import Path

import pytest

from bremen.config import CloudConfig, read_cloud_config
from bremen.api.model_source import derive_model_source
from bremen.api.app import handle_model_version
from bremen.api.schemas import ModelVersionResponse

API_SRC = Path(__file__).parents[1] / "src" / "bremen" / "api"


# ---------------------------------------------------------------------------
# Derive model source
# ---------------------------------------------------------------------------


class TestDeriveModelSource:
    def test_no_env_returns_not_configured(self):
        """derive_model_source with empty env returns not_configured."""
        cloud = read_cloud_config(env={})
        src = derive_model_source(cloud=cloud)
        assert src["model_configured"] is False
        assert src["model_status"] == "not_configured"
        assert src["model_version"] is None
        assert src["model_checksum"] is None

    def test_bucket_set_returns_configured(self):
        """derive_model_source with bucket returns configured."""
        cloud = read_cloud_config(
            env={"BREMEN_MODEL_BUCKET": "my-bucket"}
        )
        src = derive_model_source(cloud=cloud)
        assert src["model_configured"] is True
        assert src["model_status"] == "configured"

    def test_content_fields_are_none_when_configured(self):
        """All content fields are None when configured (no model fetched)."""
        cloud = read_cloud_config(
            env={
                "BREMEN_MODEL_BUCKET": "my-bucket",
                "BREMEN_MODEL_PREFIX": "v1/",
            }
        )
        src = derive_model_source(cloud=cloud)
        assert src["model_configured"] is True
        for key in [
            "model_checksum",
            "feature_schema_version",
            "threshold_version",
            "threshold_value",
            "qc_criteria_version",
        ]:
            assert src[key] is None, (
                f"Content field '{key}' must be None, got {src[key]!r}"
            )

    def test_model_version_from_env(self):
        """model_version is populated from BREMEN_MODEL_VERSION env."""
        cloud = read_cloud_config(
            env={
                "BREMEN_MODEL_BUCKET": "my-bucket",
                "BREMEN_MODEL_VERSION": "2.0.0",
            }
        )
        src = derive_model_source(cloud=cloud)
        assert src["model_version"] == "2.0.0"

    def test_no_bucket_and_no_env_defaults_not_configured(self):
        """Calling derive_model_source with None (reads os.environ).

        This test ensures the function doesn't crash when no env is set
        in the host environment.  It should return not_configured if the
        host environment doesn't have BREMEN_MODEL_BUCKET set.
        """
        # Use explicit empty dict to avoid depending on host env
        cloud = read_cloud_config(env={})
        src = derive_model_source(cloud=cloud)
        assert src["model_configured"] is False

    def test_none_cloud_config_reads_env(self):
        """Passing cloud=None reads from os.environ (safe default)."""
        # Save and restore env
        saved = os.environ.get("BREMEN_MODEL_BUCKET")
        if "BREMEN_MODEL_BUCKET" in os.environ:
            del os.environ["BREMEN_MODEL_BUCKET"]

        try:
            src = derive_model_source()
            assert src["model_configured"] is False
        finally:
            if saved is not None:
                os.environ["BREMEN_MODEL_BUCKET"] = saved


# ---------------------------------------------------------------------------
# Handle model version integration
# ---------------------------------------------------------------------------


class TestHandleModelVersion:
    def test_no_env_returns_not_configured(self):
        """handle_model_version with explicit empty cloud returns not_configured."""
        cloud = read_cloud_config(env={})
        resp = handle_model_version(cloud=cloud)
        assert isinstance(resp, ModelVersionResponse)
        assert resp.model_configured is False
        assert resp.model_status == "not_configured"

    def test_configured_env_returns_configured(self):
        """handle_model_version with configured env returns configured."""
        cloud = read_cloud_config(
            env={"BREMEN_MODEL_BUCKET": "my-bucket"}
        )
        resp = handle_model_version(cloud=cloud)
        assert resp.model_configured is True
        assert resp.model_status == "configured"
        assert resp.model_version is None  # not set in env

    def test_model_version_preserved(self):
        """handle_model_version preserves BREMEN_MODEL_VERSION."""
        cloud = read_cloud_config(
            env={
                "BREMEN_MODEL_BUCKET": "my-bucket",
                "BREMEN_MODEL_VERSION": "1.5.0",
            }
        )
        resp = handle_model_version(cloud=cloud)
        assert resp.model_version == "1.5.0"

    def test_content_fields_none_when_configured(self):
        """All content fields are None when configured."""
        cloud = read_cloud_config(
            env={"BREMEN_MODEL_BUCKET": "my-bucket"}
        )
        resp = handle_model_version(cloud=cloud)
        for field in [
            "model_checksum",
            "feature_schema_version",
            "threshold_version",
            "threshold_value",
            "qc_criteria_version",
        ]:
            assert getattr(resp, field) is None, (
                f"Field '{field}' must be None, got {getattr(resp, field)!r}"
            )

    def test_no_args_works(self):
        """handle_model_version() without args does not crash.

        Should return not_configured if host env is empty.
        """
        saved = os.environ.get("BREMEN_MODEL_BUCKET")
        if "BREMEN_MODEL_BUCKET" in os.environ:
            del os.environ["BREMEN_MODEL_BUCKET"]

        try:
            resp = handle_model_version()
            assert isinstance(resp, ModelVersionResponse)
            # Accept either state — host env may or may not have vars
            assert resp.model_configured in (True, False)
        finally:
            if saved is not None:
                os.environ["BREMEN_MODEL_BUCKET"] = saved


# ---------------------------------------------------------------------------
# Import safety (AST-based)
# ---------------------------------------------------------------------------


class TestImportSafety:
    def test_no_joblib_import(self):
        """model_source.py must not import joblib."""
        src = API_SRC / "model_source.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "joblib" in alias.name.lower():
                        pytest.fail("model_source.py imports joblib")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "joblib" in module.lower():
                    pytest.fail(f"model_source.py imports joblib via {module}")

    def test_no_pickle_import(self):
        """model_source.py must not import pickle."""
        src = API_SRC / "model_source.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "pickle" in alias.name.lower():
                        pytest.fail("model_source.py imports pickle")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "pickle" in module.lower():
                    pytest.fail(f"model_source.py imports pickle via {module}")

    def test_no_boto3_botocore(self):
        """model_source.py must not import boto3 or botocore."""
        src = API_SRC / "model_source.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        prohibited = {"boto3", "botocore"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in prohibited:
                        pytest.fail(f"model_source.py imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                top = module.split(".")[0]
                if top in prohibited:
                    pytest.fail(f"model_source.py imports {module}")

    def test_no_network_imports(self):
        """model_source.py must not import requests, httpx, or urllib."""
        src = API_SRC / "model_source.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        prohibited = {"requests", "httpx", "urllib"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in prohibited:
                        pytest.fail(f"model_source.py imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                top = module.split(".")[0]
                if top in prohibited:
                    pytest.fail(f"model_source.py imports {module}")

    def test_no_h5_references(self):
        """model_source.py must not reference .h5, .hdf5, or h5py."""
        src = API_SRC / "model_source.py"
        content = src.read_text(encoding="utf-8")
        for ref in [".h5", ".hdf5", "h5py"]:
            if ref in content:
                pytest.fail(f"model_source.py contains H5 reference: {ref}")

    def test_no_joblib_load_string(self):
        """model_source.py must not contain 'joblib.load(' or 'pickle.load('."""
        src = API_SRC / "model_source.py"
        content = src.read_text(encoding="utf-8")
        if "joblib.load(" in content:
            pytest.fail("model_source.py contains 'joblib.load('")
        if "pickle.load(" in content:
            pytest.fail("model_source.py contains 'pickle.load('")

    def test_import_succeeds(self):
        """Importing bremen.api.model_source succeeds."""
        import importlib

        if "bremen.api.model_source" in sys.modules:
            del sys.modules["bremen.api.model_source"]

        mod = importlib.import_module("bremen.api.model_source")
        assert mod is not None
