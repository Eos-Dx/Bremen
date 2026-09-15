"""DEPRECATED compatibility shim — Aramina raw-H5 preprocessing (PR0156).

The authoritative implementation moved to the inference-complete Aramina model
package: ``bremen.model_packages.aramina_v0213.preprocessing`` (Model Package
Standard v1).  This module re-exports the identical objects (zero logic) so the
historical ``bremen.api.aramina_preprocessing`` import path keeps resolving for
existing callers and test fixtures during the transition.  New code must import
from the package.

There is exactly ONE active scientific implementation — the package module.
"""
from __future__ import annotations

from bremen.model_packages.aramina_v0213.preprocessing import (  # noqa: F401
    PREPROCESSING_EXCEPTION_CLASSES,
    PREPROCESSING_REASON_CODES,
    PREPROCESSING_RELEASES,
    PREPROCESSING_STAGES,
    AraminaPreprocessingError,
    _log_preprocessing_rejection,
    preprocessing_release_tag,
    safe_preprocessing_diagnostic,
    preprocess_aramina,
)

__all__ = [
    "PREPROCESSING_EXCEPTION_CLASSES",
    "PREPROCESSING_REASON_CODES",
    "PREPROCESSING_RELEASES",
    "PREPROCESSING_STAGES",
    "AraminaPreprocessingError",
    "preprocess_aramina",
    "preprocessing_release_tag",
    "safe_preprocessing_diagnostic",
]
