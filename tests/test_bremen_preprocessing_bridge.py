"""Tests for the preprocessing bridge.

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
    BREMEN_FEATURE_COLUMNS,
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_synthetic_h5(
    tmp_path: Path,
    *,
    patient_id: str = "TEST-001",
    target_side: str = "L",
    contralateral_side: str = "R",
    target_n: int = 3,
    contralateral_n: int = 3,
) -> Path:
    """Create a minimal synthetic H5 with target/contralateral profiles."""
    path = tmp_path / "bridge_test.h5"
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
# Valid bridge
# ---------------------------------------------------------------------------


class TestValidBridge:
    def test_valid_produces_7_features(self, tmp_path: Path):
        """Valid preflight + synthetic H5 produces exactly 7 features."""
        h5_path = _create_synthetic_h5(tmp_path)
        result = run_preprocessing_bridge(h5_path)
        assert result.passed is True
        assert result.feature_vector is not None
        assert len(result.feature_vector.features) == 7

    def test_feature_order_matches_BREMEN_FEATURE_COLUMNS(self, tmp_path: Path):
        """Feature names in output match exact order."""
        h5_path = _create_synthetic_h5(tmp_path)
        result = run_preprocessing_bridge(h5_path)
        assert result.passed
        assert result.feature_vector is not None
        for i, expected in enumerate(BREMEN_FEATURE_COLUMNS):
            assert result.feature_vector.feature_names[i] == expected

    def test_all_feature_values_are_finite_numeric(self, tmp_path: Path):
        """All 7 feature values are finite floats."""
        h5_path = _create_synthetic_h5(tmp_path)
        result = run_preprocessing_bridge(h5_path)
        assert result.passed
        assert result.feature_vector is not None
        for val in result.feature_vector.features:
            assert isinstance(val, float)
            assert np.isfinite(val)

    def test_result_excludes_raw_arrays(self, tmp_path: Path):
        """Result does not contain measurement arrays."""
        h5_path = _create_synthetic_h5(tmp_path)
        result = run_preprocessing_bridge(h5_path)
        assert result.passed
        assert result.feature_vector is not None
        # Check no measurement keys in preflight_summary
        for key in result.preflight_summary:
            assert "measurement" not in key.lower()
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

    def test_feature_schema_version_matches_constant(self, tmp_path: Path):
        """Feature vector schema version matches FEATURE_SCHEMA_VERSION."""
        h5_path = _create_synthetic_h5(tmp_path)
        result = run_preprocessing_bridge(h5_path)
        assert result.feature_vector is not None
        assert result.feature_vector.feature_schema_version == FEATURE_SCHEMA_VERSION

    def test_patient_metadata_preserved(self, tmp_path: Path):
        """Patient metadata is preserved in result."""
        h5_path = _create_synthetic_h5(tmp_path, patient_id="P100")
        result = run_preprocessing_bridge(h5_path)
        assert result.feature_vector is not None
        assert result.feature_vector.patient_id == "P100"
        assert result.feature_vector.target_side == "L"
        assert result.feature_vector.contralateral_side == "R"


# ---------------------------------------------------------------------------
# Preflight failure
# ---------------------------------------------------------------------------


class TestPreflightFailure:
    def test_failed_preflight_blocks_bridge(self, tmp_path: Path):
        """Passing a failed preflight result raises PreflightNotPassedError."""
        h5_path = _create_synthetic_h5(tmp_path)
        failed = PreflightResult(
            status="failed",
            passed=False,
            reasons=[],
            warnings=[],
            patient_id=None,
            target_side=None,
            contralateral_side=None,
            target_measurement_count=None,
            contralateral_measurement_count=None,
            metadata={},
            qc_flags=[],
        )
        with pytest.raises(PreflightNotPassedError):
            run_preprocessing_bridge(h5_path, preflight_result=failed)

    def test_skip_preflight_allows_bridge(self, tmp_path: Path):
        """skip_preflight=True runs bridge without preflight result."""
        h5_path = _create_synthetic_h5(tmp_path)
        result = run_preprocessing_bridge(h5_path, skip_preflight=True)
        assert result.passed is True

    def test_skip_preflight_summary_has_skipped_flag(self, tmp_path: Path):
        """skip_preflight produces skipped=True in preflight_summary."""
        h5_path = _create_synthetic_h5(tmp_path)
        result = run_preprocessing_bridge(h5_path, skip_preflight=True)
        assert result.preflight_summary.get("skipped") is True


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class TestSchemaValidation:
    def test_missing_feature_fails_validation(self):
        """Feature vector with wrong count raises FeatureSchemaMismatchError."""
        vec = BremenFeatureVector(
            features=[0.1] * 6,
            feature_names=list(BREMEN_FEATURE_COLUMNS)[:6],
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            patient_id=None,
            target_side=None,
            contralateral_side=None,
        )
        with pytest.raises(FeatureSchemaMismatchError, match="7.*6"):
            validate_feature_schema(vec)

    def test_extra_feature_fails_validation(self):
        """Feature vector with 8 features raises FeatureSchemaMismatchError."""
        vec = BremenFeatureVector(
            features=[0.1] * 8,
            feature_names=list(BREMEN_FEATURE_COLUMNS) + ["extra"],
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            patient_id=None,
            target_side=None,
            contralateral_side=None,
        )
        with pytest.raises(FeatureSchemaMismatchError, match="7.*8"):
            validate_feature_schema(vec)

    def test_wrong_feature_order_fails_validation(self):
        """Reordered feature names raise FeatureSchemaMismatchError."""
        wrong_order = list(BREMEN_FEATURE_COLUMNS)
        wrong_order[0], wrong_order[1] = wrong_order[1], wrong_order[0]
        vec = BremenFeatureVector(
            features=[0.1] * 7,
            feature_names=wrong_order,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            patient_id=None,
            target_side=None,
            contralateral_side=None,
        )
        with pytest.raises(FeatureSchemaMismatchError, match="index 0"):
            validate_feature_schema(vec)

    def test_feature_schema_version_mismatch_fails(self):
        """Wrong schema version raises FeatureSchemaMismatchError."""
        vec = BremenFeatureVector(
            features=[0.1] * 7,
            feature_names=list(BREMEN_FEATURE_COLUMNS),
            feature_schema_version="v0.2",
            patient_id=None,
            target_side=None,
            contralateral_side=None,
        )
        with pytest.raises(FeatureSchemaMismatchError, match="v0.1"):
            validate_feature_schema(vec)

    def test_validate_feature_values_returns_warnings(self):
        """validate_feature_values returns warnings for non-finite values."""
        vec = BremenFeatureVector(
            features=[float("nan")] + [0.1] * 6,
            feature_names=list(BREMEN_FEATURE_COLUMNS),
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            patient_id=None,
            target_side=None,
            contralateral_side=None,
        )
        warnings = validate_feature_values(vec)
        assert len(warnings) >= 1


# ---------------------------------------------------------------------------
# Build feature table
# ---------------------------------------------------------------------------


class TestBuildFeatureTable:
    def test_build_feature_table_returns_7_keys(self, tmp_path: Path):
        """build_feature_table returns dict with exactly 7 keys."""
        h5_path = _create_synthetic_h5(tmp_path)
        table = build_feature_table(h5_path)
        assert len(table) == 7
        for col in BREMEN_FEATURE_COLUMNS:
            assert col in table


# ---------------------------------------------------------------------------
# Import safety
# ---------------------------------------------------------------------------


class TestImportSafety:
    def test_no_model_loading_or_inference(self):
        """preprocessing_bridge must not import training/inference/model modules (AST)."""
        src = API_SRC / "preprocessing_bridge.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        prohibited = {
            "inference", "model_loader", "model_package", "training",
            "pipelines", "modeling",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in prohibited:
                        pytest.fail(
                            f"preprocessing_bridge.py imports {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                top = module.split(".")[0]
                if top in prohibited or module in prohibited:
                    pytest.fail(
                        f"preprocessing_bridge.py imports from {module}"
                    )

    def test_no_joblib_or_pickle(self):
        """preprocessing_bridge must not import joblib or pickle (AST)."""
        src = API_SRC / "preprocessing_bridge.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        prohibited = {"joblib", "pickle"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in prohibited:
                        pytest.fail(f"imports {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                top = module.split(".")[0]
                if top in prohibited:
                    pytest.fail(f"imports from {module}")


# ---------------------------------------------------------------------------
# Real subset smoke (opt-in, skipped in CI)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    "BREMEN_H5_PREFLIGHT_SMOKE_PATH" not in os.environ,
    reason="BREMEN_H5_PREFLIGHT_SMOKE_PATH not set — skipping real subset smoke",
)
def test_real_subset_bridge_smoke():
    """Opt-in smoke test for real H5 bridge.

    Set BREMEN_H5_PREFLIGHT_SMOKE_PATH to enable.
    Verifies 7 features are produced. No clinical assertions.
    """
    h5_path = os.environ["BREMEN_H5_PREFLIGHT_SMOKE_PATH"]
    result = run_preprocessing_bridge(h5_path)
    assert result.passed is True
    assert result.feature_vector is not None
    assert len(result.feature_vector.features) == 7
    for val in result.feature_vector.features:
        assert np.isfinite(val)
