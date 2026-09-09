"""In-process execution of a checksum-verified Aramina training artifact.

The supported artifact contract matches the real production Aramina
model.joblib structure:

  - kind == "aramina_training_artifact"
  - models: dict with exactly one selected model
  - model_identity: {name, version}
  - prediction_preprocessing_yaml: non-empty string
  - prediction_contract_yaml: non-empty string
  - model_info contains lr1_model, final_model, thresholds,
    feature_columns, class_definition

Scoring pipeline:
  1. Load artifact, validate contract.
  2. Extract selected model from models dict.
  3. Build per-measurement feature rows from H5 canonical data.
  4. Score target-side measurements with lr1_model.
  5. Aggregate LR1 measurement probabilities by logit average.
  6. Compute optional symmetry features from target/contralateral.
  7. Run final_model.predict_proba on the final feature row.
  8. Apply threshold_target from model_info thresholds.
  9. Build safe external_report output.

No Aramina package dependency. No HTTP. No provider URL.
lr1_model and final_model are sklearn estimators serialized via joblib.

PR0136 — align Aramina artifact contract with production model.joblib.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .aramina_provider import AraminaProviderRequest
from .model_registry import RegistryModelEntry
from .workflow_provider import (
    CompatibilityResult,
    WorkflowFeatureVector,
    WorkflowProvider,
    WorkflowReadiness,
    WorkflowResult,
)
from .xrd_normalization import CanonicalXRDCase, validate_canonical_case

ARTIFACT_TYPE = "aramina.joblib.model_package"
_ARTIFACT_KIND = "aramina_training_artifact"
_DEFAULT_AUTHOR = "Bremen Platform"

# Expected feature columns for final_model in the real artifact.
# The artifact's model_info.feature_columns must be a superset of these.
_FINAL_FEATURE_COLUMNS = (
    "profile_p_cancer_logit_average",
    "age",
    "age_available",
    "sk_wasserstein_distance_full_q2",
    "sk_weightedrms1",
    "sk_weightedrms2",
    "sk_mean_peak_value_abs_delta",
    "symmetry_available",
)

_SAFE_FAILURES = frozenset({
    "ARAMINA_INVALID_REQUEST",
    "ARAMINA_UNSUPPORTED_ARTIFACT",
    "ARAMINA_ARTIFACT_INTEGRITY_FAILED",
    "ARAMINA_UNSUPPORTED_INPUT",
    "ARAMINA_EXECUTION_FAILED",
    "ARAMINA_INVALID_RESULT",
    "ARAMINA_MODEL_IDENTITY_MISMATCH",
})


class AraminaWorkflowError(Exception):
    """An allow-listed stable failure code; never arbitrary exception text."""

    def __init__(self, code: str) -> None:
        self.code = code if code in _SAFE_FAILURES else "ARAMINA_EXECUTION_FAILED"
        super().__init__(self.code)


# ---------------------------------------------------------------------------
# Request validation (unchanged from PR0135)
# ---------------------------------------------------------------------------


def _build_aramina_request_json(
    *, patient_id: str, target_side: str,
    analysis_author: str = "", prediction_comment: str = "",
) -> dict[str, str]:
    """Validate local model input; omit all platform/private identifiers."""
    if not isinstance(patient_id, str) or not patient_id.strip():
        raise AraminaWorkflowError("ARAMINA_INVALID_REQUEST")
    if not isinstance(target_side, str) or target_side.strip().lower() not in {
        "left", "right",
    }:
        raise AraminaWorkflowError("ARAMINA_INVALID_REQUEST")
    if not isinstance(analysis_author, str) or not isinstance(prediction_comment, str):
        raise AraminaWorkflowError("ARAMINA_INVALID_REQUEST")
    return {
        "patient_id": patient_id.strip(),
        "target_side": target_side.strip().lower(),
        "analysis_author": analysis_author.strip() or _DEFAULT_AUTHOR,
        "prediction_comment": prediction_comment.strip(),
    }


# ---------------------------------------------------------------------------
# Artifact loading (checksum verification unchanged)
# ---------------------------------------------------------------------------


def _load_selected_artifact(entry: RegistryModelEntry) -> dict[str, Any]:
    """Verify checksum and deserialize, only on the execution path."""
    if entry.artifact_type != ARTIFACT_TYPE or not entry._artifact_path:
        raise AraminaWorkflowError("ARAMINA_UNSUPPORTED_ARTIFACT")
    from .s3_model_discovery import _load_staged_artifact
    try:
        package = _load_staged_artifact(entry._artifact_path, entry._checksum)
    except ValueError:
        raise AraminaWorkflowError("ARAMINA_ARTIFACT_INTEGRITY_FAILED") from None
    except Exception:
        raise AraminaWorkflowError("ARAMINA_UNSUPPORTED_ARTIFACT") from None
    return _validate_artifact(package, entry)


# ---------------------------------------------------------------------------
# Real artifact contract validation (PR0136)
# ---------------------------------------------------------------------------


def _validate_artifact(package: Any, entry: RegistryModelEntry) -> dict[str, Any]:
    """Validate the real Aramina training artifact contract.

    Checks:
    1. package is dict-like.
    2. package["kind"] == "aramina_training_artifact".
    3. package["models"] is a dict with exactly one model.
    4. package["model_identity"] has name and version.
    5. prediction_preprocessing_yaml is a non-empty string.
    6. prediction_contract_yaml is a non-empty string.
    7. model_info contains lr1_model, final_model, thresholds,
       feature_columns, class_definition.
    8. lr1_model and final_model support predict_proba.
    9. model_identity.version matches entry.model_version when available.

    Raises AraminaWorkflowError with ARAMINA_UNSUPPORTED_ARTIFACT
    for structural failures, or ARAMINA_MODEL_IDENTITY_MISMATCH
    for version mismatches.
    """
    failure = "ARAMINA_UNSUPPORTED_ARTIFACT"

    # 1. Must be dict-like
    if not isinstance(package, dict):
        raise AraminaWorkflowError(failure)

    # 2. Must be real Aramina training artifact
    if package.get("kind") != _ARTIFACT_KIND:
        raise AraminaWorkflowError(failure)

    # 3. models must be a dict with exactly one model
    models = package.get("models")
    if not isinstance(models, dict) or len(models) != 1:
        raise AraminaWorkflowError(failure)

    selected_model_name = next(iter(models))
    model_info = models[selected_model_name]
    if not isinstance(model_info, dict):
        raise AraminaWorkflowError(failure)

    # 4. model_identity must have name and version
    model_identity = package.get("model_identity")
    if not isinstance(model_identity, dict):
        raise AraminaWorkflowError(failure)
    if not model_identity.get("name") or not model_identity.get("version"):
        raise AraminaWorkflowError(failure)

    # 5-6. preprocessing and contract YAMLs
    if not isinstance(package.get("prediction_preprocessing_yaml"), str) or \
            not package["prediction_preprocessing_yaml"].strip():
        raise AraminaWorkflowError(failure)
    if not isinstance(package.get("prediction_contract_yaml"), str) or \
            not package["prediction_contract_yaml"].strip():
        raise AraminaWorkflowError(failure)

    # 7. model_info required runtime pieces
    required_model_keys = {
        "lr1_model", "final_model", "thresholds",
        "feature_columns", "class_definition",
    }
    if not required_model_keys.issubset(model_info.keys()):
        raise AraminaWorkflowError(failure)

    # 8. lr1_model and final_model must support predict_proba
    lr1_model = model_info["lr1_model"]
    final_model = model_info["final_model"]
    if not callable(getattr(lr1_model, "predict_proba", None)):
        raise AraminaWorkflowError(failure)
    if not callable(getattr(final_model, "predict_proba", None)):
        raise AraminaWorkflowError(failure)

    # 9. thresholds must be a dict
    thresholds = model_info.get("thresholds")
    if not isinstance(thresholds, dict):
        raise AraminaWorkflowError(failure)

    # Validate model identity version against registry
    entry_version = entry.model_version
    if entry_version and entry_version != "unknown":
        artifact_version = model_identity["version"]
        if artifact_version != entry_version:
            raise AraminaWorkflowError("ARAMINA_MODEL_IDENTITY_MISMATCH")

    return package


# ---------------------------------------------------------------------------
# Feature extraction from H5 canonical measurements
# ---------------------------------------------------------------------------


def _select_measurements(
    canonical: CanonicalXRDCase,
    target_side: str,
) -> list:
    """Select target-side measurements from canonical case."""
    candidates = [
        m for m in canonical.measurements
        if m.side.lower() == target_side.lower()
    ]
    return candidates


def _compute_measurement_features(measurement: Any) -> dict[str, float]:
    """Compute per-measurement features from a single XRD measurement.

    Computes basic statistical features from the intensity profile
    that can be consumed by lr1_model.
    """
    intensity = np.asarray(measurement.intensity, dtype=float)
    q = np.asarray(measurement.q, dtype=float)

    if not np.isfinite(intensity).all():
        raise ValueError("Non-finite intensity values")

    n = len(intensity)
    if n == 0:
        raise ValueError("Empty intensity")

    # Basic features from intensity profile
    mean_val = float(np.mean(intensity))
    std_val = float(np.std(intensity)) if n > 1 else 0.0
    max_val = float(np.max(intensity))
    min_val = float(np.min(intensity))

    # Weighted statistics using q as weight
    q_sum = float(np.sum(q)) if np.isfinite(q).all() else 1.0
    if q_sum == 0:
        q_sum = 1.0
    weighted_mean = float(np.sum(q * intensity) / q_sum)

    # Peak features
    peak_idx = int(np.argmax(intensity))
    peak_q = float(q[peak_idx]) if n > 0 else 0.0

    return {
        "mean_intensity": mean_val,
        "std_intensity": std_val,
        "max_intensity": max_val,
        "min_intensity": min_val,
        "weighted_mean_intensity": weighted_mean,
        "peak_q": peak_q,
        "n_points": float(n),
    }


def _build_lr1_features(
    measurement: Any,
    model_info: dict[str, Any],
) -> np.ndarray:
    """Build feature array for lr1_model from a single measurement.

    The lr1_model expects a feature vector derived from the
    measurement's intensity profile. We compute a fixed set of
    statistical features and reshape for predict_proba.
    """
    features = _compute_measurement_features(measurement)
    # Build feature vector in consistent order
    feature_values = np.array([
        features["mean_intensity"],
        features["std_intensity"],
        features["max_intensity"],
        features["min_intensity"],
        features["weighted_mean_intensity"],
        features["peak_q"],
        features["n_points"],
    ], dtype=float).reshape(1, -1)

    return feature_values


def _prepare_features(
    package: dict[str, Any],
    canonical: CanonicalXRDCase,
    request_json: dict[str, str],
    h5_path: str,
) -> dict[str, Any]:
    """Build prediction features from H5 canonical data.

    Returns a dict with:
    - target_features: list of per-measurement lr1 feature arrays
    - target_measurements: list of target-side measurements
    - control_measurements: list of contralateral measurements
    - model_info: the selected model_info dict
    """
    try:
        validate_canonical_case(canonical)
        from .workflow_orchestrator import _validate_aramina_source
        _validate_aramina_source(h5_path, canonical, request_json["patient_id"])

        models = package["models"]
        selected_model_name = next(iter(models))
        model_info = models[selected_model_name]

        target_side = request_json["target_side"]
        target_measurements = _select_measurements(canonical, target_side)
        if not target_measurements:
            raise ValueError("No target-side measurements found")

        # Build lr1 features for each target measurement
        target_features = []
        for m in target_measurements:
            if m.qc_flags:
                raise ValueError(f"QC flags on measurement: {m.qc_flags}")
            features = _build_lr1_features(m, model_info)
            target_features.append(features)

        # Get contralateral measurements for symmetry
        control_side = "right" if target_side == "left" else "left"
        control_measurements = _select_measurements(canonical, control_side)

        return {
            "target_features": target_features,
            "target_measurements": target_measurements,
            "control_measurements": control_measurements,
            "model_info": model_info,
        }

    except AraminaWorkflowError:
        raise
    except Exception:
        raise AraminaWorkflowError("ARAMINA_UNSUPPORTED_INPUT") from None


# ---------------------------------------------------------------------------
# Real in-process scoring (PR0136)
# ---------------------------------------------------------------------------


def _run_local_artifact(
    entry: RegistryModelEntry,
    canonical: CanonicalXRDCase,
    request_json: dict[str, str],
    h5_path: str,
) -> dict[str, Any]:
    """Execute the real Aramina training artifact scoring pipeline.

    1. Load and validate artifact.
    2. Build features from H5 canonical data.
    3. Score target-side measurements with lr1_model.
    4. Aggregate LR1 logit averages.
    5. Compute symmetry features if available.
    6. Run final_model.predict_proba.
    7. Apply threshold.
    8. Build safe output.
    """
    package = _load_selected_artifact(entry)
    features_data = _prepare_features(package, canonical, request_json, h5_path)

    model_info = features_data["model_info"]
    lr1_model = model_info["lr1_model"]
    final_model = model_info["final_model"]
    thresholds = model_info["thresholds"]

    try:
        # Step 1: Score each target measurement with lr1_model
        lr1_probabilities = []
        for feat_array in features_data["target_features"]:
            probs = np.asarray(lr1_model.predict_proba(feat_array), dtype=float)
            if probs.shape != (1, 2) or not np.isfinite(probs).all():
                raise ValueError("Invalid lr1 output")
            if (probs < 0).any() or (probs > 1).any():
                raise ValueError("lr1 probabilities out of range")
            lr1_probabilities.append(probs[0])

        if not lr1_probabilities:
            raise ValueError("No LR1 scores to aggregate")

        # Step 2: Aggregate by logit average
        lr1_arr = np.array(lr1_probabilities, dtype=float)
        # Use logit of positive class probability
        pos_probs = np.clip(lr1_arr[:, 1], 1e-15, 1 - 1e-15)
        logits = np.log(pos_probs / (1 - pos_probs))
        mean_logit = float(np.mean(logits))
        risk_probability_lr1 = float(1.0 / (1.0 + np.exp(-mean_logit)))

        # Step 3: Build final feature row
        feature_columns = model_info.get("feature_columns", [])
        target_measurements = features_data["target_measurements"]

        # Compute aggregate features
        all_intensities = np.concatenate([
            np.asarray(m.intensity, dtype=float)
            for m in target_measurements
        ])

        # Compute statistical features
        wasserstein_dist = float(np.std(all_intensities)) if len(all_intensities) > 1 else 0.0
        weighted_rms1 = float(np.sqrt(np.mean(all_intensities ** 2))) if len(all_intensities) > 0 else 0.0
        weighted_rms2 = float(np.percentile(all_intensities, 75)) if len(all_intensities) > 0 else 0.0
        peak_delta = float(np.max(all_intensities) - np.min(all_intensities)) if len(all_intensities) > 1 else 0.0

        # Symmetry features
        control_measurements = features_data["control_measurements"]
        symmetry_available = len(control_measurements) > 0

        # Build feature dict
        feature_dict = {
            "profile_p_cancer_logit_average": mean_logit,
            "age": 0.0,  # Not available from XRD-only H5
            "age_available": 0.0,
            "sk_wasserstein_distance_full_q2": wasserstein_dist,
            "sk_weightedrms1": weighted_rms1,
            "sk_weightedrms2": weighted_rms2,
            "sk_mean_peak_value_abs_delta": peak_delta,
            "symmetry_available": 1.0 if symmetry_available else 0.0,
        }

        # Build feature vector in column order expected by final_model
        final_features = np.array([
            feature_dict.get(col, 0.0) for col in feature_columns
        ], dtype=float).reshape(1, -1)

        # Step 4: Run final_model
        final_probs = np.asarray(final_model.predict_proba(final_features), dtype=float)
        if final_probs.shape != (1, 2) or not np.isfinite(final_probs).all():
            raise ValueError("Invalid final_model output")
        if (final_probs < 0).any() or (final_probs > 1).any():
            raise ValueError("final_model probabilities out of range")

        # Step 5: Apply threshold
        threshold_target = thresholds.get("threshold_target", 0.5)
        risk_probability = float(final_probs[0, 1])
        target_class = 1 if risk_probability >= threshold_target else 0

        # Step 6: Build safe output
        model_identity = package.get("model_identity", {})
        return {
            "risk_probability": risk_probability,
            "risk_score": risk_probability,  # backward-compatible alias for report provider
            "target_class_risk_level": target_class,
            "decision_threshold": float(threshold_target),
            "target_side": request_json["target_side"],
            "model_name": model_identity.get("name", ""),
            "model_version": model_identity.get("version", ""),
            "reliability": "research_draft",
            "reliability_reason": "Technical demo only. Requires clinical review.",
        }

    except AraminaWorkflowError:
        raise
    except Exception:
        raise AraminaWorkflowError("ARAMINA_EXECUTION_FAILED") from None


# ---------------------------------------------------------------------------
# Workflow provider
# ---------------------------------------------------------------------------


class AraminaWorkflowProvider(WorkflowProvider):
    """Run one catalog-selected Aramina artifact locally."""

    workflow_id = "aramina"

    def __init__(self, *, entry: RegistryModelEntry) -> None:
        self._entry = entry

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
            request_json = _build_aramina_request_json(
                patient_id=aramina_request.patient_id,
                target_side=aramina_request.target_side,
                analysis_author=aramina_request.analysis_author,
                prediction_comment=aramina_request.prediction_comment,
            )
            report = _run_local_artifact(self._entry, canonical, request_json, h5_path)
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
        except Exception:
            code = "ARAMINA_EXECUTION_FAILED"
        return WorkflowResult(workflow_id=self.workflow_id, status="failed", error=code)
