from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from aramis.modeling import (
    aggregate_measurement_scores_by_specimen,
    fit_repeated_one_to_many_product_logistic_comparison,
    fit_repeated_one_to_many_product_logistic,
    fit_repeated_one_to_many_logistic,
    profile_matrix,
    summarize_one_to_many_dataframe,
)


def _one_to_many_model_frame() -> pd.DataFrame:
    rows = []
    q = np.linspace(2.0, 23.0, 20)
    for patient_idx in range(20):
        label = "CANCER" if patient_idx % 2 else "BENIGN"
        for measurement_idx in range(2):
            baseline = 1.0 if label == "CANCER" else -1.0
            profile = baseline + np.sin(q / 3.0) + measurement_idx * 0.01
            rows.append(
                {
                    "patientId": f"P{patient_idx:02d}",
                    "specimenId": f"P{patient_idx:02d}_RIGHT",
                    "measurementId": f"P{patient_idx:02d}_M{measurement_idx}",
                    "product_status_group": label,
                    "radial_profile_data": profile,
                    "q_range": q,
                }
            )
    return pd.DataFrame(rows)


def test_repeated_one_to_many_logistic_has_patient_safe_splits():
    df = _one_to_many_model_frame()

    result = fit_repeated_one_to_many_logistic(
        df,
        n_splits=5,
        test_size=0.30,
        random_state=7,
    )

    assert len(result.split_metrics) == 5
    assert set(result.predictions["split_id"]) == set(range(5))
    assert result.mean_fpr.shape == result.mean_tpr.shape
    assert result.split_metrics["roc_auc"].between(0.0, 1.0).all()
    for split_id in range(5):
        test_patients = set(
            result.predictions.loc[
                result.predictions["split_id"] == split_id,
                "patientId",
            ]
        )
        train_rows = result.split_metrics.loc[
            result.split_metrics["split_id"] == split_id,
            "train_patients",
        ].iloc[0]
        assert len(test_patients) + int(train_rows) == df["patientId"].nunique()


def test_repeated_one_to_many_product_logistic_returns_specimen_predictions():
    df = _one_to_many_model_frame()

    result = fit_repeated_one_to_many_product_logistic(
        df,
        n_splits=4,
        test_size=0.30,
        random_state=11,
        inner_splits=3,
    )

    assert len(result.split_metrics) == 4
    assert set(result.specimen_predictions["set_name"]) == {"train_oof", "test"}
    assert set(result.measurement_predictions["set_name"]) == {"train_oof", "test"}
    assert result.split_metrics["roc_auc"].between(0.0, 1.0).all()
    assert {"threshold_youden", "threshold_target"}.issubset(
        result.threshold_summary.columns
    )


def test_one_to_many_product_comparison_returns_named_summaries():
    df = _one_to_many_model_frame()
    biopsy_df = df[df["patientId"].isin([f"P{idx:02d}" for idx in range(12)])].copy()

    result = fit_repeated_one_to_many_product_logistic_comparison(
        {
            "standard": df,
            "biopsy_only": biopsy_df,
        },
        n_splits=3,
        test_size=0.30,
        random_state=17,
        inner_splits=3,
    )

    assert set(result.results) == {"standard", "biopsy_only"}
    assert set(result.dataset_summary["dataset"]) == {"standard", "biopsy_only"}
    assert set(result.metric_summary["dataset"]) == {"standard", "biopsy_only"}
    assert result.metric_summary["roc_auc_mean"].between(0.0, 1.0).all()


def test_aggregate_measurement_scores_by_specimen_uses_mean_score():
    df = _one_to_many_model_frame().head(4).copy()
    df["p_cancer_measurement"] = [0.1, 0.3, 0.8, 1.0]

    out = aggregate_measurement_scores_by_specimen(
        df,
        score_column="p_cancer_measurement",
    )

    assert len(out) == 2
    np.testing.assert_allclose(sorted(out["p_cancer"]), [0.2, 0.9])


def test_one_to_many_summary_counts_rows_patients_specimens_and_labels():
    df = _one_to_many_model_frame()

    summary = summarize_one_to_many_dataframe(df)

    assert summary.loc[0, "rows"] == 40
    assert summary.loc[0, "patients"] == 20
    assert summary.loc[0, "specimens"] == 20
    assert summary.loc[0, "BENIGN_rows"] == 20
    assert summary.loc[0, "CANCER_rows"] == 20


def test_profile_matrix_rejects_different_profile_lengths():
    df = _one_to_many_model_frame().head(2).copy()
    df.at[df.index[1], "radial_profile_data"] = np.array([1.0, 2.0])

    with pytest.raises(ValueError, match="equal length"):
        profile_matrix(df, "radial_profile_data")
