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
  1. Load artifact (with compatibility bridge for pickle stubs).
  2. Validate artifact contract.
  3. Execute artifact-owned raw H5 preprocessing and build profile_matrix.
  4. Score target-side measurements with lr1_model using profile_matrix.
  5. Aggregate LR1 measurement probabilities by logit average.
  6. Compute symmetry features from target/contralateral.
  7. Build pandas DataFrame with model_info["feature_columns"].
  8. Run final_model.predict_proba on DataFrame.
  9. Apply threshold_target from model_info thresholds.
  10. Build safe external_report output.

No Aramina package dependency. No HTTP. No provider URL.
lr1_model and final_model are sklearn estimators serialized via joblib.

PR0137 — remove fake PR0136 features, implement real Aramina scoring.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from typing import Any

import numpy as np
import pandas as pd

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

# Allowlisted preprocessing release tags (never arbitrary artifact values).
_ALLOWED_PREPROCESSING_RELEASES = frozenset({"v0.1.7-beta", "v0.1.9-beta"})


_TRACE_LABELS = frozenset(_FINAL_FEATURE_COLUMNS) | {
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


def _debug_checkpoint(stage: str, *, _failure: bool = False, **fields: Any) -> None:  # noqa: D401
    """Private diagnostics: opt-in checkpoints and always-on failure stages.

    Only fixed metadata labels and numeric shapes/counts survive. Unknown
    artifact keys, columns, class names, and sides are redacted. Nothing is
    attached to public events, reports, or API responses.
    """
    if stage not in _TRACE_STAGES:
        return
    if not _failure and os.environ.get("BREMEN_ARAMINA_DEBUG_TRACE") != "1":
        return
    try:
        safe = {}
        for key, value in fields.items():
            if value is None or type(value) in (bool, int):
                safe[key] = value
            elif isinstance(value, str):
                safe[key] = value if value in _TRACE_LABELS | _TRACE_STAGES else "redacted"
            elif isinstance(value, (list, tuple)):
                safe[key] = [
                    item if type(item) is int or (
                        isinstance(item, str) and item in _TRACE_LABELS
                    ) else "redacted" for item in value
                ]
        logging.getLogger(__name__).warning(
            "%s %s", "aramina.runtime.rejected" if _failure else "aramina.debug_trace",
            json.dumps({"stage": stage, **safe}),
        )
    except Exception:  # noqa: BLE001, S110 -- logging failures must not affect inference
        # Diagnostics must never change inference or public failure behavior.
        pass


@contextmanager
def _debug_stage(stage: str, group: str = "execution"):
    """Record the original exception class before public error translation.

    PR0141: an inner boundary may already have translated the failure into an
    ``AraminaWorkflowError``. In that case the original exception class is
    carried on the error so the private trace still names the real cause
    instead of the translation wrapper.
    """
    try:
        yield
    except Exception as exc:
        name = type(exc).__name__
        if isinstance(exc, AraminaWorkflowError):
            # Prefer the original cause. When the cause class is unknown or
            # unsafe, report a fixed label rather than the translation
            # wrapper name, which would misattribute the failure.
            name = exc.original_exception_class or "redacted"
        if name not in _TRACE_LABELS:
            name = "redacted"
        _debug_checkpoint(stage, **{
            f"{group}_exception_class": name,
            f"{group}_exception_stage": stage,
        })
        _debug_checkpoint(stage, _failure=True, **{
            f"{group}_exception_class": name,
            f"{group}_exception_stage": stage,
        })
        # Stage comes from a fixed call-site literal, not exception contents.
        raise


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
    return release if release in _ALLOWED_PREPROCESSING_RELEASES else ""


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
# Artifact loading with compatibility bridge (PR0137)
# ---------------------------------------------------------------------------


def _load_selected_artifact(entry: RegistryModelEntry) -> dict[str, Any]:
    """Verify checksum, install compatibility bridge, then deserialize.

    The compatibility bridge registers minimal pickle stubs for
    Aramina training classes before the artifact is deserialized. This
    allows the real artifact to be deserialized without an external
    Aramina package dependency.
    """
    if entry.artifact_type != ARTIFACT_TYPE or not entry._artifact_path:
        _reject_artifact("entry_contract", entry.artifact_type)

    # Install compatibility bridge before deserialization
    from .aramina_artifact_compat import ensure_compatibility_bridge
    with _debug_stage("compatibility_bridge"):
        ensure_compatibility_bridge()
    _debug_checkpoint("compatibility_bridge", compatibility_bridge_status="success")

    from .s3_model_discovery import _load_staged_artifact
    try:
        package = _load_staged_artifact(entry._artifact_path, entry._checksum)
    except ValueError:
        raise AraminaWorkflowError("ARAMINA_ARTIFACT_INTEGRITY_FAILED") from None
    except Exception as exc:
        _debug_checkpoint("joblib_load", joblib_load_status="failed", execution_exception_class=type(exc).__name__)
        raise AraminaWorkflowError("ARAMINA_UNSUPPORTED_ARTIFACT") from None
    _debug_checkpoint("joblib_load", joblib_load_status="success", artifact_loaded=True)
    return _validate_artifact(package, entry)


# ---------------------------------------------------------------------------
# Real artifact contract validation (PR0136/PR0137)
# ---------------------------------------------------------------------------


def _reject_artifact(check: str, value: Any, missing_keys: list[str] | None = None) -> None:
    _debug_checkpoint("artifact_validation", artifact_validated=False, validation_check=check,
                      actual_type=type(value).__name__, missing_keys=missing_keys)
    raise AraminaWorkflowError("ARAMINA_UNSUPPORTED_ARTIFACT")


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

    # 1. Must be dict-like
    if not isinstance(package, dict):
        _reject_artifact("package_type", package)

    _debug_checkpoint("artifact_validation", artifact_top_level_keys=list(package),
                      kind=package.get("kind"), version=package.get("version"))
    # 2. Must be real Aramina training artifact
    if package.get("kind") != _ARTIFACT_KIND:
        _reject_artifact("artifact_kind", package.get("kind"))

    # 3. models must be a dict with exactly one model
    models = package.get("models")
    if not isinstance(models, dict) or len(models) != 1:
        _reject_artifact("single_model", models)

    _debug_checkpoint("artifact_validation", models_keys=list(models))
    selected_model_name = next(iter(models))
    model_info = models[selected_model_name]
    if not isinstance(model_info, dict):
        _reject_artifact("model_info_type", model_info)

    # 4. model_identity must have name and version
    model_identity = package.get("model_identity")
    if not isinstance(model_identity, dict):
        _reject_artifact("identity_type", model_identity)
    if not model_identity.get("name") or not model_identity.get("version"):
        _reject_artifact("identity_fields", model_identity)

    _debug_checkpoint("artifact_validation", model_identity=[model_identity["name"], model_identity["version"]])
    # 5-6. preprocessing and contract YAMLs
    if not isinstance(package.get("prediction_preprocessing_yaml"), str) or \
            not package["prediction_preprocessing_yaml"].strip():
        _reject_artifact("preprocessing_yaml", package.get("prediction_preprocessing_yaml"))
    if not isinstance(package.get("prediction_contract_yaml"), str) or \
            not package["prediction_contract_yaml"].strip():
        _reject_artifact("contract_yaml", package.get("prediction_contract_yaml"))

    # 7. model_info required runtime pieces
    required_model_keys = {
        "lr1_model", "final_model", "thresholds",
        "feature_columns", "class_definition",
    }
    if not required_model_keys.issubset(model_info.keys()):
        _reject_artifact("required_model_keys", model_info, sorted(required_model_keys - model_info.keys()))

    # 8. lr1_model and final_model must support predict_proba
    lr1_model = model_info["lr1_model"]
    final_model = model_info["final_model"]
    if not callable(getattr(lr1_model, "predict_proba", None)):
        _reject_artifact("lr1_predict_method", lr1_model)
    if not callable(getattr(final_model, "predict_proba", None)):
        _reject_artifact("final_predict_method", final_model)

    # 9. thresholds must be a dict
    thresholds = model_info.get("thresholds")
    if not isinstance(thresholds, dict):
        _reject_artifact("threshold_type", thresholds)

    # Validate model identity version against registry
    entry_version = entry.model_version
    if entry_version and entry_version != "unknown":
        artifact_version = model_identity["version"]
        if artifact_version != entry_version:
            _debug_checkpoint("artifact_validation", validation_check="model_version_match", artifact_validated=False)
            raise AraminaWorkflowError("ARAMINA_MODEL_IDENTITY_MISMATCH")

    _debug_checkpoint("artifact_validation", artifact_validated=True)
    return package


# ---------------------------------------------------------------------------
# Profile matrix construction from H5 canonical measurements
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


def _build_profile_matrix(measurements: list) -> np.ndarray:
    """Build a profile matrix from a list of canonical measurements.

    Each preprocessed measurement's intensity array becomes one matrix row.
    Stacking enforces equal row lengths; all values must be finite.
    Returns shape (n_measurements, n_points).
    """
    if not measurements:
        raise ValueError("No measurements to build profile matrix")

    rows = []
    for m in measurements:
        intensity = np.asarray(m.intensity, dtype=float)
        # PR0141: an empty profile is not a usable matrix row. Without this
        # check it would silently become a (n, 0) matrix and fail later in
        # LR1, misattributing a profile-matrix failure to the scorer.
        if intensity.ndim != 1 or intensity.size == 0:
            raise ValueError("Empty intensity in measurement")
        if not np.isfinite(intensity).all():
            raise ValueError("Non-finite intensity in measurement")
        rows.append(intensity)

    matrix = np.vstack(rows)
    return matrix


def _prepare_features(
    package: dict[str, Any],
    canonical: CanonicalXRDCase,
    request_json: dict[str, str],
    h5_path: str,
) -> dict[str, Any]:
    """Validate the case, then execute the artifact-owned raw H5 preprocessing.

    Return the target profile matrix, patient measurement DataFrame, selected
    model information, and measured age/availability for final features.

    PR0141: each fixed boundary raises ARAMINA_UNSUPPORTED_INPUT with an
    allowlisted ``stage`` so the public failure is explainable. No exception
    text, path, or measurement data is attached.
    """
    try:
        _debug_checkpoint(
            "canonical_validation", canonical_measurement_count=len(canonical.measurements),
            target_side=request_json["target_side"],
        )
        with _debug_stage("canonical_validation"):
            validate_canonical_case(canonical)
        from .workflow_orchestrator import _validate_aramina_source
        with _debug_stage("source_validation"):
            try:
                _validate_aramina_source(h5_path, canonical, request_json["patient_id"])
            except Exception as exc:  # noqa: BLE001 -- boundary translation only
                # The staged H5 does not belong to the requested patient, or
                # its bytes changed after normalization. Both are H5 patient
                # contract failures, not generic input failures.
                raise AraminaWorkflowError(
                    "ARAMINA_UNSUPPORTED_INPUT", "h5_patient_contract",
                    type(exc).__name__,
                ) from None

        models = package["models"]
        selected_model_name = next(iter(models))
        model_info = models[selected_model_name]

        target_side = request_json["target_side"]
        target_measurements = _select_measurements(canonical, target_side)
        _debug_checkpoint(
            "target_selection", canonical_measurement_count=len(canonical.measurements),
            target_side=target_side, target_measurement_count=len(target_measurements),
            target_profile_lengths=[len(m.intensity) for m in target_measurements],
        )
        with _debug_stage("target_selection"):
            if not target_measurements:
                raise AraminaWorkflowError(
                    "ARAMINA_UNSUPPORTED_INPUT", "target_side_contract",
                )

        # Check QC flags on target measurements
        with _debug_stage("target_qc"):
            for m in target_measurements:
                if m.qc_flags:
                    raise AraminaWorkflowError(
                        "ARAMINA_UNSUPPORTED_INPUT", "target_side_contract",
                    )

        from types import SimpleNamespace

        from .aramina_preprocessing import AraminaPreprocessingError, preprocess_aramina

        with _debug_stage("artifact_preprocessing", "lr1"):
            try:
                frame = preprocess_aramina(
                    h5_path, package["prediction_preprocessing_yaml"],
                )
            except AraminaPreprocessingError as exc:
                # PR0142: carry the allowlisted worker subdiagnostic so the
                # public failure names the exact preprocessing stage.
                raise AraminaWorkflowError(
                    "ARAMINA_UNSUPPORTED_INPUT", "preprocessing_contract",
                    type(exc).__name__, exc.diagnostic,
                ) from None
            except Exception as exc:  # noqa: BLE001 -- boundary translation only
                raise AraminaWorkflowError(
                    "ARAMINA_UNSUPPORTED_INPUT", "preprocessing_contract",
                    type(exc).__name__,
                ) from None
            # A job is bound to exactly one requested patient; never mix rows.
            if set(frame["patientId"].astype(str)) != {request_json["patient_id"]}:
                raise AraminaWorkflowError(
                    "ARAMINA_UNSUPPORTED_INPUT", "h5_patient_contract",
                )
            sides = frame["side"].astype(str).str.strip().str.lower()
            target_frame = frame.loc[sides == target_side]
            if target_frame.empty:
                raise AraminaWorkflowError(
                    "ARAMINA_UNSUPPORTED_INPUT", "target_side_contract",
                )
            measurements = [SimpleNamespace(intensity=row) for row in target_frame["radial_profile_data"]]
        with _debug_stage("profile_matrix", "lr1"):
            try:
                profile_matrix = _build_profile_matrix(measurements)
            except Exception as exc:  # noqa: BLE001 -- boundary translation only
                raise AraminaWorkflowError(
                    "ARAMINA_UNSUPPORTED_INPUT", "profile_matrix_contract",
                    type(exc).__name__,
                ) from None
        _debug_checkpoint("profile_matrix", target_measurement_count=len(measurements),
                          target_profile_lengths=[len(m.intensity) for m in measurements])
        ages = pd.to_numeric(frame.get("age", pd.Series(dtype=float)), errors="coerce")
        return {
            "profile_matrix": profile_matrix, "dataframe": frame,
            "model_info": model_info,
            "age": float(ages.median()) if ages.notna().any() else 0.0,
            "age_available": float(ages.notna().any()),
        }

    except AraminaWorkflowError:
        raise
    except Exception:
        raise AraminaWorkflowError(
            "ARAMINA_UNSUPPORTED_INPUT", "unknown_input_contract",
        ) from None


# ---------------------------------------------------------------------------
# Real Aramina scoring pipeline (PR0137)
# ---------------------------------------------------------------------------


def _run_local_artifact(
    entry: RegistryModelEntry,
    canonical: CanonicalXRDCase,
    request_json: dict[str, str],
    h5_path: str,
) -> dict[str, Any]:
    """Execute the real Aramina training artifact scoring pipeline.

    1. Load and validate artifact (with compatibility bridge).
    2. Preprocess raw H5 using the artifact pipeline and build profile_matrix.
    3. Score target-side measurements with lr1_model using profile_matrix.
    4. Aggregate LR1 logit averages.
    5. Compute symmetry features from target/contralateral.
    6. Build pandas DataFrame with model_info["feature_columns"].
    7. Run final_model.predict_proba on DataFrame.
    8. Apply threshold.
    9. Build safe output.
    """
    _debug_checkpoint(
        "artifact_load", artifact_loaded=False, artifact_validated=False, lr1_input_shape=None,
        lr1_exception_class=None, lr1_exception_stage=None,
        final_feature_columns=None, final_input_shape=None,
        final_exception_class=None, final_exception_stage=None,
        report_build_exception_class=None, report_build_exception_stage=None,
    )
    with _debug_stage("artifact_load"):
        package = _load_selected_artifact(entry)
    if os.environ.get("BREMEN_ARAMINA_DEBUG_TRACE") == "1":
        info = next(iter(package["models"].values()))
        _debug_checkpoint(
            "artifact_loaded", artifact_loaded=True,
            selected_model_info_keys=list(info),
            lr1_model_type=type(info["lr1_model"]).__name__,
            lr1_expected_feature_count=getattr(info["lr1_model"], "n_features_in_", None),
            final_model_type=type(info["final_model"]).__name__,
            feature_columns=info.get("feature_columns"),
            threshold_keys=list(info["thresholds"]),
        )
    features_data = _prepare_features(package, canonical, request_json, h5_path)

    model_info = features_data["model_info"]
    lr1_model = model_info["lr1_model"]
    final_model = model_info["final_model"]
    thresholds = model_info["thresholds"]

    try:
        # Step 1: Score each target measurement with lr1_model using profile_matrix
        profile_matrix = features_data["profile_matrix"]
        lr1_probabilities = []

        for i in range(profile_matrix.shape[0]):
            profile_row = profile_matrix[i:i+1, :]  # shape (1, n_points)
            _debug_checkpoint("lr1_predict_proba", lr1_input_shape=list(profile_row.shape))
            with _debug_stage("lr1_predict_proba", "lr1"):
                try:
                    probs = np.asarray(lr1_model.predict_proba(profile_row), dtype=float)
                except Exception as exc:  # noqa: BLE001 -- boundary translation only
                    raise AraminaWorkflowError(
                        "ARAMINA_UNSUPPORTED_INPUT", "lr1_contract",
                        type(exc).__name__,
                    ) from None
            with _debug_stage("lr1_output_validation", "lr1"):
                if probs.shape != (1, 2) or not np.isfinite(probs).all():
                    raise AraminaWorkflowError(
                        "ARAMINA_UNSUPPORTED_INPUT", "lr1_contract",
                    )
                if (probs < 0).any() or (probs > 1).any():
                    raise AraminaWorkflowError(
                        "ARAMINA_UNSUPPORTED_INPUT", "lr1_contract",
                    )

            lr1_probabilities.append(probs[0])

        with _debug_stage("lr1_aggregation", "lr1"):
            if not lr1_probabilities:
                raise AraminaWorkflowError(
                    "ARAMINA_UNSUPPORTED_INPUT", "lr1_contract",
                )

            # Step 2: Aggregate by logit average
            lr1_arr = np.array(lr1_probabilities, dtype=float)
            pos_probs = np.clip(lr1_arr[:, 1], 1e-6, 1 - 1e-6)
            logits = np.log(pos_probs / (1 - pos_probs))
            mean_logit_probability = float(1.0 / (1.0 + np.exp(-float(np.mean(logits)))))

        # Step 3: Compute symmetry features
        with _debug_stage("symmetry_features", "execution"):
            from .aramina_symmetry import symmetry_features
            try:
                sym_features = symmetry_features(
                    features_data["dataframe"], request_json["target_side"],
                    model_info.get("symmetry_feature_contract", "aramina_sk_symmetry_v0_1"),
                )
            except Exception as exc:  # noqa: BLE001 -- boundary translation only
                raise AraminaWorkflowError(
                    "ARAMINA_UNSUPPORTED_INPUT", "symmetry_contract",
                    type(exc).__name__,
                ) from None

        # Step 4: Build feature dict with all required columns
        feature_dict = {
            "profile_p_cancer_logit_average": mean_logit_probability,
            "age": features_data["age"],
            "age_available": features_data["age_available"],
            **sym_features,
        }

        # Step 5: Build pandas DataFrame with model_info["feature_columns"]
        with _debug_stage("final_dataframe", "final"):
            feature_columns = model_info.get("feature_columns", [])
            try:
                final_features_df = pd.DataFrame(
                    [{col: feature_dict[col] for col in feature_columns}]
                )
            except Exception as exc:  # noqa: BLE001 -- boundary translation only
                raise AraminaWorkflowError(
                    "ARAMINA_UNSUPPORTED_INPUT", "final_dataframe_contract",
                    type(exc).__name__,
                ) from None

        _debug_checkpoint(
            "final_dataframe", final_feature_columns=list(final_features_df.columns),
            final_input_shape=list(final_features_df.shape),
        )
        # Step 6: Run final_model.predict_proba on DataFrame
        with _debug_stage("final_predict_proba", "final"):
            try:
                final_probs = np.asarray(
                    final_model.predict_proba(final_features_df), dtype=float
                )
            except Exception as exc:  # noqa: BLE001 -- boundary translation only
                raise AraminaWorkflowError(
                    "ARAMINA_UNSUPPORTED_INPUT", "final_model_contract",
                    type(exc).__name__,
                ) from None

        with _debug_stage("final_output_validation", "final"):
            if final_probs.shape != (1, 2) or not np.isfinite(final_probs).all():
                raise AraminaWorkflowError(
                    "ARAMINA_UNSUPPORTED_INPUT", "final_model_contract",
                )
            if (final_probs < 0).any() or (final_probs > 1).any():
                raise AraminaWorkflowError(
                    "ARAMINA_UNSUPPORTED_INPUT", "final_model_contract",
                )

        # Step 7: Apply threshold
        with _debug_stage("threshold", "final"):
            threshold_target = thresholds["threshold_target"]
            risk_probability = float(final_probs[0, 1])
            target_class = 1 if risk_probability >= threshold_target else 0

        # Step 8: Build safe output
        with _debug_stage("report", "report_build"):
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
