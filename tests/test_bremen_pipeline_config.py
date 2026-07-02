from __future__ import annotations

import joblib
import pandas as pd
import pytest
import yaml

from bremen.__main__ import main
from bremen.pipelines import (
    _config_path,
    _h5_filters,
    _measurement_filters,
    _normalizer_step,
    _output_column_steps,
    _quality_exclusion_h5_filters,
    _validate_branch,
    payload_columns_to_drop,
)

from .synthetic_bremen_h5 import load_synthetic_config, write_known_synthetic_h5


def test_payload_drop_columns_follow_metadata_config():
    config = {"metadata": {"drop_payload_columns": True}}

    columns = payload_columns_to_drop(config)

    assert "measurement_data" in columns
    assert "radial_profile_data_raw" in columns


def test_payload_drop_columns_can_keep_selected_debug_profiles():
    config = {
        "metadata": {
            "drop_payload_columns": True,
            "keep_payload_columns": ["radial_profile_data_raw", "radial_profile_sigma"],
        }
    }

    columns = payload_columns_to_drop(config)

    assert "measurement_data" in columns
    assert "radial_profile_data_raw" not in columns
    assert "radial_profile_sigma" not in columns


def test_payload_drop_keeps_columns_requested_for_output():
    config = {
        "metadata": {
            "drop_payload_columns": True,
            "output_columns": ["radial_profile_data_raw"],
        }
    }

    columns = payload_columns_to_drop(config)

    assert "measurement_data" in columns
    assert "radial_profile_data_raw" not in columns


def test_payload_drop_columns_can_be_disabled_for_debug_exports():
    config = {"metadata": {"drop_payload_columns": False}}

    assert payload_columns_to_drop(config) == ()


def test_output_columns_build_select_columns_transformer():
    steps = _output_column_steps(
        {"metadata": {"output_columns": ["patientId", "radial_profile_data"]}}
    )

    assert len(steps) == 1
    assert steps[0].columns == ("patientId", "radial_profile_data")


def test_output_columns_are_optional():
    assert _output_column_steps({"metadata": {}}) == []


def test_quality_exclusion_filter_prefers_session_id_with_date_fallback():
    filters = {
        "quality_exclusions": {
            "enabled": True,
            "primary_key": {
                "column": "linked_agbh_session_uid",
                "excluded_values": ["bad-session"],
            },
            "fallback_date": {
                "column": "started_at",
                "excluded_dates": ["2026-03-16"],
                "use_when_primary_key_missing": True,
            },
        }
    }

    h5_filters = _quality_exclusion_h5_filters(filters)

    assert len(h5_filters) == 1
    assert h5_filters[0].column == "linked_agbh_session_uid"
    assert h5_filters[0].op == "not in"
    assert h5_filters[0].values == ["bad-session"]
    assert h5_filters[0].fallback["op"] == "date not in"


def test_quality_exclusion_filter_can_use_date_only_or_disabled():
    date_only = _quality_exclusion_h5_filters(
        {
            "quality_exclusions": {
                "enabled": True,
                "primary_key": {"excluded_values": []},
                "fallback_date": {
                    "column": "started_at",
                    "excluded_dates": ["2026-03-16"],
                },
            }
        }
    )

    assert date_only[0].column == "started_at"
    assert date_only[0].op == "date not in"
    assert _quality_exclusion_h5_filters({"quality_exclusions": {"enabled": False}}) == []


def test_h5_and_measurement_filter_builders_use_yaml_rules():
    config = load_synthetic_config("one_to_many_benign_cancer")
    config["filters"]["accepted_dates"] = ["2026-05-01"]
    config["filters"]["require_biopsy"] = True

    h5_filters = _h5_filters(config, "one_to_many")
    measurement_filters = _measurement_filters(config)

    assert any(item.column == "started_at" for item in h5_filters)
    assert any(item.column == "biopsy" for item in h5_filters)
    assert any(item.column == "specimen_status" for item in h5_filters)
    assert any(item.column == "position" for item in measurement_filters)


def test_config_path_resolves_absolute_relative_and_missing(tmp_path):
    config = {"io": {"input_h5_path": "data/input.h5", "output_joblib_path": ""}}
    config_path = tmp_path / "config" / "preprocess.yaml"
    config_path.parent.mkdir()

    assert _config_path(config, config_path, "input_h5_path") == (
        config_path.parent / "data" / "input.h5"
    ).resolve()
    with pytest.raises(ValueError, match="Missing io.output_joblib_path"):
        _config_path(config, config_path, "output_joblib_path")


def test_normalizer_and_branch_validation_errors():
    with pytest.raises(ValueError, match="Unknown normalization mode"):
        _normalizer_step({"mode": "bad"}, 6.7, 7.1)
    with pytest.raises(ValueError, match="Unknown Bremen preprocessing branch"):
        _validate_branch("bad")


def test_preprocess_cli_reads_input_and_output_from_yaml(tmp_path):
    h5_path = tmp_path / "known_synthetic_bremen.h5"
    output_path = tmp_path / "out" / "one_to_many.joblib"
    config_path = tmp_path / "preprocess.yaml"
    config = load_synthetic_config("one_to_many_benign_cancer")
    config["io"] = {
        "input_h5_path": "known_synthetic_bremen.h5",
        "output_joblib_path": "out/one_to_many.joblib",
    }
    config["raw_data"]["h5_dataset_candidates"]["npy"] = ["processed/data"]
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    write_known_synthetic_h5(h5_path)

    exit_code = main(["preprocess", "--config", str(config_path)])

    assert exit_code == 0
    assert output_path.exists()
    df = joblib.load(output_path)
    assert isinstance(df, pd.DataFrame)
    assert set(df["product_status_group"]) == {"BENIGN", "CANCER"}


def test_preprocess_cli_can_write_minimal_output_columns(tmp_path):
    h5_path = tmp_path / "known_synthetic_bremen.h5"
    output_path = tmp_path / "out" / "minimal.joblib"
    config_path = tmp_path / "preprocess_minimal.yaml"
    output_columns = [
        "patientId",
        "specimenId",
        "q_range",
        "radial_profile_data_raw",
        "radial_profile_data",
    ]
    config = load_synthetic_config("one_to_many_benign_cancer")
    config["io"] = {
        "input_h5_path": "known_synthetic_bremen.h5",
        "output_joblib_path": "out/minimal.joblib",
    }
    config["metadata"]["output_columns"] = output_columns
    config["normalization"]["save_initial_data"] = True
    config["raw_data"]["h5_dataset_candidates"]["npy"] = ["processed/data"]
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    write_known_synthetic_h5(h5_path)

    exit_code = main(["preprocess", "--config", str(config_path)])

    assert exit_code == 0
    df = joblib.load(output_path)
    assert df.columns.tolist() == output_columns
    assert not df["radial_profile_data_raw"].equals(df["radial_profile_data"])
