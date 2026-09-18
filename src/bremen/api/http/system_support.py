"""Model and service metadata queries for the HTTP boundary."""
from __future__ import annotations
from pathlib import Path
from bremen.config import CloudConfig
from bremen.api.schemas import HealthResponse, ModelVersionResponse, build_health_response
from bremen.platform.models.state import ModelState

def handle_health(version: str | None = None) -> HealthResponse:
    """Return service health information.

    Parameters
    ----------
    version : Optional package version string.

    Returns
    -------
    A ``HealthResponse`` with current status.
    """
    resp = build_health_response(version=version)

    # Check registry first (catalog mode), fall back to ModelState (legacy)
    from bremen.platform.models.registry import get_registry  # noqa: PLC0415
    registry = get_registry()
    if registry.catalog_status != "not_configured":
        model_ready = registry.available_count > 0
    else:
        model_ready = ModelState.is_ready()

    return HealthResponse(
        status=resp.status,
        service=resp.service,
        version=resp.version,
        timestamp=resp.timestamp,
        model_ready=model_ready,
    )

def handle_model_version(
    explicit_path: str | Path | None = None,
    cloud: CloudConfig | None = None,
) -> ModelVersionResponse:
    """Return configured model package metadata.

    Resolution priority:

    1. Catalog mode (BREMEN_MODEL_CATALOG_URI):
       - Zero models: not_configured
       - One model: that model's metadata
       - Multiple models: selection_required with null singular fields
    2. Explicit local package path.
    3. Already-loaded ``ModelState`` ready metadata.
    4. Failed/attempted ``ModelState`` error metadata.
    5. Cloud metadata from ``read_cloud_config()`` / ``derive_model_source()``.
    6. ``not_configured``.

    Parameters
    ----------
    explicit_path : Optional explicit path to a local model package
        directory.
    cloud : Optional ``CloudConfig``.

    Returns
    -------
    A ``ModelVersionResponse``.

    Must not import ``joblib`` / ``pickle`` or deserialize artifacts.
    """
    # 0. Catalog mode — check registry first
    from bremen.platform.models.registry import get_registry  # noqa: PLC0415
    registry = get_registry()
    if registry.catalog_status != "not_configured":
        avail = registry.available_entries
        if len(avail) == 0:
            return ModelVersionResponse(
                model_configured=False,
                model_version=None,
                model_checksum=None,
                feature_schema_version=None,
                threshold_version=None,
                threshold_value=None,
                qc_criteria_version=None,
                model_status="not_configured",
                model_uri_configured=True,
                checksum_configured=False,
                error_category=None,
            )
        if len(avail) == 1:
            entry = avail[0]
            return ModelVersionResponse(
                model_configured=True,
                model_version=entry.model_version,
                model_checksum=None,  # checksum is private
                feature_schema_version=entry.feature_schema_version,
                threshold_version=None,
                threshold_value=None,
                qc_criteria_version=None,
                model_status="ready",
                model_uri_configured=True,
                checksum_configured=True,
                error_category=None,
            )
        # Multiple models
        return ModelVersionResponse(
            model_configured=True,
            model_version=None,
            model_checksum=None,
            feature_schema_version=None,
            threshold_version=None,
            threshold_value=None,
            qc_criteria_version=None,
            model_status="selection_required",
            model_uri_configured=True,
            checksum_configured=False,
            error_category=None,
        )

    # 1. Explicit local package path
    if explicit_path is not None:
        from bremen.model_package_source import resolve_model_package_source  # noqa: PLC0415

        source = resolve_model_package_source(explicit_path=explicit_path)
        return ModelVersionResponse(
            model_configured=source.model_configured,
            model_version=source.model_version,
            model_checksum=source.model_checksum,
            feature_schema_version=source.feature_schema_version,
            threshold_version=source.threshold_version,
            threshold_value=source.threshold_value,
            qc_criteria_version=source.qc_criteria_version,
            model_status=source.model_status,
            model_uri_configured=source.model_configured,
            checksum_configured=source.model_checksum is not None,
            error_category=source.error,
        )

    # 2. Already-loaded ModelState — model is loaded and ready
    model_pkg = ModelState.get_model()
    if model_pkg is not None:
        state = ModelState.get_instance()
        plr = model_pkg.get("portable_logreg", {})
        return ModelVersionResponse(
            model_configured=True,
            model_version=state._model_version or plr.get("model_version"),
            model_checksum=state._model_checksum,
            feature_schema_version=plr.get("feature_schema_version"),
            threshold_version=plr.get("threshold_version"),
            threshold_value=(
                float(plr["threshold"]) if plr.get("threshold") is not None
                else None
            ),
            qc_criteria_version=None,
            model_status="ready",
            model_uri_configured=True,
            checksum_configured=True,
            error_category=None,
        )

    # 3. Failed load attempt — model_status="error"
    if ModelState.was_load_attempted():
        state = ModelState.get_instance()
        load_error = ModelState.get_load_error()
        uri_configured = bool(state._model_version) or (
            state._load_error not in (None, "model_uri_not_set")
        )
        checksum_configured = bool(state._model_checksum)
        return ModelVersionResponse(
            model_configured=True,
            model_version=state._model_version,
            model_checksum=state._model_checksum,
            feature_schema_version=None,
            threshold_version=None,
            threshold_value=None,
            qc_criteria_version=None,
            model_status="error",
            model_uri_configured=uri_configured,
            checksum_configured=checksum_configured,
            error_category=load_error,
        )

    # 4. Cloud metadata / not_configured via derive_model_source
    from bremen.api.model_source import derive_model_source  # noqa: PLC0415

    src = derive_model_source(cloud=cloud)
    is_configured = src["model_configured"]
    return ModelVersionResponse(
        **src,
        model_uri_configured=is_configured,
        checksum_configured=bool(src.get("model_checksum")),
        error_category=None,
    )
