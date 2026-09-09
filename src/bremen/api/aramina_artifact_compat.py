"""Bremen-owned compatibility bridge for Aramina pickle classes.

When the real Aramina model.joblib is deserialized via joblib,
pickle references ``aramina.m2q_model.GatedSymmetryLogistic``.
This module provides a minimal Bremen-owned implementation that
preserves exact prediction behavior using the unpickled fitted
attributes.

No external Aramina dependency. No provider URL. No HTTP.
All implementations are private to artifact loading.

PR0137 — real GatedSymmetryLogistic from live artifact inspection.
"""

from __future__ import annotations

import sys
import types
from typing import Any


# ---------------------------------------------------------------------------
# Real GatedSymmetryLogistic implementation
# ---------------------------------------------------------------------------


class GatedSymmetryLogistic:
    """Bremen-owned implementation of Aramina's GatedSymmetryLogistic.

    Preserves exact prediction behavior using unpickled fitted attributes:
    - base_fill_values_: default values for 3 base features
    - base_scaler_: StandardScaler for 3 base features
    - symmetry_means_: mean for 4 symmetry features
    - symmetry_scales_: scale for 4 symmetry features
    - logreg_: fitted LogisticRegression (7 features → 2 classes)
    - feature_names_: list of 7 feature names

    predict_proba(X) where X is a pandas DataFrame with 8 columns:
    1. Extract 3 base features
    2. Scale base features with base_scaler_
    3. Extract 4 symmetry features
    4. Gate symmetry: if symmetry_available == 1, apply
       (symmetry - means) / scales; else zero out
    5. Concatenate [scaled_base, gated_symmetry] = 7 features
    6. Feed to logreg_.predict_proba
    """

    def __init__(self, **kwargs: Any) -> None:
        self._params = kwargs

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)

    def __getstate__(self) -> dict[str, Any]:
        return self.__dict__.copy()

    def _matrix(self, X: Any) -> Any:
        """Build the 7-feature matrix from an 8-column DataFrame.

        X columns: profile_p_cancer_logit_average, age, age_available,
        sk_wasserstein_distance_full_q2, sk_weightedrms1, sk_weightedrms2,
        sk_mean_peak_value_abs_delta, symmetry_available

        Returns: numpy array of shape (n, 7)
        """
        import numpy as _np
        import pandas as _pd

        # Ensure X is a DataFrame
        if not isinstance(X, _pd.DataFrame):
            X = _pd.DataFrame(X)

        # 1. Extract and scale 3 base features
        base_cols = ["profile_p_cancer_logit_average", "age", "age_available"]
        base_values = X[base_cols].values.copy()
        base_scaled = self.base_scaler_.transform(base_values)

        # 2. Extract 4 symmetry features
        sym_cols = [
            "sk_wasserstein_distance_full_q2",
            "sk_weightedrms1",
            "sk_weightedrms2",
            "sk_mean_peak_value_abs_delta",
        ]
        sym_values = X[sym_cols].values.copy()

        # 3. Gate symmetry: if symmetry_available == 1, apply normalization
        sym_available = X["symmetry_available"].values
        sym_means = _np.array(self.symmetry_means_)
        sym_scales = _np.array(self.symmetry_scales_)

        for i in range(sym_values.shape[0]):
            if sym_available[i] == 1:
                # Normalize: (value - mean) / scale
                sym_values[i] = (sym_values[i] - sym_means) / sym_scales
            else:
                # Zero out gated symmetry features
                sym_values[i] = 0.0

        # 4. Concatenate: [scaled_base, gated_symmetry] = 7 features
        result = _np.hstack([base_scaled, sym_values])
        return result

    def predict_proba(self, X: Any) -> Any:
        """Predict class probabilities using the fitted logistic regression.

        X must be a pandas DataFrame with the 8 expected columns.
        Returns array of shape (n_samples, 2).
        """
        import numpy as _np

        matrix = self._matrix(X)
        return _np.asarray(self.logreg_.predict_proba(matrix), dtype=float)

    def predict(self, X: Any) -> Any:
        """Predict class labels."""
        import numpy as _np

        matrix = self._matrix(X)
        return _np.asarray(self.logreg_.predict(matrix), dtype=int)

    def get_params(self, deep: bool = True) -> dict[str, Any]:
        return {"logreg_c": getattr(self, "logreg_c", 1.0)}

    def set_params(self, **params: Any) -> "GatedSymmetryLogistic":
        for k, v in params.items():
            setattr(self, k, v)
        return self


# ---------------------------------------------------------------------------
# Module registration for pickle resolution
# ---------------------------------------------------------------------------


def ensure_compatibility_bridge() -> None:
    """Register the real GatedSymmetryLogistic in sys.modules.

    Must be called BEFORE the Aramina artifact is deserialized.
    Idempotent — safe to call multiple times.
    """
    if "aramina" not in sys.modules:
        sys.modules["aramina"] = types.ModuleType("aramina")
    if "aramina.m2q_model" not in sys.modules:
        mod = types.ModuleType("aramina.m2q_model")
        sys.modules["aramina.m2q_model"] = mod
    sys.modules["aramina.m2q_model"].GatedSymmetryLogistic = GatedSymmetryLogistic
