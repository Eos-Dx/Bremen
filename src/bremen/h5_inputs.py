"""H5 input staging — download from S3, verify checksum, stage locally.

Narrow module that provides a single public function ``stage_h5_input()``
for staging H5 files from S3 URIs to a local staging directory before
inference.

Reuses ``parse_s3_uri`` and ``verify_file_sha256`` from
``bremen.model_artifacts`` — no duplicated S3 parsing or checksum logic.
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

_DEFAULT_STAGING_DIR = Path("/tmp/bremen-inputs")


def stage_h5_input(
    h5_uri: str,
    staging_dir: str | Path = _DEFAULT_STAGING_DIR,
    expected_checksum: str | None = None,
    *,
    s3_client: Any = None,
) -> Path:
    """Stage an H5 file from S3 to a local staging directory.

    Downloads the object to a temporary file under *staging_dir*,
    optionally verifies its SHA-256 checksum, then atomically moves
    it to its final staged path.  On checksum mismatch or download
    failure, the temporary file is deleted and ``ValueError`` raised.

    Parameters
    ----------
    h5_uri :
        ``s3://bucket/key`` URI of the H5 object.
    staging_dir :
        Local staging directory.  Created if it does not exist.
        Defaults to ``/tmp/bremen-inputs``.
    expected_checksum :
        Optional ``sha256:<64hex>`` checksum.  If provided, the
        downloaded file is verified before the staged path is returned.
        Case-insensitive hex.
    s3_client :
        Injectable S3 client for testing.  If ``None``, ``boto3`` is
        imported lazily and a client created.

    Returns
    -------
    ``Path`` to the staged file (checksum verified if expected).

    Raises
    ------
    ValueError
        If *h5_uri* does not start with ``s3://``, download fails, or
        checksum verification fails.
    """
    from .model_artifacts import parse_s3_uri, verify_file_sha256  # noqa: PLC0415

    # Validate URI scheme
    if not h5_uri.startswith("s3://"):
        raise ValueError(f"h5_uri must start with 's3://', got: {h5_uri!r}")

    staging = Path(staging_dir)
    staging.mkdir(parents=True, exist_ok=True)

    # Parse bucket/key
    bucket, key = parse_s3_uri(h5_uri)

    # Derive safe local filename: S3 basename + deterministic hash of key
    basename = Path(key).name or f"{bucket}-{key.replace('/', '_')}.h5"
    # Reject path traversal in basename
    if ".." in basename or "/" in basename:
        raise ValueError(f"Unsafe basename derived from S3 key: {basename!r}")

    # Hashing key for deterministic local suffix (prevents collision)
    key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    staged_name = f"{basename}_{key_hash}.h5"
    final_path = staging / staged_name

    checksum_present = expected_checksum is not None

    _logger.info(
        "bremen.h5_input.stage.start\t"
        "stage=h5_input\tstatus=started\t"
        "uri_scheme=s3\t"
        "h5_basename=%s\t"
        "checksum_present=%s",
        basename,
        str(checksum_present).lower(),
    )

    # Download to temp file first
    fd, tmp_path_str = tempfile.mkstemp(
        suffix=".tmp",
        prefix="bremen-h5-",
        dir=str(staging),
    )
    tmp_path = Path(tmp_path_str)
    os.close(fd)  # Close file descriptor; we'll use Path operations

    try:
        if s3_client is None:
            from boto3 import client as _s3_client  # noqa: PLC0415

            s3_client = _s3_client("s3")

        s3_client.download_file(bucket, key, str(tmp_path))
        size_bytes = tmp_path.stat().st_size
    except Exception as exc:
        # Clean up temp file on download failure
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        _logger.error(
            "bremen.h5_input.stage.failure\t"
            "stage=h5_input\tstatus=failed\t"
            "reason=s3_download_failed\t"
            "exception_class=%s\t"
            "safe_reason=%s",
            type(exc).__name__,
            str(exc).split(".")[0][:200],
        )
        raise ValueError(f"S3 download failed for {basename}: {exc}") from exc

    # Verify checksum if requested
    if expected_checksum is not None:
        try:
            verify_file_sha256(tmp_path, expected_checksum)
            _logger.info(
                "bremen.h5_input.checksum.verify.success\t"
                "stage=checksum\tstatus=completed\t"
                "checksum_algorithm=sha256",
            )
        except ValueError:
            _logger.error(
                "bremen.h5_input.checksum.verify.failure\t"
                "stage=checksum\tstatus=failed\t"
                "reason=checksum_mismatch",
            )
            # verify_file_sha256 already deletes the tmp file on mismatch
            raise

    # Atomically move to final path
    shutil.move(str(tmp_path), str(final_path))

    _logger.info(
        "bremen.h5_input.stage.success\t"
        "stage=h5_input\tstatus=completed\t"
        "size_bytes=%s",
        str(size_bytes),
    )

    return final_path
