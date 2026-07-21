"""Workflow provider contract and result types.

Defines the abstract provider interface for independent scientific
workflows (Bremen, Aramis, ...).  Providers share canonical XRD inputs
but own their feature schemas, model artifacts, thresholds, and
decision contracts.

PR0075 — multi-workflow runtime foundation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Workflow-specific types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkflowFeatureVector:
    """Feature vector produced by a workflow provider."""

    workflow_id: str
    feature_names: tuple[str, ...]
    feature_values: tuple[float, ...]


@dataclass(frozen=True)
class WorkflowResult:
    """Result of a single workflow execution."""

    workflow_id: str
    status: str  # "completed" | "failed" | "skipped"
    payload: dict[str, Any] | None = None
    error: str | None = None


@dataclass(frozen=True)
class WorkflowReadiness:
    """Independent readiness state for one workflow."""

    workflow_id: str
    configured: bool
    model_ready: bool
    scientifically_certified: bool

    @property
    def ready(self) -> bool:
        return self.configured and self.model_ready and self.scientifically_certified


@dataclass(frozen=True)
class PlatformReadiness:
    """Aggregated platform readiness."""

    alive: bool
    normalization_ready: bool
    workflows: dict[str, WorkflowReadiness]


@dataclass(frozen=True)
class CompatibilityResult:
    """Result of a workflow compatibility check against a canonical case."""

    compatible: bool
    reason: str | None = None


# ---------------------------------------------------------------------------
# Multi-workflow result envelope
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MultiWorkflowResult:
    """Result of a multi-workflow execution.

    One normalization produces one canonical case.  Each requested
    workflow runs independently against it.  Partial success is
    explicit: a working Bremen + failed Aramis produces
    ``overall_status = "partial_success"``.
    """

    request_id: str
    job_id: str
    normalization_status: str  # "completed" | "failed"
    source_checksum: str
    requested_workflows: tuple[str, ...]
    workflows: dict[str, WorkflowResult]
    overall_status: str  # "completed" | "partial_success" | "failed" | "normalization_failed"
    technical_demo_only: bool = True


# ---------------------------------------------------------------------------
# Abstract provider
# ---------------------------------------------------------------------------


class WorkflowProvider(ABC):
    """Abstract workflow provider.

    Each provider owns its scientific identity independently.
    """

    workflow_id: str = ""

    @abstractmethod
    def readiness(self) -> WorkflowReadiness:
        """Return the current readiness state of this workflow."""

    @abstractmethod
    def validate_compatibility(
        self, canonical: Any,
    ) -> CompatibilityResult:
        """Check whether a canonical XRD case is compatible with this workflow."""

    @abstractmethod
    def build_features(
        self, canonical: Any,
    ) -> WorkflowFeatureVector:
        """Build per-workflow features from a canonical XRD case."""

    @abstractmethod
    def run_inference(
        self, features: WorkflowFeatureVector,
    ) -> WorkflowResult:
        """Run inference and produce a workflow-specific result."""

    @abstractmethod
    def execute(
        self, canonical: Any,
    ) -> WorkflowResult:
        """Full execution: compatibility → features → inference."""
