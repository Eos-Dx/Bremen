from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
import yaml

from aramis.pipelines import AramisOneToManyPreprocessingPipeline

from .synthetic_aramis_h5 import (
    ONE_TO_MANY_OUTPUT_COLUMNS,
    assert_common_output_contract,
    load_synthetic_config,
    write_known_synthetic_h5,
)


def test_one_to_many_pipeline_dataframe_and_joblib_contract(tmp_path: Path):
    h5_path = tmp_path / "known_synthetic_aramis.h5"
    config_path = tmp_path / "aramis_one_to_many_preprocessing_v0_1.yaml"
    joblib_path = tmp_path / "aramis_one_to_many_dataframe.joblib"
    config = load_synthetic_config("one_to_many")
    config["raw_data"]["h5_dataset_candidates"]["npy"] = ["processed/data"]
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    write_known_synthetic_h5(h5_path)

    pipeline = AramisOneToManyPreprocessingPipeline(
        config=config_path,
        output_joblib_path=joblib_path,
    )
    df = pipeline.fit_transform(h5_path)
    loaded = joblib.load(joblib_path)

    assert pipeline.fit(h5_path) is pipeline
    pd.testing.assert_frame_equal(df, loaded)
    assert set(df.columns) == ONE_TO_MANY_OUTPUT_COLUMNS
    assert_common_output_contract(df)
    assert len(df) == 5
    assert set(df["patientId"]) == {"P1", "P2", "P3", "P4"}
    assert set(df["specimenId"]) == {
        "P1_LEFT",
        "P1_RIGHT",
        "P2_LEFT",
        "P3_RIGHT",
        "P4_RIGHT",
    }
    assert set(df["product_status_group"]) == {"BENIGN", "CANCER"}
    assert set(df["product_diagnosis"]) == {"BENIGN", "CANCER"}
    assert "NORMAL" not in set(df["specimen_status"])
    assert "P4_LEFT" not in set(df["specimenId"])
    assert "P5" not in set(df["patientId"])
    assert set(df["measurement_data_source"]) == {"npy:processed/data"}
