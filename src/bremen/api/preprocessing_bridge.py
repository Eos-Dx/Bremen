"""Preprocessing bridge — converts validated H5 input to Bremen 7-feature vector.

This module lives under ``src/bremen/api/`` and must NOT import from
``src/bremen/training/``.  Feature computation functions are duplicated
here to maintain the runtime/training separation boundary.

PR 0038 stops at feature table creation and schema validation.
No model loading, no inference, no prediction route wiring.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import h5py
import numpy as np

from .preflight import PreflightResult, run_h5_preflight


# ---------------------------------------------------------------------------
# Feature schema constants
# ---------------------------------------------------------------------------

BREMEN_FEATURE_COLUMNS: tuple[str, ...] = (
    "sigma_l1",
    "sigma_l2",
    "Mahalanobis1",
    "Mahalanobis2",
    "wasserstein_distance_full_q2",
    "meanrms2",
    "weightedrms1",
)

FEATURE_SCHEMA_VERSION: str = "v0.1"

_EXPECTED_FEATURE_COUNT = len(BREMEN_FEATURE_COLUMNS)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class BremenFeatureVector:
    """Ordered feature vector with schema metadata.

    Does NOT include raw scan data.
    """

    features: list[float]
    feature_names: list[str]
    feature_schema_version: str
    patient_id: str | None
    target_side: str | None
    contralateral_side: str | None


@dataclass
class PreprocessingBridgeResult:
    """Result of the preprocessing bridge."""

    passed: bool
    feature_vector: BremenFeatureVector | None
    warnings: list[str]
    qc_flags: list[str]
    preflight_summary: dict[str, Any]


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class PreprocessingBridgeError(Exception):
    """Base exception for preprocessing bridge errors."""


class PreflightNotPassedError(PreprocessingBridgeError):
    """Preflight must pass before the bridge can run."""


class FeatureSchemaMismatchError(PreprocessingBridgeError):
    """Feature schema does not match expected columns or order."""


# ---------------------------------------------------------------------------
# Core public functions
# ---------------------------------------------------------------------------


def run_preprocessing_bridge(
    h5_path: str | Path,
    *,
    preflight_result: PreflightResult | None = None,
    skip_preflight: bool = False,
) -> PreprocessingBridgeResult:
    """Run the preprocessing bridge on a validated H5 container.

    Parameters
    ----------
    h5_path : Path to the H5 container.
    preflight_result : Optional already-computed ``PreflightResult``.
        If provided and ``passed`` is ``True``, the bridge proceeds.
        If not provided and ``skip_preflight`` is ``False``, the bridge
        calls ``run_h5_preflight()`` first.
    skip_preflight : If ``True``, skip preflight check (for testing).

    Returns
    -------
    A ``PreprocessingBridgeResult`` with the extracted feature vector.

    Raises
    ------
    PreflightNotPassedError
        If preflight was not passed.
    PreprocessingBridgeError
        On extraction or schema validation failure.
    """
    warnings: list[str] = []
    qc_flags: list[str] = []

    # Preflight gate
    if not skip_preflight:
        if preflight_result is not None:
            if not preflight_result.passed:
                raise PreflightNotPassedError(
                    "Preflight did not pass. Cannot run preprocessing bridge."
                )
        else:
            preflight_result = run_h5_preflight(h5_path)
            if not preflight_result.passed:
                raise PreflightNotPassedError(
                    f"Preflight did not pass (status={preflight_result.status}). "
                    "Cannot run preprocessing bridge."
                )
        preflight_summary = {
            "patient_id": preflight_result.patient_id,
            "target_side": preflight_result.target_side,
            "contralateral_side": preflight_result.contralateral_side,
            "passed": preflight_result.passed,
            "status": preflight_result.status,
        }
    else:
        preflight_summary = {"skipped": True}

    # Open H5 and extract
    try:
        feature_dict = build_feature_table(h5_path)
    except Exception as exc:
        raise PreprocessingBridgeError(
            f"Feature extraction failed: {exc}"
        ) from exc

    # Build feature vector
    feature_values: list[float] = []
    for col in BREMEN_FEATURE_COLUMNS:
        val = feature_dict.get(col)
        if val is None or not np.isfinite(val):
            raise PreprocessingBridgeError(
                f"Feature '{col}' is missing or non-finite: {val!r}"
            )
        feature_values.append(float(val))

    feature_vector = BremenFeatureVector(
        features=feature_values,
        feature_names=list(BREMEN_FEATURE_COLUMNS),
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        patient_id=(
            preflight_result.patient_id if preflight_result is not None else None
        ),
        target_side=(
            preflight_result.target_side if preflight_result is not None else None
        ),
        contralateral_side=(
            preflight_result.contralateral_side
            if preflight_result is not None
            else None
        ),
    )

    return PreprocessingBridgeResult(
        passed=True,
        feature_vector=feature_vector,
        warnings=warnings,
        qc_flags=qc_flags,
        preflight_summary=preflight_summary,
    )


def build_feature_table(h5_path: str | Path) -> dict[str, float]:
    """Extract the 7-feature vector from an H5 container.

    Reads target and contralateral profiles from H5.
    Computes per-patient symmetry measures for all 7 feature families.

    Parameters
    ----------
    h5_path : Path to the H5 container.

    Returns
    -------
    A dict mapping feature names to finite float values.
    """
    with h5py.File(h5_path, "r") as f:
        target_profiles = _extract_profiles(f, "target")
        contralateral_profiles = _extract_profiles(f, "contralateral")

    if not target_profiles or not contralateral_profiles:
        raise PreprocessingBridgeError(
            "Cannot compute features: missing profiles"
        )

    t_mean = np.mean(np.array(target_profiles), axis=0)
    c_mean = np.mean(np.array(contralateral_profiles), axis=0)

    sigma_l1, sigma_l2 = _sigma_rms(t_mean, c_mean)
    m1, m2 = _mahalanobis_difference(t_mean, c_mean)
    wass = _profile_wasserstein(t_mean, c_mean)
    rms = _rms_difference(t_mean, c_mean)
    wrms = _weighted_rms_difference(t_mean, c_mean)

    return {
        "sigma_l1": float(sigma_l1),
        "sigma_l2": float(sigma_l2),
        "Mahalanobis1": float(m1),
        "Mahalanobis2": float(m2),
        "wasserstein_distance_full_q2": float(wass),
        "meanrms2": float(rms),
        "weightedrms1": float(wrms),
    }


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def validate_feature_schema(
    feature_vector: BremenFeatureVector,
    *,
    expected_version: str | None = "v0.1",
) -> None:
    """Validate feature vector against schema expectations.

    Checks:
    - Feature count matches ``BREMEN_FEATURE_COLUMNS``.
    - Feature names match exact order.
    - Feature schema version matches (if provided).
    - All values are finite (not NaN, not Inf).

    Raises ``FeatureSchemaMismatchError`` on any mismatch.
    """
    # Count
    if len(feature_vector.features) != _EXPECTED_FEATURE_COUNT:
        raise FeatureSchemaMismatchError(
            f"Expected {_EXPECTED_FEATURE_COUNT} features, "
            f"got {len(feature_vector.features)}"
        )

    # Names and order
    actual_names = feature_vector.feature_names
    if len(actual_names) != _EXPECTED_FEATURE_COUNT:
        raise FeatureSchemaMismatchError(
            f"Expected {_EXPECTED_FEATURE_COUNT} feature names, "
            f"got {len(actual_names)}"
        )

    for i, (expected, actual) in enumerate(zip(BREMEN_FEATURE_COLUMNS, actual_names)):
        if expected != actual:
            raise FeatureSchemaMismatchError(
                f"Feature name mismatch at index {i}: "
                f"expected {expected!r}, got {actual!r}"
            )

    # Version
    if expected_version is not None:
        if feature_vector.feature_schema_version != expected_version:
            raise FeatureSchemaMismatchError(
                f"Expected feature schema version {expected_version!r}, "
                f"got {feature_vector.feature_schema_version!r}"
            )

    # Finiteness
    for i, val in enumerate(feature_vector.features):
        if not np.isfinite(val):
            raise FeatureSchemaMismatchError(
                f"Feature at index {i} "
                f"({feature_vector.feature_names[i]}) "
                f"is not finite: {val}"
            )


def validate_feature_values(
    feature_vector: BremenFeatureVector,
) -> list[str]:
    """Validate feature values are finite.

    Does NOT raise on non-finite values — returns warnings.
    """
    warnings: list[str] = []
    for i, val in enumerate(feature_vector.features):
        if not np.isfinite(val):
            warnings.append(
                f"Feature at index {i} "
                f"({feature_vector.feature_names[i]}) "
                f"is not finite: {val}"
            )
    return warnings


# ---------------------------------------------------------------------------
# Private feature computation helpers
#
# These are duplicated from the training pipeline to maintain the
# runtime/training separation boundary (ADR-0008).  They are pure
# deterministic numpy math — no model state, no training data.
# A future PR may extract a shared runtime-safe feature module.
# ---------------------------------------------------------------------------


def _extract_profiles(
    h5_file: h5py.File, scan_label: str
) -> list[np.ndarray]:
    """Extract profile arrays from an H5 scan group.

    Profiles are stored as rows of a 2D array at
    ``/scans/{scan_label}/measurements``.
    """
    measurements = h5_file[f"/scans/{scan_label}/measurements"][:]
    if measurements.ndim == 1:
        return [np.asarray(measurements, dtype=np.float64)]
    return [
        np.asarray(measurements[i], dtype=np.float64)
        for i in range(measurements.shape[0])
    ]


def _mahalanobis_difference(
    target_profile: np.ndarray,
    contralateral_profile: np.ndarray,
) -> tuple[float, float]:
    """Per-patient Mahalanobis1 and Mahalanobis2.

    Mahalanobis1: normalised by per-element variance estimate.
    Mahalanobis2: normalised by standard deviation with dampening.
    """
    diff = target_profile - contralateral_profile
    var = np.var(np.stack([target_profile, contralateral_profile]), axis=0)
    var_damped = var + 1e-10

    m1 = float(np.sqrt(np.mean(diff**2 / var_damped)))
    std_damped = np.sqrt(var_damped)
    m2 = float(np.mean(np.abs(diff) / (std_damped + 1e-10)))
    return m1, m2


def _profile_wasserstein(
    target_profile: np.ndarray,
    contralateral_profile: np.ndarray,
) -> float:
    """Wasserstein-1 distance for wasserstein_distance_full_q2."""
    t = target_profile / (np.sum(np.abs(target_profile)) + 1e-10)
    c = contralateral_profile / (np.sum(np.abs(contralateral_profile)) + 1e-10)
    t_sorted = np.sort(t)
    c_sorted = np.sort(c)
    return float(np.mean(np.abs(np.cumsum(t_sorted) - np.cumsum(c_sorted))))


def _rms_difference(
    target_profile: np.ndarray,
    contralateral_profile: np.ndarray,
) -> float:
    """Root-mean-square asymmetry (meanrms2)."""
    diff = target_profile - contralateral_profile
    return float(np.sqrt(np.mean(diff**2)))


def _weighted_rms_difference(
    target_profile: np.ndarray,
    contralateral_profile: np.ndarray,
) -> float:
    """Weighted RMS asymmetry (weightedrms1)."""
    diff = target_profile - contralateral_profile
    weights = (np.abs(target_profile) + np.abs(contralateral_profile)) / 2
    weights = weights / (np.sum(weights) + 1e-10)
    return float(np.sqrt(np.sum(weights * diff**2)))


def _sigma_rms(
    target_profile: np.ndarray,
    contralateral_profile: np.ndarray,
) -> tuple[float, float]:
    """sigma_l1 and sigma_l2."""
    diff = target_profile - contralateral_profile
    sigma_l1 = float(np.mean(np.abs(diff)))
    sigma_l2 = float(np.sqrt(np.mean(diff**2)))
    return sigma_l1, sigma_l2
