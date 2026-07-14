"""Tests for the preprocessing bridge (v0.1 15-column schema).

All tests use synthetic H5 under tmp_path.
Optional real-subset smoke test at the bottom, skipped by default.
"""

from __future__ import annotations

import os
import ast
from pathlib import Path

import h5py
import numpy as np
import pytest

from bremen.api.preprocessing_bridge import (
    BREMEN_V01_FEATURE_COLUMNS,
    FEATURE_SCHEMA_VERSION,
    BremenFeatureVector,
    FeatureSchemaMismatchError,
    PreflightNotPassedError,
    PreprocessingBridgeError,
    PreprocessingBridgeResult,
    build_feature_table,
    run_preprocessing_bridge,
    validate_feature_schema,
    validate_feature_values,
)
from bremen.api.preflight import PreflightResult

API_SRC = Path(__file__).parents[1] / "src" / "bremen" / "api"


def _create_synthetic_h5(
    tmp_path: Path,
    *,
    patient_id: str = "TEST-001",
    target_side: str = "L",
    contralateral_side: str = "R",
    target_n: int = 3,
    contralateral_n: int = 3,
) -> Path:
    path = tmp_path / "bridge_v01_test.h5"
    with h5py.File(path, "w") as f:
        f.create_dataset("/patient/id", data=patient_id)
        tg = f.create_group("/scans/target")
        tg.create_dataset("side", data=target_side)
        rng = np.random.default_rng(42)
        tg.create_dataset(
            "measurements", data=rng.normal(0, 1, (target_n, 100)).astype(np.float64)
        )
        ct = f.create_group("/scans/contralateral")
        ct.create_dataset("side", data=contralateral_side)
        ct.create_dataset(
            "measurements",
            data=rng.normal(0.3, 1, (contralateral_n, 100)).astype(np.float64),
        )
    return path


# ---------------------------------------------------------------------------
# Valid bridge (15-column)
# ---------------------------------------------------------------------------


class TestValidBridge:
    def test_valid_produces_15_features(self, tmp_path: Path, caplog):
        """Valid preflight + synthetic H5 produces exactly 15 features.

        Also verifies that ``bremen.prediction.preprocessing.completed`` is NOT
        emitted by ``run_preprocessing_bridge()`` alone (only by ``run_inference()``).
        """
        import logging
        caplog.set_level(logging.INFO)
        import logging
        h5_path = _create_synthetic_h5(tmp_path)
        result = run_preprocessing_bridge(h5_path)
        assert result.passed is True
        assert result.feature_vector is not None
        assert len(result.feature_vector.features) == 15
        assert "bremen.prediction.preprocessing.completed" not in caplog.text

    def test_feature_order_matches_v01(self, tmp_path: Path):
        """Feature names match BREMEN_V01_FEATURE_COLUMNS exact order."""
        h5_path = _create_synthetic_h5(tmp_path)
        result = run_preprocessing_bridge(h5_path)
        assert result.passed
        assert result.feature_vector is not None
        for i, expected in enumerate(BREMEN_V01_FEATURE_COLUMNS):
            assert result.feature_vector.feature_names[i] == expected

    def test_all_15_feature_values_are_finite(self, tmp_path: Path):
        """All 15 feature values are finite floats."""
        h5_path = _create_synthetic_h5(tmp_path)
        result = run_preprocessing_bridge(h5_path)
        assert result.passed
        assert result.feature_vector is not None
        for val in result.feature_vector.features:
            assert isinstance(val, float)
            assert np.isfinite(val)

    def test_new_features_present(self, tmp_path: Path):
        """sigma_r1, sigma_r2, peak14_intensity, etc. are present."""
        h5_path = _create_synthetic_h5(tmp_path)
        result = run_preprocessing_bridge(h5_path)
        assert result.feature_vector is not None
        names = result.feature_vector.feature_names
        for new_feature in [
            "sigma_r1", "sigma_r2", "mahalanobis1", "mahalanobis2",
            "weightedrms2", "peak14_intensity", "mean_peak_value_raw",
            "wasserstein_distance_muLR", "cosine_distance_full_q2",
            "meanrms1",
        ]:
            assert new_feature in names, f"Missing new feature: {new_feature}"

    def test_mahalanobis_is_lowercase(self, tmp_path: Path):
        """Points 4 and 8 are lowercase mahalanobis1 and mahalanobis2."""
        h5_path = _create_synthetic_h5(tmp_path)
        result = run_preprocessing_bridge(h5_path)
        assert result.feature_vector is not None
        assert result.feature_vector.feature_names[3] == "mahalanobis1"
        assert result.feature_vector.feature_names[7] == "mahalanobis2"

    def test_result_excludes_raw_arrays(self, tmp_path: Path):
        """Result does not contain measurement arrays."""
        h5_path = _create_synthetic_h5(tmp_path)
        result = run_preprocessing_bridge(h5_path)
        assert result.passed
        assert not hasattr(result, "profiles")
        assert not hasattr(result, "measurements")

    def test_bridge_deterministic(self, tmp_path: Path):
        """Same H5 produces identical feature values."""
        h5_path = _create_synthetic_h5(tmp_path)
        r1 = run_preprocessing_bridge(h5_path)
        r2 = run_preprocessing_bridge(h5_path)
        assert r1.feature_vector is not None
        assert r2.feature_vector is not None
        for a, b in zip(r1.feature_vector.features, r2.feature_vector.features):
            assert a == pytest.approx(b)

    def test_feature_schema_version_v0_1(self, tmp_path: Path):
        """Feature vector schema version is 'v0.1'."""
        h5_path = _create_synthetic_h5(tmp_path)
        result = run_preprocessing_bridge(h5_path)
        assert result.feature_vector is not None
        assert result.feature_vector.feature_schema_version == FEATURE_SCHEMA_VERSION

    def test_patient_metadata_preserved(self, tmp_path: Path):
        """Patient metadata preserved in result."""
        h5_path = _create_synthetic_h5(tmp_path, patient_id="P100")
        result = run_preprocessing_bridge(h5_path)
        assert result.feature_vector is not None
        assert result.feature_vector.patient_id == "P100"


# ---------------------------------------------------------------------------
# Preflight failure
# ---------------------------------------------------------------------------


class TestPreflightFailure:
    def test_failed_preflight_blocks_bridge(self, tmp_path: Path):
        """Failed preflight result raises PreflightNotPassedError."""
        h5_path = _create_synthetic_h5(tmp_path)
        failed = PreflightResult(
            status="failed", passed=False, reasons=[], warnings=[],
            patient_id=None, target_side=None, contralateral_side=None,
            target_measurement_count=None, contralateral_measurement_count=None,
            metadata={}, qc_flags=[],
        )
        with pytest.raises(PreflightNotPassedError):
            run_preprocessing_bridge(h5_path, preflight_result=failed)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_15_feature_schema_accepted(self):
        """15-column schema passes validation."""
        vec = BremenFeatureVector(
            features=[0.1] * 15,
            feature_names=list(BREMEN_V01_FEATURE_COLUMNS),
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            patient_id=None, target_side=None, contralateral_side=None,
        )
        validate_feature_schema(vec)

    def test_7_feature_old_schema_rejected(self):
        """Old 7-feature schema fails."""
        old = ["sigma_l1", "sigma_l2", "Mahalanobis1", "Mahalanobis2",
               "wasserstein_distance_full_q2", "meanrms2", "weightedrms1"]
        vec = BremenFeatureVector(
            features=[0.1] * 7,
            feature_names=old,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            patient_id=None, target_side=None, contralateral_side=None,
        )
        with pytest.raises(FeatureSchemaMismatchError, match="15.*7"):
            validate_feature_schema(vec)

    def test_wrong_order_fails(self):
        """Reordered names fail."""
        wrong = list(BREMEN_V01_FEATURE_COLUMNS)
        wrong[0], wrong[1] = wrong[1], wrong[0]
        vec = BremenFeatureVector(
            features=[0.1] * 15,
            feature_names=wrong,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            patient_id=None, target_side=None, contralateral_side=None,
        )
        with pytest.raises(FeatureSchemaMismatchError):
            validate_feature_schema(vec)

    def test_wrong_version_fails(self):
        """Wrong schema version fails."""
        vec = BremenFeatureVector(
            features=[0.1] * 15,
            feature_names=list(BREMEN_V01_FEATURE_COLUMNS),
            feature_schema_version="v0.2",
            patient_id=None, target_side=None, contralateral_side=None,
        )
        with pytest.raises(FeatureSchemaMismatchError, match="v0.1"):
            validate_feature_schema(vec)

    def test_validate_feature_values_returns_warnings(self):
        """validate_feature_values returns warnings for NaN."""
        vec = BremenFeatureVector(
            features=[float("nan")] + [0.1] * 14,
            feature_names=list(BREMEN_V01_FEATURE_COLUMNS),
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            patient_id=None, target_side=None, contralateral_side=None,
        )
        warnings = validate_feature_values(vec)
        assert len(warnings) >= 1


# ---------------------------------------------------------------------------
# Build feature table
# ---------------------------------------------------------------------------


class TestBuildFeatureTable:
    def test_build_feature_table_returns_15_keys(self, tmp_path: Path):
        """build_feature_table returns dict with exactly 15 keys."""
        h5_path = _create_synthetic_h5(tmp_path)
        table = build_feature_table(h5_path)
        assert len(table) == 15
        for col in BREMEN_V01_FEATURE_COLUMNS:
            assert col in table


# ---------------------------------------------------------------------------
# Import safety
# ---------------------------------------------------------------------------


class TestImportSafety:
    def test_no_model_loading_or_inference(self):
        """Bridge does not import training/inference (AST)."""
        src = API_SRC / "preprocessing_bridge.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        prohibited = {"inference", "model_loader", "training"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in prohibited:
                        pytest.fail(f"imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.split(".")[0] in prohibited:
                    pytest.fail(f"imports from {module}")


# ---------------------------------------------------------------------------
# Real subset smoke (opt-in)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    "BREMEN_H5_PREFLIGHT_SMOKE_PATH" not in os.environ,
    reason="BREMEN_H5_PREFLIGHT_SMOKE_PATH not set",
)
def test_real_subset_bridge_smoke():
    """Opt-in smoke test for real H5 bridge (15 columns)."""
    h5_path = os.environ["BREMEN_H5_PREFLIGHT_SMOKE_PATH"]
    result = run_preprocessing_bridge(h5_path)
    assert result.passed is True
    assert result.feature_vector is not None
    assert len(result.feature_vector.features) == 15
    for val in result.feature_vector.features:
        assert np.isfinite(val)
