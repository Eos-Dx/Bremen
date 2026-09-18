"""Bremen v0.1 inference-complete model package (PR0154).

One clear runtime entry point implementing Model Runtime Contract v1
(``bremen.contracts.model_runtime.ModelRuntime``):

- ``BremenRuntime`` — requirements / validate / predict over the frozen
  PR0151/PR0152 scientific sequence.

The package owns the complete model-specific inference contract: exact
3 LEFT + 3 RIGHT validation, preprocessing, q-grid behavior, smoothing,
normalization, replicate statistics, the frozen 15 features, imputation and
scaling, portable logistic-regression execution, the model-owned threshold,
safe scientific diagnostics and release identity/provenance.

Platform code should import the runtime entry point here (or the
``.runtime`` module) rather than the internal ``features`` / ``predictor``
scientific helpers.  Release identity and the model-declared input contract
live in ``.manifest``.

Research decision support requiring radiologist review; no clinical or
release claim is established by packaging.
"""
from __future__ import annotations

from bremen.model_packages.bremen_v01 import manifest
from bremen.model_packages.bremen_v01.runtime import (
    BremenFeatureError,
    BremenFeatures,
    BremenModelResult,
    BremenRuntime,
    BremenRuntimeError,
)

PACKAGE_ID = manifest.PACKAGE_ID
MODEL_CONTRACT_VERSION = manifest.MODEL_CONTRACT_VERSION

__all__ = [
    "BremenFeatureError",
    "BremenFeatures",
    "BremenModelResult",
    "BremenRuntime",
    "BremenRuntimeError",
    "MODEL_CONTRACT_VERSION",
    "PACKAGE_ID",
    "manifest",
]
