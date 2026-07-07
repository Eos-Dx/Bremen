"""Tests for ``src/bremen/h5_inputs.py`` — S3 H5 input staging.

All tests use fake/injectable S3 clients and temporary directories.
No real S3 access, no real H5 files.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bremen.h5_inputs import stage_h5_input


# ---------------------------------------------------------------------------
# A. test_h5_input_staging_downloads_s3_object
# ---------------------------------------------------------------------------


class TestStagingDownloads:
    """Verify stage_h5_input downloads S3 objects correctly."""

    def test_h5_input_staging_downloads_s3_object(self, tmp_path: Path):
        """Fake S3 client: correct bucket/key, staged path under tmp_path,
        file exists, no path traversal."""
        content = b"fake h5 content for staging test"
        captured_bucket = None
        captured_key = None

        mock_client = MagicMock()

        def fake_download(Bucket, Key, Filename):
            nonlocal captured_bucket, captured_key
            captured_bucket = Bucket
            captured_key = Key
            Path(Filename).write_bytes(content)

        mock_client.download_file.side_effect = fake_download

        staging_dir = tmp_path / "staging"
        result = stage_h5_input(
            "s3://test-bucket/path/to/input.h5",
            staging_dir=staging_dir,
            s3_client=mock_client,
        )

        # Assert correct bucket/key passed to download
        assert captured_bucket == "test-bucket"
        assert captured_key == "path/to/input.h5"

        # Assert staged path is under tmp_path
        assert str(result).startswith(str(staging_dir)), (
            f"Staged path {result} not under staging dir {staging_dir}"
        )

        # Assert file exists
        assert result.exists(), f"Staged file {result} does not exist"
        assert result.read_bytes() == content

        # Assert no path traversal
        assert ".." not in str(result)


# ---------------------------------------------------------------------------
# B. test_h5_input_staging_verifies_checksum_success
# ---------------------------------------------------------------------------


class TestChecksumSuccess:
    """Checksum verification succeeds when expected matches actual."""

    def test_h5_input_staging_verifies_checksum_success(self, tmp_path: Path):
        """Fake download writes known bytes, expected sha256 matches."""
        content = b"content for checksum success test"
        expected_checksum = hashlib.sha256(content).hexdigest()

        mock_client = MagicMock()

        def fake_download(Bucket, Key, Filename):
            Path(Filename).write_bytes(content)

        mock_client.download_file.side_effect = fake_download

        staging_dir = tmp_path / "staging_checksum_ok"
        result = stage_h5_input(
            "s3://bucket/checksum_ok.h5",
            staging_dir=staging_dir,
            expected_checksum=expected_checksum,
            s3_client=mock_client,
        )

        # Assert function returns Path
        assert isinstance(result, Path)
        # Assert file exists at the returned path
        assert result.exists()
        # Assert content is what we wrote
        assert result.read_bytes() == content


# ---------------------------------------------------------------------------
# C. test_h5_input_staging_rejects_checksum_mismatch
# ---------------------------------------------------------------------------


class TestChecksumMismatch:
    """Checksum mismatch raises ValueError and cleans up."""

    def test_h5_input_staging_rejects_checksum_mismatch(self, tmp_path: Path):
        """Fake download writes known bytes, expected sha256 mismatches."""
        content = b"content for checksum mismatch test"
        # Deliberately wrong checksum
        wrong_checksum = hashlib.sha256(b"different content").hexdigest()

        mock_client = MagicMock()

        def fake_download(Bucket, Key, Filename):
            Path(Filename).write_bytes(content)

        mock_client.download_file.side_effect = fake_download

        staging_dir = tmp_path / "staging_checksum_bad"

        with pytest.raises(ValueError, match="SHA-256 mismatch"):
            stage_h5_input(
                "s3://bucket/checksum_bad.h5",
                staging_dir=staging_dir,
                expected_checksum=wrong_checksum,
                s3_client=mock_client,
            )

        # Verify that no invalid staged file was left as valid input
        # The temp file should have been deleted by verify_file_sha256
        remaining_files = list(staging_dir.iterdir()) if staging_dir.exists() else []
        for f in remaining_files:
            # Only .tmp files may remain (if cleanup didn't fully happen),
            # but no .h5 file should be present
            assert not f.name.endswith(".h5"), (
                f"Invalid staged file left behind: {f}"
            )


# ---------------------------------------------------------------------------
# D. test_h5_input_staging_rejects_non_s3_uri
# ---------------------------------------------------------------------------


class TestRejectNonS3:
    """Non-s3 URIs are rejected early."""

    def test_h5_input_staging_rejects_non_s3_uri(self, tmp_path: Path):
        """h5_uri=https://example.com/file.h5 raises ValueError."""
        with pytest.raises(ValueError, match="must start with 's3://'"):
            stage_h5_input(
                "https://example.com/file.h5",
                staging_dir=tmp_path / "staging",
            )


# ---------------------------------------------------------------------------
# E. test_h5_input_staging_logs_safe_metadata
# ---------------------------------------------------------------------------


class TestLoggingSafety:
    """Verify safe log events and no forbidden fields."""

    def test_h5_input_staging_logs_safe_metadata(self, tmp_path: Path, caplog):
        """Fake S3 download: safe events present, forbidden fields absent."""
        caplog.set_level(logging.INFO)
        content = b"content for logging test"
        expected_checksum = hashlib.sha256(content).hexdigest()

        mock_client = MagicMock()

        def fake_download(Bucket, Key, Filename):
            Path(Filename).write_bytes(content)

        mock_client.download_file.side_effect = fake_download

        staging_dir = tmp_path / "staging_logging"
        result = stage_h5_input(
            "s3://bucket/log_test.h5",
            staging_dir=staging_dir,
            expected_checksum=expected_checksum,
            s3_client=mock_client,
        )
        assert result.exists()

        log_text = caplog.text

        # Assert safe events present
        assert "bremen.h5_input.stage.start" in log_text
        assert "bremen.h5_input.stage.success" in log_text
        assert "bremen.h5_input.checksum.verify.success" in log_text

        # Assert safe fields in stage.start
        assert "uri_scheme=s3" in log_text
        assert "h5_basename=log_test.h5" in log_text
        assert "checksum_present=true" in log_text

        # Assert size_bytes in stage.success
        assert "size_bytes=" in log_text

        # Assert checksum_algorithm in checksum success
        assert "checksum_algorithm=sha256" in log_text

        # Assert forbidden fields NOT in logs
        assert "s3://bucket/log_test.h5" not in log_text, (
            "Full S3 URI must not appear in logs"
        )
        assert "/Users/" not in log_text, (
            "Local /Users/ paths must not appear in logs"
        )
        # Raw checksum hex should not appear
        assert expected_checksum not in log_text, (
            "Raw checksum hex must not appear in logs"
        )
