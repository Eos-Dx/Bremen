"""Aramina v0.2.13 model inference pipeline — package-owned science (PR0156).

Moved verbatim from ``bremen.api.workflow_aramina`` by PR0156 so the complete
model-specific scientific inference is owned by the Aramina model package, not
by platform orchestration.  Every computation is unchanged from PR0137/PR0153B:
artifact loading with the pickle compatibility bridge, artifact-contract
validation, target-side selection + QC, artifact-owned raw-H5 preprocessing,
profile-matrix construction, LR1 scoring, logit aggregation, symmetry features,
final-model scoring, model-owned threshold and the safe report payload.

The only structural changes (import retargeting; no behavior change):
- the pickle bridge / preprocessing / symmetry live in this package;
- artifact contract constants and the failure vocabulary come from
  ``manifest``/``errors``;
- private diagnostics come from ``trace``;
- the controlled joblib loader comes from the narrow platform bridge
  ``bremen.model_packages_bridge.load_staged_artifact`` (error contract
  preserved);
- Source integrity and patient binding are performed by the platform provider
  before package invocation (PR0160); no package-to-API dependency remains.

No HTTP, no FastAPI, no auth, no job objects, no report providers, no S3
credentials, no frontend.  Research decision support requiring radiologist
review.
"""
from __future__ import annotations

import os
from typing import Any

import numpy as np
import pandas as pd

from bremen.canonical_input import CanonicalXRDCase, validate_canonical_case
from bremen.model_packages.aramina_v0213 import manifest
from bremen.model_packages.aramina_v0213.errors import AraminaWorkflowError
from bremen.model_packages.aramina_v0213.trace import _debug_checkpoint, _debug_stage
from bremen.model_packages_bridge import load_staged_artifact as _load_staged_artifact

# Contract identifiers from the manifest (names preserved for verbatim bodies).
ARTIFACT_TYPE = manifest.ARTIFACT_TYPE
_ARTIFACT_KIND = manifest.ARTIFACT_KIND
_DEFAULT_AUTHOR = manifest.DEFAULT_AUTHOR


# ---- moved verbatim from bremen.api.workflow_aramina ----
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


def _load_selected_artifact(entry: Any) -> dict[str, Any]:
    """Verify checksum, install compatibility bridge, then deserialize.

    The compatibility bridge registers minimal pickle stubs for
    Aramina training classes before the artifact is deserialized. This
    allows the real artifact to be deserialized without an external
    Aramina package dependency.
    """
    if entry.artifact_type != ARTIFACT_TYPE or not entry._artifact_path:
        _reject_artifact("entry_contract", entry.artifact_type)

    # Install compatibility bridge before deserialization
    from bremen.model_packages.aramina_v0213.artifact_compat import (
        ensure_compatibility_bridge as _ensure_bridge,
    )
    with _debug_stage("compatibility_bridge"):
        _ensure_bridge()
    _debug_checkpoint("compatibility_bridge", compatibility_bridge_status="success")

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


def _validate_artifact(package: Any, entry: Any) -> dict[str, Any]:
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

        from bremen.model_packages.aramina_v0213.preprocessing import (
            AraminaPreprocessingError, preprocess_aramina,
        )

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
    entry: Any,
    canonical: CanonicalXRDCase,
    request_json: dict[str, str],
    h5_path: str,
) -> tuple[dict[str, Any], Any, Any, Any]:
    """Execute the real Aramina training artifact scoring pipeline.

    1. Load and validate artifact (with compatibility bridge).
    2. Preprocess raw H5 using the artifact pipeline and build profile_matrix.
    3. Score target-side measurements with lr1_model using profile_matrix.
    4. Aggregate LR1 logit averages.
    5. Compute symmetry features from target/contralateral.
    6. Build pandas DataFrame with model_info["feature_columns"].
    7. Run final_model.predict_proba on DataFrame.
    8. Apply threshold.
    9. Build safe model-native report.

    Returns ``(report, source_metadata, model_metadata, model_metrics)`` where
    the last three are the model package's own normalized metadata contract
    (PR0159) — the model-native ``report`` dict is unchanged.
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
            from bremen.model_packages.aramina_v0213.symmetry import symmetry_features
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
            report = {
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
            # PR0159: the normalized metadata contract is produced by this
            # model package's own adapter (container + artifact interpretation)
            # and transported alongside the model-native report so the runtime
            # can attach it to the ModelRuntime result.  The model-native
            # report itself stays unchanged.  The frame age is the model's own
            # preprocessing output; it is only used when the frame genuinely
            # provides one (``age_available``), otherwise the container
            # attribute is the fallback.
            from . import source_metadata as _source_metadata  # noqa: PLC0415

            frame_age = features_data.get("age")
            if not features_data.get("age_available"):
                frame_age = None
            source_metadata = _source_metadata.extract_source_metadata(
                h5_path, frame_age=frame_age,
            )
            model_metadata = _source_metadata.extract_model_metadata(package)
            model_metrics = _source_metadata.extract_model_metrics(package)
            return report, source_metadata, model_metadata, model_metrics

    except AraminaWorkflowError:
        raise
    except Exception:
        raise AraminaWorkflowError("ARAMINA_EXECUTION_FAILED") from None

