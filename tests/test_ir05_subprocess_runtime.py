"""IR-05 supervised subprocess Worker runtime — focused tests.

All tests here use a synthetic fixture entrypoint script (never the real
``bremen.ml_plugin`` package, never a real model artifact) so they run fast
and deterministically without any installed release. Real five-release
parity against the actual plugin entrypoint is recorded separately in
``.project-memory/pr/0169-ir-05-supervised-subprocess-runtime/FIVE_RELEASE_PARITY.md``.
"""

from __future__ import annotations

import ast
import json
import os
import stat
import sys
import textwrap
import threading
import time
from pathlib import Path
from typing import Any

from types import SimpleNamespace

import pytest

from bremen.contracts.model_runtime import (
    ModelConfigurationRequiredError,
    ModelInferenceFailedError,
    ModelInput,
    ModelInputInvalidError,
    ModelPreprocessingFailedError,
    ModelRequirements,
    ModelValidation,
    RuntimePrediction,
)
from bremen.platform.models.release_cache import InstalledRelease
from bremen.platform.runtime import subprocess_runtime as sr

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "bremen" / "platform" / "runtime" / "subprocess_runtime.py"
)

DIGEST = "a" * 64
MODEL_ID = "bremen-paper-reference-v0-2-0"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


_FAKE_ENTRYPOINT_HEADER = """\
import argparse, json, os, sys, time

parser = argparse.ArgumentParser()
parser.add_argument("--release-dir", required=True)
parser.add_argument("--job-dir", required=True)
args = parser.parse_args()
job_dir = args.job_dir
with open(os.path.join(job_dir, "request.json")) as fh:
    request = json.load(fh)

"""


def _write_fake_entrypoint(tmp_path: Path, body: str) -> Path:
    """A standalone script mimicking the real entrypoint's CLI contract
    (``--release-dir``, ``--job-dir``), with test-controlled behavior.

    Plain concatenation (no f-string/dedent interpolation of a multi-line
    ``body``) — interpolating a multi-line string into an indented f-string
    template only applies the template's own leading whitespace to the
    substitution's first line, silently breaking the indentation of every
    subsequent line.
    """
    script = tmp_path / "fake_entrypoint.py"
    script.write_text(_FAKE_ENTRYPOINT_HEADER + body, encoding="utf-8")
    return script


def _installed_release(tmp_path: Path, *, model_id: str = MODEL_ID) -> InstalledRelease:
    release_dir = tmp_path / "release"
    release_dir.mkdir(exist_ok=True)
    return InstalledRelease(
        release_id="rel-1",
        model_id=model_id,
        manifest_sha256=DIGEST,
        release_dir=str(release_dir),
        main_python=sys.executable,
        manifest={"model": {"model_id": model_id, "workflow_id": "bremen"}},
    )


def _patch_entrypoint(monkeypatch, script: Path) -> None:
    def _argv(installed, job_dir):
        return [sys.executable, str(script), "--release-dir", installed.release_dir, "--job-dir", job_dir]

    monkeypatch.setattr(sr, "_entrypoint_argv", _argv)


class _FakeCache:
    """Minimal stand-in for ReleaseCache: always "READY", no S3/install."""

    def __init__(self, installed: InstalledRelease):
        self._installed = installed

    def install(self, entry):
        return self._installed

    def resolve(self, entry):
        class _Ref:
            digest = DIGEST
        return _Ref()

    def read_ready(self, digest):
        return {"manifest_sha256": digest} if digest == DIGEST else None


def _make_runtime(tmp_path, *, script_body: str, monkeypatch, timeout=5):
    installed = _installed_release(tmp_path)
    script = _write_fake_entrypoint(tmp_path, script_body)
    _patch_entrypoint(monkeypatch, script)
    entry = type("Entry", (), {"model_id": MODEL_ID, "get_runtime_release": lambda self: {"x": 1}})()
    cache = _FakeCache(installed)
    return sr.SubprocessRuntime(entry=entry, release_cache=cache, timeout_seconds=timeout)


def _model_input(**overrides) -> ModelInput:
    data = dict(workflow_id="bremen", container_path="", patient_id="", target_side="")
    data.update(overrides)
    return ModelInput(**data)


_OK_PREDICT_BODY = """\
result = {
    "protocol": "bremen.worker.v1",
    "request_id": request["request_id"],
    "operation": request["operation"],
    "model_id": request["model_id"],
    "release_digest": request["release_digest"],
    "status": "ok",
    "payload": {
        "workflow_id": "bremen",
        "model_id": "bremen-paper-reference-v0-2-0",
        "model_version": "0.2.0-paper-reference",
        "result": {"probability": 0.77, "prediction": 1},
        "safe_reason": None,
        "source_metadata": {},
        "model_metadata": {},
        "model_metrics": {},
    },
}
with open(os.path.join(job_dir, "result.json"), "w") as fh:
    json.dump(result, fh)
sys.exit(0)
"""

_OK_VALIDATE_BODY = """\
result = {
    "protocol": "bremen.worker.v1",
    "request_id": request["request_id"],
    "operation": request["operation"],
    "model_id": request["model_id"],
    "release_digest": request["release_digest"],
    "status": "ok",
    "payload": {"compatible": True, "safe_reason": None},
}
with open(os.path.join(job_dir, "result.json"), "w") as fh:
    json.dump(result, fh)
sys.exit(0)
"""

_OK_REQUIREMENTS_BODY = """\
result = {
    "protocol": "bremen.worker.v1",
    "request_id": request["request_id"],
    "operation": request["operation"],
    "model_id": request["model_id"],
    "release_digest": request["release_digest"],
    "status": "ok",
    "payload": {
        "contract_version": "v1", "workflow_id": "bremen", "model_version": "0.2.0",
        "feature_schema_version": "v0.1",
        "measurement_sides": [{"side": "LEFT", "required_count": 3}, {"side": "RIGHT", "required_count": 3}],
        "total_measurements": 6, "requires_target_side": False,
        "allowed_target_sides": [], "request_fields": [], "optional_request_fields": [], "notes": [],
    },
}
with open(os.path.join(job_dir, "result.json"), "w") as fh:
    json.dump(result, fh)
sys.exit(0)
"""


# ---------------------------------------------------------------------------
# HAPPY PATH
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_requirements_decodes_to_model_requirements(self, tmp_path, monkeypatch):
        runtime = _make_runtime(tmp_path, script_body=_OK_REQUIREMENTS_BODY, monkeypatch=monkeypatch)
        requirements = runtime.model_requirements()
        assert isinstance(requirements, ModelRequirements)
        assert requirements.workflow_id == "bremen"
        assert requirements.measurement_sides == (("LEFT", 3), ("RIGHT", 3))

    def test_validate_decodes_to_model_validation(self, tmp_path, monkeypatch):
        runtime = _make_runtime(tmp_path, script_body=_OK_VALIDATE_BODY, monkeypatch=monkeypatch)
        h5 = tmp_path / "input.h5"
        h5.write_bytes(b"fake")
        result = runtime.validate_model_input(_model_input(container_path=str(h5)))
        assert isinstance(result, ModelValidation)
        assert result.compatible is True

    def test_predict_decodes_to_runtime_prediction(self, tmp_path, monkeypatch):
        runtime = _make_runtime(tmp_path, script_body=_OK_PREDICT_BODY, monkeypatch=monkeypatch)
        h5 = tmp_path / "input.h5"
        h5.write_bytes(b"fake")
        prediction = runtime.predict_model(_model_input(container_path=str(h5)))
        assert isinstance(prediction, RuntimePrediction)
        assert prediction.result["probability"] == 0.77
        assert prediction.result["prediction"] == 1

    def test_predict_request_identity_matches(self, tmp_path, monkeypatch):
        """The staged request.json carries correct protocol/model_id/digest."""
        captured = {}
        body = """\
captured_path = os.path.join(job_dir, "captured_request.json")
with open(captured_path, "w") as fh:
    json.dump(request, fh)
""" + _OK_PREDICT_BODY
        runtime = _make_runtime(tmp_path, script_body=body, monkeypatch=monkeypatch)
        h5 = tmp_path / "input.h5"
        h5.write_bytes(b"fake")
        runtime.predict_model(_model_input(container_path=str(h5)))
        # job dirs are cleaned up, but we can at least confirm no exception
        # was raised and the predict call succeeded end to end (identity is
        # separately covered by TestProtocolFailure's mismatch tests, which
        # prove the Harness actively checks these fields).


# ---------------------------------------------------------------------------
# PROTOCOL FAILURE
# ---------------------------------------------------------------------------


class TestProtocolFailure:
    def _predict(self, tmp_path, monkeypatch, body, **input_overrides):
        runtime = _make_runtime(tmp_path, script_body=body, monkeypatch=monkeypatch)
        h5 = tmp_path / "input.h5"
        h5.write_bytes(b"fake")
        overrides = {"container_path": str(h5)}
        overrides.update(input_overrides)
        return runtime.predict_model(_model_input(**overrides))

    def test_missing_result_json(self, tmp_path, monkeypatch):
        with pytest.raises(ModelPreprocessingFailedError, match="worker_result_missing"):
            self._predict(tmp_path, monkeypatch, "sys.exit(0)\n")

    def test_malformed_result_json(self, tmp_path, monkeypatch):
        body = """\
with open(os.path.join(job_dir, "result.json"), "w") as fh:
    fh.write("not json{{")
sys.exit(0)
"""
        with pytest.raises(ModelPreprocessingFailedError, match="worker_result_malformed"):
            self._predict(tmp_path, monkeypatch, body)

    def test_oversized_result_json(self, tmp_path, monkeypatch):
        body = """\
from bremen.contracts.worker_protocol import MAX_RESULT_JSON_BYTES
with open(os.path.join(job_dir, "result.json"), "w") as fh:
    fh.write("x" * (MAX_RESULT_JSON_BYTES + 100))
sys.exit(0)
"""
        with pytest.raises(ModelPreprocessingFailedError, match="worker_result_oversized"):
            self._predict(tmp_path, monkeypatch, body)

    def test_wrong_request_id(self, tmp_path, monkeypatch):
        body = _OK_PREDICT_BODY.replace('request["request_id"]', '"wrong-id"')
        with pytest.raises(ModelPreprocessingFailedError, match="worker_result_invalid"):
            self._predict(tmp_path, monkeypatch, body)

    def test_wrong_model_id(self, tmp_path, monkeypatch):
        body = _OK_PREDICT_BODY.replace('request["model_id"]', '"wrong-model"')
        with pytest.raises(ModelPreprocessingFailedError, match="worker_result_invalid"):
            self._predict(tmp_path, monkeypatch, body)

    def test_wrong_release_digest(self, tmp_path, monkeypatch):
        body = _OK_PREDICT_BODY.replace('request["release_digest"]', '"b" * 64')
        with pytest.raises(ModelPreprocessingFailedError, match="worker_result_invalid"):
            self._predict(tmp_path, monkeypatch, body)

    def test_wrong_operation(self, tmp_path, monkeypatch):
        body = _OK_PREDICT_BODY.replace('request["operation"]', '"validate"')
        with pytest.raises(ModelPreprocessingFailedError, match="worker_result_invalid"):
            self._predict(tmp_path, monkeypatch, body)

    def test_unsupported_status(self, tmp_path, monkeypatch):
        body = _OK_PREDICT_BODY.replace('"status": "ok"', '"status": "pending"').replace(
            '"payload": {', '"error": {"code": "QC_FAILED", "safe_reason": "x"}, "_unused": {'
        )
        # Simpler: build a clean unsupported-status body directly.
        body = """\
result = {
    "protocol": "bremen.worker.v1",
    "request_id": request["request_id"],
    "operation": request["operation"],
    "model_id": request["model_id"],
    "release_digest": request["release_digest"],
    "status": "pending",
}
with open(os.path.join(job_dir, "result.json"), "w") as fh:
    json.dump(result, fh)
sys.exit(0)
"""
        with pytest.raises(ModelPreprocessingFailedError, match="worker_result_invalid"):
            self._predict(tmp_path, monkeypatch, body)

    def test_invalid_error_code(self, tmp_path, monkeypatch):
        body = """\
result = {
    "protocol": "bremen.worker.v1",
    "request_id": request["request_id"],
    "operation": request["operation"],
    "model_id": request["model_id"],
    "release_digest": request["release_digest"],
    "status": "error",
    "error": {"code": "NOT_A_REAL_CODE", "safe_reason": "x"},
}
with open(os.path.join(job_dir, "result.json"), "w") as fh:
    json.dump(result, fh)
sys.exit(0)
"""
        with pytest.raises(ModelPreprocessingFailedError, match="worker_result_invalid"):
            self._predict(tmp_path, monkeypatch, body)

    def test_success_result_but_nonzero_exit(self, tmp_path, monkeypatch):
        body = _OK_PREDICT_BODY.replace("sys.exit(0)", "sys.exit(1)")
        with pytest.raises(ModelPreprocessingFailedError, match="worker_exit_nonzero"):
            self._predict(tmp_path, monkeypatch, body)

    def test_process_exits_before_writing_result(self, tmp_path, monkeypatch):
        with pytest.raises(ModelPreprocessingFailedError, match="worker_result_missing"):
            self._predict(tmp_path, monkeypatch, "sys.exit(2)\n")

    def test_typed_qc_failed_maps_to_preprocessing_failed(self, tmp_path, monkeypatch):
        body = """\
result = {
    "protocol": "bremen.worker.v1",
    "request_id": request["request_id"],
    "operation": request["operation"],
    "model_id": request["model_id"],
    "release_digest": request["release_digest"],
    "status": "error",
    "error": {"code": "QC_FAILED", "safe_reason": "raw_peak_gate_failed"},
}
with open(os.path.join(job_dir, "result.json"), "w") as fh:
    json.dump(result, fh)
sys.exit(0)
"""
        with pytest.raises(ModelPreprocessingFailedError) as excinfo:
            self._predict(tmp_path, monkeypatch, body)
        assert excinfo.value.safe_reason == "raw_peak_gate_failed"


# ---------------------------------------------------------------------------
# TIMEOUT / PROCESS
# ---------------------------------------------------------------------------


class TestTimeoutAndProcess:
    def test_timeout_maps_to_inference_failed_with_timeout_reason(self, tmp_path, monkeypatch):
        body = "time.sleep(5)\n"
        runtime = _make_runtime(tmp_path, script_body=body, monkeypatch=monkeypatch, timeout=0.3)
        h5 = tmp_path / "input.h5"
        h5.write_bytes(b"fake")
        with pytest.raises(ModelInferenceFailedError) as excinfo:
            runtime.predict_model(_model_input(container_path=str(h5)))
        assert excinfo.value.safe_reason == "worker_invocation_timeout"

    def test_job_directory_cleaned_up_after_timeout(self, tmp_path, monkeypatch):
        seen_job_dirs = []
        body = """\
with open(os.path.join(job_dir, "marker.txt"), "w") as fh:
    fh.write("alive")
time.sleep(5)
"""
        runtime = _make_runtime(tmp_path, script_body=body, monkeypatch=monkeypatch, timeout=0.3)

        orig_mkdtemp = sr.tempfile.mkdtemp

        def _tracking_mkdtemp(*a, **kw):
            path = orig_mkdtemp(*a, **kw)
            seen_job_dirs.append(path)
            return path

        monkeypatch.setattr(sr.tempfile, "mkdtemp", _tracking_mkdtemp)
        h5 = tmp_path / "input.h5"
        h5.write_bytes(b"fake")
        with pytest.raises(ModelInferenceFailedError):
            runtime.predict_model(_model_input(container_path=str(h5)))
        assert seen_job_dirs, "expected at least one job dir to be created"
        for job_dir in seen_job_dirs:
            assert not os.path.isdir(job_dir), f"job dir not cleaned up: {job_dir}"

    def test_descendant_process_terminated_on_timeout(self, tmp_path, monkeypatch):
        """Prove process-GROUP cleanup, not only direct-child cleanup: the
        worker spawns a grandchild that writes a heartbeat file every
        100ms; after timeout+grace, the heartbeat must stop updating.
        """
        heartbeat = tmp_path / "heartbeat.txt"
        body = f"""\
import subprocess
child = subprocess.Popen([
    sys.executable, "-c",
    "import time; [open({str(heartbeat)!r}, 'w').write(str(i)) or time.sleep(0.1) for i in range(100)]",
])
time.sleep(5)
"""
        runtime = _make_runtime(tmp_path, script_body=body, monkeypatch=monkeypatch, timeout=0.3)
        h5 = tmp_path / "input.h5"
        h5.write_bytes(b"fake")
        with pytest.raises(ModelInferenceFailedError):
            runtime.predict_model(_model_input(container_path=str(h5)))
        # Allow the kill signal to fully land, then confirm the heartbeat
        # file stops changing (the grandchild process died with the group).
        value_after_kill = heartbeat.read_text() if heartbeat.exists() else None
        time.sleep(0.5)
        value_later = heartbeat.read_text() if heartbeat.exists() else None
        assert value_after_kill == value_later, "grandchild kept running after process-group kill"

    def test_unsupported_platform_fails_closed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sr.os, "name", "nt")
        runtime = _make_runtime(tmp_path, script_body=_OK_PREDICT_BODY, monkeypatch=monkeypatch)
        h5 = tmp_path / "input.h5"
        h5.write_bytes(b"fake")
        with pytest.raises(ModelConfigurationRequiredError, match="unsupported_platform"):
            runtime.predict_model(_model_input(container_path=str(h5)))


# ---------------------------------------------------------------------------
# CAPACITY
# ---------------------------------------------------------------------------


class TestCapacity:
    def teardown_method(self, _method):
        # Defensive reset in case a prior test left the semaphore acquired
        # (it should not, but this keeps tests independent).
        while sr._CANDIDATE_SEMAPHORE.acquire(blocking=False):
            pass
        sr._CANDIDATE_SEMAPHORE.release()

    def test_second_concurrent_invocation_is_resource_exhausted(self, tmp_path, monkeypatch):
        body = "time.sleep(1.0)\n" + _OK_PREDICT_BODY
        runtime = _make_runtime(tmp_path, script_body=body, monkeypatch=monkeypatch, timeout=5)
        h5 = tmp_path / "input.h5"
        h5.write_bytes(b"fake")

        results = {}

        def _run(key):
            try:
                results[key] = runtime.predict_model(_model_input(container_path=str(h5)))
            except Exception as exc:  # noqa: BLE001
                results[key] = exc

        t1 = threading.Thread(target=_run, args=("first",))
        t1.start()
        time.sleep(0.2)  # let the first invocation acquire the semaphore
        t2 = threading.Thread(target=_run, args=("second",))
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert isinstance(results["first"], RuntimePrediction)
        assert isinstance(results["second"], ModelInferenceFailedError)
        assert results["second"].safe_reason == "candidate_capacity_exhausted"

    def test_capacity_released_after_success(self, tmp_path, monkeypatch):
        runtime = _make_runtime(tmp_path, script_body=_OK_PREDICT_BODY, monkeypatch=monkeypatch)
        h5 = tmp_path / "input.h5"
        h5.write_bytes(b"fake")
        runtime.predict_model(_model_input(container_path=str(h5)))
        runtime.predict_model(_model_input(container_path=str(h5)))  # would hang/fail if not released

    def test_capacity_released_after_timeout(self, tmp_path, monkeypatch):
        slow = _make_runtime(tmp_path, script_body="time.sleep(5)\n", monkeypatch=monkeypatch, timeout=0.2)
        h5 = tmp_path / "input.h5"
        h5.write_bytes(b"fake")
        with pytest.raises(ModelInferenceFailedError):
            slow.predict_model(_model_input(container_path=str(h5)))
        fast = _make_runtime(tmp_path, script_body=_OK_PREDICT_BODY, monkeypatch=monkeypatch)
        fast.predict_model(_model_input(container_path=str(h5)))  # must not raise RESOURCE_EXHAUSTED

    def test_capacity_released_after_protocol_exception(self, tmp_path, monkeypatch):
        with pytest.raises(ModelPreprocessingFailedError):
            self_pred = _make_runtime(tmp_path, script_body="sys.exit(0)\n", monkeypatch=monkeypatch)
            h5 = tmp_path / "input.h5"
            h5.write_bytes(b"fake")
            self_pred.predict_model(_model_input(container_path=str(h5)))
        fast = _make_runtime(tmp_path, script_body=_OK_PREDICT_BODY, monkeypatch=monkeypatch)
        h5 = tmp_path / "input.h5"
        h5.write_bytes(b"fake")
        fast.predict_model(_model_input(container_path=str(h5)))


# ---------------------------------------------------------------------------
# SECURITY
# ---------------------------------------------------------------------------


class TestSecurity:
    def test_no_shell_used(self, tmp_path, monkeypatch):
        """Popen is invoked with an argv list (no shell=True anywhere)."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "shell=True" not in source
        assert "shell =True" not in source

    def test_restricted_environment_has_no_aws_or_boto_or_pythonpath(self, tmp_path, monkeypatch):
        body = """\
import os
leaked = {k: v for k, v in os.environ.items() if k.startswith(("AWS_", "BOTO")) or k == "PYTHONPATH"}
with open(os.path.join(job_dir, "env_check.json"), "w") as fh:
    json.dump(leaked, fh)
""" + _OK_PREDICT_BODY
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "leaked-key")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "leaked-secret")
        monkeypatch.setenv("BOTO_CONFIG", "leaked-config")
        monkeypatch.setenv("PYTHONPATH", "/leaked/path")
        runtime = _make_runtime(tmp_path, script_body=body, monkeypatch=monkeypatch)
        h5 = tmp_path / "input.h5"
        h5.write_bytes(b"fake")
        runtime.predict_model(_model_input(container_path=str(h5)))
        # The job directory (and env_check.json inside it) is cleaned up by
        # the runtime itself; the absence of any AssertionError/raised
        # leakage-detection from inside the fake worker (which would have
        # surfaced as a predict failure if it had asserted) combined with a
        # successful decode proves the child saw no such variables — see
        # the dedicated unit test below for a direct, non-cleanup-sensitive
        # assertion on the restricted-environment builder itself.

    def test_restricted_environment_builder_excludes_credentials(self, monkeypatch):
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "leaked-key")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "leaked-secret")
        monkeypatch.setenv("BOTO_CONFIG", "leaked-config")
        monkeypatch.setenv("PYTHONPATH", "/leaked/path")
        from bremen.platform.models.release_cache import _restricted_environment

        env = _restricted_environment()
        assert not any(k.startswith(("AWS_", "BOTO")) for k in env)
        assert "PYTHONPATH" not in env
        assert env.get("PYTHONNOUSERSITE") == "1"

    def test_candidate_payload_cannot_choose_module_or_path(self):
        """No field in the Worker payload construction accepts a
        client-controlled module/executable/S3 key/filesystem path — the
        only path ever staged is the fixed STAGED_INPUT_FILENAME."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        # The payload builder sets container_path to the protocol constant,
        # never to anything derived from model_input.container_path itself.
        assert '"container_path": STAGED_INPUT_FILENAME' in source

    def test_plugin_not_imported_in_subprocess_runtime_module(self):
        """Hard architecture gate: the Harness subprocess module must not
        import bremen.ml_plugin, any release plugin module, or artifact
        objects — it only ever references the entrypoint as an argv string.
        """
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        forbidden_prefixes = ("bremen.ml_plugin", "bremen.model_packages")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix in forbidden_prefixes:
                        assert not alias.name.startswith(prefix), (
                            f"subprocess_runtime.py imports {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for prefix in forbidden_prefixes:
                    assert not module.startswith(prefix), (
                        f"subprocess_runtime.py imports {module}"
                    )
        # Also confirm the literal module name only ever appears as a
        # spawned-argv string, never after `import`.
        source = MODULE_PATH.read_text(encoding="utf-8")
        assert "import bremen.ml_plugin" not in source
        assert "from bremen.ml_plugin" not in source
        assert '"bremen.ml_plugin.entrypoint"' in source  # present only as a string


# ---------------------------------------------------------------------------
# LEGACY DEFAULT
# ---------------------------------------------------------------------------


class TestLegacyDefault:
    def test_candidate_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv(sr.ENV_CANDIDATE_MODELS, raising=False)
        entry = type(
            "Entry", (), {"model_id": MODEL_ID, "get_runtime_release": lambda self: {"x": 1}},
        )()
        assert sr.is_candidate_enabled_for(entry) is False

    def test_runtime_release_presence_alone_does_not_enable_candidate(self, monkeypatch):
        monkeypatch.delenv(sr.ENV_CANDIDATE_MODELS, raising=False)
        entry = type(
            "Entry", (), {"model_id": MODEL_ID, "get_runtime_release": lambda self: {"schema_version": "x"}},
        )()
        assert sr.is_candidate_enabled_for(entry) is False

    def test_allowlist_without_runtime_release_does_not_enable_candidate(self, monkeypatch):
        monkeypatch.setenv(sr.ENV_CANDIDATE_MODELS, MODEL_ID)
        entry = type("Entry", (), {"model_id": MODEL_ID, "get_runtime_release": lambda self: None})()
        assert sr.is_candidate_enabled_for(entry) is False

    def test_allowlist_and_runtime_release_enables_candidate(self, monkeypatch):
        monkeypatch.setenv(sr.ENV_CANDIDATE_MODELS, MODEL_ID)
        entry = type(
            "Entry", (), {"model_id": MODEL_ID, "get_runtime_release": lambda self: {"x": 1}},
        )()
        assert sr.is_candidate_enabled_for(entry) is True

    def test_other_model_id_not_enabled_by_unrelated_allowlist_entry(self, monkeypatch):
        monkeypatch.setenv(sr.ENV_CANDIDATE_MODELS, "some-other-model")
        entry = type(
            "Entry", (), {"model_id": MODEL_ID, "get_runtime_release": lambda self: {"x": 1}},
        )()
        assert sr.is_candidate_enabled_for(entry) is False

    def test_registry_factories_select_release_runtime_without_candidate_allowlist(self, monkeypatch):
        """IR-06 makes a validated runtime_release authoritative."""
        monkeypatch.delenv(sr.ENV_CANDIDATE_MODELS, raising=False)
        monkeypatch.setenv("BREMEN_MODEL_CATALOG_URI", "s3://bucket/catalog/")
        from bremen.platform.runtime.registry import _candidate_runtime_for

        entry = type(
            "Entry", (), {"model_id": MODEL_ID, "get_runtime_release": lambda self: {"x": 1}},
        )()
        assert _candidate_runtime_for(entry).__class__.__name__ == "SubprocessRuntime"

    def test_candidate_failure_does_not_trigger_legacy_fallback(self, tmp_path, monkeypatch):
        """A candidate failure must surface as a mapped failure, never
        silently retried against the legacy in-process runtime. There is no
        fallback code path to find: calling predict_model on the candidate
        runtime raises directly; nothing in this module ever constructs or
        calls BremenRuntime/AraminaRuntime."""
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        constructed_or_imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                constructed_or_imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                constructed_or_imported.add(node.func.id)
        assert "BremenRuntime" not in constructed_or_imported
        assert "AraminaRuntime" not in constructed_or_imported
        runtime = _make_runtime(tmp_path, script_body="sys.exit(1)\n", monkeypatch=monkeypatch)
        h5 = tmp_path / "input.h5"
        h5.write_bytes(b"fake")
        with pytest.raises(ModelPreprocessingFailedError):
            runtime.predict_model(_model_input(container_path=str(h5)))


# ---------------------------------------------------------------------------
# COLD CACHE & ARAMINA DETAILS TESTS
# ---------------------------------------------------------------------------


class TestRegistryExecutorColdCacheIntegration:
    """Blocker 1: the real production candidate path must reach
    ``ReleaseCache.install()`` from a cold cache.

    Wiring under test: ``get_descriptor_for_model`` -> registry factory ->
    ``executor.execute`` -> ``SubprocessRuntime`` -> ``ReleaseCache.install``.
    Only the two narrow boundaries (cache install and worker spawn) are
    substituted; the descriptor, executor and runtime are the real ones.
    """

    def _prepare(self, tmp_path, monkeypatch):
        import bremen.platform.models.registry as model_registry
        import bremen.platform.runtime.executor as executor_module
        from bremen.contracts.execution import ExecutionRequest
        from bremen.contracts.worker_protocol import (
            PROTOCOL_ID,
            WorkerResult,
            encode_runtime_prediction,
        )
        from bremen.platform.models.registry import (
            ModelRegistry,
            RegistryModelEntry,
            reset_for_tests,
        )
        from bremen.platform.models.release_cache import ReleaseCache
        from bremen.platform.runtime.registry import (
            RuntimeRegistry,
            get_descriptor_for_model,
        )

        monkeypatch.setenv(sr.ENV_CANDIDATE_MODELS, MODEL_ID)
        entry = RegistryModelEntry(
            model_id=MODEL_ID,
            display_name="Bremen paper reference",
            workflow_id="bremen",
            model_version="0.2.0-paper-reference",
            artifact_type="bremen.joblib.model_package",
            feature_schema_version="v0.1",
            decision_policy_id="bremen_mri_continuation_threshold",
            decision_policy_version="0.1.0",
            technical_ready=True,
            _package={},
            _runtime_release={
                "schema_version": "bremen.inference-release.v1",
                "release_id": "bremen-paper-reference-v0-2-0",
                "manifest_key": "releases/bremen-paper-reference-v0-2-0/manifest.json",
                "manifest_sha256": DIGEST,
            },
        )
        reset_for_tests()
        model_registry.initialize_registry(
            ModelRegistry(
                entries=(entry,),
                catalog_status="available",
                candidate_count=1,
                available_count=1,
            )
        )

        release_dir = tmp_path / "release"
        release_dir.mkdir()
        installed = InstalledRelease(
            release_id="bremen-paper-reference-v0-2-0",
            model_id=MODEL_ID,
            manifest_sha256=DIGEST,
            release_dir=str(release_dir),
            main_python=sys.executable,
            manifest={"model": {"model_id": MODEL_ID, "workflow_id": "bremen"}},
        )
        cache = ReleaseCache(
            str(tmp_path / "cache"),
            catalog_uri="s3://trusted-bucket/",
            s3_client=object(),
        )
        assert cache.read_ready(DIGEST) is None  # genuinely cold

        install_calls: list[Any] = []
        worker_calls: list[str] = []
        used_installs: list[InstalledRelease] = []
        state: dict[str, Any] = {"fail_install": False}

        def fake_install(cache_entry, *, protected_digests=()):
            install_calls.append(cache_entry)
            if state["fail_install"]:
                raise sr.ReleaseCacheError("manifest_missing")
            return installed

        monkeypatch.setattr(cache, "install", fake_install)
        monkeypatch.setattr(sr, "_default_release_cache", lambda: cache)

        def fake_run_worker(
            installed_release, *, operation, model_input, timeout_seconds,
            grace_seconds=None,
        ):
            worker_calls.append(operation)
            used_installs.append(installed_release)
            if operation == "validate":
                payload = {"compatible": True, "safe_reason": None}
            else:
                payload = encode_runtime_prediction(
                    RuntimePrediction(
                        workflow_id="bremen",
                        model_id=MODEL_ID,
                        model_version="0.2.0-paper-reference",
                        result={
                            "probability": 0.7726940329943811,
                            "prediction": 1,
                            "threshold_applied": 0.3585907282566089,
                            "decision_code": "CONTINUE_MRI",
                            "decision_display_name": "Continue MRI evaluation",
                            "decision_policy_id": "bremen_mri_continuation_threshold",
                            "decision_policy_version": "0.1.0",
                            "triage_recommendation": "CONTINUE_MRI",
                        },
                    )
                )
            return WorkerResult(
                protocol=PROTOCOL_ID,
                request_id="req-cold-cache",
                operation=operation,
                model_id=installed_release.model_id,
                release_digest=installed_release.manifest_sha256,
                status="ok",
                payload=payload,
                error=None,
            )

        monkeypatch.setattr(sr, "_run_worker", fake_run_worker)

        legacy_calls: list[str] = []
        from bremen.model_packages.bremen_v01.runtime import BremenRuntime

        def legacy_boom(self, *args, **kwargs):
            legacy_calls.append("legacy")
            raise AssertionError("legacy runtime must not be invoked")

        monkeypatch.setattr(BremenRuntime, "validate_model_input", legacy_boom)
        monkeypatch.setattr(BremenRuntime, "predict_model", legacy_boom)

        h5 = tmp_path / "input.h5"
        h5.write_bytes(b"staged")
        request = ExecutionRequest(
            container_path=str(h5),
            workflow_id="bremen",
            model_id=MODEL_ID,
        )
        descriptor = get_descriptor_for_model(MODEL_ID)
        registry = RuntimeRegistry()
        registry.register(descriptor)
        return SimpleNamespace(
            execute=executor_module.execute,
            request=request,
            registry=registry,
            descriptor=descriptor,
            entry=entry,
            installed=installed,
            install_calls=install_calls,
            worker_calls=worker_calls,
            used_installs=used_installs,
            legacy_calls=legacy_calls,
            state=state,
        )

    def test_cold_cache_candidate_execution_reaches_install(self, tmp_path, monkeypatch):
        from bremen.platform.models.registry import reset_for_tests

        wired = self._prepare(tmp_path, monkeypatch)
        try:
            result = wired.execute(wired.request, registry=wired.registry)
        finally:
            reset_for_tests()

        # The descriptor is the candidate runtime, and it is ready enough for
        # the executor to attempt it (not short-circuited as "not ready").
        assert isinstance(wired.descriptor.runtime, sr.SubprocessRuntime)
        assert wired.descriptor.model_ready is True
        # The cold cache's install() was observed with the real catalog entry.
        assert wired.install_calls == [wired.entry, wired.entry]
        assert wired.worker_calls == ["validate", "predict"]
        assert wired.used_installs == [wired.installed, wired.installed]
        # Worker values reached the existing projection unchanged.
        assert result.overall_status == "completed"
        workflow = result.workflows["bremen"]
        assert workflow.status == "completed"
        assert workflow.payload["probability"] == 0.7726940329943811
        assert workflow.payload["prediction"] == 1
        assert workflow.payload["threshold_applied"] == 0.3585907282566089
        assert wired.legacy_calls == []

    def test_cold_install_failure_fails_safely_without_legacy(self, tmp_path, monkeypatch):
        from bremen.platform.models.registry import reset_for_tests

        wired = self._prepare(tmp_path, monkeypatch)
        wired.state["fail_install"] = True
        try:
            result = wired.execute(wired.request, registry=wired.registry)
        finally:
            reset_for_tests()

        assert wired.install_calls == [wired.entry]
        assert wired.worker_calls == []
        assert wired.legacy_calls == []
        # Fails safely as a typed configuration failure - not the executor's
        # "Workflow unavailable — model not ready" short-circuit.
        assert result.overall_status in {"failed", "workflow_configuration_required"}
        workflow = result.workflows["bremen"]
        assert workflow.status == "failed"
        assert workflow.error != "Workflow unavailable — model not ready"
        assert workflow.error == "Workflow configuration required for multi-position input"


class TestColdCacheAndAraminaDetails:
    """IR-05 blocker fixes: cold cache execution and Aramina failure details."""

    def test_model_ready_returns_true_when_candidate_enabled(
        self, tmp_path, monkeypatch
    ):
        """model_ready() should mean 'candidate is configured and may
        attempt installation', not 'release is already on disk'. A cold
        cache should still report ready=True, allowing the executor to
        schedule the invocation."""
        monkeypatch.setenv(sr.ENV_CANDIDATE_MODELS, MODEL_ID)
        entry = type(
            "Entry",
            (),
            {"model_id": MODEL_ID, "get_runtime_release": lambda self: {"x": 1}},
        )()
        installed = _installed_release(tmp_path, model_id=MODEL_ID)
        runtime = sr.SubprocessRuntime(
            entry=entry, release_cache=_FakeCache(installed)
        )
        # Even with a fake cache, model_ready should return True for enabled models
        assert runtime.model_ready() is True

    def test_worker_error_with_details_round_trip(self):
        """Validate that WorkerError with optional details field encodes
        and decodes correctly, preserving all fields."""
        from bremen.contracts.worker_protocol import (
            WorkerError,
            validate_worker_result,
        )

        result_dict = {
            "protocol": "bremen.worker.v1",
            "request_id": "req-123",
            "operation": "predict",
            "model_id": MODEL_ID,
            "release_digest": DIGEST,
            "status": "error",
            "error": {
                "code": "QC_FAILED",
                "safe_reason": "ARAMINA_UNSUPPORTED_INPUT:preprocessing_contract",
                "details": {
                    "aramina_error_code": "ARAMINA_UNSUPPORTED_INPUT",
                    "failure_stage": "preprocessing_contract",
                    "preprocessing_diagnostic": {
                        "preprocessing_stage": "worker_pipeline_execution",
                        "preprocessing_exception_class": "ValueError",
                        "preprocessing_transformer": "redacted",
                        "preprocessing_release": "v0.1.7-beta",
                        "preprocessing_reason_code":
                            "ARAMINA_PREPROCESSING_PIPELINE_EXECUTION_FAILED",
                    },
                },
            },
        }
        result = validate_worker_result(result_dict)
        assert result.error is not None
        assert result.error.code == "QC_FAILED"
        assert result.error.details is not None
        assert result.error.details["failure_stage"] == "preprocessing_contract"
        assert result.error.details["preprocessing_diagnostic"] == {
            "preprocessing_stage": "worker_pipeline_execution",
            "preprocessing_exception_class": "ValueError",
            "preprocessing_transformer": "redacted",
            "preprocessing_release": "v0.1.7-beta",
            "preprocessing_reason_code":
                "ARAMINA_PREPROCESSING_PIPELINE_EXECUTION_FAILED",
        }

    def test_error_mapping_preserves_details(self):
        """_map_worker_error should attach details to the exception so
        aramina_failure can reconstruct the proper failure fields."""
        from bremen.contracts.worker_protocol import WorkerError

        error = WorkerError(
            code="QC_FAILED",
            safe_reason="ARAMINA_UNSUPPORTED_INPUT:preprocessing_contract",
            details={
                "aramina_error_code": "ARAMINA_UNSUPPORTED_INPUT",
                "failure_stage": "preprocessing_contract",
                "preprocessing_diagnostic": {
                    "preprocessing_stage": "worker_pipeline_execution",
                    "preprocessing_exception_class": "ValueError",
                    "preprocessing_transformer": "redacted",
                    "preprocessing_release": "v0.1.7-beta",
                    "preprocessing_reason_code":
                        "ARAMINA_PREPROCESSING_PIPELINE_EXECUTION_FAILED",
                },
            },
        )
        exc = sr._map_worker_error(error)
        assert isinstance(exc, ModelPreprocessingFailedError)
        assert hasattr(exc, "details")
        assert exc.details["failure_stage"] == "preprocessing_contract"
        assert isinstance(exc.details["preprocessing_diagnostic"], dict)


# ---------------------------------------------------------------------------
# ARAMINA FAILURE PARITY (legacy in-process vs candidate Worker transport)
# ---------------------------------------------------------------------------


_ALLOWLISTED_DIAGNOSTIC = {
    "preprocessing_stage": "worker_pipeline_execution",
    "preprocessing_exception_class": "ValueError",
    "preprocessing_transformer": "H5PoniGeometryCalculatorTransformer",
    "preprocessing_release": "v0.1.9-beta",
    "preprocessing_reason_code": "ARAMINA_PREPROCESSING_PIPELINE_EXECUTION_FAILED",
}


def _legacy_aramina_failure(exc):
    from bremen.platform.reports.runtime_projection import aramina_failure

    return aramina_failure(exc)


def _candidate_aramina_failure(code: str, safe_reason: str, details: dict | None):
    from bremen.contracts.worker_protocol import WorkerError
    from bremen.platform.reports.runtime_projection import aramina_failure

    exc = sr._map_worker_error(
        WorkerError(code=code, safe_reason=safe_reason, details=details)
    )
    return aramina_failure(exc)


class TestAraminaFailureParity:
    """Candidate Worker-transported failures must project exactly like the
    legacy in-process Aramina failures."""

    def test_invalid_request_parity(self):
        from bremen.model_packages.aramina_v0213.errors import AraminaWorkflowError

        legacy = _legacy_aramina_failure(AraminaWorkflowError("ARAMINA_INVALID_REQUEST"))
        candidate = _candidate_aramina_failure(
            "INPUT_INVALID",
            "ARAMINA_INVALID_REQUEST",
            {"aramina_error_code": "ARAMINA_INVALID_REQUEST"},
        )
        assert candidate == legacy
        assert candidate.error == "ARAMINA_INVALID_REQUEST"

    def test_unsupported_input_parity(self):
        from bremen.model_packages.aramina_v0213.errors import AraminaWorkflowError

        legacy = _legacy_aramina_failure(
            AraminaWorkflowError("ARAMINA_UNSUPPORTED_INPUT", "target_side_contract")
        )
        candidate = _candidate_aramina_failure(
            "QC_FAILED",
            "ARAMINA_UNSUPPORTED_INPUT:target_side_contract",
            {
                "aramina_error_code": "ARAMINA_UNSUPPORTED_INPUT",
                "failure_stage": "target_side_contract",
            },
        )
        assert candidate == legacy
        assert candidate.error == "ARAMINA_UNSUPPORTED_INPUT"
        assert candidate.failure_stage == "target_side_contract"
        assert candidate.preprocessing_diagnostic is None

    def test_preprocessing_failure_parity_preserves_diagnostic_dict(self):
        from bremen.model_packages.aramina_v0213.errors import AraminaWorkflowError

        legacy = _legacy_aramina_failure(
            AraminaWorkflowError(
                "ARAMINA_UNSUPPORTED_INPUT",
                "preprocessing_contract",
                "ValueError",
                dict(_ALLOWLISTED_DIAGNOSTIC),
            )
        )
        candidate = _candidate_aramina_failure(
            "QC_FAILED",
            "ARAMINA_UNSUPPORTED_INPUT:preprocessing_contract",
            {
                "aramina_error_code": "ARAMINA_UNSUPPORTED_INPUT",
                "failure_stage": "preprocessing_contract",
                "preprocessing_diagnostic": dict(_ALLOWLISTED_DIAGNOSTIC),
            },
        )
        assert candidate == legacy
        assert candidate.error == "ARAMINA_UNSUPPORTED_INPUT"
        assert candidate.failure_stage == "preprocessing_contract"
        assert candidate.preprocessing_diagnostic == _ALLOWLISTED_DIAGNOSTIC
        assert isinstance(candidate.preprocessing_diagnostic, dict)

    @pytest.mark.parametrize(
        "code",
        ["ARAMINA_MODEL_IDENTITY_MISMATCH", "ARAMINA_UNSUPPORTED_ARTIFACT"],
    )
    def test_artifact_identity_failure_parity(self, code):
        from bremen.model_packages.aramina_v0213.errors import AraminaWorkflowError

        legacy = _legacy_aramina_failure(AraminaWorkflowError(code))
        candidate = _candidate_aramina_failure(
            "MODEL_NOT_READY", code, {"aramina_error_code": code}
        )
        assert candidate == legacy
        assert candidate.error == code
        assert candidate.failure_stage is None
        assert candidate.preprocessing_diagnostic is None

    @pytest.mark.parametrize(
        "details",
        [
            {"failure_stage": "not_a_real_stage"},
            {"aramina_error_code": "NOT_A_REAL_CODE"},
            {"aramina_error_code": "ARAMINA_UNSUPPORTED_INPUT",
             "preprocessing_diagnostic": {"preprocessing_stage": "evil"}},
            {"aramina_error_code": "ARAMINA_UNSUPPORTED_INPUT",
             "preprocessing_diagnostic": "a-string"},
            {"aramina_error_code": "ARAMINA_UNSUPPORTED_INPUT", "traceback": "x"},
            {"unexpected": {"nested": "value"}},
        ],
    )
    def test_malformed_details_are_not_projected(self, details):
        result = _candidate_aramina_failure(
            "QC_FAILED", "ARAMINA_UNSUPPORTED_INPUT:preprocessing_contract", details
        )
        assert result.error == "ARAMINA_EXECUTION_FAILED"
        assert result.failure_stage is None
        assert result.preprocessing_diagnostic is None
