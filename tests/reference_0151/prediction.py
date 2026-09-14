"""Verbatim upstream portable scorer; test-only."""
from typing import Any
import numpy as np
import pandas as pd

def predict_proba_portable(
    portable: dict[str, Any],
    features: pd.DataFrame,
) -> np.ndarray:
    x = features.to_numpy(dtype=float)
    imputer = np.asarray(portable["imputer_statistics"], dtype=float)
    x = np.where(np.isfinite(x), x, imputer)
    mean = np.asarray(portable["scaler_mean"], dtype=float)
    scale = np.asarray(portable["scaler_scale"], dtype=float)
    scale = np.where(np.isclose(scale, 0.0), 1.0, scale)
    coefficient = np.asarray(portable["coef"], dtype=float)
    intercept = float(portable["intercept"])
    probability = 1.0 / (1.0 + np.exp(-(((x - mean) / scale) @ coefficient + intercept)))
    classes = list(portable.get("classes", [0, 1]))
    if classes == [0, 1]:
        return probability
    if classes == [1, 0]:
        return 1.0 - probability
    raise ValueError(f"Unsupported portable class order: {classes}")
