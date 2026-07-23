"""Bremen model catalog — server-owned catalog of configured models.

Supports zero, one, or multiple real configured Bremen models.
Each entry has a stable ``model_id``.  The catalog is rebuilt on
every call to reflect current ``ModelState`` without requiring server
restart.

Privacy:  No artifact URIs, S3 model keys, local paths, checksums,
coefficients, weights, intercepts, scaler values, imputer values, or
reference distributions are exposed.

PR0082a — Control Room Data and Selection Foundation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .decision_contract import (
    DECISION_POLICY_ID,
    DECISION_POLICY_VERSION,
)


# ---------------------------------------------------------------------------
# ModelEntry — single catalog entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelEntry:
    """Single entry in the Bremen model catalog.

    All fields are safe for public API exposure.  No artifact URIs,
    checksums, or internal paths are included.
    """

    model_id: str
    display_name: str
    workflow_id: str
    model_version: str
    artifact_type: str
    feature_schema_version: str
    decision_policy_id: str
    decision_policy_version: str
    technical_ready: bool
    scientifically_certified: bool
    technical_demo_only: bool
    availability: str  # "available" | "unavailable" | "not_configured"

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "workflow_id": self.workflow_id,
            "model_version": self.model_version,
            "artifact_type": self.artifact_type,
            "feature_schema_version": self.feature_schema_version,
            "decision_policy_id": self.decision_policy_id,
            "decision_policy_version": self.decision_policy_version,
            "technical_ready": self.technical_ready,
            "scientifically_certified": self.scientifically_certified,
            "technical_demo_only": self.technical_demo_only,
            "availability": self.availability,
        }


# ---------------------------------------------------------------------------
# Build the model catalog from the current ModelState
# ---------------------------------------------------------------------------


def build_model_catalog() -> dict[str, Any]:
    """Build the model catalog from current ModelState.

    Returns a dict suitable for the GET /demo/api/models response
    with ``schema_version``, ``catalog_timestamp``, ``models`` list,
    ``default_model_id``, and ``status``.

    With the existing single-model configuration (BREMEN_MODEL_URI),
    returns one entry with ``model_id = "bremen-current"``.
    When no model is configured, returns an empty models list.
    """
    from .model_state import ModelState  # noqa: PLC0415

    now = datetime.now(timezone.utc)
    catalog_timestamp = now.isoformat()
    model_pkg = ModelState.get_model()
    state = ModelState.get_instance()

    models: list[ModelEntry] = []
    default_model_id: str | None = None

    if model_pkg is not None:
        # Model is configured — build a catalog entry from ModelState
        model_ready = ModelState.is_ready()
        model_version = state._model_version or "unknown"

        # Derive feature_schema_version from model package
        plr = model_pkg.get("portable_logreg", {})
        feature_schema_version = plr.get(
            "feature_schema_version",
            plr.get("feature_schema", "v0.1"),
        )

        entry = ModelEntry(
            model_id="bremen-current",
            display_name="Bremen Current",
            workflow_id="bremen",
            model_version=model_version,
            artifact_type="portable_logreg",
            feature_schema_version=str(feature_schema_version),
            decision_policy_id=DECISION_POLICY_ID,
            decision_policy_version=DECISION_POLICY_VERSION,
            technical_ready=model_ready,
            scientifically_certified=False,
            technical_demo_only=True,
            availability="available" if model_ready else "unavailable",
        )
        models.append(entry)
        if entry.availability == "available":
            default_model_id = entry.model_id
    else:
        # No model configured
        pass

    status: str = "available" if models else "not_configured"

    return {
        "schema_version": "v1",
        "catalog_timestamp": catalog_timestamp,
        "models": [m.to_dict() for m in models],
        "default_model_id": default_model_id,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Resolve and validate a model_id against the catalog
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
    """Resolve and validate a model_id against the current catalog.

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
    catalog = build_model_catalog()
    entries = catalog["models"]
    default_id = catalog["default_model_id"]

    if model_id is None:
        # Default resolution
        if not entries:
            raise AmbiguousModelSelectionError(
                "No model configured. "
                "Configure BREMEN_MODEL_URI to enable analysis."
            )
        available_entries = [m for m in entries if m["availability"] == "available"]
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
        matching = [m for m in entries if m["model_id"] == model_id]
        if not matching:
            raise ModelNotFoundError(
                f"Model '{model_id}' not found in catalog."
            )
        resolved = matching[0]

    # Availability check
    if require_availability and resolved["availability"] != "available":
        raise ModelUnavailableError(
            f"Model '{resolved['model_id']}' is not available. "
            f"Status: {resolved['availability']}."
        )

    # Workflow compatibility
    if resolved["workflow_id"] != workflow_id:
        raise ModelIncompatibleError(
            f"Model '{resolved['model_id']}' targets workflow "
            f"'{resolved['workflow_id']}', not '{workflow_id}'."
        )

    return str(resolved["model_id"])
