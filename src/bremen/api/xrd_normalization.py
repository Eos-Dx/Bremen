"""Canonical in-memory XRD representation and layout normalization.

Converts supported H5 layouts into a canonical scientific form
before any workflow-specific computation.  No H5 mutation, no
workflow-specific normalization.

PR0075 — multi-workflow runtime foundation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Canonical measurement types (immutable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CanonicalXRDMeasurement:
    """A single canonical XRD measurement.

    q and intensity are kept separate.  q must be 1D, strictly
    increasing, non-empty, and all-finite.  intensity must be 1D,
    same length as q, and all-finite.
    """

    side: str  # "LEFT" or "RIGHT"
    position: str  # validated structural token, e.g. "P1", "P2"
    q: np.ndarray  # shape (n,), strictly increasing
    intensity: np.ndarray  # shape (n,), same length as q
    qc_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CanonicalXRDCase:
    """Canonical XRD case produced by layout normalization.

    Immutable.  Contains all validated measurements from a single
    H5 container.  No patient identifiers.  No raw detector data
    after integration.  No workflow-specific normalization.
    """

    source_layout: str  # adapter name
    source_layout_version: str  # adapter version
    source_checksum: str  # SHA-256 of source H5
    calibration_provenance: str  # "poni_text" | "session_pre_integrated" | "none"
    measurements: tuple[CanonicalXRDMeasurement, ...]
    calibration_metadata: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class NormalizationError(Exception):
    """Base exception for canonical normalization failures."""


def validate_canonical_measurement(m: CanonicalXRDMeasurement) -> None:
    """Validate a canonical measurement's q and intensity arrays.

    Raises NormalizationError on any violation.
    """
    if m.side not in ("LEFT", "RIGHT"):
        raise NormalizationError(
            f"Invalid side {m.side!r} — must be LEFT or RIGHT"
        )
    if not isinstance(m.position, str) or not m.position.strip():
        raise NormalizationError("Position must be a non-empty string")
    if m.q.ndim != 1:
        raise NormalizationError("q must be 1-dimensional")
    if m.intensity.ndim != 1:
        raise NormalizationError("intensity must be 1-dimensional")
    if len(m.q) == 0:
        raise NormalizationError("q must be non-empty")
    if len(m.intensity) == 0:
        raise NormalizationError("intensity must be non-empty")
    if len(m.q) != len(m.intensity):
        raise NormalizationError(
            f"q length ({len(m.q)}) != intensity length ({len(m.intensity)})"
        )
    if not np.all(np.isfinite(m.q)):
        raise NormalizationError("q must be all-finite")
    if not np.all(np.isfinite(m.intensity)):
        raise NormalizationError("intensity must be all-finite")
    if not np.all(np.diff(m.q) > 0):
        raise NormalizationError("q must be strictly increasing")


def validate_canonical_case(case: CanonicalXRDCase) -> None:
    """Validate a complete canonical XRD case."""
    if not case.measurements:
        raise NormalizationError("Canonical case must have at least one measurement")
    for m in case.measurements:
        validate_canonical_measurement(m)
