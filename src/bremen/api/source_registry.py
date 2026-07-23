"""Opaque source registry for S3 catalog objects.

Creates server-generated opaque source_ids at selection time and
maintains a server-side mapping to bucket/object-key pairs.
Used by GET /demo/api/h5/containers and resolve_source().

PR0082a — Control Room Data and Selection Foundation.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# StagedSource — server-side record of a registered S3 catalog source
# ---------------------------------------------------------------------------


class StagedSource:
    """Server-side record of an opaque source_id -> S3 object mapping."""

    def __init__(
        self,
        source_id: str,
        bucket: str,
        object_key: str,
        filename: str,
        size_bytes: int,
        created_at: str,
        prefix: str,
        consumed: bool = False,
    ) -> None:
        self.source_id = source_id
        self.bucket = bucket
        self.object_key = object_key
        self.filename = filename
        self.size_bytes = size_bytes
        self.created_at = created_at
        self.prefix = prefix
        self.consumed = consumed


# ---------------------------------------------------------------------------
# Module-level registry (process-local, ephemeral)
# ---------------------------------------------------------------------------

_registry: dict[str, StagedSource] = {}
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def register_source(
    bucket: str,
    object_key: str,
    filename: str,
    size_bytes: int,
    prefix: str,
) -> str:
    """Register an S3 catalog object and return an opaque source_id.

    The source_id is a server-generated UUID.  The bucket, object_key,
    and prefix are stored server-side and never exposed to the browser.

    Returns
    -------
    The opaque source_id string.
    """
    source_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    source = StagedSource(
        source_id=source_id,
        bucket=bucket,
        object_key=object_key,
        filename=filename,
        size_bytes=size_bytes,
        created_at=now,
        prefix=prefix,
    )
    with _lock:
        _registry[source_id] = source
    return source_id


def resolve_source_id(
    source_id: str,
    current_bucket: str,
    current_prefix: str,
) -> tuple[str, str, int]:
    """Resolve an opaque source_id against current configuration.

    Validates:
    - source_id exists in the registry.
    - source_id has not been consumed.
    - bucket matches current configured bucket.
    - prefix matches current configured prefix.
    - source has not expired (> 1 hour).
    - object extension is a supported H5 format.

    Parameters
    ----------
    source_id : The opaque source_id from the browser.
    current_bucket : Current configured BREMEN_DEMO_H5_BUCKET.
    current_prefix : Current configured BREMEN_DEMO_H5_PREFIX.

    Returns
    -------
    A tuple of (object_key, filename, size_bytes).

    Raises
    ------
    ValueError
        With typed safe error message if resolution fails.
    """
    import os as _os

    with _lock:
        source = _registry.get(source_id)
        if source is None:
            raise ValueError(
                "The selected source is no longer available. "
                "Please select another container or re-upload."
            )

        # Check expiry (> 1 hour)
        try:
            created = datetime.fromisoformat(source.created_at)
            now = datetime.now(timezone.utc)
            if (now - created).total_seconds() > 3600:
                # Expired — remove from registry
                _registry.pop(source_id, None)
                raise ValueError(
                    "The selected source has expired. "
                    "Please refresh the catalog and try again."
                )
        except (ValueError, TypeError):
            _registry.pop(source_id, None)
            raise ValueError(
                "The selected source is no longer available."
            )

        # Must not be consumed
        if source.consumed:
            raise ValueError(
                "The selected source has already been used. "
                "Please select another container."
            )

        # Bucket must match current configuration
        if source.bucket != current_bucket:
            _registry.pop(source_id, None)
            raise ValueError(
                "The selected source is no longer available. "
                "Please select another container or re-upload."
            )

        # Prefix must match (prevents out-of-prefix selection)
        if source.prefix != current_prefix:
            _registry.pop(source_id, None)
            raise ValueError(
                "The selected source is no longer available. "
                "Please select another container or re-upload."
            )

        # Validate extension — supported H5 formats only
        key_lower = source.object_key.lower()
        if not (key_lower.endswith(".h5") or key_lower.endswith(".hdf5")):
            _registry.pop(source_id, None)
            raise ValueError(
                "The selected source has an unsupported format."
            )

        # Mark as consumed
        source.consumed = True

        return (source.object_key, source.filename, source.size_bytes)


def mark_source_stale(source_id: str) -> None:
    """Mark a source_id as stale so it cannot be used.

    Called when the registry entry is no longer valid (e.g., after
    catalog refresh where the item disappeared).
    """
    with _lock:
        source = _registry.get(source_id)
        if source is not None:
            source.consumed = True


def get_source_info(source_id: str) -> dict[str, Any] | None:
    """Return safe display metadata for a source_id, or None if unknown."""
    with _lock:
        source = _registry.get(source_id)
        if source is None:
            return None
        return {
            "source_id": source.source_id,
            "filename": source.filename,
            "size_bytes": source.size_bytes,
        }


def reset_for_tests() -> None:
    """Clear the registry (test-only)."""
    with _lock:
        _registry.clear()
