"""Feature artifact prediction — controlled internal prediction flow.

PR0059 — Controlled Feature Artifact Prediction Flow.

Provides a single public function ``run_feature_artifact_prediction()``
that takes a validated feature artifact and an already-loaded model
package dict, then runs portable logistic regression inference and
produces a safe decision-support report.

This is an internal module only — no public HTTP schema change,
no feature_artifact_path/feature_artifact_uri public fields,
no h5_path/h5_uri behavior change, no raw GFRM/H5 preprocessing.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from bremen.feature_artifacts import (
    FEATURE_ARTIFACT_SCHEMA_VERSION,
    REQUIRED_FEATURE_COLUMNS,
    FeatureArtifactError,
    validate_feature_artifact,
)
from bremen.inference import predict_proba_portable
from bremen.api.decision_support import build_decision_support_report

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRIAGE_RECOMMENDED = "MRI_RECOMMENDED"
TRIAGE_RULE_OUT = "MRI_RULE_OUT"

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class FeatureArtifactPredictionError(Exception):
    """Base exception for feature artifact prediction failures."""


class FeatureArtifactPredictorError(FeatureArtifactPredictionError):
    """Predictor-related failure (e.g., model mismatch, inference error)."""


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class FeatureArtifactPredictionResult:
    """Structured result from feature artifact prediction.

    Contains prediction fields, decision-support report, and safe
    provenance metadata.  Does NOT contain raw patient identifiers,
    raw scan refs, raw H5 paths, raw checksums, or raw feature values.
    """

    prediction_id: str
    model_version: str
    feature_schema_version: str
    threshold_version: str
    threshold_value: float
    qc_status: str
    qc_flags: list[str]
    patient_id: str | None
    p_mri_needed: float
    triage_recommendation: str
    created_at_utc: str
    decision_support_report: dict[str, Any]
    feature_columns: list[str]
    provenance: dict[str, Any] = field(default_factory=dict)

    # Convenience aliases for test/discovery clarity
    @property
    def predicted_class(self) -> str:
        """Synonym for triage_recommendation."""
        return self.triage_recommendation

    @property
    def probability(self) -> float:
        """Synonym for p_mri_needed (model score)."""
        return self.p_mri_needed


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------


def run_feature_artifact_prediction(
    artifact: dict[str, Any],
    predictor: dict[str, Any],
    *,
    model_version: str | None = None,
) -> FeatureArtifactPredictionResult:
    """Run prediction from a validated feature artifact.

    Parameters
    ----------
    artifact :
        Feature artifact dict conforming to
        ``bremen.feature_artifact.v0.1`` schema.
        Must pass ``validate_feature_artifact()``.
    predictor :
        Already-loaded model package dict (``portable_logreg`` format).
        Must be compatible with ``predict_proba_portable()``.
    model_version :
        Optional model version string.  If ``None``, resolved from
        the predictor package ``model_version`` field.

    Returns
    -------
    ``FeatureArtifactPredictionResult`` with prediction, decision-support
    report, and safe provenance metadata.

    Raises
    ------
    FeatureArtifactPredictionError
        If artifact validation fails.
    FeatureArtifactPredictorError
        If predictor inference fails.
    """
    # 1. Validate artifact — reject before any prediction
    try:
        validated = validate_feature_artifact(artifact)
    except FeatureArtifactError as exc:
        raise FeatureArtifactPredictionError(
            f"Feature artifact validation failed: {exc}"
        ) from exc

    # 2. Extract features in REQUIRED_FEATURE_COLUMNS order.
    #    validate_feature_artifact already normalised the ordering.
    feature_values: list[float] = validated["feature_values"]
    feature_columns: list[str] = validated["feature_columns"]

    # Verify feature columns match REQUIRED_FEATURE_COLUMNS
    if list(feature_columns) != list(REQUIRED_FEATURE_COLUMNS):
        raise FeatureArtifactPredictionError(
            "Validated feature columns do not match REQUIRED_FEATURE_COLUMNS. "
            "This is a validation invariant failure."
        )

    # 3. Run portable inference using the already-loaded predictor
    try:
        inference_result = predict_proba_portable(
            predictor, feature_values, skip_validation=False
        )
    except Exception as exc:
        raise FeatureArtifactPredictorError(
            f"Predictor inference failed: {exc}"
        ) from exc

    # 4. Extract probability and prediction from inference result
    prob: float = float(inference_result["probability"])
    threshold: float = float(inference_result["threshold_applied"])
    prediction_raw: int = int(inference_result["prediction"])
    triage: str = TRIAGE_RECOMMENDED if prediction_raw == 1 else TRIAGE_RULE_OUT

    # 5. Resolve model metadata from predictor package
    plr: dict[str, Any] = predictor.get("portable_logreg", {})
    resolved_model_version: str = model_version or str(
        plr.get("model_version", "")
    ) or ""
    threshold_version: str = str(
        plr.get("threshold_version", "")
    ) or "v0.1"

    # 6. Build safe prediction dict for decision-support report
    created_at: str = datetime.now(timezone.utc).isoformat()
    prediction_id: str = str(uuid.uuid4())

    prediction_dict: dict[str, Any] = {
        "prediction_id": prediction_id,
        "model_version": resolved_model_version,
        "model_checksum": "",
        "feature_schema_version": FEATURE_ARTIFACT_SCHEMA_VERSION,
        "threshold_version": threshold_version,
        "threshold_value": threshold,
        "qc_status": "passed",
        "qc_flags": [],
        "patient_id": None,
        "p_mri_needed": prob,
        "triage_recommendation": triage,
        "created_at_utc": created_at,
    }

    # 7. Build decision-support report using existing helper
    decision_support: dict[str, Any] = build_decision_support_report(
        prediction_dict,
        input_mode="feature_artifact",
    )

    # 8. Build safe provenance from validated artifact metadata
    safe_metadata: dict[str, Any] | None = validated.get("metadata")
    provenance: dict[str, Any] = {}
    if isinstance(safe_metadata, dict):
        for key in (
            "preprocessing_source",
            "source_package_version",
            "configuration_label",
        ):
            if key in safe_metadata:
                provenance[key] = safe_metadata[key]

    return FeatureArtifactPredictionResult(
        prediction_id=prediction_id,
        model_version=resolved_model_version,
        feature_schema_version=FEATURE_ARTIFACT_SCHEMA_VERSION,
        threshold_version=threshold_version,
        threshold_value=threshold,
        qc_status="passed",
        qc_flags=[],
        patient_id=None,
        p_mri_needed=prob,
        triage_recommendation=triage,
        created_at_utc=created_at,
        decision_support_report=decision_support,
        feature_columns=list(feature_columns),
        provenance=provenance,
    )
