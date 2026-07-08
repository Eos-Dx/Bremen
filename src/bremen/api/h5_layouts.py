"""H5 layout adapter/plugin boundary.

Defines the adapter protocol for resolving a prediction context from
different H5 container layouts.  Built-in adapters:
- CanonicalH5LayoutAdapter: existing /scans/target/ + /scans/contralateral/
- CalibrationSampleH5LayoutAdapter: calibration-group sample layout
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import h5py


# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------


@dataclass
class H5PredictionContext:
    """Resolved prediction context from an H5 layout adapter."""

    layout_name: str
    target_scan_ref: str
    control_scan_ref: str
    target_group_path: str
    control_group_path: str
    target_side: str | None
    control_side: str | None
    patient_identifier: str
    patient_identifier_source: str
    metadata_fallback_used: bool
    target_measurement_count: int | None
    control_measurement_count: int | None
    adapter_metadata: dict[str, Any]


# ---------------------------------------------------------------------------
# Abstract adapter
# ---------------------------------------------------------------------------


class H5LayoutAdapter(ABC):
    """Abstract base for H5 layout adapters."""

    name: str = ""

    @abstractmethod
    def detect(self, h5_file: h5py.File) -> bool:
        """Return True if this adapter can handle the H5 layout."""

    @abstractmethod
    def resolve_prediction_context(
        self,
        h5_file: h5py.File,
        target_scan_ref: str,
        control_scan_ref: str,
    ) -> H5PredictionContext:
        """Resolve target/control refs to a prediction context.

        Raises H5MetadataError, H5ContainerError, H5SideMismatchError,
        H5PatientMismatchError on validation failure.
        """


# ---------------------------------------------------------------------------
# Adapter registry
# ---------------------------------------------------------------------------

_BUILTIN_ADAPTERS: list[H5LayoutAdapter] = []


def register_adapter(adapter: H5LayoutAdapter) -> None:
    """Register a built-in adapter."""
    _BUILTIN_ADAPTERS.append(adapter)


def detect_layout(h5_file: h5py.File) -> H5LayoutAdapter:
    """Detect the H5 layout by trying registered adapters in order.

    Returns the first adapter whose detect() returns True.
    Raises H5ContainerError if no adapter matches.
    """
    for adapter in _BUILTIN_ADAPTERS:
        if adapter.detect(h5_file):
            return adapter
    from bremen.api.preflight import H5ContainerError

    raise H5ContainerError("Unrecognised H5 container layout")


# ---------------------------------------------------------------------------
# Helper: validate scan refs
# ---------------------------------------------------------------------------


def _validate_ref(ref: str | None, label: str) -> str:
    """Validate and normalise a scan ref string.

    Returns the stripped ref.
    Raises ValueError for invalid refs.
    """
    if not ref or not ref.strip():
        raise ValueError(f"{label} must be a non-empty string")
    stripped = ref.strip()
    if stripped.startswith("/"):
        raise ValueError(f"{label} must not start with '/'")
    if ".." in stripped:
        raise ValueError(f"{label} contains invalid path characters")
    return stripped


# ---------------------------------------------------------------------------
# Canonical layout adapter
# ---------------------------------------------------------------------------


class CanonicalH5LayoutAdapter(H5LayoutAdapter):
    """Adapter for canonical /scans/target/ + /scans/contralateral/ layout."""

    name = "canonical"

    def detect(self, h5_file: h5py.File) -> bool:
        return "/scans/target/measurements" in h5_file

    def resolve_prediction_context(
        self,
        h5_file: h5py.File,
        target_scan_ref: str,
        control_scan_ref: str,
    ) -> H5PredictionContext:
        # Validate refs
        t_ref = _validate_ref(target_scan_ref, "target_scan_ref")
        c_ref = _validate_ref(control_scan_ref, "control_scan_ref")

        # Canonical expects specific ref values
        if t_ref != "target":
            from bremen.api.preflight import H5MetadataError

            raise H5MetadataError(
                "target_scan_ref for canonical layout must be 'target'"
            )
        if c_ref != "contralateral":
            from bremen.api.preflight import H5MetadataError

            raise H5MetadataError(
                "control_scan_ref for canonical layout must be 'contralateral'"
            )

        # Use existing resolve_patient_metadata for patient ID
        from bremen.api.preflight import resolve_patient_metadata

        patient_meta = resolve_patient_metadata(h5_file)

        # Read sides
        target_side = _read_side(h5_file, "/scans/target/side")
        control_side = _read_side(h5_file, "/scans/contralateral/side")

        # Read measurements for counting
        from bremen.api.preflight import H5MeasurementError

        target_measurements = h5_file["/scans/target/measurements"][:]
        control_measurements = h5_file["/scans/contralateral/measurements"][:]
        target_count = (
            len(target_measurements) if target_measurements.size > 0 else 0
        )
        control_count = (
            len(control_measurements) if control_measurements.size > 0 else 0
        )

        return H5PredictionContext(
            layout_name="canonical",
            target_scan_ref=t_ref,
            control_scan_ref=c_ref,
            target_group_path="/scans/target",
            control_group_path="/scans/contralateral",
            target_side=target_side,
            control_side=control_side,
            patient_identifier=patient_meta.patient_identifier,
            patient_identifier_source=patient_meta.patient_identifier_source,
            metadata_fallback_used=patient_meta.fallback_used,
            target_measurement_count=target_count,
            control_measurement_count=control_count,
            adapter_metadata={},
        )


# ---------------------------------------------------------------------------
# Calibration sample layout adapter
# ---------------------------------------------------------------------------


class CalibrationSampleH5LayoutAdapter(H5LayoutAdapter):
    """Adapter for calibration-group sample layout.

    Detects H5 files with top-level calib_* groups containing
    sample/patient_name and sample/sample_type metadata.
    Requires explicit target_scan_ref and control_scan_ref paths.
    """

    name = "calibration_sample"

    def detect(self, h5_file: h5py.File) -> bool:
        # Must NOT claim canonical layouts
        if "/scans/target/measurements" in h5_file:
            return False
        # Look for calibration group with sample metadata
        for key in h5_file.keys():
            if key.startswith("calib_"):
                calib_group = h5_file[key]
                if _has_sample_metadata(calib_group):
                    return True
        return False

    def resolve_prediction_context(
        self,
        h5_file: h5py.File,
        target_scan_ref: str,
        control_scan_ref: str,
    ) -> H5PredictionContext:
        from bremen.api.preflight import (
            H5ContainerError,
            H5MetadataError,
            H5PatientMismatchError,
            H5SideMismatchError,
        )

        # Validate refs
        t_ref = _validate_ref(target_scan_ref, "target_scan_ref")
        c_ref = _validate_ref(control_scan_ref, "control_scan_ref")

        # Reject identical refs
        if t_ref == c_ref:
            raise H5ContainerError("Target and control refs must be distinct")

        # Build absolute paths
        target_path = f"/{t_ref}"
        control_path = f"/{c_ref}"

        # Verify groups exist
        if target_path not in h5_file:
            raise H5ContainerError("Target scan group not found")
        if control_path not in h5_file:
            raise H5ContainerError("Control scan group not found")
        if not isinstance(h5_file.get(target_path, None), h5py.Group):
            raise H5ContainerError("Target scan group not found")
        if not isinstance(h5_file.get(control_path, None), h5py.Group):
            raise H5ContainerError("Control scan group not found")

        # Read patient_name from both samples
        target_pn = _read_sample_metadata_str(
            h5_file, target_path, "sample/patient_name"
        )
        control_pn = _read_sample_metadata_str(
            h5_file, control_path, "sample/patient_name"
        )

        # Validate patient_name values
        if not target_pn or not target_pn.strip():
            raise H5MetadataError("Missing sample patient_name metadata")
        if not control_pn or not control_pn.strip():
            raise H5MetadataError("Missing sample patient_name metadata")
        if target_pn != control_pn:
            raise H5PatientMismatchError(
                "Target and control patient names do not match"
            )

        # Read sample_type from both samples
        target_type = _read_sample_metadata_str(
            h5_file, target_path, "sample/sample_type"
        )
        control_type = _read_sample_metadata_str(
            h5_file, control_path, "sample/sample_type"
        )

        # Validate sample_type values
        if not target_type or not target_type.strip():
            raise H5MetadataError("Missing sample_type metadata")
        if not control_type or not control_type.strip():
            raise H5MetadataError("Missing sample_type metadata")

        # Resolve sides from sample_type
        target_side = _breast_type_to_side(target_type)
        control_side = _breast_type_to_side(control_type)

        # Validate opposite sides
        if target_side == control_side:
            raise H5SideMismatchError(
                "Target and control samples are the same breast side"
            )

        # Count measurement sets
        target_count = _count_sets(h5_file, target_path)
        control_count = _count_sets(h5_file, control_path)

        # Find calibration group name for adapter_metadata
        calib_group = _find_calibration_group(h5_file)

        resolved_pn = target_pn.strip()

        return H5PredictionContext(
            layout_name="calibration_sample",
            target_scan_ref=t_ref,
            control_scan_ref=c_ref,
            target_group_path=target_path,
            control_group_path=control_path,
            target_side=target_side,
            control_side=control_side,
            patient_identifier=resolved_pn,
            patient_identifier_source="patient_name_fallback",
            metadata_fallback_used=True,
            target_measurement_count=target_count,
            control_measurement_count=control_count,
            adapter_metadata={
                "calibration_group": calib_group,
            },
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _has_sample_metadata(group: h5py.Group) -> bool:
    """Check if a group contains sample-level metadata.

    Walks the group tree using h5py Group/K keys  (relative)
    rather than absolute paths to avoid path resolution issues.
    """
    found_patient_name = False
    found_sample_type = False

    def _walk(obj: h5py.Group, accumulated: str) -> None:
        nonlocal found_patient_name, found_sample_type
        for key in obj.keys():
            sub = obj[key]
            sub_path = f"{accumulated}/{key}" if accumulated else f"/{key}"
            if isinstance(sub, h5py.Group):
                _walk(sub, sub_path)
            else:
                if sub_path.endswith("/sample/patient_name"):
                    found_patient_name = True
                if sub_path.endswith("/sample/sample_type"):
                    found_sample_type = True

    _walk(group, "")
    return found_patient_name and found_sample_type


def _read_sample_metadata_str(
    h5_file: h5py.File, sample_path: str, dataset_rel_path: str
) -> str | None:
    """Read a sample metadata string dataset.

    Returns stripped string, or None if path not found or empty.
    """
    full_path = f"{sample_path}/{dataset_rel_path}"
    if full_path not in h5_file:
        return None
    try:
        item = h5_file[full_path]
        raw = item[()]
        if isinstance(raw, bytes):
            val = raw.decode("utf-8")
        else:
            val = str(raw)
        stripped = val.strip()
        return stripped if stripped else None
    except Exception:
        return None


def _read_side(h5_file: h5py.File, side_path: str) -> str | None:
    """Read a side dataset from a fixed path."""
    from bremen.api.preflight import H5MetadataError

    if side_path not in h5_file:
        raise H5MetadataError(f"Missing {side_path}")
    try:
        raw = h5_file[side_path][()]
        if isinstance(raw, bytes):
            return raw.decode("utf-8").strip()
        return str(raw).strip()
    except Exception as exc:
        raise H5MetadataError(f"Cannot read {side_path}: {exc}") from exc


_BREAST_TYPE_SIDE_MAP: dict[str, str] = {
    "RIGHT BREAST": "RIGHT",
    "LEFT BREAST": "LEFT",
    "right breast": "RIGHT",
    "left breast": "LEFT",
    "BREAST RIGHT": "RIGHT",
    "BREAST LEFT": "LEFT",
    "breast right": "RIGHT",
    "breast left": "LEFT",
}


def _breast_type_to_side(sample_type: str) -> str:
    """Convert a sample_type string to a normalised side value (LEFT/RIGHT)."""
    from bremen.api.preflight import H5MetadataError

    normalised = sample_type.strip()
    # Try direct lookup
    if normalised in _BREAST_TYPE_SIDE_MAP:
        return _BREAST_TYPE_SIDE_MAP[normalised]

    # Try case-insensitive normalised lookup
    upper_val = normalised.upper()
    for pattern, side in _BREAST_TYPE_SIDE_MAP.items():
        if pattern.upper() == upper_val:
            return side

    raise H5MetadataError("Cannot determine breast side from sample_type")


def _count_sets(h5_file: h5py.File, sample_path: str) -> int:
    """Count the number of measurement set groups under a sample."""
    sets_path = f"{sample_path}/sets"
    if sets_path not in h5_file:
        return 0
    sets_group = h5_file[sets_path]
    count = sum(1 for key in sets_group.keys() if key.startswith("set_"))
    return count


def _find_calibration_group(h5_file: h5py.File) -> str | None:
    """Find the first top-level calibration group key."""
    for key in h5_file.keys():
        if key.startswith("calib_"):
            return key
    return None


# ---------------------------------------------------------------------------
# Register built-in adapters
# ---------------------------------------------------------------------------

register_adapter(CanonicalH5LayoutAdapter())
register_adapter(CalibrationSampleH5LayoutAdapter())
