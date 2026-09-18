"""Jobs application operations."""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any

_log = logging.getLogger(__name__)


def _clean_metadata_field(value: Any) -> str:
    """PR0157: normalize an optional request metadata field for report mapping.

    Free-text author/comment fields must never smuggle paths, URIs, or secrets
    into the public standard result; oversized or unsafe values collapse to
    empty string rather than being echoed or truncated to something plausible.
    """
    import re

    if not isinstance(value, str):
        return ""
    clean = value.strip()
    if not clean or len(clean) > 240:
        return ""
    if "://" in clean or clean.startswith(("/", "\\", "~")):
        return ""
    if re.search(r"(aws|token|secret|password|s3|bearer)", clean, re.IGNORECASE):
        return ""
    # Allow only printable non-control characters.
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in clean):
        return ""
    return clean


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
