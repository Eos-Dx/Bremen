"""Canonical in-memory XRD representation and layout normalization.

Converts supported H5 layouts into a canonical scientific form
before any workflow-specific computation.  No H5 mutation, no
workflow-specific normalization.

PR0075 — multi-workflow runtime foundation.

PR0156 — the canonical input vocabulary (measurement/case dataclasses,
``NormalizationError`` and the structural validators) has a single neutral
authoritative home in ``bremen.canonical_input`` so model-runtime packages can
depend on generic cross-model input vocabulary without importing the
``bremen.api`` platform layer.  This module re-exports those objects (identical
``is`` identity, zero logic) and continues to serve as the platform-side
canonical surface used by H5 normalizers, job handlers and the runtime
orchestrator.  Layout adapters that import these names from here are unchanged.
"""
from __future__ import annotations

from bremen.canonical_input import (
    CanonicalXRDCase,
    CanonicalXRDMeasurement,
    NormalizationError,
    validate_canonical_case,
    validate_canonical_measurement,
)

__all__ = [
    "CanonicalXRDCase",
    "CanonicalXRDMeasurement",
    "NormalizationError",
    "validate_canonical_case",
    "validate_canonical_measurement",
]
