"""Aramina failure vocabulary — model-owned safe taxonomy (PR0156).

Moved verbatim from ``bremen.api.workflow_aramina`` by PR0156.  This owns the
allow-listed public failure codes, the PR0141 safe stage taxonomy, the fixed
per-stage remediation/detail copy that the platform failure API renders, and
the trace allowlists consumed by the private diagnostics in ``trace.py``.

The strings and sets are the established public contract and are unchanged;
only their authoritative module location moved so Aramina model science is not
owned by platform orchestration modules.  No scientific inference happens here;
this is failure metadata only.
"""
from __future__ import annotations

from bremen.model_packages.aramina_v0213 import manifest

# ---------------------------------------------------------------------------
# Public failure codes — stable, allow-listed; never arbitrary exception text.
# ---------------------------------------------------------------------------

_SAFE_FAILURES = frozenset({
    "ARAMINA_INVALID_REQUEST",
    "ARAMINA_UNSUPPORTED_ARTIFACT",
    "ARAMINA_ARTIFACT_INTEGRITY_FAILED",
    "ARAMINA_UNSUPPORTED_INPUT",
    "ARAMINA_EXECUTION_FAILED",
    "ARAMINA_INVALID_RESULT",
    "ARAMINA_MODEL_IDENTITY_MISMATCH",
})

# PR0141 — fixed safe failure taxonomy for ARAMINA_UNSUPPORTED_INPUT.
# These are public category names, not private failing function names.
FAILURE_STAGES = frozenset({
    "preprocessing_contract",
    "h5_patient_contract",
    "target_side_contract",
    "profile_matrix_contract",
    "lr1_contract",
    "symmetry_contract",
    "final_dataframe_contract",
    "final_model_contract",
    "report_contract",
    "unknown_input_contract",
})

# Fixed remediation text per stage. Never derived from exception contents.
_STAGE_REMEDIATION = {
    "preprocessing_contract": (
        "The selected H5 could not be preprocessed with the model's declared "
        "preprocessing contract. Verify the container layout and required "
        "measurement metadata, then retry with a fresh source_id."
    ),
    "h5_patient_contract": (
        "The requested patient_id was not present in the preprocessed "
        "measurements. Use the patient_display_name returned by "
        "/demo/api/h5/containers for the selected source_id."
    ),
    "target_side_contract": (
        "The selected container has no usable measurements for the requested "
        "target_side. Retry with the other side, or select a container that "
        "contains the requested side."
    ),
    "profile_matrix_contract": (
        "The target-side measurements could not be assembled into a valid "
        "profile matrix. Verify the container measurement data, then retry."
    ),
    "lr1_contract": (
        "The model's first-stage scorer rejected the profile matrix. This is "
        "a model/input compatibility failure, not a request error."
    ),
    "symmetry_contract": (
        "Paired target/contralateral symmetry features could not be computed "
        "for this container and target_side."
    ),
    "final_dataframe_contract": (
        "The final feature table could not be built with the model's declared "
        "feature columns."
    ),
    "final_model_contract": (
        "The model's final scorer rejected the feature table. This is a "
        "model/input compatibility failure, not a request error."
    ),
    "report_contract": (
        "The model produced a result but the report payload could not be "
        "constructed safely."
    ),
    "unknown_input_contract": (
        "The selected H5 could not be used for the requested Aramina patient "
        "and target side. Refresh /demo/api/h5/containers and retry with a "
        "fresh source_id."
    ),
}

# Fixed public detail text per stage.
_STAGE_DETAIL = {
    "preprocessing_contract": "Artifact-declared preprocessing did not produce usable measurements.",
    "h5_patient_contract": "Requested patient was not present in the preprocessed measurements.",
    "target_side_contract": "No usable measurements were available for the requested target side.",
    "profile_matrix_contract": "Target-side measurements did not form a valid profile matrix.",
    "lr1_contract": "The first-stage scorer could not score the profile matrix.",
    "symmetry_contract": "Paired symmetry features could not be computed.",
    "final_dataframe_contract": "The final feature table did not match the model feature contract.",
    "final_model_contract": "The final scorer could not score the feature table.",
    "report_contract": "The report payload could not be constructed.",
    "unknown_input_contract": "Selected H5 could not be used for the requested patient and target side.",
}

# ---------------------------------------------------------------------------
# Private diagnostics allowlists (consumed by trace.py; never public output).
# ---------------------------------------------------------------------------

_TRACE_LABELS = frozenset(manifest.FINAL_FEATURE_COLUMNS) | {
    "lr1_model", "final_model", "thresholds", "feature_columns", "class_definition",
    "symmetry_policy", "prediction_reference_scores", "tissue_risk_assessment",
    "final_fit_training_metrics", "threshold_target", "threshold_control",
    "Pipeline", "StandardScaler", "LogisticRegression", "GatedSymmetryLogistic",
    "ValueError", "TypeError", "KeyError", "IndexError", "AttributeError",
    "RuntimeError", "AraminaWorkflowError", "left", "right", "ModuleNotFoundError",
    "TargetBreastGatedSymmetryLogistic", "aramina_training_artifact",
    "aramina_target_breast_risk", "0.2.12-beta", "0.2.13-beta", "0.3",
    "kind", "version", "model_identity", "name", "models", "model_type",
    "model_columns", "feature_schema", "prediction_preprocessing_yaml",
    "prediction_contract_yaml", "model_descriptions", "warnings", "dataset_summary",
    "training_config_yaml", "historical_preprocessing_yaml", "model_definition_yaml",
    "model_performance", "evaluation", "preprocessing_metadata", "metadata", "reproducibility",
    "symmetry_gate", "symmetry_feature_contract", "threshold_youden", "target_sensitivity",
    "target_reached", "success", "failed", "dict", "str", "list", "NoneType",
    "package_type", "artifact_kind", "single_model", "model_info_type",
    "identity_type", "identity_fields", "preprocessing_yaml", "contract_yaml",
    "required_model_keys", "lr1_predict_method", "final_predict_method", "threshold_type",
    "model_version_match", "entry_contract",
}
_TRACE_STAGES = frozenset({
    "artifact_load", "artifact_loaded", "artifact_validation", "compatibility_bridge", "joblib_load", "canonical_validation", "source_validation",
    "target_selection", "target_qc", "profile_matrix", "lr1_predict_proba",
    "lr1_output_validation", "lr1_aggregation", "symmetry_features",
    "final_dataframe", "final_predict_proba", "final_output_validation",
    "threshold", "report", "artifact_preprocessing",
})


class AraminaWorkflowError(Exception):
    """An allow-listed stable failure code; never arbitrary exception text.

    PR0141 adds an optional fixed ``stage`` so ARAMINA_UNSUPPORTED_INPUT can
    report which safe runtime boundary failed. ``stage`` is always drawn from
    ``FAILURE_STAGES``; unknown values collapse to ``unknown_input_contract``.
    """

    def __init__(
        self, code: str, stage: str | None = None,
        original_exception_class: str | None = None,
        preprocessing_diagnostic: dict[str, str] | None = None,
    ) -> None:
        self.code = code if code in _SAFE_FAILURES else "ARAMINA_EXECUTION_FAILED"
        self.stage = stage if stage in FAILURE_STAGES else None
        # Private only: never serialized into public responses.
        self.original_exception_class = (
            original_exception_class
            if original_exception_class in _TRACE_LABELS else None
        )
        # PR0142: allowlisted preprocessing subdiagnostics. Already sanitized
        # by aramina_preprocessing.safe_preprocessing_diagnostic.
        self.preprocessing_diagnostic = (
            dict(preprocessing_diagnostic)
            if isinstance(preprocessing_diagnostic, dict) else None
        )
        super().__init__(self.code)


def _safe_stage(stage: str | None) -> str:
    """Collapse any non-allowlisted stage to the unknown input contract."""
    return stage if stage in FAILURE_STAGES else "unknown_input_contract"


def _safe_release_tag(config_yaml: str) -> str:
    """Return an allowlisted preprocessing release tag, or empty string."""
    try:
        import yaml

        config = yaml.safe_load(config_yaml)
        release = config.get("xrd_preprocessing", {}).get("release_tag")
    except Exception:  # noqa: BLE001 -- diagnostics must never raise
        return ""
    return release if release in manifest.ALLOWED_PREPROCESSING_RELEASES else ""


__all__ = [
    "FAILURE_STAGES",
    "AraminaWorkflowError",
    "_SAFE_FAILURES",
    "_STAGE_DETAIL",
    "_STAGE_REMEDIATION",
    "_TRACE_LABELS",
    "_TRACE_STAGES",
    "_safe_release_tag",
    "_safe_stage",
]
