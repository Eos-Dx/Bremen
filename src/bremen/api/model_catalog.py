"""Bremen model catalog — server-owned catalog of configured models.

Reads from the immutable process-local ModelRegistry. Supports zero,
one, or multiple real configured Bremen models.

PR0082a — Control Room Data and Selection Foundation.
PR0085 — Startup S3 Model Discovery and Per-Job Model Selection.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .model_registry import get_registry, RegistryModelEntry

# Re-export for backward compatibility
ModelEntry = RegistryModelEntry


# ---------------------------------------------------------------------------
# Build the model catalog from the current registry
# ---------------------------------------------------------------------------


def build_model_catalog() -> dict[str, Any]:
    """Build the model catalog from the current ModelRegistry.

    Returns a dict suitable for the GET /demo/api/models response
    with ``schema_version``, ``catalog_timestamp``, ``models`` list,
    ``default_model_id``, and ``status``.
    """
    registry = get_registry()
    now = datetime.now(timezone.utc)
    catalog_timestamp = now.isoformat()

    models = [e.to_safe_dict() for e in registry.entries]
    # Sort by model_id for deterministic ordering
    models.sort(key=lambda m: m["model_id"])
    default_model_id = registry.default_model_id

    # Determine status
    if registry.catalog_status == "discovery_failed":
        status = "discovery_failed"
    elif registry.available_count > 0:
        status = "available"
    elif registry.candidate_count > 0 and registry.available_count == 0:
        status = "no_valid_models"
    else:
        status = "not_configured"

    result: dict[str, Any] = {
        "schema_version": "v1",
        "catalog_timestamp": catalog_timestamp,
        "models": models,
        "default_model_id": default_model_id,
        "status": status,
    }

    # Add safe aggregate counts in catalog mode
    if registry.catalog_status != "not_configured":
        result["candidate_count"] = registry.candidate_count
        result["available_count"] = registry.available_count
        result["rejected_count"] = registry.rejected_count

    return result


# ---------------------------------------------------------------------------
# Resolve and validate a model_id against the registry
# ---------------------------------------------------------------------------


class ModelCatalogError(Exception):
    """Base error for model catalog operations."""


class ModelNotFoundError(ModelCatalogError):
    """Requested model_id does not exist in the catalog."""


class ModelUnavailableError(ModelCatalogError):
    """Requested model exists but is not available."""


class ModelIncompatibleError(ModelCatalogError):
    """Requested model is incompatible (wrong workflow or feature schema)."""


class AmbiguousModelSelectionError(ModelCatalogError):
    """No model_id specified and catalog has zero or multiple available models."""


def resolve_model(
    model_id: str | None,
    *,
    workflow_id: str = "bremen",
    require_availability: bool = True,
) -> str:
    """Resolve and validate a model_id against the current registry.

    Parameters
    ----------
    model_id : The model_id to resolve, or ``None`` for default resolution.
    workflow_id : The target workflow that the model must be compatible with.
    require_availability : If ``True``, only available models are accepted.

    Returns
    -------
    The resolved model_id (canonical string).

    Raises
    ------
    ModelNotFoundError
        If model_id does not exist in the catalog.
    ModelUnavailableError
        If the model exists but is not available.
    ModelIncompatibleError
        If the model's workflow_id does not match.
    AmbiguousModelSelectionError
        If model_id is ``None`` and the catalog does not have exactly
        one available model.
    """
    registry = get_registry()
    entries = registry.entries

    if model_id is None:
        # Default resolution
        if not entries:
            raise AmbiguousModelSelectionError(
                "No model configured. "
                "Configure BREMEN_MODEL_URI or BREMEN_MODEL_CATALOG_URI "
                "to enable analysis."
            )
        available_entries = registry.available_entries
        if len(available_entries) == 0:
            raise AmbiguousModelSelectionError(
                "No model is currently available. "
                "Model may be loading or not configured."
            )
        if len(available_entries) > 1:
            raise AmbiguousModelSelectionError(
                "Multiple available models — model_id is required."
            )
        resolved = available_entries[0]
    else:
        # Explicit model_id
        resolved = registry.get_entry(model_id)
        if resolved is None:
            raise ModelNotFoundError(
                f"Model '{model_id}' not found in catalog."
            )

    # Availability check
    if require_availability and resolved.availability != "available":
        raise ModelUnavailableError(
            f"Model '{resolved.model_id}' is not available. "
            f"Status: {resolved.availability}."
        )

    # Workflow compatibility
    if resolved.workflow_id != workflow_id:
        raise ModelIncompatibleError(
            f"Model '{resolved.model_id}' targets workflow "
            f"'{resolved.workflow_id}', not '{workflow_id}'."
        )

    return str(resolved.model_id)
