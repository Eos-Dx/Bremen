"""Model artifact staging utilities — local and S3 download.

Safe model artifact download and staging with SHA-256 checksum
verification before the staged path is returned.  No deserialization
— returns a file path only.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

_STAGING_DIR_VAR = "BREMEN_MODEL_STAGING_DIR"
_DEFAULT_STAGING = Path(tempfile.gettempdir()) / "bremen-models"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_s3_uri(uri: str) -> tuple[str, str]:
    """Parse an ``s3://bucket/key`` URI into ``(bucket, key)``.

    Parameters
    ----------
    uri : S3 URI string, e.g. ``s3://my-bucket/path/to/object.joblib``.

    Returns
    -------
    A ``(bucket, key)`` tuple.

    Raises
    ------
    ValueError
        If the URI is malformed, bucket is empty, or key is empty.
    """
    if not uri.startswith("s3://"):
        raise ValueError(f"URI must start with 's3://', got: {uri!r}")

    rest = uri[len("s3://"):]
    parts = rest.split("/", 1)

    bucket = parts[0]
    key = parts[1] if len(parts) > 1 else ""

    if not bucket:
        raise ValueError(f"S3 URI has empty bucket: {uri!r}")

    if not key:
        raise ValueError(f"S3 URI has empty key: {uri!r}")

    return bucket, key


def verify_file_sha256(path: str | Path, expected_checksum: str) -> None:
    """Verify a file's SHA-256 checksum.

    Supports ``sha256:<hex>`` and bare hex formats.
    Deletes the file on mismatch.

    Parameters
    ----------
    path : Path to the file to verify.
    expected_checksum : Expected SHA-256 hex digest (with or without
        ``sha256:`` prefix).

    Raises
    ------
    ValueError
        If the checksum does not match.  The file is deleted on failure.
    """
    p = Path(path)
    if not p.exists():
        raise ValueError(f"File not found for checksum verification: {p}")

    hex_digest = expected_checksum
    if hex_digest.startswith("sha256:"):
        hex_digest = hex_digest[len("sha256:"):]

    if len(hex_digest) != 64:
        raise ValueError(
            f"Expected 64-char hex digest, got {len(hex_digest)} chars: "
            f"{hex_digest!r}"
        )

    computed = _compute_sha256(p)
    if computed != hex_digest:
        # Delete bad file before raising
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass
        raise ValueError(
            f"SHA-256 mismatch for {p}: "
            f"computed={computed}, expected={hex_digest}"
        )


def stage_model_artifact(
    uri: str,
    expected_checksum: str,
    staging_dir: str | Path | None = None,
) -> Path:
    """Download and stage a model artifact, verifying its checksum.

    Supports:
    - Local filesystem paths (unchanged behavior).
    - ``file://`` URIs (unchanged behavior).
    - ``s3://`` URIs (new in PR 0040).

    Parameters
    ----------
    uri : The model URI or filesystem path.
    expected_checksum : Expected SHA-256 hex digest.
    staging_dir : Override for the staging directory.  Defaults to
        ``tempfile.gettempdir() / "bremen-models"`` or the
        ``BREMEN_MODEL_STAGING_DIR`` environment variable.

    Returns
    -------
    The ``Path`` to the staged file (checksum verified).

    Raises
    ------
    ValueError
        On download failure, checksum mismatch, or invalid URI.
    """
    staging_path = _resolve_staging_dir(staging_dir)

    if uri.startswith("s3://"):
        bucket, key = parse_s3_uri(uri)
        staged = stage_s3_model_artifact(
            bucket, key, expected_checksum, staging_path
        )
    else:
        staged = _stage_local_artifact(uri, expected_checksum, staging_path)

    return staged


def stage_s3_model_artifact(
    bucket: str,
    key: str,
    expected_checksum: str,
    staging_dir: str | Path,
    *,
    s3_client: Any = None,
) -> Path:
    """Download an S3 object, verify SHA-256, stage locally.

    Uses ``boto3.client('s3')`` by default.
    ``s3_client`` parameter is injectable for testing.

    Parameters
    ----------
    bucket : S3 bucket name.
    key : S3 object key.
    expected_checksum : Expected SHA-256 hex digest (bare hex or
        ``sha256:`` prefix).
    staging_dir : Directory for staged files.
    s3_client : Optional S3 client.  If ``None``, imports ``boto3``
        lazily and creates a client.

    Returns
    -------
    The ``Path`` to the staged file (checksum verified).

    Raises
    ------
    ValueError
        On download failure or checksum mismatch.
    """
    staging_dir = Path(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    # Determine a safe filename from the key
    filename = Path(key).name or f"{bucket}-{key.replace('/', '_')}.joblib"
    final_path = staging_dir / filename

    # Download to temp file first
    fd, tmp_path_str = tempfile.mkstemp(
        suffix=".tmp",
        prefix="bremen-",
        dir=str(staging_dir),
    )
    tmp_path = Path(tmp_path_str)
    try:
        if s3_client is None:
            from boto3 import client as _s3_client  # noqa: PLC0415

            s3_client = _s3_client("s3")

        s3_client.download_file(bucket, key, str(tmp_path))
    except Exception as exc:
        # Clean up temp file on download failure
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise ValueError(f"S3 download failed: {exc}") from exc

    # Verify checksum before finalising
    try:
        verify_file_sha256(tmp_path, expected_checksum)
    except ValueError:
        # verify_file_sha256 already deletes the tmp file on mismatch
        raise

    # Atomically rename to final path
    shutil.move(str(tmp_path), str(final_path))

    return final_path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_staging_dir(
    override: str | Path | None = None,
) -> Path:
    """Resolve the staging directory path.

    Priority:
    1. ``override`` parameter.
    2. ``BREMEN_MODEL_STAGING_DIR`` environment variable.
    3. ``tempfile.gettempdir() / "bremen-models"``.
    """
    if override is not None:
        return Path(override)

    env_dir = os.environ.get(_STAGING_DIR_VAR)
    if env_dir:
        return Path(env_dir)

    return _DEFAULT_STAGING


def _stage_local_artifact(
    uri: str,
    expected_checksum: str,
    staging_dir: Path,
) -> Path:
    """Stage a local filesystem artifact by copying it."""
    local_path = uri
    if local_path.startswith("file://"):
        local_path = local_path[len("file://"):]

    src = Path(local_path)
    if not src.exists():
        raise ValueError(f"Local artifact not found: {src}")

    staging_dir.mkdir(parents=True, exist_ok=True)
    dest = staging_dir / src.name

    shutil.copy2(src, dest)

    try:
        verify_file_sha256(dest, expected_checksum)
    except ValueError:
        # Delete on checksum mismatch
        try:
            dest.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    return dest


def _compute_sha256(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
