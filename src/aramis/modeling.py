"""Modeling helpers for Aramis research-draft classifiers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import auc, roc_auc_score, roc_curve
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


LABEL_MAP = {"BENIGN": 0, "CANCER": 1}


@dataclass(frozen=True)
class RepeatedLogisticResult:
    """Repeated patient-safe split result for a binary Aramis model."""

    predictions: pd.DataFrame
    split_metrics: pd.DataFrame
    roc_curves: list[dict[str, Any]]
    mean_fpr: np.ndarray
    mean_tpr: np.ndarray
    mean_auc: float
    std_auc: float


def load_one_to_many_dataframe(path: str | Path) -> pd.DataFrame:
    """Load one-to-many preprocessing joblib DataFrame."""
    loaded = joblib.load(Path(path))
    if not isinstance(loaded, pd.DataFrame):
        raise TypeError("One-to-many joblib must contain a pandas DataFrame.")
    return loaded


def summarize_one_to_many_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return basic row/patient/specimen/label counts."""
    _require_columns(df, ["patientId", "specimenId", "product_status_group"])
    return pd.DataFrame(
        [
            {
                "rows": int(len(df)),
                "patients": int(df["patientId"].astype(str).nunique()),
                "specimens": int(df["specimenId"].astype(str).nunique()),
                "BENIGN_rows": int((df["product_status_group"] == "BENIGN").sum()),
                "CANCER_rows": int((df["product_status_group"] == "CANCER").sum()),
            }
        ]
    )


def fit_repeated_one_to_many_logistic(
    df: pd.DataFrame,
    *,
    n_splits: int = 20,
    test_size: float = 0.30,
    random_state: int = 42,
    profile_column: str = "radial_profile_data",
    label_column: str = "product_status_group",
    group_column: str = "patientId",
    logreg_c: float = 1.0,
) -> RepeatedLogisticResult:
    """Train LogisticRegression on full normalized profiles over repeated splits.

    Splits are grouped by ``patientId`` so the same patient never appears in
    train and test in one split.
    """
    _validate_binary_frame(df, profile_column, label_column, group_column)
    x = profile_matrix(df, profile_column)
    y = df[label_column].map(LABEL_MAP).astype(int).to_numpy()
    groups = df[group_column].astype(str).to_numpy()

    predictions: list[pd.DataFrame] = []
    metrics: list[dict[str, Any]] = []
    curves: list[dict[str, Any]] = []
    mean_fpr = np.linspace(0.0, 1.0, 101)
    interpolated_tpr: list[np.ndarray] = []

    for split_id, train_idx, test_idx in _patient_safe_splits(
        y,
        groups,
        n_splits=n_splits,
        test_size=test_size,
        random_state=random_state,
    ):
        model = _logistic_pipeline(logreg_c=logreg_c, random_state=random_state + split_id)
        model.fit(x[train_idx], y[train_idx])
        y_score = model.predict_proba(x[test_idx])[:, 1]
        fpr, tpr, thresholds = roc_curve(y[test_idx], y_score)
        split_auc = float(roc_auc_score(y[test_idx], y_score))
        interp_tpr = np.interp(mean_fpr, fpr, tpr)
        interp_tpr[0] = 0.0
        interpolated_tpr.append(interp_tpr)

        curves.append(
            {
                "split_id": split_id,
                "fpr": fpr,
                "tpr": tpr,
                "thresholds": thresholds,
                "auc": split_auc,
            }
        )
        metrics.append(
            _split_metric_row(
                df,
                y,
                groups,
                train_idx=train_idx,
                test_idx=test_idx,
                split_id=split_id,
                auc_value=split_auc,
            )
        )
        predictions.append(
            _prediction_frame(
                df,
                y[test_idx],
                y_score,
                test_idx=test_idx,
                split_id=split_id,
            )
        )

    mean_tpr = np.mean(np.vstack(interpolated_tpr), axis=0)
    mean_tpr[-1] = 1.0
    split_metrics = pd.DataFrame(metrics)
    return RepeatedLogisticResult(
        predictions=pd.concat(predictions, ignore_index=True),
        split_metrics=split_metrics,
        roc_curves=curves,
        mean_fpr=mean_fpr,
        mean_tpr=mean_tpr,
        mean_auc=float(auc(mean_fpr, mean_tpr)),
        std_auc=float(split_metrics["roc_auc"].std(ddof=0)),
    )


def profile_matrix(df: pd.DataFrame, profile_column: str) -> np.ndarray:
    """Stack one profile-array column into a 2D model matrix."""
    _require_columns(df, [profile_column])
    profiles = [np.asarray(value, dtype=float) for value in df[profile_column]]
    lengths = {profile.size for profile in profiles}
    if len(lengths) != 1:
        raise ValueError(f"Profiles in {profile_column!r} must have equal length.")
    x = np.vstack(profiles)
    if not np.isfinite(x).all():
        raise ValueError(f"Profiles in {profile_column!r} contain non-finite values.")
    return x


def _patient_safe_splits(
    y: np.ndarray,
    groups: np.ndarray,
    *,
    n_splits: int,
    test_size: float,
    random_state: int,
):
    if n_splits < 1:
        raise ValueError("n_splits must be at least 1.")
    if not (0.0 < float(test_size) < 1.0):
        raise ValueError("test_size must be in (0, 1).")

    seen = 0
    seed = int(random_state)
    attempts = 0
    while seen < int(n_splits) and attempts < int(n_splits) * 200:
        splitter = GroupShuffleSplit(
            n_splits=1,
            test_size=float(test_size),
            random_state=seed + attempts,
        )
        train_idx, test_idx = next(splitter.split(np.zeros_like(y), y, groups))
        attempts += 1
        if len(np.unique(y[train_idx])) < 2 or len(np.unique(y[test_idx])) < 2:
            continue
        if set(groups[train_idx]).intersection(set(groups[test_idx])):
            raise RuntimeError("Patient leakage detected in grouped split.")
        yield seen, train_idx, test_idx
        seen += 1

    if seen != int(n_splits):
        raise ValueError("Could not create enough patient-safe two-class splits.")


def _logistic_pipeline(*, logreg_c: float, random_state: int) -> Pipeline:
    return Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "logreg",
                LogisticRegression(
                    C=float(logreg_c),
                    class_weight="balanced",
                    max_iter=5000,
                    random_state=int(random_state),
                    solver="lbfgs",
                ),
            ),
        ]
    )


def _split_metric_row(
    df: pd.DataFrame,
    y: np.ndarray,
    groups: np.ndarray,
    *,
    train_idx: np.ndarray,
    test_idx: np.ndarray,
    split_id: int,
    auc_value: float,
) -> dict[str, Any]:
    return {
        "split_id": int(split_id),
        "roc_auc": float(auc_value),
        "train_rows": int(train_idx.size),
        "test_rows": int(test_idx.size),
        "train_patients": int(pd.Series(groups[train_idx]).nunique()),
        "test_patients": int(pd.Series(groups[test_idx]).nunique()),
        "train_benign_rows": int((y[train_idx] == 0).sum()),
        "train_cancer_rows": int((y[train_idx] == 1).sum()),
        "test_benign_rows": int((y[test_idx] == 0).sum()),
        "test_cancer_rows": int((y[test_idx] == 1).sum()),
        "test_specimens": int(df.iloc[test_idx]["specimenId"].astype(str).nunique()),
    }


def _prediction_frame(
    df: pd.DataFrame,
    y_true: np.ndarray,
    y_score: np.ndarray,
    *,
    test_idx: np.ndarray,
    split_id: int,
) -> pd.DataFrame:
    keep = [
        column
        for column in ("patientId", "specimenId", "measurementId", "product_status_group")
        if column in df.columns
    ]
    out = df.iloc[test_idx][keep].reset_index(drop=True)
    out["split_id"] = int(split_id)
    out["y_true"] = np.asarray(y_true, dtype=int)
    out["p_cancer"] = np.asarray(y_score, dtype=float)
    return out


def _validate_binary_frame(
    df: pd.DataFrame,
    profile_column: str,
    label_column: str,
    group_column: str,
) -> None:
    _require_columns(
        df,
        [profile_column, label_column, group_column, "specimenId"],
    )
    labels = set(df[label_column].dropna().astype(str).unique())
    if labels != set(LABEL_MAP):
        raise ValueError(f"Expected only BENIGN/CANCER labels, got: {sorted(labels)}")
    if df[group_column].isna().any():
        raise ValueError(f"Missing {group_column} values are not allowed.")


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns: {missing}")
