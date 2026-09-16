"""Standard Model Result Contract v1 — canonical mapped result schema (PR0157).

A model-independent result envelope produced by the platform mapping boundary
(``bremen.api.model_result_mapper``) from an authoritative model runtime result
plus platform/source metadata.  It is defined by
``docs/standard_model_result_contract_v1.md`` and ADR-0018.

This is a representation contract, NOT model science:

- it owns no preprocessing, feature, estimator, threshold, or decision logic;
- it consumes already-produced model values (``bremen.api`` platform layer only);
- it must not import or depend on any individual model package's science.

The frozen dataclass mirrors the contract field order.  ``to_envelope_dict()``
emits the canonical JSON shape.  A frozen dataclass (not Pydantic) matches the
other ``api/*`` result/contract dataclasses; Pydantic is reserved for inbound
request models.  Absent optional source values follow the contract's explicit
absence convention (empty string for metadata strings, ``None`` for
numerically-absent patient age and unavailable release metrics) — never a
fabricated medical/patient value.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CONTRACT_VERSION = "standard_model_result.v1"

# Contract v1 canonical target-class risk vocabulary (exactly these two).
RISK_LEVEL_HIGH = "high"
RISK_LEVEL_LOW = "low"

# Canonical field order (top-level).  ``model_metrics`` is a nested object.
CANONICAL_FIELDS: tuple[str, ...] = (
    "report_id",
    "created_at",
    "analysis_author",
    "prediction_comment",
    "patient_id",
    "patient_age",
    "scan_date_time",
    "operator_id",
    "hardware_version",
    "eoscan_version",
    "model_name",
    "model_version",
    "model_method",
    "model_metrics",
    "threshold_value",
    "risk_probability",
    "target_class_risk_level",
    "specific_output",
)


@dataclass(frozen=True)
class StandardModelResult:
    """One stable mapped model result independent of the producing model.

    Field semantics and source ownership are documented in
    docs/standard_model_result_contract_v1.md and in the PR0157 metadata source
    map.  Every value here is an authoritative source value or an explicitly
    documented compatibility mapping; none is fabricated.
    """

    report_id: str = ""
    created_at: str = ""
    analysis_author: str = ""
    prediction_comment: str = ""
    patient_id: str = ""
    patient_age: int | float | None = None
    scan_date_time: str = ""
    operator_id: str = ""
    hardware_version: str = ""
    eoscan_version: str = ""
    model_name: str = ""
    model_version: str = ""
    model_method: str = ""
    model_metrics: dict[str, Any] = field(
        default_factory=lambda: {"sensitivity": None, "specificity": None}
    )
    threshold_value: float | None = None
    risk_probability: float | None = None
    target_class_risk_level: str = RISK_LEVEL_LOW
    specific_output: dict[str, Any] = field(default_factory=dict)

    def to_envelope_dict(self) -> dict[str, Any]:
        """Return the canonical contract-v1 JSON shape in stable field order."""
        metrics = {
            "sensitivity": self.model_metrics.get("sensitivity"),
            "specificity": self.model_metrics.get("specificity"),
        }
        return {
            "report_id": self.report_id,
            "created_at": self.created_at,
            "analysis_author": self.analysis_author,
            "prediction_comment": self.prediction_comment,
            "patient_id": self.patient_id,
            "patient_age": self.patient_age,
            "scan_date_time": self.scan_date_time,
            "operator_id": self.operator_id,
            "hardware_version": self.hardware_version,
            "eoscan_version": self.eoscan_version,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "model_method": self.model_method,
            "model_metrics": metrics,
            "threshold_value": self.threshold_value,
            "risk_probability": self.risk_probability,
            "target_class_risk_level": self.target_class_risk_level,
            "specific_output": dict(self.specific_output),
        }


__all__ = [
    "CANONICAL_FIELDS",
    "CONTRACT_VERSION",
    "RISK_LEVEL_HIGH",
    "RISK_LEVEL_LOW",
    "StandardModelResult",
]
