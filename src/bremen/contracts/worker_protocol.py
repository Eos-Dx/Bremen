"""Worker protocol v1 (``bremen.worker.v1``) — IR-02 contract foundations.

Defines the file-based wire protocol between the platform Harness and a
release Worker process, per ``docs/inference-releases/architecture-and-contract.md``:
the Harness stages ``request.json`` + ``input.h5`` for one invocation; the
Worker writes ``result.json`` on completion. stdout/stderr carry diagnostics
only and are never parsed as a result channel.

This module implements contract validation and JSON codecs only. It does
not spawn, supervise, or communicate with any real subprocess (no process
supervision, no installation, no activation — see IR-02 PLAN and the
coder task's NON-GOALS).

Dependency direction (enforced by
``tests/test_worker_protocol_contract.py``): this module must not import
``bremen.platform``, ``bremen.model_packages``, ``boto3``, ``fastapi``, or any
model-specific scientific implementation. It may import sibling contract
modules (``bremen.contracts.model_runtime``) because those are the
transport-neutral dataclasses this module provides JSON codecs for.

No pickle/joblib ever crosses this boundary: every payload here is validated
to be JSON-safe (str/bool/int/finite-float/None/list/dict-with-string-keys)
before it is accepted or encoded.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from bremen.contracts.model_runtime import (
    CONTRACT_VERSION,
    ModelMetadata,
    ModelMetrics,
    ModelRequirements,
    ModelValidation,
    RuntimePrediction,
    SourceMetadata,
)

__all__ = [
    "ALLOWED_ERROR_CODES",
    "ALLOWED_OPERATIONS",
    "ALLOWED_RESULT_STATUSES",
    "ALLOWED_TARGET_SIDES",
    "ERROR_CODE_INFERENCE_FAILED",
    "ERROR_CODE_INPUT_INVALID",
    "ERROR_CODE_MODEL_NOT_READY",
    "ERROR_CODE_PROTOCOL_ERROR",
    "ERROR_CODE_QC_FAILED",
    "ERROR_CODE_RESOURCE_EXHAUSTED",
    "ERROR_CODE_TIMEOUT",
    "MAX_DIAGNOSTIC_BYTES",
    "MAX_REQUEST_JSON_BYTES",
    "MAX_RESULT_JSON_BYTES",
    "MAX_STRUCTURED_EVENT_COUNT",
    "PROTOCOL_ID",
    "RESULT_STATUS_ERROR",
    "RESULT_STATUS_OK",
    "STAGED_INPUT_FILENAME",
    "STAGED_REQUEST_FILENAME",
    "STAGED_RESULT_FILENAME",
    "CanonicalMetadata",
    "ModelInputPayload",
    "WorkerError",
    "WorkerProtocolError",
    "WorkerRequest",
    "WorkerResult",
    "decode_model_input_payload",
    "decode_model_metadata",
    "decode_model_requirements",
    "decode_model_metrics",
    "decode_model_validation",
    "decode_runtime_prediction",
    "decode_source_metadata",
    "encode_json",
    "encode_model_input_payload",
    "encode_model_metadata",
    "encode_model_metrics",
    "encode_model_requirements",
    "encode_model_validation",
    "encode_runtime_prediction",
    "encode_source_metadata",
    "encode_worker_request",
    "encode_worker_result",
    "reject_non_json_safe",
    "validate_request_size",
    "validate_result_matches_request",
    "validate_result_size",
    "validate_worker_request",
    "validate_worker_result",
]

# ---------------------------------------------------------------------------
# Protocol identity and wire filenames
# ---------------------------------------------------------------------------

PROTOCOL_ID = "bremen.worker.v1"

#: Fixed filenames inside the per-job staging directory. The staged H5 input
#: always has this exact name; no arbitrary client-supplied filesystem path
#: is ever accepted anywhere in this protocol.
STAGED_REQUEST_FILENAME = "request.json"
STAGED_INPUT_FILENAME = "input.h5"
STAGED_RESULT_FILENAME = "result.json"

ALLOWED_OPERATIONS = frozenset({"requirements", "validate", "predict"})

RESULT_STATUS_OK = "ok"
RESULT_STATUS_ERROR = "error"
ALLOWED_RESULT_STATUSES = frozenset({RESULT_STATUS_OK, RESULT_STATUS_ERROR})

ERROR_CODE_INPUT_INVALID = "INPUT_INVALID"
ERROR_CODE_QC_FAILED = "QC_FAILED"
ERROR_CODE_MODEL_NOT_READY = "MODEL_NOT_READY"
ERROR_CODE_INFERENCE_FAILED = "INFERENCE_FAILED"
ERROR_CODE_TIMEOUT = "TIMEOUT"
ERROR_CODE_RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
ERROR_CODE_PROTOCOL_ERROR = "PROTOCOL_ERROR"

ALLOWED_ERROR_CODES = frozenset({
    ERROR_CODE_INPUT_INVALID,
    ERROR_CODE_QC_FAILED,
    ERROR_CODE_MODEL_NOT_READY,
    ERROR_CODE_INFERENCE_FAILED,
    ERROR_CODE_TIMEOUT,
    ERROR_CODE_RESOURCE_EXHAUSTED,
    ERROR_CODE_PROTOCOL_ERROR,
})

ALLOWED_TARGET_SIDES = frozenset({"left", "right"})

# ---------------------------------------------------------------------------
# Bounded contract defaults (IR-02 defines the constants; a later supervisor
# PR enforces them against a running process — no process supervision is
# implemented in this module).
# ---------------------------------------------------------------------------

MAX_REQUEST_JSON_BYTES = 1_048_576  # 1 MiB
MAX_RESULT_JSON_BYTES = 1_048_576  # 1 MiB
MAX_STRUCTURED_EVENT_COUNT = 1000
MAX_DIAGNOSTIC_BYTES = 65536  # 64 KiB

# ---------------------------------------------------------------------------
# Identity patterns
# ---------------------------------------------------------------------------

_IDENTITY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_SHA256_HEX_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

_REQUEST_ALLOWED_TOP_LEVEL = frozenset({
    "protocol", "request_id", "operation", "model_id", "release_digest", "payload",
})
_RESULT_ALLOWED_TOP_LEVEL = frozenset({
    "protocol", "request_id", "operation", "model_id", "release_digest",
    "status", "payload", "error",
})
_ERROR_ALLOWED_FIELDS = frozenset({"code", "safe_reason", "details"})

#: Review fix (IR02-PROTOCOL-MODELINPUT): the predict/validate payload must
#: explicitly enumerate every transportable field of the existing
#: ``bremen.contracts.model_runtime.ModelInput`` carrier. ``measurements``
#: and ``canonical`` (the full ``CanonicalXRDCase``, which carries numpy
#: arrays) are never transported directly — the Worker reconstructs them
#: from the staged ``input.h5`` file; only the small, JSON-safe
#: non-measurement provenance fields needed for compatibility validation
#: travel as ``canonical_metadata`` (see ``CanonicalMetadata`` below).
_PAYLOAD_ALLOWED_FIELDS_BY_OPERATION: dict[str, frozenset[str]] = {
    "requirements": frozenset(),
    "validate": frozenset({
        "workflow_id", "patient_id", "target_side", "container_path",
        "parameters", "canonical_metadata",
    }),
    "predict": frozenset({
        "workflow_id", "patient_id", "target_side", "container_path",
        "parameters", "canonical_metadata",
    }),
}

#: ``workflow_id`` has no default on ``ModelInput`` (it is always supplied
#: by the platform) — required whenever the operation carries a payload at
#: all; ``requirements`` has no ``ModelInput`` and no required fields.
_PAYLOAD_REQUIRED_FIELDS_BY_OPERATION: dict[str, frozenset[str]] = {
    "requirements": frozenset(),
    "validate": frozenset({"workflow_id", "container_path"}),
    "predict": frozenset({"workflow_id", "container_path"}),
}

#: ``CanonicalXRDCase`` field vocabulary (``bremen.contracts.canonical_input``);
#: only its non-measurement provenance fields are transportable JSON.
_CANONICAL_METADATA_REQUIRED_FIELDS = frozenset({
    "source_layout", "source_layout_version", "source_checksum",
    "calibration_provenance",
})
_CANONICAL_METADATA_ALLOWED_FIELDS = _CANONICAL_METADATA_REQUIRED_FIELDS | {
    "calibration_metadata",
}
_CALIBRATION_PROVENANCE_VALUES = frozenset({
    "poni_text", "session_pre_integrated", "none",
})


class WorkerProtocolError(ValueError):
    """Fail-closed validation failure for the ``bremen.worker.v1`` contract.

    Raised for any malformed identity, digest, path, operation, status,
    error code, or non-JSON-safe value. Never carries exception internals
    beyond a fixed, safe message string.
    """


# ---------------------------------------------------------------------------
# JSON safety
# ---------------------------------------------------------------------------


def reject_non_json_safe(value: Any, *, path: str = "$") -> None:
    """Recursively reject NaN/Infinity and non-JSON-safe Python values.

    Allowed leaves: ``str``, ``bool``, ``int``, finite ``float``, ``None``.
    Allowed containers: ``Mapping`` with string keys, ``list``/``tuple``.
    Anything else (bytes, sets, custom objects, functions, NaN, Infinity)
    is rejected. This is the single recursive guard used before accepting
    or encoding any request/result/payload in this protocol.
    """
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise WorkerProtocolError(f"Non-finite number at {path}")
        return
    if isinstance(value, str):
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise WorkerProtocolError(f"Non-string key at {path}")
            reject_non_json_safe(child, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            reject_non_json_safe(child, path=f"{path}[{index}]")
        return
    raise WorkerProtocolError(
        f"Non-JSON-safe value of type {type(value).__name__} at {path}"
    )


def encode_json(value: Any) -> str:
    """Deterministic JSON encoding: sorted keys, compact separators.

    Rejects NaN/Infinity and non-JSON-safe values before encoding (never
    relies on ``json.dumps``'s own ``allow_nan`` silently producing
    non-standard ``NaN``/``Infinity`` tokens).
    """
    reject_non_json_safe(value)
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False,
    )


def validate_request_size(encoded: str | bytes) -> None:
    """Reject a request encoding larger than ``MAX_REQUEST_JSON_BYTES``."""
    size = len(encoded.encode("utf-8")) if isinstance(encoded, str) else len(encoded)
    if size > MAX_REQUEST_JSON_BYTES:
        raise WorkerProtocolError(
            f"request.json exceeds {MAX_REQUEST_JSON_BYTES} bytes ({size} bytes)"
        )


def validate_result_size(encoded: str | bytes) -> None:
    """Reject a result encoding larger than ``MAX_RESULT_JSON_BYTES``."""
    size = len(encoded.encode("utf-8")) if isinstance(encoded, str) else len(encoded)
    if size > MAX_RESULT_JSON_BYTES:
        raise WorkerProtocolError(
            f"result.json exceeds {MAX_RESULT_JSON_BYTES} bytes ({size} bytes)"
        )


# ---------------------------------------------------------------------------
# Identity validators
# ---------------------------------------------------------------------------


def _require_identity(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not _IDENTITY_PATTERN.match(value):
        raise WorkerProtocolError(f"{field_name} is not a valid identity string")
    return value


def _require_request_id(value: Any) -> str:
    if not isinstance(value, str) or not _REQUEST_ID_PATTERN.match(value):
        raise WorkerProtocolError("request_id is not a valid identity string")
    return value


def _require_digest(value: Any, *, field_name: str = "release_digest") -> str:
    if not isinstance(value, str) or not _SHA256_HEX_PATTERN.match(value):
        raise WorkerProtocolError(
            f"{field_name} must be a lowercase 64-character hex SHA-256 digest"
        )
    return value


def _require_protocol(value: Any) -> str:
    if value != PROTOCOL_ID:
        raise WorkerProtocolError(
            f"protocol must be {PROTOCOL_ID!r}, got {value!r}"
        )
    return value


def _require_string_keys(mapping: Mapping[str, Any], *, field_name: str) -> None:
    """Reject a top-level mapping with any non-string key.

    ``reject_non_json_safe`` already covers nested mappings; this guard
    makes every validator/decoder fail closed with a ``WorkerProtocolError``
    (instead of a raw ``TypeError`` from ``sorted(...)``) for top-level keys.
    """
    for key in mapping:
        if not isinstance(key, str):
            raise WorkerProtocolError(f"{field_name} must use string keys")


# ---------------------------------------------------------------------------
# Worker request (request.json)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkerRequest:
    """Validated ``request.json`` envelope for one Worker invocation."""

    protocol: str
    request_id: str
    operation: str
    model_id: str
    release_digest: str
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CanonicalMetadata:
    """Explicit JSON-safe transport for the non-measurement fields of the
    existing platform ``CanonicalXRDCase``
    (``bremen.contracts.canonical_input``), needed by a runtime's
    ``validate_model_input`` compatibility check.

    The measurement arrays themselves (``CanonicalXRDCase.measurements``,
    each carrying numpy ``q``/``intensity`` data) are never transported —
    the Worker reconstructs the full canonical case from the staged
    ``input.h5`` file. Only the small string/dict provenance fields that
    already exist on ``CanonicalXRDCase`` travel here.
    """

    source_layout: str
    source_layout_version: str
    source_checksum: str
    calibration_provenance: str
    calibration_metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelInputPayload:
    """Explicit JSON-safe transport for the existing
    ``bremen.contracts.model_runtime.ModelInput`` fields carried by the
    ``validate`` and ``predict`` operations.

    Mirrors ``ModelInput`` field-for-field except ``measurements`` and
    ``canonical`` (never transported directly; see ``CanonicalMetadata``).
    """

    workflow_id: str
    patient_id: str = ""
    target_side: str = ""
    container_path: str = ""
    parameters: Mapping[str, Any] = field(default_factory=dict)
    canonical_metadata: CanonicalMetadata | None = None


def _validate_canonical_metadata(value: Any) -> CanonicalMetadata:
    if not isinstance(value, Mapping):
        raise WorkerProtocolError("payload.canonical_metadata must be a JSON object")
    unknown = set(value) - _CANONICAL_METADATA_ALLOWED_FIELDS
    if unknown:
        raise WorkerProtocolError(
            f"payload.canonical_metadata has unsupported fields: {sorted(unknown)}"
        )
    missing = _CANONICAL_METADATA_REQUIRED_FIELDS - set(value)
    if missing:
        raise WorkerProtocolError(
            f"payload.canonical_metadata missing required fields: {sorted(missing)}"
        )
    for field_name in ("source_layout", "source_layout_version", "source_checksum"):
        field_value = value[field_name]
        if not isinstance(field_value, str) or isinstance(field_value, bool) or not field_value:
            raise WorkerProtocolError(
                f"payload.canonical_metadata.{field_name} must be a non-empty string"
            )
    source_checksum = value["source_checksum"]
    if not _SHA256_HEX_PATTERN.match(source_checksum):
        raise WorkerProtocolError(
            "payload.canonical_metadata.source_checksum must be a lowercase "
            "64-character hex SHA-256 digest"
        )
    calibration_provenance = value["calibration_provenance"]
    if (
        not isinstance(calibration_provenance, str)
        or calibration_provenance not in _CALIBRATION_PROVENANCE_VALUES
    ):
        raise WorkerProtocolError(
            "payload.canonical_metadata.calibration_provenance must be one of "
            f"{sorted(_CALIBRATION_PROVENANCE_VALUES)}"
        )
    calibration_metadata = value.get("calibration_metadata", {})
    if not isinstance(calibration_metadata, Mapping):
        raise WorkerProtocolError(
            "payload.canonical_metadata.calibration_metadata must be a JSON object"
        )
    for key, val in calibration_metadata.items():
        if not isinstance(key, str) or not isinstance(val, str) or isinstance(val, bool):
            raise WorkerProtocolError(
                "payload.canonical_metadata.calibration_metadata must map strings to strings"
            )
    return CanonicalMetadata(
        source_layout=value["source_layout"],
        source_layout_version=value["source_layout_version"],
        source_checksum=source_checksum,
        calibration_provenance=calibration_provenance,
        calibration_metadata=dict(calibration_metadata),
    )


def _validate_payload_fields(payload: Mapping[str, Any], *, operation: str) -> None:
    allowed = _PAYLOAD_ALLOWED_FIELDS_BY_OPERATION[operation]
    unknown = set(payload) - allowed
    if unknown:
        raise WorkerProtocolError(
            f"payload for operation {operation!r} has unsupported fields: "
            f"{sorted(unknown)}"
        )
    required = _PAYLOAD_REQUIRED_FIELDS_BY_OPERATION[operation]
    missing = required - set(payload)
    if missing:
        raise WorkerProtocolError(
            f"payload for operation {operation!r} missing required fields: "
            f"{sorted(missing)}"
        )
    if "workflow_id" in payload:
        workflow_id = payload["workflow_id"]
        if not isinstance(workflow_id, str) or isinstance(workflow_id, bool) or not workflow_id:
            raise WorkerProtocolError("payload.workflow_id must be a non-empty string")
    if "patient_id" in payload:
        patient_id = payload["patient_id"]
        if not isinstance(patient_id, str) or isinstance(patient_id, bool):
            raise WorkerProtocolError("payload.patient_id must be a string")
    if "target_side" in payload:
        target_side = payload["target_side"]
        if not isinstance(target_side, str) or isinstance(target_side, bool):
            raise WorkerProtocolError("payload.target_side must be a string")
        if target_side != "" and target_side not in ALLOWED_TARGET_SIDES:
            raise WorkerProtocolError(
                f"payload.target_side must be one of {sorted(ALLOWED_TARGET_SIDES)} "
                "or empty"
            )
    if "container_path" in payload:
        container_path = payload["container_path"]
        if not isinstance(container_path, str) or isinstance(container_path, bool):
            raise WorkerProtocolError("payload.container_path must be a string")
        if container_path != STAGED_INPUT_FILENAME:
            raise WorkerProtocolError(
                f"payload.container_path must be exactly "
                f"{STAGED_INPUT_FILENAME!r}; missing, empty, and any "
                "client-supplied filesystem path are rejected"
            )
    if "parameters" in payload and not isinstance(payload["parameters"], Mapping):
        raise WorkerProtocolError("payload.parameters must be an object")
    if "canonical_metadata" in payload:
        _validate_canonical_metadata(payload["canonical_metadata"])


def encode_model_input_payload(value: ModelInputPayload) -> dict[str, Any]:
    """Strict, fail-closed encoder for ``ModelInputPayload`` — built
    field-by-field, never ``dataclasses.asdict``.

    Every field is validated before the result mapping is built (no silent
    normalization), the parameters mapping is recursively JSON-safety
    checked, and ``container_path`` must be exactly the staged
    ``input.h5`` filename.
    """
    if not isinstance(value, ModelInputPayload):
        raise WorkerProtocolError(
            "ModelInputPayload encoder requires a ModelInputPayload instance"
        )
    workflow_id = value.workflow_id
    if not isinstance(workflow_id, str) or isinstance(workflow_id, bool) or not workflow_id:
        raise WorkerProtocolError("payload.workflow_id must be a non-empty string")
    for field_name in ("patient_id", "target_side", "container_path"):
        if not isinstance(getattr(value, field_name), str):
            raise WorkerProtocolError(f"payload.{field_name} must be a string")
    if value.target_side != "" and value.target_side not in ALLOWED_TARGET_SIDES:
        raise WorkerProtocolError(
            f"payload.target_side must be one of {sorted(ALLOWED_TARGET_SIDES)} "
            "or empty"
        )
    if value.container_path != STAGED_INPUT_FILENAME:
        raise WorkerProtocolError(
            f"payload.container_path must be exactly "
            f"{STAGED_INPUT_FILENAME!r}; missing, empty, and any "
            "client-supplied filesystem path are rejected"
        )
    if not isinstance(value.parameters, Mapping):
        raise WorkerProtocolError("payload.parameters must be an object")
    reject_non_json_safe(value.parameters, path="payload.parameters")
    data: dict[str, Any] = {
        "workflow_id": workflow_id,
        "patient_id": value.patient_id,
        "target_side": value.target_side,
        "container_path": value.container_path,
        "parameters": dict(value.parameters),
    }
    if value.canonical_metadata is not None:
        cm = value.canonical_metadata
        if not isinstance(cm, CanonicalMetadata):
            raise WorkerProtocolError(
                "payload.canonical_metadata must be a CanonicalMetadata instance"
            )
        if not isinstance(cm.calibration_metadata, Mapping):
            raise WorkerProtocolError(
                "payload.canonical_metadata.calibration_metadata must be a JSON object"
            )
        raw_canonical_metadata: dict[str, Any] = {
            "source_layout": cm.source_layout,
            "source_layout_version": cm.source_layout_version,
            "source_checksum": cm.source_checksum,
            "calibration_provenance": cm.calibration_provenance,
            "calibration_metadata": dict(cm.calibration_metadata),
        }
        # Reuse the same strict validator the decoder uses; this rejects
        # wrong types, bad checksums, unknown provenance and non-string
        # calibration values without duplicating the rules.
        _validate_canonical_metadata(raw_canonical_metadata)
        data["canonical_metadata"] = raw_canonical_metadata
    reject_non_json_safe(data)
    return data


def decode_model_input_payload(data: Mapping[str, Any], *, operation: str) -> ModelInputPayload:
    """Explicit, fail-closed decoder for a validate/predict payload.

    Delegates field-level validation to ``_validate_payload_fields`` (the
    same function ``validate_worker_request`` uses), then builds the typed
    ``ModelInputPayload`` without any ``str()``/``int()``/``float()``/
    ``bool()`` coercion of already-checked values.
    """
    if not isinstance(operation, str) or operation not in _PAYLOAD_ALLOWED_FIELDS_BY_OPERATION:
        raise WorkerProtocolError(f"Unknown operation {operation!r}")
    if not isinstance(data, Mapping):
        raise WorkerProtocolError("payload must be a JSON object")
    # Whole-payload recursive guard: non-string keys, NaN/Infinity, bytes,
    # sets and arbitrary Python objects are rejected before any field logic.
    reject_non_json_safe(data, path="payload")
    _validate_payload_fields(data, operation=operation)
    parameters = data.get("parameters", {})
    canonical_metadata = None
    if "canonical_metadata" in data:
        canonical_metadata = _validate_canonical_metadata(data["canonical_metadata"])
    return ModelInputPayload(
        workflow_id=data["workflow_id"],
        patient_id=data.get("patient_id", ""),
        target_side=data.get("target_side", ""),
        container_path=data["container_path"],
        parameters=dict(parameters),
        canonical_metadata=canonical_metadata,
    )


def validate_worker_request(data: Mapping[str, Any]) -> WorkerRequest:
    """Validate a raw ``request.json`` dict and return a ``WorkerRequest``.

    Fail-closed: rejects unknown top-level fields, wrong protocol, invalid
    digest, empty identities, unknown operations, unsupported payload
    fields, and non-JSON-safe values (including NaN/Infinity) anywhere in
    the payload.
    """
    if not isinstance(data, Mapping):
        raise WorkerProtocolError("request.json must be a JSON object")
    _require_string_keys(data, field_name="request.json")

    unknown = set(data) - _REQUEST_ALLOWED_TOP_LEVEL
    if unknown:
        raise WorkerProtocolError(f"request.json has unsupported fields: {sorted(unknown)}")

    for required in ("protocol", "request_id", "operation", "model_id", "release_digest"):
        if required not in data:
            raise WorkerProtocolError(f"request.json missing required field: {required}")

    protocol = _require_protocol(data["protocol"])
    request_id = _require_request_id(data["request_id"])

    operation = data["operation"]
    if not isinstance(operation, str) or operation not in ALLOWED_OPERATIONS:
        raise WorkerProtocolError(
            f"Unknown operation {operation!r}; allowed: {sorted(ALLOWED_OPERATIONS)}"
        )

    model_id = _require_identity(data["model_id"], field_name="model_id")
    release_digest = _require_digest(data["release_digest"])

    payload = data.get("payload", {})
    if not isinstance(payload, Mapping):
        raise WorkerProtocolError("request.json payload must be a JSON object")
    reject_non_json_safe(payload, path="$.payload")
    _validate_payload_fields(payload, operation=operation)

    return WorkerRequest(
        protocol=protocol,
        request_id=request_id,
        operation=operation,
        model_id=model_id,
        release_digest=release_digest,
        payload=dict(payload),
    )


def encode_worker_request(request: WorkerRequest) -> str:
    """Deterministically encode a ``WorkerRequest`` as ``request.json`` bytes.

    Strict: the request is re-validated through ``validate_worker_request``
    before encoding, so wrong field types, an invalid operation and
    non-JSON-safe payload values fail closed instead of being emitted.
    """
    if not isinstance(request, WorkerRequest):
        raise WorkerProtocolError("encode_worker_request requires a WorkerRequest instance")
    if not isinstance(request.payload, Mapping):
        raise WorkerProtocolError("WorkerRequest.payload must be a JSON object")
    data = {
        "protocol": request.protocol,
        "request_id": request.request_id,
        "operation": request.operation,
        "model_id": request.model_id,
        "release_digest": request.release_digest,
        "payload": dict(request.payload),
    }
    validate_worker_request(data)
    encoded = encode_json(data)
    validate_request_size(encoded)
    return encoded


# ---------------------------------------------------------------------------
# Worker result (result.json)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkerError:
    """Required shape of ``result.json``'s ``error`` object for a failure.

    Exactly ``code`` (one of the seven allowed typed codes) and
    ``safe_reason`` (a fixed safe string). Optional ``details`` carries
    structured JSON-safe metadata only (e.g., Aramina error attributes).
    Never a traceback, raw exception, filesystem path, S3 key, token, or secret.
    """

    code: str
    safe_reason: str
    details: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class WorkerResult:
    """Validated ``result.json`` envelope — the sole authoritative Worker
    output channel. stdout/stderr are diagnostics only and are never parsed
    as this result.
    """

    protocol: str
    request_id: str
    operation: str
    model_id: str
    release_digest: str
    status: str
    payload: Mapping[str, Any] | None = None
    error: WorkerError | None = None


def _validate_error_object(value: Any) -> WorkerError:
    if not isinstance(value, Mapping):
        raise WorkerProtocolError("result.json error must be a JSON object")
    _require_string_keys(value, field_name="result.json error")
    unknown = set(value) - _ERROR_ALLOWED_FIELDS
    if unknown:
        raise WorkerProtocolError(
            f"result.json error object has unsupported fields: {sorted(unknown)} "
            "(no traceback, path, or secret fields are ever allowed)"
        )
    for required in ("code", "safe_reason"):
        if required not in value:
            raise WorkerProtocolError(f"result.json error missing required field: {required}")
    code = value["code"]
    if not isinstance(code, str) or code not in ALLOWED_ERROR_CODES:
        raise WorkerProtocolError(
            f"Unknown error code {code!r}; allowed: {sorted(ALLOWED_ERROR_CODES)}"
        )
    safe_reason = value["safe_reason"]
    if not isinstance(safe_reason, str) or not safe_reason.strip():
        raise WorkerProtocolError("result.json error.safe_reason must be a non-empty string")
    details = None
    if "details" in value:
        details = value["details"]
        if not isinstance(details, Mapping):
            raise WorkerProtocolError("result.json error.details must be a JSON object (if present)")
        _require_string_keys(details, field_name="result.json error.details")
        reject_non_json_safe(details, path="result.json error.details")
    return WorkerError(code=code, safe_reason=safe_reason, details=details)


def validate_worker_result(data: Mapping[str, Any]) -> WorkerResult:
    """Validate a raw ``result.json`` dict and return a ``WorkerResult``.

    Fail-closed, mirroring ``validate_worker_request``: unknown top-level
    fields, wrong protocol, invalid digest, empty identities, unknown
    operation, invalid status, malformed error object/code, and
    non-JSON-safe payload values are all rejected.
    """
    if not isinstance(data, Mapping):
        raise WorkerProtocolError("result.json must be a JSON object")
    _require_string_keys(data, field_name="result.json")

    unknown = set(data) - _RESULT_ALLOWED_TOP_LEVEL
    if unknown:
        raise WorkerProtocolError(f"result.json has unsupported fields: {sorted(unknown)}")

    for required in (
        "protocol", "request_id", "operation", "model_id", "release_digest", "status",
    ):
        if required not in data:
            raise WorkerProtocolError(f"result.json missing required field: {required}")

    protocol = _require_protocol(data["protocol"])
    request_id = _require_request_id(data["request_id"])

    operation = data["operation"]
    if not isinstance(operation, str) or operation not in ALLOWED_OPERATIONS:
        raise WorkerProtocolError(
            f"Unknown operation {operation!r}; allowed: {sorted(ALLOWED_OPERATIONS)}"
        )

    model_id = _require_identity(data["model_id"], field_name="model_id")
    release_digest = _require_digest(data["release_digest"])

    status = data["status"]
    if not isinstance(status, str) or status not in ALLOWED_RESULT_STATUSES:
        raise WorkerProtocolError(
            f"Unknown status {status!r}; allowed: {sorted(ALLOWED_RESULT_STATUSES)}"
        )

    has_payload = "payload" in data
    has_error = "error" in data

    if status == RESULT_STATUS_OK:
        if has_error:
            raise WorkerProtocolError("result.json status=ok must not carry an error object")
        if not has_payload or data["payload"] is None:
            raise WorkerProtocolError("result.json status=ok requires a payload")
        payload = data["payload"]
        if not isinstance(payload, Mapping):
            raise WorkerProtocolError("result.json payload must be a JSON object")
        reject_non_json_safe(payload, path="$.payload")
        return WorkerResult(
            protocol=protocol, request_id=request_id, operation=operation,
            model_id=model_id, release_digest=release_digest, status=status,
            payload=dict(payload), error=None,
        )

    # status == RESULT_STATUS_ERROR
    if has_payload:
        raise WorkerProtocolError("result.json status=error must not carry a payload")
    if not has_error:
        raise WorkerProtocolError("result.json status=error requires an error object")
    error = _validate_error_object(data["error"])
    return WorkerResult(
        protocol=protocol, request_id=request_id, operation=operation,
        model_id=model_id, release_digest=release_digest, status=status,
        payload=None, error=error,
    )


def validate_result_matches_request(request: WorkerRequest, result: WorkerResult) -> None:
    """Reject a result whose identity does not match its originating request.

    Checks ``protocol``, ``request_id``, ``operation``, ``model_id`` and
    ``release_digest`` for exact equality. This is the explicit
    identity/digest-mismatch guard the supervisor will rely on once it
    exists (not implemented here).
    """
    mismatches = [
        field_name
        for field_name in ("protocol", "request_id", "operation", "model_id", "release_digest")
        if getattr(request, field_name) != getattr(result, field_name)
    ]
    if mismatches:
        raise WorkerProtocolError(
            f"result.json identity does not match request.json for: {mismatches}"
        )


def encode_worker_result(result: WorkerResult) -> str:
    """Deterministically encode a ``WorkerResult`` as ``result.json`` bytes.

    Strict: every envelope field, the status-specific payload/error shape and
    the JSON-safe status of all values are re-validated through
    ``validate_worker_result`` before encoding.
    """
    if not isinstance(result, WorkerResult):
        raise WorkerProtocolError("encode_worker_result requires a WorkerResult instance")
    if not isinstance(result.status, str) or result.status not in ALLOWED_RESULT_STATUSES:
        raise WorkerProtocolError(
            f"Unknown status {result.status!r}; allowed: {sorted(ALLOWED_RESULT_STATUSES)}"
        )
    data: dict[str, Any] = {
        "protocol": result.protocol,
        "request_id": result.request_id,
        "operation": result.operation,
        "model_id": result.model_id,
        "release_digest": result.release_digest,
        "status": result.status,
    }
    if result.status == RESULT_STATUS_OK:
        if result.payload is None:
            data["payload"] = {}
        elif not isinstance(result.payload, Mapping):
            raise WorkerProtocolError("WorkerResult.payload must be a JSON object")
        else:
            data["payload"] = dict(result.payload)
    else:
        error = result.error
        if not isinstance(error, WorkerError):
            raise WorkerProtocolError("WorkerResult status=error requires a WorkerError object")
        error_payload: dict[str, Any] = {
            "code": error.code, "safe_reason": error.safe_reason,
        }
        if error.details is not None:
            error_payload["details"] = dict(error.details)
        data["error"] = error_payload
    validate_worker_result(data)
    encoded = encode_json(data)
    validate_result_size(encoded)
    return encoded


# ---------------------------------------------------------------------------
# Explicit codecs for the JSON-safe portions of the existing Model Runtime
# Contract v1 dataclasses (``bremen.contracts.model_runtime``). Each encoder
# builds its dict field-by-field from the dataclass's own accessors/`to_dict`
# helpers — never ``dataclasses.asdict`` and never implicit arbitrary-object
# serialization — then rejects any non-JSON-safe value before returning.
# ---------------------------------------------------------------------------


def encode_model_requirements(value: ModelRequirements) -> dict[str, Any]:
    """Strict, fail-closed encoder for ``ModelRequirements``.

    Validates the semantic type of every contract field BEFORE encoding and
    rejects malformed values rather than silently coercing them:

    - ``scientifically_certified`` / ``requires_target_side`` must be ``bool``
      (a JSON string or ``1`` is rejected);
    - ``total_measurements`` must be ``int`` or ``None`` (a numeric string or
      ``bool`` is rejected — ``bool`` is not accepted as integer);
    - string fields must be ``str`` (and not ``bool``);
    - tuple fields (``measurement_sides``, ``allowed_target_sides``,
      ``request_fields``, ``optional_request_fields``, ``notes``) must be
      tuples/lists of strings (or string-int pairs for measurement_sides);
    - the fully-validated result is then JSON-safe guarded and returned.
    """
    if not isinstance(value, ModelRequirements):
        raise WorkerProtocolError(
            "ModelRequirements encoder requires a ModelRequirements instance"
        )
    for field_name in (
        "contract_version", "workflow_id", "model_id", "model_version",
        "feature_schema_version",
    ):
        field_value = getattr(value, field_name)
        if not isinstance(field_value, str) or isinstance(field_value, bool):
            raise WorkerProtocolError(
                f"ModelRequirements.{field_name} must be a string"
            )
    for field_name in ("scientifically_certified", "requires_target_side"):
        field_value = getattr(value, field_name)
        if not isinstance(field_value, bool):
            raise WorkerProtocolError(
                f"ModelRequirements.{field_name} must be a boolean"
            )
    total_measurements = value.total_measurements
    if total_measurements is not None and (
        isinstance(total_measurements, bool)
        or not isinstance(total_measurements, int)
    ):
        raise WorkerProtocolError(
            "ModelRequirements.total_measurements must be an integer or null"
        )
    measurement_sides = value.measurement_sides
    if not isinstance(measurement_sides, (tuple, list)):
        raise WorkerProtocolError(
            "ModelRequirements.measurement_sides must be a list of side/count pairs"
        )
    for pair in measurement_sides:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise WorkerProtocolError(
                "ModelRequirements.measurement_sides entries must be (side, count) pairs"
            )
        side, count = pair
        if not isinstance(side, str) or isinstance(side, bool) or not side:
            raise WorkerProtocolError(
                "ModelRequirements.measurement_sides side must be a non-empty string"
            )
        if isinstance(count, bool) or not isinstance(count, int):
            raise WorkerProtocolError(
                "ModelRequirements.measurement_sides count must be an integer"
            )
    for field_name in (
        "allowed_target_sides", "request_fields", "optional_request_fields", "notes",
    ):
        field_value = getattr(value, field_name)
        if not isinstance(field_value, (tuple, list)):
            raise WorkerProtocolError(
                f"ModelRequirements.{field_name} must be a list of strings"
            )
        for item in field_value:
            if not isinstance(item, str) or isinstance(item, bool):
                raise WorkerProtocolError(
                    f"ModelRequirements.{field_name} entries must be strings"
                )
    data = value.to_input_requirements()
    reject_non_json_safe(data)
    return data


#: IR-05 addition (NOT a change to any existing function/shape): the Harness
#: now needs the decode direction for ``ModelRequirements`` to reconstruct
#: the dataclass from a Worker's ``requirements`` result payload — IR-02 only
#: implemented the encode direction (the model package was the only producer
#: of ``ModelRequirements`` before IR-05). This is purely additive: it
#: consumes exactly the same shape ``encode_model_requirements``/
#: ``ModelRequirements.to_input_requirements()`` produce, with the same
#: strict, no-coercion validation style as every other ``decode_*`` function
#: in this module. ``model_id`` and ``scientifically_certified`` are not part
#: of that JSON shape (see ``to_input_requirements``) and default to their
#: dataclass defaults ("" / False) here, exactly as they would for any other
#: caller that only has the JSON view.
def decode_model_requirements(data: Mapping[str, Any]) -> ModelRequirements:
    if not isinstance(data, Mapping):
        raise WorkerProtocolError("ModelRequirements payload must be a JSON object")
    allowed = {
        "contract_version", "workflow_id", "model_version", "feature_schema_version",
        "measurement_sides", "total_measurements", "requires_target_side",
        "allowed_target_sides", "request_fields", "optional_request_fields", "notes",
    }
    unknown = set(data) - allowed
    if unknown:
        raise WorkerProtocolError(
            f"ModelRequirements payload has unsupported fields: {sorted(unknown)}"
        )

    def _str_field(key: str, *, default: str = "") -> str:
        value = data.get(key, default)
        if not isinstance(value, str) or isinstance(value, bool):
            raise WorkerProtocolError(f"ModelRequirements.{key} must be a string")
        return value

    def _str_tuple(key: str) -> tuple[str, ...]:
        raw = data.get(key, [])
        if not isinstance(raw, (list, tuple)):
            raise WorkerProtocolError(f"ModelRequirements.{key} must be an array")
        for item in raw:
            if not isinstance(item, str) or isinstance(item, bool):
                raise WorkerProtocolError(f"ModelRequirements.{key} entries must be strings")
        return tuple(raw)

    contract_version = _str_field("contract_version", default=CONTRACT_VERSION)
    workflow_id = _str_field("workflow_id")
    model_version = _str_field("model_version")
    feature_schema_version = _str_field("feature_schema_version")

    measurement_sides_raw = data.get("measurement_sides", [])
    if not isinstance(measurement_sides_raw, (list, tuple)):
        raise WorkerProtocolError("ModelRequirements.measurement_sides must be an array")
    measurement_sides: list[tuple[str, int]] = []
    for item in measurement_sides_raw:
        if not isinstance(item, Mapping) or set(item) != {"side", "required_count"}:
            raise WorkerProtocolError(
                "ModelRequirements.measurement_sides entries must have exactly "
                "'side' and 'required_count'"
            )
        side = item["side"]
        count = item["required_count"]
        if not isinstance(side, str) or isinstance(side, bool) or not side:
            raise WorkerProtocolError(
                "ModelRequirements.measurement_sides.side must be a non-empty string"
            )
        if isinstance(count, bool) or not isinstance(count, int):
            raise WorkerProtocolError(
                "ModelRequirements.measurement_sides.required_count must be an integer"
            )
        measurement_sides.append((side, count))

    total_measurements = data.get("total_measurements")
    if total_measurements is not None and (
        isinstance(total_measurements, bool) or not isinstance(total_measurements, int)
    ):
        raise WorkerProtocolError(
            "ModelRequirements.total_measurements must be an integer or null"
        )

    requires_target_side = data.get("requires_target_side", False)
    if not isinstance(requires_target_side, bool):
        raise WorkerProtocolError("ModelRequirements.requires_target_side must be a boolean")

    return ModelRequirements(
        contract_version=contract_version,
        workflow_id=workflow_id,
        model_id="",
        model_version=model_version,
        feature_schema_version=feature_schema_version,
        measurement_sides=tuple(measurement_sides),
        total_measurements=total_measurements,
        requires_target_side=requires_target_side,
        allowed_target_sides=_str_tuple("allowed_target_sides"),
        request_fields=_str_tuple("request_fields"),
        optional_request_fields=_str_tuple("optional_request_fields"),
        notes=_str_tuple("notes"),
        scientifically_certified=False,
    )


def encode_model_validation(value: ModelValidation) -> dict[str, Any]:
    """Strict, fail-closed encoder for ``ModelValidation``.

    ``compatible`` must already be a ``bool`` (never ``bool(...)``-coerced
    from a string or integer); ``safe_reason`` must be a string or ``None``.
    """
    if not isinstance(value, ModelValidation):
        raise WorkerProtocolError(
            "ModelValidation encoder requires a ModelValidation instance"
        )
    if not isinstance(value.compatible, bool):
        raise WorkerProtocolError("ModelValidation.compatible must be a boolean")
    if value.safe_reason is not None and not isinstance(value.safe_reason, str):
        raise WorkerProtocolError(
            "ModelValidation.safe_reason must be a string or null"
        )
    data = {"compatible": value.compatible, "safe_reason": value.safe_reason}
    reject_non_json_safe(data)
    return data


def decode_model_validation(data: Mapping[str, Any]) -> ModelValidation:
    if not isinstance(data, Mapping):
        raise WorkerProtocolError("ModelValidation payload must be a JSON object")
    reject_non_json_safe(data)
    allowed = {"compatible", "safe_reason"}
    unknown = set(data) - allowed
    if unknown:
        raise WorkerProtocolError(f"ModelValidation payload has unsupported fields: {sorted(unknown)}")
    if "compatible" not in data:
        raise WorkerProtocolError("ModelValidation payload missing 'compatible'")
    compatible = data["compatible"]
    if not isinstance(compatible, bool):
        raise WorkerProtocolError("ModelValidation.compatible must be a boolean")
    safe_reason = data.get("safe_reason")
    if safe_reason is not None and not isinstance(safe_reason, str):
        raise WorkerProtocolError("ModelValidation.safe_reason must be a string or null")
    return ModelValidation(compatible=compatible, safe_reason=safe_reason)


def encode_source_metadata(value: SourceMetadata) -> dict[str, Any]:
    """Strict, fail-closed encoder for ``SourceMetadata``.

    Every field is type-checked before ``to_dict()`` is called; no value is
    ever silently coerced with ``str(...)``/``float(...)``.
    """
    if not isinstance(value, SourceMetadata):
        raise WorkerProtocolError(
            "SourceMetadata encoder requires a SourceMetadata instance"
        )
    patient_age = value.patient_age
    if patient_age is not None and (
        isinstance(patient_age, bool) or not isinstance(patient_age, (int, float))
    ):
        raise WorkerProtocolError("SourceMetadata.patient_age must be numeric or null")
    if patient_age is not None and not math.isfinite(float(patient_age)):
        raise WorkerProtocolError("SourceMetadata.patient_age must be finite")
    for field_name in (
        "referring_physician", "scan_date_time", "operator_id", "hardware_version",
    ):
        field_value = getattr(value, field_name)
        if not isinstance(field_value, str):
            raise WorkerProtocolError(
                f"SourceMetadata.{field_name} must be a string"
            )
    if value.eoscan_version is not None and not isinstance(value.eoscan_version, str):
        raise WorkerProtocolError("SourceMetadata.eoscan_version must be a string or null")
    data = value.to_dict()
    reject_non_json_safe(data)
    return data


def _require_optional_str(value: Any, *, field_name: str, default: str = "") -> str:
    """Validate an optional string field: missing -> ``default``, present ->
    must already be ``str`` (never coerced with ``str(...)``).
    """
    if value is None:
        return default
    if not isinstance(value, str):
        raise WorkerProtocolError(f"{field_name} must be a string")
    return value


def decode_source_metadata(data: Mapping[str, Any]) -> SourceMetadata:
    if not isinstance(data, Mapping):
        raise WorkerProtocolError("SourceMetadata payload must be a JSON object")
    reject_non_json_safe(data)
    allowed = {
        "patient_age", "referring_physician", "scan_date_time",
        "operator_id", "hardware_version", "eoscan_version",
    }
    unknown = set(data) - allowed
    if unknown:
        raise WorkerProtocolError(f"SourceMetadata payload has unsupported fields: {sorted(unknown)}")
    patient_age = data.get("patient_age")
    if patient_age is not None and (
        isinstance(patient_age, bool) or not isinstance(patient_age, (int, float))
    ):
        raise WorkerProtocolError("SourceMetadata.patient_age must be numeric or null")
    if patient_age is not None and not math.isfinite(float(patient_age)):
        raise WorkerProtocolError("SourceMetadata.patient_age must be finite")
    eoscan_version = data.get("eoscan_version")
    if eoscan_version is not None and not isinstance(eoscan_version, str):
        raise WorkerProtocolError("SourceMetadata.eoscan_version must be a string or null")
    return SourceMetadata(
        patient_age=patient_age,
        referring_physician=_require_optional_str(
            data.get("referring_physician"), field_name="SourceMetadata.referring_physician"
        ),
        scan_date_time=_require_optional_str(
            data.get("scan_date_time"), field_name="SourceMetadata.scan_date_time"
        ),
        operator_id=_require_optional_str(
            data.get("operator_id"), field_name="SourceMetadata.operator_id"
        ),
        hardware_version=_require_optional_str(
            data.get("hardware_version"), field_name="SourceMetadata.hardware_version"
        ),
        eoscan_version=eoscan_version,
    )


def encode_model_metadata(value: ModelMetadata) -> dict[str, Any]:
    """Strict, fail-closed encoder for ``ModelMetadata``."""
    if not isinstance(value, ModelMetadata):
        raise WorkerProtocolError(
            "ModelMetadata encoder requires a ModelMetadata instance"
        )
    if not isinstance(value.model_method, str):
        raise WorkerProtocolError("ModelMetadata.model_method must be a string")
    data = value.to_dict()
    reject_non_json_safe(data)
    return data


def decode_model_metadata(data: Mapping[str, Any]) -> ModelMetadata:
    if not isinstance(data, Mapping):
        raise WorkerProtocolError("ModelMetadata payload must be a JSON object")
    reject_non_json_safe(data)
    allowed = {"model_method"}
    unknown = set(data) - allowed
    if unknown:
        raise WorkerProtocolError(f"ModelMetadata payload has unsupported fields: {sorted(unknown)}")
    return ModelMetadata(
        model_method=_require_optional_str(
            data.get("model_method"), field_name="ModelMetadata.model_method"
        )
    )


def encode_model_metrics(value: ModelMetrics) -> dict[str, Any]:
    """Strict, fail-closed encoder for ``ModelMetrics``.

    ``sensitivity``/``specificity`` must be finite numbers or ``None``;
    ``bool`` never satisfies the numeric check.
    """
    if not isinstance(value, ModelMetrics):
        raise WorkerProtocolError(
            "ModelMetrics encoder requires a ModelMetrics instance"
        )
    for name in ("sensitivity", "specificity"):
        metric = getattr(value, name)
        if metric is not None and (
            isinstance(metric, bool) or not isinstance(metric, (int, float))
        ):
            raise WorkerProtocolError(f"ModelMetrics.{name} must be numeric or null")
        if metric is not None and not math.isfinite(float(metric)):
            raise WorkerProtocolError(f"ModelMetrics.{name} must be finite")
    data = value.to_dict()
    reject_non_json_safe(data)
    return data


def decode_model_metrics(data: Mapping[str, Any]) -> ModelMetrics:
    if not isinstance(data, Mapping):
        raise WorkerProtocolError("ModelMetrics payload must be a JSON object")
    reject_non_json_safe(data)
    allowed = {"sensitivity", "specificity"}
    unknown = set(data) - allowed
    if unknown:
        raise WorkerProtocolError(f"ModelMetrics payload has unsupported fields: {sorted(unknown)}")
    sensitivity = data.get("sensitivity")
    specificity = data.get("specificity")
    for name, val in (("sensitivity", sensitivity), ("specificity", specificity)):
        if val is not None and (isinstance(val, bool) or not isinstance(val, (int, float))):
            raise WorkerProtocolError(f"ModelMetrics.{name} must be numeric or null")
        if val is not None and not math.isfinite(float(val)):
            raise WorkerProtocolError(f"ModelMetrics.{name} must be finite")
    return ModelMetrics(sensitivity=sensitivity, specificity=specificity)


def encode_runtime_prediction(value: RuntimePrediction) -> dict[str, Any]:
    """Strict, fail-closed encoder for ``RuntimePrediction``.

    Every field is validated before the result mapping is copied; the whole
    resulting mapping is then passed through the recursive JSON-safety guard
    (so NaN/Infinity, bytes, arbitrary objects and non-string keys in the
    model-owned ``result`` mapping never cross the wire).
    """
    if not isinstance(value, RuntimePrediction):
        raise WorkerProtocolError(
            "RuntimePrediction encoder requires a RuntimePrediction instance"
        )
    workflow_id = value.workflow_id
    if not isinstance(workflow_id, str) or isinstance(workflow_id, bool) or not workflow_id:
        raise WorkerProtocolError("RuntimePrediction.workflow_id must be a non-empty string")
    for field_name in ("model_id", "model_version"):
        field_value = getattr(value, field_name)
        if not isinstance(field_value, str):
            raise WorkerProtocolError(
                f"RuntimePrediction.{field_name} must be a string"
            )
    if not isinstance(value.result, Mapping):
        raise WorkerProtocolError("RuntimePrediction.result must be a JSON object")
    if value.safe_reason is not None and not isinstance(value.safe_reason, str):
        raise WorkerProtocolError(
            "RuntimePrediction.safe_reason must be a string or null"
        )
    for field_name, expected_type in (
        ("source_metadata", SourceMetadata),
        ("model_metadata", ModelMetadata),
        ("model_metrics", ModelMetrics),
    ):
        if not isinstance(getattr(value, field_name), expected_type):
            raise WorkerProtocolError(
                f"RuntimePrediction.{field_name} must be a {expected_type.__name__} instance"
            )
    data: dict[str, Any] = {
        "workflow_id": workflow_id,
        "model_id": value.model_id,
        "model_version": value.model_version,
        "result": dict(value.result),
        "safe_reason": value.safe_reason,
        "source_metadata": encode_source_metadata(value.source_metadata),
        "model_metadata": encode_model_metadata(value.model_metadata),
        "model_metrics": encode_model_metrics(value.model_metrics),
    }
    reject_non_json_safe(data)
    return data


def decode_runtime_prediction(data: Mapping[str, Any]) -> RuntimePrediction:
    if not isinstance(data, Mapping):
        raise WorkerProtocolError("RuntimePrediction payload must be a JSON object")
    reject_non_json_safe(data)
    allowed = {
        "workflow_id", "model_id", "model_version", "result", "safe_reason",
        "source_metadata", "model_metadata", "model_metrics",
    }
    unknown = set(data) - allowed
    if unknown:
        raise WorkerProtocolError(f"RuntimePrediction payload has unsupported fields: {sorted(unknown)}")
    if "workflow_id" not in data:
        raise WorkerProtocolError("RuntimePrediction payload missing 'workflow_id'")
    workflow_id = data["workflow_id"]
    if not isinstance(workflow_id, str) or isinstance(workflow_id, bool) or not workflow_id:
        raise WorkerProtocolError("RuntimePrediction.workflow_id must be a non-empty string")
    model_id = _require_optional_str(data.get("model_id"), field_name="RuntimePrediction.model_id")
    model_version = _require_optional_str(
        data.get("model_version"), field_name="RuntimePrediction.model_version"
    )
    result = data.get("result", {})
    if not isinstance(result, Mapping):
        raise WorkerProtocolError("RuntimePrediction.result must be a JSON object")
    # Recursive JSON-safety guard on the model-owned result mapping: NaN,
    # Infinity, arbitrary Python objects, bytes, sets, and non-string keys
    # must never cross the wire.
    reject_non_json_safe(result, path="RuntimePrediction.result")
    safe_reason = data.get("safe_reason")
    if safe_reason is not None and not isinstance(safe_reason, str):
        raise WorkerProtocolError("RuntimePrediction.safe_reason must be a string or null")
    for field_name in ("source_metadata", "model_metadata", "model_metrics"):
        if field_name in data and data[field_name] is not None and not isinstance(data[field_name], Mapping):
            raise WorkerProtocolError(f"RuntimePrediction.{field_name} must be a JSON object or null")
    return RuntimePrediction(
        workflow_id=workflow_id,
        model_id=model_id,
        model_version=model_version,
        result=dict(result),
        safe_reason=safe_reason,
        source_metadata=decode_source_metadata(data.get("source_metadata") or {}),
        model_metadata=decode_model_metadata(data.get("model_metadata") or {}),
        model_metrics=decode_model_metrics(data.get("model_metrics") or {}),
    )
