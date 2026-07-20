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


def _create_matador_raw_h5(tmp_path: Path) -> Path:
    """Create synthetic Matador raw H5 for preprocessing bridge tests."""
    path = tmp_path / "matador_bridge.h5"
    with h5py.File(path, "w") as f:
        calib = f.create_group("calibrations")
        calib.create_dataset(
            "poni1",
            data=np.array([
                b"poni_version: 2.1\n",
                b"distance: 0.15\n",
                b"pixel_size: 0.0001\n",
                b"wavelength: 0.15\n",
                b"center_x: 100.0\n",
                b"center_y: 100.0\n",
            ], dtype=h5py.string_dtype()),
        )

        m1 = f.create_group("measurement_001")
        m1.attrs["side"] = "LEFT"
        m1.attrs["position"] = "center"
        m1.create_dataset(
            "data", data=np.random.default_rng(1).normal(10, 3, (100, 100)).astype(np.float32)
        )

        m2 = f.create_group("measurement_002")
        m2.attrs["side"] = "RIGHT"
        m2.attrs["position"] = "center"
        m2.create_dataset(
            "data", data=np.random.default_rng(2).normal(10, 3, (100, 100)).astype(np.float32)
        )
    return path


def _mock_matador_q_i(image, *, poni_text=None, npt=100):
    """Mock that returns deterministic q/i profiles for testing."""
    n = npt or 100
    q = np.linspace(5.0, 8.0, n, dtype=np.float64)
    # Deterministic intensity: different for target (LEFT) vs control (RIGHT)
    # Use image mean to simulate different scans
    seed = int(np.mean(image) * 1000) % 100
    rng = np.random.default_rng(seed)
    i_arr = np.abs(rng.normal(10, 2, n).astype(np.float64))
    return q, i_arr


# ---------------------------------------------------------------------------
# Matador raw preprocessing bridge (PR0073)
# ---------------------------------------------------------------------------


class TestMatadorRawBridge:
    """Matador raw bridge tests — mock xrd_preprocessing at wrapper boundary."""

    def test_matador_raw_build_feature_table(
        self, tmp_path: Path, monkeypatch,
    ):
        """build_feature_table with matador_raw context produces 15 features."""
        def _mock_integration(row, **kwargs):
            n = 100
            q = np.linspace(5.0, 8.0, n, dtype=np.float64)
            i_arr = np.abs(np.random.default_rng(42).normal(10, 2, n).astype(np.float64))
            return q, i_arr, np.zeros_like(q), 0.15

        monkeypatch.setattr(
            "xrd_preprocessing.perform_azimuthal_integration",
            _mock_integration,
        )
        h5_path = _create_matador_raw_h5(tmp_path)

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        with h5py.File(h5_path, "r") as f:
            adapter = MatadorRawH5Adapter()
            ctx = adapter.resolve_prediction_context(f, "", "")

        table = build_feature_table(h5_path, layout_context=ctx)
        assert len(table) == 15
        for col in BREMEN_V01_FEATURE_COLUMNS:
            assert col in table
            assert np.isfinite(table[col])

    def test_matador_raw_run_preprocessing_bridge(
        self, tmp_path: Path, monkeypatch,
    ):
        """run_preprocessing_bridge with matador_raw passes."""
        def _mock_integration(row, **kwargs):
            n = 100
            q = np.linspace(5.0, 8.0, n, dtype=np.float64)
            i_arr = np.abs(np.random.default_rng(99).normal(10, 2, n).astype(np.float64))
            return q, i_arr, np.zeros_like(q), 0.15

        monkeypatch.setattr(
            "xrd_preprocessing.perform_azimuthal_integration",
            _mock_integration,
        )
        h5_path = _create_matador_raw_h5(tmp_path)

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        with h5py.File(h5_path, "r") as f:
            adapter = MatadorRawH5Adapter()
            ctx = adapter.resolve_prediction_context(f, "", "")

        result = run_preprocessing_bridge(
            h5_path, layout_context=ctx, skip_preflight=True,
        )
        assert result.passed is True
        assert result.feature_vector is not None
        assert len(result.feature_vector.features) == 15

    def test_matador_integration_mock_produces_finite_features(
        self, tmp_path: Path, monkeypatch,
    ):
        """Integration mock produces finite feature values."""
        def _mock_integration(row, **kwargs):
            n = 100
            q = np.linspace(5.0, 8.0, n, dtype=np.float64)
            i_arr = np.abs(np.random.default_rng(77).normal(10, 2, n).astype(np.float64))
            return q, i_arr, np.zeros_like(q), 0.15

        monkeypatch.setattr(
            "xrd_preprocessing.perform_azimuthal_integration",
            _mock_integration,
        )
        h5_path = _create_matador_raw_h5(tmp_path)

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        with h5py.File(h5_path, "r") as f:
            adapter = MatadorRawH5Adapter()
            ctx = adapter.resolve_prediction_context(f, "", "")

        result = run_preprocessing_bridge(
            h5_path, layout_context=ctx, skip_preflight=True,
        )
        assert result.feature_vector is not None
        for val in result.feature_vector.features:
            assert isinstance(val, float)
            assert np.isfinite(val)

    def test_matador_integration_failure_propagates(
        self, tmp_path: Path, monkeypatch,
    ):
        """Integration failure raises PreprocessingBridgeError."""
        def _failing_azi(row, **kwargs):
            raise RuntimeError("Simulated integration failure")

        monkeypatch.setattr(
            "xrd_preprocessing.perform_azimuthal_integration",
            _failing_azi,
        )
        h5_path = _create_matador_raw_h5(tmp_path)

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        with h5py.File(h5_path, "r") as f:
            adapter = MatadorRawH5Adapter()
            ctx = adapter.resolve_prediction_context(f, "", "")

        with pytest.raises(PreprocessingBridgeError, match="integration failed"):
            build_feature_table(h5_path, layout_context=ctx)

    def test_matador_nonfinite_q_i_fails(
        self, tmp_path: Path, monkeypatch,
    ):
        """Non-finite q/i raises PreprocessingBridgeError."""
        def _nan_azi(row, **kwargs):
            n = 100
            q = np.linspace(5.0, 8.0, n)
            i_arr = np.full(n, np.nan)
            return q, i_arr, None, 0.15

        monkeypatch.setattr(
            "xrd_preprocessing.perform_azimuthal_integration",
            _nan_azi,
        )
        h5_path = _create_matador_raw_h5(tmp_path)

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        with h5py.File(h5_path, "r") as f:
            adapter = MatadorRawH5Adapter()
            ctx = adapter.resolve_prediction_context(f, "", "")

        with pytest.raises(PreprocessingBridgeError):
            build_feature_table(h5_path, layout_context=ctx)

    def test_matador_q_length_mismatch_fails(
        self, tmp_path: Path, monkeypatch,
    ):
        """Mismatched q/i lengths between sides raises PreprocessingBridgeError."""
        call_count = [0]

        def _variable_azi(row, **kwargs):
            call_count[0] += 1
            n = 100 if call_count[0] == 1 else 150
            q = np.linspace(5.0, 8.0, n)
            i_arr = np.abs(np.random.default_rng(call_count[0]).normal(10, 2, n))
            return q, i_arr, None, 0.15

        monkeypatch.setattr(
            "xrd_preprocessing.perform_azimuthal_integration",
            _variable_azi,
        )
        h5_path = _create_matador_raw_h5(tmp_path)

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        with h5py.File(h5_path, "r") as f:
            adapter = MatadorRawH5Adapter()
            ctx = adapter.resolve_prediction_context(f, "", "")

        with pytest.raises(PreprocessingBridgeError):
            build_feature_table(h5_path, layout_context=ctx)

    def test_matador_nonmonotonic_q_fails(
        self, tmp_path: Path,
    ):
        """Non-monotonic q raises error at validation layer."""
        from bremen.api.preprocessing_bridge import (
            _validate_q_i_output, PreprocessingBridgeError as _Pbe,
        )
        q = np.array([5.0, 6.0, 5.5, 7.0])
        i_arr = np.array([1.0, 2.0, 3.0, 4.0])
        with pytest.raises(_Pbe, match="strictly increasing"):
            _validate_q_i_output(q, i_arr)

    def test_matador_empty_profiles_fails(
        self, tmp_path: Path,
    ):
        """Empty integration output raises error."""
        from bremen.api.preprocessing_bridge import (
            _validate_q_i_output, PreprocessingBridgeError as _Pbe,
        )
        q = np.array([])
        i_arr = np.array([])
        with pytest.raises(_Pbe, match="empty"):
            _validate_q_i_output(q, i_arr)

    def test_matador_wrapper_nonfinite_output_fails(
        self, tmp_path: Path,
    ):
        """Validator rejects non-finite output."""
        from bremen.api.preprocessing_bridge import (
            _validate_q_i_output, PreprocessingBridgeError as _Pbe,
        )
        q = np.array([5.0, 6.0, 7.0])
        i_arr = np.array([1.0, np.inf, 3.0])
        with pytest.raises(_Pbe, match="non-finite"):
            _validate_q_i_output(q, i_arr)

    def test_matador_wrapper_external_exception(
        self, tmp_path: Path,
    ):
        """External API exception is wrapped (tested via build_feature_table mock)."""
        # This test case is covered by test_matador_integration_failure_propagates
        # which exercises the same error path through build_feature_table.
        pass

    def test_q_i_validation_monotonic_success(
        self, tmp_path: Path, monkeypatch,
    ):
        """Valid monotonic q passes wrapper validation."""
        image = np.random.rand(50, 50).astype(np.float64)
        def _mock_azi(row, **kwargs):
            q = np.linspace(5.0, 8.0, 100)
            i_arr = np.abs(np.random.default_rng(42).normal(10, 2, 100))
            return q, i_arr, np.zeros_like(q), 0.15

        monkeypatch.setattr(
            "xrd_preprocessing.perform_azimuthal_integration",
            _mock_azi,
        )
        from bremen.api.preprocessing_bridge import _matador_raw_to_q_i
        q, i_arr = _matador_raw_to_q_i(image, poni_text="mock poni", npt=100)
        assert len(q) == 100
        assert len(i_arr) == 100
        assert np.all(np.isfinite(q))
        assert np.all(np.isfinite(i_arr))
        assert np.all(np.diff(q) > 0)


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
