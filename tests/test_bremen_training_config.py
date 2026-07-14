"""Tests for training config validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from bremen.training.pipeline import (
    _validate_training_config,
    run_training_from_config,
    REQUIRED_TRAINING_CONFIG_SECTIONS,
    REQUIRED_TRAINING_CONFIG_FIELDS,
)

CONFIG_DIR = Path(__file__).parents[1] / "config" / "training"


def _load_yaml(path: str | Path) -> dict:
    import yaml
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


class TestConfigAccept:
    def test_example_config_accepts(self):
        """The example training config passes validation."""
        yaml_path = CONFIG_DIR / "bremen_v0_1_train.yaml"
        assert yaml_path.is_file()
        config = _load_yaml(yaml_path)
        _validate_training_config(config)

    def test_example_config_has_bremen_cohort(self):
        """lr1_row_policy is mri_referred_only."""
        yaml_path = CONFIG_DIR / "bremen_v0_1_train.yaml"
        config = _load_yaml(yaml_path)
        assert config["model"]["lr1_row_policy"] == "mri_referred_only"

    def test_example_config_has_all_required_fields(self):
        """The example config has all required sections and fields."""
        yaml_path = CONFIG_DIR / "bremen_v0_1_train.yaml"
        config = _load_yaml(yaml_path)
        for section in REQUIRED_TRAINING_CONFIG_SECTIONS:
            assert section in config, f"Missing section: {section}"
            for field in REQUIRED_TRAINING_CONFIG_FIELDS.get(section, ()):
                assert field in config[section], (
                    f"Missing field '{field}' in section '{section}'"
                )


class TestConfigRejection:
    def test_rejects_missing_section(self):
        """Config missing 'training' section raises ValueError."""
        config = {"io": {}, "model": {}, "evaluation": {}}
        with pytest.raises(ValueError, match="training"):
            _validate_training_config(config)

    def test_rejects_missing_field(self):
        """Config missing training.name raises ValueError."""
        config = {
            "training": {"version": "0.1.0"},
            "io": {"input_dataframe_joblib_path": "data.joblib"},
            "model": {"profile_column": "prof"},
            "evaluation": {"n_splits": 5},
        }
        with pytest.raises(ValueError, match="name"):
            _validate_training_config(config)
