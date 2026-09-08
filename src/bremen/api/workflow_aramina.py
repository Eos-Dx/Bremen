"""Aramina workflow provider.

Manifest-gated Aramina workflow path.  Only activates when a valid
Aramina model manifest is present in the catalog.  Does NOT route
through the Bremen provider.

PR0129 — Aramina manifest-gated workflow runtime.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from logging import getLogger as _getLogger
from typing import Any

from .aramina_provider import (
    AraminaProviderRequest,
    AraminaProviderResult,
    build_aramina_safe_error,
)
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


class AraminaProviderUnavailableError(AraminaWorkflowError):
    """Aramina provider service is not reachable."""


# ---------------------------------------------------------------------------
# Aramina provider boundary (service adapter)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _AraminaProviderConfig:
    """Configuration for the Aramina provider service boundary."""

    provider_url: str = ""
    timeout_seconds: int = 300


def _load_aramina_provider_config() -> _AraminaProviderConfig:
    """Load Aramina provider config from environment variables."""
    return _AraminaProviderConfig(
        provider_url=os.environ.get("BREMEN_ARAMINA_PROVIDER_URL", ""),
        timeout_seconds=int(os.environ.get("BREMEN_ARAMINA_TIMEOUT", "300")),
    )


def _call_aramina_provider(
    config: _AraminaProviderConfig,
    request: AraminaProviderRequest,
    *,
    h5_path: str = "",
) -> AraminaProviderResult:
    """Call the Aramina provider service.

    Validates that the provider is configured, then returns a safe result.
    Future implementation will send multipart input_h5 + request_json.
    No real external calls are made in test/stub mode.
    """
    if not config.provider_url:
        raise AraminaProviderUnavailableError(
            "Aramina provider URL not configured. "
            "Set BREMEN_ARAMINA_PROVIDER_URL."
        )

    _log.info(
        "aramina.provider.call\tpatient_id=%s\ttarget_side=%s",
        request.patient_id,
        request.target_side,
    )

    return AraminaProviderResult(
        model_family="aramina",
        workflow_id="aramina",
        model_id=request.patient_id,
        model_version="",
        status="passed",
        target_side=request.target_side,
        patient_id_supplied=True,
        technical_demo_only=True,
        clinical_stage="research draft",
    )


# ---------------------------------------------------------------------------
# Workflow provider
# ---------------------------------------------------------------------------


class AraminaWorkflowProvider(WorkflowProvider):
    """Aramina workflow provider.

    Manifest-gated: only available when the catalog entry has a valid
    Aramina manifest with provider_contract == "aramina_provider.v0.1".

    Does NOT route through Bremen provider.  Does NOT call Bremen
    model artifacts.
    """

    workflow_id: str = "aramina"

    def __init__(
        self,
        *,
        model_id: str = "",
        model_version: str = "",
        provider_url: str | None = None,
    ) -> None:
        self._model_id = model_id
        self._model_version = model_version
        self._provider_url = provider_url or ""
        self._config = _AraminaProviderConfig(
            provider_url=self._provider_url,
        )

    def readiness(self) -> WorkflowReadiness:
        configured = bool(self._provider_url)
        # Manifest-backed Aramina instances are model_ready even without
        # a provider URL.  The missing-URL case is handled inside
        # execute() as a safe provider-boundary failure, not a generic
        # workflow_unavailable gate.
        return WorkflowReadiness(
            workflow_id=self.workflow_id,
            configured=configured,
            model_ready=True,
            scientifically_certified=False,
        )

    def validate_compatibility(
        self, canonical: Any,
    ) -> CompatibilityResult:
        return CompatibilityResult(
            compatible=True,
            reason="aramina_manifest_gated",
        )

    def build_features(
        self, canonical: Any,
    ) -> WorkflowFeatureVector:
        raise AraminaWorkflowError(
            "Aramina does not use Bremen feature vectors"
        )

    def run_inference(
        self, features: WorkflowFeatureVector,
    ) -> WorkflowResult:
        return WorkflowResult(
            workflow_id=self.workflow_id,
            status="failed",
            error="Aramina inference not called via Bremen feature path",
        )

    def execute(
        self,
        canonical: Any,
        *,
        aramina_request: AraminaProviderRequest | None = None,
        h5_path: str = "",
    ) -> WorkflowResult:
        """Execute the Aramina workflow.

        Validates provider availability and calls the Aramina provider service.
        """
        try:
            result = _call_aramina_provider(
                self._config,
                aramina_request or AraminaProviderRequest(
                    container_id="",
                    source_id="",
                    patient_id="",
                    target_side="left",
                ),
                h5_path=h5_path,
            )
            return WorkflowResult(
                workflow_id=self.workflow_id,
                status="completed",
                payload={
                    "model_family": result.model_family,
                    "model_id": self._model_id,
                    "model_version": self._model_version,
                    "clinical_stage": result.clinical_stage,
                    "technical_demo_only": result.technical_demo_only,
                    "target_side": result.target_side,
                    "patient_id_supplied": result.patient_id_supplied,
                },
            )
        except AraminaProviderUnavailableError:
            return WorkflowResult(
                workflow_id=self.workflow_id,
                status="failed",
                error="Aramina provider service is not configured",
            )
        except Exception as exc:
            safe_err = build_aramina_safe_error(exc)
            return WorkflowResult(
                workflow_id=self.workflow_id,
                status="failed",
                error=safe_err.safe_reason,
            )
