"""Neutral H5 canonicalization owned by the standalone ML plugin.

The platform's ``bremen.platform.sources.legacy_layouts`` module is
platform-owned and must never be imported by a release.  This module carries
the same established canonical layout logic for the layouts the five IR-03
variants require, using only ``h5py``/``numpy`` and the neutral
``bremen.contracts.canonical_input`` vocabulary.

The arithmetic is a faithful carrier of the existing adapters: the same
datasets, the same side metadata rules and the same canonical case fields are
produced.  No scientific value is recomputed here.  Unsupported layouts fail
closed with a safe reason instead of guessing.

Archive layouts (``matador_raw``) are intentionally not supported in this
release.  B2/B3 consume the raw H5 through their own artifact-owned
preprocessing and therefore do not use this module.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

import h5py
import numpy as np

from bremen.contracts.canonical_input import (
    CanonicalXRDCase,
    CanonicalXRDMeasurement,
)
from bremen.ml_plugin.errors import PluginInputError

__all__ = [
    "canonical_case_from_h5",
    "detect_layout_name",
    "SUPPORTED_LAYOUTS",
]

SUPPORTED_LAYOUTS = ("canonical", "calibration_sample", "session_layout")

_LAYOUT_VERSION = "v1"


# ---------------------------------------------------------------------------
# Shared metadata helpers (same established rules as the platform adapters)
# ---------------------------------------------------------------------------


def _read_sample_metadata_str(
    h5_file: h5py.File, group_path: str, relative_path: str,
) -> str | None:
    full_path = f"{group_path.rstrip('/')}/{relative_path}"
    if full_path not in h5_file:
        return None
    try:
        raw = h5_file[full_path][()]
    except Exception:
        return None
    if isinstance(raw, bytes):
        try:
            return raw.decode("utf-8").strip()
        except Exception:
            return None
    if isinstance(raw, str):
        return raw.strip()
    return str(raw).strip()


def _breast_type_to_side(sample_type: str) -> str:
    normalized = str(sample_type or "").strip().upper()
    if "LEFT" in normalized:
        return "LEFT"
    if "RIGHT" in normalized:
        return "RIGHT"
    raise PluginInputError("unknown_sample_side")


def _checksum(h5_file: h5py.File) -> str:
    return hashlib.sha256(Path(h5_file.filename).read_bytes()).hexdigest()


def _case(
    *, layout: str, checksum: str, measurements: list[CanonicalXRDMeasurement],
    calibration_provenance: str = "session_pre_integrated",
) -> CanonicalXRDCase:
    return CanonicalXRDCase(
        source_layout=layout,
        source_layout_version=_LAYOUT_VERSION,
        source_checksum=checksum,
        calibration_provenance=calibration_provenance,
        measurements=tuple(measurements),
    )


# ---------------------------------------------------------------------------
# Canonical /scans layout
# ---------------------------------------------------------------------------


def _detect_canonical(h5_file: h5py.File) -> bool:
    return "/scans/target/measurements" in h5_file


def _canonical_pair(h5_file: h5py.File) -> CanonicalXRDCase:
    measurements: list[CanonicalXRDMeasurement] = []
    for side, label in (("LEFT", "target"), ("RIGHT", "contralateral")):
        array = np.asarray(h5_file[f"/scans/{label}/measurements"][:], dtype=np.float64)
        profiles = [array] if array.ndim == 1 else [
            np.asarray(array[index], dtype=np.float64) for index in range(array.shape[0])
        ]
        for index, profile in enumerate(profiles):
            measurements.append(
                CanonicalXRDMeasurement(
                    side=side,
                    position=f"scan_{index}",
                    q=np.arange(len(profile), dtype=np.float64),
                    intensity=profile,
                )
            )
    return _case(
        layout="canonical", checksum=_checksum(h5_file), measurements=measurements,
    )


def _canonical_bremen(h5_file: h5py.File) -> CanonicalXRDCase:
    """Use explicit physical q coordinates for Bremen, never array indices."""
    from dataclasses import replace

    case = _canonical_pair(h5_file)
    measurements: list[CanonicalXRDMeasurement] = []
    for side, label in (("LEFT", "target"), ("RIGHT", "contralateral")):
        q_path = f"/scans/{label}/q"
        if q_path not in h5_file:
            raise PluginInputError("missing_physical_q")
        q = np.asarray(h5_file[q_path][()], dtype=np.float64)
        for index, measurement in enumerate(
            m for m in case.measurements if m.side == side
        ):
            measurements.append(
                replace(measurement, q=q if q.ndim == 1 else q[index])
            )
    return _case(
        layout="canonical", checksum=case.source_checksum, measurements=measurements,
    )


# ---------------------------------------------------------------------------
# Calibration-group sample layout
# ---------------------------------------------------------------------------


def _has_sample_metadata(group: h5py.Group) -> bool:
    return "sample" in group and "patient_name" in group["sample"]


def _find_calibration_group(h5_file: h5py.File) -> str | None:
    for key in h5_file:
        if not key.startswith("calib_"):
            continue
        group = h5_file[key]
        if _has_sample_metadata(group):
            return key
        for sample_key in group:
            if sample_key.startswith("sample_") and _has_sample_metadata(group[sample_key]):
                return key
    return None


def _detect_calibration(h5_file: h5py.File) -> bool:
    if "/scans/target/measurements" in h5_file:
        return False
    return any(
        key.startswith("calib_") and _has_sample_metadata(h5_file[key])
        for key in h5_file
    )


def _calibration_pair(h5_file: h5py.File) -> CanonicalXRDCase:
    group_name = _find_calibration_group(h5_file)
    if group_name is None:
        raise PluginInputError("no_calibration_group")
    group = h5_file[group_name]
    sample_keys = sorted(k for k in group if k.startswith("sample_"))
    if len(sample_keys) < 2:
        raise PluginInputError("insufficient_calibration_samples")
    target_path = f"/{group_name}/{sample_keys[0]}"
    control_path = f"/{group_name}/{sample_keys[1]}"
    target_sets = sorted(k for k in h5_file[f"{target_path}/sets"] if k.startswith("set_"))
    control_sets = sorted(k for k in h5_file[f"{control_path}/sets"] if k.startswith("set_"))
    if not target_sets or not control_sets:
        raise PluginInputError("missing_calibration_sets")
    target_set = f"{target_path}/sets/{target_sets[0]}"
    control_set = f"{control_path}/sets/{control_sets[0]}"
    target_side, control_side = "LEFT", "RIGHT"
    target_type = _read_sample_metadata_str(h5_file, target_path, "sample/sample_type")
    control_type = _read_sample_metadata_str(h5_file, control_path, "sample/sample_type")
    if target_type:
        target_side = _breast_type_to_side(target_type)
    if control_type:
        control_side = _breast_type_to_side(control_type)
    measurements = [
        CanonicalXRDMeasurement(
            side=target_side, position="session",
            q=np.asarray(h5_file[f"{target_set}/integration/q"][()], dtype=np.float64),
            intensity=np.asarray(h5_file[f"{target_set}/integration/i"][()], dtype=np.float64),
        ),
        CanonicalXRDMeasurement(
            side=control_side, position="session",
            q=np.asarray(h5_file[f"{control_set}/integration/q"][()], dtype=np.float64),
            intensity=np.asarray(h5_file[f"{control_set}/integration/i"][()], dtype=np.float64),
        ),
    ]
    return _case(
        layout="calibration_sample", checksum=_checksum(h5_file),
        measurements=measurements,
    )


def _calibration_bremen(h5_file: h5py.File) -> CanonicalXRDCase:
    measurements: list[CanonicalXRDMeasurement] = []
    for key, calibration in h5_file.items():
        if not key.startswith("calib_"):
            continue
        for sample_key, sample in calibration.items():
            if not sample_key.startswith("sample_"):
                continue
            sample_type = _read_sample_metadata_str(
                h5_file, sample.name, "sample/sample_type",
            )
            if not sample_type or "sets" not in sample:
                raise PluginInputError("missing_sample_profile_metadata")
            side = _breast_type_to_side(sample_type)
            for group in sample["sets"].values():
                if "integration/q" not in group or "integration/i" not in group:
                    raise PluginInputError("missing_sample_profile_arrays")
                measurements.append(
                    CanonicalXRDMeasurement(
                        side=side, position="session",
                        q=np.asarray(group["integration/q"][()], dtype=np.float64),
                        intensity=np.asarray(group["integration/i"][()], dtype=np.float64),
                    )
                )
    return _case(
        layout="calibration_sample", checksum=_checksum(h5_file),
        measurements=measurements,
    )


# ---------------------------------------------------------------------------
# Session layout
# ---------------------------------------------------------------------------


def _detect_session(h5_file: h5py.File) -> bool:
    if "/scans/target/measurements" in h5_file:
        return False
    if "/session/sets" not in h5_file:
        return False
    try:
        groups = list(h5_file["/session/sets"].keys())
    except Exception:
        return False
    return any(
        key.startswith("set_") and "_sample_main" in key
        and f"contralateral_{key}" in groups
        for key in groups
    )


def _session_bremen(h5_file: h5py.File) -> CanonicalXRDCase:
    sample_type = _read_sample_metadata_str(h5_file, "/session", "sample/sample_type")
    if not sample_type:
        raise PluginInputError("missing_session_side_metadata")
    target_side = _breast_type_to_side(sample_type)
    control_side = "RIGHT" if target_side == "LEFT" else "LEFT"
    measurements: list[CanonicalXRDMeasurement] = []
    for key, group in h5_file["/session/sets"].items():
        if key.startswith("contralateral_set_") and key.endswith("_sample_main"):
            side = control_side
        elif key.startswith("set_") and key.endswith("_sample_main"):
            side = target_side
        else:
            raise PluginInputError("unsupported_session_measurement_structure")
        if "integration/q" not in group or "integration/i" not in group:
            raise PluginInputError("missing_session_profile_arrays")
        measurements.append(
            CanonicalXRDMeasurement(
                side=side, position="session",
                q=np.asarray(group["integration/q"][()], dtype=np.float64),
                intensity=np.asarray(group["integration/i"][()], dtype=np.float64),
            )
        )
    return _case(
        layout="session_layout", checksum=_checksum(h5_file), measurements=measurements,
    )


def _session_pair(h5_file: h5py.File) -> CanonicalXRDCase:
    """Legacy Aramina pair selection (first set/contralateral pair)."""
    groups = h5_file["/session/sets"]
    group_keys = list(groups.keys())
    target_path = control_path = None
    for key in sorted(group_keys):
        if key.startswith("set_") and "_sample_main" in key:
            contra_key = f"contralateral_{key}"
            if contra_key in group_keys:
                target_path = f"/session/sets/{key}"
                control_path = f"/session/sets/{contra_key}"
                break
    if not target_path or not control_path:
        raise PluginInputError("no_target_control_pairs")

    for path in (target_path, control_path):
        for name in ("integration/q", "integration/i"):
            full_path = f"{path}/{name}"
            if full_path not in h5_file:
                raise PluginInputError("missing_session_profile_arrays")
            if len(h5_file[full_path][:]) == 0:
                raise PluginInputError("empty_session_profile_arrays")

    target_q = np.asarray(h5_file[f"{target_path}/integration/q"][()], dtype=np.float64)
    control_q = np.asarray(h5_file[f"{control_path}/integration/q"][()], dtype=np.float64)
    if len(target_q) != len(control_q):
        raise PluginInputError("q_axis_length_mismatch")
    if np.max(np.abs(target_q - control_q)) > 0.01:
        raise PluginInputError("q_axis_incompatible")

    target_side: str | None = None
    control_side: str | None = None
    session_sample_type = _read_sample_metadata_str(
        h5_file, "/session", "sample/sample_type",
    )
    if session_sample_type is not None:
        target_side = _breast_type_to_side(session_sample_type)
        control_side = "RIGHT" if target_side == "LEFT" else "LEFT"

    measurements = [
        CanonicalXRDMeasurement(
            side=(target_side or "LEFT"), position="session",
            q=target_q,
            intensity=np.asarray(h5_file[f"{target_path}/integration/i"][()], dtype=np.float64),
        ),
        CanonicalXRDMeasurement(
            side=(control_side or "RIGHT"), position="session",
            q=control_q,
            intensity=np.asarray(h5_file[f"{control_path}/integration/i"][()], dtype=np.float64),
        ),
    ]
    return _case(
        layout="session_layout", checksum=_checksum(h5_file), measurements=measurements,
    )


# ---------------------------------------------------------------------------
# Detection / public entry point
# ---------------------------------------------------------------------------

_Detector = Callable[[h5py.File], bool]
_Detectors: tuple[tuple[str, _Detector], ...] = (
    ("canonical", _detect_canonical),
    ("calibration_sample", _detect_calibration),
    ("session_layout", _detect_session),
)


def detect_layout_name(h5_file: h5py.File) -> str:
    """Return the first supported layout name, or raise safely."""
    for name, detector in _Detectors:
        try:
            if detector(h5_file):
                return name
        except Exception:
            continue
    raise PluginInputError("unsupported_container_layout")


def canonical_case_from_h5(h5_path: str, *, workflow_id: str) -> CanonicalXRDCase:
    """Normalize a staged H5 into the neutral canonical case.

    ``workflow_id == "bremen"`` preserves the platform's all-profile Bremen
    adapter; any other workflow uses the legacy pair-selection adapter.  The
    stored source checksum is the SHA-256 of the file bytes, as in the
    platform adapters.
    """
    try:
        with h5py.File(h5_path, "r") as h5_file:
            layout = detect_layout_name(h5_file)
            if layout == "canonical":
                return _canonical_bremen(h5_file) if workflow_id == "bremen" else _canonical_pair(h5_file)
            if layout == "calibration_sample":
                return _calibration_bremen(h5_file) if workflow_id == "bremen" else _calibration_pair(h5_file)
            return _session_bremen(h5_file) if workflow_id == "bremen" else _session_pair(h5_file)
    except PluginInputError:
        raise
    except Exception:
        raise PluginInputError("invalid_container") from None
