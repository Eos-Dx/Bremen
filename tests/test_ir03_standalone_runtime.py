"""IR-03 standalone runtime / entrypoint contract tests (synthetic only).

No real artifact, H5 fixture, platform module or network call participates.
The real five-model parity evidence is in ``tests/test_ir03_parity.py`` and
``.project-memory/pr/0167-ir-03-standalone-model-releases/PARITY_EVIDENCE.md``.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from bremen.contracts.model_runtime import (
    ModelInputInvalidError,
    ModelPreprocessingFailedError,
    ModelRequirements,
    ModelValidation,
    RuntimePrediction,
)
from bremen.contracts.worker_protocol import (
    PROTOCOL_ID,
    WorkerProtocolError,
    validate_worker_request,
)
from bremen.ml_plugin.entrypoint import main as entrypoint_main
from bremen.ml_plugin.errors import PluginReleaseError
from bremen.ml_plugin.inference import execute_operation, runtime_for_requirements
from bremen.ml_plugin.variants import variant_spec


def _make_release(tmp_path: Path, variant: str = "b2") -> tuple[Path, dict]:
    spec = variant_spec(variant)
    release = tmp_path / "release"
    (release / "configs").mkdir(parents=True)
    (release / "model").mkdir()
    (release / "model" / "model.joblib").write_bytes(b"")
    (release / "manifest.json").write_text("{}\n", encoding="utf-8")
    config = {
        "schema_version": "bremen.ml-plugin.runtime.v1",
        "release_id": spec.release_id,
        "variant": spec.key,
        "workflow_id": spec.workflow_id,
        "artifact": {
            "relative_path": "model/model.joblib",
            "sha256": spec.artifact_checksum,
            "model_id": spec.model_id,
            "model_version": spec.model_version,
        },
        "preprocessing_environment": {},
    }
    (release / "configs" / "runtime.json").write_text(
        json.dumps(config), encoding="utf-8",
    )
    return release, config


def _request(
    release: Path, spec_key: str = "b2", *, operation: str = "predict",
    payload: dict | None = None,
):
    spec = variant_spec(spec_key)
    digest = hashlib.sha256((release / "manifest.json").read_bytes()).hexdigest()
    return validate_worker_request(
        {
            "protocol": PROTOCOL_ID,
            "request_id": "req-ir03",
            "operation": operation,
            "model_id": spec.model_id,
            "release_digest": digest,
            "payload": payload
            if payload is not None
            else {"workflow_id": spec.workflow_id, "container_path": "input.h5"},
        }
    )


def _job(tmp_path: Path, *, with_input: bool = True) -> Path:
    job = tmp_path / "job"
    job.mkdir()
    if with_input:
        (job / "input.h5").write_bytes(b"staged-input")
    return job


class StubRuntime:
    def __init__(self, *, validation=None, prediction=None, exc=None):
        self._validation = validation or ModelValidation(compatible=True)
        self._prediction = prediction
        self._exc = exc
        self.seen_input = None

    def model_requirements(self):
        return ModelRequirements(workflow_id="bremen", model_id="x")

    def validate_model_input(self, model_input):
        self.seen_input = model_input
        return self._validation

    def predict_model(self, model_input, on_features=None):
        self.seen_input = model_input
        if self._exc is not None:
            raise self._exc
        return self._prediction


def _prediction() -> RuntimePrediction:
    return RuntimePrediction(
        workflow_id="bremen",
        model_id="bremen-paper-reference-v0-2-0",
        model_version="0.2.0-paper-reference",
        result={"probability": 0.5, "prediction": 1},
    )


class TestRequirements:
    @pytest.mark.parametrize("variant", ["a1", "a2", "b1", "b2", "b3"])
    def test_requirements_needs_no_staged_input(self, tmp_path, variant):
        release, _ = _make_release(tmp_path, variant)
        result = execute_operation(
            _request(release, variant, operation="requirements", payload={}),
            release_dir=str(release),
            job_dir=str(tmp_path / "does-not-exist"),
        )
        assert result.status == "ok"
        assert result.payload["workflow_id"] == variant_spec(variant).workflow_id
        assert result.payload["model_version"] == variant_spec(variant).model_version

    def test_requirements_does_not_load_artifact(self, tmp_path):
        release, _ = _make_release(tmp_path, "b2")
        calls = []

        def loader(*args, **kwargs):
            calls.append(args)
            raise AssertionError("artifact must not be loaded for requirements")

        result = execute_operation(
            _request(release, "b2", operation="requirements", payload={}),
            release_dir=str(release),
            job_dir=str(tmp_path / "job"),
            runtime_loader=loader,
        )
        assert result.status == "ok"
        assert calls == []

    def test_requirements_operation_rejects_payload_fields(self):
        with pytest.raises(WorkerProtocolError, match="unsupported fields"):
            validate_worker_request(
                {
                    "protocol": PROTOCOL_ID,
                    "request_id": "req",
                    "operation": "requirements",
                    "model_id": variant_spec("b2").model_id,
                    "release_digest": "a" * 64,
                    "payload": {"container_path": "input.h5"},
                }
            )


class TestValidateAndPredict:
    def test_validate_returns_compatible_verdict(self, tmp_path):
        release, _ = _make_release(tmp_path, "b2")
        job = _job(tmp_path)
        stub = StubRuntime(validation=ModelValidation(compatible=False, safe_reason="shape"))
        result = execute_operation(
            _request(release, "b2", operation="validate"),
            release_dir=str(release),
            job_dir=str(job),
            runtime_loader=lambda *a, **k: stub,
        )
        assert result.status == "ok"
        assert result.payload == {"compatible": False, "safe_reason": "shape"}
        assert stub.seen_input.container_path == str(job / "input.h5")
        assert stub.seen_input.measurements == ()

    def test_predict_returns_contract_encoded_prediction(self, tmp_path):
        release, _ = _make_release(tmp_path, "b2")
        job = _job(tmp_path)
        stub = StubRuntime(prediction=_prediction())
        result = execute_operation(
            _request(release, "b2", operation="predict"),
            release_dir=str(release),
            job_dir=str(job),
            runtime_loader=lambda *a, **k: stub,
        )
        assert result.status == "ok"
        assert result.payload["result"]["probability"] == 0.5
        assert result.payload["workflow_id"] == "bremen"
        assert result.payload["model_version"] == "0.2.0-paper-reference"

    def test_missing_staged_input_is_protocol_error(self, tmp_path):
        release, _ = _make_release(tmp_path, "b2")
        result = execute_operation(
            _request(release, "b2", operation="predict"),
            release_dir=str(release),
            job_dir=str(_job(tmp_path, with_input=False)),
            runtime_loader=lambda *a, **k: StubRuntime(prediction=_prediction()),
        )
        assert result.status == "error"
        assert result.error.code == "PROTOCOL_ERROR"
        assert result.error.safe_reason == "staged_input_missing"

    def test_staged_input_symlink_is_rejected(self, tmp_path):
        release, _ = _make_release(tmp_path, "b2")
        job = _job(tmp_path, with_input=False)
        (job / "input.h5").symlink_to(tmp_path / "release" / "manifest.json")
        result = execute_operation(
            _request(release, "b2", operation="predict"),
            release_dir=str(release),
            job_dir=str(job),
            runtime_loader=lambda *a, **k: StubRuntime(prediction=_prediction()),
        )
        assert result.status == "error"
        assert result.error.code == "PROTOCOL_ERROR"

    def test_release_digest_mismatch_fails_closed(self, tmp_path):
        release, _ = _make_release(tmp_path, "b2")
        spec = variant_spec("b2")
        request = validate_worker_request(
            {
                "protocol": PROTOCOL_ID,
                "request_id": "req",
                "operation": "validate",
                "model_id": spec.model_id,
                "release_digest": "b" * 64,
                "payload": {"workflow_id": "bremen", "container_path": "input.h5"},
            }
        )
        result = execute_operation(
            request, release_dir=str(release), job_dir=str(_job(tmp_path)),
            runtime_loader=lambda *a, **k: StubRuntime(),
        )
        assert result.status == "error"
        assert result.error.code == "PROTOCOL_ERROR"
        assert result.error.safe_reason == "release_digest_mismatch"

    def test_model_identity_mismatch_fails_closed(self, tmp_path):
        release, _ = _make_release(tmp_path, "b2")
        result = execute_operation(
            _request(release, "b3", operation="validate"),
            release_dir=str(release),
            job_dir=str(_job(tmp_path)),
            runtime_loader=lambda *a, **k: StubRuntime(),
        )
        assert result.status == "error"
        assert result.error.code == "PROTOCOL_ERROR"
        assert result.error.safe_reason == "model_identity_mismatch"


class TestErrorMapping:
    def test_scientific_qc_failure_maps_to_qc_failed(self, tmp_path):
        release, _ = _make_release(tmp_path, "b2")
        stub = StubRuntime(exc=ModelPreprocessingFailedError("raw_peak_gate_failed"))
        result = execute_operation(
            _request(release, "b2"), release_dir=str(release),
            job_dir=str(_job(tmp_path)), runtime_loader=lambda *a, **k: stub,
        )
        assert result.status == "error"
        assert result.error.code == "QC_FAILED"
        assert result.error.safe_reason == "raw_peak_gate_failed"

    def test_input_invalid_maps_to_input_invalid(self, tmp_path):
        release, _ = _make_release(tmp_path, "b3")
        stub = StubRuntime(exc=ModelInputInvalidError("requires_exactly_3_left_3_right"))
        result = execute_operation(
            _request(release, "b3"), release_dir=str(release),
            job_dir=str(_job(tmp_path)), runtime_loader=lambda *a, **k: stub,
        )
        assert result.status == "error"
        assert result.error.code == "INPUT_INVALID"
        assert result.error.safe_reason == "requires_exactly_3_left_3_right"

    def test_aramina_failure_preserves_code_and_stage(self, tmp_path):
        from bremen.model_packages.aramina_v0213.errors import AraminaWorkflowError

        release, _ = _make_release(tmp_path, "b2")
        stub = StubRuntime(
            exc=AraminaWorkflowError("ARAMINA_UNSUPPORTED_INPUT", "preprocessing_contract")
        )
        result = execute_operation(
            _request(release, "b2"), release_dir=str(release),
            job_dir=str(_job(tmp_path)), runtime_loader=lambda *a, **k: stub,
        )
        assert result.status == "error"
        assert result.error.code == "QC_FAILED"
        assert result.error.safe_reason == "ARAMINA_UNSUPPORTED_INPUT:preprocessing_contract"

    def test_error_result_has_exactly_code_and_safe_reason(self, tmp_path):
        release, _ = _make_release(tmp_path, "b2")
        result = execute_operation(
            _request(release, "b2"), release_dir=str(tmp_path / "missing-release"),
            job_dir=str(_job(tmp_path)),
        )
        assert result.status == "error"
        assert result.error.code == "PROTOCOL_ERROR"
        assert result.error.safe_reason == "release_directory_missing"
        assert set(vars(result.error)) == {"code", "safe_reason"}

    def test_error_identity_matches_request(self, tmp_path):
        release, _ = _make_release(tmp_path, "b2")
        request = _request(release, "b2")
        result = execute_operation(
            request, release_dir=str(release), job_dir=str(_job(tmp_path)),
            runtime_loader=lambda *a, **k: StubRuntime(exc=RuntimeError("secret")),
        )
        assert result.request_id == request.request_id
        assert result.operation == request.operation
        assert result.model_id == request.model_id
        assert result.release_digest == request.release_digest
        assert result.error.safe_reason == "inference_failed"


class TestPreprocessingProvenance:
    def _record(self, tmp_path: Path, **overrides) -> Path:
        record = {
            "release_tag": "v0.1.7-beta",
            "version": "0.1.7b0",
            "source_commit": "45d5568248e9774b7938a36e028d80e72b130b19",
        }
        record.update(overrides)
        path = tmp_path / "provenance.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        return path

    def test_bremen_worker_accepts_explicit_provenance(self, tmp_path, monkeypatch):
        import bremen.model_packages.bremen_v01.bremen_preprocess_worker as worker

        path = self._record(tmp_path)
        monkeypatch.setenv("BREMEN_PREPROCESS_PROVENANCE", str(path))
        monkeypatch.setattr(
            worker, "_read_explicit_provenance",
            lambda variable: json.loads(path.read_text()),
        )
        class _Distribution:
            version = "0.1.7b0"
            def read_text(self, name):
                return "{}"
        monkeypatch.setattr(
            "importlib.metadata.distribution", lambda name: _Distribution(),
        )
        worker._validate_dependency("v0.1.7-beta")  # no raise

    def test_bremen_worker_rejects_commit_drift(self, tmp_path, monkeypatch):
        import bremen.model_packages.bremen_v01.bremen_preprocess_worker as worker

        path = self._record(tmp_path, source_commit="0" * 40)
        monkeypatch.setattr(
            worker, "_read_explicit_provenance",
            lambda variable: json.loads(path.read_text()),
        )
        class _Distribution:
            version = "0.1.7b0"
            def read_text(self, name):
                return "{}"
        monkeypatch.setattr(
            "importlib.metadata.distribution", lambda name: _Distribution(),
        )
        with pytest.raises(ValueError, match="preprocessing dependency"):
            worker._validate_dependency("v0.1.7-beta")

    def test_bremen_worker_rejects_direct_url_disagreement(self, tmp_path, monkeypatch):
        import bremen.model_packages.bremen_v01.bremen_preprocess_worker as worker

        path = self._record(tmp_path)
        monkeypatch.setattr(
            worker, "_read_explicit_provenance",
            lambda variable: json.loads(path.read_text()),
        )
        class _Distribution:
            version = "0.1.7b0"
            def read_text(self, name):
                return json.dumps({"vcs_info": {"commit_id": "1" * 40}})
        monkeypatch.setattr(
            "importlib.metadata.distribution", lambda name: _Distribution(),
        )
        with pytest.raises(ValueError, match="preprocessing dependency"):
            worker._validate_dependency("v0.1.7-beta")

    def test_aramina_worker_accepts_explicit_provenance(self, tmp_path, monkeypatch):
        import bremen.model_packages.aramina_v0213.aramina_preprocess_worker as worker

        path = self._record(tmp_path)
        monkeypatch.setattr(
            worker, "_read_explicit_provenance",
            lambda variable: json.loads(path.read_text()),
        )
        monkeypatch.setattr(
            "importlib.metadata.distribution",
            lambda name: type("D", (), {"read_text": lambda self, n: "{}"})(),
        )
        worker._validate_provenance("v0.1.7-beta", "0.1.7b0", "0.1.7b0")

    def test_aramina_worker_rejects_missing_known_commit(self, tmp_path, monkeypatch):
        import bremen.model_packages.aramina_v0213.aramina_preprocess_worker as worker

        path = self._record(tmp_path, source_commit=None)
        monkeypatch.setattr(
            worker, "_read_explicit_provenance",
            lambda variable: json.loads(path.read_text()),
        )
        monkeypatch.setattr(
            "importlib.metadata.distribution",
            lambda name: type("D", (), {"read_text": lambda self, n: "{}"})(),
        )
        with pytest.raises(ValueError, match="provenance"):
            worker._validate_provenance("v0.1.7-beta", "0.1.7b0", "0.1.7b0")

    def test_aramina_worker_rejects_commit_drift(self, tmp_path, monkeypatch):
        import bremen.model_packages.aramina_v0213.aramina_preprocess_worker as worker

        path = self._record(tmp_path, source_commit="1" * 40)
        monkeypatch.setattr(
            worker, "_read_explicit_provenance",
            lambda variable: json.loads(path.read_text()),
        )
        monkeypatch.setattr(
            "importlib.metadata.distribution",
            lambda name: type("D", (), {"read_text": lambda self, n: "{}"})(),
        )
        with pytest.raises(ValueError, match="provenance"):
            worker._validate_provenance("v0.1.7-beta", "0.1.7b0", "0.1.7b0")


class TestPreprocessingEnvironmentPortability:
    def _config(self, release: Path, value: str):
        from bremen.ml_plugin.release import ReleaseConfig

        return ReleaseConfig(
            release_dir=str(release.resolve()),
            release_id="r",
            variant="b2",
            artifact_relative_path="model/model.joblib",
            artifact_sha256="a" * 64,
            preprocessing_environment={"BREMEN_PREPROCESS_PYTHON": value},
        )

    def test_aux_reference_resolves_from_env_root(self, tmp_path, monkeypatch):
        from bremen.ml_plugin.release import (
            AUX_ENV_ROOT_ENV, apply_preprocessing_environment,
        )

        release = tmp_path / "release"
        release.mkdir()
        aux_root = tmp_path / "aux-root"
        interpreter = aux_root / "v0.1.7-beta" / "bin" / "python"
        interpreter.parent.mkdir(parents=True)
        interpreter.write_text("")
        monkeypatch.setenv(AUX_ENV_ROOT_ENV, str(aux_root))
        config = self._config(release, "@aux/v0.1.7-beta")
        apply_preprocessing_environment(config)
        assert os.environ["BREMEN_PREPROCESS_PYTHON"] == str(interpreter)

    def test_release_relative_aux_directory_preferred(self, tmp_path, monkeypatch):
        from bremen.ml_plugin.release import apply_preprocessing_environment

        release = tmp_path / "release"
        interpreter = release / "aux" / "v0.1.7-beta" / "bin" / "python"
        interpreter.parent.mkdir(parents=True)
        interpreter.write_text("")
        config = self._config(release, "@aux/v0.1.7-beta")
        apply_preprocessing_environment(config)
        assert os.environ["BREMEN_PREPROCESS_PYTHON"] == str(interpreter)

    def test_missing_aux_environment_fails_closed(self, tmp_path, monkeypatch):
        from bremen.ml_plugin.release import (
            AUX_ENV_ROOT_ENV, apply_preprocessing_environment,
        )

        monkeypatch.delenv(AUX_ENV_ROOT_ENV, raising=False)
        release = tmp_path / "release"
        release.mkdir()
        with pytest.raises(PluginReleaseError) as excinfo:
            apply_preprocessing_environment(
                self._config(release, "@aux/v0.1.7-beta")
            )
        assert excinfo.value.safe_reason == "auxiliary_environment_missing"

    def test_absolute_path_is_rejected(self, tmp_path):
        from bremen.ml_plugin.release import apply_preprocessing_environment

        release = tmp_path / "release"
        release.mkdir()
        with pytest.raises(PluginReleaseError) as excinfo:
            apply_preprocessing_environment(
                self._config(release, "/tmp/machine-local/bin/python")
            )
        assert excinfo.value.safe_reason == (
            "preprocessing_reference_must_be_release_relative"
        )

    def test_release_relative_provenance_resolves_inside_release(self, tmp_path):
        from bremen.ml_plugin.release import apply_preprocessing_environment

        release = tmp_path / "release"
        (release / "provenance").mkdir(parents=True)
        (release / "provenance" / "p.json").write_text("{}")
        config = self._config(release, "@release/provenance/p.json")
        apply_preprocessing_environment(config)
        assert os.environ["BREMEN_PREPROCESS_PYTHON"] == str(
            (release / "provenance" / "p.json").resolve()
        )


class TestEntrypoint:
    def _write_request(self, job: Path, request: dict) -> None:
        (job / "request.json").write_text(json.dumps(request), encoding="utf-8")

    def _request_data(self, release: Path, variant: str = "b2") -> dict:
        spec = variant_spec(variant)
        digest = hashlib.sha256((release / "manifest.json").read_bytes()).hexdigest()
        return {
            "protocol": PROTOCOL_ID,
            "request_id": "req-entry",
            "operation": "validate",
            "model_id": spec.model_id,
            "release_digest": digest,
            "payload": {"workflow_id": spec.workflow_id, "container_path": "input.h5"},
        }

    def test_entrypoint_writes_result_json(self, tmp_path, monkeypatch):
        release, _ = _make_release(tmp_path, "b2")
        job = _job(tmp_path)
        self._write_request(job, self._request_data(release))
        import bremen.ml_plugin.entrypoint as entrypoint_module

        monkeypatch.setattr(
            entrypoint_module,
            "execute_operation",
            lambda request, **kwargs: __import__(
                "bremen.contracts.worker_protocol", fromlist=["WorkerResult"]
            ).WorkerResult(
                protocol=request.protocol,
                request_id=request.request_id,
                operation=request.operation,
                model_id=request.model_id,
                release_digest=request.release_digest,
                status="ok",
                payload={"compatible": True},
                error=None,
            ),
        )
        assert entrypoint_main(["--release-dir", str(release), "--job-dir", str(job)]) == 0
        result = json.loads((job / "result.json").read_text())
        assert result["status"] == "ok"
        assert result["request_id"] == "req-entry"

    def test_entrypoint_missing_request_exits_nonzero(self, tmp_path):
        release, _ = _make_release(tmp_path, "b2")
        job = _job(tmp_path)
        assert entrypoint_main(["--release-dir", str(release), "--job-dir", str(job)]) == 2
        assert not (job / "result.json").exists()

    def test_entrypoint_missing_input_exits_without_result(self, tmp_path):
        release, _ = _make_release(tmp_path, "b2")
        job = _job(tmp_path, with_input=False)
        self._write_request(job, self._request_data(release))
        assert entrypoint_main(["--release-dir", str(release), "--job-dir", str(job)]) == 2
        assert not (job / "result.json").exists()

    def test_entrypoint_malformed_request_exits_nonzero(self, tmp_path):
        release, _ = _make_release(tmp_path, "b2")
        job = _job(tmp_path)
        self._write_request(job, {"protocol": "wrong"})
        assert entrypoint_main(["--release-dir", str(release), "--job-dir", str(job)]) == 2
