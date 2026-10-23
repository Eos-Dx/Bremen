"""Standalone XRD scientific feature library (Bremen IR-07).

No ``import bremen``, no platform/catalog/S3/Worker-protocol dependency. See
``README.md`` for the frozen contracts this package owns.
"""

from __future__ import annotations

from xrd_inference_features.aramina_symmetry import CORE4, symmetry_features
from xrd_inference_features.bremen_contract import (
    CONTRACT_ID as BREMEN_CONTRACT_ID,
    FEATURE_COLS,
    BremenFeatureError,
    build_bremen_features,
    build_bremen_features_from_frame,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "BREMEN_CONTRACT_ID",
    "FEATURE_COLS",
    "BremenFeatureError",
    "build_bremen_features",
    "build_bremen_features_from_frame",
    "CORE4",
    "symmetry_features",
]
