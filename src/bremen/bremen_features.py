"""DEPRECATED compatibility shim — Bremen v0.1 feature science (PR0154).

The authoritative implementation moved to the inference-complete Bremen model
package: ``bremen.model_packages.bremen_v01.features``.

This module re-exports the identical objects (zero logic) so historical import
paths keep resolving for external callers and test fixtures during the
transition.  New code must import from the package.

There is exactly ONE active scientific implementation — the package module.
"""
from __future__ import annotations

from bremen.model_packages.bremen_v01.features import (
    AnalysisConfig,
    FEATURE_COLS,
    LEFT_VALUES,
    RIGHT_VALUES,
    BremenFeatureError,
    apply_roi,
    build_bremen_features,
    build_common_grid,
    cosine_distance,
    local_peak_in_window,
    mahalanobis_band,
    mask_q,
    mean_rms_band,
    minimum_reference_value,
    normalize_by_minimum,
    parse_q_grid,
    patient_lr_mean_metrics,
    patient_mean_raw_peak14,
    peak14_intensity_from_means,
    resample_to_common,
    safe_savgol,
    side_label,
    sigma_rms_band,
    validate_bremen_shape,
    wasserstein_distance,
    weighted_rms_band,
)

__all__ = [
    "AnalysisConfig",
    "FEATURE_COLS",
    "LEFT_VALUES",
    "RIGHT_VALUES",
    "BremenFeatureError",
    "apply_roi",
    "build_bremen_features",
    "build_common_grid",
    "cosine_distance",
    "local_peak_in_window",
    "mahalanobis_band",
    "mask_q",
    "mean_rms_band",
    "minimum_reference_value",
    "normalize_by_minimum",
    "parse_q_grid",
    "patient_lr_mean_metrics",
    "patient_mean_raw_peak14",
    "peak14_intensity_from_means",
    "resample_to_common",
    "safe_savgol",
    "side_label",
    "sigma_rms_band",
    "validate_bremen_shape",
    "wasserstein_distance",
    "weighted_rms_band",
]
