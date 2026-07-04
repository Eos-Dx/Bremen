"""Metadata-only model package source descriptor.

Safe to import at any point — no model loading, no network calls,
no H5 reads, no ``joblib`` / ``pickle``.
"""

from __future__ import annotations

from ..config import CloudConfig, read_cloud_config


def derive_model_source(
    cloud: CloudConfig | None = None,
) -> dict:
    """Derive safe model package source metadata from cloud config.

    Parameters
    ----------
    cloud : A ``CloudConfig`` instance.  If ``None``, reads from
        environment variables via ``read_cloud_config()``.

    Returns
    -------
    A dict with keys matching ``ModelVersionResponse`` fields:
    ``model_configured``, ``model_version``, ``model_checksum``,
    ``feature_schema_version``, ``threshold_version``,
    ``threshold_value``, ``qc_criteria_version``, ``model_status``.

    No S3 reads, no model file reads, no manifest fetching, no
    validation.
    """
    if cloud is None:
        cloud = read_cloud_config()

    if not cloud.configured:
        return {
            "model_configured": False,
            "model_version": None,
            "model_checksum": None,
            "feature_schema_version": None,
            "threshold_version": None,
            "threshold_value": None,
            "qc_criteria_version": None,
            "model_status": "not_configured",
        }

    return {
        "model_configured": True,
        "model_version": cloud.model_version or None,
        "model_checksum": None,  # unknown until package is fetched
        "feature_schema_version": None,  # unknown until manifest is read
        "threshold_version": None,  # unknown until manifest is read
        "threshold_value": None,  # unknown until manifest is read
        "qc_criteria_version": None,  # unknown until manifest is read
        "model_status": "configured",
    }
