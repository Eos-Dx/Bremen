"""Symmetry signal computation from Bremen 15-feature vector.

Produces per-signal difference_level values via percentile-position
bucketing against a safe aggregate reference-statistics artifact.

Phase 1 (PR0092): Fail-closed not_available implementation.
The reference-statistics artifact does not exist yet — all signals
return ``difference_level: "not_available"``.

Phase 2 (follow-up PR): Wire real percentile-position bucketing once
the aggregate reference-statistics JSON artifact is delivered by the
data science team.

PR0092 — Real Symmetry Difference-Level Computation.
"""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowed difference levels
# ---------------------------------------------------------------------------

ALLOWED_DIFFERENCE_LEVELS: frozenset[str] = frozenset({
    "small",
    "moderate",
    "larger",
    "not_available",
})

# ---------------------------------------------------------------------------
# Feature-to-signal mapping (verified from preprocessing_bridge.py)
# ---------------------------------------------------------------------------

# 15 features → 5 signal families, classified by real computational
# logic.  Duplicate computations (sigma_l1==meanrms1,
# sigma_l2==sigma_r2==meanrms2) are mapped to the same signal family.

FEATURE_TO_SIGNAL_MAP: dict[str, str] = {
    # profile_difference_magnitude (3 unique computations, 6 features)
    "sigma_l1": "profile_difference_magnitude",
    "sigma_r1": "profile_difference_magnitude",
    "sigma_l2": "profile_difference_magnitude",
    "sigma_r2": "profile_difference_magnitude",
    "meanrms1": "profile_difference_magnitude",
    "meanrms2": "profile_difference_magnitude",
    # weighted_profile_asymmetry
    "weightedrms1": "weighted_profile_asymmetry",
    "weightedrms2": "weighted_profile_asymmetry",
    # statistical_shape_deviation
    "mahalanobis1": "statistical_shape_deviation",
    "mahalanobis2": "statistical_shape_deviation",
    # distributional_divergence
    "wasserstein_distance_muLR": "distributional_divergence",
    "cosine_distance_full_q2": "distributional_divergence",
    "wasserstein_distance_full_q2": "distributional_divergence",
    # bilateral_profile_intensity
    "peak14_intensity": "bilateral_profile_intensity",
    "mean_peak_value_raw": "bilateral_profile_intensity",
}

# Plain-language clinician-facing labels per signal family
SIGNAL_LABELS: dict[str, str] = {
    "profile_difference_magnitude": "Profile difference magnitude",
    "weighted_profile_asymmetry": "Weighted profile asymmetry",
    "statistical_shape_deviation": "Statistical shape deviation",
    "distributional_divergence": "Distributional divergence",
    "bilateral_profile_intensity": "Bilateral profile intensity",
}

# Feature-family names per signal (internal detail)
SIGNAL_FEATURE_FAMILIES: dict[str, list[str]] = {
    "profile_difference_magnitude": [
        "sigma_l1", "sigma_l2", "sigma_r1", "sigma_r2",
        "meanrms1", "meanrms2",
    ],
    "weighted_profile_asymmetry": ["weightedrms1", "weightedrms2"],
    "statistical_shape_deviation": ["mahalanobis1", "mahalanobis2"],
    "distributional_divergence": [
        "wasserstein_distance_full_q2",
        "wasserstein_distance_muLR",
        "cosine_distance_full_q2",
    ],
    "bilateral_profile_intensity": [
        "peak14_intensity", "mean_peak_value_raw",
    ],
}

# Ordered signal keys for deterministic output
_SIGNAL_ORDER: tuple[str, ...] = (
    "profile_difference_magnitude",
    "weighted_profile_asymmetry",
    "statistical_shape_deviation",
    "distributional_divergence",
    "bilateral_profile_intensity",
)

# ---------------------------------------------------------------------------
# Level ordering for "most extreme" aggregation
# ---------------------------------------------------------------------------

_LEVEL_RANK: dict[str, int] = {
    "not_available": -1,
    "small": 0,
    "moderate": 1,
    "larger": 2,
}


# ---------------------------------------------------------------------------
# Bucketing
# ---------------------------------------------------------------------------


def _percentile_bucket(
    value: float,
    bounds: dict[str, float] | None,
) -> str:
    """Classify a feature value into a difference_level bucket.

    Parameters
    ----------
    value : The feature value (computed from target/control profiles).
    bounds : Dict with ``"small"`` and ``"moderate"`` percentile
        cutoff values, or ``None`` if no reference is available.

    Returns
    -------
    One of ``"small"``, ``"moderate"``, ``"larger"``, or
    ``"not_available"``.
    """
    import math  # noqa: PLC0415
    if bounds is None:
        return "not_available"
    if not isinstance(value, (int, float)):
        return "not_available"
    if math.isnan(value) or math.isinf(value):
        return "not_available"

    small_cutoff = bounds.get("small")
    moderate_cutoff = bounds.get("moderate")

    if small_cutoff is None or moderate_cutoff is None:
        return "not_available"

    if not isinstance(small_cutoff, (int, float)) or not isinstance(
        moderate_cutoff, (int, float)
    ):
        return "not_available"

    if value <= small_cutoff:
        return "small"
    if value <= moderate_cutoff:
        return "moderate"
    return "larger"


def _aggregate_signal_level(per_feature_levels: list[str]) -> str:
    """Aggregate per-feature levels into a signal-level using the most
    extreme (highest) level.

    ``not_available`` is treated as a sentinel — if any feature in
    the signal is ``not_available``, the signal is ``not_available``
    unless all features are ``not_available`` and the signal truly has
    no data.  For safety, if *all* features are ``not_available`` the
    signal stays ``not_available``; if any feature has a real level,
    ``not_available`` features are ignored and the max of the rest
    is used.
    """
    real = [l for l in per_feature_levels if l != "not_available"]
    if not real:
        return "not_available"
    return max(real, key=lambda l: _LEVEL_RANK.get(l, -1))


# ---------------------------------------------------------------------------
# Reference statistics loading
# ---------------------------------------------------------------------------


def _validate_reference_statistics(artifact: dict[str, Any]) -> bool:
    """Validate the reference-statistics artifact shape.

    Returns True if the artifact passes basic schema validation.
    Does NOT load numpy, does NOT access filesystem.
    """
    if not isinstance(artifact, dict):
        return False
    if artifact.get("artifact_type") != "bremen_reference_statistics":
        return False
    signals = artifact.get("signals")
    if not isinstance(signals, dict):
        return False
    # Every expected signal must have percentile_bounds
    for key in _SIGNAL_ORDER:
        signal = signals.get(key)
        if not isinstance(signal, dict):
            return False
        bounds = signal.get("percentile_bounds")
        if not isinstance(bounds, dict):
            return False
        if "small" not in bounds or "moderate" not in bounds:
            return False
    return True


def _load_reference_statistics(
    artifact_path_or_obj: str | dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Load and validate the reference-statistics artifact.

    Phase 1: Returns ``None`` (artifact does not exist yet).
    Phase 2: Will load from S3 or a local path, validate, and return
    the parsed artifact dict.

    Parameters
    ----------
    artifact_path_or_obj : Optional path or pre-loaded dict for tests.
        When a dict is provided, validates it and returns it if valid.
        When a string is provided, attempts to load from that path.

    Returns
    -------
    The validated artifact dict, or ``None`` if unavailable.
    """
    import json as _json
    import os as _os

    if artifact_path_or_obj is None:
        # Phase 1: artifact not yet available
        _log.debug(
            "event=bremen.symmetry.ref_stats.load\tstatus=not_configured"
        )
        return None

    if isinstance(artifact_path_or_obj, dict):
        # Pre-loaded dict (test path)
        if _validate_reference_statistics(artifact_path_or_obj):
            _log.debug(
                "event=bremen.symmetry.ref_stats.load\tstatus=loaded\t"
                "source=dict"
            )
            return artifact_path_or_obj
        _log.warning(
            "event=bremen.symmetry.ref_stats.load\tstatus=invalid_schema\t"
            "source=dict"
        )
        return None

    if isinstance(artifact_path_or_obj, str):
        # Path-based loading
        try:
            with open(artifact_path_or_obj, "r", encoding="utf-8") as fh:
                data = _json.load(fh)
            if _validate_reference_statistics(data):
                _log.debug(
                    "event=bremen.symmetry.ref_stats.load\t"
                    "status=loaded\tsource=path"
                )
                return data
            _log.warning(
                "event=bremen.symmetry.ref_stats.load\t"
                "status=invalid_schema\tsource=path"
            )
            return None
        except (OSError, _json.JSONDecodeError, ValueError) as exc:
            _log.warning(
                "event=bremen.symmetry.ref_stats.load\t"
                "status=failed\tmessage=%s",
                type(exc).__name__,
            )
            return None

    return None


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------


def compute_symmetry_signals(
    feature_values: dict[str, float] | None = None,
    ref_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute symmetry difference-level signals from feature values.

    Parameters
    ----------
    feature_values : Dict mapping feature names to float values.
        When ``None`` or empty, all signals return ``not_available``.
    ref_stats : Validated reference-statistics artifact dict, or
        ``None`` if unavailable.

    Returns
    -------
    A dict with ``schema_status``, ``measurement_summary``,
    ``signals`` (list of per-signal dicts with ``label``,
    ``feature_family``, ``difference_level``), and optional
    ``note`` and ``checksum_prefix``.
    """
    import numpy as np  # noqa: PLC0415 — needed for np.isfinite

    if ref_stats is None:
        # Phase 1: fail-closed — all not_available
        signals = []
        for key in _SIGNAL_ORDER:
            signals.append({
                "label": SIGNAL_LABELS[key],
                "feature_family": list(SIGNAL_FEATURE_FAMILIES[key]),
                "difference_level": "not_available",
            })
        return {
            "schema_status": "unavailable",
            "measurement_summary": (
                "Asymmetry assessment from 5 signal families across "
                "15 features."
            ),
            "signals": signals,
            "note": (
                "Reference statistics: not available. "
                "Symmetry assessment is not computed."
            ),
            "checksum_prefix": None,
            "reference_artifact_version": None,
        }

    # Validate artifact
    if not _validate_reference_statistics(ref_stats):
        signals = []
        for key in _SIGNAL_ORDER:
            signals.append({
                "label": SIGNAL_LABELS[key],
                "feature_family": list(SIGNAL_FEATURE_FAMILIES[key]),
                "difference_level": "not_available",
            })
        return {
            "schema_status": "error",
            "measurement_summary": (
                "Asymmetry assessment from 5 signal families across "
                "15 features."
            ),
            "signals": signals,
            "note": (
                "Reference statistics: invalid artifact. "
                "Symmetry assessment is not computed."
            ),
            "checksum_prefix": None,
            "reference_artifact_version": None,
        }

    # Build per-signal difference levels
    artifact_signals = ref_stats.get("signals", {})
    result_signals: list[dict[str, Any]] = []

    for key in _SIGNAL_ORDER:
        label = SIGNAL_LABELS[key]
        feature_family = list(SIGNAL_FEATURE_FAMILIES[key])
        signal_cfg = artifact_signals.get(key)

        if signal_cfg is None or not isinstance(signal_cfg, dict):
            # Signal missing from artifact → not_available
            result_signals.append({
                "label": label,
                "feature_family": feature_family,
                "difference_level": "not_available",
            })
            continue

        bounds = signal_cfg.get("percentile_bounds")
        per_feature: list[str] = []

        for feat_name in feature_family:
            val = feature_values.get(feat_name) if feature_values else None
            if val is None:
                per_feature.append("not_available")
            else:
                per_feature.append(_percentile_bucket(float(val), bounds))

        level = _aggregate_signal_level(per_feature)
        result_signals.append({
            "label": label,
            "feature_family": feature_family,
            "difference_level": level,
        })

    # Checksum prefix — first 8 hex chars, never full checksum
    checksum_raw = ref_stats.get("_artifact_checksum", "")
    checksum_prefix = checksum_raw[:8] if checksum_raw else None

    return {
        "schema_status": "populated",
        "measurement_summary": (
            "Asymmetry assessment computed from 5 signal families "
            "across 15 features."
        ),
        "signals": result_signals,
        "checksum_prefix": checksum_prefix,
        "reference_artifact_version": ref_stats.get("artifact_version"),
        "note": None,
    }


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _format_external(
    symmetry_result: dict[str, Any],
) -> dict[str, Any]:
    """Format symmetry signals for external (public) output.

    External output includes only: schema_status, measurement_summary,
    signals (label + difference_level), note.

    Explicitly excluded: feature_family, feature values, deltas,
    percentile cutoffs, checksum_prefix, reference_artifact_version,
    raw target/control refs.
    """
    external_signals: list[dict[str, Any]] = []
    for sig in symmetry_result.get("signals", []):
        external_signals.append({
            "label": sig.get("label", ""),
            "difference_level": sig.get("difference_level", "not_available"),
        })

    result: dict[str, Any] = {
        "schema_status": symmetry_result.get("schema_status", "unavailable"),
        "measurement_summary": symmetry_result.get(
            "measurement_summary", ""
        ),
        "signals": external_signals,
    }

    note = symmetry_result.get("note")
    if note is not None:
        result["note"] = note

    return result


def _format_internal(
    symmetry_result: dict[str, Any],
) -> dict[str, Any]:
    """Format symmetry signals for internal (technical) output.

    Internal output includes: schema_status, measurement_summary,
    signals (label + feature_family + difference_level),
    checksum_prefix (first 8 hex chars only), reference_artifact_version,
    note.

    Explicitly excluded: raw feature values, raw deltas, percentile
    cutoffs, full checksum, raw target/control refs, patient names,
    PHI, raw H5/S3 paths, model internals, coefficients, exception text.
    """
    internal_signals: list[dict[str, Any]] = []
    for sig in symmetry_result.get("signals", []):
        internal_signals.append({
            "label": sig.get("label", ""),
            "feature_family": sig.get("feature_family", []),
            "difference_level": sig.get("difference_level", "not_available"),
        })

    result: dict[str, Any] = {
        "schema_status": symmetry_result.get("schema_status", "unavailable"),
        "measurement_summary": symmetry_result.get(
            "measurement_summary", ""
        ),
        "signals": internal_signals,
    }

    cprefix = symmetry_result.get("checksum_prefix")
    if cprefix is not None:
        result["checksum_prefix"] = str(cprefix)

    ra_version = symmetry_result.get("reference_artifact_version")
    if ra_version is not None:
        result["reference_artifact_version"] = str(ra_version)

    note = symmetry_result.get("note")
    if note is not None:
        result["note"] = note

    return result
