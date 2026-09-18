"""Aramina v0.2.13 package-owned metadata adapter (PR0159).

Each model package owns the interpretation of ITS OWN container/artifact
metadata.  This module is the Aramina package's adapter: it reads the Aramina
container's authoritative patient/acquisition fields plus the ACTIVE artifact's
model-type and held-out evaluation metrics, and maps them to the shared
normalized contract (``bremen.contracts.model_runtime.SourceMetadata`` /
``ModelMetadata`` / ``ModelMetrics``).

The platform (orchestrator, providers, job layer, Standard Result mapper)
depends only on the normalized names; it never sees Aramina-specific source
field names, artifact paths, preprocessing dataframe columns, or pickle/joblib
structure.

Authoritative Aramina container sources (xrd-session layout):

- ``/session/sample.attrs[\"age\"]``              -> ``source_metadata.patient_age``
  (when the model-owned preprocessing frame provides no usable age)
- ``/session.attrs[\"started_at\"]``              -> ``source_metadata.scan_date_time`` (raw; mapper normalizes)
- ``/session.attrs[\"operator_username\"]``       -> ``source_metadata.operator_id`` (verbatim)
- ``/session/sets/<set>/metadata`` JSON
  ``backfill_provenance.human1_version``        -> ``source_metadata.hardware_version``
  (deterministic consensus across the participating sets)

``eoscan_version`` has NO authoritative source in the current Aramina
container/artifact contract.  In particular ``/session.attrs["producer_version"]``
is NOT mapped to ``eoscan_version``: observed provenance
(``producer_software = "omniscan-backfill"``, ``producer_version = "0.1.0"``)
shows the producer is the omniscan backfill pipeline, not the Eoscan
acquisition software, so the attribute is not semantically Eoscan version.
The adapter therefore returns ``eoscan_version=None`` (explicit absence),
never a promoted alias.

Authoritative Aramina artifact sources (the ACTIVE selected artifact):

- artifact top-level ``model_type``               -> ``model_metadata.model_method``
- ``model_performance.held_out_metrics.sensitivity.mean`` /
  ``model_performance.held_out_metrics.specificity.mean``
                                                  -> ``model_metrics.*``
  (held-out evaluation of the exact active artifact; nothing is hardcoded from
  another version such as 0.2.12)

The adapter is fault-tolerant: missing/malformed metadata yields the explicit
absence value and never raises, so existing normalization/inference/QC
behavior is untouched.  No value is ever fabricated.
"""
from __future__ import annotations

import json
import math
import numbers
from typing import Any

from bremen.contracts.model_runtime import (
    ModelMetadata,
    ModelMetrics,
    SourceMetadata,
)


def extract_source_metadata(
    h5_path: str, *, frame_age: int | float | None = None,
) -> SourceMetadata:
    """Extract the Aramina container's canonical source metadata.

    ``frame_age`` is the model-owned preprocessing output's median patient age
    (used verbatim when the frame provides one); the container attribute is the
    fallback.  Fault-tolerant by design: any read/parse failure leaves the
    affected canonical field at its explicit absence default.
    """
    result = SourceMetadata()
    if not h5_path:
        return result
    try:
        import h5py  # noqa: PLC0415 -- lazy; keeps the package entry import light

        with h5py.File(h5_path, "r") as h5_file:
            age = frame_age if frame_age is not None else _read_sample_age(h5_file)
            result = SourceMetadata(
                patient_age=_to_number(age) if age is not None else None,
                scan_date_time=_read_session_attr_str(h5_file, "started_at"),
                operator_id=_read_session_attr_str(h5_file, "operator_username"),
                hardware_version=_resolve_hardware_version(h5_file),
                # No authoritative package-owned Eoscan version source exists
                # for the current Aramina container/artifact contract;
                # producer_version is omniscan-backfill provenance, NOT
                # eoscan_version.  Explicit absence (None) is correct.
                eoscan_version=None,
            )
    except Exception:
        # Optional metadata must never break a run.
        pass
    return result


def extract_model_metadata(package: Any) -> ModelMetadata:
    """Map the active Aramina artifact's model-type/inference-method field."""
    model_type = package.get("model_type") if isinstance(package, dict) else None
    if isinstance(model_type, str) and model_type.strip():
        return ModelMetadata(model_method=model_type.strip())
    return ModelMetadata()


def extract_model_metrics(package: Any) -> ModelMetrics:
    """Map the ACTIVE Aramina artifact's held-out metrics verbatim.

    Reads ``model_performance.held_out_metrics.sensitivity.mean`` /
    ``specificity.mean`` from the exact active package.  Absent or non-numeric
    values stay ``None`` (never a hardcoded constant from another version).
    """
    performance = package.get("model_performance") if isinstance(package, dict) else None
    if not isinstance(performance, dict):
        return ModelMetrics()
    held_out = performance.get("held_out_metrics")
    if not isinstance(held_out, dict):
        return ModelMetrics()
    sensitivity = _metric_mean(held_out.get("sensitivity"))
    specificity = _metric_mean(held_out.get("specificity"))
    return ModelMetrics(sensitivity=sensitivity, specificity=specificity)


# ---------------------------------------------------------------------------
# Internal readers (Aramina container contract)
# ---------------------------------------------------------------------------


def _metric_mean(entry: Any) -> float | None:
    if not isinstance(entry, dict):
        return None
    return _to_float(entry.get("mean"))


def _read_sample_age(h5_file: Any) -> int | float | None:
    try:
        raw = h5_file["/session/sample"].attrs.get("age")
    except Exception:
        return None
    return _to_number(raw)


def _read_session_attr_str(h5_file: Any, name: str) -> str:
    """Read a ``/session`` attribute as a stripped string, or ``""``."""
    try:
        raw = h5_file["/session"].attrs.get(name)
    except Exception:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace").strip()
    if isinstance(raw, str):
        return raw.strip()
    return ""


def _resolve_hardware_version(h5_file: Any) -> str:
    """Resolve hardware_version from the measurement-set metadata consensus."""
    values: set[str] = set()
    try:
        sets_group = h5_file["/session/sets"]
    except Exception:
        return ""
    for key in sets_group.keys():
        version = _read_set_human1_version(sets_group[key])
        if version:
            values.add(version)
    if len(values) == 1:
        return next(iter(values))
    return ""


def _read_set_human1_version(set_group: Any) -> str:
    """Read one set group's ``metadata`` JSON ``human1_version`` (or ``""``)."""
    try:
        if "metadata" not in set_group:
            return ""
        raw = set_group["metadata"][()]
        if isinstance(raw, bytes):
            text = raw.decode("utf-8")
        elif isinstance(raw, str):
            text = raw
        else:
            return ""
        data = json.loads(text)
        provenance = data.get("backfill_provenance") if isinstance(data, dict) else None
        version = provenance.get("human1_version") if isinstance(provenance, dict) else None
        if isinstance(version, str) and version.strip():
            return version.strip()
    except Exception:
        pass
    return ""


def _to_number(value: Any) -> int | float | None:
    """Normalize a real numeric value to ``int``/``float``; reject everything else."""
    if isinstance(value, bool) or value is None:
        return None
    if not isinstance(value, numbers.Real):
        return None
    as_float = float(value)
    if not math.isfinite(as_float):
        return None
    return int(as_float) if as_float.is_integer() else as_float


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        return None
    as_float = float(value)
    if not math.isfinite(as_float):
        return None
    return as_float


__all__ = [
    "extract_model_metadata",
    "extract_model_metrics",
    "extract_source_metadata",
]
