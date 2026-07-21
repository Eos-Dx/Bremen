"""Tests for H5 layout adapter boundary (PR 0045).

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

from bremen.api.h5_layouts import (
    H5PredictionContext,
    H5LayoutAdapter,
    CanonicalH5LayoutAdapter,
    CalibrationSampleH5LayoutAdapter,
    detect_layout,
    register_adapter,
    _validate_ref,
    _breast_type_to_side,
    _count_sets,
    _has_sample_metadata,
    _read_sample_metadata_str,
)
from bremen.api.preflight import (
    H5ContainerError,
    H5MetadataError,
    H5PatientMismatchError,
    H5SideMismatchError,
    PreflightResult,
    run_h5_preflight,
)


# ---------------------------------------------------------------------------
# Brittle-test hardening helper
# ---------------------------------------------------------------------------


def _assert_h5_error(
    exc_info: pytest.ExceptionInfo,
    expected_class_name: str,
    expected_message: str,
) -> None:
    """Assert an exception by class name and message, not identity.

    Cross-suite import/reload/order can produce a distinct exception
    class object even when the same exception is raised.  This helper
    avoids ``pytest.raises(SomeException)`` identity checks and
    instead validates by ``__class__.__name__`` and
    ``__class__.__module__``.
    """
    err = exc_info.value
    assert err.__class__.__name__ == expected_class_name, (
        f"Expected {expected_class_name}, got {err.__class__.__name__}"
    )
    assert err.__class__.__module__.endswith("preflight"), (
        f"Expected module preflight, got {err.__class__.__module__}"
    )
    assert expected_message in str(err), (
        f"Expected {expected_message!r} in {str(err)!r}"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_canonical_h5(tmp_path: Path) -> Path:
    """Create a synthetic canonical-layout H5."""
    path = tmp_path / "canonical.h5"
    with h5py.File(path, "w") as f:
        f.create_dataset("/patient/id", data="TEST-001")
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
) -> Path:
    """Create a synthetic calibration sample layout H5.

    If control_patient_name is None, uses same as target_patient_name.
    """
    if control_patient_name is None:
        control_patient_name = target_patient_name

    path = tmp_path / "calibration.h5"
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
        _add_sets(t_group, target_sets)

        # Control sample
        c_group = calib.create_group(control_sample_name)
        c_group.create_dataset("sample/name", data=control_sample_name)
        c_group.create_dataset(
            "sample/patient_name", data=control_patient_name
        )
        c_group.create_dataset(
            "sample/sample_type", data=control_sample_type
        )
        _add_sets(c_group, control_sets)

    return path


def _add_sets(sample_group: h5py.Group, count: int) -> None:
    """Add measurement set groups to a sample group."""
    for i in range(1, count + 1):
        set_group = sample_group.create_group(f"sets/set_{i:03d}_sample_main")
        int_group = set_group.create_group("integration")
        int_group.create_dataset("i", data=np.array([1.0, 2.0, 3.0]))
        int_group.create_dataset("q", data=np.array([4.0, 5.0, 6.0]))


def _get_target_ref() -> str:
    """Return default target scan ref for calibration H5."""
    return "calib_20260128_132622/sample_01_20260128_Nova_376_Right"


def _get_control_ref() -> str:
    """Return default control scan ref for calibration H5."""
    return "calib_20260128_132622/sample_02_20260128_Nova_376_Left"


# ---------------------------------------------------------------------------
# A. Canonical layout detection
# ---------------------------------------------------------------------------


class TestCanonicalLayoutDetection:
    def test_detects_canonical_layout(self, tmp_path: Path):
        """Canonical adapter detects canonical H5."""
        h5_path = _create_canonical_h5(tmp_path)
        canonical = CanonicalH5LayoutAdapter()
        calibration = CalibrationSampleH5LayoutAdapter()
        with h5py.File(h5_path, "r") as f:
            assert canonical.detect(f) is True
            assert calibration.detect(f) is False

    def test_canonical_detect_refuses_non_canonical(self, tmp_path: Path):
        """Canonical adapter does not detect non-canonical H5."""
        h5_path = _create_calibration_h5(tmp_path)
        canonical = CanonicalH5LayoutAdapter()
        with h5py.File(h5_path, "r") as f:
            assert canonical.detect(f) is False


# ---------------------------------------------------------------------------
# B. Calibration sample layout detection
# ---------------------------------------------------------------------------


class TestCalibrationLayoutDetection:
    def test_detects_calibration_sample_layout(self, tmp_path: Path):
        """Calibration adapter detects calibration-style H5."""
        h5_path = _create_calibration_h5(tmp_path)
        calibration = CalibrationSampleH5LayoutAdapter()
        canonical = CanonicalH5LayoutAdapter()
        with h5py.File(h5_path, "r") as f:
            assert calibration.detect(f) is True
            assert canonical.detect(f) is False

    def test_calibration_has_sample_metadata(self, tmp_path: Path):
        """_has_sample_metadata returns True for calibration groups."""
        h5_path = _create_calibration_h5(tmp_path)
        with h5py.File(h5_path, "r") as f:
            calib = f["/calib_20260128_132622"]
            assert _has_sample_metadata(calib) is True


# ---------------------------------------------------------------------------
# C. Explicit calibration context resolution
# ---------------------------------------------------------------------------


class TestCalibrationContextResolution:
    def test_resolves_explicit_calibration_target_control_context(
        self, tmp_path: Path,
    ):
        """Calibration adapter resolves explicit target/control refs."""
        h5_path = _create_calibration_h5(tmp_path)
        adapter = CalibrationSampleH5LayoutAdapter()
        with h5py.File(h5_path, "r") as f:
            ctx = adapter.resolve_prediction_context(
                f, _get_target_ref(), _get_control_ref()
            )
        assert ctx.layout_name == "calibration_sample"
        assert ctx.target_group_path == f"/{_get_target_ref()}"
        assert ctx.control_group_path == f"/{_get_control_ref()}"
        assert ctx.patient_identifier == "Nova_376"
        assert ctx.patient_identifier_source == "patient_name_fallback"
        assert ctx.metadata_fallback_used is True
        assert ctx.target_side == "RIGHT"
        assert ctx.control_side == "LEFT"
        assert ctx.target_measurement_count == 3
        assert ctx.control_measurement_count == 3
        assert ctx.adapter_metadata.get("calibration_group") == "calib_20260128_132622"

    def test_canonical_adapter_resolves_canonical_context(
        self, tmp_path: Path,
    ):
        """Canonical adapter resolves canonical target/control context."""
        h5_path = _create_canonical_h5(tmp_path)
        adapter = CanonicalH5LayoutAdapter()
        with h5py.File(h5_path, "r") as f:
            ctx = adapter.resolve_prediction_context(
                f, "target", "contralateral"
            )
        assert ctx.layout_name == "canonical"
        assert ctx.target_group_path == "/scans/target"
        assert ctx.control_group_path == "/scans/contralateral"
        assert ctx.patient_identifier == "TEST-001"
        assert ctx.patient_identifier_source == "patient_id"
        assert ctx.metadata_fallback_used is False


# ---------------------------------------------------------------------------
# D. Missing refs
# ---------------------------------------------------------------------------


class TestMissingRefs:
    def test_rejects_missing_target_ref(self, tmp_path: Path):
        """Missing target scan ref raises error."""
        h5_path = _create_calibration_h5(tmp_path)
        adapter = CalibrationSampleH5LayoutAdapter()
        with h5py.File(h5_path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(
                    f, "nonexistent_group", _get_control_ref()
                )
        _assert_h5_error(exc_info, "H5ContainerError", "Target scan group not found")

    def test_rejects_missing_control_ref(self, tmp_path: Path):
        """Missing control scan ref raises error."""
        h5_path = _create_calibration_h5(tmp_path)
        adapter = CalibrationSampleH5LayoutAdapter()
        with h5py.File(h5_path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(
                    f, _get_target_ref(), "nonexistent_group"
                )
        _assert_h5_error(exc_info, "H5ContainerError", "Control scan group not found")


# ---------------------------------------------------------------------------
# E. Mismatched patient names
# ---------------------------------------------------------------------------


class TestMismatchedPatientNames:
    def test_rejects_mismatched_patient_names(self, tmp_path: Path):
        """Different patient_name values raise error."""
        h5_path = _create_calibration_h5(
            tmp_path,
            target_patient_name="Nova_376",
            control_patient_name="Nova_378",
        )
        adapter = CalibrationSampleH5LayoutAdapter()
        with h5py.File(h5_path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(
                    f, _get_target_ref(), _get_control_ref()
                )
        _assert_h5_error(
            exc_info, "H5PatientMismatchError", "patient names do not match"
        )
        # Must not contain raw patient_name values
        err_msg = str(exc_info.value)
        assert "Nova_376" not in err_msg
        assert "Nova_378" not in err_msg


# ---------------------------------------------------------------------------
# F. Same side samples
# ---------------------------------------------------------------------------


class TestSameSide:
    def test_rejects_same_side_samples(self, tmp_path: Path):
        """Both RIGHT BREAST raises H5SideMismatchError."""
        h5_path = _create_calibration_h5(
            tmp_path,
            target_sample_type="RIGHT BREAST",
            control_sample_type="RIGHT BREAST",
        )
        adapter = CalibrationSampleH5LayoutAdapter()
        with h5py.File(h5_path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(
                    f, _get_target_ref(), _get_control_ref()
                )
        _assert_h5_error(
            exc_info, "H5SideMismatchError", "same breast side"
        )

    def test_rejects_both_left_breast(self, tmp_path: Path):
        """Both LEFT BREAST raises H5SideMismatchError."""
        h5_path = _create_calibration_h5(
            tmp_path,
            target_sample_type="LEFT BREAST",
            control_sample_type="LEFT BREAST",
        )
        adapter = CalibrationSampleH5LayoutAdapter()
        with h5py.File(h5_path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(
                    f, _get_target_ref(), _get_control_ref()
                )
        _assert_h5_error(
            exc_info, "H5SideMismatchError", "same breast side"
        )


# ---------------------------------------------------------------------------
# G. Missing sample_type
# ---------------------------------------------------------------------------


class TestMissingSampleType:
    def test_rejects_missing_sample_type(self, tmp_path: Path):
        """Missing sample/sample_type raises H5MetadataError."""
        path = tmp_path / "missing_sample_type.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("/calib_test")
            s1 = calib.create_group("target_sample")
            s1.create_dataset("sample/patient_name", data="P001")
            s2 = calib.create_group("control_sample")
            s2.create_dataset("sample/patient_name", data="P001")
            s2.create_dataset("sample/sample_type", data="LEFT BREAST")

        adapter = CalibrationSampleH5LayoutAdapter()
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(
                    f, "calib_test/target_sample", "calib_test/control_sample"
                )
        _assert_h5_error(
            exc_info, "H5MetadataError", "Missing sample_type metadata"
        )


# ---------------------------------------------------------------------------
# H. Missing patient_name
# ---------------------------------------------------------------------------


class TestMissingPatientName:
    def test_rejects_missing_patient_name(self, tmp_path: Path):
        """Missing sample/patient_name raises H5MetadataError."""
        path = tmp_path / "missing_patient_name.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("/calib_test")
            s1 = calib.create_group("target_sample")
            s1.create_dataset("sample/sample_type", data="RIGHT BREAST")
            s2 = calib.create_group("control_sample")
            s2.create_dataset("sample/patient_name", data="P001")
            s2.create_dataset("sample/sample_type", data="LEFT BREAST")

        adapter = CalibrationSampleH5LayoutAdapter()
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(
                    f, "calib_test/target_sample", "calib_test/control_sample"
                )
        _assert_h5_error(
            exc_info,
            "H5MetadataError",
            "Missing sample patient_name metadata",
        )


# ---------------------------------------------------------------------------
# I. No auto-select first patient
# ---------------------------------------------------------------------------


class TestNoAutoSelect:
    def test_does_not_auto_select_first_patient_in_multi_patient_h5(
        self, tmp_path: Path,
    ):
        """Multi-patient calibration H5 without matching refs raises error.

        The adapter must NOT auto-select the first patient.
        """
        path = tmp_path / "multi_patient.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("/calib_test")
            # Patient Nova_376
            s1 = calib.create_group("sample_Nova_376_Right")
            s1.create_dataset("sample/patient_name", data="Nova_376")
            s1.create_dataset("sample/sample_type", data="RIGHT BREAST")
            s2 = calib.create_group("sample_Nova_376_Left")
            s2.create_dataset("sample/patient_name", data="Nova_376")
            s2.create_dataset("sample/sample_type", data="LEFT BREAST")
            # Patient Nova_378
            s3 = calib.create_group("sample_Nova_378_Right")
            s3.create_dataset("sample/patient_name", data="Nova_378")
            s3.create_dataset("sample/sample_type", data="RIGHT BREAST")
            s4 = calib.create_group("sample_Nova_378_Left")
            s4.create_dataset("sample/patient_name", data="Nova_378")
            s4.create_dataset("sample/sample_type", data="LEFT BREAST")

        adapter = CalibrationSampleH5LayoutAdapter()

        # Detection should work
        with h5py.File(path, "r") as f:
            assert adapter.detect(f) is True

        # Without matching ref, should fail — never auto-select
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(
                    f,
                    "nonexistent_target",
                    "calib_test/sample_Nova_376_Left",
                )
        _assert_h5_error(
            exc_info, "H5ContainerError", "Target scan group not found"
        )

    def test_detect_layout_returns_adapter(self, tmp_path: Path):
        """detect_layout returns the correct adapter for each layout."""
        canonical_path = _create_canonical_h5(tmp_path)
        calib_path = _create_calibration_h5(tmp_path)

        with h5py.File(canonical_path, "r") as f:
            adapter = detect_layout(f)
            assert isinstance(adapter, CanonicalH5LayoutAdapter)

        with h5py.File(calib_path, "r") as f:
            adapter = detect_layout(f)
            assert isinstance(adapter, CalibrationSampleH5LayoutAdapter)


# ---------------------------------------------------------------------------
# J. Preflight with explicit calibration refs
# ---------------------------------------------------------------------------


class TestPreflightWithCalibrationRefs:
    def test_preflight_with_explicit_calibration_refs(
        self, tmp_path: Path,
    ):
        """Preflight with explicit calibration refs passes correctly."""
        h5_path = _create_calibration_h5(tmp_path)
        result = run_h5_preflight(
            h5_path,
            target_scan_ref=_get_target_ref(),
            control_scan_ref=_get_control_ref(),
        )
        assert result.passed is True
        assert result.patient_id == "Nova_376"
        assert result.patient_identifier_source == "patient_name_fallback"
        assert result.metadata_fallback_used is True
        assert result.target_side == "RIGHT"
        assert result.contralateral_side == "LEFT"
        assert result.target_measurement_count == 3
        assert result.contralateral_measurement_count == 3
        assert result.metadata.get("layout_name") == "calibration_sample"

    def test_preflight_with_canonical_refs_through_adapter(
        self, tmp_path: Path,
    ):
        """Preflight with canonical refs via adapter passes."""
        h5_path = _create_canonical_h5(tmp_path)
        result = run_h5_preflight(
            h5_path,
            target_scan_ref="target",
            control_scan_ref="contralateral",
        )
        assert result.passed is True
        assert result.patient_id == "TEST-001"
        assert result.patient_identifier_source == "patient_id"
        assert result.metadata_fallback_used is False


# ---------------------------------------------------------------------------
# K. Legacy canonical preflight preserved
# ---------------------------------------------------------------------------


class TestCanonicalPreserved:
    def test_preflight_canonical_without_refs_preserved(
        self, tmp_path: Path,
    ):
        """Preflight without refs preserves legacy canonical behavior."""
        h5_path = _create_canonical_h5(tmp_path)
        result = run_h5_preflight(h5_path)
        assert result.passed is True
        assert result.patient_id == "TEST-001"
        assert result.patient_identifier_source == "patient_id"
        assert result.metadata_fallback_used is False
        assert result.target_side == "L"
        assert result.contralateral_side == "R"


# ---------------------------------------------------------------------------
# L. No raw patient_name in logs or exceptions
# ---------------------------------------------------------------------------


class TestNoRawPatientName:
    def test_no_raw_patient_name_in_logs(self, tmp_path: Path, caplog):
        """No raw patient_name appears in preflight logs with explicit refs."""
        caplog.set_level(logging.INFO)
        h5_path = _create_calibration_h5(tmp_path)
        result = run_h5_preflight(
            h5_path,
            target_scan_ref=_get_target_ref(),
            control_scan_ref=_get_control_ref(),
        )
        assert result.passed is True
        assert "Nova_376" not in caplog.text

    def test_no_raw_patient_name_in_exception(self, tmp_path: Path):
        """Exception for mismatched patient names does not include raw values."""
        h5_path = _create_calibration_h5(
            tmp_path,
            target_patient_name="Nova_376",
            control_patient_name="Nova_378",
        )
        with pytest.raises(Exception) as exc_info:
            run_h5_preflight(
                h5_path,
                target_scan_ref=_get_target_ref(),
                control_scan_ref=_get_control_ref(),
            )
        _assert_h5_error(
            exc_info, "H5PatientMismatchError", "patient names do not match"
        )
        err_msg = str(exc_info.value)
        assert "Nova_376" not in err_msg
        assert "Nova_378" not in err_msg


# ---------------------------------------------------------------------------
# Extra: Ref validation unit tests
# ---------------------------------------------------------------------------


class TestRefValidation:
    def test_validate_ref_rejects_empty(self):
        """Empty ref raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            _validate_ref("", "target_scan_ref")

    def test_validate_ref_rejects_whitespace(self):
        """Whitespace-only ref raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            _validate_ref("   ", "target_scan_ref")

    def test_validate_ref_rejects_leading_slash(self):
        """Ref with leading '/' raises ValueError."""
        with pytest.raises(ValueError, match="must not start with '/'"):
            _validate_ref("/absolute/path", "target_scan_ref")

    def test_validate_ref_rejects_path_traversal(self):
        """Ref with '..' raises ValueError."""
        with pytest.raises(ValueError, match="invalid path"):
            _validate_ref("calib/../sample", "target_scan_ref")

    def test_validate_ref_accepts_valid(self):
        """Valid ref returns stripped value."""
        result = _validate_ref(
            "calib_20260128/sample_01", "target_scan_ref"
        )
        assert result == "calib_20260128/sample_01"


# ---------------------------------------------------------------------------
# Extra: Breast type to side mapping
# ---------------------------------------------------------------------------


class TestBreastTypeToSide:
    def test_right_breast_maps_to_right(self):
        assert _breast_type_to_side("RIGHT BREAST") == "RIGHT"

    def test_left_breast_maps_to_left(self):
        assert _breast_type_to_side("LEFT BREAST") == "LEFT"

    def test_lowercase_variants(self):
        assert _breast_type_to_side("right breast") == "RIGHT"
        assert _breast_type_to_side("left breast") == "LEFT"

    def test_reversed_word_order(self):
        assert _breast_type_to_side("BREAST RIGHT") == "RIGHT"
        assert _breast_type_to_side("BREAST LEFT") == "LEFT"

    def test_unrecognized_type_raises(self):
        with pytest.raises(Exception) as exc_info:
            _breast_type_to_side("UNKNOWN TYPE")
        _assert_h5_error(
            exc_info, "H5MetadataError", "Cannot determine breast side from sample_type"
        )


# ---------------------------------------------------------------------------
# Extra: Set counting
# ---------------------------------------------------------------------------


class TestSetCounting:
    def test_counts_sets_correctly(self, tmp_path: Path):
        """Counts set groups under a sample path."""
        h5_path = _create_calibration_h5(tmp_path, target_sets=5, control_sets=2)
        with h5py.File(h5_path, "r") as f:
            target_count = _count_sets(f, f"/{_get_target_ref()}")
            control_count = _count_sets(f, f"/{_get_control_ref()}")
        assert target_count == 5
        assert control_count == 2


# ---------------------------------------------------------------------------
# Extra: detect_layout with no match
# ---------------------------------------------------------------------------


class TestDetectLayoutNoMatch:
    def test_detect_layout_raises_for_unknown(self, tmp_path: Path):
        """detect_layout raises H5ContainerError if no adapter matches."""
        path = tmp_path / "empty.h5"
        with h5py.File(path, "w") as f:
            f.create_dataset("/some_data", data=42)
        with pytest.raises(Exception) as exc_info:
            with h5py.File(path, "r") as f:
                detect_layout(f)
        _assert_h5_error(exc_info, "H5ContainerError", "Unrecognised")


# ---------------------------------------------------------------------------
# Extra: Reject identical target/control refs
# ---------------------------------------------------------------------------


class TestIdenticalRefs:
    def test_rejects_identical_refs(self, tmp_path: Path):
        """Same ref for target and control raises H5ContainerError."""
        h5_path = _create_calibration_h5(tmp_path)
        adapter = CalibrationSampleH5LayoutAdapter()
        with h5py.File(h5_path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(
                    f, _get_target_ref(), _get_target_ref()
                )
        _assert_h5_error(
            exc_info, "H5ContainerError", "must be distinct"
        )


# ---------------------------------------------------------------------------
# M. Session layout adapter (PR0071)
# ---------------------------------------------------------------------------


class TestSessionLayoutDetection:
    """Tests for SessionLayoutH5Adapter detection."""

    def test_detects_session_layout(self, tmp_path: Path):
        """Session adapter detects valid session layout."""
        path = tmp_path / "session.h5"
        with h5py.File(path, "w") as f:
            sets = f.create_group("/session/sets")
            s1 = sets.create_group("set_001_sample_main")
            s1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0]))
            s1.create_dataset("integration/i", data=np.array([0.1, 0.2, 0.3]))
            c1 = sets.create_group("contralateral_set_001_sample_main")
            c1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0]))
            c1.create_dataset("integration/i", data=np.array([0.4, 0.5, 0.6]))

        from bremen.api.h5_layouts import SessionLayoutH5Adapter
        adapter = SessionLayoutH5Adapter()
        with h5py.File(path, "r") as f:
            assert adapter.detect(f) is True

    def test_detect_false_for_canonical(self, tmp_path: Path):
        """Session adapter returns False for canonical layout."""
        path = tmp_path / "canonical.h5"
        with h5py.File(path, "w") as f:
            tg = f.create_group("/scans/target")
            tg.create_dataset("measurements", data=np.random.rand(3, 10))

        from bremen.api.h5_layouts import SessionLayoutH5Adapter
        adapter = SessionLayoutH5Adapter()
        with h5py.File(path, "r") as f:
            assert adapter.detect(f) is False

    def test_detect_false_for_missing_session_sets(self, tmp_path: Path):
        """Session adapter returns False without /session/sets."""
        path = tmp_path / "empty.h5"
        with h5py.File(path, "w") as f:
            f.create_dataset("/some_data", data=42)

        from bremen.api.h5_layouts import SessionLayoutH5Adapter
        adapter = SessionLayoutH5Adapter()
        with h5py.File(path, "r") as f:
            assert adapter.detect(f) is False

    def test_detect_false_for_missing_contralateral_pair(self, tmp_path: Path):
        """Session adapter returns False without matching contralateral pair."""
        path = tmp_path / "session_no_contra.h5"
        with h5py.File(path, "w") as f:
            sets = f.create_group("/session/sets")
            s1 = sets.create_group("set_001_sample_main")
            s1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0]))
            s1.create_dataset("integration/i", data=np.array([0.1, 0.2, 0.3]))

        from bremen.api.h5_layouts import SessionLayoutH5Adapter
        adapter = SessionLayoutH5Adapter()
        with h5py.File(path, "r") as f:
            assert adapter.detect(f) is False

    def test_detect_false_for_calibration_layout(self, tmp_path: Path):
        """Session adapter returns False for calibration layout."""
        path = tmp_path / "calib.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("/calib_test")
            s1 = calib.create_group("sample_01")
            s1.create_dataset("sample/patient_name", data="P001")
            s1.create_dataset("sample/sample_type", data="RIGHT BREAST")

        from bremen.api.h5_layouts import SessionLayoutH5Adapter
        adapter = SessionLayoutH5Adapter()
        with h5py.File(path, "r") as f:
            assert adapter.detect(f) is False


class TestSessionContextResolution:
    """Tests for SessionLayoutH5Adapter.resolve_prediction_context."""

    def _create_session_h5(self, tmp_path: Path) -> Path:
        path = tmp_path / "session.h5"
        with h5py.File(path, "w") as f:
            f.create_dataset("/patient/id", data="P001")
            f.create_dataset("/session/sample/patient_name", data="patient_cancer_001")
            f.create_dataset("/session/sample/sample_type", data="RIGHT BREAST")
            sets = f.create_group("/session/sets")
            s1 = sets.create_group("set_001_sample_main")
            s1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
            s1.create_dataset("integration/i", data=np.array([0.1, 0.2, 0.3], dtype=np.float64))
            c1 = sets.create_group("contralateral_set_001_sample_main")
            c1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
            c1.create_dataset("integration/i", data=np.array([0.4, 0.5, 0.6], dtype=np.float64))
            s2 = sets.create_group("set_002_sample_main")
            s2.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
            s2.create_dataset("integration/i", data=np.array([0.7, 0.8, 0.9], dtype=np.float64))
            c2 = sets.create_group("contralateral_set_002_sample_main")
            c2.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
            c2.create_dataset("integration/i", data=np.array([1.0, 1.1, 1.2], dtype=np.float64))
        return path

    def test_resolves_first_pair_by_default(self, tmp_path: Path):
        """Resolves first valid pair when no explicit refs given."""
        path = self._create_session_h5(tmp_path)
        from bremen.api.h5_layouts import SessionLayoutH5Adapter
        adapter = SessionLayoutH5Adapter()
        # The adapter requires explicit refs; we pass them directly
        with h5py.File(path, "r") as f:
            ctx = adapter.resolve_prediction_context(
                f, "set_001_sample_main", "contralateral_set_001_sample_main"
            )
        assert ctx.layout_name == "session_layout"
        assert "set_001_sample_main" in ctx.target_group_path
        assert "contralateral_set_001_sample_main" in ctx.control_group_path

    def test_includes_patient_identifier(self, tmp_path: Path):
        """Resolved context includes patient identifier."""
        path = self._create_session_h5(tmp_path)
        from bremen.api.h5_layouts import SessionLayoutH5Adapter
        adapter = SessionLayoutH5Adapter()
        with h5py.File(path, "r") as f:
            ctx = adapter.resolve_prediction_context(
                f, "set_001_sample_main", "contralateral_set_001_sample_main"
            )
        assert ctx.patient_identifier == "P001"
        assert ctx.patient_identifier_source == "patient_id"

    def test_raises_on_missing_integration(self, tmp_path: Path):
        """Missing integration array raises H5ContainerError."""
        path = tmp_path / "session_no_i.h5"
        with h5py.File(path, "w") as f:
            sets = f.create_group("/session/sets")
            s1 = sets.create_group("set_001_sample_main")
            s1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0]))
            c1 = sets.create_group("contralateral_set_001_sample_main")
            c1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0]))
            c1.create_dataset("integration/i", data=np.array([0.4, 0.5, 0.6]))

        from bremen.api.h5_layouts import SessionLayoutH5Adapter
        adapter = SessionLayoutH5Adapter()
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(
                    f, "set_001_sample_main", "contralateral_set_001_sample_main"
                )
        assert "Missing" in str(exc_info.value)
        assert "integration/i" in str(exc_info.value)

    def test_raises_on_q_axis_mismatch(self, tmp_path: Path):
        """Mismatched q-axis lengths raise H5ContainerError."""
        path = tmp_path / "session_q_mismatch.h5"
        with h5py.File(path, "w") as f:
            sets = f.create_group("/session/sets")
            s1 = sets.create_group("set_001_sample_main")
            s1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
            s1.create_dataset("integration/i", data=np.array([0.1, 0.2, 0.3], dtype=np.float64))
            c1 = sets.create_group("contralateral_set_001_sample_main")
            c1.create_dataset("integration/q", data=np.array([4.0, 5.0], dtype=np.float64))
            c1.create_dataset("integration/i", data=np.array([0.4, 0.5], dtype=np.float64))

        from bremen.api.h5_layouts import SessionLayoutH5Adapter
        adapter = SessionLayoutH5Adapter()
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(
                    f, "set_001_sample_main", "contralateral_set_001_sample_main"
                )
        assert "lengths do not match" in str(exc_info.value)


# ---------------------------------------------------------------------------
# N. Session layout preflight passes (PR0071)
# ---------------------------------------------------------------------------


class TestSessionPreflight:
    """Tests that session layout H5 passes preflight with explicit refs."""

    def test_preflight_passes_with_session_layout(self, tmp_path: Path):
        """run_h5_preflight with session layout refs passes."""
        path = tmp_path / "session_preflight.h5"
        with h5py.File(path, "w") as f:
            f.create_dataset("/patient/id", data="P001")
            f.create_dataset("/session/sample/patient_name", data="patient_cancer_001")
            f.create_dataset("/session/sample/sample_type", data="RIGHT BREAST")
            sets = f.create_group("/session/sets")
            s1 = sets.create_group("set_001_sample_main")
            s1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
            s1.create_dataset("integration/i", data=np.array([0.1, 0.2, 0.3], dtype=np.float64))
            c1 = sets.create_group("contralateral_set_001_sample_main")
            c1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
            c1.create_dataset("integration/i", data=np.array([0.4, 0.5, 0.6], dtype=np.float64))

        result = run_h5_preflight(
            path,
            target_scan_ref="set_001_sample_main",
            control_scan_ref="contralateral_set_001_sample_main",
        )
        assert result.passed is True
        assert result.metadata.get("layout_name") == "session_layout"
        assert result.patient_id == "P001"


# ---------------------------------------------------------------------------
# O. No biopsy/birads/BENIGN/CANCER labels as prediction targets
# ---------------------------------------------------------------------------


class TestNoClinicalLabels:
    """Session layout adapter must not use clinical labels as targets."""

    def test_no_biopsy_or_birads_in_adapter(self):
        """SessionLayoutH5Adapter does not use biopsy/birads as prediction targets."""
        from bremen.api import h5_layouts as _hl
        src_path = Path(_hl.__file__)
        source = src_path.read_text(encoding="utf-8")
        # "birads" and "biopsy" may appear in safety comments but NOT as
        # prediction target references or dataset reads
        import ast
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                s = node.value.lower()
                # Allow safety comments that say "NOT use ..."
                if "not use" in s:
                    continue
                if "birads" in s:
                    pytest.fail(f"birads found in string literal: {node.value!r}")
                if "biopsy" in s:
                    pytest.fail(f"biopsy found in string literal: {node.value!r}")

    def test_no_benign_vs_cancer_as_target(self):
        """Adapter does not use BENIGN vs CANCER classification."""
        from bremen.api import h5_layouts as _hl
        src_path = Path(_hl.__file__)
        source = src_path.read_text(encoding="utf-8")
        assert "benign" not in source.lower() or "BENIGN" in source
        assert "cancer" not in source.lower() or "CANCER" in source


# ---------------------------------------------------------------------------
# P. Matador raw acquisition adapter (PR0073)
# ---------------------------------------------------------------------------


def _create_matador_raw_h5(
    tmp_path: Path,
    *,
    include_calib: bool = True,
    left_side: str = "LEFT",
    right_side: str = "RIGHT",
    left_position: str = "center",
    right_position: str = "center",
    image_shape: tuple = (50, 50),
) -> Path:
    """Create a synthetic Matador raw acquisition H5.

    Structure:
    - calibrations/poni1 (PONI dataset)
    - measurement_001/ (LEFT/CENTER 2D image)
      - data (2D float array)
      - attrs: side=LEFT, position=center
    - measurement_002/ (RIGHT/CENTER 2D image)
      - data (2D float array)
      - attrs: side=RIGHT, position=center
    """
    path = tmp_path / "matador_raw.h5"
    with h5py.File(path, "w") as f:
        if include_calib:
            calib = f.create_group("calibrations")
            calib.create_dataset(
                "poni1", data=np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
            )

        m1 = f.create_group("measurement_001")
        m1.attrs["side"] = left_side
        m1.attrs["position"] = left_position
        m1.create_dataset(
            "data", data=np.random.rand(*image_shape).astype(np.float32)
        )

        m2 = f.create_group("measurement_002")
        m2.attrs["side"] = right_side
        m2.attrs["position"] = right_position
        m2.create_dataset(
            "data", data=np.random.rand(*image_shape).astype(np.float32)
        )

    return path


class TestMatadorRawDetection:
    """Tests for MatadorRawH5Adapter.detect()."""

    def test_detects_real_like_matador_raw(self, tmp_path: Path):
        """Detects H5 with 2D images + PONI calibration via structural fallback."""
        h5_path = _create_matador_raw_h5(tmp_path)
        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(h5_path, "r") as f:
            assert adapter.detect(f) is True

    def test_detect_returns_false_for_canonical(self, tmp_path: Path):
        """Does NOT claim canonical H5."""
        h5_path = _create_canonical_h5(tmp_path)
        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(h5_path, "r") as f:
            assert adapter.detect(f) is False

    def test_detect_returns_false_for_session(self, tmp_path: Path):
        """Does NOT claim session H5."""
        path = tmp_path / "session.h5"
        with h5py.File(path, "w") as f:
            sets = f.create_group("/session/sets")
            s1 = sets.create_group("set_001_sample_main")
            s1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0]))
            s1.create_dataset("integration/i", data=np.array([0.1, 0.2, 0.3]))
            c1 = sets.create_group("contralateral_set_001_sample_main")
            c1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0]))
            c1.create_dataset("integration/i", data=np.array([0.4, 0.5, 0.6]))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            assert adapter.detect(f) is False

    def test_detect_false_missing_calibration(self, tmp_path: Path):
        """Without PONI/calibration data, detection returns False."""
        path = tmp_path / "no_calib.h5"
        with h5py.File(path, "w") as f:
            m1 = f.create_group("measurement_001")
            m1.attrs["side"] = "LEFT"
            m1.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))
            m2 = f.create_group("measurement_002")
            m2.attrs["side"] = "RIGHT"
            m2.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            assert adapter.detect(f) is False

    def test_detect_false_no_2d_image(self, tmp_path: Path):
        """Without 2D datasets, detection returns False."""
        path = tmp_path / "no_2d.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("calibrations")
            calib.create_dataset("poni1", data=np.array([0.1, 0.2, 0.3]))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            assert adapter.detect(f) is False

    def test_detect_false_empty_h5(self, tmp_path: Path):
        """Empty H5 is not detected."""
        path = tmp_path / "empty.h5"
        with h5py.File(path, "w") as f:
            pass

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            assert adapter.detect(f) is False

    def test_detect_no_filename_dependence(self, tmp_path: Path):
        """Detection works regardless of filename."""
        h5_path = _create_matador_raw_h5(tmp_path)
        # Rename to something unrelated
        renamed = tmp_path / "random_name.h5"
        import shutil
        shutil.copy(h5_path, renamed)
        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(renamed, "r") as f:
            assert adapter.detect(f) is True

    def test_detect_no_product_name_dependence(self, tmp_path: Path):
        """Detection does NOT use 'Nova' or 'Matador' in filenames."""
        # H5 with 2D image but NO Matador/Nova in group names
        path = tmp_path / "test.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("calibrations")
            calib.create_dataset("wavelength", data=np.array([0.1]))
            g1 = f.create_group("group_A")
            g1.attrs["side"] = "LEFT"
            g1.attrs["position"] = "center"
            g1.create_dataset("image", data=np.random.rand(50, 50).astype(np.float32))
            g2 = f.create_group("group_B")
            g2.attrs["side"] = "RIGHT"
            g2.attrs["position"] = "center"
            g2.create_dataset("image", data=np.random.rand(50, 50).astype(np.float32))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            assert adapter.detect(f) is True


class TestMatadorRawContextResolution:
    """Tests for MatadorRawH5Adapter.resolve_prediction_context()."""

    def test_resolves_bilateral_pair(self, tmp_path: Path):
        """Resolves LEFT/RIGHT pair by position key."""
        h5_path = _create_matador_raw_h5(tmp_path)
        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(h5_path, "r") as f:
            ctx = adapter.resolve_prediction_context(f, "", "")

        assert ctx.layout_name == "matador_raw"
        assert ctx.target_side is not None
        assert ctx.control_side is not None
        assert ctx.target_side != ctx.control_side
        assert "/measurement_001" in ctx.target_group_path or "/measurement_001" in ctx.control_group_path
        assert "/measurement_002" in ctx.target_group_path or "/measurement_002" in ctx.control_group_path
        assert ctx.adapter_metadata.get("pair_key") is not None
        assert ctx.adapter_metadata.get("calibration_refs") is not None

    def test_pairs_by_position_not_first_two(self, tmp_path: Path):
        """Measurements with different positions pair correctly, not first-two."""
        path = tmp_path / "multi_pos.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("calibrations")
            calib.create_dataset("poni1", data=np.array([0.1, 0.2]))
            # Position "top": left only
            m1 = f.create_group("m_top_left")
            m1.attrs["side"] = "LEFT"
            m1.attrs["position"] = "top"
            m1.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))
            # Position "center": both sides (complete pair)
            m2 = f.create_group("m_center_left")
            m2.attrs["side"] = "LEFT"
            m2.attrs["position"] = "center"
            m2.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))
            m3 = f.create_group("m_center_right")
            m3.attrs["side"] = "RIGHT"
            m3.attrs["position"] = "center"
            m3.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            ctx = adapter.resolve_prediction_context(f, "", "")

        # Should pair by "center" (the complete pair), not the first two
        assert ctx.adapter_metadata.get("pair_key") == "center"

    def test_fails_missing_side_metadata(self, tmp_path: Path):
        """Missing side attribute fails."""
        path = tmp_path / "no_side.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("calibrations")
            calib.create_dataset("poni1", data=np.array([0.1, 0.2]))
            m1 = f.create_group("m1")
            m1.attrs["position"] = "center"  # no side
            m1.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))
            m2 = f.create_group("m2")
            m2.attrs["position"] = "center"  # no side
            m2.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(f, "", "")
        assert "side" in str(exc_info.value).lower()

    def test_fails_no_complete_bilateral_pair(self, tmp_path: Path):
        """Only LEFT sides, no RIGHT side, fails."""
        path = tmp_path / "left_only.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("calibrations")
            calib.create_dataset("poni1", data=np.array([0.1, 0.2]))
            m1 = f.create_group("m1")
            m1.attrs["side"] = "LEFT"
            m1.attrs["position"] = "center"
            m1.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))
            m2 = f.create_group("m2")
            m2.attrs["side"] = "LEFT"
            m2.attrs["position"] = "top"  # Different position — unique
            m2.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(f, "", "")
        assert "bilateral" in str(exc_info.value).lower()

    def test_fails_duplicate_side_same_pair_key(self, tmp_path: Path):
        """Two LEFT measurements with same pair_key fails."""
        path = tmp_path / "dup_side.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("calibrations")
            calib.create_dataset("poni1", data=np.array([0.1, 0.2]))
            m1 = f.create_group("m1")
            m1.attrs["side"] = "LEFT"
            m1.attrs["position"] = "center"
            m1.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))
            m2 = f.create_group("m2")
            m2.attrs["side"] = "LEFT"  # duplicate LEFT for same position
            m2.attrs["position"] = "center"
            m2.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(f, "", "")
        assert "duplicate" in str(exc_info.value).lower()

    def test_fails_insufficient_measurements(self, tmp_path: Path):
        """Only one measurement fails."""
        path = tmp_path / "one_meas.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("calibrations")
            calib.create_dataset("poni1", data=np.array([0.1, 0.2]))
            m1 = f.create_group("m1")
            m1.attrs["side"] = "LEFT"
            m1.attrs["position"] = "center"
            m1.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(f, "", "")
        assert "Insufficient" in str(exc_info.value)

    def test_fails_no_calibration_data(self, tmp_path: Path):
        """No PONI/calibration dataset fails resolution."""
        h5_path = _create_matador_raw_h5(tmp_path, include_calib=False)
        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(h5_path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(f, "", "")
        assert "calibration" in str(exc_info.value).lower()

    def test_context_excludes_identifiers(self, tmp_path: Path):
        """Resolved context does not leak identifiers."""
        h5_path = _create_matador_raw_h5(tmp_path)
        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(h5_path, "r") as f:
            ctx = adapter.resolve_prediction_context(f, "", "")
        # adapter_metadata should not contain raw values
        meta = ctx.adapter_metadata
        for val in meta.values():
            if isinstance(val, str):
                assert "Nova" not in val
                assert "patient" not in val.lower()
        # No patient name/id leakage
        assert "Nova" not in ctx.patient_identifier


class TestMatadorRawPreflight:
    """Matador raw preflight integration tests."""

    def test_preflight_passes_matador_raw(self, tmp_path: Path):
        """run_h5_preflight with Matador raw H5 passes."""
        h5_path = _create_matador_raw_h5(tmp_path)
        result = run_h5_preflight(h5_path)
        assert result.passed is True
        assert result.metadata.get("layout_name") == "matador_raw"

    def test_preflight_fails_no_calibration(self, tmp_path: Path):
        """Preflight fails when no calibration found."""
        h5_path = _create_matador_raw_h5(tmp_path, include_calib=False)
        # Without calibration, detect_layout cannot match any adapter
        # → H5ContainerError "Unrecognised H5 container layout"
        with pytest.raises(Exception) as exc_info:
            run_h5_preflight(h5_path)
        # Either "Unrecognised" (detection failure) or "calibration"
        # (adapter resolution failure if detection somehow passes)
        err_lower = str(exc_info.value).lower()
        assert "unrecognised" in err_lower or "calibration" in err_lower

    def test_source_checksum_unchanged(self, tmp_path: Path):
        """Source H5 checksum unchanged after preflight."""
        import hashlib
        h5_path = _create_matador_raw_h5(tmp_path)
        original = hashlib.sha256(h5_path.read_bytes()).hexdigest()
        result = run_h5_preflight(h5_path)
        assert result.passed is True
        final = hashlib.sha256(h5_path.read_bytes()).hexdigest()
        assert original == final


# ---------------------------------------------------------------------------
# Real-subset smoke (opt-in)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    "BREMEN_H5_PREFLIGHT_SMOKE_PATH" not in os.environ,
    reason="BREMEN_H5_PREFLIGHT_SMOKE_PATH not set — skipping real H5 smoke",
)
def test_preflight_with_explicit_calibration_refs_on_real_h5():
    """Opt-in smoke test: preflight with explicit refs on real H5.

    Set BREMEN_H5_PREFLIGHT_SMOKE_PATH to the path of a real H5
    container to enable this test.

    Uses explicit refs:
      target_scan_ref = "calib_20260128_132622/sample_01_20260128_Nova_376_Right"
      control_scan_ref = "calib_20260128_132622/sample_02_20260128_Nova_376_Left"

    NOTE: Preflight may pass but preprocessing bridge will still fail.
    That is expected and documented as PR0046 scope.
    """
    h5_path = os.environ["BREMEN_H5_PREFLIGHT_SMOKE_PATH"]
    target_ref = "calib_20260128_132622/sample_01_20260128_Nova_376_Right"
    control_ref = "calib_20260128_132622/sample_02_20260128_Nova_376_Left"

    try:
        result = run_h5_preflight(
            h5_path,
            target_scan_ref=target_ref,
            control_scan_ref=control_ref,
        )
        assert result is not None
        # Must no longer fail with Ambiguous sample patient_name metadata
        assert "Ambiguous" not in str(result)
        assert result.metadata.get("layout_name") in (
            "calibration_sample", "canonical",
        )
    except H5MetadataError as e:
        # Must not fail on ambiguous patient_name with explicit refs
        assert "Ambiguous" not in str(e), (
            f"Still failing with ambiguous patient_name: {e}"
        )


# ---------------------------------------------------------------------------
# Q. Real-like Matador fixture tests (PR0074)
# ---------------------------------------------------------------------------


def _create_real_like_matador_h5(
    tmp_path: Path,
    *,
    side_attr: str = "organSide",
    include_calib_image: bool = False,
) -> Path:
    """Create a real-like Matador raw acquisition H5.

    Mimics the deployed real container structure:
    - Arbitrary acquisition-root name
    - Calibration subtree with PONI text and optional 2D calibration image
    - Multiple validated measurement groups with organSide and P<number> names

    The calibration image and raw images are structurally similar
    (both 2D float arrays) so classification must depend on context,
    not only shape/dtype.
    """
    path = tmp_path / "real_like_matador.h5"
    with h5py.File(path, "w") as f:
        # Calibration subtree
        calib = f.create_group("acquisition_001/calibration")
        calib.create_dataset(
            "poni1",
            data=np.array([
                b"poni_version: 2\n",
                b"Detector: Pilatus 100k\n",
                b"Detector_config: {\"pixel1\": 0.0001, \"pixel2\": 0.0001, "
                b"\"max_shape\": [50, 50], \"orientation\": 3}\n",
                b"Distance: 0.15\n",
                b"Poni1: 0.025\n",
                b"Poni2: 0.025\n",
                b"Rot1: 0.0\n",
                b"Rot2: 0.0\n",
                b"Rot3: 0.0\n",
                b"Wavelength: 1e-10\n",
            ], dtype=h5py.string_dtype()),
        )
        # Optional 2D calibration image — same shape/dtype as measurements
        if include_calib_image:
            calib.create_dataset(
                "calib_image",
                data=np.random.default_rng(99).normal(0, 1, (50, 50)).astype(np.float32),
            )

        # Measurement groups with organSide and P<number> dataset names
        for i, (p_num, side) in enumerate([
            ("P1", "LEFT"),
            ("P1", "RIGHT"),
        ]):
            m = f.create_group(f"measurements/measurement_{i}_{side.lower()}")
            m.attrs[side_attr] = side
            # Dataset name contains P<number> token for position extraction
            m.create_dataset(
                f"diffraction_{p_num}",
                data=np.random.default_rng(i).normal(10, 3, (50, 50)).astype(np.float32),
            )

    return path


class TestRealLikeMatador:
    """Real-like Matador fixture tests (PR0074 corrections)."""

    def test_organ_side_resolved(self, tmp_path: Path):
        """organSide attribute on measurement groups is resolved correctly."""
        h5_path = _create_real_like_matador_h5(tmp_path, side_attr="organSide")
        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(h5_path, "r") as f:
            ctx = adapter.resolve_prediction_context(f, "", "")
        assert ctx.target_side is not None
        assert ctx.control_side is not None
        assert ctx.target_side in ("LEFT", "RIGHT")
        assert ctx.control_side in ("LEFT", "RIGHT")
        assert ctx.target_side != ctx.control_side

    def test_organ_side_case_insensitive(self, tmp_path: Path):
        """organside (all lowercase) attribute is resolved."""
        path = tmp_path / "lowercase.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("calibrations")
            calib.create_dataset("poni1", data=np.array([0.1, 0.2, 0.3]))
            m1 = f.create_group("measurement_left")
            m1.attrs["organside"] = "LEFT"
            m1.attrs["position"] = "center"
            m1.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))
            m2 = f.create_group("measurement_right")
            m2.attrs["organside"] = "RIGHT"
            m2.attrs["position"] = "center"
            m2.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            ctx = adapter.resolve_prediction_context(f, "", "")
        assert ctx.target_side is not None
        assert ctx.control_side is not None

    def test_calibration_image_excluded_from_measurements(self, tmp_path: Path):
        """2D calibration image is NOT counted as a measurement."""
        h5_path = _create_real_like_matador_h5(
            tmp_path, side_attr="organSide", include_calib_image=True,
        )
        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(h5_path, "r") as f:
            ctx = adapter.resolve_prediction_context(f, "", "")
        # Only 2 measurement datasets (LEFT + RIGHT), not 3 (calib image excluded)
        assert ctx.target_measurement_count == 2
        assert ctx.control_measurement_count == 2

    def test_p_token_extracted_from_dataset_name(self, tmp_path: Path):
        """P<number> token is extracted from dataset name for pairing."""
        path = tmp_path / "p_token.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("calibrations")
            calib.create_dataset("poni1", data=np.array([0.1, 0.2, 0.3]))
            m1 = f.create_group("measurement_left")
            m1.attrs["side"] = "LEFT"
            m1.create_dataset("diffraction_P1", data=np.random.rand(50, 50).astype(np.float32))
            m2 = f.create_group("measurement_right")
            m2.attrs["side"] = "RIGHT"
            m2.create_dataset("diffraction_P1", data=np.random.rand(50, 50).astype(np.float32))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            ctx = adapter.resolve_prediction_context(f, "", "")
        assert ctx.adapter_metadata.get("pair_key") == "P1"

    def test_p_token_preferred_over_attribute(self, tmp_path: Path):
        """Explicit position attribute takes precedence over P-token extraction."""
        path = tmp_path / "prefer_attr.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("calibrations")
            calib.create_dataset("poni1", data=np.array([0.1, 0.2, 0.3]))
            m1 = f.create_group("measurement_P1_left")
            m1.attrs["side"] = "LEFT"
            m1.attrs["position"] = "custom_pos"
            m1.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))
            m2 = f.create_group("measurement_P1_right")
            m2.attrs["side"] = "RIGHT"
            m2.attrs["position"] = "custom_pos"
            m2.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            ctx = adapter.resolve_prediction_context(f, "", "")
        # Uses explicit position attribute, not extracted P1
        assert ctx.adapter_metadata.get("pair_key") == "custom_pos"

    def test_missing_p_token_fails(self, tmp_path: Path):
        """No P<number> token and no position attribute → missing pair_key → fail."""
        path = tmp_path / "no_token.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("calibrations")
            calib.create_dataset("poni1", data=np.array([0.1, 0.2, 0.3]))
            m1 = f.create_group("no_token_left")
            m1.attrs["side"] = "LEFT"
            m1.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))
            m2 = f.create_group("no_token_right")
            m2.attrs["side"] = "RIGHT"
            m2.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(f, "", "")
        err_msg = str(exc_info.value).lower()
        assert "pair-key" in err_msg or "pair_key" in err_msg

    def test_multiple_conflicting_p_tokens_fails(self, tmp_path: Path):
        """Multiple P<number> tokens in one dataset name → failure."""
        path = tmp_path / "multi_token.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("calibrations")
            calib.create_dataset("poni1", data=np.array([0.1, 0.2, 0.3]))
            m1 = f.create_group("measurement_left")
            m1.attrs["side"] = "LEFT"
            m1.create_dataset("diffraction_P1_P2", data=np.random.rand(50, 50).astype(np.float32))
            m2 = f.create_group("measurement_right")
            m2.attrs["side"] = "RIGHT"
            m2.create_dataset("diffraction_P1_P2", data=np.random.rand(50, 50).astype(np.float32))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(f, "", "")
        err_msg = str(exc_info.value).lower()
        assert "conflicting" in err_msg

    def test_duplicate_side_same_pair_key_fails(self, tmp_path: Path):
        """Duplicate side for one pair_key raises error."""
        path = tmp_path / "dup_side_p.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("calibrations")
            calib.create_dataset("poni1", data=np.array([0.1, 0.2, 0.3]))
            m1 = f.create_group("m_left_1")
            m1.attrs["side"] = "LEFT"
            m1.create_dataset("diffraction_P1", data=np.random.rand(50, 50).astype(np.float32))
            m2 = f.create_group("m_left_2")
            m2.attrs["side"] = "LEFT"
            m2.create_dataset("diffraction_P1", data=np.random.rand(50, 50).astype(np.float32))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(f, "", "")
        err_msg = str(exc_info.value).lower()
        assert "duplicate" in err_msg

    def test_incomplete_bilateral_pair_fails(self, tmp_path: Path):
        """Only LEFT side for P1, no RIGHT → incomplete bilateral → fail."""
        path = tmp_path / "incomplete.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("calibrations")
            calib.create_dataset("poni1", data=np.array([0.1, 0.2, 0.3]))
            m1 = f.create_group("m_left")
            m1.attrs["side"] = "LEFT"
            m1.create_dataset("diffraction_P1", data=np.random.rand(50, 50).astype(np.float32))
            m2 = f.create_group("m_right")
            m2.attrs["side"] = "RIGHT"
            m2.create_dataset("diffraction_P2", data=np.random.rand(50, 50).astype(np.float32))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(f, "", "")
        err_msg = str(exc_info.value).lower()
        assert "bilateral" in err_msg or "complete" in err_msg

    def test_ambiguous_multiple_complete_pairs_retained(self, tmp_path: Path):
        """Multiple complete bilateral pairs are retained (not rejected).

        The adapter logs a warning and selects the first complete pair
        for backward-compatible prediction context.  All pairs are
        available through normalize_to_canonical.
        """
        path = tmp_path / "ambiguous.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("calibrations")
            calib.create_dataset(
                "poni1",
                data=np.array([
                    b"poni_version: 2\n",
                    b"Detector: Pilatus 100k\n",
                    b"Detector_config: {\"pixel1\": 0.0001, \"pixel2\": 0.0001, "
                    b"\"max_shape\": [50, 50], \"orientation\": 3}\n",
                    b"Distance: 0.15\n",
                    b"Poni1: 0.025\n",
                    b"Poni2: 0.025\n",
                    b"Rot1: 0.0\n",
                    b"Rot2: 0.0\n",
                    b"Rot3: 0.0\n",
                    b"Wavelength: 1e-10\n",
                ], dtype=h5py.string_dtype()),
            )
            # P1 pair
            m1 = f.create_group("m_P1_left")
            m1.attrs["side"] = "LEFT"
            m1.create_dataset("diffraction_P1", data=np.random.rand(50, 50).astype(np.float32))
            m2 = f.create_group("m_P1_right")
            m2.attrs["side"] = "RIGHT"
            m2.create_dataset("diffraction_P1", data=np.random.rand(50, 50).astype(np.float32))
            # P2 pair
            m3 = f.create_group("m_P2_left")
            m3.attrs["side"] = "LEFT"
            m3.create_dataset("diffraction_P2", data=np.random.rand(50, 50).astype(np.float32))
            m4 = f.create_group("m_P2_right")
            m4.attrs["side"] = "RIGHT"
            m4.create_dataset("diffraction_P2", data=np.random.rand(50, 50).astype(np.float32))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            ctx = adapter.resolve_prediction_context(f, "", "")

        # Context is produced (no exception)
        assert ctx.layout_name == "matador_raw"
        assert ctx.adapter_metadata.get("pair_key") is not None
        # Both complete pairs are accessible via normalize_to_canonical
        with h5py.File(path, "r") as f:
            case = adapter.normalize_to_canonical(f)
        # All 4 measurements retained (P1 LEFT, P1 RIGHT, P2 LEFT, P2 RIGHT)
        assert len(case.measurements) == 4

    def test_missing_organ_side_fails(self, tmp_path: Path):
        """Missing organSide/side attribute → fail."""
        path = tmp_path / "no_side.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("calibrations")
            calib.create_dataset("poni1", data=np.array([0.1, 0.2, 0.3]))
            m1 = f.create_group("m_left")
            m1.create_dataset("diffraction_P1", data=np.random.rand(50, 50).astype(np.float32))
            m2 = f.create_group("m_right")
            m2.create_dataset("diffraction_P1", data=np.random.rand(50, 50).astype(np.float32))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(f, "", "")
        err_msg = str(exc_info.value).lower()
        assert "side" in err_msg

    def test_unsupported_side_value_fails(self, tmp_path: Path):
        """Unrecognised side value (not LEFT/L/RIGHT/R) → fail."""
        path = tmp_path / "bad_side.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("calibrations")
            calib.create_dataset("poni1", data=np.array([0.1, 0.2, 0.3]))
            m1 = f.create_group("measurement_P1_top")
            m1.attrs["organSide"] = "TOP"
            m1.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))
            m2 = f.create_group("measurement_P1_bottom")
            m2.attrs["organSide"] = "BOTTOM"
            m2.create_dataset("data", data=np.random.rand(50, 50).astype(np.float32))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(f, "", "")
        err_msg = str(exc_info.value).lower()
        assert "unrecognised" in err_msg or "unrecognized" in err_msg

    def test_source_checksum_unchanged(self, tmp_path: Path):
        """Source H5 checksum unchanged after resolution."""
        import hashlib
        h5_path = _create_real_like_matador_h5(tmp_path, side_attr="organSide")
        original = hashlib.sha256(h5_path.read_bytes()).hexdigest()
        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(h5_path, "r") as f:
            adapter.resolve_prediction_context(f, "", "")
        final = hashlib.sha256(h5_path.read_bytes()).hexdigest()
        assert original == final

    def test_no_public_paths_in_errors(self, tmp_path: Path):
        """Error messages do not contain H5 internal paths or measurement names."""
        path = tmp_path / "no_path_leak.h5"
        with h5py.File(path, "w") as f:
            calib = f.create_group("calibrations")
            calib.create_dataset("poni1", data=np.array([0.1, 0.2, 0.3]))
            m1 = f.create_group("m_left_1")
            m1.attrs["side"] = "LEFT"
            m1.create_dataset("diffraction_P1", data=np.random.rand(50, 50).astype(np.float32))
            m2 = f.create_group("m_left_2")
            m2.attrs["side"] = "LEFT"
            m2.create_dataset("diffraction_P1", data=np.random.rand(50, 50).astype(np.float32))

        from bremen.api.h5_layouts import MatadorRawH5Adapter
        adapter = MatadorRawH5Adapter()
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(f, "", "")
        # Error should not leak internal paths or dataset names
        err_msg = str(exc_info.value)
        assert "/measurement_data" not in err_msg
        assert "/calibrations" not in err_msg


# ---------------------------------------------------------------------------
# R. Session mode selection tests (PR0074)
# ---------------------------------------------------------------------------


class TestSessionModeSelection:
    """Session adapter ref-mode selection tests (PR0074 defect 1)."""

    def _create_session_h5(self, tmp_path: Path) -> Path:
        path = tmp_path / "session.h5"
        with h5py.File(path, "w") as f:
            f.create_dataset("/patient/id", data="P001")
            sets = f.create_group("/session/sets")
            s1 = sets.create_group("set_001_sample_main")
            s1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
            s1.create_dataset("integration/i", data=np.array([0.1, 0.2, 0.3], dtype=np.float64))
            c1 = sets.create_group("contralateral_set_001_sample_main")
            c1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
            c1.create_dataset("integration/i", data=np.array([0.4, 0.5, 0.6], dtype=np.float64))
        return path

    def test_no_refs_auto_detects_pair(self, tmp_path: Path):
        """Both refs absent → automatic pair discovery succeeds."""
        path = self._create_session_h5(tmp_path)
        from bremen.api.h5_layouts import SessionLayoutH5Adapter
        adapter = SessionLayoutH5Adapter()
        with h5py.File(path, "r") as f:
            ctx = adapter.resolve_prediction_context(f, "", "")
        assert ctx.layout_name == "session_layout"
        assert "set_001_sample_main" in ctx.target_group_path
        assert "contralateral" in ctx.control_group_path

    def test_blank_refs_auto_detects_pair(self, tmp_path: Path):
        """Whitespace-only refs count as absent → automatic discovery."""
        path = self._create_session_h5(tmp_path)
        from bremen.api.h5_layouts import SessionLayoutH5Adapter
        adapter = SessionLayoutH5Adapter()
        with h5py.File(path, "r") as f:
            ctx = adapter.resolve_prediction_context(f, "   ", "\t\n")
        assert ctx.layout_name == "session_layout"
        assert "set_001_sample_main" in ctx.target_group_path

    def test_both_explicit_refs_succeeds(self, tmp_path: Path):
        """Both refs present and nonblank → explicit ref validation."""
        path = self._create_session_h5(tmp_path)
        from bremen.api.h5_layouts import SessionLayoutH5Adapter
        adapter = SessionLayoutH5Adapter()
        with h5py.File(path, "r") as f:
            ctx = adapter.resolve_prediction_context(
                f, "set_001_sample_main", "contralateral_set_001_sample_main"
            )
        assert ctx.layout_name == "session_layout"
        assert ctx.target_scan_ref == "set_001_sample_main"
        assert ctx.control_scan_ref == "contralateral_set_001_sample_main"

    def test_exactly_one_ref_rejected(self, tmp_path: Path):
        """Exactly one ref present → H5ContainerError."""
        path = self._create_session_h5(tmp_path)
        from bremen.api.h5_layouts import SessionLayoutH5Adapter
        adapter = SessionLayoutH5Adapter()
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(
                    f, "set_001_sample_main", ""
                )
        _assert_h5_error(
            exc_info, "H5ContainerError", "must be provided together"
        )

    def test_exactly_one_ref_target_only_rejected(self, tmp_path: Path):
        """Only target ref provided → rejected."""
        path = self._create_session_h5(tmp_path)
        from bremen.api.h5_layouts import SessionLayoutH5Adapter
        adapter = SessionLayoutH5Adapter()
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(
                    f, "set_001_sample_main", "  "
                )
        _assert_h5_error(
            exc_info, "H5ContainerError", "must be provided together"
        )

    def test_exactly_one_ref_control_only_rejected(self, tmp_path: Path):
        """Only control ref provided → rejected."""
        path = self._create_session_h5(tmp_path)
        from bremen.api.h5_layouts import SessionLayoutH5Adapter
        adapter = SessionLayoutH5Adapter()
        with h5py.File(path, "r") as f:
            with pytest.raises(Exception) as exc_info:
                adapter.resolve_prediction_context(
                    f, "", "contralateral_set_001_sample_main"
                )
        _assert_h5_error(
            exc_info, "H5ContainerError", "must be provided together"
        )
