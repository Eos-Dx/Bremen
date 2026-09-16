"""Aramina v0.2.13 runtime — Model Runtime Contract v1 (PR0156).

Moved from ``bremen.api.workflow_aramina`` so Aramina's complete model-specific
inference entry point is owned by the model package, not by platform
orchestration.  The runtime composes the package inference pipeline
(``inference._run_local_artifact``) unchanged; it performs no scientific
computation itself and does not reimplement any step of PR0137/PR0153B.

Behavior is preserved exactly from PR0153B:

- ``model_requirements`` assembles the contract view from the package
  ``manifest`` (model-declared static contract) plus per-deployment identity
  supplied by the platform registry entry passed at construction (public
  model_id/routing unchanged);
- ``validate_model_input`` performs the same request-parameter contract check;
- ``predict_model`` builds the request, calls the pipeline and PROPAGATES
  ``AraminaWorkflowError`` unchanged — the platform provider keeps the exact
  code/stage/preprocessing_diagnostic → WorkflowResult envelope translation it
  performs today;
- ``on_features`` is an intentional no-op (Aramina has no feature-stage
  boundary), unchanged from PR0153B.

No HTTP, jobs, reports, auth, storage or frontend coupling.
"""
from __future__ import annotations

from bremen.model_runtime import (
    CONTRACT_VERSION,
    ModelInput,
    ModelInputInvalidError,
    ModelRequirements,
    ModelValidation,
    RuntimePrediction,
)
from bremen.model_packages.aramina_v0213 import inference, manifest
from bremen.model_packages.aramina_v0213.errors import AraminaWorkflowError

# Historical module-level names retained for the transitional re-export
# surface (external callers/tests reference these via bremen.api.workflow_aramina).
ARAMINA_WORKFLOW_ID = manifest.WORKFLOW_ID
ARAMINA_REQUEST_FIELDS = manifest.REQUEST_FIELDS
ARAMINA_OPTIONAL_REQUEST_FIELDS = manifest.OPTIONAL_REQUEST_FIELDS
ARAMINA_ALLOWED_TARGET_SIDES = manifest.ALLOWED_TARGET_SIDES


class AraminaRuntime:
    """Model Runtime Contract v1 runtime over the Aramina v0.2.13 pipeline.

    It owns model-specific inference by composing the package inference
    pipeline.  No Aramina scientific logic is reimplemented here: preprocessing
    release selection, LR1, symmetry, the final model and the threshold all
    stay in the pipeline functions in ``inference.py``.
    """

    workflow_id = ARAMINA_WORKFLOW_ID

    def __init__(self, *, entry) -> None:
        self._entry = entry

    def model_requirements(self) -> ModelRequirements:
        """Describe the Aramina model-specific input contract.

        Static contract values (workflow, requires_target_side, allowed sides,
        request fields, notes) come from the package manifest.  Per-selection
        identity (model_id/version/feature_schema_version) remains entry-driven
        so public model identifiers are unchanged.
        """
        return ModelRequirements(
            contract_version=CONTRACT_VERSION,
            workflow_id=manifest.WORKFLOW_ID,
            model_id=self._entry.model_id,
            model_version=self._entry.model_version,
            feature_schema_version=self._entry.feature_schema_version,
            measurement_sides=manifest.MEASUREMENT_SIDES,
            total_measurements=manifest.TOTAL_MEASUREMENTS,
            requires_target_side=manifest.REQUIRES_TARGET_SIDE,
            allowed_target_sides=manifest.ALLOWED_TARGET_SIDES,
            request_fields=manifest.REQUEST_FIELDS,
            optional_request_fields=manifest.OPTIONAL_REQUEST_FIELDS,
            notes=manifest.INPUT_NOTES,
        )

    def _request_json(self, input: ModelInput) -> dict[str, str]:
        """Build the validated local request from the runtime input carrier."""
        parameters = input.parameters if isinstance(input.parameters, dict) else {}
        author = str(parameters.get("analysis_author", "") or "")
        comment = str(parameters.get("prediction_comment", "") or "")
        return inference._build_aramina_request_json(
            patient_id=input.patient_id,
            target_side=input.target_side,
            analysis_author=author,
            prediction_comment=comment,
        )

    def validate_model_input(self, input: ModelInput) -> ModelValidation:
        """Validate the model-specific explicit-target_side contract.

        Only the request-parameter scientific contract is checked here; the
        full canonical/source validation remains inside the pipeline.  Platform
        concerns (source existence, authorization, routing, job identity) are
        not runtime responsibilities.
        """
        if input.canonical is None:
            raise ModelInputInvalidError("not_a_canonical_case")
        try:
            self._request_json(input)
        except AraminaWorkflowError as exc:
            raise ModelInputInvalidError(exc.code) from None
        return ModelValidation(compatible=True)

    def predict_model(
        self, input: ModelInput, *, on_features=None,
    ) -> RuntimePrediction:
        """Execute the pipeline through the contract boundary.

        ``on_features`` is accepted for contract compatibility; Aramina does
        not emit a feature-stage boundary, so it is intentionally a no-op.
        ``AraminaWorkflowError`` propagates unchanged so the established
        public code/stage/diagnostic taxonomy is preserved exactly by the
        platform provider.
        """
        request_json = self._request_json(input)
        report, source_metadata, model_metadata, model_metrics = (
            inference._run_local_artifact(
                self._entry, input.canonical, request_json, input.container_path,
            )
        )
        return RuntimePrediction(
            workflow_id=manifest.WORKFLOW_ID,
            model_id=self._entry.model_id,
            model_version=str(report.get("model_version", "") or ""),
            result=report,
            # PR0159: the normalized metadata contract is produced by this
            # model package's own adapter and transported verbatim (never
            # interpreted by the platform).
            source_metadata=source_metadata,
            model_metadata=model_metadata,
            model_metrics=model_metrics,
        )


__all__ = [
    "ARAMINA_ALLOWED_TARGET_SIDES",
    "ARAMINA_OPTIONAL_REQUEST_FIELDS",
    "ARAMINA_REQUEST_FIELDS",
    "ARAMINA_WORKFLOW_ID",
    "AraminaRuntime",
]
