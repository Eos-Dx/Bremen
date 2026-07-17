"""Demo-specific configuration for H5 container browser demo.

Reads demo config from environment variables.

Standard library only — no third-party dependencies.
"""

from __future__ import annotations

import os

_DEFAULT_DEMO_H5_PREFIX = "demo-uploads/"
_DEFAULT_UPLOAD_MAX_BYTES = 100 * 1024 * 1024  # 100 MB


def read_demo_h5_config(env: dict[str, str] | None = None) -> dict:
    """Read demo H5 container storage configuration.

    Parameters
    ----------
    env : Optional explicit env mapping (for testing).  Defaults to
        ``os.environ``.

    Returns
    -------
    A dict with keys:
    - ``h5_bucket`` (str or None) — configured bucket
    - ``h5_prefix`` (str) — object key prefix
    - ``allow_upload`` (bool) — whether browser upload is enabled
    - ``upload_max_bytes`` (int) — max upload size in bytes
    """
    if env is None:
        env = os.environ

    bucket = env.get("BREMEN_DEMO_H5_BUCKET", "").strip() or None
    prefix_raw = env.get("BREMEN_DEMO_H5_PREFIX", "").strip()
    prefix = prefix_raw if prefix_raw else _DEFAULT_DEMO_H5_PREFIX
    allow_upload = (
        env.get("BREMEN_DEMO_H5_ALLOW_UPLOAD", "true")
        .strip()
        .lower() in ("true", "1", "yes")
    )
    max_bytes_raw = env.get(
        "BREMEN_DEMO_H5_MAX_BYTES", str(_DEFAULT_UPLOAD_MAX_BYTES)
    )
    try:
        upload_max_bytes = int(max_bytes_raw.strip())
    except (ValueError, TypeError):
        upload_max_bytes = _DEFAULT_UPLOAD_MAX_BYTES

    return {
        "h5_bucket": bucket,
        "h5_prefix": prefix,
        "allow_upload": allow_upload,
        "upload_max_bytes": upload_max_bytes,
    }
