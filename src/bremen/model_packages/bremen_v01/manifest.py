"""Authoritative Bremen v0.1 release manifest and inference-completeness record.

PR0154: this module is the single package-owned source for Bremen
``bremen-paper-reference-v0-2-0`` release identity and for the declared
model-specific input contract.  Platform code must consume these values only
through the package runtime entry point (``BremenRuntime.model_requirements``)
or this manifest; no platform module may re-declare scientific requirements.

Evidence anchors (do not edit without release change control):

- PR0151 froze the training contract and the golden fixture
  (``tests/fixtures/bremen_3x3/``).
- PR0152 verified the artifact SHA256 against the training run manifest and
  bound identity + portable parameters (docs/bremen_3x3_training_parity.md,
  Part 2).
- ``model_id`` is recorded in the training run manifest; the joblib artifact's
  ``model_identity`` block carries name+version only (PR0152 review note).

This is Python release-contract metadata, NOT the ADR-0007 artifact-directory
``manifest.json`` (see ``bremen.model_package``); it is intentionally not a
second artifact-manifest system.  Physical artifact staging/verification
remains platform-owned.
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Release identity (PR0151/PR0152 evidence)
# ---------------------------------------------------------------------------

PACKAGE_ID = "bremen_v01"
MODEL_CONTRACT_VERSION = "bremen_v01.inference_package.v1"

WORKFLOW_ID = "bremen"
MODEL_ID = "bremen-paper-reference-v0-2-0"
MODEL_NAME = "bremen_paper_reference_symmetry_logreg"
MODEL_VERSION = "0.2.0-paper-reference"
FEATURE_SCHEMA_VERSION = "v0.1"

# Artifact provenance verified in PR0152 (SHA256 of the exact joblib bytes).
ARTIFACT_SHA256 = "65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0"

# Decision-threshold identity from PR0151/PR0152 evidence.  The value applied
# at inference time always comes from the loaded artifact contract
# (predictor); this constant exists for provenance/reconciliation only.
THRESHOLD_VALUE = 0.3585907282566089

# ---------------------------------------------------------------------------
# Model-declared input contract (requirements ownership)
# ---------------------------------------------------------------------------

MEASUREMENT_SIDES: tuple[tuple[str, int], ...] = (("LEFT", 3), ("RIGHT", 3))
TOTAL_MEASUREMENTS = 6
REQUIRES_TARGET_SIDE = False
REQUEST_FIELDS: tuple[str, ...] = ("container_id", "source_id")
OPTIONAL_REQUEST_FIELDS: tuple[str, ...] = ()

INPUT_NOTES: tuple[str, ...] = (
    "Bremen requires exactly 3 LEFT and 3 RIGHT canonical "
    "measurements (six total) before any scientific work.",
)

# ---------------------------------------------------------------------------
# Scientific runtime dependencies (for PR0155 packaging capture)
# ---------------------------------------------------------------------------

# Minimum package-owned scientific dependency expectations (numpy/pandas/scipy
# only).  Exact pinned versions belong to the deployment image / PR0155.
RUNTIME_DEPENDENCIES: tuple[str, ...] = ("numpy", "pandas", "scipy")


@dataclass(frozen=True)
class ReleaseManifest:
    """Static release identity for the Bremen v0.1 inference package."""

    package_id: str
    model_id: str
    model_name: str
    model_version: str
    workflow_id: str
    feature_schema_version: str
    artifact_sha256: str
    threshold_value: float
    runtime_dependencies: tuple[str, ...]


RELEASE = ReleaseManifest(
    package_id=PACKAGE_ID,
    model_id=MODEL_ID,
    model_name=MODEL_NAME,
    model_version=MODEL_VERSION,
    workflow_id=WORKFLOW_ID,
    feature_schema_version=FEATURE_SCHEMA_VERSION,
    artifact_sha256=ARTIFACT_SHA256,
    threshold_value=THRESHOLD_VALUE,
    runtime_dependencies=RUNTIME_DEPENDENCIES,
)


def release_manifest() -> ReleaseManifest:
    """Return the authoritative release manifest for this package."""
    return RELEASE


__all__ = [
    "ARTIFACT_SHA256",
    "FEATURE_SCHEMA_VERSION",
    "INPUT_NOTES",
    "MEASUREMENT_SIDES",
    "MODEL_CONTRACT_VERSION",
    "MODEL_ID",
    "MODEL_NAME",
    "MODEL_VERSION",
    "OPTIONAL_REQUEST_FIELDS",
    "PACKAGE_ID",
    "RELEASE",
    "REQUIRES_TARGET_SIDE",
    "REQUEST_FIELDS",
    "RUNTIME_DEPENDENCIES",
    "ReleaseManifest",
    "THRESHOLD_VALUE",
    "TOTAL_MEASUREMENTS",
    "WORKFLOW_ID",
    "release_manifest",
]
