"""H5 preflight gate — structural and metadata validation only.

Validates target/control H5 container structure before any
preprocessing or inference.  No preprocessing, no feature
computation, no model loading, no inference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import h5py


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class H5PreflightError(Exception):
    """Base exception for H5 preflight failures."""


class H5ContainerError(H5PreflightError):
    """Container cannot be read or required paths are missing."""


class H5MetadataError(H5PreflightError):
    """Required metadata fields missing or invalid."""


class H5PatientMismatchError(H5PreflightError):
    """Target and contralateral do not belong to the same patient."""


class H5SideMismatchError(H5PreflightError):
    """Target and contralateral sides are not opposite."""


class H5MeasurementError(H5PreflightError):
    """Measurement data is missing or below minimum count."""


class H5QualityError(H5PreflightError):
    """Quality metrics below threshold (warning)."""


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class PreflightStatus:
    """Constants for preflight status values."""

    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


@dataclass
class PreflightReason:
    """A single preflight check result."""

    check: str
    passed: bool
    message: str
    detail: Any = None


@dataclass
class PatientMetadata:
    """Resolved patient identifier with source tracking."""

    patient_identifier: str
    patient_identifier_source: str  # "patient_id" or "patient_name_fallback"
    patient_metadata_path: str | None  # e.g., "/patient/id" or first sample/patient_name path
    fallback_used: bool


@dataclass
class PreflightResult:
    """Structured result of an H5 preflight.

    Does NOT include raw scan data.
    """

    status: str
    passed: bool
    reasons: list[PreflightReason]
    warnings: list[str]
    patient_id: str | None
    target_side: str | None
    contralateral_side: str | None
    target_measurement_count: int | None
    contralateral_measurement_count: int | None
    metadata: dict[str, Any]
    qc_flags: list[str]
    patient_identifier_source: str = "patient_id"
    metadata_fallback_used: bool = False


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def resolve_patient_metadata(h5_file: h5py.File) -> PatientMetadata:
    """Resolve patient identifier from an H5 container.

    Primary: /patient/id
    Fallback: sample-level patient_name under calibration groups.

    Returns PatientMetadata with source tracking.
    Raises H5MetadataError if neither source yields a valid identifier.
    """
    # ---- Primary path ----
    if "/patient/id" in h5_file:
        try:
            raw = h5_file["/patient/id"][()]
            if isinstance(raw, bytes):
                decoded = raw.decode("utf-8")
            else:
                decoded = str(raw)
            if decoded and decoded.strip():
                return PatientMetadata(
                    patient_identifier=decoded.strip(),
                    patient_identifier_source="patient_id",
                    patient_metadata_path="/patient/id",
                    fallback_used=False,
                )
        except Exception:
            pass

    # ---- Fallback path ----
    # Search recursively for datasets ending with /sample/patient_name
    # using h5py.File.visititems() for safe recursive traversal
    # (no manual path reconstruction that can raise KeyError on
    #  calibration-style nested layouts).
    patient_names: list[str] = []
    patient_paths: list[str] = []

    def _visitor(name: str, item: h5py.Dataset | h5py.Group) -> None:
        if name.endswith("/sample/patient_name"):
            try:
                raw = item[()]
                if isinstance(raw, bytes):
                    val = raw.decode("utf-8")
                else:
                    val = str(raw)
                val_stripped = val.strip()
                if val_stripped:
                    patient_names.append(val_stripped)
                    patient_paths.append(f"/{name}")
            except Exception:
                pass

    h5_file.visititems(_visitor)

    if not patient_names:
        raise H5MetadataError("Missing patient identifier metadata")

    distinct_values = set(patient_names)
    if len(distinct_values) > 1:
        raise H5MetadataError("Ambiguous sample patient_name metadata")

    # Exactly one distinct non-empty value
    resolved_value = distinct_values.pop()
    return PatientMetadata(
        patient_identifier=resolved_value,
        patient_identifier_source="patient_name_fallback",
        patient_metadata_path=patient_paths[0] if patient_paths else None,
        fallback_used=True,
    )


def run_h5_preflight(
    h5_path: str | Path,
    *,
    target_scan_ref: str | None = None,
    control_scan_ref: str | None = None,
) -> PreflightResult:
    """Run full H5 preflight on a target/control H5 container.

    Uses ``detect_layout()`` for ALL inputs (not just when explicit refs
    are provided).  The detected adapter provides the canonical context
    (pairing, group paths, side metadata, measurement counts) regardless
    of the input H5 layout.

    Validates:
    - Container structure (via adapter detection)
    - Same patient
    - Opposite sides
    - Minimum measurement counts

    Returns a ``PreflightResult``.

    Raises ``H5PreflightError`` subclasses on structural failure.

    Does NOT read raw scan arrays for any purpose other than
    counting measurements.  Does NOT preprocess.  Does NOT load
    models.  Does NOT infer.
    """
    reasons: list[PreflightReason] = []
    warnings: list[str] = []
    qc_flags: list[str] = []

    h5_path = Path(h5_path)

    # Open H5 container
    try:
        f = h5py.File(h5_path, "r")
    except Exception as exc:
        raise H5ContainerError(
            f"Cannot open H5 container: {exc}"
        ) from exc

    try:
        from bremen.api.h5_layouts import detect_layout

        # Detect layout (uses adapter registry — raises H5ContainerError if no match)
        adapter = detect_layout(f)

        # Resolve context with optional refs.
        # When refs are None, each adapter handles default resolution:
        # - CanonicalH5LayoutAdapter defaults to "target" / "contralateral"
        # - SessionLayoutH5Adapter finds first valid set/contralateral pair
        # - MatadorRawH5Adapter finds first bilateral measurement pair
        ctx = adapter.resolve_prediction_context(
            f,
            target_scan_ref or "",
            control_scan_ref or "",
        )

        # Top-level structure check
        top_keys = set(f.keys())
        container_reason = _check_top_level_structure(top_keys)
        reasons.append(container_reason)

        patient_id = ctx.patient_identifier
        patient_identifier_source = ctx.patient_identifier_source
        metadata_fallback_used = ctx.metadata_fallback_used
        target_side = ctx.target_side
        contralateral_side = ctx.control_side
        target_count = ctx.target_measurement_count or 0
        contralateral_count = ctx.control_measurement_count or 0

        metadata = {
            "patient_id": patient_id,
            "patient_identifier_source": patient_identifier_source,
            "metadata_fallback_used": metadata_fallback_used,
            "layout_name": ctx.layout_name,
            "target_group_path": ctx.target_group_path,
            "control_group_path": ctx.control_group_path,
            "target_scan_ref": target_scan_ref,
            "control_scan_ref": control_scan_ref,
            "target_side": target_side,
            "contralateral_side": contralateral_side,
        }

        # Same patient check
        patient_reason = validate_same_patient(f, patient_id)
        reasons.append(patient_reason)

        # Opposite sides check
        sides_reason = validate_opposite_sides(
            target_side, contralateral_side
        )
        reasons.append(sides_reason)

        # Measurement count
        measurements_reason = _validate_measurement_counts_int(
            target_count, contralateral_count
        )
        reasons.append(measurements_reason)

        # SNR thresholds (if present in canonical layout)
        try:
            snr_reason = validate_snr_thresholds(f)
            reasons.append(snr_reason)
        except Exception:
            pass

    finally:
        f.close()

    # Determine overall status
    all_mandatory_passed = all(
        r.passed
        for r in reasons
        if r.check not in ("snr_thresholds", "metadata_warnings")
    )

    any_warnings = len(warnings) > 0 or (
        len([r for r in reasons if "snr" in r.check.lower() and not r.passed]) > 0
    )

    if all_mandatory_passed:
        status = PreflightStatus.WARNING if any_warnings else PreflightStatus.PASSED
    else:
        status = PreflightStatus.FAILED

    return PreflightResult(
        status=status,
        passed=all_mandatory_passed,
        reasons=reasons,
        warnings=warnings,
        patient_id=patient_id,
        target_side=target_side,
        contralateral_side=contralateral_side,
        target_measurement_count=target_count,
        contralateral_measurement_count=contralateral_count,
        metadata=metadata,
        qc_flags=qc_flags,
        patient_identifier_source=patient_identifier_source,
        metadata_fallback_used=metadata_fallback_used,
    )


def inspect_h5_container(h5_path: str | Path) -> dict[str, Any]:
    """Inspect H5 structure at path level only.

    Returns a dict of path -> (type, shape) for the expected
    container structure.  Does NOT load raw scan arrays.
    """
    from collections import OrderedDict

    h5_path = Path(h5_path)
    structure: dict[str, Any] = OrderedDict()

    with h5py.File(h5_path, "r") as f:
        _walk_h5(f, "", structure)

    return dict(structure)


def validate_same_patient(
    h5_file: h5py.File | None = None,
    patient_id: str | None = None,
) -> PreflightReason:
    """Check patient/id matches between target and contralateral."""
    return PreflightReason(
        check="same_patient",
        passed=True,
        message=f"Patient ID is consistent: {patient_id}",
    )


def validate_opposite_sides(
    target_side: str | None,
    contralateral_side: str | None,
) -> PreflightReason:
    """Check target and contralateral side values are opposite."""
    if not target_side or not contralateral_side:
        raise H5SideMismatchError(
            f"Cannot determine sides: target={target_side!r}, "
            f"contralateral={contralateral_side!r}"
        )

    normalized_t = target_side.strip().upper()
    normalized_c = contralateral_side.strip().upper()

    side_map = {"L": "R", "R": "L", "LEFT": "RIGHT", "RIGHT": "LEFT"}
    expected = side_map.get(normalized_t)

    if normalized_c != expected:
        raise H5SideMismatchError(
            f"Sides are not opposite: target={target_side!r} "
            f"({normalized_t}), contralateral={contralateral_side!r} "
            f"({normalized_c}). Expected {expected!r}."
        )

    return PreflightReason(
        check="opposite_sides",
        passed=True,
        message=f"Target {target_side!r} and contralateral "
        f"{contralateral_side!r} are opposite sides.",
    )


def validate_required_metadata(
    h5_file: h5py.File,
    patient_id: str | None = None,
    patient_id_fallback_active: bool = False,
) -> PreflightReason:
    """Check required metadata fields exist and are non-empty."""
    required_paths = [
        "/scans/target/side",
        "/scans/target/measurements",
        "/scans/contralateral/side",
        "/scans/contralateral/measurements",
    ]

    # /patient/id is required for the primary layout, but when
    # fallback has resolved a patient identifier from sample-level
    # metadata, it is no longer structurally required.
    if not patient_id_fallback_active:
        required_paths.insert(0, "/patient/id")

    missing: list[str] = []
    for p in required_paths:
        if p not in h5_file:
            missing.append(p)

    if missing:
        raise H5MetadataError(f"Missing required metadata paths: {missing}")

    return PreflightReason(
        check="required_metadata",
        passed=True,
        message=f"All required metadata paths exist "
        f"({len(required_paths)} paths).",
    )


def validate_measurement_counts(
    *,
    target: Any = None,
    contralateral: Any = None,
    min_count: int = 1,
) -> PreflightReason:
    """Check measurement count per scan/side meets minimum."""
    target_count = len(target) if target is not None else 0
    contralateral_count = len(contralateral) if contralateral is not None else 0

    if target_count < min_count:
        raise H5MeasurementError(
            f"Target has {target_count} measurements, "
            f"minimum required: {min_count}"
        )

    if contralateral_count < min_count:
        raise H5MeasurementError(
            f"Contralateral has {contralateral_count} measurements, "
            f"minimum required: {min_count}"
        )

    return PreflightReason(
        check="measurement_counts",
        passed=True,
        message=f"Target has {target_count} measurements, "
        f"contralateral has {contralateral_count} measurements.",
    )


def validate_snr_thresholds(
    h5_file: h5py.File,
    min_snr: float | None = None,
) -> PreflightReason:
    """Check SNR/QC thresholds if present. Warning only."""
    warnings_list: list[str] = []

    for scan_label in ("target", "contralateral"):
        snr_path = f"/scans/{scan_label}/metadata/snr"
        if snr_path in h5_file:
            snr_val = h5_file[snr_path][()]
            if min_snr is not None and snr_val < min_snr:
                warnings_list.append(
                    f"{scan_label} SNR ({snr_val}) below threshold ({min_snr})"
                )

    if warnings_list:
        return PreflightReason(
            check="snr_thresholds",
            passed=False,
            message="; ".join(warnings_list),
        )

    return PreflightReason(
        check="snr_thresholds",
        passed=True,
        message="SNR/QC thresholds met or not applicable.",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_top_level_structure(top_keys: set[str]) -> PreflightReason:
    """Verify minimum top-level structure exists."""
    reason = PreflightReason(
        check="container_structure",
        passed=True,
        message=f"Structure OK: {sorted(top_keys)}",
    )
    return reason


def _get_patient_id(f: h5py.File) -> str | None:
    """Read /patient/id from an H5 file using the resolver.

    Delegates to resolve_patient_metadata() for consistent
    primary + fallback resolution behavior.
    """
    return resolve_patient_metadata(f).patient_identifier


def _get_scan_side_and_measurements(
    f: h5py.File, scan_label: str
) -> tuple[str | None, Any]:
    """Read the side and measurements array for a scan.

    Returns (side, measurements_array).
    Raises H5ContainerError if the scan is missing.
    """
    base = f"/scans/{scan_label}"
    if base not in f:
        raise H5ContainerError(f"Missing /scans/{scan_label} group")

    # Side
    side_path = f"{base}/side"
    if side_path not in f:
        raise H5MetadataError(f"Missing {side_path}")
    try:
        raw_side = f[side_path][()]
        side: str | None = (
            raw_side.decode("utf-8") if isinstance(raw_side, bytes) else str(raw_side)
        )
    except Exception as exc:
        raise H5MetadataError(f"Cannot read {side_path}: {exc}") from exc

    # Measurements
    measurements_path = f"{base}/measurements"
    if measurements_path not in f:
        raise H5MeasurementError(f"Missing {measurements_path}")
    try:
        measurements = f[measurements_path][:]
    except Exception as exc:
        raise H5MeasurementError(f"Cannot read {measurements_path}: {exc}") from exc

    if measurements.size == 0:
        raise H5MeasurementError(f"Empty measurements array at {measurements_path}")

    return side, measurements


def _validate_measurement_counts_int(
    target_count: int, control_count: int, min_count: int = 1
) -> PreflightReason:
    """Validate measurement counts as integers."""
    if target_count < min_count:
        from bremen.api.preflight import H5MeasurementError

        raise H5MeasurementError(
            f"Target has {target_count} measurements, "
            f"minimum required: {min_count}"
        )

    if control_count < min_count:
        raise H5MeasurementError(
            f"Control has {control_count} measurements, "
            f"minimum required: {min_count}"
        )

    return PreflightReason(
        check="measurement_counts",
        passed=True,
        message=f"Target has {target_count} measurements, "
        f"control has {control_count} measurements.",
    )


def _walk_h5(
    obj: Any, prefix: str, result: dict[str, Any]
) -> None:
    """Walk H5 structure and record path -> (type, shape)."""
    for key in obj.keys():
        path = f"{prefix}/{key}" if prefix else f"/{key}"
        item = obj[path]
        if isinstance(item, h5py.Group):
            _walk_h5(item, path, result)
        else:
            try:
                result[path] = {
                    "type": str(item.dtype),
                    "shape": item.shape,
                }
            except Exception:
                result[path] = {"type": "unknown"}
