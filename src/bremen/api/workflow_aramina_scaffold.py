"""Aramina workflow provider scaffold.

Separate first-class provider.  No cross-imports from Bremen.
Implementation depends on authoritative Aramina artifacts.

PR0075 — multi-workflow runtime foundation.
"""

from __future__ import annotations

from dataclasses import dataclass
from logging import getLogger as _getLogger
from typing import Any

from .workflow_provider import (
    WorkflowProvider,
    WorkflowFeatureVector,
    WorkflowResult,
    WorkflowReadiness,
    CompatibilityResult,
)

_log = _getLogger(__name__)


class AraminaWorkflowError(Exception):
    """Base exception for Aramina workflow errors."""


class WorkflowUnavailableError(AraminaWorkflowError):
    """Aramina workflow is not available (missing artifacts or runtime)."""


# ---------------------------------------------------------------------------
# Provider scaffold
# ---------------------------------------------------------------------------


class AraminaProvider(WorkflowProvider):
    """Aramina workflow provider.

    Currently scaffolded — returns ``workflow_unavailable`` until
    authoritative Aramina artifacts (model, config, runtime) are
    provided.  Does NOT reverse-engineer Aramina features or
    inference.

    Integration mode: to be determined (Option A: in-process,
    Option B: subprocess, Option C: service client).
    """

    workflow_id: str = "aramina"

    def __init__(self) -> None:
        self._enabled = False

    def readiness(self) -> WorkflowReadiness:
        return WorkflowReadiness(
            workflow_id=self.workflow_id,
            configured=True,
            model_ready=False,
            scientifically_certified=False,
        )

    def validate_compatibility(self, canonical: Any) -> CompatibilityResult:
        return CompatibilityResult(
            compatible=True,
            reason="aramina_not_active",
        )

    def build_features(self, canonical: Any) -> WorkflowFeatureVector:
        raise WorkflowUnavailableError(
            "Aramina workflow is not available"
        )

    def run_inference(self, features: WorkflowFeatureVector) -> WorkflowResult:
        return WorkflowResult(
            workflow_id=self.workflow_id,
            status="failed",
            error="Aramina workflow unavailable — missing authoritative artifacts",
        )

    def execute(self, canonical: Any) -> WorkflowResult:
        return self.run_inference(
            WorkflowFeatureVector(
                workflow_id=self.workflow_id,
                feature_names=(),
                feature_values=(),
            )
        )
