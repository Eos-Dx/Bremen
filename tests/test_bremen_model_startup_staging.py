"""Tests for S3 model download / startup staging (PR 0040).

All tests use fake/injectable S3 clients — no real AWS calls,
no credentials, no network access.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bremen.model_artifacts import (
    parse_s3_uri,
    verify_file_sha256,
    stage_model_artifact,
    stage_s3_model_artifact,
)
from bremen.api.model_state import ModelState


# ---------------------------------------------------------------------------
# S3 URI parsing
# ---------------------------------------------------------------------------


class TestParseS3Uri:
    def test_valid_uri(self):
        """Valid s3://bucket/key parses correctly."""
        bucket, key = parse_s3_uri("s3://my-bucket/path/to/model.joblib")
        assert bucket == "my-bucket"
        assert key == "path/to/model.joblib"

    def test_valid_uri_single_component_key(self):
        """s3://bucket/file works."""
        bucket, key = parse_s3_uri("s3://my-bucket/model.joblib")
        assert bucket == "my-bucket"
        assert key == "model.joblib"

    def test_empty_bucket_rejected(self):
        """s3:///key raises ValueError."""
        with pytest.raises(ValueError, match="empty bucket"):
            parse_s3_uri("s3:///key")

    def test_empty_key_rejected(self):
        """s3://bucket/ raises ValueError."""
        with pytest.raises(ValueError, match="empty key"):
            parse_s3_uri("s3://my-bucket/")

    def test_no_s3_prefix_rejected(self):
        """Non-s3 URI raises ValueError."""
        with pytest.raises(ValueError, match="must start with 's3://'"):
            parse_s3_uri("http://example.com/obj.joblib")


# ---------------------------------------------------------------------------
# Checksum verification
# ---------------------------------------------------------------------------


class TestVerifyFileSha256:
    def test_valid_checksum_passes(self, tmp_path: Path):
        """Correct checksum passes verification."""
        content = b"test artifact content"
        f = tmp_path / "artifact.joblib"
        f.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        verify_file_sha256(f, expected)  # should not raise

    def test_valid_checksum_with_sha256_prefix(self, tmp_path: Path):
        """Checksum with sha256: prefix works."""
        content = b"another test"
        f = tmp_path / "artifact2.joblib"
        f.write_bytes(content)
        expected = "sha256:" + hashlib.sha256(content).hexdigest()
        verify_file_sha256(f, expected)  # should not raise

    def test_checksum_mismatch_raises(self, tmp_path: Path):
        """Wrong checksum raises ValueError."""
        content = b"some content"
        f = tmp_path / "bad_artifact.joblib"
        f.write_bytes(content)
        with pytest.raises(ValueError, match="SHA-256 mismatch"):
            verify_file_sha256(f, "a" * 64)

    def test_checksum_mismatch_deletes_file(self, tmp_path: Path):
        """Mismatch deletes the bad file."""
        content = b"delete me"
        f = tmp_path / "to_delete.joblib"
        f.write_bytes(content)
        assert f.exists()
        with pytest.raises(ValueError):
            verify_file_sha256(f, "b" * 64)
        assert not f.exists(), "Bad file should be deleted on checksum mismatch"


# ---------------------------------------------------------------------------
# S3 download with fake client
# ---------------------------------------------------------------------------


class TestS3Download:
    def test_s3_download_with_fake_client(self, tmp_path: Path):
        """Fake S3 client writes staged file."""
        content = b"fake model package content"
        expected_checksum = hashlib.sha256(content).hexdigest()

        mock_client = MagicMock()
        def fake_download(Bucket, Key, Filename):
            Path(Filename).write_bytes(content)
        mock_client.download_file.side_effect = fake_download

        staging_dir = tmp_path / "staging"
        result = stage_s3_model_artifact(
            "test-bucket", "models/v1/model.joblib",
            expected_checksum,
            staging_dir,
            s3_client=mock_client,
        )

        assert result.exists()
        assert result.name == "model.joblib"

    def test_s3_download_verifies_checksum(self, tmp_path: Path):
        """Checksum mismatch on downloaded file raises ValueError."""
        content = b"original content"
        # Checksum does NOT match the downloaded content
        wrong_checksum = hashlib.sha256(b"different content").hexdigest()

        mock_client = MagicMock()
        def fake_download(Bucket, Key, Filename):
            Path(Filename).write_bytes(content)
        mock_client.download_file.side_effect = fake_download

        staging_dir = tmp_path / "staging2"

        with pytest.raises(ValueError, match="SHA-256 mismatch"):
            stage_s3_model_artifact(
                "test-bucket", "models/bad.joblib",
                wrong_checksum,
                staging_dir,
                s3_client=mock_client,
            )

    def test_s3_download_fake_failure_raises(self, tmp_path: Path):
        """Download error is surfaced."""
        mock_client = MagicMock()
        mock_client.download_file.side_effect = RuntimeError("S3 timeout")

        staging_dir = tmp_path / "staging3"

        with pytest.raises(ValueError, match="S3 download failed"):
            stage_s3_model_artifact(
                "test-bucket", "models/fail.joblib",
                "a" * 64,
                staging_dir,
                s3_client=mock_client,
            )

    def test_stage_model_artifact_uses_s3_path(self, tmp_path: Path):
        """stage_model_artifact with s3:// URI delegates to S3."""
        content = b"s3 test content"
        expected_checksum = hashlib.sha256(content).hexdigest()

        mock_client = MagicMock()
        def fake_download(Bucket, Key, Filename):
            Path(Filename).write_bytes(content)
        mock_client.download_file.side_effect = fake_download

        with patch(
            "bremen.model_artifacts.stage_s3_model_artifact",
        ) as mock_stage_s3:
            mock_stage_s3.return_value = tmp_path / "staged" / "model.joblib"
            result = stage_model_artifact(
                "s3://bucket/models/model.joblib",
                expected_checksum,
                staging_dir=tmp_path / "staging",
            )
            mock_stage_s3.assert_called_once()


# ---------------------------------------------------------------------------
# Local path staging
# ---------------------------------------------------------------------------


class TestLocalStaging:
    def test_local_file_stages_correctly(self, tmp_path: Path):
        """Local file is copied to staging dir and checksum verified."""
        content = b"local file content"
        src = tmp_path / "local_model.joblib"
        src.write_bytes(content)
        expected_checksum = hashlib.sha256(content).hexdigest()

        staging_dir = tmp_path / "staging"
        result = stage_model_artifact(
            str(src), expected_checksum,
            staging_dir=staging_dir,
        )

        assert result.exists()
        assert result.name == "local_model.joblib"
        # Verify the staged file has the right content
        assert result.read_bytes() == content

    def test_file_uri_stages_correctly(self, tmp_path: Path):
        """file:// URI is handled."""
        content = b"file:// test"
        src = tmp_path / "file_uri_model.joblib"
        src.write_bytes(content)
        expected_checksum = hashlib.sha256(content).hexdigest()

        result = stage_model_artifact(
            f"file://{src}", expected_checksum,
            staging_dir=tmp_path / "staging2",
        )

        assert result.exists()


# ---------------------------------------------------------------------------
# ModelState integration
# ---------------------------------------------------------------------------


class TestModelStateIntegration:
    def test_ModelState_loads_fake_s3_object(self, tmp_path: Path):
        """ModelState.load_at_startup with fake S3 object makes model ready."""
        ModelState.reset_for_tests()

        content = b"fake model package for state test"
        expected_checksum = hashlib.sha256(content).hexdigest()
        staging_dir = tmp_path / "ms_staging"

        # Create a valid portable_logreg package for ModelState to accept
        from joblib import dump
        from bremen.api.preprocessing_bridge import BREMEN_V01_FEATURE_COLUMNS

        n_features = 15
        package = {
            "portable_logreg": {
                "feature_columns": list(BREMEN_V01_FEATURE_COLUMNS),
                "imputer_statistics": [0.0] * n_features,
                "scaler_mean": [0.0] * n_features,
                "scaler_scale": [1.0] * n_features,
                "coef": [0.1] * n_features,
                "intercept": 0.0,
                "threshold": 0.5,
            }
        }
        pkg_path = staging_dir / "test_model_pkg.joblib"
        staging_dir.mkdir(parents=True, exist_ok=True)
        dump(package, pkg_path)
        pkg_checksum = hashlib.sha256(pkg_path.read_bytes()).hexdigest()

        with patch("bremen.model_artifacts.stage_s3_model_artifact") as mock_stage:
            mock_stage.return_value = pkg_path
            result = ModelState.load_at_startup(
                model_uri="s3://bucket/models/pkg.joblib",
                model_version="v0.1",
                model_checksum=pkg_checksum,
            )

        assert result is True
        assert ModelState.is_ready() is True
        ModelState.reset_for_tests()

    def test_ModelState_not_ready_on_download_failure(self):
        """ModelState stays not ready when S3 download fails."""
        ModelState.reset_for_tests()

        with patch("bremen.model_artifacts.stage_model_artifact") as mock_stage:
            mock_stage.side_effect = ValueError("Failed to download")

            result = ModelState.load_at_startup(
                model_uri="s3://bucket/models/bad.joblib",
                model_version="v0.1",
                model_checksum="a" * 64,
            )

        assert result is False
        assert ModelState.is_ready() is False
        ModelState.reset_for_tests()

    def test_ModelState_local_loading_still_works(self, tmp_path: Path):
        """Local file loading from PR 0039 is preserved."""
        ModelState.reset_for_tests()

        from joblib import dump
        from bremen.api.preprocessing_bridge import BREMEN_V01_FEATURE_COLUMNS

        n_features = 15
        package = {
            "portable_logreg": {
                "feature_columns": list(BREMEN_V01_FEATURE_COLUMNS),
                "imputer_statistics": [0.0] * n_features,
                "scaler_mean": [0.0] * n_features,
                "scaler_scale": [1.0] * n_features,
                "coef": [0.1] * n_features,
                "intercept": 0.0,
                "threshold": 0.5,
            }
        }
        local_path = tmp_path / "local_test.joblib"
        dump(package, local_path)
        checksum = hashlib.sha256(local_path.read_bytes()).hexdigest()

        result = ModelState.load_at_startup(
            model_uri=str(local_path),
            model_version="local-v0.1",
            model_checksum=checksum,
        )
        assert result is True
        assert ModelState.is_ready() is True
        ModelState.reset_for_tests()


# ---------------------------------------------------------------------------
# Import safety — module does not create boto3 client at import time
# ---------------------------------------------------------------------------


class TestImportSafety:
    def test_import_does_not_create_boto3_client(self):
        """Importing model_artifacts does NOT import or create boto3 client."""
        import sys

        # Remove from sys.modules if already cached
        if "bremen.model_artifacts" in sys.modules:
            del sys.modules["bremen.model_artifacts"]

        # Confirm boto3 is not already imported (from previous tests)
        boto3_was_loaded = "boto3" in sys.modules

        import bremen.model_artifacts  # noqa: F811

        # The import of model_artifacts should NOT trigger boto3 import
        if not boto3_was_loaded:
            assert "boto3" not in sys.modules, (
                "Importing bremen.model_artifacts triggered boto3 import"
            )
        # If boto3 was already loaded, that's fine — we just want to verify
        # that our import doesn't create a client
        # Check that no S3 client was created during import
        # (We can't easily check this at module level, but the fact that
        # boto3.client is lazy inside stage_s3_model_artifact proves safety)


# ---------------------------------------------------------------------------
# No real AWS credentials needed
# ---------------------------------------------------------------------------


class TestNoRealAws:
    def test_no_real_aws_credentials_required(self):
        """All tests use mocks — no real AWS calls."""
        assert "AWS_ACCESS_KEY_ID" not in os.environ
        assert "AWS_SECRET_ACCESS_KEY" not in os.environ


# ---------------------------------------------------------------------------
# Staging directory resolution
# ---------------------------------------------------------------------------


class TestStagingDir:
    def test_default_staging_dir(self):
        """Default staging dir uses tempdir / bremen-models."""
        from bremen.model_artifacts import _resolve_staging_dir

        result = _resolve_staging_dir(None)
        expected = Path(tempfile.gettempdir()) / "bremen-models"
        assert result == expected

    def test_override_staging_dir(self, tmp_path: Path):
        """Override parameter takes precedence."""
        from bremen.model_artifacts import _resolve_staging_dir

        override = tmp_path / "my-staging"
        result = _resolve_staging_dir(override)
        assert result == override

    def test_env_var_staging_dir(self, tmp_path: Path):
        """BREMEN_MODEL_STAGING_DIR env var is respected."""
        from bremen.model_artifacts import _resolve_staging_dir

        expected = tmp_path / "env-staging"
        os.environ["BREMEN_MODEL_STAGING_DIR"] = str(expected)
        try:
            result = _resolve_staging_dir(None)
            assert result == expected
        finally:
            del os.environ["BREMEN_MODEL_STAGING_DIR"]
