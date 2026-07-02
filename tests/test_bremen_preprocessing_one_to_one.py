from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
import yaml

from bremen.pipelines import BremenOneToOnePreprocessingPipeline

from .synthetic_bremen_h5 import (
    ONE_TO_ONE_OUTPUT_COLUMNS,
    assert_common_output_contract,
    load_synthetic_config,
    write_known_synthetic_h5,
)


def test_one_to_one_pipeline_dataframe_and_joblib_contract(tmp_path: Path):
    h5_path = tmp_path / "known_synthetic_bremen.h5"
    config_path = tmp_path / "bremen_one_to_one_preprocessing_v0_1.yaml"
    joblib_path = tmp_path / "bremen_one_to_one_dataframe.joblib"
    config = load_synthetic_config("one_to_one")
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    write_known_synthetic_h5(h5_path)

    pipeline = BremenOneToOnePreprocessingPipeline(
        config=config_path,
        output_joblib_path=joblib_path,
    )
    df = pipeline.fit_transform(h5_path)
    loaded = joblib.load(joblib_path)

    assert pipeline.fit(h5_path) is pipeline
    pd.testing.assert_frame_equal(df, loaded)
    assert set(df.columns) == ONE_TO_ONE_OUTPUT_COLUMNS
    assert_common_output_contract(df)
    assert len(df) == 4
    assert set(df["patientId"]) == {"P1", "P3"}
    assert set(df["specimenId"]) == {"P1_LEFT", "P1_RIGHT", "P3_LEFT", "P3_RIGHT"}
    assert set(df["product_status_group"]) == {"BENIGN", "CANCER", "NORMAL"}
    assert set(df["one_to_one_pair_type"]) == {
        "BENIGN__CANCER",
        "CANCER__NORMAL",
    }
    assert set(df["patient_valid_specimen_count"]) == {2}
    assert "P2" not in set(df["patientId"])
    assert "P4" not in set(df["patientId"])
    assert "P5" not in set(df["patientId"])
    assert set(df["measurement_data_source"]) == {"npy:raw/data"}
