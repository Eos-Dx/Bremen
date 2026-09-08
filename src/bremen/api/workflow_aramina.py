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
from typing import Any, Mapping

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
# Official Aramina /predict contract
# ---------------------------------------------------------------------------

# The official Aramina /predict request_json may contain ONLY these fields.
_ARAMINA_OFFICIAL_REQUEST_FIELDS = frozenset({
    "analysis_author",
    "prediction_comment",
    "patient_id",
    "target_side",
})

_ARAMINA_DEFAULT_ANALYSIS_AUTHOR = "Bremen Platform"
_ARAMINA_ALLOWED_TARGET_SIDES = frozenset({"left", "right"})

# Keys that must never appear in a public report payload.
_ARAMINA_SENSITIVE_REPORT_KEYS = frozenset({
    "artifact_sha256",
    "model_checksum",
    "checksum",
    "path",
    "s3",
    "s3_key",
    "bucket",
    "token",
    "ticket",
    "traceback",
    "password",
    "secret",
    "credential",
})


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


def _safe_model_id_env_key(model_id: str) -> str:
    """Convert a model_id to a safe env-var suffix.

    Uppercases the model_id and converts every non-alphanumeric character
    to an underscore (e.g. ``model-a`` -> ``MODEL_A``).
    """
    return "".join(ch.upper() if ch.isalnum() else "_" for ch in model_id)


def _resolve_aramina_provider_url(model_id: str = "") -> str:
    """Resolve the Aramina provider URL for a model.

    Prefers the per-model env var ``BREMEN_ARAMINA_PROVIDER_URL__<SAFE_MODEL_ID>``
    when present; otherwise falls back to ``BREMEN_ARAMINA_PROVIDER_URL``.
    """
    if model_id:
        per_model = os.environ.get(
            f"BREMEN_ARAMINA_PROVIDER_URL__{_safe_model_id_env_key(model_id)}",
            "",
        )
        if per_model:
            return per_model
    return os.environ.get("BREMEN_ARAMINA_PROVIDER_URL", "")


def _build_aramina_request_json(
    *,
    patient_id: str,
    target_side: str,
    analysis_author: str = "",
    prediction_comment: str = "",
) -> dict[str, str]:
    """Build the official Aramina /predict request_json.

    Only the official fields (analysis_author, prediction_comment,
    patient_id, target_side) are included.  Bremen-only identifiers
    (container_id, source_id, workflow_id, model_id, job_id, request_id)
    are never forwarded.

    ``analysis_author`` defaults to "Bremen Platform" when absent/blank.
    ``target_side`` must be "left" or "right".  ``patient_id`` is required.

    Raises
    ------
    ValueError
        If patient_id is missing or target_side is invalid.
    """
    if not patient_id:
        raise ValueError("patient_id is required for Aramina prediction")
    side = str(target_side).strip().lower()
    if side not in _ARAMINA_ALLOWED_TARGET_SIDES:
        raise ValueError(
            f"Invalid target_side: {target_side!r}. "
            f"Allowed values: {', '.join(sorted(_ARAMINA_ALLOWED_TARGET_SIDES))}"
        )
    author = str(analysis_author).strip() if analysis_author else ""
    if not author:
        author = _ARAMINA_DEFAULT_ANALYSIS_AUTHOR
    comment = str(prediction_comment).strip() if prediction_comment else ""
    return {
        "analysis_author": author,
        "prediction_comment": comment,
        "patient_id": str(patient_id),
        "target_side": side,
    }


def _sanitize_report_value(value: Any) -> Any:
    """Recursively strip sensitive keys from a report value."""
    if isinstance(value, Mapping):
        return {
            k: _sanitize_report_value(v)
            for k, v in value.items()
            if k.lower() not in _ARAMINA_SENSITIVE_REPORT_KEYS
        }
    if isinstance(value, list):
        return [_sanitize_report_value(v) for v in value]
    return value


def _normalize_aramina_provider_response(
    response: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize a raw Aramina provider response into a safe public report.

    Accepts responses carrying external_report/internal_report.  The public
    report exposes external_report but never internal_report wholesale.
    Sensitive keys (artifact_sha256, model_checksum, path, S3, token,
    ticket, traceback) are stripped.  No probability/TRA/decision fields
    are invented when absent.
    """
    if not isinstance(response, Mapping):
        raise AraminaWorkflowError(
            "Aramina provider returned an invalid response"
        )
    report: dict[str, Any] = {}
    external = response.get("external_report")
    if external is not None:
        report["external_report"] = _sanitize_report_value(external)
    # internal_report is intentionally never exposed wholesale.
    return report


def _post_aramina_predict(
    provider_url: str,
    *,
    h5_path: str,
    request_json: Mapping[str, str],
) -> dict[str, Any]:
    """POST multipart input_h5 + request_json to Aramina /predict.

    This is the only network boundary.  Tests monkeypatch this function.
    No real external call is made here; no model.joblib is loaded or
    vendored in Bremen.
    """
    # Placeholder — no real network call is made in this environment.
    return {
        "external_report": {},
        "internal_report": {},
    }


def _call_aramina_provider(
    config: _AraminaProviderConfig,
    request: AraminaProviderRequest,
    *,
    h5_path: str = "",
) -> AraminaProviderResult:
    """Call the Aramina provider service.

    Validates that the provider is configured, builds the official
    request_json, and calls the provider HTTP boundary.  The response is
    normalized into a safe public report.
    """
    if not config.provider_url:
        raise AraminaProviderUnavailableError(
            "Aramina provider URL not configured. "
            "Set BREMEN_ARAMINA_PROVIDER_URL."
        )

    # Build the official request_json — validates patient_id and
    # target_side before any provider call.
    request_json = _build_aramina_request_json(
        patient_id=request.patient_id,
        target_side=request.target_side,
        analysis_author=request.analysis_author,
        prediction_comment=request.prediction_comment,
    )

    _log.info(
        "aramina.provider.call\tpatient_id=%s\ttarget_side=%s",
        request.patient_id,
        request.target_side,
    )

    response = _post_aramina_predict(
        config.provider_url,
        h5_path=h5_path,
        request_json=request_json,
    )
    report = _normalize_aramina_provider_response(response)

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
        report=report,
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
        # When no explicit provider_url is supplied, resolve it from the
        # environment (per-model override first, then the base fallback).
        resolved = (
            provider_url
            if provider_url is not None
            else _resolve_aramina_provider_url(model_id)
        )
        self._provider_url = resolved
        self._config = _AraminaProviderConfig(
            provider_url=resolved,
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
            payload: dict[str, Any] = {
                "model_family": result.model_family,
                "model_id": self._model_id,
                "model_version": self._model_version,
                "clinical_stage": result.clinical_stage,
                "technical_demo_only": result.technical_demo_only,
                "target_side": result.target_side,
                "patient_id_supplied": result.patient_id_supplied,
            }
            # Merge the safe public report (external_report only) into the
            # payload.  internal_report is never exposed wholesale.
            payload.update(result.report)
            return WorkflowResult(
                workflow_id=self.workflow_id,
                status="completed",
                payload=payload,
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
