"""Standard Model Result Mapper v1 — platform integration boundary (PR0157).

One authoritative boundary that maps an **already-produced** model runtime
result into the model-independent Standard Model Result Contract v1
(``bremen.api.standard_model_result.StandardModelResult``), per
docs/standard_model_result_contract_v1.md and ADR-0018.

Model packages remain authoritative for science: this module consumes the
runtime result and release manifest only.  It performs NO preprocessing,
feature generation, estimator execution, threshold application, coefficient
inspection, or probability/decision recomputation, and it never hardcodes a
threshold or fabricates metrics, authors, timestamps, or patient values.

Allowed mapping operations (per the contract): normalize field names, normalize
timestamp representation, translate the model-native probability field to
``risk_probability``, translate the authoritative model decision to the canonical
``high``/``low`` vocabulary, assemble platform/source/release metadata, and build
``specific_output``.

Dispatch is by ``workflow_id``; the only model-specific code here is which
authoritative field to read.  Absent source values follow the contract's explicit
absence convention (empty string / ``None``) and are never invented.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from bremen.api.standard_model_result import (
    RISK_LEVEL_HIGH,
    RISK_LEVEL_LOW,
    StandardModelResult,
)
# Release identity is read from the authoritative model-package manifests
# (platform -> package direction; the packages do not import this module).
from bremen.model_packages.bremen_v01 import manifest as _bremen_manifest
from bremen.model_packages.aramina_v0213 import manifest as _aramina_manifest


# ---------------------------------------------------------------------------
# Shared mapping helpers (single implementations; no per-route duplication)
# ---------------------------------------------------------------------------


def normalize_timestamp(value: Any) -> str:
    """Return an RFC3339-compatible string: timezone preserved, no fractional seconds.

    Preserves the source instant; never coerces a naive value to local time and
    never invents a timezone.  Returns ``""`` for empty/unparseable input.
    """
    if not isinstance(value, str) or not value.strip():
        return ""
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return ""
    # Strip fractional seconds only (timezone/offset preserved by isoformat()).
    return parsed.replace(microsecond=0).isoformat()


def _model_method(model_version: str) -> str:
    """Compatibility mapping: for current releases ``model_method`` == ``model_version``.

    Single documented rule so no provider duplicates an independent method value.
    """
    return model_version


def _risk_level(positive: Any, *, probability: Any = None, threshold: Any = None) -> str:
    """Translate the authoritative model decision to canonical ``high``/``low``.

    Prefers the model-owned positive decision (0/1 or bool).  Only if it is
    absent does it reproduce the model semantics exactly using the model-owned
    probability and threshold (``probability >= threshold`` — the same operator
    the package predictor applied).  It never introduces an independent
    threshold or a new decision rule.
    """
    if isinstance(positive, bool):
        return RISK_LEVEL_HIGH if positive else RISK_LEVEL_LOW
    if isinstance(positive, int) and positive in (0, 1):
        return RISK_LEVEL_HIGH if positive == 1 else RISK_LEVEL_LOW
    # Fallback: reproduce model-owned comparison with model-owned values only.
    if isinstance(probability, (int, float)) and isinstance(threshold, (int, float)):
        return RISK_LEVEL_HIGH if probability >= threshold else RISK_LEVEL_LOW
    return RISK_LEVEL_LOW


def _clean_str(value: Any) -> str:
    """Return a stripped string or "" — never a fabricated value."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def _clean_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _empty_metrics() -> dict[str, Any]:
    """Release metrics are model-release metadata, never per-patient values.

    No authoritative sensitivity/specificity exists in the current
    Bremen/Aramina release metadata, so both are reported as explicit absence
    (``None``) rather than fabricated.  If a future authoritative release
    source provides them, they should be threaded through here (see
    docs/standard_model_result_contract_v1.md "Model metrics ownership").
    """
    return {"sensitivity": None, "specificity": None}


# ---------------------------------------------------------------------------
# Bremen mapping
# ---------------------------------------------------------------------------


def map_bremen_result(
    result_summary: dict[str, Any],
    *,
    model_identity: dict[str, Any] | None = None,
    job_context: dict[str, Any] | None = None,
    report_id: str = "",
    created_at: Any = "",
) -> StandardModelResult | None:
    """Map an authoritative Bremen runtime result into the common contract.

    Consumes the model-owned ``probability`` / ``threshold_applied`` /
    ``prediction``; recomputes nothing.  Bremen ``specific_output`` is empty per
    the contract.  Returns ``None`` when the result is not a valid scientific
    outcome (nothing to map), so the caller leaves the report unchanged.
    """
    if not isinstance(result_summary, dict):
        return None
    probability = _clean_number(result_summary.get("probability"))
    threshold = _clean_number(result_summary.get("threshold_applied"))
    if probability is None or threshold is None:
        return None  # not a completed scientific result — do not map

    identity = model_identity or {}
    context = job_context or {}

    model_version = (
        _clean_str(result_summary.get("model_version"))
        or _clean_str(identity.get("model_version"))
        or _bremen_manifest.MODEL_VERSION
    )

    return StandardModelResult(
        report_id=_clean_str(report_id),
        created_at=normalize_timestamp(created_at),
        analysis_author=_clean_str(context.get("analysis_author")),
        prediction_comment=_clean_str(context.get("prediction_comment")),
        patient_id=_clean_str(context.get("patient_id")),
        patient_age=None,                 # not present in Bremen report metadata
        scan_date_time="",                # not present — do not fabricate
        operator_id="",
        hardware_version="",
        eoscan_version="",
        model_name=_bremen_manifest.MODEL_NAME,   # authoritative package identity
        model_version=model_version,
        model_method=_model_method(model_version),
        model_metrics=_empty_metrics(),
        threshold_value=threshold,
        risk_probability=probability,     # authoritative; not recalculated
        target_class_risk_level=_risk_level(
            result_summary.get("prediction"),
            probability=probability, threshold=threshold,
        ),
        specific_output={},               # contract: Bremen has none
    )


# ---------------------------------------------------------------------------
# Aramina mapping
# ---------------------------------------------------------------------------

ARAMINA_MAMMOGRAPHY_FIELD = "mammography_suspicious_field"


def map_aramina_result(
    result_summary: dict[str, Any],
    *,
    model_identity: dict[str, Any] | None = None,
    job_context: dict[str, Any] | None = None,
    report_id: str = "",
    created_at: Any = "",
) -> StandardModelResult | None:
    """Map an authoritative Aramina runtime result into the common contract.

    Consumes the model-native ``external_report`` numbers verbatim
    (``risk_probability`` / ``decision_threshold`` / ``target_class_risk_level``);
    recomputes nothing.  ``target_side`` moves under ``specific_output`` with the
    same semantics; ``mammography_suspicious_field`` is an empty string because
    the current Aramina result provides no such value (never fabricated).
    Returns ``None`` when there is no valid model-native result to map.
    """
    if not isinstance(result_summary, dict):
        return None
    external = result_summary.get("external_report")
    if not isinstance(external, dict):
        return None
    probability = _clean_number(external.get("risk_probability"))
    threshold = _clean_number(external.get("decision_threshold"))
    if probability is None or threshold is None:
        return None  # not a completed scientific result — do not map

    identity = model_identity or {}
    context = job_context or {}

    model_version = (
        _clean_str(external.get("model_version"))
        or _clean_str(result_summary.get("model_version"))
        or _clean_str(identity.get("model_version"))
        or _aramina_manifest.MODEL_VERSION
    )
    model_name = (
        _clean_str(external.get("model_name"))
        or _aramina_manifest.MODEL_NAME
    )

    target_side = _clean_str(external.get("target_side"))
    if target_side not in {"left", "right"}:
        # Fall back to the sanitized request side; only an allowlisted value.
        candidate = _clean_str(context.get("target_side"))
        target_side = candidate if candidate in {"left", "right"} else ""

    return StandardModelResult(
        report_id=_clean_str(report_id),
        created_at=normalize_timestamp(created_at),
        analysis_author=_clean_str(context.get("analysis_author")),
        prediction_comment=_clean_str(context.get("prediction_comment")),
        patient_id=_clean_str(context.get("patient_id")),
        patient_age=None,                 # not exposed in report metadata; do not re-derive
        scan_date_time="",                # not present — do not fabricate
        operator_id="",
        hardware_version="",
        eoscan_version="",
        model_name=model_name,            # authoritative artifact/release identity
        model_version=model_version,
        model_method=_model_method(model_version),
        model_metrics=_empty_metrics(),
        threshold_value=threshold,
        risk_probability=probability,     # authoritative; not recalculated
        target_class_risk_level=_risk_level(
            external.get("target_class_risk_level"),
            probability=probability, threshold=threshold,
        ),
        specific_output={
            "target_side": target_side,
            ARAMINA_MAMMOGRAPHY_FIELD: "",
        },
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_MAPPERS = {
    "bremen": map_bremen_result,
    "aramina": map_aramina_result,
}


def build_standard_result(
    workflow_id: str,
    result_summary: dict[str, Any] | None,
    *,
    model_identity: dict[str, Any] | None = None,
    job_context: dict[str, Any] | None = None,
    report_id: str = "",
    created_at: Any = "",
) -> dict[str, Any] | None:
    """Map a completed workflow result to the Standard Model Result v1 dict.

    Returns ``None`` for unknown workflows or when there is no valid scientific
    result to map, so the caller leaves the existing report contract unchanged.
    """
    if result_summary is None:
        return None
    mapper = _MAPPERS.get(workflow_id)
    if mapper is None:
        return None
    mapped = mapper(
        result_summary,
        model_identity=model_identity,
        job_context=job_context,
        report_id=report_id,
        created_at=created_at,
    )
    return mapped.to_envelope_dict() if mapped is not None else None


__all__ = [
    "ARAMINA_MAMMOGRAPHY_FIELD",
    "build_standard_result",
    "map_aramina_result",
    "map_bremen_result",
    "normalize_timestamp",
]
