"""Sources application operations."""

from __future__ import annotations
import logging
import uuid as _uuid
from datetime import datetime, timezone
from bremen.platform.jobs.repository import _staged_uploads, _uploads_lock

_log = logging.getLogger(__name__)


class StagedUpload:
    """Record of a staged file upload."""

    def __init__(
        self,
        upload_id: str,
        h5_path: str,
        filename: str,
        size_bytes: int,
        created_at: str,
        consumed: bool = False,
    ) -> None:
        self.upload_id = upload_id
        self.h5_path = h5_path
        self.filename = filename
        self.size_bytes = size_bytes
        self.created_at = created_at
        self.consumed = consumed


def register_staged_upload(
    h5_path: str,
    filename: str,
    size_bytes: int,
) -> str:
    """Register a staged upload and return an opaque upload_id.

    The upload is stored in the in-memory registry and consumed
    when a job uses it.  The file is cleaned up after consumption
    or after a timeout period.
    """
    upload_id = str(_uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    upload = StagedUpload(
        upload_id=upload_id,
        h5_path=h5_path,
        filename=filename,
        size_bytes=size_bytes,
        created_at=now,
    )
    with _uploads_lock:
        _staged_uploads[upload_id] = upload
    return upload_id


def resolve_upload(upload_id: str) -> str | None:
    """Resolve an upload_id to a local h5_path with ownership transfer.

    Returns None if the upload_id is unknown or already consumed.
    The upload entry is atomically removed from the registry and
    ownership of the temp file is transferred to the caller.
    """
    with _uploads_lock:
        upload = _staged_uploads.pop(upload_id, None)
        if upload is None:
            return None
        if upload.consumed:
            return None
        upload.consumed = True
        return upload.h5_path


def resolve_source(
    source_id: str | None,
    upload_id: str | None,
    *, consume: bool = True,
) -> str:
    """Resolve a source reference to a local filesystem path.

    Parameters
    ----------
    source_id : An opaque source_id for a catalog object, or None.
    upload_id : An opaque upload_id for a staged file, or None.

    Returns
    -------
    The resolved local filesystem h5_path.

    Raises
    ------
    ValueError
        If source resolution fails with a typed safe error.
    """
    from bremen.demo_config import read_demo_h5_config
    from bremen.h5_inputs import stage_h5_input
    from bremen.platform.sources.registry import resolve_source_id as _resolve_source_id

    if source_id and upload_id:
        raise ValueError("Only one of source_id or upload_id may be provided.")

    if source_id:
        # Resolve S3 catalog source through opaque registry
        config = read_demo_h5_config()
        if config["h5_bucket"] is None:
            raise ValueError(
                "H5 storage not configured. "
                "Set BREMEN_DEMO_H5_BUCKET to enable catalog selection."
            )

        # Resolve via opaque registry — validates bucket, prefix, existence, expiry,
        # extension, and size constraints
        try:
            object_key, filename, size_bytes = _resolve_source_id(
                source_id,
                current_bucket=config["h5_bucket"],
                current_prefix=config["h5_prefix"],
                consume=consume,
            )
        except ValueError:
            # Re-raise the safe typed error from the registry
            raise

        # Validate size against current limit
        max_bytes = config["upload_max_bytes"]
        if size_bytes > max_bytes:
            raise ValueError("The selected source exceeds the maximum size limit.")

        # Construct S3 URI from server-side config only (no browser input)
        s3_uri = f"s3://{config['h5_bucket']}/{object_key}"
        try:
            staged_path = stage_h5_input(s3_uri)
            return str(staged_path)
        except (ValueError, OSError, IOError) as exc:
            # stage_h5_input raises ValueError on S3 download failure
            raise ValueError(
                "Could not download the selected source from storage."
            ) from exc

    elif upload_id:
        # Resolve upload from registry
        if consume:
            h5_path = resolve_upload(upload_id)
        else:
            with _uploads_lock:
                upload = _staged_uploads.get(upload_id)
                h5_path = upload.h5_path if upload and not upload.consumed else None
        if h5_path is None:
            raise ValueError(
                "The uploaded file is no longer available. Please re-upload the file."
            )
        return h5_path

    else:
        raise ValueError(
            "A source_id or upload_id is required to create an analysis job."
        )


def _cleanup_expired_uploads() -> None:
    """Remove expired uploads from the registry and clean up temp files.

    Uploads older than 1 hour are considered expired and are removed.
    File deletion is performed within the lock to prevent race conditions
    with concurrent consumption.
    """
    import os as _os

    now = datetime.now(timezone.utc)
    expiry_seconds = 3600  # 1 hour
    with _uploads_lock:
        expired_ids = []
        for uid, upload in list(_staged_uploads.items()):
            try:
                created = datetime.fromisoformat(upload.created_at)
                if (now - created).total_seconds() > expiry_seconds:
                    expired_ids.append(uid)
            except (ValueError, TypeError):
                expired_ids.append(uid)

        for uid in expired_ids:
            upload = _staged_uploads.pop(uid, None)
            if upload and upload.h5_path:
                try:
                    _os.unlink(upload.h5_path)
                except OSError:
                    pass


def extract_patient_display_name(h5_path: str) -> str:
    """Safely extract patient display name from H5 metadata.

    Reads /session/sample/patient_name from the H5 file.
    Returns empty string if unavailable, unsafe, or extraction fails.
    Never raises — fault-tolerant by design.
    """
    if not h5_path:
        return ""
    try:
        import h5py  # noqa: PLC0415

        with h5py.File(h5_path, "r") as f:
            for sample_path in [
                "/session/sample",
                "/scans/target",
                "/scans/contralateral",
            ]:
                full = f"{sample_path}/patient_name"
                if full not in f:
                    continue
                try:
                    item = f[full]
                    raw = item[()]
                    if isinstance(raw, bytes):
                        val = raw.decode("utf-8")
                    elif isinstance(raw, str):
                        val = raw
                    else:
                        val = str(raw)
                    val = val.strip()
                    if not val:
                        continue
                    # Safety checks
                    if len(val) > 80:
                        continue
                    if "s3://" in val or "/tmp/" in val or "/" in val:
                        continue
                    if any(
                        c in val for c in ["\\", "traceback", "exception", "bucket"]
                    ):
                        continue
                    return val
                except Exception:
                    continue
    except Exception:
        pass
    return ""
