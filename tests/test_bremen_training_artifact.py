"""Tests for training artifact assembly."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from bremen.training.pipeline import (
    REQUIRED_TRAINING_ARTIFACT_FIELDS,
    _patient_training_artifact,
)

from sklearn.linear_model import LogisticRegression
CONFIG_DIR = Path(__file__).parents[1] / "config" / "training"


@pytest.fixture
def config() -> dict:
    path = CONFIG_DIR / "bremen_v0_1_train.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture
def raw_yaml() -> str:
    path = CONFIG_DIR / "bremen_v0_1_train.yaml"
    return path.read_text(encoding="utf-8")


class TestArtifactFields:
    def test_artifact_has_all_21_required_fields(self, config, raw_yaml):
        """Artifact dict keys match REQUIRED_TRAINING_ARTIFACT_FIELDS."""
        with Path("/tmp/.test_df.joblib").open("wb") as f:
            import joblib
            df = pd.DataFrame({"a": [1]})
            joblib.dump(df, f)

        artifact = _patient_training_artifact(
            config=config,
            raw_yaml=raw_yaml,
            models={},
            thresholds={},
            model_descriptions={},
            feature_table=pd.DataFrame(),
            metric_summary={},
            split_metrics=[],
            split_predictions=pd.DataFrame(),
            input_dataframe_path=Path("/tmp/.test_df.joblib"),
            output_model_path=Path("/tmp/.test_output.joblib"),
            warnings=[],
        )
        for field in REQUIRED_TRAINING_ARTIFACT_FIELDS:
            assert field in artifact, f"Missing artifact field: {field}"
        import os
        os.remove("/tmp/.test_df.joblib")

    def test_artifact_kind_is_bremen_training_artifact(self, config, raw_yaml):
        """artifact['kind'] == 'bremen_training_artifact'."""
        with Path("/tmp/.test_df2.joblib").open("wb") as f:
            import joblib
            joblib.dump(pd.DataFrame({"a": [1]}), f)
        artifact = _patient_training_artifact(
            config=config,
            raw_yaml=raw_yaml,
            models={},
            thresholds={},
            model_descriptions={},
            feature_table=pd.DataFrame(),
            metric_summary={},
            split_metrics=[],
            split_predictions=pd.DataFrame(),
            input_dataframe_path=Path("/tmp/.test_df2.joblib"),
            output_model_path=Path("/tmp/.test_output.joblib"),
            warnings=[],
        )
        assert artifact["kind"] == "bremen_training_artifact"
        import os
        os.remove("/tmp/.test_df2.joblib")

    def test_artifact_has_required_metadata_fields(self, config, raw_yaml):
        """metadata contains bremen_version, git_sha, created_at, branch, training_role."""
        with Path("/tmp/.test_df3.joblib").open("wb") as f:
            import joblib
            joblib.dump(pd.DataFrame({"a": [1]}), f)
        artifact = _patient_training_artifact(
            config=config,
            raw_yaml=raw_yaml,
            models={},
            thresholds={},
            model_descriptions={},
            feature_table=pd.DataFrame(),
            metric_summary={},
            split_metrics=[],
            split_predictions=pd.DataFrame(),
            input_dataframe_path=Path("/tmp/.test_df3.joblib"),
            output_model_path=Path("/tmp/.test_output.joblib"),
            warnings=[],
        )
        meta = artifact["metadata"]
        assert "bremen_version" in meta
        assert "git_sha" in meta
        assert "created_at" in meta
        assert "branch" in meta
        assert "training_role" in meta
        import os
        os.remove("/tmp/.test_df3.joblib")

    def test_artifact_hashes_deterministic(self, config, raw_yaml, tmp_path):
        """Calling _patient_training_artifact twice with same inputs produces matching hash fields."""
        import joblib

        df = pd.DataFrame({"a": [1], "b": [2]})
        df_path = tmp_path / "input.joblib"
        joblib.dump(df, df_path)

        models = {"M0": LogisticRegression(C=0.1).fit(np.array([[1.0], [2.0]]), np.array([0, 1]))}
        thresholds = {"M0": 0.5}

        artifact_a = _patient_training_artifact(
            config=config,
            raw_yaml=raw_yaml,
            models=models,
            thresholds=thresholds,
            model_descriptions={"M0": {"type": "LogisticRegression"}},
            feature_table=pd.DataFrame(),
            metric_summary={},
            split_metrics=[],
            split_predictions=pd.DataFrame(),
            input_dataframe_path=df_path,
            output_model_path=tmp_path / "output.joblib",
            warnings=[],
        )

        artifact_b = _patient_training_artifact(
            config=config,
            raw_yaml=raw_yaml,
            models=models,
            thresholds=thresholds,
            model_descriptions={"M0": {"type": "LogisticRegression"}},
            feature_table=pd.DataFrame(),
            metric_summary={},
            split_metrics=[],
            split_predictions=pd.DataFrame(),
            input_dataframe_path=df_path,
            output_model_path=tmp_path / "output.joblib",
            warnings=[],
        )

        # Hash fields must match across identical calls
        assert artifact_a["training_config_sha256"] == artifact_b["training_config_sha256"], (
            "training_config_sha256 must be deterministic"
        )
        assert artifact_a["input_dataframe_joblib_sha256"] == artifact_b["input_dataframe_joblib_sha256"], (
            "input_dataframe_joblib_sha256 must be deterministic"
        )

        # Stable metadata fields must match (timestamps change; skip created_at)
        for key in ["kind", "version", "model_type", "training_config_text", "training_config_yaml"]:
            assert artifact_a[key] == artifact_b[key], (
                f"Artifact field '{key}' must be deterministic"
            )


class TestArtifactSemantics:
    def test_artifact_does_not_rename_adr_0007_fields(self, config, raw_yaml, tmp_path):
        """Runtime manifest fields (model_version, model_checksum, feature_schema_version)
        must NOT appear in the training artifact."""
        import joblib

        df = pd.DataFrame({"a": [1]})
        df_path = tmp_path / "input.joblib"
        joblib.dump(df, df_path)

        artifact = _patient_training_artifact(
            config=config,
            raw_yaml=raw_yaml,
            models={},
            thresholds={},
            model_descriptions={},
            feature_table=pd.DataFrame(),
            metric_summary={},
            split_metrics=[],
            split_predictions=pd.DataFrame(),
            input_dataframe_path=df_path,
            output_model_path=tmp_path / "output.joblib",
            warnings=[],
        )

        # The artifact SHOULD contain 'version' (training version)
        assert "version" in artifact
        # Should NOT contain runtime manifest field names
        assert "model_version" not in artifact, (
            "Runtime field 'model_version' must not appear in training artifact"
        )
        assert "model_checksum" not in artifact, (
            "Runtime field 'model_checksum' must not appear in training artifact"
        )
        assert "feature_schema_version" not in artifact, (
            "Runtime field 'feature_schema_version' must not appear in training artifact"
        )
        # model_type is present (training concept, not runtime)
        assert artifact["model_type"] == "patient_m0_m1_m2_logistic_set"
