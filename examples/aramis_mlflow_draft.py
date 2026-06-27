"""Marimo draft for Aramis MLflow lineage."""

import marimo

__generated_with = "0.23.9"
app = marimo.App(width="medium")


@app.cell
def _():
    import sys
    from pathlib import Path

    import marimo as mo
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import balanced_accuracy_score, roc_auc_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    repo_root = (
        Path(__file__).resolve().parents[1]
        if "__file__" in globals()
        else Path.cwd()
    )
    src_path = repo_root / "src"
    if src_path.exists() and str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    from aramis import DEFAULT_EXPERIMENT_NAME, build_run_name, log_product_run

    return (
        DEFAULT_EXPERIMENT_NAME,
        LogisticRegression,
        Path,
        Pipeline,
        StandardScaler,
        balanced_accuracy_score,
        build_run_name,
        log_product_run,
        mo,
        np,
        pd,
        repo_root,
        roc_auc_score,
        train_test_split,
    )


@app.cell
def _(mo, repo_root):
    tracking_uri_input = mo.ui.text(
        label="MLflow tracking URI",
        value=f"file://{repo_root / 'mlruns'}",
        full_width=True,
    )
    dry_run_input = mo.ui.checkbox(label="dry run", value=True)
    mo.vstack(
        [
            mo.md("# Aramis MLflow draft"),
            mo.md(
                """
                This draft logs the full product run shape:

                ```text
                H5 -> product filter -> preprocessing -> dataset -> model -> metrics
                ```

                Default mode writes local artifacts only. Uncheck `dry run` after
                MLflow is installed to create a real MLflow run.
                """
            ),
            tracking_uri_input,
            dry_run_input,
        ]
    )
    return dry_run_input, tracking_uri_input


@app.cell
def _(dry_run_input, tracking_uri_input):
    tracking_uri = str(tracking_uri_input.value).strip()
    dry_run = bool(dry_run_input.value)
    return dry_run, tracking_uri


@app.cell
def _(np, pd):
    _rng = np.random.default_rng(42)
    _n = 80
    _q = np.linspace(2.0, 23.0, 120)
    _rows = []
    for _idx in range(_n):
        _label = int(_idx >= _n // 2)
        _profile = (
            np.sin(_q / 2.0)
            + 0.15 * _rng.normal(size=len(_q))
            + _label * np.exp(-((_q - 9.5) ** 2) / 3.0)
        )
        _rows.append(
            {
                "sample_id": f"S{_idx:03d}",
                "patient_id": f"P{_idx // 2:03d}",
                "diagnosis": "CANCER" if _label else "BENIGN",
                "cancer_status": _label,
                "snr": float(22.0 + _rng.normal()),
                **{f"q_{_j:03d}": float(_value) for _j, _value in enumerate(_profile)},
            }
        )

    dataset_df = pd.DataFrame(_rows)
    feature_columns = [col for col in dataset_df.columns if col.startswith("q_")]
    return dataset_df, feature_columns


@app.cell
def _(
    LogisticRegression,
    Pipeline,
    StandardScaler,
    balanced_accuracy_score,
    dataset_df,
    feature_columns,
    np,
    roc_auc_score,
    train_test_split,
):
    _X = dataset_df[feature_columns]
    _y = dataset_df["cancer_status"].astype(int)
    _train_idx, _test_idx = train_test_split(
        dataset_df.index,
        test_size=0.25,
        random_state=42,
        stratify=_y,
    )

    model = Pipeline(
        [
            ("scale", StandardScaler()),
            ("classifier", LogisticRegression(max_iter=1000, random_state=42)),
        ]
    )
    model.fit(_X.loc[_train_idx], _y.loc[_train_idx])
    _p_cancer = model.predict_proba(_X.loc[_test_idx])[:, 1]
    _prediction = (_p_cancer >= 0.5).astype(int)

    metrics = {
        "roc_auc": float(roc_auc_score(_y.loc[_test_idx], _p_cancer)),
        "balanced_accuracy": float(
            balanced_accuracy_score(_y.loc[_test_idx], _prediction)
        ),
    }
    predictions_df = dataset_df.loc[_test_idx, ["sample_id", "patient_id", "diagnosis"]].copy()
    predictions_df["p_cancer"] = _p_cancer
    predictions_df["predicted_diagnosis"] = np.where(_prediction == 1, "CANCER", "BENIGN")
    return metrics, model, predictions_df


@app.cell
def _(DEFAULT_EXPERIMENT_NAME, build_run_name, repo_root):
    preprocessing_config = {
        "h5_container_version": "v0.3",
        "source": "fake_dataset_until_real_h5_is_available",
        "pipeline": [
            "h5_to_df",
            "PatientFilter",
            "FaultyPixelDetector",
            "AzimuthalIntegration(error_model='poisson')",
            "SNRTransformer(snr_method='poisson')",
            "SNRFilter(min_snr_db=20.0)",
            "QRangeValueNormalizer(q_min=6.7, q_max=7.1, statistic='median')",
        ],
    }
    product_filter_rules = {
        "product": "Aramis",
        "task": "benign_vs_cancer",
        "positive_labels": ["CANCER", "PRE_CANCEROUS", "ATYPICAL"],
        "negative_labels": ["BENIGN", "NORMAL"],
    }
    params = {
        "model_type": "LogisticRegression",
        "threshold": 0.5,
        "split": "stratified_fake_demo",
        "snr_threshold_db": 20.0,
    }
    experiment_name = DEFAULT_EXPERIMENT_NAME
    run_name = build_run_name("Aramis")
    artifacts_dir = repo_root / "analysis" / run_name
    return (
        artifacts_dir,
        experiment_name,
        params,
        preprocessing_config,
        product_filter_rules,
        run_name,
    )


@app.cell
def _(
    artifacts_dir,
    dataset_df,
    dry_run,
    experiment_name,
    log_product_run,
    metrics,
    model,
    params,
    preprocessing_config,
    product_filter_rules,
    run_name,
    tracking_uri,
):
    mlflow_result = log_product_run(
        tracking_uri=tracking_uri,
        experiment_name=experiment_name,
        run_name=run_name,
        product_name="Aramis",
        preprocessing_config=preprocessing_config,
        product_filter_rules=product_filter_rules,
        dataset_df=dataset_df,
        model=model,
        metrics=metrics,
        params=params,
        artifacts_dir=artifacts_dir,
        dry_run=dry_run,
    )
    return (mlflow_result,)


@app.cell
def _(metrics, mlflow_result, mo, predictions_df):
    _head = predictions_df.head(8).to_string(index=False)
    mo.md(
        f"""
        ## Result

        ```text
        dry_run = {mlflow_result["dry_run"]}
        mlflow_run_id = {mlflow_result["mlflow_run_id"]}
        tracking_uri = {mlflow_result["tracking_uri"]}
        artifacts_dir = {mlflow_result["artifacts_dir"]}
        dataset_fingerprint = {mlflow_result["dataset_fingerprint"]}
        roc_auc = {metrics["roc_auc"]:.3f}
        balanced_accuracy = {metrics["balanced_accuracy"]:.3f}
        ```

        Prediction preview:

        ```text
        {_head}
        ```
        """
    )
    return


if __name__ == "__main__":
    app.run()
