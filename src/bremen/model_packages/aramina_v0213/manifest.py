"""Aramina v0.2.13 release manifest — model-owned identity and input contract.

PR0156 authoritative package source for the Aramina model's static release
contract: workflow identity, artifact type/kind, allowed preprocessing releases,
expected final-model feature columns, and the model-declared input contract
(request fields, explicit ``target_side`` semantics, allowed sides).

Per-deployment model identity (``model_id`` / ``model_version`` /
``feature_schema_version``) continues to be supplied by the platform registry
entry at runtime (public model IDs and routing are unchanged); this manifest
owns the *contract* and the *reference release* identity/provenance used for
package-level direct execution and golden evidence.

This is model-package metadata, not an artifact-directory manifest (see
``bremen.model_package``). It declares no scientific computation and imports
nothing from the platform.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Artifact contract identity
# ---------------------------------------------------------------------------

ARTIFACT_TYPE = "aramina.joblib.model_package"
ARTIFACT_KIND = "aramina_training_artifact"
WORKFLOW_ID = "aramina"
DEFAULT_AUTHOR = "Bremen Platform"

# Reference release identity (production Aramina model). Public per-selection
# identity is still resolved from the registry entry; these constants are the
# package's authoritative reference release for direct/golden execution.
MODEL_ID = "aramina-target-brest-risk"
MODEL_NAME = "aramina_target_breast_risk"
MODEL_VERSION = "0.2.13-beta"
FEATURE_SCHEMA_VERSION = "v0.1"

# Expected feature columns for the final model in the real artifact. The
# artifact's model_info.feature_columns must be a superset of these.
FINAL_FEATURE_COLUMNS = (
    "profile_p_cancer_logit_average",
    "age",
    "age_available",
    "sk_wasserstein_distance_full_q2",
    "sk_weightedrms1",
    "sk_weightedrms2",
    "sk_mean_peak_value_abs_delta",
    "symmetry_available",
)

# Allowlisted preprocessing release tags (never arbitrary artifact values).
ALLOWED_PREPROCESSING_RELEASES = frozenset({"v0.1.7-beta", "v0.1.9-beta"})

# ---------------------------------------------------------------------------
# Model-declared input contract (requirements ownership)
# ---------------------------------------------------------------------------
# These match the existing public requirements defaults exactly; target_side
# remains explicit and required.

REQUEST_FIELDS = ("container_id", "source_id", "patient_id", "target_side")
OPTIONAL_REQUEST_FIELDS = ("analysis_author", "prediction_comment")
ALLOWED_TARGET_SIDES = ("left", "right")
REQUIRES_TARGET_SIDE = True
MEASUREMENT_SIDES: tuple[tuple[str, int], ...] = ()  # no fixed per-side count
TOTAL_MEASUREMENTS = None

INPUT_NOTES = (
    "Aramina requires an explicit target_side (left or right).",
    "Preprocessing is artifact-owned and release-gated.",
)

# ---------------------------------------------------------------------------
# Scientific runtime dependencies (for PR0155/packaging capture)
# ---------------------------------------------------------------------------

RUNTIME_DEPENDENCIES = ("numpy", "pandas", "scipy", "scikit-learn", "pyyaml")

# Historical module-level alias retained for the transitional re-export
# surface (api/workflow_aramina.py imports ``_ARTIFACT_KIND``).
_ARTIFACT_KIND = ARTIFACT_KIND
_DEFAULT_AUTHOR = DEFAULT_AUTHOR
_FINAL_FEATURE_COLUMNS = FINAL_FEATURE_COLUMNS
_ALLOWED_PREPROCESSING_RELEASES = ALLOWED_PREPROCESSING_RELEASES


__all__ = [
    "ALLOWED_PREPROCESSING_RELEASES",
    "ALLOWED_TARGET_SIDES",
    "ARTIFACT_KIND",
    "ARTIFACT_TYPE",
    "DEFAULT_AUTHOR",
    "FEATURE_SCHEMA_VERSION",
    "FINAL_FEATURE_COLUMNS",
    "INPUT_NOTES",
    "MEASUREMENT_SIDES",
    "MODEL_ID",
    "MODEL_NAME",
    "MODEL_VERSION",
    "OPTIONAL_REQUEST_FIELDS",
    "REQUEST_FIELDS",
    "REQUIRES_TARGET_SIDE",
    "RUNTIME_DEPENDENCIES",
    "TOTAL_MEASUREMENTS",
    "WORKFLOW_ID",
    "_ARTIFACT_KIND",
    "_ALLOWED_PREPROCESSING_RELEASES",
    "_DEFAULT_AUTHOR",
    "_FINAL_FEATURE_COLUMNS",
]
