"""Feature artifact ingestion boundary — validates precomputed feature
artifacts from upstream preprocessing.

PR0058 — Option C: Bremen runtime accepts precomputed feature
artifacts rather than raw upstream container data.

This module duplicates the feature column list from
``src/bremen/api/preprocessing_bridge.BREMEN_V01_FEATURE_COLUMNS``
intentionally.  This preserves independence from the H5-based
preprocessing bridge and avoids coupling the feature artifact
ingestion path to H5 layout assumptions.  The two lists must be kept
in sync.  A future PR may extract a shared feature column constant.

No model loading, no inference, no H5 parsing, no network calls.
Standard-library only — no numpy, h5py, joblib, pyFAI, fabio,
xrd_preprocessing, or eosdx-container imports.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

FEATURE_ARTIFACT_SCHEMA_VERSION = "bremen.feature_artifact.v0.1"
FEATURE_ARTIFACT_KIND = "bremen.precomputed_features"

# Duplicated intentionally from src/bremen/api/preprocessing_bridge.py
# BREMEN_V01_FEATURE_COLUMNS.  Kept independent from H5-based bridge.
REQUIRED_FEATURE_COLUMNS: tuple[str, ...] = (
    "weightedrms1",
    "sigma_l1",
    "sigma_r1",
    "mahalanobis1",
    "weightedrms2",
    "sigma_l2",
    "sigma_r2",
    "mahalanobis2",
    "peak14_intensity",
    "mean_peak_value_raw",
    "wasserstein_distance_muLR",
    "cosine_distance_full_q2",
    "wasserstein_distance_full_q2",
    "meanrms1",
    "meanrms2",
)

_EXPECTED_FEATURE_COUNT = len(REQUIRED_FEATURE_COLUMNS)

# ---------------------------------------------------------------------------
# Metadata safety — prohibited key patterns (case-insensitive substring)
# ---------------------------------------------------------------------------

_PROHIBITED_METADATA_KEY_PATTERNS: tuple[str, ...] = (
    "_id",
    "_ref",
    "_path",
    "_uri",
    "_checksum",
    "secret",
    "token",
    "password",
    "account",
    "key",
)

# ---------------------------------------------------------------------------
# Metadata safety — forbidden value patterns
# ---------------------------------------------------------------------------

_FORBIDDEN_VALUE_PATTERNS: tuple[str, ...] = (
    "AKIA",
    "s3://",
    "sha256:",
    "Nova_",
    "/Users/",
    "/home/",
    "SECRET_ACCESS_KEY",
    "dkr.ecr",
)

# 12-digit numeric string → account ID detection
_ACCOUNT_ID_RE = re.compile(r"^\d{12}$")

# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class FeatureArtifactError(Exception):
    """Base exception for feature artifact errors."""


class FeatureArtifactValidationError(FeatureArtifactError):
    """Validation failure — artifact data does not satisfy the contract."""


class FeatureArtifactSchemaError(FeatureArtifactError):
    """Schema version or artifact kind mismatch."""


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _is_finite_numeric(value: object) -> bool:
    """Return True if *value* is a finite numeric type (not NaN, not Inf)."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(value)
    return False


def _check_unsafe_metadata(metadata: dict[str, Any]) -> list[str]:
    """Check metadata dict for prohibited keys and values.

    Returns a list of warning strings describing each unsafe entry.
    Does not raise — the caller decides whether to reject or warn.
    """
    warnings: list[str] = []

    for key, value in metadata.items():
        key_lower = key.lower()
        for pattern in _PROHIBITED_METADATA_KEY_PATTERNS:
            if pattern in key_lower:
                warnings.append(
                    f"Unsafe metadata key '{key}' matches "
                    f"prohibited pattern '{pattern}'"
                )
                break

        # Check value only if it's a string
        if isinstance(value, str):
            if _check_forbidden_value(value):
                warnings.append(
                    f"Metadata value for key '{key}' contains "
                    f"forbidden content"
                )

    return warnings


def _check_forbidden_value(value: str) -> bool:
    """Return True if *value* matches any forbidden pattern."""
    for pattern in _FORBIDDEN_VALUE_PATTERNS:
        if pattern in value:
            return True
    if _ACCOUNT_ID_RE.match(value):
        return True
    return False


def _check_unsafe_metadata_strict(metadata: dict[str, Any]) -> None:
    """Check metadata for unsafe keys/values and raise on the first violation.

    Raises FeatureArtifactValidationError on any unsafe entry.
    """
    warnings = _check_unsafe_metadata(metadata)
    if warnings:
        raise FeatureArtifactValidationError(
            f"Unsafe metadata: {'; '.join(warnings)}"
        )


# ---------------------------------------------------------------------------
# Core validation
# ---------------------------------------------------------------------------


def validate_feature_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalise a feature artifact dict.

    Parameters
    ----------
    artifact : Raw artifact dict from the caller.

    Returns
    -------
    A validated dict with ``feature_values`` ordered to match
    ``REQUIRED_FEATURE_COLUMNS`` and coerced to ``float``.

    Raises
    ------
    FeatureArtifactSchemaError
        If ``schema_version`` or ``artifact_kind`` is incorrect.
    FeatureArtifactValidationError
        If any validation rule fails.
    """

    # ---- schema_version ----
    sv = artifact.get("schema_version")
    if sv != FEATURE_ARTIFACT_SCHEMA_VERSION:
        raise FeatureArtifactSchemaError(
            f"Expected schema_version {FEATURE_ARTIFACT_SCHEMA_VERSION!r}, "
            f"got {sv!r}"
        )

    # ---- artifact_kind ----
    ak = artifact.get("artifact_kind")
    if ak != FEATURE_ARTIFACT_KIND:
        raise FeatureArtifactSchemaError(
            f"Expected artifact_kind {FEATURE_ARTIFACT_KIND!r}, "
            f"got {ak!r}"
        )

    # ---- feature_columns ----
    columns: Any = artifact.get("feature_columns")
    if not isinstance(columns, list) or len(columns) != _EXPECTED_FEATURE_COUNT:
        raise FeatureArtifactValidationError(
            f"feature_columns must be a list of {_EXPECTED_FEATURE_COUNT} "
            f"strings, got {columns!r}"
        )

    # Reject duplicate feature names
    if len(set(columns)) != len(columns):
        raise FeatureArtifactValidationError(
            "feature_columns contains duplicate feature names"
        )

    # Reject non-string feature names
    for i, col in enumerate(columns):
        if not isinstance(col, str):
            raise FeatureArtifactValidationError(
                f"feature_columns[{i}] must be a string, got {type(col).__name__}"
            )

    # Reject missing or extra features
    for col in columns:
        if col not in REQUIRED_FEATURE_COLUMNS:
            raise FeatureArtifactValidationError(
                f"Unknown feature column {col!r} — not in required set"
            )

    for req in REQUIRED_FEATURE_COLUMNS:
        if req not in columns:
            raise FeatureArtifactValidationError(
                f"Missing required feature column {req!r}"
            )

    # ---- feature_values ----
    values: Any = artifact.get("feature_values")
    if not isinstance(values, list) or len(values) != _EXPECTED_FEATURE_COUNT:
        raise FeatureArtifactValidationError(
            f"feature_values must be a list of {_EXPECTED_FEATURE_COUNT} "
            f"numeric values, got {values!r}"
        )

    # Validate each value
    for i, val in enumerate(values):
        if isinstance(val, bool):
            raise FeatureArtifactValidationError(
                f"feature_values[{i}] is a boolean — "
                f"numeric value required, got {val!r}"
            )
        if not isinstance(val, (int, float)):
            raise FeatureArtifactValidationError(
                f"feature_values[{i}] is not numeric: "
                f"{type(val).__name__} {val!r}"
            )
        if not math.isfinite(val):
            raise FeatureArtifactValidationError(
                f"feature_values[{i}] is not finite: {val!r}"
            )

    # ---- Normalise values to required column order ----
    col_to_val: dict[str, float] = {}
    for col, val in zip(columns, values):
        col_to_val[col] = float(val)

    normalised_values: list[float] = []
    for req in REQUIRED_FEATURE_COLUMNS:
        normalised_values.append(col_to_val[req])

    # ---- metadata (optional) ----
    metadata = artifact.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise FeatureArtifactValidationError(
                "metadata must be a dict if present"
            )
        _check_unsafe_metadata_strict(metadata)

    # ---- Build validated result ----
    return {
        "schema_version": FEATURE_ARTIFACT_SCHEMA_VERSION,
        "artifact_kind": FEATURE_ARTIFACT_KIND,
        "feature_columns": list(REQUIRED_FEATURE_COLUMNS),
        "feature_values": normalised_values,
        "metadata": metadata,
    }


# ---------------------------------------------------------------------------
# Convenience loaders
# ---------------------------------------------------------------------------


def load_feature_artifact_from_dict(
    artifact: dict[str, Any],
) -> dict[str, Any]:
    """Validate a feature artifact dict (in-memory use).

    Calls ``validate_feature_artifact`` and returns the validated,
    normalised artifact.
    """
    return validate_feature_artifact(artifact)


def load_feature_artifact_from_json(path: str | Path) -> dict[str, Any]:
    """Read a JSON file and validate it as a feature artifact.

    For controlled dev/test use only.  Does not perform network calls
    or S3 staging.
    """
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict):
        raise FeatureArtifactValidationError(
            "JSON root must be a dict"
        )

    return validate_feature_artifact(data)
