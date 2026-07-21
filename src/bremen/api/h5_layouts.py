"""H5 layout adapter/plugin boundary.

Defines the adapter protocol for resolving a prediction context from
different H5 container layouts.  Built-in adapters:
- CanonicalH5LayoutAdapter: existing /scans/target/ + /scans/contralateral/
- CalibrationSampleH5LayoutAdapter: calibration-group sample layout
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import h5py
import numpy as np


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

    raise H5ContainerError("Unrecognised H5 container layout — h5_preflight_failed")


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


def _extract_position_token(dataset_name: str) -> str | None:
    """Extract a position token like P1, P2, P3 from a dataset name.

    Returns the normalized token (e.g., 'P1') if exactly one
    P<number> token is found.  Returns ``None`` if no token or
    multiple conflicting tokens are detected.

    Only matches the pattern ``P`` or ``p`` followed by one or more
    digits.  Does NOT match patient/sample identifiers or other
    filename components.
    """
    matches = re.findall(r'[Pp](\d+)', dataset_name)
    if len(matches) == 0:
        return None
    if len(matches) > 1:
        # Multiple conflicting P tokens — cannot disambiguate
        return None
    return f"P{matches[0]}"


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
        # Default refs when empty — allows no-ref calls to work
        t_ref = target_scan_ref if target_scan_ref and target_scan_ref.strip() else "target"
        c_ref = control_scan_ref if control_scan_ref and control_scan_ref.strip() else "contralateral"

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
# Session layout adapter (legacy/synthetic demo H5 containers)
# ---------------------------------------------------------------------------


class SessionLayoutH5Adapter(H5LayoutAdapter):
    """Adapter for legacy/synthetic session-layout diffraction H5 containers.

    Detects H5 files with ``/session/sets`` structure containing paired
    ``set_NNN_sample_main`` and ``contralateral_set_NNN_sample_main``
    groups with ``integration/q`` and ``integration/i`` datasets.

    This adapter does NOT use Aramis product labels, biopsy metadata,
    or clinical classifications as Bremen prediction targets.
    """

    name = "session_layout"

    def detect(self, h5_file: h5py.File) -> bool:
        # Must NOT claim canonical or calibration layouts
        if "/scans/target/measurements" in h5_file:
            return False
        # Must have session/sets
        if "/session/sets" not in h5_file:
            return False
        # Verify at least one target-contralateral pair exists
        try:
            groups = list(h5_file["/session/sets"].keys())
        except Exception:
            return False
        for key in groups:
            if key.startswith("set_") and "_sample_main" in key:
                contra_key = f"contralateral_{key}"
                if contra_key in groups:
                    return True
        return False

    def resolve_prediction_context(
        self,
        h5_file: h5py.File,
        target_scan_ref: str,
        control_scan_ref: str,
    ) -> H5PredictionContext:
        from bremen.api.preflight import (
            H5MetadataError,
            H5ContainerError,
            H5SideMismatchError,
            H5PatientMismatchError,
            resolve_patient_metadata,
        )

        # Determine mode: explicit-ref vs automatic pair detection.
        # Whitespace-only strings count as absent.
        t_provided = bool(target_scan_ref and target_scan_ref.strip())
        c_provided = bool(control_scan_ref and control_scan_ref.strip())

        sets_group = h5_file["/session/sets"]
        group_keys = list(sets_group.keys())

        target_path: str | None = None
        control_path: str | None = None
        t_ref: str = ""
        c_ref: str = ""

        if t_provided and c_provided:
            # Validate and use explicit refs
            t_ref = _validate_ref(target_scan_ref, "target_scan_ref")
            c_ref = _validate_ref(control_scan_ref, "control_scan_ref")
            if t_ref in group_keys:
                target_path = f"/session/sets/{t_ref}"
            if c_ref in group_keys:
                control_path = f"/session/sets/{c_ref}"
        elif not t_provided and not c_provided:
            # Automatic pair detection — find first valid set/contralateral pair
            for key in sorted(group_keys):
                if key.startswith("set_") and "_sample_main" in key:
                    contra_key = f"contralateral_{key}"
                    if contra_key in group_keys:
                        target_path = f"/session/sets/{key}"
                        control_path = f"/session/sets/{contra_key}"
                        t_ref = key
                        c_ref = contra_key
                        break
        else:
            raise H5ContainerError(
                "Both target_scan_ref and control_scan_ref must be provided "
                "together or omitted together"
            )

        if not target_path or not control_path:
            raise H5ContainerError(
                "No valid target-controlateral pair found in "
                "/session/sets"
            )

        # Validate integration arrays exist and have correct shape
        for path, label in [(target_path, "target"), (control_path, "control")]:
            for arr_name in ("integration/q", "integration/i"):
                arr_full = f"{path}/{arr_name}"
                if arr_full not in h5_file:
                    raise H5ContainerError(
                        f"Missing {arr_full} for {label} scan"
                    )
                arr = h5_file[arr_full][:]
                if not isinstance(arr, (list, tuple, h5py.Dataset, np.ndarray)) or len(arr) == 0:
                    raise H5ContainerError(
                        f"Empty or invalid {arr_full} for {label} scan"
                    )

        # Validate q axes compatibility
        target_q = np.asarray(h5_file[f"{target_path}/integration/q"][()], dtype=np.float64)
        control_q = np.asarray(h5_file[f"{control_path}/integration/q"][()], dtype=np.float64)
        if len(target_q) != len(control_q):
            raise H5ContainerError(
                "Target and control q-axis lengths do not match"
            )
        if np.max(np.abs(target_q - control_q)) > 0.01:
            raise H5ContainerError(
                "Target and control q-axes are not compatible for "
                "Bremen feature computation"
            )

        # Patient metadata
        try:
            patient_meta = resolve_patient_metadata(h5_file)
        except Exception:
            patient_meta = None

        # Side metadata — read from sample_type/side if available
        # Use safe defaults: "target" / "contralateral"
        # This adapter intentionally does NOT use biopsy/birads/target_side
        # labels as prediction targets.
        target_side: str | None = None
        control_side: str | None = None

        # Try reading from session/sample/sample_type
        session_sample_type = _read_sample_metadata_str(
            h5_file, "/session", "sample/sample_type"
        )
        # If session-level sample_type not available, look up via sets group path
        if session_sample_type is not None:
            target_side = _breast_type_to_side(session_sample_type)
            if target_side == "RIGHT":
                control_side = "LEFT"
            else:
                control_side = "RIGHT"
        else:
            # Try reading sample_type from target/control group sibling paths
            # using the parent of the sets group
            try:
                t_st = _read_sample_metadata_str(
                    h5_file, "/session", "sample/sample_type"
                )
                if t_st:
                    target_side = _breast_type_to_side(t_st)
                    control_side = "LEFT" if target_side == "RIGHT" else "RIGHT"
            except Exception:
                pass

        # Measurement count from integration arrays
        try:
            target_count = len(np.asarray(h5_file[f"{target_path}/integration/i"][()]))
        except Exception:
            target_count = 0
        try:
            control_count = len(np.asarray(h5_file[f"{control_path}/integration/i"][()]))
        except Exception:
            control_count = 0

        return H5PredictionContext(
            layout_name=self.name,
            target_scan_ref=t_ref,
            control_scan_ref=c_ref,
            target_group_path=target_path,
            control_group_path=control_path,
            target_side=target_side,
            control_side=control_side,
            patient_identifier=(
                patient_meta.patient_identifier if patient_meta else "unknown"
            ),
            patient_identifier_source=(
                patient_meta.patient_identifier_source
                if patient_meta
                else "session_layout"
            ),
            metadata_fallback_used=(
                patient_meta.fallback_used if patient_meta else True
            ),
            target_measurement_count=target_count,
            control_measurement_count=control_count,
            adapter_metadata={
                "layout_name": self.name,
                "pairing_method": "set_contralateral_index",
            },
        )


# ---------------------------------------------------------------------------
# Matador raw acquisition adapter
# ---------------------------------------------------------------------------


class MatadorRawH5Adapter(H5LayoutAdapter):
    """Adapter for Matador raw acquisition H5 containers.

    Detects H5 files with raw 2D diffraction images and calibration
    (PONI) data.  Discover calibration data, raw measurement datasets,
    and pair bilateral measurements by position.

    The actual 2D-to-1D radial integration is performed via the
    ``xrd_preprocessing`` library wrapper in the preprocessing bridge.

    This adapter does NOT use Aramis product labels, biopsy metadata,
    or clinical classifications as Bremen prediction targets.
    """

    name = "matador_raw"

    def detect(self, h5_file: h5py.File) -> bool:
        """Detect Matador raw acquisition H5 layout.

        Detection strategy (first match wins):

        1. Explicit exclusions: must NOT be canonical or session layout.
        2. Tier 1 — native ``list_h5_sessions`` +
           ``list_h5_measurement_sets`` from ``xrd_preprocessing``.
        3. Tier 2 — structural ``visititems`` fallback: at least one
           2D numeric dataset AND at least one calibration/PONI dataset
           anywhere in the file.

        Detection MUST NOT depend on filename, top-level group-name
        keyword matching, or product/patient labels.
        """
        # --- Explicit exclusions ---
        if "/scans/target/measurements" in h5_file:
            return False
        if "/session/sets" in h5_file:
            return False

        # --- Tier 1: xrd_preprocessing native session listing ---
        try:
            from xrd_preprocessing import (
                list_h5_sessions,
                list_h5_measurement_sets,
            )

            h5_path = str(h5_file.filename)
            sessions = list_h5_sessions(h5_path)
            if sessions is not None and isinstance(sessions, object) and len(sessions) > 0:
                measurements = list_h5_measurement_sets(h5_path)
                if measurements is not None and isinstance(measurements, object) and len(measurements) > 0:
                    return True
        except Exception:
            pass

        # --- Tier 2: structural fallback ---
        found_2d_image = False
        found_calib_or_poni = False

        def _visitor(name: str, obj: object) -> None:
            nonlocal found_2d_image, found_calib_or_poni
            if isinstance(obj, h5py.Dataset):
                ndim = len(obj.shape) if hasattr(obj, 'shape') else 0
                dtype_kind = obj.dtype.kind if hasattr(obj, 'dtype') else ''
                name_lower = name.lower()
                # 2D numeric image
                if ndim >= 2 and dtype_kind in ('f', 'i', 'u'):
                    found_2d_image = True
                # Calibration / PONI keywords anywhere in the path
                if any(kw in name_lower for kw in (
                    'poni', 'distance', 'wavelength', 'pixel_size',
                    'center_x', 'center_y', 'calibration',
                )):
                    found_calib_or_poni = True

        h5_file.visititems(_visitor)
        return found_2d_image and found_calib_or_poni

    def resolve_prediction_context(
        self,
        h5_file: h5py.File,
        target_scan_ref: str,
        control_scan_ref: str,
    ) -> H5PredictionContext:
        """Discover measurements, pair by position/side, resolve context.

        Walks the H5 tree to find all 2D numeric measurement datasets,
        resolves side and position metadata from group attributes, pairs
        bilateral measurements by a shared position key, and validates
        completeness.
        """
        from bremen.api.preflight import (
            H5MetadataError,
            H5ContainerError,
            resolve_patient_metadata,
        )

        # ---- Phase 1: Discover calibration subtrees ----
        # Walk the H5 to identify groups/datasets related to calibration.
        # Record the top-level calibration group path prefixes.
        calib_subtree_prefixes: set[str] = set()

        def _calib_finder(name: str, obj: object) -> None:
            if isinstance(obj, (h5py.Dataset, h5py.Group)):
                name_lower = name.lower()
                if any(kw in name_lower for kw in (
                    'poni', 'calib', 'calibration', 'distance',
                    'wavelength', 'pixel_size', 'center_x', 'center_y',
                )):
                    # Record the containing group path
                    prefix = "/" + "/".join(name.split("/")[:-1]) if "/" in name else ""
                    if prefix:
                        calib_subtree_prefixes.add(prefix)

        h5_file.visititems(_calib_finder)

        # ---- Phase 2: Discover measurement datasets (exclude calibration) ----
        measurements: list[dict] = []

        def _meas_visitor(name: str, obj: object) -> None:
            if not isinstance(obj, h5py.Dataset):
                return
            ndim = len(obj.shape) if hasattr(obj, 'shape') else 0
            dtype_kind = obj.dtype.kind if hasattr(obj, 'dtype') else ''
            if not (ndim >= 2 and dtype_kind in ('f', 'i', 'u')):
                return
            # Exclude datasets under calibration subtrees
            name_path = "/" + name
            for prefix in calib_subtree_prefixes:
                if name_path.startswith(prefix + "/") or name_path == prefix:
                    return
            # Walk up to find the containing group
            parent_path = "/" + "/".join(name.split("/")[:-1])
            parent = h5_file.get(parent_path)
            measurements.append({
                "dataset_path": name,
                "dataset_name": name.split("/")[-1],
                "group_path": parent_path,
                "group_name": parent_path.rstrip("/").split("/")[-1],
                "shape": obj.shape,
                "dtype": obj.dtype,
                "parent_attrs": dict(parent.attrs) if parent is not None else {},
            })

        h5_file.visititems(_meas_visitor)

        if len(measurements) < 2:
            raise H5ContainerError(
                "Insufficient 2D measurement datasets found for bilateral pairing"
            )

        # ---- Resolve side and position/pair-key from attributes ----
        #    Preferred attribute keys (case-insensitive lookup):
        #    - side: "side", "breast_side", "sample_side", "organSide"
        #    - position: "position", "pair_key", "measurement_position"
        SIDE_ATTR_KEYS = ("side", "breast_side", "sample_side", "organSide")
        POS_ATTR_KEYS = ("position", "pair_key", "measurement_position")

        def _resolve_attr(attrs: dict, keys: tuple[str, ...]) -> str | None:
            """Case-insensitive attribute lookup."""
            for k in keys:
                for ak, av in attrs.items():
                    if ak.lower() == k.lower():
                        val = str(av).strip()
                        return val if val else None
            return None

        for m in measurements:
            attrs = m.get("parent_attrs", {})
            m["side"] = _resolve_attr(attrs, SIDE_ATTR_KEYS)
            m["pair_key"] = _resolve_attr(attrs, POS_ATTR_KEYS)
            # If no explicit pair_key, extract P<number> token from dataset name
            if m["pair_key"] is None:
                ds_name = m.get("dataset_name", "")
                token = _extract_position_token(ds_name)
                if token is not None:
                    m["pair_key"] = token

        # ---- Validate all measurements have side ----
        missing_side = [m["dataset_path"] for m in measurements if not m["side"]]
        if missing_side:
            raise H5ContainerError(
                "Missing side metadata for one or more measurements"
            )

        # Normalise sides
        for m in measurements:
            side = m["side"].upper()
            if side in ("LEFT", "L"):
                m["side"] = "LEFT"
            elif side in ("RIGHT", "R"):
                m["side"] = "RIGHT"
            else:
                raise H5MetadataError(
                    "Unrecognised side value"
                )

        # ---- Validate all measurements have a valid pair_key ----
        missing_pair_key = [m["dataset_path"] for m in measurements if not m["pair_key"]]
        if missing_pair_key:
            # Check for multiple conflicting P tokens first (more specific error)
            for m in measurements:
                if m["pair_key"] is not None:
                    continue
                ds_name = m.get("dataset_name", "")
                matches = re.findall(r'[Pp](\d+)', ds_name)
                if len(matches) > 1:
                    raise H5ContainerError(
                        "Multiple conflicting position tokens in measurement name"
                    )
            raise H5ContainerError(
                "Missing position/pair-key metadata for one or more measurements"
            )

        # ---- Detect multiple conflicting P tokens ----
        for m in measurements:
            ds_name = m.get("dataset_name", "")
            matches = re.findall(r'[Pp](\d+)', ds_name)
            if len(matches) > 1:
                raise H5ContainerError(
                    "Multiple conflicting position tokens in measurement name"
                )

        # ---- Pair by position key (NOT first-two) ----
        pair_keys = {m["pair_key"] for m in measurements}
        pairs: dict[str, dict[str, dict]] = {}
        for m in measurements:
            pk = m["pair_key"]
            pairs.setdefault(pk, {})
            if m["side"] in pairs[pk]:
                raise H5ContainerError(
                    f"Duplicate side for pair_key {pk!r}"
                )
            pairs[pk][m["side"]] = m

        # Find all complete bilateral pairs
        complete_pairs = [
            (pk, sd) for pk, sd in pairs.items()
            if "LEFT" in sd and "RIGHT" in sd
        ]
        if not complete_pairs:
            raise H5ContainerError(
                "No complete bilateral pair (LEFT + RIGHT) found"
            )

        # Exactly one complete pair required — reject ambiguity
        if len(complete_pairs) > 1:
            raise H5ContainerError(
                "Ambiguous bilateral pair set — multiple complete pairs found"
            )

        # Use the single complete pair
        pair_key, sides = complete_pairs[0]
        left_m = sides["LEFT"]
        right_m = sides["RIGHT"]

        # ---- Discover calibration data ----
        calib_refs: dict[str, str] = {}

        def _calib_visitor(name: str, obj: object) -> None:
            if isinstance(obj, h5py.Dataset):
                name_lower = name.lower()
                if any(kw in name_lower for kw in (
                    'poni', 'distance', 'wavelength', 'pixel_size',
                    'center_x', 'center_y',
                )):
                    calib_refs[name] = str(obj.dtype)

        h5_file.visititems(_calib_visitor)

        if not calib_refs:
            raise H5ContainerError(
                "No PONI/calibration data found"
            )

        # ---- Patient metadata ----
        try:
            patient_meta = resolve_patient_metadata(h5_file)
        except Exception:
            patient_meta = None

        # ---- Detection target/control mapping ----
        # In bilateral pairing the clinical target vs control designation
        # is deferred to the clinician.  We assign LEFT as target and
        # RIGHT as control for deterministic processing only.
        target_m = left_m
        control_m = right_m

        return H5PredictionContext(
            layout_name=self.name,
            target_scan_ref=target_m["dataset_path"],
            control_scan_ref=control_m["dataset_path"],
            target_group_path=target_m["group_path"],
            control_group_path=control_m["group_path"],
            target_side=target_m["side"],
            control_side=control_m["side"],
            patient_identifier=(
                patient_meta.patient_identifier if patient_meta else "unknown"
            ),
            patient_identifier_source=(
                patient_meta.patient_identifier_source
                if patient_meta
                else "matador_raw"
            ),
            metadata_fallback_used=(
                patient_meta.fallback_used if patient_meta else True
            ),
            target_measurement_count=len(measurements),
            control_measurement_count=len(measurements),
            adapter_metadata={
                "layout_name": self.name,
                "calibration_refs": calib_refs,
                "pair_key": pair_key,
                "target_dataset_path": target_m["dataset_path"],
                "control_dataset_path": control_m["dataset_path"],
                "measurement_count": len(measurements),
            },
        )


# ---------------------------------------------------------------------------
# Register built-in adapters
# ---------------------------------------------------------------------------

register_adapter(CanonicalH5LayoutAdapter())
register_adapter(CalibrationSampleH5LayoutAdapter())
register_adapter(SessionLayoutH5Adapter())
register_adapter(MatadorRawH5Adapter())
