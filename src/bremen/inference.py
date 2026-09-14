"""DEPRECATED compatibility shim — Bremen v0.1 portable inference (PR0154).

The authoritative implementation moved to the inference-complete Bremen model
package: ``bremen.model_packages.bremen_v01.predictor``.

This module re-exports the identical objects (zero logic) so the historical
``bremen.inference`` import path keeps resolving for the existing platform
callers (``feature_artifact_prediction``, ``inference_handler``,
``s3_model_discovery``, ``server``) and for test fixtures during the
transition.  New code must import from the package.

There is exactly ONE active scientific implementation — the package module.
"""
from __future__ import annotations

from bremen.model_packages.bremen_v01.predictor import (
    PortableLogRegModelError,
    adapt_model_package,
    predict_proba_portable,
    validate_portable_logreg_model,
)

__all__ = [
    "PortableLogRegModelError",
    "adapt_model_package",
    "predict_proba_portable",
    "validate_portable_logreg_model",
]
