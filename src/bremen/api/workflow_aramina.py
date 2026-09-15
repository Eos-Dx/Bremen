"""Aramina workflow provider — platform orchestration adapter (PR0156).

PR0156 moved the complete Aramina model-specific scientific inference into the
inference-complete model package ``bremen.model_packages.aramina_v0213``
(Model Package Standard v1).  What remains here is a thin platform provider
that:

- builds the canonical/model input carrier,
- delegates prediction to the package runtime through Model Runtime Contract v1,
- translates the established ``AraminaWorkflowError`` taxonomy into the exact
  ``WorkflowResult`` public envelope (``ARAMINA_*`` code / failure_stage /
  preprocessing_diagnostic) it produced before the move.

This module performs NO model-specific preprocessing, feature engineering,
aggregation, scaler/estimator math or threshold application.

Transitional re-exports: the names that were defined here before PR0156 are
re-exported from the authoritative package modules (zero logic) so existing
platform/test imports keep resolving during the transition.  They are marked
deprecated; new code imports the package entry point
``bremen.model_packages.aramina_v0213`` directly.

The scoring pipeline itself is documented in the package (``inference.py``).
"""

from __future__ import annotations

from typing import Any

from .aramina_provider import AraminaProviderRequest
from .model_registry import RegistryModelEntry
from ..model_runtime import ModelInput
from ..model_packages.aramina_v0213 import manifest as _manifest
from ..model_packages.aramina_v0213 import runtime as _package_runtime
# ---------------------------------------------------------------------------
# Transitional re-exports (authoritative homes in the model package).
# These names existed here before PR0156 and remain importable here for
# backward compatibility only; the provider below does not use them.
# ---------------------------------------------------------------------------
from ..model_packages.aramina_v0213.errors import (  # noqa: F401
    FAILURE_STAGES,
    AraminaWorkflowError,
    _SAFE_FAILURES,
    _STAGE_DETAIL,
    _STAGE_REMEDIATION,
    _safe_release_tag,
    _safe_stage,
)
from ..model_packages.aramina_v0213.inference import (  # noqa: F401
    _build_aramina_request_json,
    _build_profile_matrix,
    _load_selected_artifact,
    _prepare_features,
    _reject_artifact,
    _run_local_artifact,
    _select_measurements,
    _validate_artifact,
)
from ..model_packages.aramina_v0213.trace import (  # noqa: F401
    _debug_checkpoint,
    _debug_stage,
)
from .workflow_provider import (
    CompatibilityResult,
    WorkflowFeatureVector,
    WorkflowProvider,
    WorkflowReadiness,
    WorkflowResult,
)

# ---------------------------------------------------------------------------
# Transitional re-exports (authoritative homes in the model package)
# ---------------------------------------------------------------------------

ARTIFACT_TYPE = _manifest.ARTIFACT_TYPE
_ARTIFACT_KIND = _manifest.ARTIFACT_KIND
_DEFAULT_AUTHOR = _manifest.DEFAULT_AUTHOR
_FINAL_FEATURE_COLUMNS = _manifest.FINAL_FEATURE_COLUMNS
_ALLOWED_PREPROCESSING_RELEASES = _manifest.ALLOWED_PREPROCESSING_RELEASES
ARAMINA_WORKFLOW_ID = _package_runtime.ARAMINA_WORKFLOW_ID
ARAMINA_REQUEST_FIELDS = _package_runtime.ARAMINA_REQUEST_FIELDS
ARAMINA_OPTIONAL_REQUEST_FIELDS = _package_runtime.ARAMINA_OPTIONAL_REQUEST_FIELDS
ARAMINA_ALLOWED_TARGET_SIDES = _package_runtime.ARAMINA_ALLOWED_TARGET_SIDES

# The Aramina runtime is now the package entry point.
AraminaRuntime = _package_runtime.AraminaRuntime


# ---------------------------------------------------------------------------
# Workflow provider (platform orchestration only)
# ---------------------------------------------------------------------------


class AraminaWorkflowProvider(WorkflowProvider):
    """Run one catalog-selected Aramina artifact locally.

    Platform adapter only: it resolves/owns the model package runtime, passes
    the canonical/model input, invokes the runtime contract and translates the
    runtime outcome into the established workflow result.  It performs no
    model-specific scientific preprocessing, feature engineering, aggregation,
    scaler/estimator math or threshold application of its own.
    """

    workflow_id = "aramina"

    def __init__(self, *, entry: RegistryModelEntry) -> None:
        self._entry = entry
        self._runtime = AraminaRuntime(entry=entry)

    @property
    def runtime(self) -> AraminaRuntime:
        """The model package runtime this provider orchestrates."""
        return self._runtime

    def model_runtime(self) -> AraminaRuntime:
        """Return the Model Runtime Contract v1 implementation for this workflow."""
        return self._runtime

    def readiness(self) -> WorkflowReadiness:
        return WorkflowReadiness(
            workflow_id=self.workflow_id, configured=True, model_ready=True,
            scientifically_certified=False,
        )

    def validate_compatibility(self, canonical: Any) -> CompatibilityResult:
        return CompatibilityResult(compatible=True, reason="artifact_contract_required")

    def build_features(self, canonical: Any) -> WorkflowFeatureVector:
        raise AraminaWorkflowError("ARAMINA_INVALID_REQUEST")

    def run_inference(self, features: WorkflowFeatureVector) -> WorkflowResult:
        return WorkflowResult(
            workflow_id=self.workflow_id, status="failed",
            error="ARAMINA_INVALID_REQUEST",
        )

    def execute(
        self, canonical: Any, context: Any = None, *,
        aramina_request: AraminaProviderRequest | None = None, h5_path: str = "",
    ) -> WorkflowResult:
        try:
            if aramina_request is None:
                raise AraminaWorkflowError("ARAMINA_INVALID_REQUEST")
            model_input = ModelInput(
                workflow_id=self.workflow_id,
                measurements=tuple(getattr(canonical, "measurements", ()) or ()),
                canonical=canonical,
                patient_id=aramina_request.patient_id,
                target_side=aramina_request.target_side,
                container_path=h5_path,
                parameters={
                    "analysis_author": aramina_request.analysis_author,
                    "prediction_comment": aramina_request.prediction_comment,
                    "container_id": aramina_request.container_id,
                    "source_id": aramina_request.source_id,
                },
            )
            prediction = self._runtime.predict_model(model_input)
            report = dict(prediction.result)
            payload = {
                "workflow_id": self.workflow_id,
                "model_id": self._entry.model_id,
                "model_version": self._entry.model_version,
                "technical_demo_only": True,
                "scientifically_certified": False,
                "external_report": report,
            }
            if self._entry._clinical_stage == "research draft":
                payload["clinical_stage"] = "research draft"
            if context is not None:
                context.emit("runtime.output.completed", "output", "completed")
            return WorkflowResult(
                workflow_id=self.workflow_id, status="completed", payload=payload,
            )
        except AraminaWorkflowError as exc:
            code = exc.code
            stage = exc.stage
            diagnostic = exc.preprocessing_diagnostic
        except Exception:
            code = "ARAMINA_EXECUTION_FAILED"
            stage = None
            diagnostic = None
        return WorkflowResult(
            workflow_id=self.workflow_id, status="failed", error=code,
            failure_stage=_safe_stage(stage) if code == "ARAMINA_UNSUPPORTED_INPUT" else None,
            preprocessing_diagnostic=(
                diagnostic
                if code == "ARAMINA_UNSUPPORTED_INPUT" and stage == "preprocessing_contract"
                else None
            ),
        )
