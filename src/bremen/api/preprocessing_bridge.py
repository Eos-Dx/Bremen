"""Preprocessing bridge — converts validated H5 input to Bremen v0.1 15-feature vector.

This module lives under ``src/bremen/api/`` and must NOT import from
``src/bremen/training/``.  Feature computation functions are duplicated
here to maintain the runtime/training separation boundary (ADR-0008).

PR 0039 updates the bridge from a 7-feature assumption to the delivered
v0.1 model's 15-column concrete schema (see ADR-0010).

No model loading, no inference, no prediction route wiring.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import h5py
import numpy as np

from .preflight import PreflightResult, run_h5_preflight

# Import H5PredictionContext for layout-aware extraction
# (cyclic-safe — h5_layouts does not import preprocessing_bridge)
from .h5_layouts import H5PredictionContext


# ---------------------------------------------------------------------------
# Feature schema constants
# ---------------------------------------------------------------------------

# Delivered v0.1 model exact 15-column schema (see ADR-0010).
# Lowercase mahalanobis1/2 — not the uppercase-M naming used in earlier ADRs.
BREMEN_V01_FEATURE_COLUMNS: tuple[str, ...] = (
    "weightedrms1",
    "sigma_l1",
    "sigma_r1",
    "mahalanobis1",
    "weightedrms2",
    "sigma_l2",
    "sigma_r2",
    "mahalanobis2",
    "peak14_intensity",
    "mean_peak_value_raw",
    "wasserstein_distance_muLR",
    "cosine_distance_full_q2",
    "wasserstein_distance_full_q2",
    "meanrms1",
    "meanrms2",
)

# Backward-compatible alias for code that references BREMEN_FEATURE_COLUMNS.
# The 7-feature assumption is superseded by the 15-column v0.1 schema.
BREMEN_FEATURE_COLUMNS: tuple[str, ...] = BREMEN_V01_FEATURE_COLUMNS

FEATURE_SCHEMA_VERSION: str = "v0.1"

_EXPECTED_FEATURE_COUNT = len(BREMEN_V01_FEATURE_COLUMNS)


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
    layout_context: H5PredictionContext | None = None,
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
    layout_context : Optional ``H5PredictionContext`` for layout-aware
        extraction.  When ``layout_context.layout_name == "calibration_sample"``,
        the bridge reads integration i/q arrays from the resolved group paths
        instead of the canonical ``/scans/target/measurements`` paths.
        When ``None`` or ``layout_name == "canonical"``, the canonical path
        is used (backward compatible).
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

    # Determine layout context if not provided but preflight_result has metadata
    resolved_context = layout_context
    if resolved_context is None and preflight_result is not None:
        meta = preflight_result.metadata or {}
        layout_name = meta.get("layout_name")
        if layout_name and layout_name != "canonical":
            # Build a minimal context from PreflightResult metadata for
            # any non-canonical layout (calibration_sample, session_layout, etc.)
            resolved_context = H5PredictionContext(
                layout_name=layout_name,
                target_scan_ref=meta.get("target_scan_ref", ""),
                control_scan_ref=meta.get("control_scan_ref", ""),
                target_group_path=meta.get("target_group_path", ""),
                control_group_path=meta.get("control_group_path", ""),
                target_side=preflight_result.target_side,
                control_side=preflight_result.contralateral_side,
                patient_identifier=preflight_result.patient_id or "",
                patient_identifier_source=preflight_result.patient_identifier_source,
                metadata_fallback_used=preflight_result.metadata_fallback_used,
                target_measurement_count=preflight_result.target_measurement_count,
                control_measurement_count=preflight_result.contralateral_measurement_count,
                adapter_metadata={},
            )

    # Open H5 and extract
    try:
        feature_dict = build_feature_table(h5_path, layout_context=resolved_context)
    except Exception as exc:
        raise PreprocessingBridgeError(
            f"Feature extraction failed: {exc}"
        ) from exc

    # Build feature vector
    feature_values: list[float] = []
    for col in BREMEN_V01_FEATURE_COLUMNS:
        val = feature_dict.get(col)
        if val is None or not np.isfinite(val):
            raise PreprocessingBridgeError(
                f"Feature '{col}' is missing or non-finite: {val!r}"
            )
        feature_values.append(float(val))

    feature_vector = BremenFeatureVector(
        features=feature_values,
        feature_names=list(BREMEN_V01_FEATURE_COLUMNS),
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


def build_feature_table(
    h5_path: str | Path,
    *,
    layout_context: H5PredictionContext | None = None,
) -> dict[str, float]:
    """Extract the 15-feature v0.1 vector from an H5 container.

    Reads target and contralateral profiles from H5.
    Computes per-patient symmetry measures.

    Parameters
    ----------
    h5_path : Path to the H5 container.
    layout_context : Optional ``H5PredictionContext`` for layout-aware
        extraction.  When ``layout_context.layout_name == "calibration_sample"``,
        reads integration i/q arrays from resolved group paths.
        When ``None`` or ``layout_name == "canonical"``, uses canonical path.

    Returns
    -------
    A dict mapping all 15 v0.1 feature names to finite float values.
    """
    with h5py.File(h5_path, "r") as f:
        # Determine extraction path based on layout context
        if layout_context is not None and layout_context.layout_name == "calibration_sample":
            target_path = layout_context.target_group_path
            control_path = layout_context.control_group_path
            if not target_path or not control_path:
                raise PreprocessingBridgeError(
                    "Missing target/control group paths for calibration preprocessing"
                )
            target_profiles = _extract_calibration_profiles(f, target_path)
            contralateral_profiles = _extract_calibration_profiles(f, control_path)
        elif layout_context is not None and layout_context.layout_name == "session_layout":
            # Session layout: read integration/i arrays directly from target/control group paths
            target_path = layout_context.target_group_path
            control_path = layout_context.control_group_path
            if not target_path or not control_path:
                raise PreprocessingBridgeError(
                    "Missing target/control group paths for session preprocessing"
                )
            target_profiles = _extract_session_profiles(f, target_path)
            contralateral_profiles = _extract_session_profiles(f, control_path)
        elif layout_context is not None and layout_context.layout_name == "matador_raw":
            # Matador raw layout: read raw 2D arrays, integrate via xrd_preprocessing,
            # and compute 1D magnitude profiles.
            target_path = layout_context.target_group_path
            control_path = layout_context.control_group_path
            adapter_metadata = layout_context.adapter_metadata
            if not target_path or not control_path:
                raise PreprocessingBridgeError(
                    "Missing target/control group paths for Matador preprocessing"
                )
            target_profiles, target_q = _extract_matador_profiles(
                f, target_path, adapter_metadata
            )
            contralateral_profiles, control_q = _extract_matador_profiles(
                f, control_path, adapter_metadata
            )
            # Align q ranges if they differ (must be compatible)
            if len(target_q) != len(control_q):
                raise PreprocessingBridgeError(
                    f"Matador target/control q-axis lengths mismatch: "
                    f"{len(target_q)} vs {len(control_q)}"
                )
            if np.max(np.abs(target_q - control_q)) > 0.01:
                raise PreprocessingBridgeError(
                    "Matador target/control q-axes are not compatible "
                    "for feature computation"
                )
        else:
            target_profiles = _extract_profiles(f, "target")
            contralateral_profiles = _extract_profiles(f, "contralateral")

    if not target_profiles or not contralateral_profiles:
        raise PreprocessingBridgeError(
            "Cannot compute features: missing profiles"
        )

    t_mean = np.mean(np.array(target_profiles), axis=0)
    c_mean = np.mean(np.array(contralateral_profiles), axis=0)

    # Features 1-2: existing sigma/weighted RMS
    sigma_l1, sigma_l2 = _sigma_rms(t_mean, c_mean)
    weighted_rms1 = _weighted_rms_difference(t_mean, c_mean)

    # Features 3, 6-7: sigma_r1, sigma_r2 (r-variant sigma RMS)
    sigma_r1, sigma_r2 = _sigma_rms_r(t_mean, c_mean)

    # Features 4, 8: mahalanobis1, mahalanobis2 (lowercase)
    m1, m2 = _mahalanobis_difference(t_mean, c_mean)

    # Feature 5: weightedrms2 (additional weighted RMS variant)
    weighted_rms2 = _weighted_rms_difference_v2(t_mean, c_mean)

    # Feature 9: peak14_intensity
    peak14 = _peak14_intensity(t_mean, c_mean)

    # Feature 10: mean_peak_value_raw
    mean_peak = _mean_peak_value_raw(t_mean, c_mean)

    # Feature 11: wasserstein_distance_muLR
    wass_mulr = _wasserstein_mulr(t_mean, c_mean)

    # Feature 12: cosine_distance_full_q2
    cosine_dist = _cosine_distance(t_mean, c_mean)

    # Feature 13: wasserstein_distance_full_q2
    wass_fq2 = _profile_wasserstein(t_mean, c_mean)

    # Feature 14: meanrms1
    meanrms1_val = _mean_rms1(t_mean, c_mean)

    # Feature 15: meanrms2
    meanrms2_val = _rms_difference(t_mean, c_mean)

    return {
        "weightedrms1": float(weighted_rms1),
        "sigma_l1": float(sigma_l1),
        "sigma_r1": float(sigma_r1),
        "mahalanobis1": float(m1),
        "weightedrms2": float(weighted_rms2),
        "sigma_l2": float(sigma_l2),
        "sigma_r2": float(sigma_r2),
        "mahalanobis2": float(m2),
        "peak14_intensity": float(peak14),
        "mean_peak_value_raw": float(mean_peak),
        "wasserstein_distance_muLR": float(wass_mulr),
        "cosine_distance_full_q2": float(cosine_dist),
        "wasserstein_distance_full_q2": float(wass_fq2),
        "meanrms1": float(meanrms1_val),
        "meanrms2": float(meanrms2_val),
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
    - Feature count matches ``BREMEN_V01_FEATURE_COLUMNS``.
    - Feature names match exact order.
    - Feature schema version matches (if provided).
    - All values are finite (not NaN, not Inf).

    Raises ``FeatureSchemaMismatchError`` on any mismatch.
    """
    if len(feature_vector.features) != _EXPECTED_FEATURE_COUNT:
        raise FeatureSchemaMismatchError(
            f"Expected {_EXPECTED_FEATURE_COUNT} features, "
            f"got {len(feature_vector.features)}"
        )

    actual_names = feature_vector.feature_names
    if len(actual_names) != _EXPECTED_FEATURE_COUNT:
        raise FeatureSchemaMismatchError(
            f"Expected {_EXPECTED_FEATURE_COUNT} feature names, "
            f"got {len(actual_names)}"
        )

    for i, (expected, actual) in enumerate(
        zip(BREMEN_V01_FEATURE_COLUMNS, actual_names)
    ):
        if expected != actual:
            raise FeatureSchemaMismatchError(
                f"Feature name mismatch at index {i}: "
                f"expected {expected!r}, got {actual!r}"
            )

    if expected_version is not None:
        if feature_vector.feature_schema_version != expected_version:
            raise FeatureSchemaMismatchError(
                f"Expected feature schema version {expected_version!r}, "
                f"got {feature_vector.feature_schema_version!r}"
            )

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
    measurements = h5_file[f"/scans/{scan_label}/measurements"][:]
    if measurements.ndim == 1:
        return [np.asarray(measurements, dtype=np.float64)]
    return [
        np.asarray(measurements[i], dtype=np.float64)
        for i in range(measurements.shape[0])
    ]


def _extract_calibration_profiles(
    h5_file: h5py.File,
    sample_group_path: str,
) -> list[np.ndarray]:
    """Read profiles from a calibration sample group.

    Reads integration/i and integration/q from each set_* group under
    ``{sample_group_path}/sets/``, computes per-set magnitude
    ``sqrt(i^2 + q^2)``, and returns a list of 1D profile arrays.

    Parameters
    ----------
    h5_file : Open H5 file handle.
    sample_group_path : Absolute H5 group path to the sample
        (e.g. ``/calib_20260128_132622/sample_01_...``).

    Returns
    -------
    List of 1D numpy arrays (one per set).

    Raises
    ------
    PreprocessingBridgeError
        If sets group is missing, sets are empty, i/q arrays are missing,
        or i/q arrays have incompatible lengths.
    """
    sets_path = f"{sample_group_path}/sets"
    if sets_path not in h5_file:
        raise PreprocessingBridgeError(
            "Missing calibration sample sets group"
        )

    sets_group = h5_file[sets_path]
    set_keys = sorted(
        k for k in sets_group.keys() if k.startswith("set_")
    )

    if not set_keys:
        raise PreprocessingBridgeError(
            "No measurement sets found in calibration sample"
        )

    profiles: list[np.ndarray] = []
    for set_key in set_keys:
        set_path = f"{sets_path}/{set_key}"

        # Read integration/i
        i_path = f"{set_path}/integration/i"
        if i_path not in h5_file:
            raise PreprocessingBridgeError(
                "Missing calibration integration/i"
            )
        i_arr = np.asarray(h5_file[i_path][()], dtype=np.float64)
        if i_arr.ndim != 1:
            raise PreprocessingBridgeError(
                "Calibration integration/i is not a 1D array"
            )

        # Read integration/q
        q_path = f"{set_path}/integration/q"
        if q_path not in h5_file:
            raise PreprocessingBridgeError(
                "Missing calibration integration/q"
            )
        q_arr = np.asarray(h5_file[q_path][()], dtype=np.float64)
        if q_arr.ndim != 1:
            raise PreprocessingBridgeError(
                "Calibration integration/q is not a 1D array"
            )

        # Validate compatible lengths
        if len(i_arr) != len(q_arr):
            raise PreprocessingBridgeError(
                "Calibration integration i and q have different lengths"
            )

        # Compute magnitude: sqrt(i^2 + q^2)
        magnitude = np.sqrt(i_arr**2 + q_arr**2)
        profiles.append(magnitude)

    return profiles


def _extract_session_profiles(
    h5_file: h5py.File,
    group_path: str,
) -> list[np.ndarray]:
    """Read profiles from a session-layout group.

    Reads integration/i and integration/q from the group at
    ``{group_path}/integration/``, computes magnitude
    ``sqrt(i^2 + q^2)``, and returns a list with a single 1D profile.

    Parameters
    ----------
    h5_file : Open H5 file handle.
    group_path : Absolute H5 group path to the target or control
        group (e.g. ``/session/sets/set_001_sample_main``).

    Returns
    -------
    List with one 1D numpy array.

    Raises
    ------
    PreprocessingBridgeError
        If integration arrays are missing or invalid.
    """
    # Read integration/i
    i_path = f"{group_path}/integration/i"
    if i_path not in h5_file:
        raise PreprocessingBridgeError(
            "Missing session integration/i"
        )
    i_arr = np.asarray(h5_file[i_path][()], dtype=np.float64)
    if i_arr.ndim != 1:
        raise PreprocessingBridgeError(
            "Session integration/i is not a 1D array"
        )

    # Read integration/q
    q_path = f"{group_path}/integration/q"
    if q_path not in h5_file:
        raise PreprocessingBridgeError(
            "Missing session integration/q"
        )
    q_arr = np.asarray(h5_file[q_path][()], dtype=np.float64)
    if q_arr.ndim != 1:
        raise PreprocessingBridgeError(
            "Session integration/q is not a 1D array"
        )

    # Validate compatible lengths
    if len(i_arr) != len(q_arr):
        raise PreprocessingBridgeError(
            "Session integration i and q have different lengths"
        )

    # Compute magnitude: sqrt(i^2 + q^2)
    magnitude = np.sqrt(i_arr**2 + q_arr**2)
    return [magnitude]


def _matador_raw_to_q_i(
    image: np.ndarray,
    *,
    poni_text: str | None = None,
    npt: int = 100,
) -> tuple[np.ndarray, np.ndarray]:
    """Integrate one Matador raw 2D image into q/i profile.

    Thin wrapper around ``xrd_preprocessing.perform_azimuthal_integration``.
    This is the single external integration boundary — all Matador-specific
    test mocking targets this function.

    Parameters
    ----------
    image : 2D numpy array (the raw diffraction frame).
    poni_text : PONI calibration text.  Required for PONI-mode
        integration.  If ``None``, dataframe-mode calibration
        parameters must be supplied (not yet implemented).
    npt : Number of radial points for 1D integration (default 100).

    Returns
    -------
    (q, intensity) — two 1D numpy arrays of matching length.

    Raises
    ------
    PreprocessingBridgeError
        If ``xrd_preprocessing`` is unavailable, raises an exception,
        or returns non-finite / empty / mismatched-length profiles.
    """
    import pandas as pd
    import xrd_preprocessing

    # Build a pd.Series row compatible with perform_azimuthal_integration
    row_data: dict = {
        "measurement_data": image,
    }
    calibration_mode: str
    if poni_text is not None:
        row_data["ponifile"] = poni_text
        calibration_mode = "poni"
    else:
        raise PreprocessingBridgeError(
            "Matador raw integration currently requires a PONI file. "
            "Dataframe-mode calibration not yet implemented for "
            "Matador raw containers."
        )

    row = pd.Series(row_data)

    try:
        radial, intensity, _sigma_or_az, _dist = \
            xrd_preprocessing.perform_azimuthal_integration(
                row,
                column="measurement_data",
                npt=npt,
                mode="1D",
                calibration_mode=calibration_mode,
                error_model=None,
                thickness_adjustment=False,
                require_thickness_adjustment=False,
            )
    except Exception as exc:
        raise PreprocessingBridgeError(
            f"xrd_preprocessing integration failed: {exc}"
        ) from exc

    # Convert and validate
    q = np.asarray(radial, dtype=np.float64)
    i_arr = np.asarray(intensity, dtype=np.float64)
    _validate_q_i_output(q, i_arr)
    return q, i_arr


def _validate_q_i_output(
    q: np.ndarray, i_arr: np.ndarray,
) -> None:
    """Validate q/i integration output (pure function, no external deps).

    Checks:
    - 1-dimensionality
    - Matching lengths
    - Non-empty
    - Finite values
    - Strictly increasing q

    Raises PreprocessingBridgeError on any validation failure.
    """
    if q.ndim != 1 or i_arr.ndim != 1:
        raise PreprocessingBridgeError(
            "Integration output is not 1-dimensional"
        )
    if len(q) != len(i_arr):
        raise PreprocessingBridgeError(
            f"q ({len(q)}) and intensity ({len(i_arr)}) lengths mismatch"
        )
    if len(q) == 0:
        raise PreprocessingBridgeError("Integration returned empty profiles")
    if not np.all(np.isfinite(q)) or not np.all(np.isfinite(i_arr)):
        raise PreprocessingBridgeError(
            "Integration returned non-finite q or intensity values"
        )
    if not np.all(np.diff(q) > 0):
        raise PreprocessingBridgeError("Integration output q is not strictly increasing")


def _extract_matador_profiles(
    h5_file: h5py.File,
    group_path: str,
    adapter_metadata: dict,
) -> tuple[list[np.ndarray], np.ndarray]:
    """Read raw 2D image, integrate, return 1D profile.

    For a Matador raw measurement group:
    1. Reads the 2D measurement dataset at the first 2D dataset found.
    2. Reads PONI text from a calibration group/dataset.
    3. Calls ``_matador_raw_to_q_i`` (the external integration wrapper).
    4. Returns the 1D magnitude profile (sqrt(i^2 + q^2)).

    Parameters
    ----------
    h5_file : Open H5 file handle.
    group_path : Absolute H5 group path containing the raw 2D dataset.
    adapter_metadata : Adapter metadata dict from ``H5PredictionContext``
        containing calibration references.

    Returns
    -------
    (profiles, q) — list with one 1D profile array and the q axis.

    Raises
    ------
    PreprocessingBridgeError
        On missing data, integration failure, or invalid output.
    """
    # Find the 2D measurement dataset inside the group
    group = h5_file[group_path]
    dataset_name: str | None = None
    for key in group.keys():
        sub = group[key]
        if isinstance(sub, h5py.Dataset):
            ndim = len(sub.shape) if hasattr(sub, 'shape') else 0
            if ndim >= 2:
                dataset_name = key
                break

    if dataset_name is None:
        raise PreprocessingBridgeError(
            f"No 2D measurement dataset found in {group_path}"
        )

    image = np.asarray(group[dataset_name][()], dtype=np.float64)

    # Find PONI text — search known calibration locations
    poni_text: str | None = None
    calib_refs = adapter_metadata.get("calibration_refs", {})

    # Look for any dataset whose path contains "poni"
    poni_candidates = [
        path for path in calib_refs.keys()
        if "poni" in path.lower()
    ]
    if poni_candidates:
        poni_path = poni_candidates[0]
        try:
            raw = h5_file[poni_path][()]
            if isinstance(raw, bytes):
                poni_text = raw.decode("utf-8")
            else:
                poni_text = str(raw)
        except Exception:
            pass

    # If no explicit PONI dataset, search the entire file
    if poni_text is None:
        def _poni_visitor(name: str, obj: object) -> None:
            nonlocal poni_text
            if poni_text is not None:
                return
            if isinstance(obj, h5py.Dataset) and "poni" in name.lower():
                try:
                    raw = obj[()]
                    if isinstance(raw, bytes):
                        poni_text = raw.decode("utf-8")
                    else:
                        poni_text = str(raw)
                except Exception:
                    pass

        h5_file.visititems(_poni_visitor)

    if poni_text is None:
        raise PreprocessingBridgeError(
            "No PONI calibration text found for Matador integration"
        )

    q, i_arr = _matador_raw_to_q_i(image, poni_text=poni_text, npt=100)

    # Compute magnitude profile: sqrt(i^2 + q^2)
    magnitude = np.sqrt(i_arr**2 + q**2)
    return [magnitude], q


def _sigma_rms(
    target: np.ndarray, contralateral: np.ndarray
) -> tuple[float, float]:
    diff = target - contralateral
    return float(np.mean(np.abs(diff))), float(np.sqrt(np.mean(diff**2)))


def _sigma_rms_r(
    target: np.ndarray, contralateral: np.ndarray
) -> tuple[float, float]:
    """sigma_r1 and sigma_r2 — RMS with different normalisation (r variant)."""
    diff = target - contralateral
    rms = np.sqrt(np.mean(diff**2))
    # sigma_r1: mean absolute deviation normalised by RMS
    r1 = float(np.mean(np.abs(diff)) / (rms + 1e-10))
    # sigma_r2: RMS value itself (same as sigma_l2 in this implementation)
    r2 = float(rms)
    return r1, r2


def _mahalanobis_difference(
    target_profile: np.ndarray,
    contralateral_profile: np.ndarray,
) -> tuple[float, float]:
    """Lowercase mahalanobis1 and mahalanobis2.

    mahalanobis1: normalised by per-element variance.
    mahalanobis2: normalised by standard deviation with dampening.
    """
    diff = target_profile - contralateral_profile
    var = np.var(np.stack([target_profile, contralateral_profile]), axis=0)
    var_damped = var + 1e-10
    m1 = float(np.sqrt(np.mean(diff**2 / var_damped)))
    std_damped = np.sqrt(var_damped)
    m2 = float(np.mean(np.abs(diff) / (std_damped + 1e-10)))
    return m1, m2


def _weighted_rms_difference(
    target: np.ndarray, contralateral: np.ndarray
) -> float:
    """weightedrms1."""
    diff = target - contralateral
    weights = (np.abs(target) + np.abs(contralateral)) / 2
    weights = weights / (np.sum(weights) + 1e-10)
    return float(np.sqrt(np.sum(weights * diff**2)))


def _weighted_rms_difference_v2(
    target: np.ndarray, contralateral: np.ndarray
) -> float:
    """weightedrms2 — weighted RMS variant with intensity-based damping."""
    diff = target - contralateral
    weights = (np.abs(target) + np.abs(contralateral)) / 2
    weights = np.sqrt(weights + 1e-10)
    weights = weights / (np.sum(weights) + 1e-10)
    return float(np.sqrt(np.sum(weights * diff**2)))


def _profile_wasserstein(
    target: np.ndarray, contralateral: np.ndarray
) -> float:
    """Wasserstein-1 distance for wasserstein_distance_full_q2."""
    t = target / (np.sum(np.abs(target)) + 1e-10)
    c = contralateral / (np.sum(np.abs(contralateral)) + 1e-10)
    t_sorted = np.sort(t)
    c_sorted = np.sort(c)
    return float(np.mean(np.abs(np.cumsum(t_sorted) - np.cumsum(c_sorted))))


def _wasserstein_mulr(
    target: np.ndarray, contralateral: np.ndarray
) -> float:
    """wasserstein_distance_muLR — mu/LR variant of Wasserstein distance."""
    diff = target - contralateral
    weights = np.abs(target) + np.abs(contralateral)
    weights = weights / (np.sum(weights) + 1e-10)
    return float(np.sum(weights * np.abs(diff)))


def _cosine_distance(
    target: np.ndarray, contralateral: np.ndarray
) -> float:
    """cosine_distance_full_q2."""
    t_norm = target / (np.linalg.norm(target) + 1e-10)
    c_norm = contralateral / (np.linalg.norm(contralateral) + 1e-10)
    return float(1.0 - np.dot(t_norm, c_norm))


def _rms_difference(
    target: np.ndarray, contralateral: np.ndarray
) -> float:
    """Root-mean-square asymmetry (meanrms2)."""
    diff = target - contralateral
    return float(np.sqrt(np.mean(diff**2)))


def _mean_rms1(
    target: np.ndarray, contralateral: np.ndarray
) -> float:
    """meanrms1 — L1 mean of absolute difference."""
    diff = target - contralateral
    return float(np.mean(np.abs(diff)))


def _peak14_intensity(
    target: np.ndarray, contralateral: np.ndarray
) -> float:
    """peak14_intensity — intensity near index 14 in mean profile."""
    n = min(len(target), 100)
    idx = min(14, n - 1)
    return float((np.abs(target[idx]) + np.abs(contralateral[idx])) / 2.0)


def _mean_peak_value_raw(
    target: np.ndarray, contralateral: np.ndarray
) -> float:
    """mean_peak_value_raw — mean of top-5 absolute intensities."""
    t_top = np.sort(np.abs(target))[-5:].mean()
    c_top = np.sort(np.abs(contralateral))[-5:].mean()
    return float((t_top + c_top) / 2.0)
