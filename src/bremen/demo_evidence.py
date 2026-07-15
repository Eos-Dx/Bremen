"""Bremen product demo evidence pack.

Provides deterministic synthetic payloads, evidence bundle structures,
and validation helpers for Bremen product demos and operator smoke checks.

This module is safe to import anywhere — no model loading, no network
calls, no H5 reads, no clinical data.

All outputs include ``technical_demo_only: True`` and the Bremen product
identity disclaimer.

Standard-library only — no third-party dependencies.
"""

from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEMO_EVIDENCE_VERSION = "v0.1"
DEMO_SCENARIO_ID = "bremen_demo_v1"
BREMEN_PRODUCT_NAME = "Bremen"
BREMEN_PRODUCT_QUESTION = "Should patient continue to MRI?"
BREMEN_DEMO_DISCLAIMER = (
    "This is a technical product demo of Bremen's controlled "
    "decision-support workflow. It is not a clinical result. "
    "It is not clinically validated. It does not replace MRI, "
    "biopsy, a radiologist, a clinician, or clinical judgment."
)

# Feature artifact schema constants — must match feature_artifacts.py.
# Imported lazily inside build_demo_feature_artifact_payload to avoid
# import-time coupling.
_FEATURE_ARTIFACT_SCHEMA_VERSION = "bremen.feature_artifact.v0.1"
_FEATURE_ARTIFACT_KIND = "bremen.precomputed_features"

# Required feature columns — duplicated intentionally to keep this module
# independent from the H5 preprocessing bridge.
_REQUIRED_FEATURE_COLUMNS: tuple[str, ...] = (
    "weightedrms1",
    "sigma_l1",
    "sigma_r1",
    "mahalanobis1",
    "weightedrms2",
    "sigma_l2",
    "sigma_r2",
    "mahalanobis2",
    "peak14_intensity",
    "mean_peak_value_raw",
    "wasserstein_distance_muLR",
    "cosine_distance_full_q2",
    "wasserstein_distance_full_q2",
    "meanrms1",
    "meanrms2",
)

# Deterministic synthetic feature values chosen to produce a stable,
# known prediction with the built-in synthetic model (coef=[0.1]*15,
# intercept=0.0, threshold=0.5).  Target: p_mri_needed ≈ 0.62 (above
# threshold → MRI_RECOMMENDED), verified by test.
_DEMO_FEATURE_VALUES: tuple[float, ...] = (
    0.33, 0.33, 0.32, 0.33, 0.33,
    0.32, 0.33, 0.33, 0.32, 0.33,
    0.32, 0.33, 0.33, 0.32, 0.33,
)

# Total sum ≈ 4.90 → logit ≈ 0.49 → p ≈ 0.620

# Default safety notes in every evidence bundle
_DEFAULT_SAFETY_NOTES: list[str] = [
    "Technical product demo only — not a clinical result.",
    "Not clinically validated.",
    "Does not replace MRI, biopsy, radiologist, clinician, or clinical judgment.",
    "All clinical decisions must be made by qualified clinicians.",
]

# ---------------------------------------------------------------------------
# Forbidden-pattern checks used by validation
# ---------------------------------------------------------------------------

# Prohibited Aramis-related strings (case-insensitive match)
_ARAMIS_PATTERNS: tuple[str, ...] = (
    "aramis",
    "m2q",
    "benign vs cancer",
    "benign and cancer",
)

# Prohibited clinical/replacement language (case-insensitive match)
_CLINICAL_REPLACEMENT_PATTERNS: tuple[str, ...] = (
    "diagnosis",
    "diagnose",
    "replaces mri",
    "replace mri",
    "replaces biopsy",
    "replace biopsy",
    "replaces radiologist",
    "replace radiologist",
    "replaces clinician",
    "replace clinician",
)


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def build_demo_feature_artifact_payload() -> dict[str, Any]:
    """Build a deterministic synthetic Bremen feature artifact payload.

    Returns a dict conforming to the ``bremen.feature_artifact.v0.1``
    schema.  The payload contains exactly 15 feature columns with stable
    synthetic values suitable for the built-in synthetic model.

    No real patient data, no H5 reads, no model loading, no network calls.

    Returns
    -------
    A dict with keys: ``schema_version``, ``artifact_kind``,
    ``feature_columns``, ``feature_values``, ``metadata``.
    The ``metadata`` sub-dict contains safe synthetic provenance fields
    only.
    """
    return {
        "schema_version": _FEATURE_ARTIFACT_SCHEMA_VERSION,
        "artifact_kind": _FEATURE_ARTIFACT_KIND,
        "feature_columns": list(_REQUIRED_FEATURE_COLUMNS),
        "feature_values": list(_DEMO_FEATURE_VALUES),
        "metadata": {
            "preprocessing_source": "demo_evidence_pack",
            "source_package_version": DEMO_EVIDENCE_VERSION,
            "configuration_label": "technical_demo_only",
        },
    }


def build_demo_evidence_bundle(
    *,
    base_url: str | None = None,
    request_id: str | None = None,
    job_id: str | None = None,
    model_status: str | None = None,
    model_version: str | None = None,
    feature_schema_version: str | None = None,
    prediction_status: str | None = None,
    decision_support: dict[str, Any] | None = None,
    checks: dict[str, str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build a Bremen demo evidence bundle.

    All outputs include ``technical_demo_only: True``, the Bremen
    product identity, product question, disclaimer, scenario
    metadata, and safety notes.

    Optional fields are included only when their value is not ``None``.

    Parameters
    ----------
    base_url : Base URL of the Bremen HTTP service.
    request_id : Request ID used for this demo run.
    job_id : Prediction job ID (if a prediction was submitted).
    model_status : Model readiness status (e.g. ``"ready"``).
    model_version : Model version string.
    feature_schema_version : Feature schema version string.
    prediction_status : Prediction job status (e.g. ``"completed"``).
    decision_support : Decision-support report dict from a completed
        prediction result.
    checks : Dict of check name → ``"pass"`` / ``"fail"``.
    warnings : List of warning strings.

    Returns
    -------
    A dict with mandatory fields always present and optional fields
    included when their corresponding parameter is not ``None``.
    """
    bundle: dict[str, Any] = {
        "technical_demo_only": True,
        "product": BREMEN_PRODUCT_NAME,
        "product_question": BREMEN_PRODUCT_QUESTION,
        "disclaimer": BREMEN_DEMO_DISCLAIMER,
        "evidence_version": DEMO_EVIDENCE_VERSION,
        "scenario_id": DEMO_SCENARIO_ID,
        "safety_notes": list(_DEFAULT_SAFETY_NOTES),
    }

    # Optional fields — only included when provided
    if base_url is not None:
        bundle["base_url"] = base_url
    if request_id is not None:
        bundle["request_id"] = request_id
    if job_id is not None:
        bundle["job_id"] = job_id
    if model_status is not None:
        bundle["model_status"] = model_status
    if model_version is not None:
        bundle["model_version"] = model_version
    if feature_schema_version is not None:
        bundle["feature_schema_version"] = feature_schema_version
    if prediction_status is not None:
        bundle["prediction_status"] = prediction_status
    if decision_support is not None:
        bundle["decision_support"] = decision_support
    if checks is not None:
        bundle["checks"] = checks
    if warnings is not None:
        bundle["warnings"] = list(warnings)

    return bundle


def validate_demo_evidence_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Validate a demo evidence bundle dict.

    Checks:

    - ``technical_demo_only`` is ``True``.
    - ``product`` is ``"Bremen"``.
    - ``product_question`` is the expected string.
    - ``evidence_version`` is a non-empty string.
    - ``scenario_id`` is a non-empty string.
    - ``safety_notes`` is a non-empty list of strings.
    - ``disclaimer`` is a non-empty string.
    - No Aramis references in any field value.
    - No clinical diagnosis or replacement language in any
      field value.

    Parameters
    ----------
    bundle : Evidence bundle dict to validate.

    Returns
    -------
    The validated bundle dict (pass-through).

    Raises
    ------
    ValueError
        If any validation rule fails.
    """
    if not isinstance(bundle, dict):
        raise ValueError("Evidence bundle must be a dict")

    # Required boolean fields
    if bundle.get("technical_demo_only") is not True:
        raise ValueError(
            "technical_demo_only must be True"
        )

    # Required string fields with product identity
    _check_field(bundle, "product", BREMEN_PRODUCT_NAME)
    _check_field(bundle, "product_question", BREMEN_PRODUCT_QUESTION)

    # Required non-empty string fields
    for field in ("evidence_version", "scenario_id", "disclaimer"):
        val = bundle.get(field)
        if not isinstance(val, str) or not val:
            raise ValueError(f"{field} must be a non-empty string")

    # safety_notes must be a non-empty list of strings
    notes = bundle.get("safety_notes")
    if not isinstance(notes, list) or len(notes) == 0:
        raise ValueError("safety_notes must be a non-empty list")
    for i, note in enumerate(notes):
        if not isinstance(note, str):
            raise ValueError(
                f"safety_notes[{i}] must be a string"
            )

    # Scan all string values for forbidden patterns
    _check_no_aramis_references(bundle)
    _check_no_clinical_replacement_language(bundle)

    return bundle


# ---------------------------------------------------------------------------
# JSON serialisation helper
# ---------------------------------------------------------------------------


def json_dumps_evidence_bundle(bundle: dict[str, Any]) -> str:
    """Serialize an evidence bundle to a JSON string.

    Validates the bundle first.

    Parameters
    ----------
    bundle : Evidence bundle dict.

    Returns
    -------
    JSON-encoded string.

    Raises
    ------
    ValueError
        If validation fails.
    TypeError
        If the bundle is not JSON-serializable.
    """
    validate_demo_evidence_bundle(bundle)
    return json.dumps(bundle, indent=2, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_field(
    bundle: dict[str, Any], field: str, expected: str
) -> None:
    """Check that *bundle*[*field*] equals *expected*."""
    actual = bundle.get(field)
    if actual != expected:
        raise ValueError(
            f"{field} must be {expected!r}, got {actual!r}"
        )


def _check_no_aramis_references(bundle: dict[str, Any]) -> None:
    """Scan all string values in *bundle* for Aramis references.

    Raises ``ValueError`` on the first match found.
    """
    for key, value in _iter_flat_strs(bundle):
        value_lower = value.lower()
        for pattern in _ARAMIS_PATTERNS:
            if pattern in value_lower:
                raise ValueError(
                    f"Evidence bundle contains prohibited "
                    f"Aramis-related string {pattern!r} "
                    f"in field {key!r}"
                )


def _check_no_clinical_replacement_language(
    bundle: dict[str, Any],
) -> None:
    """Scan all string values in *bundle* for clinical/replacement language.

    Skips the ``disclaimer`` and ``safety_notes`` fields — these are intended
    to contain safe negation language (e.g. "does not replace MRI").

    Raises ``ValueError`` on the first match found.
    """
    for key, value in _iter_flat_strs(bundle):
        # disclaimer and safety_notes intentionally contain safe negation
        # language — skip these fields during clinical/replacement scan.
        if key == "disclaimer" or key.startswith("safety_notes"):
            continue
        value_lower = value.lower()
        for pattern in _CLINICAL_REPLACEMENT_PATTERNS:
            if pattern in value_lower:
                raise ValueError(
                    f"Evidence bundle contains prohibited "
                    f"clinical/replacement language {pattern!r} "
                    f"in field {key!r}"
                )


def _iter_flat_strs(obj: Any, prefix: str = ""):
    """Yield ``(key_path, str_value)`` for every string in *obj*.

    Recurses into dict values and list items.
    """
    if isinstance(obj, dict):
        for key, val in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(val, str):
                yield path, val
            elif isinstance(val, (dict, list)):
                yield from _iter_flat_strs(val, path)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            path = f"{prefix}[{i}]"
            if isinstance(item, str):
                yield path, item
            elif isinstance(item, (dict, list)):
                yield from _iter_flat_strs(item, path)
