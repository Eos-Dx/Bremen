"""Aramis workflow provider scaffold.

Separate first-class provider.  No cross-imports from Bremen.
Implementation depends on authoritative Aramis artifacts.

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


class AramisWorkflowError(Exception):
    """Base exception for Aramis workflow errors."""


class WorkflowUnavailableError(AramisWorkflowError):
    """Aramis workflow is not available (missing artifacts or runtime)."""


# ---------------------------------------------------------------------------
# Provider scaffold
# ---------------------------------------------------------------------------


class AramisProvider(WorkflowProvider):
    """Aramis workflow provider.

    Currently scaffolded — returns ``workflow_unavailable`` until
    authoritative Aramis artifacts (model, config, runtime) are
    provided.  Does NOT reverse-engineer Aramis features or
    inference.

    Integration mode: to be determined (Option A: in-process,
    Option B: subprocess, Option C: service client).
    """

    workflow_id: str = "aramis"

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
            reason="aramis_not_active",
        )

    def build_features(self, canonical: Any) -> WorkflowFeatureVector:
        raise WorkflowUnavailableError(
            "Aramis workflow is not available"
        )

    def run_inference(self, features: WorkflowFeatureVector) -> WorkflowResult:
        return WorkflowResult(
            workflow_id=self.workflow_id,
            status="failed",
            error="Aramis workflow unavailable — missing authoritative artifacts",
        )

    def execute(self, canonical: Any) -> WorkflowResult:
        return self.run_inference(
            WorkflowFeatureVector(
                workflow_id=self.workflow_id,
                feature_names=(),
                feature_values=(),
            )
        )
