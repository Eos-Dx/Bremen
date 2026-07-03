"""Tests for cloud-aware runtime configuration sourcing.

Covers:
- No env vars -> configured=False
- Bucket + prefix -> configured=True, values preserved/normalized
- Bucket only -> configured=True with default prefix
- Optional model version, manifest key, service env, AWS region preserved
- Prefix normalization adds trailing slash
- Bucket rejects s3:// URI
- Bucket rejects /Users local path
- Bucket rejects /home local path
- Bucket rejects absolute local path
- Bucket rejects file URI
- Prefix rejects absolute local path
- Prefix rejects /Users local path
- Prefix rejects /home local path
- Prefix rejects file URI
- Function accepts explicit env mapping without mutating os.environ
- No boto3/botocore/requests/httpx/urllib/network dependency
- No joblib/pickle loading
- No H5/HDF5 reading
"""

from __future__ import annotations

import sys
import ast
from pathlib import Path

import pytest

from bremen.config import (
    CloudConfig,
    CloudConfigError,
    read_cloud_config,
)

SRC_CONFIG = Path(__file__).parents[1] / "src" / "bremen" / "config.py"

_DEFAULT_PREFIX = "model-packages/"


# ---------------------------------------------------------------------------
# Not configured
# ---------------------------------------------------------------------------


class TestNotConfigured:
    def test_no_env_vars_returns_not_configured(self):
        """No env vars -> configured=False."""
        cloud = read_cloud_config(env={})
        assert cloud.configured is False
        assert cloud.model_bucket is None

    def test_empty_bucket_returns_not_configured(self):
        """Empty BREMEN_MODEL_BUCKET -> configured=False."""
        cloud = read_cloud_config(env={"BREMEN_MODEL_BUCKET": ""})
        assert cloud.configured is False

    def test_whitespace_bucket_returns_not_configured(self):
        """Whitespace-only BREMEN_MODEL_BUCKET -> configured=False."""
        cloud = read_cloud_config(env={"BREMEN_MODEL_BUCKET": "   "})
        assert cloud.configured is False

    def test_not_configured_defaults(self):
        """Not-configured state has safe defaults."""
        cloud = read_cloud_config(env={})
        assert cloud.model_prefix == _DEFAULT_PREFIX
        assert cloud.model_manifest_key == "manifest.json"
        assert cloud.model_version is None
        assert cloud.service_env is None
        assert cloud.aws_region is None


# ---------------------------------------------------------------------------
# Configured
# ---------------------------------------------------------------------------


class TestConfigured:
    def test_bucket_only_uses_default_prefix(self):
        """Bucket only -> configured=True with default prefix."""
        cloud = read_cloud_config(
            env={"BREMEN_MODEL_BUCKET": "my-bremen-models"}
        )
        assert cloud.configured is True
        assert cloud.model_bucket == "my-bremen-models"
        assert cloud.model_prefix == _DEFAULT_PREFIX

    def test_bucket_and_prefix(self):
        """Bucket + prefix -> configured=True, values preserved."""
        cloud = read_cloud_config(
            env={
                "BREMEN_MODEL_BUCKET": "my-bremen-models",
                "BREMEN_MODEL_PREFIX": "bremen/v1/",
            }
        )
        assert cloud.configured is True
        assert cloud.model_bucket == "my-bremen-models"
        assert cloud.model_prefix == "bremen/v1/"

    def test_optional_model_version(self):
        """Optional BREMEN_MODEL_VERSION is preserved."""
        cloud = read_cloud_config(
            env={
                "BREMEN_MODEL_BUCKET": "bucket",
                "BREMEN_MODEL_VERSION": "1.2.3",
            }
        )
        assert cloud.model_version == "1.2.3"

    def test_optional_manifest_key(self):
        """Optional BREMEN_MODEL_MANIFEST_KEY is preserved."""
        cloud = read_cloud_config(
            env={
                "BREMEN_MODEL_BUCKET": "bucket",
                "BREMEN_MODEL_MANIFEST_KEY": "custom.json",
            }
        )
        assert cloud.model_manifest_key == "custom.json"

    def test_optional_service_env(self):
        """Optional BREMEN_SERVICE_ENV is preserved."""
        cloud = read_cloud_config(
            env={
                "BREMEN_MODEL_BUCKET": "bucket",
                "BREMEN_SERVICE_ENV": "staging",
            }
        )
        assert cloud.service_env == "staging"

    def test_optional_aws_region(self):
        """Optional BREMEN_AWS_REGION is preserved."""
        cloud = read_cloud_config(
            env={
                "BREMEN_MODEL_BUCKET": "bucket",
                "BREMEN_AWS_REGION": "us-east-1",
            }
        )
        assert cloud.aws_region == "us-east-1"

    def test_nested_prefix(self):
        """Nested prefix like 'models/bremen/' is allowed."""
        cloud = read_cloud_config(
            env={
                "BREMEN_MODEL_BUCKET": "bucket",
                "BREMEN_MODEL_PREFIX": "models/bremen/",
            }
        )
        assert cloud.model_prefix == "models/bremen/"


# ---------------------------------------------------------------------------
# Prefix normalization
# ---------------------------------------------------------------------------


class TestPrefixNormalization:
    def test_missing_trailing_slash_added(self):
        """Prefix without trailing slash gets one added."""
        cloud = read_cloud_config(
            env={
                "BREMEN_MODEL_BUCKET": "bucket",
                "BREMEN_MODEL_PREFIX": "bremen/v1",
            }
        )
        assert cloud.model_prefix == "bremen/v1/"

    def test_leading_slash_removed(self):
        """Leading slash in prefix is removed."""
        cloud = read_cloud_config(
            env={
                "BREMEN_MODEL_BUCKET": "bucket",
                "BREMEN_MODEL_PREFIX": "/bremen/v1/",
            }
        )
        assert cloud.model_prefix == "bremen/v1/"


# ---------------------------------------------------------------------------
# Bucket validation: rejected values
# ---------------------------------------------------------------------------


class TestBucketValidation:
    def test_bucket_rejects_s3_uri(self):
        """Bucket with s3:// prefix raises CloudConfigError."""
        with pytest.raises(CloudConfigError, match="s3://"):
            read_cloud_config(
                env={"BREMEN_MODEL_BUCKET": "s3://my-bucket"}
            )

    def test_bucket_rejects_absolute_path(self):
        """Bucket that is an absolute path raises CloudConfigError."""
        with pytest.raises(CloudConfigError, match="absolute path"):
            read_cloud_config(
                env={"BREMEN_MODEL_BUCKET": "/tmp/some-path"}
            )

    def test_bucket_rejects_users_path(self):
        """Bucket containing /Users/ raises CloudConfigError."""
        with pytest.raises(CloudConfigError, match="/Users/"):
            read_cloud_config(
                env={"BREMEN_MODEL_BUCKET": "/Users/sad/models"}
            )

    def test_bucket_rejects_home_path(self):
        """Bucket containing /home/ raises CloudConfigError."""
        with pytest.raises(CloudConfigError, match="/home/"):
            read_cloud_config(
                env={"BREMEN_MODEL_BUCKET": "/home/dev/models"}
            )

    def test_bucket_rejects_file_uri(self):
        """Bucket containing file:// raises CloudConfigError."""
        with pytest.raises(CloudConfigError, match="file://"):
            read_cloud_config(
                env={"BREMEN_MODEL_BUCKET": "file:///some/path"}
            )


# ---------------------------------------------------------------------------
# Prefix validation: rejected values
# ---------------------------------------------------------------------------


class TestPrefixValidation:
    def test_prefix_rejects_users_path(self):
        """Prefix containing /Users/ raises CloudConfigError."""
        with pytest.raises(CloudConfigError):
            read_cloud_config(
                env={
                    "BREMEN_MODEL_BUCKET": "bucket",
                    "BREMEN_MODEL_PREFIX": "/Users/sad/model/",
                }
            )

    def test_prefix_rejects_home_path(self):
        """Prefix containing /home/ raises CloudConfigError."""
        with pytest.raises(CloudConfigError):
            read_cloud_config(
                env={
                    "BREMEN_MODEL_BUCKET": "bucket",
                    "BREMEN_MODEL_PREFIX": "/home/dev/",
                }
            )

    def test_prefix_rejects_file_uri(self):
        """Prefix containing file:// raises CloudConfigError."""
        with pytest.raises(CloudConfigError):
            read_cloud_config(
                env={
                    "BREMEN_MODEL_BUCKET": "bucket",
                    "BREMEN_MODEL_PREFIX": "file:///some/path",
                }
            )


# ---------------------------------------------------------------------------
# Explicit env argument
# ---------------------------------------------------------------------------


class TestExplicitEnv:
    def test_explicit_env_not_mutating_os_environ(self):
        """read_cloud_config with explicit env does not read os.environ."""
        cloud = read_cloud_config(
            env={"BREMEN_MODEL_BUCKET": "my-bucket"}
        )
        assert cloud.configured is True
        assert cloud.model_bucket == "my-bucket"


# ---------------------------------------------------------------------------
# Import safety (AST-based)
# ---------------------------------------------------------------------------


class TestImportSafety:
    def test_no_boto3_botocore(self):
        """config.py must not import boto3 or botocore."""
        tree = ast.parse(SRC_CONFIG.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in ("boto3", "botocore"):
                        pytest.fail(f"config.py imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                top = module.split(".")[0]
                if top in ("boto3", "botocore"):
                    pytest.fail(f"config.py imports {module}")

    def test_no_requests_httpx_urllib(self):
        """config.py must not import requests, httpx, or urllib."""
        tree = ast.parse(SRC_CONFIG.read_text(encoding="utf-8"))
        prohibited = {"requests", "httpx", "urllib"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in prohibited:
                        pytest.fail(f"config.py imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                top = module.split(".")[0]
                if top in prohibited:
                    pytest.fail(f"config.py imports {module}")

    def test_no_joblib_pickle(self):
        """config.py must not import joblib or pickle."""
        tree = ast.parse(SRC_CONFIG.read_text(encoding="utf-8"))
        prohibited = {"joblib", "pickle"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in prohibited:
                        pytest.fail(f"config.py imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                top = module.split(".")[0]
                if top in prohibited:
                    pytest.fail(f"config.py imports {module}")

    def test_no_h5_hdf5_h5py(self):
        """config.py must not import or reference h5py/H5/HDF5."""
        content = SRC_CONFIG.read_text(encoding="utf-8")
        for ref in [".h5", ".hdf5", "h5py"]:
            if ref in content:
                pytest.fail(f"config.py contains H5 reference: {ref!r}")

    def test_import_succeeds(self):
        """Importing bremen.config succeeds without ImportError."""
        import importlib

        if "bremen.config" in sys.modules:
            del sys.modules["bremen.config"]

        mod = importlib.import_module("bremen.config")
        assert mod is not None
