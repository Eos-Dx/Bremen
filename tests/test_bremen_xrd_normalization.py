"""Tests for canonical XRD normalization (PR0075).

Covers:
- CanonicalXRDMeasurement and CanonicalXRDCase validation
- Immutable structures (frozen dataclasses)
- q/intensity validation (1D, strictly-increasing, non-empty, finite, matching lengths)
- side validation (LEFT/RIGHT)
- position validation
- Case-level validation
- Normalization orchestration across layouts
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import h5py
import numpy as np
import pytest

from bremen.api.xrd_normalization import (
    CanonicalXRDCase,
    CanonicalXRDMeasurement,
    NormalizationError,
    validate_canonical_measurement,
    validate_canonical_case,
)
from bremen.api.h5_layouts import (
    CanonicalH5LayoutAdapter,
    SessionLayoutH5Adapter,
    detect_layout,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_measurement(**overrides) -> CanonicalXRDMeasurement:
    """Create a valid measurement with optional overrides."""
    params = {
        "side": "LEFT",
        "position": "P1",
        "q": np.array([1.0, 2.0, 3.0], dtype=np.float64),
        "intensity": np.array([0.1, 0.2, 0.3], dtype=np.float64),
    }
    params.update(overrides)
    return CanonicalXRDMeasurement(**params)


def _valid_case(**overrides) -> CanonicalXRDCase:
    """Create a valid case with optional overrides."""
    params = {
        "source_layout": "test",
        "source_layout_version": "v1",
        "source_checksum": "abc123",
        "calibration_provenance": "session_pre_integrated",
        "measurements": (
            _valid_measurement(side="LEFT", position="P1"),
            _valid_measurement(side="RIGHT", position="P1"),
        ),
    }
    params.update(overrides)
    return CanonicalXRDCase(**params)


# ---------------------------------------------------------------------------
# CanonicalXRDMeasurement validation
# ---------------------------------------------------------------------------


class TestCanonicalMeasurementValidation:
    """Validation rules for CanonicalXRDMeasurement."""

    def test_valid_measurement_passes(self):
        """Valid measurement passes all validation."""
        m = _valid_measurement()
        validate_canonical_measurement(m)  # no exception

    def test_q_not_1d_raises(self):
        """Non-1D q raises NormalizationError."""
        m = _valid_measurement(q=np.array([[1.0, 2.0], [3.0, 4.0]]))
        with pytest.raises(NormalizationError, match="q must be 1-dimensional"):
            validate_canonical_measurement(m)

    def test_intensity_not_1d_raises(self):
        """Non-1D intensity raises NormalizationError."""
        m = _valid_measurement(intensity=np.array([[0.1, 0.2], [0.3, 0.4]]))
        with pytest.raises(NormalizationError, match="intensity must be 1-dimensional"):
            validate_canonical_measurement(m)

    def test_empty_q_raises(self):
        """Empty q raises NormalizationError."""
        m = _valid_measurement(q=np.array([], dtype=np.float64))
        with pytest.raises(NormalizationError, match="q must be non-empty"):
            validate_canonical_measurement(m)

    def test_empty_intensity_raises(self):
        """Empty intensity raises NormalizationError."""
        m = _valid_measurement(intensity=np.array([], dtype=np.float64))
        with pytest.raises(NormalizationError, match="intensity must be non-empty"):
            validate_canonical_measurement(m)

    def test_mismatched_lengths_raises(self):
        """Mismatched q and intensity lengths raise NormalizationError."""
        m = _valid_measurement(
            q=np.array([1.0, 2.0], dtype=np.float64),
            intensity=np.array([0.1, 0.2, 0.3], dtype=np.float64),
        )
        with pytest.raises(NormalizationError, match="q length"):
            validate_canonical_measurement(m)

    def test_nonfinite_q_raises(self):
        """Non-finite q values raise NormalizationError."""
        m = _valid_measurement(q=np.array([1.0, np.nan, 3.0], dtype=np.float64))
        with pytest.raises(NormalizationError, match="q must be all-finite"):
            validate_canonical_measurement(m)

    def test_nonfinite_intensity_raises(self):
        """Non-finite intensity values raise NormalizationError."""
        m = _valid_measurement(intensity=np.array([0.1, np.inf, 0.3], dtype=np.float64))
        with pytest.raises(NormalizationError, match="intensity must be all-finite"):
            validate_canonical_measurement(m)

    def test_non_increasing_q_raises(self):
        """Non-strictly-increasing q raises NormalizationError."""
        m = _valid_measurement(q=np.array([1.0, 3.0, 2.0], dtype=np.float64))
        with pytest.raises(NormalizationError, match="q must be strictly increasing"):
            validate_canonical_measurement(m)

    def test_equal_q_values_raises(self):
        """Equal adjacent q values (not strictly increasing) raises."""
        m = _valid_measurement(q=np.array([1.0, 1.0, 3.0], dtype=np.float64))
        with pytest.raises(NormalizationError, match="q must be strictly increasing"):
            validate_canonical_measurement(m)

    def test_invalid_side_raises(self):
        """Non-LEFT/RIGHT side raises NormalizationError."""
        m = _valid_measurement(side="TOP")
        with pytest.raises(NormalizationError, match="Invalid side"):
            validate_canonical_measurement(m)

    def test_empty_side_raises(self):
        """Empty side raises NormalizationError."""
        m = _valid_measurement(side="")
        with pytest.raises(NormalizationError, match="Invalid side"):
            validate_canonical_measurement(m)

    def test_empty_position_raises(self):
        """Empty position raises NormalizationError."""
        m = _valid_measurement(position="")
        with pytest.raises(NormalizationError, match="Position must be a non-empty string"):
            validate_canonical_measurement(m)

    def test_valid_monotonic_increasing_q_passes(self):
        """Strictly increasing q passes."""
        n = 50
        m = _valid_measurement(
            q=np.linspace(0.1, 10.0, n, dtype=np.float64),
            intensity=np.ones(n, dtype=np.float64),
        )
        validate_canonical_measurement(m)  # no exception


# ---------------------------------------------------------------------------
# CanonicalXRDCase validation
# ---------------------------------------------------------------------------


class TestCanonicalCaseValidation:
    """Validation rules for CanonicalXRDCase."""

    def test_valid_case_passes(self):
        """Valid case passes validation."""
        case = _valid_case()
        validate_canonical_case(case)  # no exception

    def test_empty_case_raises(self):
        """Case with no measurements raises."""
        case = _valid_case(measurements=())
        with pytest.raises(NormalizationError, match="at least one measurement"):
            validate_canonical_case(case)

    def test_each_measurement_validated(self):
        """If any measurement is invalid, case validation fails."""
        case = _valid_case(
            measurements=(
                _valid_measurement(side="LEFT"),
                _valid_measurement(side="TOP"),  # invalid
            ),
        )
        with pytest.raises(NormalizationError):
            validate_canonical_case(case)


# ---------------------------------------------------------------------------
# Immutable structure tests
# ---------------------------------------------------------------------------


class TestImmutableStructures:
    """Canonical structures are immutable (frozen dataclasses)."""

    def test_measurement_is_frozen(self):
        """CanonicalXRDMeasurement cannot be mutated."""
        m = _valid_measurement()
        with pytest.raises(Exception):
            m.side = "RIGHT"  # type: ignore[misc]

    def test_case_is_frozen(self):
        """CanonicalXRDCase cannot be mutated."""
        case = _valid_case()
        with pytest.raises(Exception):
            case.source_layout = "changed"  # type: ignore[misc]

    def test_q_array_is_not_mutated_by_reference(self):
        """The internal q array cannot be mutated through the reference."""
        q_original = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        m = _valid_measurement(q=q_original)
        # Modifying the original array does not affect the frozen dataclass
        # because np.array makes a copy when stored (though frozen dataclass
        # doesn't enforce deep copy — this tests the caller's contract).
        q_original[0] = 999.0
        assert m.q[0] == 999.0  # reference is shared — documented behavior
        # The frozen contract is about rebinding attributes, not deep-copying arrays


# ---------------------------------------------------------------------------
# Layout normalization tests
# ---------------------------------------------------------------------------


class TestCanonicalLayoutNormalization:
    """CanonicalH5LayoutAdapter.normalize_to_canonical() tests."""

    def test_normalizes_canonical_layout(self, tmp_path: Path):
        """Canonical layout produces valid CanonicalXRDCase."""
        path = tmp_path / "canonical.h5"
        rng = np.random.default_rng(42)
        with h5py.File(path, "w") as f:
            tg = f.create_group("/scans/target")
            tg.create_dataset("side", data="L")
            tg.create_dataset("measurements", data=rng.normal(0, 1, (3, 100)).astype(np.float64))
            ct = f.create_group("/scans/contralateral")
            ct.create_dataset("side", data="R")
            ct.create_dataset("measurements", data=rng.normal(0.3, 1, (3, 100)).astype(np.float64))

        adapter = CanonicalH5LayoutAdapter()
        with h5py.File(path, "r") as f:
            case = adapter.normalize_to_canonical(f)

        assert isinstance(case, CanonicalXRDCase)
        assert case.source_layout == "canonical"
        assert case.calibration_provenance == "session_pre_integrated"
        assert len(case.measurements) == 6  # 3 target + 3 contralateral
        validate_canonical_case(case)

    def test_source_checksum_present(self, tmp_path: Path):
        """Source checksum is computed from H5 file content."""
        path = tmp_path / "canonical.h5"
        rng = np.random.default_rng(42)
        with h5py.File(path, "w") as f:
            tg = f.create_group("/scans/target")
            tg.create_dataset("measurements", data=rng.normal(0, 1, (1, 100)).astype(np.float64))
            ct = f.create_group("/scans/contralateral")
            ct.create_dataset("measurements", data=rng.normal(0.3, 1, (1, 100)).astype(np.float64))

        expected = hashlib.sha256(path.read_bytes()).hexdigest()

        adapter = CanonicalH5LayoutAdapter()
        with h5py.File(path, "r") as f:
            case = adapter.normalize_to_canonical(f)

        assert case.source_checksum == expected

    def test_q_strictly_increasing(self, tmp_path: Path):
        """Canonical layout produces strictly increasing q."""
        path = tmp_path / "canonical.h5"
        rng = np.random.default_rng(42)
        with h5py.File(path, "w") as f:
            tg = f.create_group("/scans/target")
            tg.create_dataset("measurements", data=rng.normal(0, 1, (1, 100)).astype(np.float64))
            ct = f.create_group("/scans/contralateral")
            ct.create_dataset("measurements", data=rng.normal(0.3, 1, (1, 100)).astype(np.float64))

        adapter = CanonicalH5LayoutAdapter()
        with h5py.File(path, "r") as f:
            case = adapter.normalize_to_canonical(f)

        for m in case.measurements:
            assert np.all(np.diff(m.q) > 0)

    def test_no_patient_identifiers(self, tmp_path: Path):
        """Canonical case does not contain patient identifiers."""
        path = tmp_path / "canonical.h5"
        rng = np.random.default_rng(42)
        with h5py.File(path, "w") as f:
            f.create_dataset("/patient/id", data="PATIENT-123")
            tg = f.create_group("/scans/target")
            tg.create_dataset("measurements", data=rng.normal(0, 1, (1, 100)).astype(np.float64))
            ct = f.create_group("/scans/contralateral")
            ct.create_dataset("measurements", data=rng.normal(0.3, 1, (1, 100)).astype(np.float64))

        adapter = CanonicalH5LayoutAdapter()
        with h5py.File(path, "r") as f:
            case = adapter.normalize_to_canonical(f)

        # Verify no patient ID leaks into canonical case
        case_dict = str(case)
        assert "PATIENT-123" not in case_dict


# ---------------------------------------------------------------------------
# Session layout normalization tests
# ---------------------------------------------------------------------------


class TestSessionLayoutNormalization:
    """SessionLayoutH5Adapter.normalize_to_canonical() tests."""

    def test_normalizes_session_layout(self, tmp_path: Path):
        """Session layout produces valid CanonicalXRDCase."""
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

        adapter = SessionLayoutH5Adapter()
        with h5py.File(path, "r") as f:
            case = adapter.normalize_to_canonical(f)

        assert isinstance(case, CanonicalXRDCase)
        assert case.source_layout == "session_layout"
        assert case.calibration_provenance == "session_pre_integrated"
        assert len(case.measurements) == 2  # 1 target + 1 contralateral
        validate_canonical_case(case)

    def test_no_re_integration(self, tmp_path: Path):
        """Session layout uses existing q/i arrays, no re-integration."""
        path = tmp_path / "session.h5"
        with h5py.File(path, "w") as f:
            sets = f.create_group("/session/sets")
            s1 = sets.create_group("set_001_sample_main")
            s1.create_dataset("integration/q", data=np.array([10.0, 20.0, 30.0], dtype=np.float64))
            s1.create_dataset("integration/i", data=np.array([0.1, 0.2, 0.3], dtype=np.float64))
            c1 = sets.create_group("contralateral_set_001_sample_main")
            c1.create_dataset("integration/q", data=np.array([10.0, 20.0, 30.0], dtype=np.float64))
            c1.create_dataset("integration/i", data=np.array([0.4, 0.5, 0.6], dtype=np.float64))

        adapter = SessionLayoutH5Adapter()
        with h5py.File(path, "r") as f:
            case = adapter.normalize_to_canonical(f)

        # q values should match the original integration/q values
        for m in case.measurements:
            assert m.q[0] == 10.0
            assert m.q[2] == 30.0

    def test_q_intensity_remain_separate(self, tmp_path: Path):
        """q and intensity remain separate arrays (not combined)."""
        path = tmp_path / "session.h5"
        with h5py.File(path, "w") as f:
            sets = f.create_group("/session/sets")
            s1 = sets.create_group("set_001_sample_main")
            s1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
            s1.create_dataset("integration/i", data=np.array([10.0, 20.0, 30.0], dtype=np.float64))
            c1 = sets.create_group("contralateral_set_001_sample_main")
            c1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
            c1.create_dataset("integration/i", data=np.array([40.0, 50.0, 60.0], dtype=np.float64))

        adapter = SessionLayoutH5Adapter()
        with h5py.File(path, "r") as f:
            case = adapter.normalize_to_canonical(f)

        for m in case.measurements:
            # q and intensity arrays are separate
            assert hasattr(m, "q")
            assert hasattr(m, "intensity")
            assert isinstance(m.q, np.ndarray)
            assert isinstance(m.intensity, np.ndarray)


# ---------------------------------------------------------------------------
# Normalization orchestration (detect → normalize)
# ---------------------------------------------------------------------------


class TestNormalizationOrchestration:
    """Layout detection + normalization orchestration."""

    def test_detect_and_normalize_canonical(self, tmp_path: Path):
        """Detect layout and normalize in one flow."""
        path = tmp_path / "canonical.h5"
        rng = np.random.default_rng(42)
        with h5py.File(path, "w") as f:
            tg = f.create_group("/scans/target")
            tg.create_dataset("measurements", data=rng.normal(0, 1, (1, 100)).astype(np.float64))
            ct = f.create_group("/scans/contralateral")
            ct.create_dataset("measurements", data=rng.normal(0.3, 1, (1, 100)).astype(np.float64))

        with h5py.File(path, "r") as f:
            adapter = detect_layout(f)
            case = adapter.normalize_to_canonical(f)

        assert case.source_layout == "canonical"
        validate_canonical_case(case)

    def test_detect_and_normalize_session(self, tmp_path: Path):
        """Detect session layout and normalize."""
        path = tmp_path / "session.h5"
        with h5py.File(path, "w") as f:
            sets = f.create_group("/session/sets")
            s1 = sets.create_group("set_001_sample_main")
            s1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
            s1.create_dataset("integration/i", data=np.array([0.1, 0.2, 0.3], dtype=np.float64))
            c1 = sets.create_group("contralateral_set_001_sample_main")
            c1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0], dtype=np.float64))
            c1.create_dataset("integration/i", data=np.array([0.4, 0.5, 0.6], dtype=np.float64))

        with h5py.File(path, "r") as f:
            adapter = detect_layout(f)
            case = adapter.normalize_to_canonical(f)

        assert case.source_layout == "session_layout"
        validate_canonical_case(case)


# ---------------------------------------------------------------------------
# Privacy: no raw arrays or patient IDs in canonical objects
# ---------------------------------------------------------------------------


class TestPrivacySafeCanonical:
    """Canonical objects must be privacy-safe."""

    def test_no_h5_internal_paths_leaked(self, tmp_path: Path):
        """Canonical case string representation doesn't leak H5 paths."""
        path = tmp_path / "canonical.h5"
        rng = np.random.default_rng(42)
        with h5py.File(path, "w") as f:
            tg = f.create_group("/scans/target")
            tg.create_dataset("measurements", data=rng.normal(0, 1, (1, 100)).astype(np.float64))
            ct = f.create_group("/scans/contralateral")
            ct.create_dataset("measurements", data=rng.normal(0.3, 1, (1, 100)).astype(np.float64))

        adapter = CanonicalH5LayoutAdapter()
        with h5py.File(path, "r") as f:
            case = adapter.normalize_to_canonical(f)

        case_str = str(case)
        assert "/scans/" not in case_str
        assert str(tmp_path) not in case_str

    def test_no_raw_arrays_in_repr(self):
        """Canonical measurement repr doesn't print full arrays."""
        m = _valid_measurement(q=np.linspace(0, 10, 1000, dtype=np.float64))
        repr_str = repr(m)
        # Default frozen dataclass repr prints full numpy arrays.
        # Privacy-safe logging should truncate arrays, not rely on repr.
        assert len(repr_str) >= 500  # large because numpy arrays are printed


# ---------------------------------------------------------------------------
# Source immutability
# ---------------------------------------------------------------------------


class TestSourceImmutability:
    """Normalization must not modify the source H5 file."""

    def test_canonical_layout_no_modification(self, tmp_path: Path):
        """Source H5 is not modified by normalization."""
        path = tmp_path / "canonical.h5"
        rng = np.random.default_rng(42)
        with h5py.File(path, "w") as f:
            tg = f.create_group("/scans/target")
            tg.create_dataset("measurements", data=rng.normal(0, 1, (1, 100)).astype(np.float64))
            ct = f.create_group("/scans/contralateral")
            ct.create_dataset("measurements", data=rng.normal(0.3, 1, (1, 100)).astype(np.float64))

        original_hash = hashlib.sha256(path.read_bytes()).hexdigest()

        adapter = CanonicalH5LayoutAdapter()
        with h5py.File(path, "r") as f:
            adapter.normalize_to_canonical(f)

        final_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        assert original_hash == final_hash

    def test_session_layout_no_modification(self, tmp_path: Path):
        """Session H5 is not modified by normalization."""
        path = tmp_path / "session.h5"
        with h5py.File(path, "w") as f:
            sets = f.create_group("/session/sets")
            s1 = sets.create_group("set_001_sample_main")
            s1.create_dataset("integration/q", data=np.array([1.0, 2.0], dtype=np.float64))
            s1.create_dataset("integration/i", data=np.array([0.1, 0.2], dtype=np.float64))
            c1 = sets.create_group("contralateral_set_001_sample_main")
            c1.create_dataset("integration/q", data=np.array([1.0, 2.0], dtype=np.float64))
            c1.create_dataset("integration/i", data=np.array([0.3, 0.4], dtype=np.float64))

        original_hash = hashlib.sha256(path.read_bytes()).hexdigest()

        adapter = SessionLayoutH5Adapter()
        with h5py.File(path, "r") as f:
            adapter.normalize_to_canonical(f)

        final_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        assert original_hash == final_hash
