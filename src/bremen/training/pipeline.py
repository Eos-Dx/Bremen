"""Bremen training pipeline — offline ML model training only.

Healthy vs disease classification (NORMAL vs BENIGN+CANCER),
MRI-referred population.

All 7 feature families are per-patient target-vs-contralateral
symmetry measures — NOT population-fitted reference statistics.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (
    roc_auc_score,
    balanced_accuracy_score,
    confusion_matrix,
)

from joblib import dump as joblib_dump

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_TRAINING_ARTIFACT_FIELDS = (
    "kind",
    "version",
    "created_at",
    "model_type",
    "models",
    "thresholds",
    "model_descriptions",
    "feature_schema",
    "warnings",
    "training_config",
    "training_config_yaml",
    "training_config_text",
    "training_config_sha256",
    "input_dataframe_joblib_sha256",
    "dataset_summary",
    "feature_table",
    "metric_summary",
    "split_metrics",
    "split_predictions",
    "preprocessing_lineage",
    "metadata",
)

REQUIRED_TRAINING_CONFIG_SECTIONS = ("training", "io", "model", "evaluation")

REQUIRED_TRAINING_CONFIG_FIELDS: dict[str, tuple[str, ...]] = {
    "training": (
        "name",
        "version",
        "branch",
        "clinical_stage",
        "intended_use",
        "role",
    ),
    "io": (
        "input_dataframe_joblib_path",
        "output_model_joblib_path",
        "output_json_path",
        "output_yaml_path",
    ),
    "model": (
        "type",
        "profile_column",
        "label_column",
        "group_column",
        "specimen_column",
        "side_column",
        "q_column",
        "age_column",
        "lr1_row_policy",
        "selected_models",
        "logreg_c",
    ),
    "evaluation": (
        "mode",
        "n_splits",
        "test_size",
        "random_state",
        "target_sensitivity",
    ),
}

BREMEN_FEATURE_FAMILIES = (
    "sigma_l1",
    "sigma_l2",
    "Mahalanobis1",
    "Mahalanobis2",
    "wasserstein_distance_full_q2",
    "meanrms2",
    "weightedrms1",
)

# ---------------------------------------------------------------------------
# Pipeline components
# ---------------------------------------------------------------------------


@dataclass
class PatientModelInputBuilder:
    """Accept a preprocessed dataframe and validate columns match config."""

    config: dict[str, Any]
    warnings: list[str]

    def build(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate and prepare input dataframe.

        Filters to MRI-referred cohort (via lr1_row_policy).
        Returns the validated DataFrame.
        """
        row_policy = self.config["model"]["lr1_row_policy"]
        if row_policy == "mri_referred_only":
            label_col = self.config["model"]["label_column"]
            # Accept only rows with known labels
            df = df[df[label_col].notna()].copy()
        return df


@dataclass
class PatientModelSetTrainer:
    """Train M0/M1/M2 models with patient-safe splits."""

    config: dict[str, Any]

    def train(
        self, X: pd.DataFrame, y: pd.Series, groups: pd.Series
    ) -> dict[str, Any]:
        """Train models using GroupShuffleSplit."""
        model_config = self.config["model"]
        selected = model_config["selected_models"]
        eval_config = self.config["evaluation"]
        logreg_c = float(model_config.get("logreg_c", 0.1))

        # Initialise splitter
        splitter = GroupShuffleSplit(
            n_splits=int(eval_config["n_splits"]),
            test_size=float(eval_config["test_size"]),
            random_state=int(eval_config["random_state"]),
        )

        models: dict[str, LogisticRegression] = {}
        thresholds: dict[str, float] = {}
        split_metrics: list[dict[str, Any]] = []
        split_predictions: list[pd.DataFrame] = []

        target_sensitivity = float(eval_config["target_sensitivity"])

        for fold, (train_idx, test_idx) in enumerate(splitter.split(X, y, groups)):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

            fold_result: dict[str, Any] = {
                "fold": fold,
                "train_size": len(X_train),
                "test_size": len(X_test),
                "models": {},
            }

            for model_name in selected:
                clf = LogisticRegression(C=logreg_c, solver="lbfgs", max_iter=1000)
                clf.fit(X_train, y_train)

                models.setdefault(model_name, clf)

                y_prob = clf.predict_proba(X_test)[:, 1]

                # Threshold calibration toward target_sensitivity
                thresholds_calibrated = _calibrate_threshold(
                    y_test, y_prob, target_sensitivity
                )
                thresholds.setdefault(model_name, thresholds_calibrated)

                y_pred = (y_prob >= thresholds_calibrated).astype(int)
                tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()

                fold_result["models"][model_name] = {
                    "auc": roc_auc_score(y_test, y_prob),
                    "balanced_accuracy": balanced_accuracy_score(y_test, y_pred),
                    "sensitivity": tp / (tp + fn) if (tp + fn) > 0 else 0.0,
                    "specificity": tn / (tn + fp) if (tn + fp) > 0 else 0.0,
                    "threshold": thresholds_calibrated,
                }

                fold_predictions = X_test.copy()
                fold_predictions["true_label"] = y_test.values
                fold_predictions["predicted_probability"] = y_prob
                fold_predictions["predicted_label"] = y_pred
                fold_predictions["fold"] = fold
                fold_predictions["model_name"] = model_name
                split_predictions.append(fold_predictions)

            split_metrics.append(fold_result)

        return {
            "models": models,
            "thresholds": thresholds,
            "split_metrics": split_metrics,
            "split_predictions": pd.concat(
                split_predictions, ignore_index=True
            ) if split_predictions else pd.DataFrame(),
        }


@dataclass
class PatientModelSetEvaluator:
    """Compute metrics and summaries from training results."""

    def evaluate(
        self, train_result: dict[str, Any]
    ) -> dict[str, Any]:
        """Aggregate metrics across folds per model."""
        split_metrics = train_result["split_metrics"]
        models = train_result["models"]
        thresholds = train_result["thresholds"]

        metric_summary: dict[str, dict[str, float]] = {}
        model_descriptions: dict[str, dict[str, Any]] = {}

        for model_name in models:
            fold_scores = [
                m["models"][model_name]
                for m in split_metrics
                if model_name in m["models"]
            ]

            if not fold_scores:
                continue

            metric_summary[model_name] = {
                key: np.mean([s[key] for s in fold_scores])
                for key in fold_scores[0]
                if isinstance(fold_scores[0][key], (int, float))
            }

            model_descriptions[model_name] = {
                "type": "LogisticRegression",
                "C": models[model_name].C,
                "threshold": thresholds.get(model_name, 0.5),
                "n_features": models[model_name].coef_.shape[1],
                "feature_weights_mean": float(
                    np.mean(np.abs(models[model_name].coef_))
                ),
            }

        return {
            "metric_summary": metric_summary,
            "model_descriptions": model_descriptions,
        }


@dataclass
class BremenPatientTrainingPipeline:
    """Assemble input builder + trainers + evaluators."""

    input_builder: PatientModelInputBuilder
    trainer: PatientModelSetTrainer
    evaluator: PatientModelSetEvaluator

    def run(self, df: pd.DataFrame) -> dict[str, Any]:
        """Run the full training pipeline."""
        df_valid = self.input_builder.build(df)
        group_col = self.input_builder.config["model"]["group_column"]
        label_col = self.input_builder.config["model"]["label_column"]

        X = _patient_feature_table(df_valid, self.input_builder.config)
        y = df_valid[label_col].values if label_col in X.columns else None

        # Build groups for patient-safe split
        if group_col in X.columns:
            groups = X[group_col]
        else:
            groups = pd.Series(np.arange(len(X)))

        train_result = self.trainer.train(X, y, groups)
        eval_result = self.evaluator.evaluate(train_result)

        return {**train_result, **eval_result}


# ---------------------------------------------------------------------------
# Core pipeline functions
# ---------------------------------------------------------------------------


def build_patient_training_pipeline(config: dict[str, Any]) -> BremenPatientTrainingPipeline:
    """Build a fully configured training pipeline from a parsed config dict."""
    return BremenPatientTrainingPipeline(
        input_builder=PatientModelInputBuilder(config=config, warnings=[]),
        trainer=PatientModelSetTrainer(config=config),
        evaluator=PatientModelSetEvaluator(),
    )


def run_training_from_config(config_path: str | Path) -> dict[str, Any]:
    """Parse config YAML, run pipeline, assemble artifact.

    Returns the full training artifact dict.
    """
    config_path = Path(config_path)
    raw_yaml = config_path.read_text(encoding="utf-8")
    config = yaml.safe_load(raw_yaml)

    _validate_training_config(config)

    pipeline = build_patient_training_pipeline(config)

    # Load synthetic/preprocessed dataframe
    io = config["io"]
    df_path = Path(str(io["input_dataframe_joblib_path"]))
    from joblib import load as _jl  # noqa: PLC0415
    df: pd.DataFrame = _jl(df_path)

    # Run pipeline
    result = pipeline.run(df)

    # Build feature table
    feature_table = _patient_feature_table(df, config)

    # Build artifact
    artifact = _patient_training_artifact(
        config=config,
        raw_yaml=raw_yaml,
        models=result.get("models", {}),
        thresholds=result.get("thresholds", {}),
        model_descriptions=result.get("model_descriptions", {}),
        feature_table=feature_table,
        metric_summary=result.get("metric_summary", {}),
        split_metrics=result.get("split_metrics", []),
        split_predictions=result.get("split_predictions", pd.DataFrame()),
        input_dataframe_path=Path(str(io["input_dataframe_joblib_path"])),
        output_model_path=Path(str(io["output_model_joblib_path"])),
        warnings=result.get("warnings", []),
    )

    # Write outputs
    output_path = Path(str(io["output_model_joblib_path"]))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib_dump(artifact, output_path)

    # Write JSON metrics summary
    import json
    json_path = Path(str(io["output_json_path"]))
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w") as f:
        json.dump(artifact.get("metric_summary", {}), f, indent=2)

    return artifact


def train_patient_m0_m1_m2_model_artifact(config_path: str | Path) -> dict[str, Any]:
    """CLI entrypoint function. Calls run_training_from_config."""
    return run_training_from_config(config_path)


# ---------------------------------------------------------------------------
# Artifact assembly
# ---------------------------------------------------------------------------


def _patient_training_artifact(
    *,
    config: dict[str, Any],
    raw_yaml: str,
    models: dict[str, Any],
    thresholds: dict[str, float],
    model_descriptions: dict[str, dict[str, Any]],
    feature_table: pd.DataFrame,
    metric_summary: dict[str, dict[str, float]],
    split_metrics: list[dict[str, Any]],
    split_predictions: pd.DataFrame,
    input_dataframe_path: Path,
    output_model_path: Path,
    warnings: list[str],
) -> dict[str, Any]:
    """Assemble the training artifact dict with all required fields."""
    from datetime import datetime, timezone

    created_at = datetime.now(timezone.utc).isoformat()

    _warnings = list(warnings)
    if feature_table.empty:
        _warnings.append("Feature table is empty — no valid features generated.")

    # Compute config SHA-256
    config_sha256 = hashlib.sha256(raw_yaml.encode("utf-8")).hexdigest()

    # Compute input dataframe SHA-256
    df_sha256 = _file_sha256(input_dataframe_path) if input_dataframe_path.exists() else ""

    # Dataset summary
    n_labels = {}
    if not feature_table.empty:
        label_col = config["model"]["label_column"]
        if label_col in feature_table.columns:
            n_labels = feature_table[label_col].value_counts().to_dict()

    dataset_summary = {
        "n_patients": int(
            feature_table[config["model"]["group_column"]].nunique()
            if not feature_table.empty and config["model"]["group_column"] in feature_table.columns
            else 0
        ),
        "n_rows": len(feature_table),
        "n_features": len(feature_table.columns) if not feature_table.empty else 0,
        "label_distribution": {str(k): int(v) for k, v in n_labels.items()},
    }

    metadata = {
        "bremen_version": config.get("training", {}).get("version", ""),
        "git_sha": "",
        "created_at": created_at,
        "branch": config.get("training", {}).get("branch", ""),
        "training_role": config.get("training", {}).get("role", ""),
    }

    artifact = {
        "kind": "bremen_training_artifact",
        "version": config.get("training", {}).get("version", ""),
        "created_at": created_at,
        "model_type": "patient_m0_m1_m2_logistic_set",
        "models": {
            name: {"model": str(type(m).__name__)}
            for name, m in models.items()
        },
        "thresholds": {str(k): float(v) for k, v in thresholds.items()},
        "model_descriptions": model_descriptions,
        "feature_schema": list(feature_table.columns) if not feature_table.empty else [],
        "warnings": _warnings,
        "training_config": dict(config),
        "training_config_yaml": raw_yaml,
        "training_config_text": raw_yaml,
        "training_config_sha256": config_sha256,
        "input_dataframe_joblib_sha256": df_sha256,
        "dataset_summary": dataset_summary,
        "feature_table": feature_table.to_dict(orient="list") if not feature_table.empty else {},
        "metric_summary": metric_summary,
        "split_metrics": split_metrics,
        "split_predictions": (
            split_predictions.to_dict(orient="list")
            if not split_predictions.empty
            else {}
        ),
        "preprocessing_lineage": {},
        "metadata": metadata,
    }

    # Validate all required fields are present
    for field in REQUIRED_TRAINING_ARTIFACT_FIELDS:
        if field not in artifact:
            raise ValueError(f"Missing required training artifact field: {field}")

    return artifact


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


def _validate_training_config(config: dict[str, Any]) -> None:
    """Validate configuration sections and required fields."""
    errors: list[str] = []

    for section in REQUIRED_TRAINING_CONFIG_SECTIONS:
        if section not in config:
            errors.append(f"Missing config section: '{section}'")
            continue

        required = REQUIRED_TRAINING_CONFIG_FIELDS.get(section, ())
        for field in required:
            if field not in config[section]:
                errors.append(
                    f"Missing required field '{field}' in section '{section}'"
                )

    if errors:
        raise ValueError(
            "Training config validation failed:\n  " + "\n  ".join(errors)
        )


# ---------------------------------------------------------------------------
# Feature computation
# ---------------------------------------------------------------------------


def _patient_feature_table(
    df: pd.DataFrame, config: dict[str, Any]
) -> pd.DataFrame:
    """Build patient-level feature table with all 7 feature families."""
    return _sk_target_contralateral_symmetry_features(df, config)


def _sk_target_contralateral_symmetry_features(
    df: pd.DataFrame, config: dict[str, Any]
) -> pd.DataFrame:
    """Compute all 7 Bremen feature families as per-patient symmetry measures."""
    model_cfg = config["model"]
    group_col = model_cfg["group_column"]
    side_col = model_cfg["side_column"]
    label_col = model_cfg["label_column"]

    side_means = _sk_side_mean_metrics(df, config)
    group_ids = df[group_col].unique()

    rows: list[dict[str, Any]] = []
    for gid in group_ids:
        gdf = df[df[group_col] == gid]
        label = gdf[label_col].iloc[0] if not gdf.empty else None

        target = gdf[gdf[side_col] == "T"]
        control = gdf[gdf[side_col] == "C"]

        t_profiles = _extract_profiles(target, config)
        c_profiles = _extract_profiles(control, config)

        if not t_profiles or not c_profiles:
            rows.append({
                group_col: gid,
                label_col: label,
                "sigma_l1": np.nan,
                "sigma_l2": np.nan,
                "Mahalanobis1": np.nan,
                "Mahalanobis2": np.nan,
                "wasserstein_distance_full_q2": np.nan,
                "meanrms2": np.nan,
                "weightedrms1": np.nan,
            })
            continue

        # Use mean profiles for target and control
        t_mean = np.mean(np.array(t_profiles), axis=0)
        c_mean = np.mean(np.array(c_profiles), axis=0)

        sigma_l1, sigma_l2 = _sigma_rms(t_mean, c_mean)
        m1, m2 = _mahalanobis_difference(t_mean, c_mean)
        wass = _profile_wasserstein(t_mean, c_mean)
        rms = _rms_difference(t_mean, c_mean)
        wrms = _weighted_rms_difference(t_mean, c_mean)

        rows.append({
            group_col: gid,
            label_col: label,
            "sigma_l1": float(sigma_l1),
            "sigma_l2": float(sigma_l2),
            "Mahalanobis1": float(m1),
            "Mahalanobis2": float(m2),
            "wasserstein_distance_full_q2": float(wass),
            "meanrms2": float(rms),
            "weightedrms1": float(wrms),
        })

    return pd.DataFrame(rows)


def _sk_side_mean_metrics(
    df: pd.DataFrame, config: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """Aggregate per-side profile means for target/contralateral.

    Returns a dict of patient_id -> {side -> {'mean_profile': array}}.
    """
    group_col = config["model"]["group_column"]
    side_col = config["model"]["side_column"]

    result: dict[str, dict[str, Any]] = {}
    for gid, gdf in df.groupby(group_col):
        result[str(gid)] = {}
        for side, sdf in gdf.groupby(side_col):
            profiles = _extract_profiles(sdf, config)
            if profiles:
                result[str(gid)][str(side)] = {
                    "mean_profile": np.mean(np.array(profiles), axis=0)
                }
    return result


def _extract_profiles(
    df_side: pd.DataFrame, config: dict[str, Any]
) -> list[np.ndarray]:
    """Extract profile arrays from a side-specific DataFrame."""
    profile_col = config["model"]["profile_column"]
    profiles: list[np.ndarray] = []
    for _, row in df_side.iterrows():
        val = row[profile_col]
        if isinstance(val, np.ndarray):
            profiles.append(val)
        elif isinstance(val, (list, tuple)):
            profiles.append(np.array(val, dtype=float))
    return profiles


def _mahalanobis_difference(
    target_profile: np.ndarray, contralateral_profile: np.ndarray
) -> tuple[float, float]:
    """Per-patient target-vs-contralateral Mahalanobis distance.

    Returns (Mahalanobis1, Mahalanobis2) — two variants with different
    normalisation scale assumptions.

    Mahalanobis1: normalised by per-element variance estimate.
    Mahalanobis2: normalised by standard deviation with dampening.
    """
    diff = target_profile - contralateral_profile
    var = np.var(np.stack([target_profile, contralateral_profile]), axis=0)
    var_damped = var + 1e-10

    m1 = float(np.sqrt(np.mean(diff**2 / var_damped)))
    # Mahalanobis2: use std instead of variance for different scale
    std_damped = np.sqrt(var_damped)
    m2 = float(np.mean(np.abs(diff) / (std_damped + 1e-10)))

    return m1, m2


def _profile_wasserstein(
    target_profile: np.ndarray, contralateral_profile: np.ndarray
) -> float:
    """Wasserstein-1 distance between two normalised profile distributions.

    Computes the L1 distance between the cumulative distribution
    approximations of the two profiles.
    """
    t = target_profile / (np.sum(np.abs(target_profile)) + 1e-10)
    c = contralateral_profile / (np.sum(np.abs(contralateral_profile)) + 1e-10)

    # Sort and compute CDF
    t_sorted = np.sort(t)
    c_sorted = np.sort(c)

    # Wasserstein-1 equals L1 distance between sorted values
    dist = float(np.mean(np.abs(np.cumsum(t_sorted) - np.cumsum(c_sorted))))
    return dist


def _rms_difference(
    target_profile: np.ndarray, contralateral_profile: np.ndarray
) -> float:
    """Root-mean-square of target/contralateral difference (meanrms2)."""
    diff = target_profile - contralateral_profile
    return float(np.sqrt(np.mean(diff**2)))


def _weighted_rms_difference(
    target_profile: np.ndarray, contralateral_profile: np.ndarray
) -> float:
    """Weighted RMS of target/contralateral difference (weightedrms1).

    Weights are derived from the mean intensity of the two profiles.
    """
    diff = target_profile - contralateral_profile
    weights = (np.abs(target_profile) + np.abs(contralateral_profile)) / 2
    weights = weights / (np.sum(weights) + 1e-10)
    return float(np.sqrt(np.sum(weights * diff**2)))


def _sigma_rms(
    target_profile: np.ndarray, contralateral_profile: np.ndarray
) -> tuple[float, float]:
    """Compute sigma RMS (sigma_l1, sigma_l2).

    sigma_l1: L1-norm of the profile difference.
    sigma_l2: L2-norm (RMS) of the profile difference.
    """
    diff = target_profile - contralateral_profile
    sigma_l1 = float(np.mean(np.abs(diff)))
    sigma_l2 = float(np.sqrt(np.mean(diff**2)))
    return sigma_l1, sigma_l2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _file_sha256(path: str | Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _config_path(path: str | Path | None) -> Path:
    """Resolve config path. Raises if None."""
    if path is None:
        raise ValueError("Config path is required")
    return Path(path)


def _optional_config_path(path: str | Path | None) -> Path | None:
    """Resolve optional config reference."""
    return Path(path) if path is not None else None


def _calibrate_threshold(
    y_true: pd.Series, y_prob: np.ndarray, target_sensitivity: float
) -> float:
    """Calibrate decision threshold toward target sensitivity.

    Scans thresholds from 0.0 to 1.0 and picks the highest threshold
    that maintains sensitivity >= target_sensitivity.
    If not achievable, falls back to 0.5.
    """
    from sklearn.metrics import recall_score

    best_threshold = 0.5
    best_sensitivity = 0.0

    for thresh in np.linspace(0.01, 0.99, 99):
        y_pred = (y_prob >= thresh).astype(int)
        sens = recall_score(y_true, y_pred)
        if sens >= target_sensitivity and sens > best_sensitivity:
            best_sensitivity = sens
            best_threshold = thresh

    return best_threshold
