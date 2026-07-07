"""Tests for H5 sample patient metadata fallback (PR 0044).

All tests use synthetic H5 files under tmp_path.
Optional real-subset smoke test at the bottom, skipped by default.
"""

from __future__ import annotations

import os
import logging
from pathlib import Path

import h5py
import numpy as np
import pytest

from bremen.api.preflight import (
    H5MetadataError,
    PatientMetadata,
    PreflightResult,
    PreflightStatus,
    resolve_patient_metadata,
    run_h5_preflight,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_standard_h5(
    tmp_path: Path,
    *,
    patient_id: str = "TEST-001",
    target_side: str = "L",
    contralateral_side: str = "R",
) -> Path:
    """Create a synthetic H5 with /patient/id and /scans/ structure."""
    path = tmp_path / "standard.h5"
    with h5py.File(path, "w") as f:
        f.create_dataset("/patient/id", data=patient_id)
        tg = f.create_group("/scans/target")
        tg.create_dataset("side", data=target_side)
        tg.create_dataset(
            "measurements", data=np.random.rand(3, 100).astype(np.float64)
        )
        ct = f.create_group("/scans/contralateral")
        ct.create_dataset("side", data=contralateral_side)
        ct.create_dataset(
            "measurements", data=np.random.rand(3, 100).astype(np.float64)
        )
    return path


def _create_fallback_h5(
    tmp_path: Path,
    *,
    patient_name: str = "Nova_376",
    target_side: str = "L",
    contralateral_side: str = "R",
) -> Path:
    """Create a synthetic H5 with no /patient/id but with calibration
    group layout containing sample/patient_name, plus /scans/ structure
    to avoid secondary failures.
    """
    path = tmp_path / "fallback.h5"
    with h5py.File(path, "w") as f:
        # Calibration group with sample-level patient_name
        calib = f.create_group("/calib_20260128_132622")
        s1 = calib.create_group("sample_01_Right")
        s1.create_dataset("sample/patient_name", data=patient_name)
        s2 = calib.create_group("sample_02_Left")
        s2.create_dataset("sample/patient_name", data=patient_name)

        # Standard /scans/ structure to avoid secondary failures
        tg = f.create_group("/scans/target")
        tg.create_dataset("side", data=target_side)
        tg.create_dataset(
            "measurements", data=np.random.rand(3, 100).astype(np.float64)
        )
        ct = f.create_group("/scans/contralateral")
        ct.create_dataset("side", data=contralateral_side)
        ct.create_dataset(
            "measurements", data=np.random.rand(3, 100).astype(np.float64)
        )
    return path


# ---------------------------------------------------------------------------
# A. Primary path preserved
# ---------------------------------------------------------------------------


class TestPrimaryPathPreserved:
    def test_preflight_uses_patient_id_when_present(self, tmp_path: Path):
        """Preflight uses /patient/id when available."""
        h5_path = _create_standard_h5(tmp_path, patient_id="P001")
        result = run_h5_preflight(h5_path)
        assert result.passed is True
        assert result.patient_id == "P001"
        assert result.patient_identifier_source == "patient_id"
        assert result.metadata_fallback_used is False

    def test_preflight_uses_patient_id_even_when_patient_name_exists(
        self, tmp_path: Path,
    ):
        """/patient/id takes priority even if sample/patient_name exists."""
        path = tmp_path / "both_present.h5"
        with h5py.File(path, "w") as f:
            f.create_dataset("/patient/id", data="P001")
            calib = f.create_group("/calib_test")
            s1 = calib.create_group("sample_01")
            s1.create_dataset("sample/patient_name", data="OtherName")
            tg = f.create_group("/scans/target")
            tg.create_dataset("side", data="L")
            tg.create_dataset(
                "measurements", data=np.random.rand(3, 100).astype(np.float64)
            )
            ct = f.create_group("/scans/contralateral")
            ct.create_dataset("side", data="R")
            ct.create_dataset(
                "measurements", data=np.random.rand(3, 100).astype(np.float64)
            )
        result = run_h5_preflight(path)
        assert result.patient_id == "P001"
        assert result.patient_identifier_source == "patient_id"
        assert result.metadata_fallback_used is False


# ---------------------------------------------------------------------------
# B. Fallback path
# ---------------------------------------------------------------------------


class TestFallbackPath:
    def test_preflight_falls_back_to_sample_patient_name_when_patient_id_missing(
        self, tmp_path: Path,
    ):
        """Preflight falls back to sample/patient_name when /patient/id missing."""
        h5_path = _create_fallback_h5(tmp_path, patient_name="Nova_376")
        result = run_h5_preflight(h5_path)
        assert result.passed is True
        assert result.patient_id == "Nova_376"
        assert result.patient_identifier_source == "patient_name_fallback"
        assert result.metadata_fallback_used is True

    def test_resolve_patient_metadata_fallback(self, tmp_path: Path):
        """Direct resolver call with fallback path."""
        h5_path = _create_fallback_h5(tmp_path, patient_name="Nova_376")
        with h5py.File(h5_path, "r") as f:
            pm = resolve_patient_metadata(f)
        assert pm.patient_identifier == "Nova_376"
        assert pm.patient_identifier_source == "patient_name_fallback"
        assert pm.fallback_used is True
        assert pm.patient_metadata_path is not None
        assert pm.patient_metadata_path.endswith("/sample/patient_name")


# ---------------------------------------------------------------------------
# C. Missing both
# ---------------------------------------------------------------------------


class TestMissingBoth:
    def test_preflight_rejects_missing_patient_id_and_missing_patient_name(
        self, tmp_path: Path,
    ):
        """No /patient/id and no sample/patient_name raises H5MetadataError."""
        path = tmp_path / "no_id_no_name.h5"
        with h5py.File(path, "w") as f:
            tg = f.create_group("/scans/target")
            tg.create_dataset("side", data="L")
            tg.create_dataset(
                "measurements", data=np.random.rand(3, 100).astype(np.float64)
            )
            ct = f.create_group("/scans/contralateral")
            ct.create_dataset("side", data="R")
            ct.create_dataset(
                "measurements", data=np.random.rand(3, 100).astype(np.float64)
            )
        with pytest.raises(H5MetadataError) as exc_info:
            run_h5_preflight(path)
        assert "Missing /patient/id" not in str(exc_info.value)


# ---------------------------------------------------------------------------
# D. Empty patient_name
# ---------------------------------------------------------------------------


class TestEmptyPatientName:
    def test_preflight_rejects_empty_sample_patient_name(self, tmp_path: Path):
        """Empty sample/patient_name raises H5MetadataError."""
        path = tmp_path / "empty_name.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("/calib_test")
            calib.create_dataset("sample_01/sample/patient_name", data="")
            tg = f.create_group("/scans/target")
            tg.create_dataset("side", data="L")
            tg.create_dataset(
                "measurements", data=np.random.rand(3, 100).astype(np.float64)
            )
            ct = f.create_group("/scans/contralateral")
            ct.create_dataset("side", data="R")
            ct.create_dataset(
                "measurements", data=np.random.rand(3, 100).astype(np.float64)
            )
        with pytest.raises(H5MetadataError) as exc_info:
            run_h5_preflight(path)
        # Error message must not include the empty value
        err_msg = str(exc_info.value)
        # Check it's the expected safe error message
        assert "Missing patient identifier metadata" in err_msg or "Ambiguous" in err_msg

    def test_preflight_rejects_whitespace_only_patient_name(self, tmp_path: Path):
        """Whitespace-only sample/patient_name raises H5MetadataError."""
        path = tmp_path / "whitespace_name.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("/calib_test")
            calib.create_dataset("sample_01/sample/patient_name", data="   ")
            tg = f.create_group("/scans/target")
            tg.create_dataset("side", data="L")
            tg.create_dataset(
                "measurements", data=np.random.rand(3, 100).astype(np.float64)
            )
            ct = f.create_group("/scans/contralateral")
            ct.create_dataset("side", data="R")
            ct.create_dataset(
                "measurements", data=np.random.rand(3, 100).astype(np.float64)
            )
        with pytest.raises(H5MetadataError):
            run_h5_preflight(path)


# ---------------------------------------------------------------------------
# E. Ambiguous patient names
# ---------------------------------------------------------------------------


class TestAmbiguousPatientNames:
    def test_preflight_rejects_ambiguous_sample_patient_names(self, tmp_path: Path):
        """Multiple distinct patient_name values raise H5MetadataError."""
        path = tmp_path / "ambiguous.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("/calib_test")
            s1 = calib.create_group("sample_01")
            s1.create_dataset("sample/patient_name", data="Nova_376")
            s2 = calib.create_group("sample_02")
            s2.create_dataset("sample/patient_name", data="Nova_378")
            tg = f.create_group("/scans/target")
            tg.create_dataset("side", data="L")
            tg.create_dataset(
                "measurements", data=np.random.rand(3, 100).astype(np.float64)
            )
            ct = f.create_group("/scans/contralateral")
            ct.create_dataset("side", data="R")
            ct.create_dataset(
                "measurements", data=np.random.rand(3, 100).astype(np.float64)
            )
        with pytest.raises(H5MetadataError) as exc_info:
            run_h5_preflight(path)
        # Error message must not include raw values
        err_msg = str(exc_info.value)
        assert "Nova_376" not in err_msg
        assert "Nova_378" not in err_msg


# ---------------------------------------------------------------------------
# F. No raw patient_name in logs
# ---------------------------------------------------------------------------


class TestNoRawNameInLogs:
    def test_preflight_does_not_log_raw_patient_name(self, tmp_path: Path, caplog):
        """No raw patient_name appears in preflight logs."""
        caplog.set_level(logging.INFO)
        h5_path = _create_fallback_h5(tmp_path, patient_name="Nova_376")
        result = run_h5_preflight(h5_path)
        assert result.passed is True
        assert "Nova_376" not in caplog.text


# ---------------------------------------------------------------------------
# G/H. Resolver unit tests
# ---------------------------------------------------------------------------


class TestResolverUnit:
    def test_resolve_patient_metadata_primary(self, tmp_path: Path):
        """Direct resolver call with /patient/id present."""
        h5_path = _create_standard_h5(tmp_path, patient_id="UNIT-001")
        with h5py.File(h5_path, "r") as f:
            pm = resolve_patient_metadata(f)
        assert pm.patient_identifier == "UNIT-001"
        assert pm.patient_identifier_source == "patient_id"
        assert pm.patient_metadata_path == "/patient/id"
        assert pm.fallback_used is False

    def test_resolve_patient_metadata_primary_with_bytes(self, tmp_path: Path):
        """Direct resolver call with /patient/id stored as bytes."""
        path = tmp_path / "bytes_id.h5"
        with h5py.File(path, "w") as f:
            f.create_dataset("/patient/id", data=b"BYTES-001")
            tg = f.create_group("/scans/target")
            tg.create_dataset("side", data="L")
            tg.create_dataset(
                "measurements", data=np.random.rand(3, 100).astype(np.float64)
            )
            ct = f.create_group("/scans/contralateral")
            ct.create_dataset("side", data="R")
            ct.create_dataset(
                "measurements", data=np.random.rand(3, 100).astype(np.float64)
            )
        with h5py.File(path, "r") as f:
            pm = resolve_patient_metadata(f)
        assert pm.patient_identifier == "BYTES-001"
        assert pm.patient_identifier_source == "patient_id"

    def test_resolve_patient_metadata_fallback(self, tmp_path: Path):
        """Direct resolver call with fallback path."""
        h5_path = _create_fallback_h5(tmp_path, patient_name="FallbackName")
        with h5py.File(h5_path, "r") as f:
            pm = resolve_patient_metadata(f)
        assert pm.patient_identifier == "FallbackName"
        assert pm.patient_identifier_source == "patient_name_fallback"
        assert pm.fallback_used is True
        assert pm.patient_metadata_path is not None


# ---------------------------------------------------------------------------
# PreflightResult new fields
# ---------------------------------------------------------------------------


class TestPreflightResultNewFields:
    def test_preflight_result_has_new_fields(self, tmp_path: Path):
        """PreflightResult includes patient_identifier_source and metadata_fallback_used."""
        h5_path = _create_standard_h5(tmp_path)
        result = run_h5_preflight(h5_path)
        assert hasattr(result, "patient_identifier_source")
        assert hasattr(result, "metadata_fallback_used")
        assert result.patient_identifier_source == "patient_id"
        assert result.metadata_fallback_used is False

    def test_preflight_result_metadata_includes_source_fields(self, tmp_path: Path):
        """PreflightResult.metadata includes patient_identifier_source and metadata_fallback_used."""
        h5_path = _create_standard_h5(tmp_path)
        result = run_h5_preflight(h5_path)
        assert "patient_identifier_source" in result.metadata
        assert "metadata_fallback_used" in result.metadata
        assert result.metadata["patient_identifier_source"] == "patient_id"
        assert result.metadata["metadata_fallback_used"] is False


# ---------------------------------------------------------------------------
# Real subset smoke (opt-in, skipped in CI)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    "BREMEN_H5_PREFLIGHT_SMOKE_PATH" not in os.environ,
    reason="BREMEN_H5_PREFLIGHT_SMOKE_PATH not set — skipping real subset smoke",
)
def test_preflight_no_longer_fails_at_missing_patient_id():
    """Opt-in smoke test: preflight no longer fails specifically at Missing /patient/id.

    Set BREMEN_H5_PREFLIGHT_SMOKE_PATH to the path of a real H5
    container to enable this test.

    NOTE: Preflight may still fail due to missing /scans/ layout paths.
    This test only asserts the specific /patient/id error is gone.
    """
    h5_path = os.environ["BREMEN_H5_PREFLIGHT_SMOKE_PATH"]
    try:
        result = run_h5_preflight(h5_path)
        if result.passed:
            assert hasattr(result, "patient_identifier_source")
            assert result.metadata_fallback_used == (
                result.patient_identifier_source == "patient_name_fallback"
            )
    except H5MetadataError as e:
        # Must not fail on "Missing /patient/id"
        assert "Missing /patient/id" not in str(e), (
            f"Still failing on missing /patient/id: {e}"
        )
