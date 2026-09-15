"""Core4 feature mathematics ported from the artifact producer's symmetry contract.

Bremen-owned implementation, no external Aramina import. v0.1 and v0.2 retain
separate ROI, normalization, and availability rules. Neutral symmetry values
are the trained missing-pair gate, never a substitute probability.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

CORE4 = (
    "sk_wasserstein_distance_full_q2",
    "sk_weightedrms1",
    "sk_weightedrms2",
    "sk_mean_peak_value_abs_delta",
)


def symmetry_features(
    df: pd.DataFrame, target_side: str, contract: str
) -> dict[str, float]:
    if contract not in {"aramina_sk_symmetry_v0_1", "aramina_sk_symmetry_v0_2"}:
        raise ValueError("Unsupported symmetry contract")
    legacy = contract == "aramina_sk_symmetry_v0_1"
    target = target_side.upper()
    control = "RIGHT" if target == "LEFT" else "LEFT"
    sides = df["side"].map(_normalize_side)
    nt, nc = int((sides == target).sum()), int((sides == control).sum())
    neutral = {**dict.fromkeys(CORE4, 0.0), "symmetry_available": 0.0}
    if nc == 0 or (not legacy and min(nt, nc) < 2):
        return neutral
    kw = {
        "profile_column": "radial_profile_data",
        "q_column": "q_range",
        "side_column": "side",
        "target_side_norm": target,
        "contralateral_side_norm": control,
    }
    metrics = _side_mean_metrics(
        df, **kw, q_roi=(7.5, 23.0) if legacy else (6.7, 23.0), legacy=legacy
    )
    full = _side_mean_metrics(df, **kw, q_roi=(2.0, 23.0), legacy=legacy)
    if not metrics or not full:
        return {**neutral, "symmetry_available": 1.0} if legacy else neutral
    q = metrics["q"]
    values = {
        "sk_wasserstein_distance_full_q2": _profile_wasserstein(
            full["q"], full["mu_target"], full["mu_contralateral"]
        ),
        "sk_mean_peak_value_abs_delta": _mean_peak_value_abs_delta(df, **kw),
    }
    for name, mask in [
        ("sk_weightedrms1", (q >= (7.0 if legacy else 6.7)) & (q <= 15.0)),
        ("sk_weightedrms2", (q >= 15.0) & (q <= 23.0)),
    ]:
        values[name] = _weighted_rms_difference(
            metrics["mu_target"],
            metrics["mu_contralateral"],
            metrics["std_target"],
            metrics["std_contralateral"],
            mask,
        )
    if not legacy and not all(np.isfinite(v) for v in values.values()):
        return neutral
    return {
        **{k: float(v) if np.isfinite(v) else 0.0 for k, v in values.items()},
        "symmetry_available": 1.0,
    }


def _side_mean_metrics(
    df: pd.DataFrame,
    *,
    profile_column: str,
    q_column: str,
    side_column: str,
    target_side_norm: str,
    contralateral_side_norm: str,
    q_roi: tuple[float, float],
    legacy: bool = False,
) -> dict[str, np.ndarray] | None:
    target_profiles: list[np.ndarray] = []
    contralateral_profiles: list[np.ndarray] = []
    q_common: np.ndarray | None = None
    for row in df.itertuples(index=False):
        side = _normalize_side(getattr(row, side_column))
        if side not in {target_side_norm, contralateral_side_norm}:
            continue
        q = np.asarray(getattr(row, q_column), dtype=float).ravel()
        y = np.asarray(getattr(row, profile_column), dtype=float).ravel()
        q, y = _profile_roi(q, y, q_roi, fallback_full_range=legacy)
        if q.size < 5:
            continue
        y = (
            _normalize_profile_near_minimum(q, _smooth_profile(y))
            if legacy
            else _smooth_profile(y)
        )
        if q_common is None:
            q_common = q
        y_common = np.interp(q_common, q, y)
        if side == target_side_norm:
            target_profiles.append(y_common)
        else:
            contralateral_profiles.append(y_common)
    if q_common is None or not target_profiles or not contralateral_profiles:
        return None
    target = np.vstack(target_profiles)
    contralateral = np.vstack(contralateral_profiles)
    return {
        "q": q_common,
        "mu_target": np.mean(target, axis=0),
        "mu_contralateral": np.mean(contralateral, axis=0),
        "std_target": _profile_std(target),
        "std_contralateral": _profile_std(contralateral),
    }


def _profile_roi(
    q: np.ndarray,
    y: np.ndarray,
    q_roi: tuple[float, float],
    *,
    fallback_full_range: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    mask = (q >= float(q_roi[0])) & (q <= float(q_roi[1]))
    if fallback_full_range and int(mask.sum()) < 5:
        return q, y
    return q[mask], y[mask]


def _smooth_profile(y: np.ndarray) -> np.ndarray:
    if y.size < 7:
        return y
    window = min(11, y.size if y.size % 2 else y.size - 1)
    if window < 5:
        return y
    return savgol_filter(y, window_length=window, polyorder=min(3, window - 2))


def _normalize_profile_near_minimum(
    q: np.ndarray,
    y: np.ndarray,
    *,
    q0: float = 6.7,
    halfwidth: float = 0.25,
) -> np.ndarray:
    """Legacy v0.1 SK-only normalization retained for released artifacts."""
    mask = (q >= q0 - halfwidth) & (q <= q0 + halfwidth) & np.isfinite(y)
    baseline = (
        float(np.nanpercentile(y[mask], 5))
        if int(mask.sum()) >= 2
        else float(np.nanpercentile(y, 5))
    )
    if not np.isfinite(baseline) or abs(baseline) < 1e-12:
        baseline = 1.0
    return y / baseline


def _profile_std(values: np.ndarray) -> np.ndarray:
    return (
        np.zeros(values.shape[1])
        if values.shape[0] < 2
        else np.std(values, axis=0, ddof=1)
    )


def _weighted_rms_difference(
    a: np.ndarray, b: np.ndarray, std_a: np.ndarray, std_b: np.ndarray, mask: np.ndarray
) -> float:
    diff = np.asarray(a - b, dtype=float)
    variance = np.asarray(std_a**2 + std_b**2, dtype=float)
    good = mask & np.isfinite(diff) & np.isfinite(variance)
    if int(good.sum()) < 5:
        return np.nan
    floor = float(np.nanpercentile(variance[good], 5))
    weight = 1.0 / np.maximum(variance[good], floor + 1e-12)
    return float(np.sqrt(np.sum(weight * diff[good] ** 2) / np.sum(weight)))


def _peak_value(q: np.ndarray, y: np.ndarray, *, q_min: float, q_max: float) -> float:
    mask = (q >= q_min) & (q <= q_max) & np.isfinite(y)
    return float(np.nanmax(y[mask])) if int(mask.sum()) >= 3 else np.nan


def _mean_peak_value_abs_delta(
    df: pd.DataFrame,
    *,
    q_column: str,
    profile_column: str,
    side_column: str,
    target_side_norm: str,
    contralateral_side_norm: str,
) -> float:
    target_peak = _mean_peak_value_for_side(
        df,
        q_column=q_column,
        profile_column=profile_column,
        side_column=side_column,
        side_norm=target_side_norm,
    )
    contralateral_peak = _mean_peak_value_for_side(
        df,
        q_column=q_column,
        profile_column=profile_column,
        side_column=side_column,
        side_norm=contralateral_side_norm,
    )
    if not np.isfinite(target_peak) or not np.isfinite(contralateral_peak):
        return np.nan
    return float(abs(target_peak - contralateral_peak))


def _mean_peak_value_for_side(
    df: pd.DataFrame,
    *,
    q_column: str,
    profile_column: str,
    side_column: str,
    side_norm: str,
) -> float:
    values = []
    for side, q_raw, y_raw in df[[side_column, q_column, profile_column]].itertuples(
        index=False, name=None
    ):
        if _normalize_side(side) != side_norm:
            continue
        peak = _peak_value(
            np.asarray(q_raw, dtype=float).ravel(),
            np.asarray(y_raw, dtype=float).ravel(),
            q_min=13.0,
            q_max=14.8,
        )
        if np.isfinite(peak):
            values.append(peak)
    return float(np.mean(values)) if values else np.nan


def _profile_wasserstein(q: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    good = np.isfinite(q) & np.isfinite(a) & np.isfinite(b)
    if int(good.sum()) < 5:
        return np.nan
    qv = q[good]
    av = np.clip(a[good], 0.0, None)
    bv = np.clip(b[good], 0.0, None)
    if float(av.sum()) <= 1e-12 or float(bv.sum()) <= 1e-12:
        return np.nan
    order = np.argsort(qv)
    qv, av, bv = qv[order], av[order] / float(av.sum()), bv[order] / float(bv.sum())
    return float(np.sum(np.abs(np.cumsum(av)[:-1] - np.cumsum(bv)[:-1]) * np.diff(qv)))


def _normalize_side(value: Any) -> str | None:
    clean = str(value).strip().upper()
    if clean.startswith("LEFT"):
        return "LEFT"
    if clean.startswith("RIGHT"):
        return "RIGHT"
    return None
