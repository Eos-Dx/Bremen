"""Bremen v0.1 integrated-profile feature science, frozen by PR0151 (package-owned).

Moved into the Bremen v0.1 inference package by PR0154.  Numerical primitives
are transcribed verbatim from the reviewed PR0151 training reference; no
scientific behavior changed.  This module is model science only: it imports
numpy/pandas/scipy/stdlib and performs NO platform work.  The structural
canonical-measurement validation that PR0152/PR0153B flagged as a lazy
``bremen.api.xrd_normalization`` import is lifted to the package runtime
boundary (``runtime.BremenRuntime``); the shape gate below stays here.

Research decision support requiring radiologist review.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

FEATURE_COLS = [
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
]


LEFT_VALUES = {"L", "LEFT"}


RIGHT_VALUES = {"R", "RIGHT"}


@dataclass(frozen=True)
class AnalysisConfig:
    q_roi: tuple[float, float] = (7.5, 23.0)
    zones: tuple[tuple[float, float], tuple[float, float]] = ((7.0, 15.0), (15.0, 23.0))
    smooth: bool = True
    sg_window: int = 11
    sg_poly: int = 3
    min_q0: float = 6.7
    min_halfwidth: float = 0.25
    min_mode: str = "p05"
    peak_center: float = 14.0
    peak_halfwidth: float = 0.5
    peak_mode: str = "max"
    raw_peak_min: float = 13.0
    raw_peak_max: float = 14.8
    raw_peak_threshold: float = 0.6
    cosine_q_roi: tuple[float, float] = (2.0, 23.0)




def parse_q_grid(q_range, n_points: int) -> np.ndarray:
    if isinstance(q_range, np.ndarray):
        q = q_range.astype(float).ravel()
        if q.size != n_points:
            raise ValueError(f"q_range length {q.size} != intensity length {n_points}")
        return q

    if isinstance(q_range, (list, tuple)):
        if len(q_range) == 2 and np.isscalar(q_range[0]) and np.isscalar(q_range[1]):
            return np.linspace(float(q_range[0]), float(q_range[1]), n_points)
        q = np.asarray(q_range, dtype=float).ravel()
        if q.size != n_points:
            raise ValueError(f"q_range length {q.size} != intensity length {n_points}")
        return q

    if isinstance(q_range, str):
        s = q_range.strip().replace(":", "-")
        parts = s.split("-")
        if len(parts) == 2:
            return np.linspace(float(parts[0]), float(parts[1]), n_points)

    raise ValueError(f"Unsupported q_range value: {q_range!r}")


def apply_roi(q: np.ndarray, intensity: np.ndarray, q_roi=None):
    if q_roi is None:
        return q, intensity
    qmin, qmax = float(q_roi[0]), float(q_roi[1])
    mask = (q >= qmin) & (q <= qmax)
    if mask.sum() < 5:
        raise ValueError(f"ROI {q_roi} leaves too few points ({mask.sum()})")
    return q[mask], intensity[mask]


def safe_savgol(y: np.ndarray, window: int = 21, poly: int = 3) -> np.ndarray:
    y = np.asarray(y, float).ravel()
    if y.size < 5 or window < 5:
        return y
    if window % 2 == 0:
        window += 1
    if window > y.size:
        window = y.size if y.size % 2 == 1 else y.size - 1
    if window < 5:
        return y
    poly = min(poly, window - 2)
    if poly < 1:
        return y
    return savgol_filter(y, window_length=window, polyorder=poly)


def minimum_reference_value(q, intensity, q0=6.7, halfwidth=0.25, mode="p05") -> float:
    q = np.asarray(q, float).ravel()
    intensity = np.asarray(intensity, float).ravel()
    mask = (q >= q0 - halfwidth) & (q <= q0 + halfwidth)
    if mask.sum() < 3:
        return np.nan
    window = intensity[mask]
    if mode == "min":
        return float(np.min(window))
    if mode in {"p05", "p5"}:
        return float(np.percentile(window, 5))
    raise ValueError("min_mode must be 'min' or 'p05'")


def normalize_by_minimum(q, intensity, q0=6.7, halfwidth=0.25, mode="p05") -> np.ndarray:
    ref = minimum_reference_value(q, intensity, q0=q0, halfwidth=halfwidth, mode=mode)
    if not np.isfinite(ref):
        return intensity
    ref_eff = max(abs(ref), 1e-12, 1e-3)
    return intensity / ref_eff


def build_common_grid(q_list: list[np.ndarray]) -> np.ndarray:
    q_min = max(float(np.nanmin(q)) for q in q_list)
    q_max = min(float(np.nanmax(q)) for q in q_list)
    if not np.isfinite(q_min) or not np.isfinite(q_max) or q_max <= q_min:
        raise ValueError("No overlapping q range across patient curves")

    def median_step(q: np.ndarray) -> float:
        q = np.sort(np.asarray(q, float).ravel())
        steps = np.diff(q)
        steps = steps[np.isfinite(steps) & (steps > 0)]
        if steps.size:
            return float(np.median(steps))
        return float((q_max - q_min) / max(len(q), 2))

    step = min(median_step(q) for q in q_list)
    n_points = int(np.clip(np.round((q_max - q_min) / max(step, 1e-12)) + 1, 50, 5000))
    return np.linspace(q_min, q_max, n_points)


def resample_to_common(q: np.ndarray, intensity: np.ndarray, q_common: np.ndarray) -> np.ndarray:
    order = np.argsort(q)
    return np.interp(q_common, q[order], intensity[order], left=np.nan, right=np.nan)


def side_label(value) -> str | None:
    text = str(value).strip().upper()
    if text in LEFT_VALUES:
        return "L"
    if text in RIGHT_VALUES:
        return "R"
    return None


def patient_lr_mean_metrics(df: pd.DataFrame, patient_id: str, config: AnalysisConfig, q_roi=None):
    sub = df[df["patient_id"] == patient_id].copy()
    if sub.empty:
        raise ValueError(f"No rows for patient_id={patient_id}")

    q_list: list[np.ndarray] = []
    intensity_list: list[np.ndarray] = []
    side_list: list[str] = []

    for _, row in sub.iterrows():
        side = side_label(row["side"])
        if side is None:
            continue
        intensity = np.asarray(row["radial_profile_data"], float).ravel()
        q = parse_q_grid(row["q_range"], n_points=len(intensity))
        q, intensity = apply_roi(q, intensity, q_roi=q_roi)
        if config.smooth:
            intensity = safe_savgol(intensity, window=config.sg_window, poly=config.sg_poly)
        intensity = normalize_by_minimum(
            q,
            intensity,
            q0=config.min_q0,
            halfwidth=config.min_halfwidth,
            mode=config.min_mode,
        )
        q_list.append(q)
        intensity_list.append(intensity)
        side_list.append(side)

    if len(intensity_list) < 2:
        raise ValueError(f"Need at least 2 curves; got {len(intensity_list)}")

    q_common = build_common_grid(q_list)
    x = np.vstack(
        [resample_to_common(q, intensity, q_common) for q, intensity in zip(q_list, intensity_list)]
    )
    if np.isnan(x).any():
        valid = np.isfinite(x).all(axis=0)
        if valid.sum() < 10:
            raise ValueError("Too few valid q points after resampling")
        q_common = q_common[valid]
        x = x[:, valid]

    sides = np.array(side_list)
    idx_left = np.where(sides == "L")[0]
    idx_right = np.where(sides == "R")[0]
    if idx_left.size == 0 or idx_right.size == 0:
        raise ValueError("Need at least one Left and one Right curve")

    x_left = x[idx_left, :]
    x_right = x[idx_right, :]
    mu_left = np.mean(x_left, axis=0)
    mu_right = np.mean(x_right, axis=0)
    std_left = np.std(x_left, axis=0, ddof=1) if idx_left.size >= 2 else np.zeros_like(mu_left)
    std_right = np.std(x_right, axis=0, ddof=1) if idx_right.size >= 2 else np.zeros_like(mu_right)

    return {
        "patient_id": patient_id,
        "q_common": q_common,
        "mu_left": mu_left,
        "mu_right": mu_right,
        "std_left": std_left,
        "std_right": std_right,
        "n_left": int(idx_left.size),
        "n_right": int(idx_right.size),
        "n_q": int(q_common.size),
    }


def mask_q(q: np.ndarray, q_min: float, q_max: float) -> np.ndarray:
    q = np.asarray(q, float).ravel()
    return (q >= float(q_min)) & (q <= float(q_max)) & np.isfinite(q)


def mean_rms_band(mu_left, mu_right, mask) -> float:
    diff = np.asarray(mu_left, float).ravel() - np.asarray(mu_right, float).ravel()
    mask = np.asarray(mask, bool) & np.isfinite(diff)
    if mask.sum() < 10:
        return np.nan
    return float(np.sqrt(np.mean(diff[mask] ** 2)))


def weighted_rms_band(mu_left, mu_right, std_left, std_right, mask, eps=1e-12):
    diff = np.asarray(mu_left, float).ravel() - np.asarray(mu_right, float).ravel()
    pooled_var = np.asarray(std_left, float).ravel() ** 2 + np.asarray(std_right, float).ravel() ** 2
    mask = np.asarray(mask, bool) & np.isfinite(diff) & np.isfinite(pooled_var)
    if mask.sum() < 10:
        return np.nan, np.nan, np.nan
    diff = diff[mask]
    pooled_var = pooled_var[mask]
    positive = pooled_var[pooled_var > 0]
    if positive.size:
        pooled_var = np.maximum(pooled_var, np.percentile(positive, 5))
    weights = 1.0 / (pooled_var + eps)
    sum_weights = float(np.sum(weights))
    if not np.isfinite(sum_weights) or sum_weights <= 0:
        return np.nan, np.nan, np.nan
    wrms = float(np.sqrt(np.sum(weights * diff * diff) / sum_weights))
    chi2 = float(np.sum(diff * diff / (pooled_var + eps)))
    return wrms, chi2, sum_weights


def mahalanobis_band(mu_left, mu_right, std_left, std_right, mask, eps=1e-12):
    diff = np.asarray(mu_left, float).ravel() - np.asarray(mu_right, float).ravel()
    pooled_var = np.asarray(std_left, float).ravel() ** 2 + np.asarray(std_right, float).ravel() ** 2
    mask = np.asarray(mask, bool) & np.isfinite(diff) & np.isfinite(pooled_var)
    if mask.sum() < 10:
        return np.nan, np.nan, 0
    diff = diff[mask]
    pooled_var = pooled_var[mask]
    positive = pooled_var[pooled_var > 0]
    if positive.size:
        pooled_var = np.maximum(pooled_var, np.percentile(positive, 5))
    d2 = float(np.sum(diff * diff / (pooled_var + eps)))
    dof = int(diff.size)
    return float(np.sqrt(d2)), float(np.sqrt(d2 / max(dof, 1))), dof


def sigma_rms_band(std, mask) -> float:
    std = np.asarray(std, float).ravel()
    mask = np.asarray(mask, bool) & np.isfinite(std)
    if mask.sum() < 10:
        return np.nan
    return float(np.sqrt(np.mean(std[mask] ** 2)))


def peak14_intensity_from_means(q, mu_left, mu_right, q_center=14.0, halfwidth=0.5, mode="max"):
    q = np.asarray(q, float).ravel()
    mu_avg = 0.5 * (np.asarray(mu_left, float).ravel() + np.asarray(mu_right, float).ravel())
    mask = (q >= q_center - halfwidth) & (q <= q_center + halfwidth) & np.isfinite(mu_avg)
    if mask.sum() < 3:
        return np.nan
    if mode == "max":
        return float(np.max(mu_avg[mask]))
    if mode == "mean":
        return float(np.mean(mu_avg[mask]))
    raise ValueError("peak_mode must be 'max' or 'mean'")


def local_peak_in_window(q, intensity, q_min=13.0, q_max=14.8) -> float:
    q = np.asarray(q, float).ravel()
    intensity = np.asarray(intensity, float).ravel()
    mask = (q >= q_min) & (q <= q_max) & np.isfinite(intensity)
    if mask.sum() < 3:
        return np.nan
    return float(np.max(intensity[mask]))


def patient_mean_raw_peak14(df: pd.DataFrame, patient_id: str, config: AnalysisConfig) -> float:
    sub = df[df["patient_id"] == patient_id]
    peaks = []
    for _, row in sub.iterrows():
        intensity = np.asarray(row["radial_profile_data"], float).ravel()
        q = parse_q_grid(row["q_range"], n_points=len(intensity))
        peak = local_peak_in_window(q, intensity, config.raw_peak_min, config.raw_peak_max)
        if np.isfinite(peak):
            peaks.append(peak)
    return float(np.mean(peaks)) if peaks else np.nan


def cosine_distance(a, b, eps=1e-12) -> float:
    a = np.asarray(a, float).ravel()
    b = np.asarray(b, float).ravel()
    mask = np.isfinite(a) & np.isfinite(b)
    if mask.sum() < 10:
        return np.nan
    a = a[mask]
    b = b[mask]
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= eps:
        return np.nan
    return float(1.0 - np.clip(np.dot(a, b) / denom, -1.0, 1.0))


def wasserstein_distance(q, a, b, eps=1e-12) -> float:
    q = np.asarray(q, float).ravel()
    a = np.clip(np.asarray(a, float).ravel(), 0.0, None)
    b = np.clip(np.asarray(b, float).ravel(), 0.0, None)
    mask = np.isfinite(q) & np.isfinite(a) & np.isfinite(b)
    if mask.sum() < 10:
        return np.nan
    q = q[mask]
    a = a[mask]
    b = b[mask]
    order = np.argsort(q)
    q = q[order]
    a = a[order]
    b = b[order]
    if np.sum(a) <= eps or np.sum(b) <= eps:
        return np.nan
    cdf_a = np.cumsum(a / np.sum(a))[:-1]
    cdf_b = np.cumsum(b / np.sum(b))[:-1]
    return float(np.sum(np.abs(cdf_a - cdf_b) * np.diff(q)))


class BremenFeatureError(ValueError):
    """Safe technical failure in Bremen scientific input or feature construction."""


def validate_bremen_shape(measurements) -> None:
    """Enforce the product contract independently of model availability."""
    sides = [getattr(m, "side", None) for m in measurements]
    if len(sides) != 6 or sides.count("LEFT") != 3 or sides.count("RIGHT") != 3:
        raise BremenFeatureError("requires_exactly_3_left_3_right")


def build_bremen_features(measurements) -> dict[str, float]:
    """Consume all six native q/intensity profiles in their supplied order."""
    validate_bremen_shape(measurements)
    # Internal opaque grouping key only; clinical labels and identifiers are unused.
    # NOTE (PR0154): structural canonical-measurement validation (1-D finite
    # strictly-increasing q matching intensity length) is performed by the
    # package runtime boundary and mapped to the same fixed
    # ``invalid_scientific_profiles`` reason, so no platform import appears in
    # this science module.
    try:
        frame = pd.DataFrame([
            {"patient_id": "case", "side": m.side, "q_range": np.asarray(m.q),
             "radial_profile_data": np.asarray(m.intensity)}
            for m in measurements
        ])
        config = AnalysisConfig()
        narrow = patient_lr_mean_metrics(frame, "case", config, config.q_roi)
        wide = patient_lr_mean_metrics(frame, "case", config, config.cosine_q_roi)
        q = narrow["q_common"]
        left, right = narrow["mu_left"], narrow["mu_right"]
        sl, sr = narrow["std_left"], narrow["std_right"]
        values = {}
        for index, zone in enumerate(config.zones, 1):
            mask = mask_q(q, *zone)
            values[f"weightedrms{index}"] = weighted_rms_band(left, right, sl, sr, mask)[0]
            values[f"sigma_l{index}"] = sigma_rms_band(sl, mask)
            values[f"sigma_r{index}"] = sigma_rms_band(sr, mask)
            values[f"mahalanobis{index}"] = mahalanobis_band(left, right, sl, sr, mask)[0]
            values[f"meanrms{index}"] = mean_rms_band(left, right, mask)
        values["peak14_intensity"] = peak14_intensity_from_means(
            q, left, right, config.peak_center, config.peak_halfwidth, config.peak_mode
        )
        values["mean_peak_value_raw"] = patient_mean_raw_peak14(frame, "case", config)
        values["wasserstein_distance_muLR"] = wasserstein_distance(q, left, right)
        values["cosine_distance_full_q2"] = cosine_distance(wide["mu_left"], wide["mu_right"])
        values["wasserstein_distance_full_q2"] = wasserstein_distance(
            wide["q_common"], wide["mu_left"], wide["mu_right"]
        )
    except Exception:
        raise BremenFeatureError("invalid_scientific_profiles") from None
    if not values["mean_peak_value_raw"] >= config.raw_peak_threshold:
        raise BremenFeatureError("raw_peak_gate_failed")
    return {name: values[name] for name in FEATURE_COLS}
