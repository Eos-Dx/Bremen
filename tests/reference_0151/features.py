"""Frozen 15-feature Bremen patient-level symmetry contract."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import pandas as pd

from . import reference_features as symmetry


FEATURE_COLUMNS = list(symmetry.FEATURE_COLS)
FEATURE_CONTRACT_VERSION = "bremen_h5_15feature_v0_2"


def analysis_config() -> symmetry.AnalysisConfig:
    """Return the fixed feature settings inherited from the H5 reference."""
    return symmetry.AnalysisConfig(
        q_roi=(7.5, 23.0),
        zones=((7.0, 15.0), (15.0, 23.0)),
        smooth=True,
        sg_window=11,
        sg_poly=3,
        min_q0=6.7,
        min_halfwidth=0.25,
        min_mode="p05",
        peak_center=14.0,
        peak_halfwidth=0.5,
        peak_mode="max",
        raw_peak_min=13.0,
        raw_peak_max=14.8,
        raw_peak_threshold=0.6,
        cosine_q_roi=(2.0, 23.0),
        excluded_patients=(),
        random_state=0,
        cv_splits=5,
    )


def feature_contract() -> dict[str, Any]:
    config = analysis_config()
    return {
        "name": FEATURE_CONTRACT_VERSION,
        "feature_columns": FEATURE_COLUMNS,
        "analysis_config": asdict(config),
        "source_reference": "bremen_h5_15feature_model",
        "patient_specific_exclusions": [],
        "raw_peak_gate": {
            "column": "mean_peak_value_raw",
            "op": ">=",
            "value": float(config.raw_peak_threshold),
        },
    }


def prepare_profile_dataframe(profile_df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize column names without reading diagnosis labels."""
    prepared = symmetry.prepare_one_to_one_dataframe(profile_df)
    return prepared


def build_feature_frame(
    profile_df: pd.DataFrame,
    *,
    patient_id: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build one unlabeled 15-feature row per paired-breast patient."""
    config = analysis_config()
    prepared = prepare_profile_dataframe(profile_df)
    if patient_id is not None:
        prepared = prepared[
            prepared["patient_id"].astype(str).eq(str(patient_id))
        ].copy()

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    zone1, zone2 = config.zones

    for current_patient_id in sorted(prepared["patient_id"].dropna().unique()):
        try:
            metrics = symmetry.patient_lr_mean_metrics(
                prepared,
                current_patient_id,
                config,
                q_roi=config.q_roi,
            )
            q = metrics["q_common"]
            mu_left = metrics["mu_left"]
            mu_right = metrics["mu_right"]
            std_left = metrics["std_left"]
            std_right = metrics["std_right"]
            mask1 = symmetry.mask_q(q, *zone1)
            mask2 = symmetry.mask_q(q, *zone2)
            wrms1, chi2_1, sum_w1 = symmetry.weighted_rms_band(
                mu_left, mu_right, std_left, std_right, mask1
            )
            mah1, mah1_red, dof1 = symmetry.mahalanobis_band(
                mu_left, mu_right, std_left, std_right, mask1
            )
            wrms2, chi2_2, sum_w2 = symmetry.weighted_rms_band(
                mu_left, mu_right, std_left, std_right, mask2
            )
            mah2, mah2_red, dof2 = symmetry.mahalanobis_band(
                mu_left, mu_right, std_left, std_right, mask2
            )
            metrics_wide = symmetry.patient_lr_mean_metrics(
                prepared,
                current_patient_id,
                config,
                q_roi=config.cosine_q_roi,
            )
            rows.append(
                {
                    "patient_id": str(current_patient_id),
                    "meanrms1": symmetry.mean_rms_band(mu_left, mu_right, mask1),
                    "meanrms2": symmetry.mean_rms_band(mu_left, mu_right, mask2),
                    "weightedrms1": wrms1,
                    "sigma_l1": symmetry.sigma_rms_band(std_left, mask1),
                    "sigma_r1": symmetry.sigma_rms_band(std_right, mask1),
                    "mahalanobis1": mah1,
                    "mahalanobis1_red": mah1_red,
                    "chi2_1": chi2_1,
                    "sum_w1": sum_w1,
                    "dof1": dof1,
                    "weightedrms2": wrms2,
                    "sigma_l2": symmetry.sigma_rms_band(std_left, mask2),
                    "sigma_r2": symmetry.sigma_rms_band(std_right, mask2),
                    "mahalanobis2": mah2,
                    "mahalanobis2_red": mah2_red,
                    "chi2_2": chi2_2,
                    "sum_w2": sum_w2,
                    "dof2": dof2,
                    "peak14_intensity": symmetry.peak14_intensity_from_means(
                        q,
                        mu_left,
                        mu_right,
                        q_center=config.peak_center,
                        halfwidth=config.peak_halfwidth,
                        mode=config.peak_mode,
                    ),
                    "mean_peak_value_raw": symmetry.patient_mean_raw_peak14(
                        prepared, current_patient_id, config
                    ),
                    "wasserstein_distance_muLR": symmetry.wasserstein_distance(
                        q, mu_left, mu_right
                    ),
                    "cosine_distance_full_q2": symmetry.cosine_distance(
                        metrics_wide["mu_left"], metrics_wide["mu_right"]
                    ),
                    "wasserstein_distance_full_q2": symmetry.wasserstein_distance(
                        metrics_wide["q_common"],
                        metrics_wide["mu_left"],
                        metrics_wide["mu_right"],
                    ),
                    "n_left": metrics["n_left"],
                    "n_right": metrics["n_right"],
                    "n_q": metrics["n_q"],
                }
            )
        except Exception as exc:
            errors.append(
                {
                    "patient_id": str(current_patient_id),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    feature_frame = pd.DataFrame(rows)
    if not feature_frame.empty:
        feature_frame["feature_gate_pass"] = feature_frame[
            "mean_peak_value_raw"
        ].ge(config.raw_peak_threshold)
    error_frame = pd.DataFrame(
        errors,
        columns=["patient_id", "error_type", "error"],
    )
    return feature_frame, error_frame


def accepted_features(feature_frame: pd.DataFrame) -> pd.DataFrame:
    """Apply the frozen patient-level feature gate."""
    if feature_frame.empty:
        return feature_frame.copy()
    return feature_frame.loc[feature_frame["feature_gate_pass"]].reset_index(drop=True)
