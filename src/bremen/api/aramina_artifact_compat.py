"""DEPRECATED compatibility shim — Aramina artifact pickle bridge (PR0156).

The authoritative implementation moved to the inference-complete Aramina model
package: ``bremen.model_packages.aramina_v0213.artifact_compat`` (Model Package
Standard v1).  This module re-exports the identical classes/functions (zero
logic) so the historical ``bremen.api.aramina_artifact_compat`` import path
keeps resolving for existing callers and test fixtures during the transition.
New code must import from the package.

There is exactly ONE active scientific implementation — the package module.
"""
from __future__ import annotations

from bremen.model_packages.aramina_v0213.artifact_compat import (
    GatedSymmetryLogistic,
    TargetBreastGatedSymmetryLogistic,
    ensure_compatibility_bridge,
)

__all__ = [
    "GatedSymmetryLogistic",
    "TargetBreastGatedSymmetryLogistic",
    "ensure_compatibility_bridge",
]
