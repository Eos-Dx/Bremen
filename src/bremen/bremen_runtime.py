"""DEPRECATED compatibility shim — Bremen v0.1 runtime (PR0154).

The authoritative inference-complete Bremen runtime moved to the model
package: ``bremen.model_packages.bremen_v01.runtime`` (entry point
``bremen.model_packages.bremen_v01``).

This module re-exports the identical objects (zero logic) so historical
``bremen.bremen_runtime`` import paths keep resolving for external callers and
test fixtures during the transition.  New code must import from the package.

There is exactly ONE active scientific implementation — the package module.
The runtime constants and error-category mapping now live in the package
(``runtime``/``manifest``).
"""
from __future__ import annotations

from bremen.model_packages.bremen_v01.runtime import (
    # ``BremenFeatureError`` is re-exported by the package runtime for caller
    # compatibility (the PR0152 runtime surface exposed it here).
    BremenFeatureError,
    BremenFeatures,
    BremenModelResult,
    BremenRuntime,
    BremenRuntimeError,
)

__all__ = [
    "BremenFeatureError",
    "BremenFeatures",
    "BremenModelResult",
    "BremenRuntime",
    "BremenRuntimeError",
]
