"""DEPRECATED compatibility shim — Aramina symmetry features (PR0156).

The authoritative implementation moved to the inference-complete Aramina model
package: ``bremen.model_packages.aramina_v0213.symmetry`` (Model Package
Standard v1).  This module re-exports the identical objects (zero logic) so the
historical ``bremen.api.aramina_symmetry`` import path keeps resolving for
existing callers and test fixtures during the transition.  New code must import
from the package.

There is exactly ONE active scientific implementation — the package module.
"""
from __future__ import annotations

from bremen.model_packages.aramina_v0213.symmetry import (
    CORE4,
    symmetry_features,
)

__all__ = [
    "CORE4",
    "symmetry_features",
]
