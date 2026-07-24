"""Immutable process-local model registry for multi-model support.

Created exactly once during startup bootstrap. After initialization,
the registry and its entries are immutable. Request handlers receive
read-only access. No request performs S3 listing, manifest download,
artifact staging, checksum verification, or deserialization.

PR0085 — Startup S3 Model Discovery and Per-Job Model Selection.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

import bremen


# ---------------------------------------------------------------------------
# Registry entry — one loaded model package
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegistryModelEntry:
    """A single model entry in the immutable registry.

    All fields are frozen after creation. Private fields (package,
    checksum, version) are never exposed in public API responses.
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
    _package: dict[str, Any] = field(repr=False, compare=False)
    _checksum: str = field(repr=False, compare=False, default="")
    scientifically_certified: bool = False
    technical_demo_only: bool = True
    availability: str = "available"

    def to_safe_dict(self) -> dict[str, Any]:
        """Return safe public fields only. No private package data."""
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

    def to_dict(self) -> dict[str, Any]:
        """Alias for to_safe_dict for backward compatibility."""
        return self.to_safe_dict()


# ---------------------------------------------------------------------------
# ModelRegistry — immutable snapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelRegistry:
    """Immutable snapshot of all discovered and validated models.

    Created once at startup. After creation, no entries can be added,
    removed, or modified.
    """

    entries: tuple[RegistryModelEntry, ...] = field(default_factory=tuple)
    catalog_status: str = "not_configured"  # "available" | "not_configured" | "discovery_failed"
    candidate_count: int = 0
    available_count: int = 0
    rejected_count: int = 0

    @property
    def available_entries(self) -> tuple[RegistryModelEntry, ...]:
        return tuple(e for e in self.entries if e.availability == "available")

    @property
    def default_model_id(self) -> str | None:
        avail = self.available_entries
        if len(avail) == 1:
            return avail[0].model_id
        return None

    def get_entry(self, model_id: str) -> RegistryModelEntry | None:
        for e in self.entries:
            if e.model_id == model_id:
                return e
        return None

    def get_package(self, model_id: str) -> dict[str, Any] | None:
        entry = self.get_entry(model_id)
        if entry is None:
            return None
        return entry._package

    def get_checksum(self, model_id: str) -> str | None:
        entry = self.get_entry(model_id)
        if entry is None:
            return None
        return entry._checksum


# ---------------------------------------------------------------------------
# Registry singleton — stored on bremen package for reload safety
# ---------------------------------------------------------------------------

_REGISTRY_KEY = "_bremen_model_registry"
_REGISTRY_LOCK_KEY = "_bremen_model_registry_lock"


def _get_registry_lock() -> threading.Lock:
    lock = getattr(bremen, _REGISTRY_LOCK_KEY, None)
    if lock is None:
        lock = threading.Lock()
        setattr(bremen, _REGISTRY_LOCK_KEY, lock)
    return lock


def initialize_registry(registry: ModelRegistry) -> None:
    """Set the process-local registry. Thread-safe, single-write.

    Must be called exactly once during startup bootstrap before any
    request handlers run. After this call, the registry is immutable.
    """
    lock = _get_registry_lock()
    with lock:
        setattr(bremen, _REGISTRY_KEY, registry)


def get_registry() -> ModelRegistry:
    """Return the current registry, or an empty not_configured registry."""
    registry = getattr(bremen, _REGISTRY_KEY, None)
    if registry is not None:
        return registry
    return ModelRegistry()


def get_model_entry(model_id: str) -> RegistryModelEntry | None:
    """Get a specific entry from the registry."""
    return get_registry().get_entry(model_id)


def get_model_package(model_id: str) -> dict[str, Any] | None:
    """Get the private package for a specific model_id."""
    return get_registry().get_package(model_id)


def get_model_checksum(model_id: str) -> str | None:
    """Get the checksum for a specific model_id."""
    return get_registry().get_checksum(model_id)


def reset_for_tests() -> None:
    """Clear the registry (test-only)."""
    lock = _get_registry_lock()
    with lock:
        if hasattr(bremen, _REGISTRY_KEY):
            delattr(bremen, _REGISTRY_KEY)


def build_legacy_registry() -> ModelRegistry:
    """Build a single-entry registry from the legacy ModelState singleton.

    Used when BREMEN_MODEL_CATALOG_URI is not configured.
    """
    from .model_state import ModelState  # noqa: PLC0415
    from .decision_contract import (  # noqa: PLC0415
        DECISION_POLICY_ID,
        DECISION_POLICY_VERSION,
    )

    model_pkg = ModelState.get_model()
    if model_pkg is None:
        return ModelRegistry()

    state = ModelState.get_instance()
    model_ready = ModelState.is_ready()
    model_version = getattr(state, "_model_version", "unknown") or "unknown"
    model_checksum = getattr(state, "_model_checksum", "") or ""

    plr = model_pkg.get("portable_logreg", {})
    feature_schema_version = str(
        plr.get("feature_schema_version", plr.get("feature_schema", "v0.1"))
    )

    entry = RegistryModelEntry(
        model_id="bremen-current",
        display_name="Bremen Current",
        workflow_id="bremen",
        model_version=model_version,
        artifact_type="portable_logreg",
        feature_schema_version=feature_schema_version,
        decision_policy_id=DECISION_POLICY_ID,
        decision_policy_version=DECISION_POLICY_VERSION,
        technical_ready=model_ready,
        scientifically_certified=False,
        technical_demo_only=True,
        availability="available" if model_ready else "unavailable",
        _package=model_pkg,
        _checksum=model_checksum,
    )

    return ModelRegistry(
        entries=(entry,),
        catalog_status="available" if model_ready else "not_configured",
        candidate_count=1,
        available_count=1 if model_ready else 0,
        rejected_count=0,
    )
