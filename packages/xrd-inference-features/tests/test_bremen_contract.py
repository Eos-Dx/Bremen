"""Standalone tests for xrd_inference_features.bremen_contract.

These tests must not import bremen (enforced below) — the package has to be
testable fully independently of the Bremen application.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import pytest

from xrd_inference_features.bremen_contract import (
    FEATURE_COLS,
    BremenFeatureError,
    build_bremen_features_from_frame,
    wasserstein_distance,
    cosine_distance,
)


def test_no_bremen_import() -> None:
    assert "bremen" not in sys.modules
    for name in sys.modules:
        assert not name.startswith("bremen"), name


def test_feature_cols_exact_frozen_order() -> None:
    assert FEATURE_COLS == [
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


def _synthetic_frame(seed: int = 0, *, peak_scale: float = 1.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    q = np.linspace(2.0, 25.0, 400)
    rows = []
    for side in ("LEFT",) * 3 + ("RIGHT",) * 3:
        baseline = 0.3 + 0.02 * rng.standard_normal(q.size)
        peak = peak_scale * np.exp(-((q - 14.0) ** 2) / (2 * 0.3**2))
        intensity = baseline + peak + (0.1 if side == "LEFT" else 0.0)
        rows.append(
            {
                "side": side,
                "q_range": q,
                "radial_profile_data": intensity,
            }
        )
    return pd.DataFrame(rows)


def test_deterministic_on_frozen_fixture() -> None:
    frame = _synthetic_frame(seed=42)
    first = build_bremen_features_from_frame(frame)
    second = build_bremen_features_from_frame(frame)
    assert first == second
    assert list(first) == FEATURE_COLS
    for name in FEATURE_COLS:
        assert np.isfinite(first[name])


def test_raw_peak_gate_failed_below_threshold() -> None:
    frame = _synthetic_frame(seed=1, peak_scale=0.0)
    with pytest.raises(BremenFeatureError) as excinfo:
        build_bremen_features_from_frame(frame)
    assert str(excinfo.value) == "raw_peak_gate_failed"


def test_requires_exactly_3_left_3_right() -> None:
    frame = _synthetic_frame(seed=2)
    frame = frame.iloc[:5].copy()
    with pytest.raises(BremenFeatureError) as excinfo:
        build_bremen_features_from_frame(frame)
    assert str(excinfo.value) == "requires_exactly_3_left_3_right"


def test_invalid_profiles_rejected_on_empty_frame() -> None:
    with pytest.raises(BremenFeatureError) as excinfo:
        build_bremen_features_from_frame(pd.DataFrame())
    assert str(excinfo.value) == "invalid_scientific_profiles"


def test_wasserstein_neutral_on_too_few_points() -> None:
    q = np.array([1.0, 2.0])
    a = np.array([1.0, 2.0])
    b = np.array([1.0, 2.0])
    assert np.isnan(wasserstein_distance(q, a, b))


def test_cosine_distance_neutral_on_zero_vector() -> None:
    a = np.zeros(20)
    b = np.ones(20)
    assert np.isnan(cosine_distance(a, b))
