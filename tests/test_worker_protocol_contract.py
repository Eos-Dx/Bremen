"""Tests for the Worker protocol v1 contract (``bremen.worker.v1``) — IR-02.

Synthetic requests/results only. No real subprocess, no real model
execution, no network calls, no pickle/joblib transport. Validates
``request.json`` / ``result.json`` shapes, the JSON-safe codecs for the
existing Model Runtime Contract v1 dataclasses, NaN/Infinity rejection,
deterministic encoding, and the module's platform/science independence.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path
from typing import Any

import pytest

from bremen.contracts.model_runtime import (
    ModelMetadata,
    ModelMetrics,
    ModelRequirements,
    ModelValidation,
    RuntimePrediction,
    SourceMetadata,
)
from bremen.contracts.worker_protocol import (
    ALLOWED_ERROR_CODES,
    ALLOWED_OPERATIONS,
    PROTOCOL_ID,
    RESULT_STATUS_ERROR,
    RESULT_STATUS_OK,
    STAGED_INPUT_FILENAME,
    CanonicalMetadata,
    ModelInputPayload,
    WorkerError,
    WorkerProtocolError,
    WorkerRequest,
    WorkerResult,
    decode_model_input_payload,
    decode_model_metadata,
    decode_model_metrics,
    decode_model_validation,
    decode_runtime_prediction,
    decode_source_metadata,
    encode_json,
    encode_model_input_payload,
    encode_model_metadata,
    encode_model_metrics,
    encode_model_requirements,
    encode_model_validation,
    encode_runtime_prediction,
    encode_source_metadata,
    encode_worker_request,
    encode_worker_result,
    reject_non_json_safe,
    validate_result_matches_request,
    validate_worker_request,
    validate_worker_result,
)

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "bremen" / "contracts" / "worker_protocol.py"
)

DIGEST = "a" * 64


def _ast_import_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
    return modules


def _valid_request_data(**overrides: Any) -> dict[str, Any]:
    data = {
        "protocol": PROTOCOL_ID,
        "request_id": "req-1",
        "operation": "predict",
        "model_id": "bremen-paper-reference-v0-2-0",
        "release_digest": DIGEST,
        "payload": {
            "workflow_id": "bremen",
            "patient_id": "Nova_227",
            "target_side": "",
            "container_path": STAGED_INPUT_FILENAME,
            "parameters": {},
        },
    }
    data.update(overrides)
    return data


def _valid_ok_result_data(**overrides: Any) -> dict[str, Any]:
    data = {
        "protocol": PROTOCOL_ID,
        "request_id": "req-1",
        "operation": "predict",
        "model_id": "bremen-paper-reference-v0-2-0",
        "release_digest": DIGEST,
        "status": "ok",
        "payload": {"probability": 0.77, "prediction": 1},
    }
    data.update(overrides)
    return data


def _valid_error_result_data(**overrides: Any) -> dict[str, Any]:
    data = {
        "protocol": PROTOCOL_ID,
        "request_id": "req-1",
        "operation": "predict",
        "model_id": "bremen-paper-reference-v0-2-0",
        "release_digest": DIGEST,
        "status": "error",
        "error": {"code": "QC_FAILED", "safe_reason": "raw_peak_gate_failed"},
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Protocol constants
# ---------------------------------------------------------------------------


class TestProtocolConstants:
    def test_protocol_id(self):
        assert PROTOCOL_ID == "bremen.worker.v1"

    def test_staged_input_filename_is_fixed(self):
        assert STAGED_INPUT_FILENAME == "input.h5"

    def test_allowed_operations(self):
        assert ALLOWED_OPERATIONS == {"requirements", "validate", "predict"}

    def test_allowed_error_codes(self):
        assert ALLOWED_ERROR_CODES == {
            "INPUT_INVALID", "QC_FAILED", "MODEL_NOT_READY", "INFERENCE_FAILED",
            "TIMEOUT", "RESOURCE_EXHAUSTED", "PROTOCOL_ERROR",
        }


# ---------------------------------------------------------------------------
# 11-13. Valid requirements / validate / predict request+result
# ---------------------------------------------------------------------------


class TestValidRequestsPerOperation:
    def test_valid_requirements_request(self):
        req = validate_worker_request(_valid_request_data(operation="requirements", payload={}))
        assert req.operation == "requirements"
        assert req.payload == {}

    def test_requirements_request_rejects_any_payload_field(self):
        with pytest.raises(WorkerProtocolError, match="unsupported fields"):
            validate_worker_request(
                _valid_request_data(operation="requirements", payload={"patient_id": "x"})
            )

    def test_valid_validate_request(self):
        req = validate_worker_request(_valid_request_data(operation="validate"))
        assert req.operation == "validate"
        assert req.payload["patient_id"] == "Nova_227"

    def test_valid_predict_request(self):
        req = validate_worker_request(_valid_request_data(operation="predict"))
        assert req.operation == "predict"

    def test_valid_requirements_result(self):
        payload = {"workflow_id": "bremen", "model_version": "0.2.0", "measurement_sides": []}
        result = validate_worker_result(_valid_ok_result_data(operation="requirements", payload=payload))
        assert result.operation == "requirements"
        assert result.payload == payload

    def test_valid_validate_result(self):
        payload = {"compatible": True, "safe_reason": None}
        result = validate_worker_result(_valid_ok_result_data(operation="validate", payload=payload))
        assert result.operation == "validate"
        assert result.payload["compatible"] is True

    def test_valid_predict_result(self):
        result = validate_worker_result(_valid_ok_result_data())
        assert result.status == RESULT_STATUS_OK
        assert result.payload["probability"] == 0.77


# ---------------------------------------------------------------------------
# 14. RuntimePrediction round trip (and the other codecs)
# ---------------------------------------------------------------------------


class TestCodecRoundTrips:
    def test_runtime_prediction_round_trip(self):
        prediction = RuntimePrediction(
            workflow_id="bremen",
            model_id="bremen-paper-reference-v0-2-0",
            model_version="0.2.0-paper-reference",
            result={"probability": 0.7726940329943811, "prediction": 1},
            safe_reason=None,
            source_metadata=SourceMetadata(
                patient_age=44, referring_physician="", scan_date_time="2025-05-28T10:19:55",
                operator_id="backfill", hardware_version="v1.0.1", eoscan_version=None,
            ),
            model_metadata=ModelMetadata(model_method="median_imputer_standard_scaler_balanced_logistic_regression"),
            model_metrics=ModelMetrics(sensitivity=0.9516129032258065, specificity=0.391304347826087),
        )
        encoded = encode_runtime_prediction(prediction)
        decoded = decode_runtime_prediction(encoded)
        assert decoded == prediction

    def test_runtime_prediction_round_trip_with_nulls(self):
        prediction = RuntimePrediction(workflow_id="aramina")
        encoded = encode_runtime_prediction(prediction)
        decoded = decode_runtime_prediction(encoded)
        assert decoded == prediction

    def test_model_validation_round_trip(self):
        value = ModelValidation(compatible=False, safe_reason="requires_exactly_3_left_3_right")
        encoded = encode_model_validation(value)
        decoded = decode_model_validation(encoded)
        assert decoded == value

    def test_source_metadata_round_trip(self):
        value = SourceMetadata(patient_age=None, eoscan_version="v1.0")
        encoded = encode_source_metadata(value)
        decoded = decode_source_metadata(encoded)
        assert decoded == value

    def test_model_metadata_round_trip(self):
        value = ModelMetadata(model_method="m2q_gated_target_case")
        encoded = encode_model_metadata(value)
        decoded = decode_model_metadata(encoded)
        assert decoded == value

    def test_model_metrics_round_trip(self):
        value = ModelMetrics(sensitivity=0.8175, specificity=None)
        encoded = encode_model_metrics(value)
        decoded = decode_model_metrics(encoded)
        assert decoded == value

    def test_model_requirements_encode_is_safe_dict(self):
        requirements = ModelRequirements(
            workflow_id="bremen", model_id="bremen-paper-reference-v0-2-0",
            measurement_sides=(("LEFT", 3), ("RIGHT", 3)), total_measurements=6,
        )
        encoded = encode_model_requirements(requirements)
        assert encoded["workflow_id"] == "bremen"
        assert encoded["measurement_sides"] == [
            {"side": "LEFT", "required_count": 3}, {"side": "RIGHT", "required_count": 3},
        ]

    def test_codecs_do_not_use_dataclass_dunder_dict(self):
        """Encoders build dicts field-by-field; they must not silently pass
        through private/internal dataclass attributes via asdict/__dict__."""
        value = SourceMetadata(patient_age=1)
        encoded = encode_source_metadata(value)
        assert set(encoded) == {
            "patient_age", "referring_physician", "scan_date_time",
            "operator_id", "hardware_version", "eoscan_version",
        }

    def test_decode_rejects_unknown_fields(self):
        with pytest.raises(WorkerProtocolError, match="unsupported fields"):
            decode_model_validation({"compatible": True, "extra": "x"})
        with pytest.raises(WorkerProtocolError, match="unsupported fields"):
            decode_source_metadata({"patient_age": 1, "extra": "x"})
        with pytest.raises(WorkerProtocolError, match="unsupported fields"):
            decode_model_metadata({"model_method": "x", "extra": "x"})
        with pytest.raises(WorkerProtocolError, match="unsupported fields"):
            decode_model_metrics({"sensitivity": 0.1, "extra": "x"})
        with pytest.raises(WorkerProtocolError, match="unsupported fields"):
            decode_runtime_prediction({"workflow_id": "bremen", "extra": "x"})


# ---------------------------------------------------------------------------
# 15. Wrong protocol
# ---------------------------------------------------------------------------


class TestWrongProtocol:
    def test_wrong_protocol_in_request_rejected(self):
        with pytest.raises(WorkerProtocolError, match="protocol"):
            validate_worker_request(_valid_request_data(protocol="bremen.worker.v0"))

    def test_wrong_protocol_in_result_rejected(self):
        with pytest.raises(WorkerProtocolError, match="protocol"):
            validate_worker_result(_valid_ok_result_data(protocol="bremen.worker.v0"))

    def test_missing_protocol_rejected(self):
        data = _valid_request_data()
        del data["protocol"]
        with pytest.raises(WorkerProtocolError, match="missing required field"):
            validate_worker_request(data)


# ---------------------------------------------------------------------------
# 16. Identity/digest mismatch validation
# ---------------------------------------------------------------------------


class TestIdentityDigestMismatch:
    def test_matching_identity_passes(self):
        req = validate_worker_request(_valid_request_data())
        result = validate_worker_result(_valid_ok_result_data())
        validate_result_matches_request(req, result)  # no raise

    def test_mismatched_request_id_rejected(self):
        req = validate_worker_request(_valid_request_data())
        result = validate_worker_result(_valid_ok_result_data(request_id="req-2"))
        with pytest.raises(WorkerProtocolError, match="request_id"):
            validate_result_matches_request(req, result)

    def test_mismatched_model_id_rejected(self):
        req = validate_worker_request(_valid_request_data())
        result = validate_worker_result(_valid_ok_result_data(model_id="other-model"))
        with pytest.raises(WorkerProtocolError, match="model_id"):
            validate_result_matches_request(req, result)

    def test_mismatched_release_digest_rejected(self):
        req = validate_worker_request(_valid_request_data())
        result = validate_worker_result(_valid_ok_result_data(release_digest="b" * 64))
        with pytest.raises(WorkerProtocolError, match="release_digest"):
            validate_result_matches_request(req, result)

    def test_invalid_digest_shape_rejected(self):
        for bad in ("not-hex", "A" * 64, "a" * 63, ""):
            with pytest.raises(WorkerProtocolError, match="release_digest"):
                validate_worker_request(_valid_request_data(release_digest=bad))


# ---------------------------------------------------------------------------
# 17. Unknown operation
# ---------------------------------------------------------------------------


class TestUnknownOperation:
    def test_unknown_operation_in_request_rejected(self):
        with pytest.raises(WorkerProtocolError, match="Unknown operation"):
            validate_worker_request(_valid_request_data(operation="activate"))

    def test_unknown_operation_in_result_rejected(self):
        with pytest.raises(WorkerProtocolError, match="Unknown operation"):
            validate_worker_result(_valid_ok_result_data(operation="activate"))

    def test_empty_model_id_rejected(self):
        with pytest.raises(WorkerProtocolError, match="model_id"):
            validate_worker_request(_valid_request_data(model_id=""))

    def test_empty_request_id_rejected(self):
        with pytest.raises(WorkerProtocolError, match="request_id"):
            validate_worker_request(_valid_request_data(request_id=""))


# ---------------------------------------------------------------------------
# 18. Malformed error code
# ---------------------------------------------------------------------------


class TestMalformedErrorCode:
    def test_unknown_error_code_rejected(self):
        with pytest.raises(WorkerProtocolError, match="Unknown error code"):
            validate_worker_result(
                _valid_error_result_data(error={"code": "SOMETHING_ELSE", "safe_reason": "x"})
            )

    def test_missing_safe_reason_rejected(self):
        with pytest.raises(WorkerProtocolError, match="safe_reason"):
            validate_worker_result(_valid_error_result_data(error={"code": "QC_FAILED"}))

    def test_empty_safe_reason_rejected(self):
        with pytest.raises(WorkerProtocolError, match="safe_reason"):
            validate_worker_result(
                _valid_error_result_data(error={"code": "QC_FAILED", "safe_reason": "   "})
            )

    def test_error_status_requires_error_object(self):
        data = _valid_error_result_data()
        del data["error"]
        with pytest.raises(WorkerProtocolError, match="requires an error object"):
            validate_worker_result(data)

    def test_ok_status_must_not_carry_error(self):
        data = _valid_ok_result_data()
        data["error"] = {"code": "QC_FAILED", "safe_reason": "x"}
        with pytest.raises(WorkerProtocolError, match="must not carry an error"):
            validate_worker_result(data)

    def test_error_status_must_not_carry_payload(self):
        data = _valid_error_result_data()
        data["payload"] = {"probability": 0.5}
        with pytest.raises(WorkerProtocolError, match="must not carry a payload"):
            validate_worker_result(data)

    def test_unknown_status_rejected(self):
        with pytest.raises(WorkerProtocolError, match="Unknown status"):
            validate_worker_result(_valid_ok_result_data(status="pending"))

    @pytest.mark.parametrize("code", sorted(ALLOWED_ERROR_CODES))
    def test_every_allowed_error_code_accepted(self, code):
        result = validate_worker_result(
            _valid_error_result_data(error={"code": code, "safe_reason": "fixed-safe-text"})
        )
        assert result.error.code == code


# ---------------------------------------------------------------------------
# 19. NaN / Infinity rejection
# ---------------------------------------------------------------------------


class TestNonFiniteRejection:
    @pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
    def test_reject_non_json_safe_rejects_non_finite(self, bad_value):
        with pytest.raises(WorkerProtocolError, match="Non-finite"):
            reject_non_json_safe({"x": bad_value})

    def test_nan_in_result_payload_rejected(self):
        with pytest.raises(WorkerProtocolError, match="Non-finite"):
            validate_worker_result(_valid_ok_result_data(payload={"probability": float("nan")}))

    def test_infinity_nested_in_list_rejected(self):
        with pytest.raises(WorkerProtocolError, match="Non-finite"):
            reject_non_json_safe({"values": [1.0, 2.0, float("inf")]})

    def test_encode_json_rejects_nan(self):
        with pytest.raises(WorkerProtocolError, match="Non-finite"):
            encode_json({"x": float("nan")})

    def test_finite_floats_accepted(self):
        reject_non_json_safe({"x": 1.5, "y": -3.25, "z": 0.0})  # no raise

    def test_non_json_safe_type_rejected(self):
        with pytest.raises(WorkerProtocolError, match="Non-JSON-safe"):
            reject_non_json_safe({"x": {1, 2, 3}})

    def test_non_string_key_rejected(self):
        with pytest.raises(WorkerProtocolError, match="Non-string key"):
            reject_non_json_safe({1: "x"})


# ---------------------------------------------------------------------------
# 20. Forbidden/private value leakage
# ---------------------------------------------------------------------------


class TestForbiddenValueLeakage:
    def test_error_object_rejects_traceback_field(self):
        with pytest.raises(WorkerProtocolError, match="unsupported fields"):
            validate_worker_result(
                _valid_error_result_data(
                    error={"code": "QC_FAILED", "safe_reason": "x", "traceback": "Traceback ..."}
                )
            )

    def test_error_object_rejects_path_field(self):
        with pytest.raises(WorkerProtocolError, match="unsupported fields"):
            validate_worker_result(
                _valid_error_result_data(
                    error={"code": "QC_FAILED", "safe_reason": "x", "path": "/tmp/secret"}
                )
            )

    def test_request_rejects_unknown_top_level_field(self):
        with pytest.raises(WorkerProtocolError, match="unsupported fields"):
            validate_worker_request(_valid_request_data(s3_credentials="leak"))

    def test_result_rejects_unknown_top_level_field(self):
        with pytest.raises(WorkerProtocolError, match="unsupported fields"):
            validate_worker_result(_valid_ok_result_data(internal_exception="leak"))

    def test_payload_rejects_unsupported_field_for_operation(self):
        with pytest.raises(WorkerProtocolError, match="unsupported fields"):
            validate_worker_request(
                _valid_request_data(
                    payload={"workflow_id": "bremen", "s3_credentials": "leak"}
                )
            )

    def test_payload_rejects_arbitrary_container_path(self):
        """HARD RULE 3/4: container_path on the wire must only ever
        represent the staged input.h5 file; an arbitrary client-supplied
        filesystem path must never be accepted, even with an otherwise
        valid payload."""
        with pytest.raises(WorkerProtocolError, match="container_path"):
            validate_worker_request(
                _valid_request_data(
                    payload={
                        "workflow_id": "bremen",
                        "container_path": "/private/tmp/secret.h5",
                    }
                )
            )

    @pytest.mark.parametrize(
        "bad_path",
        [
            "/private/tmp/secret.h5",
            "../input.h5",
            "../../etc/passwd",
            "other.h5",
            "input.h5.bak",
            "subdir/input.h5",
        ],
    )
    def test_payload_rejects_every_arbitrary_container_path_form(self, bad_path):
        with pytest.raises(WorkerProtocolError, match="container_path"):
            validate_worker_request(
                _valid_request_data(payload={"workflow_id": "bremen", "container_path": bad_path})
            )

    def test_payload_target_side_must_be_allowed_value(self):
        with pytest.raises(WorkerProtocolError, match="target_side"):
            validate_worker_request(
                _valid_request_data(
                    payload={
                        "workflow_id": "aramina",
                        "patient_id": "x",
                        "target_side": "both",
                        "container_path": STAGED_INPUT_FILENAME,
                    }
                )
            )


# ---------------------------------------------------------------------------
# 21. Deterministic JSON encoding
# ---------------------------------------------------------------------------


class TestDeterministicEncoding:
    def test_encode_worker_request_is_deterministic(self):
        req = validate_worker_request(_valid_request_data())
        encoded_1 = encode_worker_request(req)
        encoded_2 = encode_worker_request(req)
        assert encoded_1 == encoded_2

    def test_encode_worker_result_is_deterministic(self):
        result = validate_worker_result(_valid_ok_result_data())
        encoded_1 = encode_worker_result(result)
        encoded_2 = encode_worker_result(result)
        assert encoded_1 == encoded_2

    def test_encode_json_sorts_keys(self):
        assert encode_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'

    def test_encode_json_is_compact(self):
        encoded = encode_json({"a": 1})
        assert " " not in encoded

    def test_dict_key_order_does_not_affect_encoding(self):
        data_1 = {"a": 1, "b": 2}
        data_2 = {"b": 2, "a": 1}
        assert encode_json(data_1) == encode_json(data_2)


# ---------------------------------------------------------------------------
# Round trip through validate -> encode -> validate
# ---------------------------------------------------------------------------


class TestRequestResultEncodeDecodeRoundTrip:
    def test_request_encode_then_revalidate(self):
        req = validate_worker_request(_valid_request_data())
        encoded = encode_worker_request(req)
        import json as _json

        req_2 = validate_worker_request(_json.loads(encoded))
        assert req_2 == req

    def test_result_encode_then_revalidate(self):
        result = validate_worker_result(_valid_ok_result_data())
        encoded = encode_worker_result(result)
        import json as _json

        result_2 = validate_worker_result(_json.loads(encoded))
        assert result_2 == result

    def test_error_result_encode_then_revalidate(self):
        result = validate_worker_result(_valid_error_result_data())
        encoded = encode_worker_result(result)
        import json as _json

        result_2 = validate_worker_result(_json.loads(encoded))
        assert result_2 == result


# ---------------------------------------------------------------------------
# 22. Module remains platform/science independent
# ---------------------------------------------------------------------------


class TestImportBoundary:
    def test_module_imports_no_platform_or_science_code(self):
        modules = _ast_import_modules(MODULE_PATH)
        forbidden_prefixes = (
            "bremen.platform",
            "bremen.model_packages",
            "bremen.api",
            "boto3",
            "botocore",
            "fastapi",
            "uvicorn",
            "joblib",
            "sklearn",
            "h5py",
        )
        for module in modules:
            for prefix in forbidden_prefixes:
                assert not module.startswith(prefix), (
                    f"worker_protocol.py imports {module!r}, which starts "
                    f"with forbidden prefix {prefix!r}"
                )

    def test_module_only_imports_sibling_contracts_and_stdlib(self):
        modules = _ast_import_modules(MODULE_PATH)
        allowed_bremen_prefixes = ("bremen.contracts",)
        for module in modules:
            if module.startswith("bremen"):
                assert any(module.startswith(p) for p in allowed_bremen_prefixes), (
                    f"worker_protocol.py imports {module!r}, which is not a "
                    "sibling contracts module"
                )

    def test_module_imports_successfully(self):
        import bremen.contracts.worker_protocol as mod

        assert mod.PROTOCOL_ID == "bremen.worker.v1"


# ---------------------------------------------------------------------------
# Review fix (IR02-PROTOCOL-MODELINPUT): explicit ModelInput transport
# ---------------------------------------------------------------------------


def _bremen_predict_payload(**overrides: Any) -> dict[str, Any]:
    """A representative Bremen ``predict`` payload: the raw-container path
    (B2/B3) uses only ``workflow_id`` + ``container_path``; it does not use
    ``canonical``/``canonical_metadata`` at all (``BremenRuntime`` builds
    its own canonical state from the staged H5 directly).
    """
    data = {
        "workflow_id": "bremen",
        "patient_id": "",
        "target_side": "",
        "container_path": STAGED_INPUT_FILENAME,
        "parameters": {},
    }
    data.update(overrides)
    return data


def _aramina_predict_payload(**overrides: Any) -> dict[str, Any]:
    """A representative Aramina ``predict`` payload: Aramina's
    ``validate_model_input`` requires ``canonical`` to be non-None before
    preprocessing, so its wire payload carries the explicit, JSON-safe
    ``canonical_metadata`` block (never the raw measurement arrays).
    """
    data = {
        "workflow_id": "aramina",
        "patient_id": "Nova_227",
        "target_side": "left",
        "container_path": STAGED_INPUT_FILENAME,
        "parameters": {"analysis_author": "smoke test", "prediction_comment": ""},
        "canonical_metadata": {
            "source_layout": "xrd-session",
            "source_layout_version": "0.3",
            "source_checksum": "c" * 64,
            "calibration_provenance": "none",
            "calibration_metadata": {},
        },
    }
    data.update(overrides)
    return data


class TestModelInputTransport:
    """Required test cases #1-#6 from the review-fix task: validate/predict
    payloads with a staged container_path, Bremen/Aramina representative
    round trips, arbitrary-path rejection, and missing-required-subfield
    rejection for ``canonical_metadata``.
    """

    # --- 1 & 2: validate / predict payload with staged container_path ---

    def test_validate_payload_with_staged_container_path(self):
        req = validate_worker_request(
            _valid_request_data(operation="validate", payload=_bremen_predict_payload())
        )
        assert req.payload["container_path"] == STAGED_INPUT_FILENAME

    def test_predict_payload_with_staged_container_path(self):
        req = validate_worker_request(
            _valid_request_data(operation="predict", payload=_bremen_predict_payload())
        )
        assert req.payload["container_path"] == STAGED_INPUT_FILENAME

    # --- 3: Bremen-required canonical metadata round trip (none required) ---

    def test_bremen_model_input_payload_round_trip(self):
        payload = decode_model_input_payload(_bremen_predict_payload(), operation="predict")
        assert payload == ModelInputPayload(
            workflow_id="bremen", patient_id="", target_side="",
            container_path=STAGED_INPUT_FILENAME, parameters={}, canonical_metadata=None,
        )
        encoded = encode_model_input_payload(payload)
        assert encoded == _bremen_predict_payload()
        # The whole point: no measurements/canonical object ever appears.
        assert "measurements" not in encoded
        assert "canonical" not in encoded

    # --- 4: Aramina-required canonical metadata round trip ---

    def test_aramina_model_input_payload_round_trip(self):
        raw = _aramina_predict_payload()
        payload = decode_model_input_payload(raw, operation="predict")
        assert payload.workflow_id == "aramina"
        assert payload.target_side == "left"
        assert payload.canonical_metadata == CanonicalMetadata(
            source_layout="xrd-session", source_layout_version="0.3",
            source_checksum="c" * 64, calibration_provenance="none",
            calibration_metadata={},
        )
        encoded = encode_model_input_payload(payload)
        assert encoded == raw
        assert "measurements" not in encoded
        assert "canonical" not in encoded

    def test_aramina_payload_validates_through_full_request_envelope(self):
        req = validate_worker_request(
            _valid_request_data(
                operation="predict", model_id="aramina-target-breast-risk-0-2-13",
                payload=_aramina_predict_payload(),
            )
        )
        assert req.payload["canonical_metadata"]["calibration_provenance"] == "none"

    # --- 5: arbitrary container path rejected (see also TestForbiddenValueLeakage) ---

    def test_decode_model_input_payload_rejects_arbitrary_container_path(self):
        with pytest.raises(WorkerProtocolError, match="container_path"):
            decode_model_input_payload(
                _bremen_predict_payload(container_path="/private/tmp/secret.h5"),
                operation="predict",
            )

    # --- 6: missing required canonical metadata rejected where present-but-incomplete ---

    @pytest.mark.parametrize(
        "missing_field",
        ["source_layout", "source_layout_version", "source_checksum", "calibration_provenance"],
    )
    def test_canonical_metadata_missing_required_field_rejected(self, missing_field):
        payload = _aramina_predict_payload()
        del payload["canonical_metadata"][missing_field]
        with pytest.raises(WorkerProtocolError, match="canonical_metadata"):
            decode_model_input_payload(payload, operation="predict")

    def test_canonical_metadata_unknown_field_rejected(self):
        payload = _aramina_predict_payload()
        payload["canonical_metadata"]["extra_field"] = "leak"
        with pytest.raises(WorkerProtocolError, match="canonical_metadata"):
            decode_model_input_payload(payload, operation="predict")

    def test_canonical_metadata_invalid_calibration_provenance_rejected(self):
        payload = _aramina_predict_payload()
        payload["canonical_metadata"]["calibration_provenance"] = "unknown_method"
        with pytest.raises(WorkerProtocolError, match="calibration_provenance"):
            decode_model_input_payload(payload, operation="predict")

    def test_canonical_metadata_invalid_source_checksum_rejected(self):
        payload = _aramina_predict_payload()
        payload["canonical_metadata"]["source_checksum"] = "not-a-hash"
        with pytest.raises(WorkerProtocolError, match="source_checksum"):
            decode_model_input_payload(payload, operation="predict")

    def test_canonical_metadata_must_be_object(self):
        payload = _aramina_predict_payload()
        payload["canonical_metadata"] = "not-an-object"
        with pytest.raises(WorkerProtocolError, match="canonical_metadata"):
            decode_model_input_payload(payload, operation="predict")

    def test_canonical_metadata_absent_is_valid_for_bremen(self):
        """Bremen's raw-container predict never needs canonical_metadata at
        all — absence must not be treated as 'missing required field'."""
        payload = decode_model_input_payload(_bremen_predict_payload(), operation="predict")
        assert payload.canonical_metadata is None

    def test_calibration_metadata_values_must_be_strings(self):
        payload = _aramina_predict_payload()
        payload["canonical_metadata"]["calibration_metadata"] = {"k": 123}
        with pytest.raises(WorkerProtocolError, match="calibration_metadata"):
            decode_model_input_payload(payload, operation="predict")

    def test_workflow_id_required_for_validate_and_predict(self):
        for operation in ("validate", "predict"):
            with pytest.raises(WorkerProtocolError, match="workflow_id"):
                decode_model_input_payload({}, operation=operation)

    def test_requirements_operation_rejects_model_input_payload_fields(self):
        with pytest.raises(WorkerProtocolError, match="unsupported fields"):
            decode_model_input_payload({"workflow_id": "bremen"}, operation="requirements")


# ---------------------------------------------------------------------------
# Review fix (IR02-CODEC-TYPE-COERCION): strict decoding, no str()/int()/
# float()/bool() coercion of wrong JSON types; boolean-vs-integer edge cases.
# ---------------------------------------------------------------------------


class TestStrictDecodeTypeValidation:
    """Required test cases #7-#8 from the review-fix task, directly
    reproducing the reviewer's named counter-examples."""

    # -- decode_source_metadata --

    @pytest.mark.parametrize(
        "field_name", ["referring_physician", "scan_date_time", "operator_id", "hardware_version"],
    )
    def test_source_metadata_string_fields_reject_non_string(self, field_name):
        with pytest.raises(WorkerProtocolError, match=field_name):
            decode_source_metadata({field_name: 123})

    def test_source_metadata_does_not_stringify_int(self):
        """Regression for IR02-CODEC-TYPE-COERCION: previously
        ``decode_source_metadata({'referring_physician': 123})`` silently
        produced ``'123'`` via ``str(...)``; it must now raise."""
        with pytest.raises(WorkerProtocolError):
            decode_source_metadata({"referring_physician": 123})
        with pytest.raises(WorkerProtocolError):
            decode_source_metadata({"referring_physician": True})

    def test_source_metadata_explicit_null_uses_default_not_coercion(self):
        """An explicit JSON ``null`` for an optional string field means
        'absent' (-> the documented default ""), which is different from a
        wrong-type value like ``123`` — this is a default-substitution, not
        a ``str(...)`` coercion of an actual value."""
        value = decode_source_metadata({"referring_physician": None})
        assert value.referring_physician == ""

    def test_source_metadata_missing_fields_default_to_empty_string(self):
        value = decode_source_metadata({})
        assert value.referring_physician == ""
        assert value.scan_date_time == ""
        assert value.operator_id == ""
        assert value.hardware_version == ""

    def test_source_metadata_patient_age_rejects_bool(self):
        """Boolean-vs-integer edge case: ``True``/``False`` are technically
        ``int`` subclasses in Python but must never satisfy a numeric field."""
        with pytest.raises(WorkerProtocolError, match="patient_age"):
            decode_source_metadata({"patient_age": True})
        with pytest.raises(WorkerProtocolError, match="patient_age"):
            decode_source_metadata({"patient_age": False})

    def test_source_metadata_patient_age_accepts_real_numbers(self):
        assert decode_source_metadata({"patient_age": 44}).patient_age == 44
        assert decode_source_metadata({"patient_age": 44.5}).patient_age == 44.5
        assert decode_source_metadata({"patient_age": None}).patient_age is None

    def test_source_metadata_must_be_object(self):
        with pytest.raises(WorkerProtocolError, match="JSON object"):
            decode_source_metadata("not-an-object")  # type: ignore[arg-type]

    # -- decode_model_metadata --

    def test_model_metadata_rejects_non_string_model_method(self):
        with pytest.raises(WorkerProtocolError, match="model_method"):
            decode_model_metadata({"model_method": 123})

    def test_model_metadata_does_not_stringify_int(self):
        """Regression: previously ``decode_model_metadata({'model_method': 123})``
        silently produced ``'123'``; it must now raise."""
        with pytest.raises(WorkerProtocolError):
            decode_model_metadata({"model_method": 123})

    def test_model_metadata_rejects_bool_model_method(self):
        with pytest.raises(WorkerProtocolError, match="model_method"):
            decode_model_metadata({"model_method": True})

    # -- decode_model_metrics --

    def test_model_metrics_rejects_bool_sensitivity(self):
        with pytest.raises(WorkerProtocolError, match="sensitivity"):
            decode_model_metrics({"sensitivity": True})

    def test_model_metrics_rejects_bool_specificity(self):
        with pytest.raises(WorkerProtocolError, match="specificity"):
            decode_model_metrics({"specificity": False})

    def test_model_metrics_rejects_string_number(self):
        with pytest.raises(WorkerProtocolError, match="sensitivity"):
            decode_model_metrics({"sensitivity": "0.9"})

    def test_model_metrics_accepts_real_numbers_and_null(self):
        value = decode_model_metrics({"sensitivity": 0.9, "specificity": None})
        assert value.sensitivity == 0.9
        assert value.specificity is None

    # -- decode_runtime_prediction --

    def test_runtime_prediction_rejects_int_workflow_id(self):
        """Direct reproduction of the reviewer's named example:
        ``decode_runtime_prediction({'workflow_id': 123})`` must raise, not
        silently produce ``workflow_id='123'``."""
        with pytest.raises(WorkerProtocolError, match="workflow_id"):
            decode_runtime_prediction({"workflow_id": 123})

    def test_runtime_prediction_rejects_bool_workflow_id(self):
        with pytest.raises(WorkerProtocolError, match="workflow_id"):
            decode_runtime_prediction({"workflow_id": True})

    def test_runtime_prediction_rejects_empty_workflow_id(self):
        with pytest.raises(WorkerProtocolError, match="workflow_id"):
            decode_runtime_prediction({"workflow_id": ""})

    def test_runtime_prediction_rejects_non_string_model_id(self):
        with pytest.raises(WorkerProtocolError, match="model_id"):
            decode_runtime_prediction({"workflow_id": "bremen", "model_id": 42})

    def test_runtime_prediction_rejects_non_string_model_version(self):
        with pytest.raises(WorkerProtocolError, match="model_version"):
            decode_runtime_prediction({"workflow_id": "bremen", "model_version": 1.0})

    def test_runtime_prediction_rejects_non_object_source_metadata(self):
        with pytest.raises(WorkerProtocolError, match="source_metadata"):
            decode_runtime_prediction({"workflow_id": "bremen", "source_metadata": "nope"})

    def test_runtime_prediction_rejects_non_object_model_metadata(self):
        with pytest.raises(WorkerProtocolError, match="model_metadata"):
            decode_runtime_prediction({"workflow_id": "bremen", "model_metadata": 1})

    def test_runtime_prediction_rejects_non_object_model_metrics(self):
        with pytest.raises(WorkerProtocolError, match="model_metrics"):
            decode_runtime_prediction({"workflow_id": "bremen", "model_metrics": []})

    def test_runtime_prediction_must_be_object(self):
        with pytest.raises(WorkerProtocolError, match="JSON object"):
            decode_runtime_prediction([1, 2, 3])  # type: ignore[arg-type]

    def test_runtime_prediction_does_not_stringify_model_id(self):
        """Regression: previously ``model_id=str(data.get('model_id', ''))``
        would turn ``42`` into ``'42'`` silently."""
        with pytest.raises(WorkerProtocolError):
            decode_runtime_prediction({"workflow_id": "bremen", "model_id": 42})

    # -- decode_model_validation (already strict before this review; keep covered) --

    def test_model_validation_rejects_non_bool_compatible(self):
        with pytest.raises(WorkerProtocolError, match="compatible"):
            decode_model_validation({"compatible": "false"})

    def test_model_validation_rejects_int_compatible(self):
        with pytest.raises(WorkerProtocolError, match="compatible"):
            decode_model_validation({"compatible": 1})

    def test_model_validation_must_be_object(self):
        with pytest.raises(WorkerProtocolError, match="JSON object"):
            decode_model_validation(None)  # type: ignore[arg-type]

    # -- named reviewer counter-examples reproduced verbatim, as a single
    #    consolidated regression test --

    def test_named_reviewer_counterexamples_all_rejected(self):
        with pytest.raises(WorkerProtocolError):
            decode_runtime_prediction({"workflow_id": 123})
        with pytest.raises(WorkerProtocolError):
            decode_source_metadata({"referring_physician": 123})
        with pytest.raises(WorkerProtocolError):
            decode_model_metadata({"model_method": 123})


# ---------------------------------------------------------------------------
# #9/#10: existing codecs and full contract-test compatibility
# ---------------------------------------------------------------------------


class TestExistingCodecsStillRoundTrip:
    def test_runtime_prediction_round_trip_still_works_after_strict_fix(self):
        prediction = RuntimePrediction(
            workflow_id="bremen",
            model_id="bremen-paper-reference-v0-2-0",
            model_version="0.2.0-paper-reference",
            result={"probability": 0.7726940329943811, "prediction": 1},
            safe_reason=None,
            source_metadata=SourceMetadata(
                patient_age=44, referring_physician="", scan_date_time="2025-05-28T10:19:55",
                operator_id="backfill", hardware_version="v1.0.1", eoscan_version=None,
            ),
            model_metadata=ModelMetadata(model_method="median_imputer_standard_scaler_balanced_logistic_regression"),
            model_metrics=ModelMetrics(sensitivity=0.9516129032258065, specificity=0.391304347826087),
        )
        encoded = encode_runtime_prediction(prediction)
        decoded = decode_runtime_prediction(encoded)
        assert decoded == prediction

    def test_model_validation_round_trip_still_works(self):
        value = ModelValidation(compatible=False, safe_reason="requires_exactly_3_left_3_right")
        assert decode_model_validation(encode_model_validation(value)) == value

    def test_model_metrics_round_trip_still_works(self):
        value = ModelMetrics(sensitivity=0.8175, specificity=None)
        assert decode_model_metrics(encode_model_metrics(value)) == value


# ---------------------------------------------------------------------------
# Precommit review-fix pass 2: strict encoding, JSON-safe mappings, staged
# input contract. These are the blockers named in the third precommit review.
# ---------------------------------------------------------------------------


def _requirements(**overrides: Any) -> ModelRequirements:
    data: dict[str, Any] = {
        "workflow_id": "bremen",
        "model_id": "bremen-paper-reference-v0-2-0",
        "measurement_sides": (("LEFT", 3), ("RIGHT", 3)),
        "total_measurements": 6,
    }
    data.update(overrides)
    return ModelRequirements(**data)


class TestStrictEncodingModelRequirements:
    """MODELREQUIREMENTS-STRICT-TYPES: encode_model_requirements must reject
    semantically wrong dataclass values instead of emitting them."""

    @pytest.mark.parametrize("bad_value", ["false", "true", 1, 0, None])
    def test_scientifically_certified_must_be_bool(self, bad_value):
        with pytest.raises(WorkerProtocolError, match="scientifically_certified"):
            encode_model_requirements(
                _requirements(scientifically_certified=bad_value)
            )

    @pytest.mark.parametrize("bad_value", ["6", 6.0, True, False, [], {}])
    def test_total_measurements_must_be_int_or_none(self, bad_value):
        with pytest.raises(WorkerProtocolError, match="total_measurements"):
            encode_model_requirements(_requirements(total_measurements=bad_value))

    def test_total_measurements_none_is_allowed(self):
        encoded = encode_model_requirements(_requirements(total_measurements=None))
        assert encoded["total_measurements"] is None

    def test_valid_requirements_still_encode(self):
        encoded = encode_model_requirements(
            _requirements(scientifically_certified=True, total_measurements=6)
        )
        assert encoded["total_measurements"] == 6
        assert encoded["requires_target_side"] is False

    @pytest.mark.parametrize("bad_value", [123, None, "false"])
    def test_requires_target_side_must_be_bool(self, bad_value):
        with pytest.raises(WorkerProtocolError, match="requires_target_side"):
            encode_model_requirements(_requirements(requires_target_side=bad_value))

    @pytest.mark.parametrize("bad_value", [123, True, None])
    def test_workflow_id_must_be_string(self, bad_value):
        with pytest.raises(WorkerProtocolError, match="workflow_id"):
            encode_model_requirements(_requirements(workflow_id=bad_value))

    def test_measurement_sides_count_must_be_int_not_bool(self):
        with pytest.raises(WorkerProtocolError, match="count"):
            encode_model_requirements(
                _requirements(measurement_sides=(("LEFT", True),))
            )

    def test_encoder_requires_model_requirements_instance(self):
        with pytest.raises(WorkerProtocolError, match="ModelRequirements instance"):
            encode_model_requirements({"workflow_id": "bremen"})  # type: ignore[arg-type]


class TestStrictEncodingOtherCodecs:
    """Strict, fail-closed encoding for every other direct codec."""

    @pytest.mark.parametrize("bad_value", ["false", "true", 1, 0, None])
    def test_model_validation_compatible_must_be_bool(self, bad_value):
        # __post_init__ does not enforce types; encoding must.
        with pytest.raises(WorkerProtocolError, match="compatible"):
            encode_model_validation(ModelValidation(compatible=bad_value))

    @pytest.mark.parametrize("bad_value", [123, True])
    def test_model_validation_safe_reason_must_be_string_or_none(self, bad_value):
        with pytest.raises(WorkerProtocolError, match="safe_reason"):
            encode_model_validation(
                ModelValidation(compatible=True, safe_reason=bad_value)
            )

    @pytest.mark.parametrize(
        "field_name",
        ["referring_physician", "scan_date_time", "operator_id", "hardware_version"],
    )
    def test_source_metadata_string_fields_must_be_string(self, field_name):
        value = SourceMetadata(**{field_name: 123})
        with pytest.raises(WorkerProtocolError, match=field_name):
            encode_source_metadata(value)

    def test_source_metadata_patient_age_must_not_be_bool(self):
        with pytest.raises(WorkerProtocolError, match="patient_age"):
            encode_source_metadata(SourceMetadata(patient_age=True))

    @pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
    def test_source_metadata_patient_age_must_be_finite(self, bad_value):
        with pytest.raises(WorkerProtocolError, match="patient_age"):
            encode_source_metadata(SourceMetadata(patient_age=bad_value))

    def test_source_metadata_eoscan_version_must_be_string_or_none(self):
        with pytest.raises(WorkerProtocolError, match="eoscan_version"):
            encode_source_metadata(SourceMetadata(eoscan_version=123))

    def test_model_metadata_model_method_must_be_string(self):
        with pytest.raises(WorkerProtocolError, match="model_method"):
            encode_model_metadata(ModelMetadata(model_method=123))

    @pytest.mark.parametrize("name", ["sensitivity", "specificity"])
    def test_model_metrics_reject_bool_and_string(self, name):
        for bad_value in (True, False, "0.9"):
            with pytest.raises(WorkerProtocolError, match=name):
                encode_model_metrics(ModelMetrics(**{name: bad_value}))

    @pytest.mark.parametrize("name", ["sensitivity", "specificity"])
    @pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
    def test_model_metrics_reject_non_finite(self, name, bad_value):
        with pytest.raises(WorkerProtocolError, match=name):
            encode_model_metrics(ModelMetrics(**{name: bad_value}))

    @pytest.mark.parametrize("bad_value", [123, True])
    def test_runtime_prediction_workflow_id_must_be_non_empty_string(self, bad_value):
        with pytest.raises(WorkerProtocolError, match="workflow_id"):
            encode_runtime_prediction(
                RuntimePrediction(workflow_id=bad_value)  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize("field_name", ["model_id", "model_version"])
    def test_runtime_prediction_identity_fields_must_be_string(self, field_name):
        with pytest.raises(WorkerProtocolError, match=field_name):
            encode_runtime_prediction(
                RuntimePrediction(workflow_id="bremen", **{field_name: 123})
            )

    def test_runtime_prediction_result_must_be_mapping(self):
        with pytest.raises(WorkerProtocolError, match="result"):
            encode_runtime_prediction(
                RuntimePrediction(workflow_id="bremen", result=["not", "a", "mapping"])  # type: ignore[arg-type]
            )

    def test_runtime_prediction_safe_reason_must_be_string_or_none(self):
        with pytest.raises(WorkerProtocolError, match="safe_reason"):
            encode_runtime_prediction(
                RuntimePrediction(workflow_id="bremen", safe_reason=123)  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize(
        "field_name", ["source_metadata", "model_metadata", "model_metrics"]
    )
    def test_runtime_prediction_nested_metadata_must_be_typed(self, field_name):
        with pytest.raises(WorkerProtocolError, match=field_name):
            encode_runtime_prediction(
                RuntimePrediction(workflow_id="bremen", **{field_name: "not-a-dataclass"})
            )

    def test_encode_worker_request_revalidates_invalid_fields(self):
        # A payload-level NaN slipped past construction must be rejected.
        bad = WorkerRequest(
            protocol=PROTOCOL_ID,
            request_id="req-1",
            operation="predict",
            model_id="bremen-paper-reference-v0-2-0",
            release_digest=DIGEST,
            payload={"workflow_id": "bremen", "container_path": STAGED_INPUT_FILENAME,
                     "parameters": {"x": float("nan")}},
        )
        with pytest.raises(WorkerProtocolError, match="Non-finite"):
            encode_worker_request(bad)

    def test_encode_worker_result_rejects_invalid_error_code(self):
        result = WorkerResult(
            protocol=PROTOCOL_ID,
            request_id="req-1",
            operation="predict",
            model_id="bremen-paper-reference-v0-2-0",
            release_digest=DIGEST,
            status=RESULT_STATUS_ERROR,
            error=WorkerError(code="NOT_ALLOWED", safe_reason="x"),
        )
        with pytest.raises(WorkerProtocolError, match="error code"):
            encode_worker_result(result)

    def test_encode_worker_result_rejects_non_worker_error(self):
        result = WorkerResult(
            protocol=PROTOCOL_ID,
            request_id="req-1",
            operation="predict",
            model_id="bremen-paper-reference-v0-2-0",
            release_digest=DIGEST,
            status=RESULT_STATUS_ERROR,
            error={"code": "QC_FAILED", "safe_reason": "x"},  # type: ignore[arg-type]
        )
        with pytest.raises(WorkerProtocolError, match="WorkerError"):
            encode_worker_result(result)


class TestJsonSafeMappings:
    """CODEC-JSON-SAFETY: recursive JSON-safety/finite-number guard applies
    to every mapping-bearing codec, including parameters and result."""

    def _payload(self, **overrides: Any) -> dict[str, Any]:
        data = {"workflow_id": "bremen", "container_path": STAGED_INPUT_FILENAME}
        data.update(overrides)
        return data

    @pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
    def test_parameters_non_finite_rejected_by_request_validator(self, bad_value):
        with pytest.raises(WorkerProtocolError, match="Non-finite"):
            validate_worker_request(
                _valid_request_data(
                    payload=self._payload(parameters={"x": bad_value})
                )
            )

    @pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
    def test_parameters_non_finite_rejected_by_decoder(self, bad_value):
        with pytest.raises(WorkerProtocolError, match="Non-finite"):
            decode_model_input_payload(
                self._payload(parameters={"x": bad_value}), operation="predict"
            )

    @pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
    def test_parameters_non_finite_rejected_by_encoder(self, bad_value):
        with pytest.raises(WorkerProtocolError, match="Non-finite"):
            encode_model_input_payload(
                ModelInputPayload(
                    workflow_id="bremen",
                    container_path=STAGED_INPUT_FILENAME,
                    parameters={"x": bad_value},
                )
            )

    def test_nested_nan_inside_parameters_rejected(self):
        with pytest.raises(WorkerProtocolError, match="Non-finite"):
            decode_model_input_payload(
                self._payload(parameters={"nested": {"values": [1.0, float("nan")]}}),
                operation="predict",
            )

    def test_custom_python_object_inside_parameters_rejected(self):
        with pytest.raises(WorkerProtocolError, match="Non-JSON-safe"):
            decode_model_input_payload(
                self._payload(parameters={"x": object()}), operation="predict"
            )
        with pytest.raises(WorkerProtocolError, match="Non-JSON-safe"):
            encode_model_input_payload(
                ModelInputPayload(
                    workflow_id="bremen",
                    container_path=STAGED_INPUT_FILENAME,
                    parameters={"x": object()},
                )
            )

    def test_bytes_inside_parameters_rejected(self):
        with pytest.raises(WorkerProtocolError, match="bytes"):
            decode_model_input_payload(
                self._payload(parameters={"x": b"raw"}), operation="predict"
            )

    def test_set_inside_parameters_rejected(self):
        with pytest.raises(WorkerProtocolError, match="Non-JSON-safe"):
            decode_model_input_payload(
                self._payload(parameters={"x": {1, 2}}), operation="predict"
            )

    def test_non_string_key_inside_parameters_rejected(self):
        with pytest.raises(WorkerProtocolError, match="Non-string key"):
            decode_model_input_payload(
                self._payload(parameters={1: "x"}), operation="predict"
            )

    @pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
    def test_result_non_finite_rejected_by_decoder(self, bad_value):
        with pytest.raises(WorkerProtocolError, match="Non-finite"):
            decode_runtime_prediction(
                {"workflow_id": "bremen", "result": {"probability": bad_value}}
            )

    @pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
    def test_result_non_finite_rejected_by_encoder(self, bad_value):
        with pytest.raises(WorkerProtocolError, match="Non-finite"):
            encode_runtime_prediction(
                RuntimePrediction(workflow_id="bremen", result={"probability": bad_value})
            )

    def test_nested_nan_inside_result_rejected(self):
        with pytest.raises(WorkerProtocolError, match="Non-finite"):
            decode_runtime_prediction(
                {
                    "workflow_id": "bremen",
                    "result": {"nested": {"values": [1.0, float("nan")]}},
                }
            )

    def test_custom_python_object_inside_result_rejected(self):
        with pytest.raises(WorkerProtocolError, match="Non-JSON-safe"):
            decode_runtime_prediction(
                {"workflow_id": "bremen", "result": {"x": object()}}
            )

    def test_bytes_inside_result_rejected(self):
        with pytest.raises(WorkerProtocolError, match="bytes"):
            decode_runtime_prediction(
                {"workflow_id": "bremen", "result": {"x": b"raw"}}
            )

    def test_non_string_key_inside_result_rejected(self):
        with pytest.raises(WorkerProtocolError, match="Non-string key"):
            decode_runtime_prediction(
                {"workflow_id": "bremen", "result": {1: "x"}}
            )

    @pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
    def test_decode_model_metrics_rejects_non_finite(self, bad_value):
        with pytest.raises(WorkerProtocolError, match="Non-finite"):
            decode_model_metrics({"sensitivity": bad_value})

    def test_decode_source_metadata_rejects_nan_age(self):
        with pytest.raises(WorkerProtocolError, match="Non-finite"):
            decode_source_metadata({"patient_age": float("nan")})

    def test_decode_model_validation_rejects_arbitrary_object(self):
        with pytest.raises(WorkerProtocolError, match="Non-JSON-safe"):
            decode_model_validation({"compatible": True, "safe_reason": object()})

    def test_decode_model_metadata_rejects_non_string_key(self):
        with pytest.raises(WorkerProtocolError, match="Non-string key"):
            decode_model_metadata({1: "x"})


class TestStagedInputContract:
    """MODELINPUT-CONTAINER-REQUIRED: validate and predict require exactly
    the staged ``input.h5`` reference; requirements does not."""

    def _payload(self, **overrides: Any) -> dict[str, Any]:
        data = {"workflow_id": "bremen", "container_path": STAGED_INPUT_FILENAME}
        data.update(overrides)
        return data

    @pytest.mark.parametrize("operation", ["validate", "predict"])
    def test_missing_container_path_rejected_by_request_validator(self, operation):
        with pytest.raises(WorkerProtocolError, match="container_path"):
            validate_worker_request(
                _valid_request_data(
                    operation=operation, payload={"workflow_id": "bremen"}
                )
            )

    @pytest.mark.parametrize("operation", ["validate", "predict"])
    def test_missing_container_path_rejected_by_decoder(self, operation):
        with pytest.raises(WorkerProtocolError, match="container_path"):
            decode_model_input_payload({"workflow_id": "bremen"}, operation=operation)

    @pytest.mark.parametrize("operation", ["validate", "predict"])
    def test_empty_container_path_rejected(self, operation):
        with pytest.raises(WorkerProtocolError, match="container_path"):
            validate_worker_request(
                _valid_request_data(
                    operation=operation, payload=self._payload(container_path="")
                )
            )
        with pytest.raises(WorkerProtocolError, match="container_path"):
            decode_model_input_payload(self._payload(container_path=""), operation=operation)
        with pytest.raises(WorkerProtocolError, match="container_path"):
            encode_model_input_payload(
                ModelInputPayload(workflow_id="bremen", container_path="")
            )

    @pytest.mark.parametrize("operation", ["validate", "predict"])
    def test_none_container_path_rejected(self, operation):
        with pytest.raises(WorkerProtocolError, match="container_path"):
            validate_worker_request(
                _valid_request_data(
                    operation=operation, payload=self._payload(container_path=None)
                )
            )
        with pytest.raises(WorkerProtocolError, match="container_path"):
            decode_model_input_payload(
                self._payload(container_path=None), operation=operation
            )
        with pytest.raises(WorkerProtocolError, match="container_path"):
            encode_model_input_payload(
                ModelInputPayload(workflow_id="bremen", container_path=None)  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize(
        "bad_path",
        [
            "/private/tmp/secret.h5",
            "/input.h5",
            "../input.h5",
            "../../etc/passwd",
            "other.h5",
            "input.h5.bak",
            "subdir/input.h5",
            "input.H5",
            True,
            123,
        ],
    )
    @pytest.mark.parametrize("operation", ["validate", "predict"])
    def test_every_invalid_container_path_rejected(self, bad_path, operation):
        with pytest.raises(WorkerProtocolError, match="container_path"):
            validate_worker_request(
                _valid_request_data(
                    operation=operation, payload=self._payload(container_path=bad_path)
                )
            )
        with pytest.raises(WorkerProtocolError, match="container_path"):
            decode_model_input_payload(
                self._payload(container_path=bad_path), operation=operation
            )

    @pytest.mark.parametrize("operation", ["validate", "predict"])
    def test_staged_input_h5_succeeds(self, operation):
        request = validate_worker_request(
            _valid_request_data(operation=operation, payload=self._payload())
        )
        assert request.payload["container_path"] == STAGED_INPUT_FILENAME
        payload = decode_model_input_payload(self._payload(), operation=operation)
        assert payload.container_path == STAGED_INPUT_FILENAME
        encoded = encode_model_input_payload(payload)
        assert encoded["container_path"] == STAGED_INPUT_FILENAME

    def test_requirements_operation_does_not_require_container_path(self):
        request = validate_worker_request(
            _valid_request_data(operation="requirements", payload={})
        )
        assert request.operation == "requirements"
        assert "container_path" not in request.payload
