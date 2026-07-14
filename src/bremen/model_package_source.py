"""Model package source resolution for the Bremen API.

Resolves the active model package source with deterministic precedence:

1. Explicit local package directory path argument.
2. ``BREMEN_MODEL_PACKAGE_DIR`` environment variable (local directory).
3. Cloud metadata from ``read_cloud_config()`` — metadata-only, no S3 reads.
4. ``not_configured`` — no model package source configured.

Safety
------
- No ``joblib`` / ``pickle`` imports.
- No model loading or deserialization.
- No H5/HDF5 reads.
- No AWS/S3/network calls.
- Local validation reads ``manifest.json`` only; the model artifact binary
  is read only for SHA-256 checksum computation (no deserialization).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from bremen.config import CloudConfig, read_cloud_config
from bremen.model_package import (
    ModelPackageError,
    summarize_model_package,
    validate_model_package,
)

_DEV_MODEL_PACKAGE_DIR_ENV_VAR = "BREMEN_MODEL_PACKAGE_DIR"


class ModelPackageSourceError(Exception):
    """Base exception for model package source resolution errors."""


@dataclass(frozen=True)
class ModelPackageSource:
    """Represents a resolved model package source (not loaded).

    Attributes
    ----------
    source_type : ``\"not_configured\"`` | ``\"local\"`` | ``\"cloud\"``
    model_configured : Whether a model package source is configured.
    model_version : Model version string (from manifest for local, or
        env var for cloud).
    model_checksum : SHA-256 checksum string (from manifest for local;
        ``None`` for cloud).
    feature_schema_version : Feature schema version string (from
        manifest for local; ``None`` for cloud).
    threshold_version : Threshold version string (from manifest for
        local; ``None`` for cloud).
    threshold_value : Threshold value float (from manifest for local;
        ``None`` for cloud).
    qc_criteria_version : QC criteria version string (from manifest
        for local; ``None`` for cloud).
    model_status : ``\"not_configured\"`` | ``\"configured\"`` | ``\"invalid\"``
    error : Validation error message string, or ``None``.
    """

    source_type: str
    model_configured: bool
    model_version: str | None
    model_checksum: str | None
    feature_schema_version: str | None
    threshold_version: str | None
    threshold_value: float | None
    qc_criteria_version: str | None
    model_status: str
    error: str | None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_model_package_source(
    explicit_path: str | Path | None = None,
) -> ModelPackageSource:
    """Resolve the active model package source with deterministic precedence.

    Precedence order:
    1. *explicit_path* argument (local package directory).
    2. ``BREMEN_MODEL_PACKAGE_DIR`` environment variable (local directory).
    3. Cloud metadata from ``read_cloud_config()`` — no S3 reads.
    4. ``not_configured`` — no model package source configured.

    Parameters
    ----------
    explicit_path : Optional explicit path to a local model package
        directory.  Takes precedence over all env vars.

    Returns
    -------
    A ``ModelPackageSource`` with source metadata.
    """
    # 1. Explicit path argument
    if explicit_path is not None:
        return _resolve_local(Path(explicit_path))

    # 2. BREMEN_MODEL_PACKAGE_DIR env var
    env_dir = _get_model_package_dir_env()
    if env_dir is not None:
        return _resolve_local(env_dir)

    # 3. Cloud metadata
    cloud = read_cloud_config()
    if cloud.configured:
        return _resolve_cloud(cloud)

    # 4. not_configured
    return _not_configured()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_model_package_dir_env() -> Path | None:
    """Read and validate ``BREMEN_MODEL_PACKAGE_DIR`` env var.

    Returns ``None`` if the env var is unset, empty, or whitespace-only.
    Returns the ``Path`` if set.
    """
    raw = os.environ.get(_DEV_MODEL_PACKAGE_DIR_ENV_VAR, "").strip()
    if not raw:
        return None
    return Path(raw)


def _resolve_local(package_dir: Path) -> ModelPackageSource:
    """Resolve a local package directory and return validated source metadata.

    Validates the package using the existing ``validate_model_package()``
    and ``summarize_model_package()`` helpers.

    Parameters
    ----------
    package_dir : Path to the local model package directory.

    Returns
    -------
    A ``ModelPackageSource`` with ``source_type=\"local\"``.
    If validation fails, ``model_configured=False``,
    ``model_status=\"invalid\"``, and ``error`` describes the failure.
    """
    # Validate directory exists before calling summarize_model_package
    if not package_dir.exists():
        return ModelPackageSource(
            source_type="local",
            model_configured=False,
            model_version=None,
            model_checksum=None,
            feature_schema_version=None,
            threshold_version=None,
            threshold_value=None,
            qc_criteria_version=None,
            model_status="invalid",
            error=f"Package directory not found: {package_dir}",
        )

    if not package_dir.is_dir():
        return ModelPackageSource(
            source_type="local",
            model_configured=False,
            model_version=None,
            model_checksum=None,
            feature_schema_version=None,
            threshold_version=None,
            threshold_value=None,
            qc_criteria_version=None,
            model_status="invalid",
            error=f"Package path is not a directory: {package_dir}",
        )

    try:
        summary = summarize_model_package(package_dir)
    except ModelPackageError as exc:
        return ModelPackageSource(
            source_type="local",
            model_configured=False,
            model_version=None,
            model_checksum=None,
            feature_schema_version=None,
            threshold_version=None,
            threshold_value=None,
            qc_criteria_version=None,
            model_status="invalid",
            error=str(exc),
        )

    return ModelPackageSource(
        source_type="local",
        model_configured=True,
        model_version=summary.model_version,
        model_checksum=summary.model_checksum,
        feature_schema_version=summary.feature_schema_version,
        threshold_version=summary.threshold_version,
        threshold_value=summary.threshold_value,
        qc_criteria_version=summary.qc_criteria_version,
        model_status="configured",
        error=None,
    )


def _resolve_cloud(cloud: CloudConfig) -> ModelPackageSource:
    """Resolve a cloud metadata source (no S3 reads).

    Parameters
    ----------
    cloud : A ``CloudConfig`` instance with ``configured=True``.

    Returns
    -------
    A ``ModelPackageSource`` with ``source_type=\"cloud\"``.
    All content fields are ``None`` because the model package has not
    been fetched or validated.
    """
    return ModelPackageSource(
        source_type="cloud",
        model_configured=True,
        model_version=cloud.model_version,
        model_checksum=None,  # unknown until package is fetched
        feature_schema_version=None,  # unknown until manifest is read
        threshold_version=None,  # unknown until manifest is read
        threshold_value=None,  # unknown until manifest is read
        qc_criteria_version=None,  # unknown until manifest is read
        model_status="configured",
        error=None,
    )


def _not_configured() -> ModelPackageSource:
    """Return a ``not_configured`` source — nothing is configured."""
    return ModelPackageSource(
        source_type="not_configured",
        model_configured=False,
        model_version=None,
        model_checksum=None,
        feature_schema_version=None,
        threshold_version=None,
        threshold_value=None,
        qc_criteria_version=None,
        model_status="not_configured",
        error=None,
    )
