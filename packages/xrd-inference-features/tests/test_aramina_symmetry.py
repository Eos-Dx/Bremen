"""Standalone tests for xrd_inference_features.aramina_symmetry.

Must not import bremen. Covers the documented v0.1/v0.2 behavioral
differences: availability gate, ROI boundary, normalization, weighted-RMS
mask boundary, and neutral/finiteness fallback.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from xrd_inference_features.aramina_symmetry import CORE4, symmetry_features


def test_no_bremen_import() -> None:
    for name in sys.modules:
        assert not name.startswith("bremen"), name


def _profiles(n_target: int, n_contralateral: int, *, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    q = np.linspace(2.0, 25.0, 400)
    rows = []
    for _ in range(n_target):
        y = 1.0 + 0.05 * rng.standard_normal(q.size) + np.exp(-((q - 14.0) ** 2) / (2 * 0.3**2))
        rows.append({"side": "LEFT", "q_range": q, "radial_profile_data": y})
    for _ in range(n_contralateral):
        y = 1.0 + 0.05 * rng.standard_normal(q.size) + 0.8 * np.exp(-((q - 14.0) ** 2) / (2 * 0.3**2))
        rows.append({"side": "RIGHT", "q_range": q, "radial_profile_data": y})
    return pd.DataFrame(rows)


def test_core4_names_frozen() -> None:
    assert CORE4 == (
        "sk_wasserstein_distance_full_q2",
        "sk_weightedrms1",
        "sk_weightedrms2",
        "sk_mean_peak_value_abs_delta",
    )


def test_v0_1_available_with_single_contralateral() -> None:
    df = _profiles(n_target=1, n_contralateral=1, seed=1)
    out = symmetry_features(df, "left", "aramina_sk_symmetry_v0_1")
    assert out["symmetry_available"] == 1.0
    assert set(out) == set(CORE4) | {"symmetry_available"}


def test_v0_2_requires_at_least_two_each_side() -> None:
    df = _profiles(n_target=1, n_contralateral=1, seed=1)
    out = symmetry_features(df, "left", "aramina_sk_symmetry_v0_2")
    assert out["symmetry_available"] == 0.0
    assert all(out[name] == 0.0 for name in CORE4)


def test_v0_2_available_with_two_each_side() -> None:
    df = _profiles(n_target=2, n_contralateral=2, seed=2)
    out = symmetry_features(df, "left", "aramina_sk_symmetry_v0_2")
    assert out["symmetry_available"] == 1.0


def test_neutral_when_no_contralateral_rows() -> None:
    q = np.linspace(2.0, 25.0, 400)
    df = pd.DataFrame(
        [{"side": "LEFT", "q_range": q, "radial_profile_data": np.ones(q.size)}]
    )
    out_v1 = symmetry_features(df, "left", "aramina_sk_symmetry_v0_1")
    out_v2 = symmetry_features(df, "left", "aramina_sk_symmetry_v0_2")
    assert out_v1["symmetry_available"] == 0.0
    assert out_v2["symmetry_available"] == 0.0


def test_deterministic_same_input() -> None:
    df = _profiles(n_target=3, n_contralateral=3, seed=7)
    first = symmetry_features(df, "left", "aramina_sk_symmetry_v0_2")
    second = symmetry_features(df, "left", "aramina_sk_symmetry_v0_2")
    assert first == second
