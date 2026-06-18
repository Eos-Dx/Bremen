from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

DEFAULT_EXPERIMENT_NAME = "Aramis"


def build_run_name(product_name: str = "Aramis") -> str:
    """Return a stable human-readable MLflow run name."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{product_name.lower()}_draft_{stamp}"


def dataset_fingerprint(df: pd.DataFrame) -> str:
    """Hash a DataFrame including index, columns, and values."""
    row_hashes = pd.util.hash_pandas_object(df, index=True).to_numpy()
    payload = row_hashes.tobytes() + json.dumps(list(df.columns)).encode()
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def log_product_run(
    *,
    tracking_uri: str,
    experiment_name: str,
    run_name: str,
    product_name: str,
    preprocessing_config: dict[str, Any],
    product_filter_rules: dict[str, Any],
    dataset_df: pd.DataFrame,
    model: Any,
    metrics: dict[str, float],
    params: dict[str, Any],
    artifacts_dir: Path,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Log preprocessing, dataset, model, and metrics to MLflow.

    Set ``dry_run=True`` to write the exact artifacts locally without requiring
    an MLflow server or installed MLflow package.
    """
    artifacts_dir = Path(artifacts_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    dataset_path = artifacts_dir / "preprocessed_dataset.parquet"
    preprocessing_path = artifacts_dir / "preprocessing_config.json"
    filter_rules_path = artifacts_dir / "product_filter_rules.json"
    feature_schema_path = artifacts_dir / "feature_schema.json"
    metrics_path = artifacts_dir / "metrics.json"
    params_path = artifacts_dir / "params.json"
    model_path = artifacts_dir / "model.joblib"

    try:
        dataset_df.to_parquet(dataset_path, index=False)
    except ImportError:
        dataset_path = artifacts_dir / "preprocessed_dataset.csv"
        dataset_df.to_csv(dataset_path, index=False)
    _write_json(preprocessing_path, preprocessing_config)
    _write_json(filter_rules_path, product_filter_rules)
    _write_json(
        feature_schema_path,
        {
            "columns": list(dataset_df.columns),
            "dtypes": {col: str(dtype) for col, dtype in dataset_df.dtypes.items()},
        },
    )
    _write_json(metrics_path, metrics)
    _write_json(params_path, params)
    joblib.dump(model, model_path)

    common = {
        "dry_run": bool(dry_run),
        "tracking_uri": tracking_uri,
        "experiment_name": experiment_name,
        "run_name": run_name,
        "product_name": product_name,
        "dataset_rows": int(len(dataset_df)),
        "dataset_columns": int(len(dataset_df.columns)),
        "dataset_fingerprint": dataset_fingerprint(dataset_df),
        "artifacts_dir": str(artifacts_dir),
    }

    if dry_run:
        return {**common, "mlflow_run_id": None}

    try:
        import mlflow
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "MLflow is not installed. Run: conda env update -f environment.yml"
        ) from exc

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run(run_name=run_name) as run:
        mlflow.set_tag("product", product_name)
        mlflow.set_tag("dataset_fingerprint", common["dataset_fingerprint"])
        mlflow.log_param("product_name", product_name)
        mlflow.log_param("dataset_rows", common["dataset_rows"])
        mlflow.log_param("dataset_columns", common["dataset_columns"])
        for key, value in params.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                mlflow.log_param(key, value)
        for key, value in metrics.items():
            mlflow.log_metric(key, float(value))
        for path in [
            dataset_path,
            preprocessing_path,
            filter_rules_path,
            feature_schema_path,
            metrics_path,
            params_path,
            model_path,
        ]:
            mlflow.log_artifact(str(path))
        if os.environ.get("ARAMIS_LOG_MLFLOW_MODEL", "0") == "1":
            mlflow.sklearn.log_model(model, artifact_path="sklearn_model")
        return {**common, "mlflow_run_id": run.info.run_id}
