"""Portable logistic regression inference — sklearn-free pure math inference.

The v0.1 model package uses the ``portable_logreg`` format: a plain Python
dict/list/float payload with coefficients, scaler statistics, and feature
columns.  No sklearn objects, no native sklearn ``predict_proba`` call.

This module validates the model package structure and runs inference using
only ``math`` and ``numpy``.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from bremen.api.preprocessing_bridge import BREMEN_V01_FEATURE_COLUMNS


class PortableLogRegModelError(Exception):
    """Portable logistic regression model validation or inference error."""


def validate_portable_logreg_model(package: dict) -> dict:
    """Validate a v0.1 portable_logreg model package.

    Checks:
    - ``portable_logreg`` key present.
    - ``feature_columns`` list matches ``BREMEN_V01_FEATURE_COLUMNS`` (15 cols, exact order).
    - ``imputer_statistics`` is a list of 15 numbers.
    - ``scaler_mean`` is a list of 15 numbers.
    - ``scaler_scale`` is a list of 15 numbers.
    - ``coef`` is a list of 15 numbers.
    - ``intercept`` is a number.
    - ``threshold`` is a number.

    Returns the validated package dict.
    Raises ``PortableLogRegModelError`` on any failure.
    """
    if "portable_logreg" not in package:
        raise PortableLogRegModelError(
            "Model package does not contain 'portable_logreg' key. "
            "Expected v0.1 portable_logreg format."
        )

    plr = package["portable_logreg"]

    _validate_field(plr, "feature_columns", list, 15)
    _validate_field(plr, "imputer_statistics", list, 15)
    _validate_field(plr, "scaler_mean", list, 15)
    _validate_field(plr, "scaler_scale", list, 15)
    _validate_field(plr, "coef", list, 15)

    for val_name in ("intercept", "threshold"):
        _validate_field(plr, val_name, (int, float), None)

    # Validate feature columns match
    actual_cols = [str(c) for c in plr["feature_columns"]]
    expected_cols = list(BREMEN_V01_FEATURE_COLUMNS)
    if actual_cols != expected_cols:
        raise PortableLogRegModelError(
            f"Feature columns mismatch. "
            f"Expected {len(expected_cols)} columns in exact order, "
            f"got {len(actual_cols)} columns. "
            f"Mismatch at index {_first_mismatch(actual_cols, expected_cols)}."
        )

    return package


def predict_proba_portable(
    package: dict,
    feature_vector: list[float],
    *,
    skip_validation: bool = False,
) -> dict[str, Any]:
    """Run portable logistic regression inference.

    Steps:
    1. Validate package if not already validated.
    2. Impute NaN features using ``imputer_statistics``.
    3. Scale using ``(x - scaler_mean) / scaler_scale``.
    4. Compute logit = ``dot(coef, scaled) + intercept``.
    5. Compute sigmoid probability.
    6. Apply threshold.

    Parameters
    ----------
    package : Validated v0.1 portable_logreg model package dict.
    feature_vector : 15-element feature vector from the preprocessing bridge.
    skip_validation : If True, skip model validation (use after
        ``validate_portable_logreg_model()`` has been called).

    Returns
    -------
    A dict with:
    - ``probability`` : float in [0.0, 1.0]
    - ``prediction`` : int (0 or 1)
    - ``threshold_applied`` : float
    """
    if not skip_validation:
        package = validate_portable_logreg_model(package)

    plr = package["portable_logreg"]
    features = np.array(feature_vector, dtype=np.float64)

    # 1. Impute NaN values
    imputer = np.array(plr["imputer_statistics"], dtype=np.float64)
    features = np.where(np.isnan(features), imputer, features)

    # 2. Scale
    scaler_mean = np.array(plr["scaler_mean"], dtype=np.float64)
    scaler_scale = np.array(plr["scaler_scale"], dtype=np.float64)
    scaled = (features - scaler_mean) / (scaler_scale + 1e-10)

    # 3. Compute logit
    coef = np.array(plr["coef"], dtype=np.float64)
    intercept = float(plr["intercept"])
    logit = float(np.dot(coef, scaled)) + intercept

    # 4. Sigmoid
    prob = 1.0 / (1.0 + math.exp(-logit))

    # 5. Apply threshold
    threshold = float(plr["threshold"])
    prediction = 1 if prob >= threshold else 0

    return {
        "probability": prob,
        "prediction": prediction,
        "threshold_applied": threshold,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_field(
    obj: dict,
    name: str,
    expected_type: type | tuple[type, ...],
    expected_length: int | None,
) -> None:
    """Validate a single field in the portable_logreg dict."""
    if name not in obj:
        raise PortableLogRegModelError(f"Missing 'portable_logreg.{name}'")

    val = obj[name]

    if not isinstance(val, expected_type):
        raise PortableLogRegModelError(
            f"'portable_logreg.{name}' must be {expected_type}, "
            f"got {type(val).__name__}"
        )

    if expected_length is not None and isinstance(val, list):
        if len(val) != expected_length:
            raise PortableLogRegModelError(
                f"'portable_logreg.{name}' must have {expected_length} elements, "
                f"got {len(val)}"
            )

        if name not in ("feature_columns",):
            for i, v in enumerate(val):
                if not isinstance(v, (int, float)):
                    raise PortableLogRegModelError(
                        f"'portable_logreg.{name}[{i}]' must be numeric, "
                        f"got {type(v).__name__}"
                    )


def _first_mismatch(
    actual: list[str], expected: list[str]
) -> int:
    """Return index of first mismatch, or -1."""
    for i, (a, e) in enumerate(zip(actual, expected)):
        if a != e:
            return i
    return -1 if len(actual) == len(expected) else min(len(actual), len(expected))


def adapt_model_package(package: dict) -> dict:
    """Adapt a real Bremen model package to the runtime-expected format.

    The real package stores ``feature_columns`` and ``threshold`` at root
    level.  This produces a compatible view without modifying the original
    dict.  Other root-level fields (``analysis_config``,
    ``decision_rule``) are preserved as-is.

    After adaptation, the ``portable_logreg`` sub-dict contains all fields
    needed by ``validate_portable_logreg_model`` and
    ``predict_proba_portable``.

    Returns the original package unchanged if it already has everything
    under ``portable_logreg``.
    """
    if "portable_logreg" not in package:
        return package
    plr = dict(package["portable_logreg"])
    needs_patch = False
    if "feature_columns" not in plr and "feature_columns" in package:
        plr["feature_columns"] = package["feature_columns"]
        needs_patch = True
    if "threshold" not in plr and "threshold" in package:
        plr["threshold"] = package["threshold"]
        needs_patch = True
    if needs_patch:
        patched = dict(package)
        patched["portable_logreg"] = plr
        return patched
    return package
