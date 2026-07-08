"""Tests for calibration sample preprocessing bridge (PR 0047).

All tests use synthetic H5 files under tmp_path.
Optional real-subset smoke test at the bottom, skipped by default.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import h5py
import numpy as np
import pytest

from bremen.api.preprocessing_bridge import (
    BREMEN_V01_FEATURE_COLUMNS,
    FEATURE_SCHEMA_VERSION,
    PreprocessingBridgeError,
    build_feature_table,
    run_preprocessing_bridge,
)
from bremen.api.preflight import run_h5_preflight


# ---------------------------------------------------------------------------
# Helpers — reuse calibration H5 creation pattern from test_bremen_h5_layouts
# ---------------------------------------------------------------------------


def _create_canonical_h5(tmp_path: Path) -> Path:
    """Create a synthetic canonical-layout H5."""
    path = tmp_path / "canonical.h5"
    with h5py.File(path, "w") as f:
        f.create_dataset("/patient/id", data="TEST-001")
        tg = f.create_group("/scans/target")
        tg.create_dataset("side", data="L")
        rng = np.random.default_rng(42)
        tg.create_dataset(
            "measurements", data=rng.normal(0, 1, (3, 100)).astype(np.float64)
        )
        ct = f.create_group("/scans/contralateral")
        ct.create_dataset("side", data="R")
        ct.create_dataset(
            "measurements",
            data=rng.normal(0.3, 1, (3, 100)).astype(np.float64),
        )
    return path


def _create_calibration_h5(
    tmp_path: Path,
    *,
    target_patient_name: str = "Nova_376",
    control_patient_name: str | None = None,
    target_sample_type: str = "RIGHT BREAST",
    control_sample_type: str = "LEFT BREAST",
    target_sets: int = 3,
    control_sets: int = 3,
    calib_group_name: str = "calib_20260128_132622",
    target_sample_name: str = "sample_01_20260128_Nova_376_Right",
    control_sample_name: str = "sample_02_20260128_Nova_376_Left",
    target_iq_length: int = 100,
    control_iq_length: int | None = None,
) -> Path:
    """Create a synthetic calibration sample layout H5.

    If control_patient_name is None, uses same as target_patient_name.
    If control_iq_length is None, uses target_iq_length.
    """
    if control_patient_name is None:
        control_patient_name = target_patient_name
    if control_iq_length is None:
        control_iq_length = target_iq_length

    path = tmp_path / "calibration.h5"
    rng = np.random.default_rng(42)

    with h5py.File(path, "w") as f:
        calib = f.create_group(f"/{calib_group_name}")

        # Target sample
        t_group = calib.create_group(target_sample_name)
        t_group.create_dataset("sample/name", data=target_sample_name)
        t_group.create_dataset(
            "sample/patient_name", data=target_patient_name
        )
        t_group.create_dataset(
            "sample/sample_type", data=target_sample_type
        )
        _add_sets(t_group, target_sets, rng, target_iq_length)

        # Control sample
        c_group = calib.create_group(control_sample_name)
        c_group.create_dataset("sample/name", data=control_sample_name)
        c_group.create_dataset(
            "sample/patient_name", data=control_patient_name
        )
        c_group.create_dataset(
            "sample/sample_type", data=control_sample_type
        )
        _add_sets(c_group, control_sets, rng, control_iq_length)

    return path


def _add_sets(
    sample_group: h5py.Group,
    count: int,
    rng: np.random.Generator,
    iq_length: int,
) -> None:
    """Add measurement set groups to a sample group with random I/Q data."""
    for i in range(1, count + 1):
        set_group = sample_group.create_group(f"sets/set_{i:03d}_sample_main")
        int_group = set_group.create_group("integration")
        int_group.create_dataset(
            "i", data=rng.normal(0, 1, iq_length).astype(np.float64)
        )
        int_group.create_dataset(
            "q", data=rng.normal(0, 1, iq_length).astype(np.float64)
        )


def _get_target_ref() -> str:
    """Return default target scan ref for calibration H5."""
    return "calib_20260128_132622/sample_01_20260128_Nova_376_Right"


def _get_control_ref() -> str:
    """Return default control scan ref for calibration H5."""
    return "calib_20260128_132622/sample_02_20260128_Nova_376_Left"


# ---------------------------------------------------------------------------
# A. Canonical preprocessing still passes
# ---------------------------------------------------------------------------


class TestCanonicalPreserved:
    def test_canonical_preprocessing_still_passes(self, tmp_path: Path):
        """Existing canonical H5 bridge path remains unchanged."""
        h5_path = _create_canonical_h5(tmp_path)
        result = run_preprocessing_bridge(h5_path)
        assert result.passed is True
        assert result.feature_vector is not None
        assert len(result.feature_vector.features) == 15
        for val in result.feature_vector.features:
            assert np.isfinite(val)

    def test_canonical_with_layout_none(self, tmp_path: Path):
        """Explicit None layout_context uses canonical path."""
        h5_path = _create_canonical_h5(tmp_path)
        result = run_preprocessing_bridge(
            h5_path,
            # Run preflight ourselves, pass result with no calibration metadata
            preflight_result=run_h5_preflight(h5_path),
        )
        assert result.passed is True
        assert result.feature_vector is not None
        assert len(result.feature_vector.features) == 15


# ---------------------------------------------------------------------------
# B. Calibration sample reads integration i/q arrays
# ---------------------------------------------------------------------------


class TestCalibrationReadsIntegrationIQ:
    def test_calibration_sample_reads_integration_iq_arrays(
        self, tmp_path: Path,
    ):
        """Calibration bridge reads integration i/q and produces 15 features."""
        h5_path = _create_calibration_h5(tmp_path)

        # Run preflight with explicit refs to get paths in metadata
        preflight = run_h5_preflight(
            h5_path,
            target_scan_ref=_get_target_ref(),
            control_scan_ref=_get_control_ref(),
        )
        assert preflight.passed is True

        # Run bridge with associated preflight result (reconstructs layout_context)
        result = run_preprocessing_bridge(
            h5_path, preflight_result=preflight
        )
        assert result.passed is True
        assert result.feature_vector is not None
        assert len(result.feature_vector.features) == 15
        for val in result.feature_vector.features:
            assert np.isfinite(val)

        # Schema version preserved
        assert result.feature_vector.feature_schema_version == FEATURE_SCHEMA_VERSION

        # Patient metadata preserved
        assert result.feature_vector.patient_id == "Nova_376"


# ---------------------------------------------------------------------------
# C. Multiple sets handled deterministically
# ---------------------------------------------------------------------------


class TestMultipleSetsDeterministic:
    def test_calibration_sample_multiple_sets_are_handled_deterministically(
        self, tmp_path: Path,
    ):
        """Bridge produces identical results on repeated runs."""
        h5_path = _create_calibration_h5(
            tmp_path, target_sets=5, control_sets=5
        )
        preflight = run_h5_preflight(
            h5_path,
            target_scan_ref=_get_target_ref(),
            control_scan_ref=_get_control_ref(),
        )
        assert preflight.passed is True

        r1 = run_preprocessing_bridge(h5_path, preflight_result=preflight)
        r2 = run_preprocessing_bridge(h5_path, preflight_result=preflight)

        assert r1.feature_vector is not None
        assert r2.feature_vector is not None
        for a, b in zip(r1.feature_vector.features, r2.feature_vector.features):
            assert a == pytest.approx(b)


# ---------------------------------------------------------------------------
# D. Missing integration/i fails safely
# ---------------------------------------------------------------------------


class TestMissingIntegrationI:
    def test_calibration_sample_missing_integration_i_fails_safely(
        self, tmp_path: Path,
    ):
        """Missing integration/i raises PreprocessingBridgeError."""
        path = tmp_path / "missing_i.h5"
        rng = np.random.default_rng(42)
        with h5py.File(path, "w") as f:
            calib = f.create_group("/calib_test")
            s1 = calib.create_group("target_sample")
            s1.create_dataset("sample/patient_name", data="P001")
            s1.create_dataset("sample/sample_type", data="RIGHT BREAST")
            set1 = s1.create_group("sets/set_001_sample_main")
            intg = set1.create_group("integration")
            # Only integration/q, no integration/i
            intg.create_dataset("q", data=rng.normal(0, 1, 100))
            s2 = calib.create_group("control_sample")
            s2.create_dataset("sample/patient_name", data="P001")
            s2.create_dataset("sample/sample_type", data="LEFT BREAST")
            set2 = s2.create_group("sets/set_001_sample_main")
            intg2 = set2.create_group("integration")
            intg2.create_dataset("i", data=rng.normal(0, 1, 100))
            intg2.create_dataset("q", data=rng.normal(0, 1, 100))

        preflight = run_h5_preflight(
            path,
            target_scan_ref="calib_test/target_sample",
            control_scan_ref="calib_test/control_sample",
        )
        with pytest.raises(PreprocessingBridgeError, match="Missing calibration integration/i"):
            run_preprocessing_bridge(path, preflight_result=preflight)


# ---------------------------------------------------------------------------
# E. Missing integration/q fails safely
# ---------------------------------------------------------------------------


class TestMissingIntegrationQ:
    def test_calibration_sample_missing_integration_q_fails_safely(
        self, tmp_path: Path,
    ):
        """Missing integration/q raises PreprocessingBridgeError."""
        path = tmp_path / "missing_q.h5"
        rng = np.random.default_rng(42)
        with h5py.File(path, "w") as f:
            calib = f.create_group("/calib_test")
            s1 = calib.create_group("target_sample")
            s1.create_dataset("sample/patient_name", data="P001")
            s1.create_dataset("sample/sample_type", data="RIGHT BREAST")
            set1 = s1.create_group("sets/set_001_sample_main")
            intg = set1.create_group("integration")
            # Only integration/i, no integration/q
            intg.create_dataset("i", data=rng.normal(0, 1, 100))
            s2 = calib.create_group("control_sample")
            s2.create_dataset("sample/patient_name", data="P001")
            s2.create_dataset("sample/sample_type", data="LEFT BREAST")
            set2 = s2.create_group("sets/set_001_sample_main")
            intg2 = set2.create_group("integration")
            intg2.create_dataset("i", data=rng.normal(0, 1, 100))
            intg2.create_dataset("q", data=rng.normal(0, 1, 100))

        preflight = run_h5_preflight(
            path,
            target_scan_ref="calib_test/target_sample",
            control_scan_ref="calib_test/control_sample",
        )
        with pytest.raises(PreprocessingBridgeError, match="Missing calibration integration/q"):
            run_preprocessing_bridge(path, preflight_result=preflight)


# ---------------------------------------------------------------------------
# F. Mismatched i/q lengths fails safely
# ---------------------------------------------------------------------------


class TestMismatchedIQLengths:
    def test_calibration_sample_mismatched_iq_lengths_fails_safely(
        self, tmp_path: Path,
    ):
        """Mismatched i/q lengths raise PreprocessingBridgeError."""
        path = tmp_path / "mismatched_iq.h5"
        rng = np.random.default_rng(42)
        with h5py.File(path, "w") as f:
            calib = f.create_group("/calib_test")
            s1 = calib.create_group("target_sample")
            s1.create_dataset("sample/patient_name", data="P001")
            s1.create_dataset("sample/sample_type", data="RIGHT BREAST")
            set1 = s1.create_group("sets/set_001_sample_main")
            intg = set1.create_group("integration")
            intg.create_dataset("i", data=rng.normal(0, 1, 100))   # length 100
            intg.create_dataset("q", data=rng.normal(0, 1, 50))    # length 50
            s2 = calib.create_group("control_sample")
            s2.create_dataset("sample/patient_name", data="P001")
            s2.create_dataset("sample/sample_type", data="LEFT BREAST")
            set2 = s2.create_group("sets/set_001_sample_main")
            intg2 = set2.create_group("integration")
            intg2.create_dataset("i", data=rng.normal(0, 1, 100))
            intg2.create_dataset("q", data=rng.normal(0, 1, 100))

        preflight = run_h5_preflight(
            path,
            target_scan_ref="calib_test/target_sample",
            control_scan_ref="calib_test/control_sample",
        )
        with pytest.raises(PreprocessingBridgeError, match="different lengths"):
            run_preprocessing_bridge(path, preflight_result=preflight)


# ---------------------------------------------------------------------------
# G. Outputs v0.1 feature schema order
# ---------------------------------------------------------------------------


class TestFeatureSchemaOrder:
    def test_calibration_sample_outputs_v01_feature_schema_order(
        self, tmp_path: Path,
    ):
        """Calibration bridge produces exact v0.1 schema order."""
        h5_path = _create_calibration_h5(tmp_path)
        preflight = run_h5_preflight(
            h5_path,
            target_scan_ref=_get_target_ref(),
            control_scan_ref=_get_control_ref(),
        )
        result = run_preprocessing_bridge(h5_path, preflight_result=preflight)
        assert result.feature_vector is not None
        for i, expected in enumerate(BREMEN_V01_FEATURE_COLUMNS):
            assert result.feature_vector.feature_names[i] == expected, (
                f"Index {i}: expected {expected!r}, "
                f"got {result.feature_vector.feature_names[i]!r}"
            )

    def test_calibration_sample_feature_schema_version(self, tmp_path: Path):
        """Schema version is v0.1 for calibration path."""
        h5_path = _create_calibration_h5(tmp_path)
        preflight = run_h5_preflight(
            h5_path,
            target_scan_ref=_get_target_ref(),
            control_scan_ref=_get_control_ref(),
        )
        result = run_preprocessing_bridge(h5_path, preflight_result=preflight)
        assert result.feature_vector is not None
        assert result.feature_vector.feature_schema_version == FEATURE_SCHEMA_VERSION

    def test_calibration_sample_mahalanobis_lowercase(self, tmp_path: Path):
        """mahalanobis1/2 are lowercase in calibration path."""
        h5_path = _create_calibration_h5(tmp_path)
        preflight = run_h5_preflight(
            h5_path,
            target_scan_ref=_get_target_ref(),
            control_scan_ref=_get_control_ref(),
        )
        result = run_preprocessing_bridge(h5_path, preflight_result=preflight)
        assert result.feature_vector is not None
        assert result.feature_vector.feature_names[3] == "mahalanobis1"
        assert result.feature_vector.feature_names[7] == "mahalanobis2"


# ---------------------------------------------------------------------------
# H. No raw patient_name or feature values in logs
# ---------------------------------------------------------------------------


class TestNoRawPatientName:
    def test_calibration_sample_does_not_log_raw_patient_name_or_feature_values(
        self, tmp_path: Path, caplog
    ):
        """No raw patient_name or raw feature values appear in logs."""
        caplog.set_level(logging.INFO)
        h5_path = _create_calibration_h5(tmp_path)
        preflight = run_h5_preflight(
            h5_path,
            target_scan_ref=_get_target_ref(),
            control_scan_ref=_get_control_ref(),
        )
        result = run_preprocessing_bridge(h5_path, preflight_result=preflight)
        assert result.passed is True
        # No raw patient identifiers in log
        assert "Nova_376" not in caplog.text


# ---------------------------------------------------------------------------
# I. Does not read raw image arrays
# ---------------------------------------------------------------------------


class TestNoRawImageArrays:
    def test_calibration_sample_does_not_read_raw_image_arrays(
        self, tmp_path: Path,
    ):
        """Bridge does not access raw/data or measurements/*/data."""
        h5_path = tmp_path / "has_raw.h5"
        rng = np.random.default_rng(42)
        with h5py.File(h5_path, "w") as f:
            calib = f.create_group("/calib_test")
            t_group = calib.create_group("target_sample")
            t_group.create_dataset("sample/patient_name", data="P001")
            t_group.create_dataset("sample/sample_type", data="RIGHT BREAST")
            set1 = t_group.create_group("sets/set_001_sample_main")
            intg = set1.create_group("integration")
            intg.create_dataset("i", data=rng.normal(0, 1, 100))
            intg.create_dataset("q", data=rng.normal(0, 1, 100))
            # Trap — raw/data and measurements/*/data exist
            set1.create_group("raw").create_dataset(
                "data", data=rng.normal(0, 1, (512, 768))
            )
            set1.create_group("measurements").create_group("det_1_ash512x768").create_dataset(
                "data", data=rng.normal(0, 1, (512, 768))
            )

            c_group = calib.create_group("control_sample")
            c_group.create_dataset("sample/patient_name", data="P001")
            c_group.create_dataset("sample/sample_type", data="LEFT BREAST")
            set2 = c_group.create_group("sets/set_001_sample_main")
            intg2 = set2.create_group("integration")
            intg2.create_dataset("i", data=rng.normal(0, 1, 100))
            intg2.create_dataset("q", data=rng.normal(0, 1, 100))
            # Trap — raw/data
            set2.create_group("raw").create_dataset(
                "data", data=rng.normal(0, 1, (512, 768))
            )

        preflight = run_h5_preflight(
            h5_path,
            target_scan_ref="calib_test/target_sample",
            control_scan_ref="calib_test/control_sample",
        )
        # Bridge should succeed without reading raw/data or measurements/data
        result = run_preprocessing_bridge(h5_path, preflight_result=preflight)
        assert result.passed is True
        assert result.feature_vector is not None
        assert len(result.feature_vector.features) == 15
        for val in result.feature_vector.features:
            assert np.isfinite(val)


# ---------------------------------------------------------------------------
# J. Optional real H5 smoke (skipped by default)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    "BREMEN_H5_PREFLIGHT_SMOKE_PATH" not in os.environ,
    reason="Set BREMEN_H5_PREFLIGHT_SMOKE_PATH to enable",
)
def test_calibration_preprocessing_real_h5_smoke():
    """Assert calibration preprocessing moves past bridge on real H5.

    Explicit refs:
      target_scan_ref = "calib_20260128_132622/sample_01_20260128_Nova_376_Right"
      control_scan_ref = "calib_20260128_132622/sample_02_20260128_Nova_376_Left"

    NOTE: Full prediction may still fail at later stages (inference wiring).
    This test only asserts the bridge no longer fails.
    """
    h5_path = os.environ["BREMEN_H5_PREFLIGHT_SMOKE_PATH"]
    target_ref = "calib_20260128_132622/sample_01_20260128_Nova_376_Right"
    control_ref = "calib_20260128_132622/sample_02_20260128_Nova_376_Left"

    preflight = run_h5_preflight(
        h5_path,
        target_scan_ref=target_ref,
        control_scan_ref=control_ref,
    )
    assert preflight.passed is True, f"Preflight failed: {preflight.status}"

    result = run_preprocessing_bridge(h5_path, preflight_result=preflight)
    assert result.passed is True, f"Bridge failed: {result.warnings}"
    assert result.feature_vector is not None
    assert len(result.feature_vector.features) == 15
    for val in result.feature_vector.features:
        assert np.isfinite(val), f"Non-finite feature value: {val}"
