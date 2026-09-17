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
import re
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
    """Normalize acquisition syntax to seconds, preserving timezone knowledge.

    Offset-aware values retain their offset; naive values remain ISO8601 local
    wall times with unknown timezone (not strict RFC3339). No clock time or
    timezone is invented. Empty, date-only, and invalid values return ``""``.
    """
    if not isinstance(value, str) or not value.strip():
        return ""
    text = value.strip()
    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)?",
        text,
    ):
        return ""
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return ""
    # Strip fractional seconds only (timezone/offset preserved by isoformat()).
    normalized = parsed.replace(microsecond=0).isoformat()
    # RFC3339 -00:00 explicitly means unknown local offset, not known UTC.
    if text.endswith("-00:00"):
        return normalized[:-6] + "-00:00"
    return normalized


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


def _clean_age(value: Any) -> int | float | None:
    """Return a faithful numeric copy of a patient age, or ``None``.

    Preserves the numeric value exactly (integral values stay ``int``,
    non-integral values stay ``float``); booleans and non-numeric values are
    rejected so nothing is derived or fabricated.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return int(value) if value.is_integer() else float(value)
    return None


def _clean_eoscan_version(value: Any) -> str | None:
    """Return a stripped Eoscan version string, or ``None`` when absent.

    Explicit absence (``None``) is correct when no authoritative
    package-owned Eoscan version source exists; empty/whitespace values are
    treated as absent and are never promoted from unrelated producer
    provenance.  The mapper never interprets model-specific source fields.
    """
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _empty_metrics() -> dict[str, Any]:
    """Explicit absence fallback for model-release metrics.

    When the model-owned runtime result carries no authoritative
    sensitivity/specificity, both are reported as explicit absence (``None``)
    rather than fabricated.  When the runtime result DOES carry them (from the
    model package's own release/artifact metadata), the mapper copies those
    values verbatim (see ``_clean_metrics``).
    """
    return {"sensitivity": None, "specificity": None}


def _clean_metrics(value: Any) -> dict[str, Any]:
    """Copy authoritative model-owned metrics verbatim, or explicit absence.

    Consumes the metrics dict already transported by the model runtime result
    (never computed here).  Only numeric values are accepted; anything else
    falls back to explicit absence.
    """
    if not isinstance(value, dict):
        return _empty_metrics()
    return {
        "sensitivity": _clean_number(value.get("sensitivity")),
        "specificity": _clean_number(value.get("specificity")),
    }


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

    # PR0159: the five patient/acquisition metadata fields and the model
    # metadata/metrics arrive in the normalized runtime-result contract
    # (``source_metadata`` / ``model_metadata`` / ``model_metrics``) produced by
    # the model package's own adapter.  The mapper performs ONLY normalized
    # runtime result -> Standard Model Result; it never parses model-specific
    # container/artifact internals.  Absent values keep the contract's
    # explicit absence convention.
    source_metadata = result_summary.get("source_metadata")
    source_metadata = source_metadata if isinstance(source_metadata, dict) else {}
    model_metadata = result_summary.get("model_metadata")
    model_metadata = model_metadata if isinstance(model_metadata, dict) else {}

    return StandardModelResult(
        report_id=_clean_str(report_id),
        created_at=normalize_timestamp(created_at),
        analysis_author=_clean_str(context.get("analysis_author")),
        prediction_comment=_clean_str(context.get("prediction_comment")),
        patient_id=_clean_str(context.get("patient_id")),
        patient_age=_clean_age(source_metadata.get("patient_age")),
        referring_physician=_clean_str(source_metadata.get("referring_physician")),
        scan_date_time=normalize_timestamp(source_metadata.get("scan_date_time")),
        operator_id=_clean_str(source_metadata.get("operator_id")),
        hardware_version=_clean_str(source_metadata.get("hardware_version")),
        eoscan_version=_clean_eoscan_version(source_metadata.get("eoscan_version")),
        model_name=_bremen_manifest.MODEL_NAME,   # authoritative package identity
        model_version=model_version,
        model_method=(
            _clean_str(model_metadata.get("model_method"))
            or _model_method(model_version)
        ),
        model_metrics=_clean_metrics(result_summary.get("model_metrics")),
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

    # PR0159: the five patient/acquisition metadata fields and the model
    # metadata/metrics arrive in the normalized runtime-result contract
    # (``source_metadata`` / ``model_metadata`` / ``model_metrics``) produced by
    # the model package's own adapter.  The mapper performs ONLY normalized
    # runtime result -> Standard Model Result; it never parses model-specific
    # container/artifact internals.  Absent values keep the contract's
    # explicit absence convention.
    source_metadata = result_summary.get("source_metadata")
    source_metadata = source_metadata if isinstance(source_metadata, dict) else {}
    model_metadata = result_summary.get("model_metadata")
    model_metadata = model_metadata if isinstance(model_metadata, dict) else {}

    return StandardModelResult(
        report_id=_clean_str(report_id),
        created_at=normalize_timestamp(created_at),
        analysis_author=_clean_str(context.get("analysis_author")),
        prediction_comment=_clean_str(context.get("prediction_comment")),
        patient_id=_clean_str(context.get("patient_id")),
        patient_age=_clean_age(source_metadata.get("patient_age")),
        referring_physician=_clean_str(source_metadata.get("referring_physician")),
        scan_date_time=normalize_timestamp(source_metadata.get("scan_date_time")),
        operator_id=_clean_str(source_metadata.get("operator_id")),
        hardware_version=_clean_str(source_metadata.get("hardware_version")),
        eoscan_version=_clean_eoscan_version(source_metadata.get("eoscan_version")),
        model_name=model_name,            # authoritative artifact/release identity
        model_version=model_version,
        model_method=(
            _clean_str(model_metadata.get("model_method"))
            or _model_method(model_version)
        ),
        model_metrics=_clean_metrics(result_summary.get("model_metrics")),
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
