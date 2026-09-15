"""Model-package runtime bridge — controlled artifact loading (PR0156).

A narrow, framework-free platform utility that model-package runtimes may use
to deserialize a **checksum-verified, already-staged** artifact.  It performs
no S3 access, no path discovery, no catalog work and no scientific
interpretation: it reads a local file the platform already staged, verifies its
SHA-256 against the expected checksum, and joblib-loads it.  The result is an
opaque Python object (typically a ``dict``) whose scientific meaning is
interpreted only by the consuming model package.

Keeping this single loader here satisfies two goals at once:

- the platform never inspects model-specific scientific contents (it hands the
  opaque object to the package); and
- a model package does not import platform orchestration modules (it imports
  this narrow bridge, whose error vocabulary — ``ValueError("Artifact integrity
  failed")`` / ``RuntimeError("Unsupported artifact")`` — is the established
  contract preserved from ``bremen.api.s3_model_discovery._load_staged_artifact``).

``bremen.api.s3_model_discovery._load_staged_artifact`` re-exports this function
so the existing controlled-loading boundary and its error mapping stay
byte-identical.
"""
from __future__ import annotations

import hashlib
import io
import re
from typing import Any


def load_staged_artifact(local_path: str, expected_checksum: str) -> Any:
    """Runtime-only deferred loading, with checksum checked over the loaded bytes.

    The discovery/catalog path never calls this function.  Keeping controlled
    deserialization here preserves the existing artifact-loading boundary.
    """
    from joblib import load as joblib_load

    try:
        with open(local_path, "rb") as stream:
            content = stream.read()
        if (not re.fullmatch(r"[a-f0-9]{64}", expected_checksum)
                or hashlib.sha256(content).hexdigest() != expected_checksum):
            raise ValueError
    except Exception:
        raise ValueError("Artifact integrity failed") from None
    try:
        return joblib_load(io.BytesIO(content))
    except Exception:
        raise RuntimeError("Unsupported artifact") from None


__all__ = ["load_staged_artifact"]
