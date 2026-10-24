"""IR-04 verified release cache tests (deterministic fake S3 + fake installer).

No real S3, no network and no real pip.  The release closure is exercised
end-to-end with a deterministic in-memory S3 stub and a runner that emulates
`venv`/`pip`/entrypoint execution.  Live AWS validation is recorded separately
in the project-memory evidence (not run without authorized access).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from bremen.platform.models.release_cache import (
    READY_MARKER,
    ReleaseCache,
    ReleaseCacheError,
    _restricted_environment,
    _safe_join,
)
from bremen.platform.models.registry import RegistryModelEntry

RELEASE_ID = "test-release-1"
MODEL_ID = "bremen-paper-reference-v0-2-0"
MODEL_VERSION = "0.2.0-paper-reference"
ARTIFACT_BYTES = b"model-bytes"
ARTIFACT_SHA = hashlib.sha256(ARTIFACT_BYTES).hexdigest()
CATALOG_URI = "s3://test-bucket/"  # root prefix: any safe key in the bucket
WHEEL_MAIN = b"main-wheel-bytes"
WHEEL_AUX = b"aux-wheel-bytes"
MAIN_WHEEL_NAME = "numpy-2.5.4-py3-none-any.whl"
AUX_WHEEL_NAME = "numpy-2.5.4-py3-none-any.whl"
MAIN_LOCK = f"numpy==2.5.4 --hash=sha256:{hashlib.sha256(WHEEL_MAIN).hexdigest()}\n".encode()
AUX_LOCK = f"numpy==2.5.4 --hash=sha256:{hashlib.sha256(WHEEL_AUX).hexdigest()}\n".encode()
GOLDEN_FIXTURE = b"golden-fixture-bytes"
GOLDEN_EXPECTED = {
    "status": "ok",
    "probability": 0.7726940329943811,
    "threshold_applied": 0.3585907282566089,
    "prediction": 1,
}


# ---------------------------------------------------------------------------
# Fixtures: a valid release document + deterministic fake S3
# ---------------------------------------------------------------------------


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _host_compatibility() -> dict:
    return {
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
        "abi": str(sysconfig.get_config_var("SOABI") or ""),
        "os": platform.system().lower(),
        "arch": platform.machine(),
        "worker_protocol_version": "bremen.worker.v1",
        "native_libraries": [],
    }


def _runtime_config(release_id: str, *, aux: bool) -> bytes:
    environment = {}
    if aux:
        environment = {
            "BREMEN_PREPROCESS_PYTHON": "@aux/v0.1.7-beta",
            "BREMEN_PREPROCESS_PROVENANCE": (
                "@release/provenance/xrd-preprocessing-v0.1.7-beta.json"
            ),
        }
    return json.dumps(
        {
            "schema_version": "bremen.ml-plugin.runtime.v1",
            "release_id": release_id,
            "variant": "b2",
            "workflow_id": "bremen",
            "artifact": {
                "relative_path": "model/model.joblib",
                "sha256": ARTIFACT_SHA,
                "model_id": MODEL_ID,
                "model_version": MODEL_VERSION,
            },
            "preprocessing_environment": environment,
        }
    ).encode()


def _golden_cases(expected: dict | None = None) -> bytes:
    return json.dumps(
        {
            "schema_version": "bremen.golden-cases.v1",
            "release_id": RELEASE_ID,
            "cases": [
                {
                    "case_id": "golden-benign",
                    "fixture": "benign_one_patient.h5",
                    "fixture_release_path": (
                        "golden_tests/fixtures/benign_one_patient.h5"
                    ),
                    "expected": expected or dict(GOLDEN_EXPECTED),
                }
            ],
        }
    ).encode()


def build_release_files(
    *, aux: bool = False, expected: dict | None = None,
) -> dict[str, bytes]:
    """Relative path -> bytes for a valid, self-contained release."""
    files = {
        "plugin/bremen_ml_plugin-0.1.0-py3-none-any.whl": b"wheel-bytes",
        "model/model.joblib": ARTIFACT_BYTES,
        "configs/runtime.json": _runtime_config(RELEASE_ID, aux=aux),
        "configs/artifact_manifest.json": b'{"model_id": "x"}',
        "requirements/main.lock": MAIN_LOCK,
        f"wheelhouse/main/{MAIN_WHEEL_NAME}": WHEEL_MAIN,
        "provenance/build.json": b'{"build_id": "test"}',
        "golden_tests/cases.json": _golden_cases(expected),
        "golden_tests/fixtures/benign_one_patient.h5": GOLDEN_FIXTURE,
    }
    if aux:
        files["requirements/aux-v0.1.7-beta.lock"] = AUX_LOCK
        files[f"wheelhouse/aux/v0.1.7-beta/{AUX_WHEEL_NAME}"] = WHEEL_AUX
        files["provenance/xrd-preprocessing-v0.1.7-beta.json"] = b'{"source_commit": "x"}'
    return files


def build_manifest(
    files: dict[str, bytes],
    *,
    release_id: str = RELEASE_ID,
    model_id: str = MODEL_ID,
    compatibility: dict | None = None,
    extra_golden: list | None = None,
    relative_path_override: dict | None = None,
) -> dict:
    def ref(relative: str, role: str, *, size: bool = True) -> dict:
        payload = files[relative]
        entry = {
            "role": role,
            "relative_path": (relative_path_override or {}).get(relative, relative),
            "s3_key": f"releases/{release_id}/{relative}",
            "sha256": _sha(payload),
        }
        if size:
            entry["size_bytes"] = len(payload)
        return entry

    roles = {
        "plugin/bremen_ml_plugin-0.1.0-py3-none-any.whl": "plugin_wheel",
        "model/model.joblib": "model_artifact",
        "configs/runtime.json": "config",
        "configs/artifact_manifest.json": "config",
        "requirements/main.lock": "requirements_lock",
        f"wheelhouse/main/{MAIN_WHEEL_NAME}": "dependency_wheel",
        "provenance/build.json": "provenance",
    }
    file_refs = [ref(path, role) for path, role in roles.items()]
    if "requirements/aux-v0.1.7-beta.lock" in files:
        file_refs.append(
            ref("requirements/aux-v0.1.7-beta.lock", "requirements_lock_aux")
        )
        file_refs.append(
            ref(
                f"wheelhouse/aux/v0.1.7-beta/{AUX_WHEEL_NAME}",
                "dependency_wheel_aux",
            )
        )
        file_refs.append(
            ref("provenance/xrd-preprocessing-v0.1.7-beta.json", "provenance")
        )
    golden = [
        ref("golden_tests/cases.json", "golden_cases"),
        ref(
            "golden_tests/fixtures/benign_one_patient.h5",
            "golden_fixture",
        ),
    ]
    if extra_golden:
        golden.extend(extra_golden)

    environments: dict = {
        "main": {"requirements_lock_sha256": _sha(files["requirements/main.lock"])}
    }
    if "requirements/aux-v0.1.7-beta.lock" in files:
        environments["preprocess_v0_1_7_beta"] = {
            "environment_ref": "@aux/v0.1.7-beta",
            "preprocessing_release": "v0.1.7-beta",
            "requirements_lock_sha256": _sha(
                files["requirements/aux-v0.1.7-beta.lock"]
            ),
        }

    return {
        "schema_version": "bremen.inference-release.v1",
        "release_id": release_id,
        "model": {
            "model_id": model_id,
            "model_version": MODEL_VERSION,
            "workflow_id": "bremen",
            "artifact_identity": f"sha256:{ARTIFACT_SHA}",
        },
        "compatibility": compatibility or _host_compatibility(),
        "entrypoint": {
            "module": "bremen.ml_plugin.entrypoint",
            "callable": "main",
        },
        "files": file_refs,
        "environments": environments,
        "scientific_metadata": {
            "preprocessing_release": "none",
            "artifact_checksum": ARTIFACT_SHA,
            "threshold_source": "artifact.portable_logreg.threshold_applied",
            "feature_order_hash": "",
            "config_hash": "",
        },
        "golden_tests": golden,
        "build": {
            "source_repository": "https://example.invalid/repo",
            "commit": "a" * 40,
            "build_id": "test-build",
        },
    }


class FakeS3:
    """Deterministic in-memory S3 stand-in for the two calls the cache uses."""

    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = dict(objects)
        self.requested: list[str] = []
        self.buckets: list[str] = []

    def get_object(self, *, Bucket: str, Key: str):
        self.requested.append(Key)
        self.buckets.append(Bucket)
        if Key not in self.objects:
            raise KeyError(Key)
        return {"Body": io.BytesIO(self.objects[Key])}


def serve_release(
    release_id: str = RELEASE_ID,
    *,
    aux: bool = False,
    expected: dict | None = None,
    manifest: dict | None = None,
) -> tuple[FakeS3, bytes, dict]:
    files = build_release_files(aux=aux, expected=expected)
    document = manifest or build_manifest(files, release_id=release_id)
    manifest_bytes = json.dumps(document, sort_keys=True).encode()
    objects = {ref["s3_key"]: files[ref["relative_path"]] for ref in document["files"]}
    for ref in document["golden_tests"]:
        objects[ref["s3_key"]] = files[ref["relative_path"]]
    manifest_key = f"releases/{release_id}/manifest.json"
    objects[manifest_key] = manifest_bytes
    return FakeS3(objects), manifest_bytes, document


def make_entry(
    document: dict, manifest_bytes: bytes, *, manifest_key: str | None = None,
    model_id: str | None = None,
) -> RegistryModelEntry:
    return RegistryModelEntry(
        model_id=model_id or document["model"]["model_id"],
        display_name="Test model",
        workflow_id="bremen",
        model_version=document["model"]["model_version"],
        artifact_type="bremen.joblib.model_package",
        feature_schema_version="v0.1",
        decision_policy_id="p",
        decision_policy_version="1",
        technical_ready=True,
        _package={},
        _runtime_release={
            "schema_version": "bremen.inference-release.v1",
            "release_id": document["release_id"],
            "manifest_key": manifest_key
            or f"releases/{document['release_id']}/manifest.json",
            "manifest_sha256": _sha(manifest_bytes),
        },
    )


class FakeRunner:
    """Emulates venv/pip/entrypoint without touching the network or real pip."""

    def __init__(
        self,
        *,
        fail_pip: bool = False,
        fail_venv: bool = False,
        smoke_status: str = "ok",
        golden_result: dict | None = None,
        golden_error: dict | None = None,
        delay: float = 0.0,
    ) -> None:
        self.fail_pip = fail_pip
        self.fail_venv = fail_venv
        self.smoke_status = smoke_status
        self.golden_result = golden_result
        self.golden_error = golden_error
        self.delay = delay
        self.commands: list[list[str]] = []
        self.environments: list[dict[str, str]] = []
        self._lock = threading.Lock()
        self.venv_count = 0
        self.pip_count = 0

    def __call__(self, command, cwd, timeout, env=None):
        cmd = list(command)
        with self._lock:
            self.commands.append(cmd)
            self.environments.append(dict(env or {}))
        if self.delay:
            time.sleep(self.delay)
        if cmd[1:3] == ["-m", "venv"]:
            if self.fail_venv:
                return SimpleNamespace(returncode=1, stdout="", stderr="")
            env_dir = cmd[3]
            bin_dir = os.path.join(env_dir, "bin")
            os.makedirs(bin_dir, exist_ok=True)
            python = os.path.join(bin_dir, "python")
            Path(python).write_text("#!/bin/sh\n")
            os.chmod(python, 0o755)
            self.venv_count += 1
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "pip" in cmd:
            if self.fail_pip:
                return SimpleNamespace(returncode=1, stdout="", stderr="")
            self.pip_count += 1
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        job_dir = cmd[cmd.index("--job-dir") + 1]
        with open(os.path.join(job_dir, "request.json"), encoding="utf-8") as stream:
            request = json.load(stream)
        result = {
            "protocol": "bremen.worker.v1",
            "request_id": request["request_id"],
            "operation": request["operation"],
            "model_id": request["model_id"],
            "release_digest": request["release_digest"],
            "status": self.smoke_status,
        }
        if request["operation"] == "predict":
            if self.golden_error is not None:
                result["status"] = "error"
                result["error"] = dict(self.golden_error)
                result.pop("payload", None)
            else:
                result["status"] = "ok"
                result["payload"] = {
                    "result": dict(self.golden_result or {
                        "probability": GOLDEN_EXPECTED["probability"],
                        "threshold_applied": GOLDEN_EXPECTED["threshold_applied"],
                        "prediction": GOLDEN_EXPECTED["prediction"],
                    })
                }
        elif self.smoke_status == "ok":
            result["payload"] = {"compatible": True, "safe_reason": None}
        else:
            result["error"] = {"code": "QC_FAILED", "safe_reason": "smoke"}
        with open(os.path.join(job_dir, "result.json"), "w", encoding="utf-8") as stream:
            json.dump(result, stream)
        return SimpleNamespace(returncode=0, stdout="", stderr="")


def make_cache(tmp_path, s3: FakeS3, runner: FakeRunner | None = None, **kwargs):
    return ReleaseCache(
        str(tmp_path / "cache"),
        catalog_uri=kwargs.pop("catalog_uri", CATALOG_URI),
        s3_client=s3,
        runner=runner or FakeRunner(),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Happy path / warm reuse
# ---------------------------------------------------------------------------


def test_trusted_manifest_happy_path(tmp_path):
    s3, manifest_bytes, document = serve_release(aux=True)
    runner = FakeRunner()
    cache = make_cache(tmp_path, s3, runner)
    entry = make_entry(document, manifest_bytes)

    installed = cache.install(entry)

    assert installed.release_id == RELEASE_ID
    assert installed.model_id == MODEL_ID
    assert installed.manifest_sha256 == _sha(manifest_bytes)
    assert os.path.isfile(installed.main_python)
    assert os.path.isfile(os.path.join(installed.release_dir, "manifest.json"))
    assert os.path.isfile(os.path.join(installed.release_dir, "model", "model.joblib"))
    assert os.path.isdir(os.path.join(installed.release_dir, "aux", "v0.1.7-beta"))
    assert os.path.isdir(os.path.join(installed.release_dir, "wheelhouse", "main"))
    ready = json.loads(
        Path(cache.root, installed.manifest_sha256, READY_MARKER).read_text()
    )
    assert ready["release_id"] == RELEASE_ID
    assert ready["model_id"] == MODEL_ID
    assert ready["manifest_sha256"] == installed.manifest_sha256
    assert runner.venv_count == 2  # main + one auxiliary
    pip_commands = [cmd for cmd in runner.commands if "pip" in cmd]
    assert any("--require-hashes" in " ".join(cmd) for cmd in pip_commands)
    find_links = [
        cmd[cmd.index("--find-links") + 1] for cmd in pip_commands
        if "--find-links" in cmd
    ]
    assert find_links
    for path in find_links:
        assert path.startswith(installed.release_dir)
        assert os.path.basename(path) in {"main", "v0.1.7-beta"}


def test_ready_reused_on_warm_install(tmp_path):
    s3, manifest_bytes, document = serve_release()
    runner = FakeRunner()
    cache = make_cache(tmp_path, s3, runner)
    entry = make_entry(document, manifest_bytes)

    first = cache.install(entry)
    calls = len(runner.commands)
    second = cache.install(entry)

    assert second.manifest_sha256 == first.manifest_sha256
    assert len(runner.commands) == calls  # no reinstall


def test_corrupt_ready_metadata_triggers_reinstall(tmp_path):
    s3, manifest_bytes, document = serve_release()
    runner = FakeRunner()
    cache = make_cache(tmp_path, s3, runner)
    entry = make_entry(document, manifest_bytes)
    installed = cache.install(entry)

    ready_path = Path(cache.root, installed.manifest_sha256, READY_MARKER)
    ready_path.write_text('{"schema_version": "wrong"}')
    assert cache.read_ready(installed.manifest_sha256) is None

    cache.install(entry)
    assert cache.read_ready(installed.manifest_sha256) is not None


# ---------------------------------------------------------------------------
# Trust / integrity failures
# ---------------------------------------------------------------------------


def test_manifest_digest_mismatch(tmp_path):
    s3, manifest_bytes, document = serve_release()
    entry = make_entry(document, manifest_bytes)
    reference = entry.get_runtime_release()
    reference["manifest_sha256"] = "b" * 64
    entry._runtime_release.update(reference)
    cache = make_cache(tmp_path, s3)

    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(entry)
    assert excinfo.value.category == "manifest_digest_mismatch"


def test_missing_manifest(tmp_path):
    s3, manifest_bytes, document = serve_release()
    del s3.objects[f"releases/{RELEASE_ID}/manifest.json"]
    cache = make_cache(tmp_path, s3)
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "manifest_missing"


def test_missing_release_object(tmp_path):
    s3, manifest_bytes, document = serve_release()
    del s3.objects[f"releases/{RELEASE_ID}/model/model.joblib"]
    cache = make_cache(tmp_path, s3)
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "release_object_missing"


def test_missing_declared_wheel_fails_before_ready(tmp_path):
    s3, manifest_bytes, document = serve_release()
    del s3.objects[f"releases/{RELEASE_ID}/wheelhouse/main/{MAIN_WHEEL_NAME}"]
    cache = make_cache(tmp_path, s3)
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "release_object_missing"
    assert cache.read_ready(_sha(manifest_bytes)) is None


def test_tampered_dependency_wheel_fails_checksum_before_install(tmp_path):
    s3, manifest_bytes, document = serve_release()
    key = f"releases/{RELEASE_ID}/wheelhouse/main/{MAIN_WHEEL_NAME}"
    s3.objects[key] = b"tampered" + WHEEL_MAIN[len(b"tampered"):]
    runner = FakeRunner()
    cache = make_cache(tmp_path, s3, runner)
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "release_file_checksum_mismatch"
    assert runner.commands == []


def test_file_checksum_mismatch(tmp_path):
    s3, manifest_bytes, document = serve_release()
    key = f"releases/{RELEASE_ID}/model/model.joblib"
    s3.objects[key] = b"model-bytez"  # same length, different bytes
    cache = make_cache(tmp_path, s3)
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "release_file_checksum_mismatch"


def test_file_size_mismatch(tmp_path):
    files = build_release_files()
    payload = ARTIFACT_BYTES + b"extra"
    for relative in files:
        if relative == "model/model.joblib":
            files[relative] = payload
    document = build_manifest(files)
    document["model"]["artifact_identity"] = f"sha256:{_sha(payload)}"
    document["scientific_metadata"]["artifact_checksum"] = _sha(payload)
    runtime = json.loads(files["configs/runtime.json"])
    runtime["artifact"]["sha256"] = _sha(payload)
    files["configs/runtime.json"] = json.dumps(runtime).encode()
    # Recompute all refs so only the declared artifact size is wrong.
    document = build_manifest(files)
    for ref in document["files"]:
        if ref["role"] == "model_artifact":
            ref["size_bytes"] = len(payload) + 1
    manifest_bytes = json.dumps(document, sort_keys=True).encode()
    s3 = FakeS3({
        **{ref["s3_key"]: files[ref["relative_path"]] for ref in document["files"]},
        **{
            ref["s3_key"]: files[ref["relative_path"]]
            for ref in document["golden_tests"]
        },
        f"releases/{RELEASE_ID}/manifest.json": manifest_bytes,
    })
    cache = make_cache(tmp_path, s3)
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "release_file_size_mismatch"


def test_path_traversal_rejected_in_manifest(tmp_path):
    files = build_release_files()
    document = build_manifest(
        files, relative_path_override={"model/model.joblib": "../../escape.joblib"}
    )
    manifest_bytes = json.dumps(document, sort_keys=True).encode()
    s3 = FakeS3({f"releases/{RELEASE_ID}/manifest.json": manifest_bytes})
    cache = make_cache(tmp_path, s3)

    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "manifest_invalid"


def test_duplicate_relative_path_rejected(tmp_path):
    files = build_release_files()
    document = build_manifest(files)
    document["files"].append(dict(document["files"][1]))
    manifest_bytes = json.dumps(document, sort_keys=True).encode()
    s3 = FakeS3({f"releases/{RELEASE_ID}/manifest.json": manifest_bytes})
    cache = make_cache(tmp_path, s3)

    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "manifest_invalid"


def test_safe_join_rejects_escape(tmp_path):
    with pytest.raises(ReleaseCacheError):
        _safe_join(str(tmp_path), "../outside")
    with pytest.raises(ReleaseCacheError):
        _safe_join(str(tmp_path), "/absolute")
    with pytest.raises(ReleaseCacheError):
        _safe_join(str(tmp_path), "a/../../b")


def test_identity_mismatch_between_reference_and_manifest(tmp_path):
    s3, manifest_bytes, document = serve_release()
    document["model"]["model_id"] = "different-model"
    manifest_bytes = json.dumps(document, sort_keys=True).encode()
    s3.objects[f"releases/{RELEASE_ID}/manifest.json"] = manifest_bytes
    cache = make_cache(tmp_path, s3)

    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes, model_id=MODEL_ID))
    assert excinfo.value.category == "release_identity_mismatch"


# ---------------------------------------------------------------------------
# Compatibility
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("python_implementation", "PyPy"),
        ("python_version", "2.7.0"),
        ("abi", "cpython-999-darwin"),
        ("os", "plan9"),
        ("arch", "sparc"),
        ("worker_protocol_version", "bremen.worker.v0"),
    ],
)
def test_incompatible_host_rejected_before_install(tmp_path, field, value):
    files = build_release_files()
    compatibility = _host_compatibility()
    compatibility[field] = value
    document = build_manifest(files, compatibility=compatibility)
    manifest_bytes = json.dumps(document, sort_keys=True).encode()
    s3 = FakeS3({f"releases/{RELEASE_ID}/manifest.json": manifest_bytes})
    runner = FakeRunner()
    cache = make_cache(tmp_path, s3, runner)

    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category in {"incompatible_host", "manifest_invalid"}
    assert runner.commands == []


# ---------------------------------------------------------------------------
# Golden gate (mandatory)
# ---------------------------------------------------------------------------


def _manifest_with_cases(cases: list[dict]) -> tuple[FakeS3, bytes, dict]:
    files = build_release_files()
    files["golden_tests/cases.json"] = json.dumps(
        {
            "schema_version": "bremen.golden-cases.v1",
            "release_id": RELEASE_ID,
            "cases": cases,
        }
    ).encode()
    document = build_manifest(files)
    manifest_bytes = json.dumps(document, sort_keys=True).encode()
    s3 = FakeS3({
        **{ref["s3_key"]: files[ref["relative_path"]] for ref in document["files"]},
        **{
            ref["s3_key"]: files[ref["relative_path"]]
            for ref in document["golden_tests"]
        },
        f"releases/{RELEASE_ID}/manifest.json": manifest_bytes,
    })
    return s3, manifest_bytes, document


def _case(**expected) -> dict:
    values = dict(GOLDEN_EXPECTED)
    values.update(expected)
    return {
        "case_id": "golden-case",
        "fixture": "benign_one_patient.h5",
        "fixture_release_path": "golden_tests/fixtures/benign_one_patient.h5",
        "expected": values,
    }


def test_ready_requires_golden_cases(tmp_path):
    s3, manifest_bytes, document = _manifest_with_cases([])
    cache = make_cache(tmp_path, s3)
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "smoke_failed"
    assert cache.read_ready(_sha(manifest_bytes)) is None


def test_missing_golden_fixture_fails(tmp_path):
    s3, manifest_bytes, document = serve_release()
    del s3.objects[
        f"releases/{RELEASE_ID}/golden_tests/fixtures/benign_one_patient.h5"
    ]
    cache = make_cache(tmp_path, s3)
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "release_object_missing"


def test_golden_fixture_checksum_mismatch_fails(tmp_path):
    s3, manifest_bytes, document = serve_release()
    key = f"releases/{RELEASE_ID}/golden_tests/fixtures/benign_one_patient.h5"
    s3.objects[key] = b"golden-fixture-bytez"  # same length, different bytes
    cache = make_cache(tmp_path, s3)
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "release_file_checksum_mismatch"


def test_expected_probability_mismatch_fails(tmp_path):
    s3, manifest_bytes, document = serve_release()
    runner = FakeRunner(
        golden_result={
            "probability": 0.1,
            "threshold_applied": GOLDEN_EXPECTED["threshold_applied"],
            "prediction": 1,
        }
    )
    cache = make_cache(tmp_path, s3, runner)
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "smoke_failed"
    assert cache.read_ready(_sha(manifest_bytes)) is None


def test_expected_threshold_mismatch_fails(tmp_path):
    s3, manifest_bytes, document = serve_release()
    runner = FakeRunner(
        golden_result={
            "probability": GOLDEN_EXPECTED["probability"],
            "threshold_applied": 0.5,
            "prediction": 1,
        }
    )
    cache = make_cache(tmp_path, s3, runner)
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "smoke_failed"


def test_expected_prediction_mismatch_fails(tmp_path):
    s3, manifest_bytes, document = serve_release()
    runner = FakeRunner(
        golden_result={
            "probability": GOLDEN_EXPECTED["probability"],
            "threshold_applied": GOLDEN_EXPECTED["threshold_applied"],
            "prediction": 0,
        }
    )
    cache = make_cache(tmp_path, s3, runner)
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "smoke_failed"


def test_expected_typed_failure_mismatch_fails(tmp_path):
    expected = {
        "status": "error",
        "error_code": "QC_FAILED",
        "safe_reason": "raw_peak_gate_failed",
    }
    s3, manifest_bytes, document = serve_release(expected=expected)
    runner = FakeRunner(
        golden_error={"code": "QC_FAILED", "safe_reason": "different_reason"}
    )
    cache = make_cache(tmp_path, s3, runner)
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "smoke_failed"


def test_expected_typed_failure_passes(tmp_path):
    expected = {
        "status": "error",
        "error_code": "QC_FAILED",
        "safe_reason": "raw_peak_gate_failed",
    }
    s3, manifest_bytes, document = serve_release(expected=expected)
    runner = FakeRunner(
        golden_error={"code": "QC_FAILED", "safe_reason": "raw_peak_gate_failed"}
    )
    cache = make_cache(tmp_path, s3, runner)
    installed = cache.install(make_entry(document, manifest_bytes))
    assert cache.read_ready(installed.manifest_sha256) is not None


# ---------------------------------------------------------------------------
# Install failures / interruption / concurrency
# ---------------------------------------------------------------------------


def test_offline_install_failure_writes_no_ready(tmp_path):
    s3, manifest_bytes, document = serve_release()
    cache = make_cache(tmp_path, s3, FakeRunner(fail_pip=True))

    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "offline_install_failed"
    assert cache.read_ready(_sha(manifest_bytes)) is None
    assert not os.path.exists(os.path.join(cache.root, _sha(manifest_bytes)))


def test_lock_hash_failure_is_an_offline_install_failure(tmp_path):
    s3, manifest_bytes, document = serve_release()
    runner = FakeRunner(fail_pip=True)
    cache = make_cache(tmp_path, s3, runner)
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "offline_install_failed"
    pip_commands = [cmd for cmd in runner.commands if "pip" in cmd]
    assert pip_commands
    assert "--require-hashes" in pip_commands[0]
    assert "--no-index" in pip_commands[0]
    assert "--only-binary=:all:" in pip_commands[0]


def test_undeclared_wheel_never_used(tmp_path, monkeypatch):
    monkeypatch.delenv("BREMEN_RELEASE_WHEELHOUSE", raising=False)
    s3, manifest_bytes, document = serve_release()
    external = tmp_path / "external"
    external.mkdir()
    (external / "evil-9.9.9-py3-none-any.whl").write_bytes(b"evil")
    runner = FakeRunner()
    cache = make_cache(tmp_path, s3, runner)
    installed = cache.install(make_entry(document, manifest_bytes))
    pip_commands = [cmd for cmd in runner.commands if "pip" in cmd]
    for command in pip_commands:
        if "--find-links" in command:
            path = command[command.index("--find-links") + 1]
            assert path.startswith(installed.release_dir)
            assert str(external) not in path


def test_install_works_without_external_wheelhouse_env(tmp_path, monkeypatch):
    monkeypatch.delenv("BREMEN_RELEASE_WHEELHOUSE", raising=False)
    monkeypatch.delenv("BREMEN_RELEASE_GOLDEN_FIXTURES", raising=False)
    s3, manifest_bytes, document = serve_release(aux=True)
    cache = make_cache(tmp_path, s3)
    installed = cache.install(make_entry(document, manifest_bytes))
    assert cache.read_ready(installed.manifest_sha256) is not None
    assert os.path.isdir(os.path.join(installed.release_dir, "wheelhouse", "main"))


def test_interrupted_install_leaves_no_ready_and_retries(tmp_path):
    s3, manifest_bytes, document = serve_release()
    runner = FakeRunner(fail_pip=True)
    cache = make_cache(tmp_path, s3, runner)
    digest = _sha(manifest_bytes)

    with pytest.raises(ReleaseCacheError):
        cache.install(make_entry(document, manifest_bytes))
    assert cache.read_ready(digest) is None
    assert not os.path.exists(os.path.join(cache.root, digest))
    assert not [name for name in os.listdir(cache.root) if name.startswith(".staging-")]

    retry = make_cache(tmp_path, s3, FakeRunner())
    installed = retry.install(make_entry(document, manifest_bytes))
    assert installed.manifest_sha256 == digest


def test_concurrent_install_same_digest_is_serialized(tmp_path):
    s3, manifest_bytes, document = serve_release()
    runner = FakeRunner(delay=0.05)
    cache = make_cache(tmp_path, s3, runner)
    entry = make_entry(document, manifest_bytes)
    results: list = []
    errors: list = []

    def worker() -> None:
        try:
            results.append(cache.install(entry))
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    assert len(results) == 3
    assert {r.manifest_sha256 for r in results} == {_sha(manifest_bytes)}
    assert runner.venv_count == 1  # exactly one installation


def test_smoke_failure_writes_no_ready(tmp_path):
    s3, manifest_bytes, document = serve_release()
    cache = make_cache(tmp_path, s3, FakeRunner(smoke_status="error"))
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "smoke_failed"
    assert cache.read_ready(_sha(manifest_bytes)) is None


def test_invalid_runtime_configuration_writes_no_ready(tmp_path):
    s3, manifest_bytes, document = serve_release(aux=True)
    files = build_release_files(aux=True)
    runtime = json.loads(files["configs/runtime.json"])
    runtime["artifact"]["sha256"] = "0" * 64
    files["configs/runtime.json"] = json.dumps(runtime).encode()
    document = build_manifest(files)
    manifest_bytes = json.dumps(document, sort_keys=True).encode()
    s3.objects[f"releases/{RELEASE_ID}/manifest.json"] = manifest_bytes
    s3.objects[f"releases/{RELEASE_ID}/configs/runtime.json"] = files[
        "configs/runtime.json"
    ]

    cache = make_cache(tmp_path, s3)
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "invalid_runtime_configuration"
    assert cache.read_ready(_sha(manifest_bytes)) is None


# ---------------------------------------------------------------------------
# Trusted bucket / catalog configuration
# ---------------------------------------------------------------------------


def test_resolve_has_no_bucket_override(tmp_path):
    with pytest.raises(TypeError):
        ReleaseCache(  # type: ignore[call-arg]
            str(tmp_path / "cache"), bucket="attacker-bucket",
        )


def test_configured_catalog_bucket_is_used(tmp_path):
    s3, manifest_bytes, document = serve_release()
    cache = make_cache(tmp_path, s3)
    cache.install(make_entry(document, manifest_bytes))
    assert set(s3.buckets) == {"test-bucket"}


def test_runtime_release_cannot_switch_bucket(tmp_path):
    s3, manifest_bytes, document = serve_release()
    entry = make_entry(
        document, manifest_bytes, manifest_key="/other-bucket/manifest.json",
    )
    cache = make_cache(tmp_path, s3)
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(entry)
    assert excinfo.value.category == "release_reference_invalid"


@pytest.mark.parametrize(
    "catalog_uri",
    ["", "not-a-uri", "https://bucket/prefix", "s3://", "/local/path"],
)
def test_malformed_trusted_catalog_uri_fails_closed(tmp_path, catalog_uri):
    with pytest.raises(ReleaseCacheError) as excinfo:
        ReleaseCache(
            str(tmp_path / "cache"),
            catalog_uri=catalog_uri,
            s3_client=FakeS3({}),
        )
    assert excinfo.value.category == "invalid_configuration"


def test_missing_catalog_configuration_fails_closed(tmp_path, monkeypatch):
    monkeypatch.delenv("BREMEN_MODEL_CATALOG_URI", raising=False)
    with pytest.raises(ReleaseCacheError) as excinfo:
        ReleaseCache(str(tmp_path / "cache"), s3_client=FakeS3({}))
    assert excinfo.value.category == "invalid_configuration"


class TestTrustedPrefixBoundary:
    """runtime_release.manifest_key must stay beneath the trusted prefix."""

    def _entry(self, manifest_key: str) -> RegistryModelEntry:
        return RegistryModelEntry(
            model_id=MODEL_ID,
            display_name="m",
            workflow_id="bremen",
            model_version=MODEL_VERSION,
            artifact_type="bremen.joblib.model_package",
            feature_schema_version="v0.1",
            decision_policy_id="p",
            decision_policy_version="1",
            technical_ready=True,
            _package={},
            _runtime_release={
                "schema_version": "bremen.inference-release.v1",
                "release_id": RELEASE_ID,
                "manifest_key": manifest_key,
                "manifest_sha256": "a" * 64,
            },
        )

    def test_key_inside_trusted_prefix_resolves(self, tmp_path):
        s3 = FakeS3({})
        cache = ReleaseCache(
            str(tmp_path / "cache"),
            catalog_uri="s3://trusted-bucket/catalog/",
            s3_client=s3,
        )
        reference = cache.resolve(
            self._entry("catalog/releases/r1/manifest.json")
        )
        assert reference.manifest_key == "catalog/releases/r1/manifest.json"
        assert reference.manifest_sha256 == "a" * 64

    def test_key_outside_prefix_fails_before_download(self, tmp_path):
        s3 = FakeS3({})
        cache = ReleaseCache(
            str(tmp_path / "cache"),
            catalog_uri="s3://trusted-bucket/catalog/",
            s3_client=s3,
        )
        with pytest.raises(ReleaseCacheError) as excinfo:
            cache.install(self._entry("releases/r1/manifest.json"))
        assert excinfo.value.category == "release_reference_invalid"
        assert s3.requested == []

    def test_lookalike_prefix_fails(self, tmp_path):
        s3 = FakeS3({})
        cache = ReleaseCache(
            str(tmp_path / "cache"),
            catalog_uri="s3://trusted-bucket/catalog/",
            s3_client=s3,
        )
        with pytest.raises(ReleaseCacheError) as excinfo:
            cache.install(self._entry("catalog-evil/releases/r1/manifest.json"))
        assert excinfo.value.category == "release_reference_invalid"
        assert s3.requested == []

    def test_nested_key_inside_prefix_resolves(self, tmp_path):
        s3 = FakeS3({})
        cache = ReleaseCache(
            str(tmp_path / "cache"),
            catalog_uri="s3://trusted-bucket/catalog/",
            s3_client=s3,
        )
        reference = cache.resolve(
            self._entry("catalog/releases/team/model/manifest.json")
        )
        assert reference.manifest_key == (
            "catalog/releases/team/model/manifest.json"
        )

    def test_absolute_and_traversal_keys_fail(self, tmp_path):
        s3 = FakeS3({})
        cache = ReleaseCache(
            str(tmp_path / "cache"),
            catalog_uri="s3://trusted-bucket/catalog/",
            s3_client=s3,
        )
        for key in (
            "/catalog/releases/r1/manifest.json",
            "catalog/../catalog/releases/r1/manifest.json",
            "other/catalog/releases/r1/manifest.json",
        ):
            with pytest.raises(ReleaseCacheError) as excinfo:
                cache.resolve(self._entry(key))
            assert excinfo.value.category == "release_reference_invalid"
        assert s3.requested == []

    def test_root_prefix_allows_any_safe_key(self, tmp_path):
        s3 = FakeS3({})
        cache = ReleaseCache(
            str(tmp_path / "cache"),
            catalog_uri="s3://trusted-bucket/",
            s3_client=s3,
        )
        reference = cache.resolve(
            self._entry("releases/r1/manifest.json")
        )
        assert reference.manifest_key == "releases/r1/manifest.json"

    def test_inside_prefix_key_still_fetches(self, tmp_path):
        s3, manifest_bytes, document = serve_release()
        document["release_id"] = RELEASE_ID
        manifest_bytes = json.dumps(document, sort_keys=True).encode()
        prefixed = f"catalog/releases/{RELEASE_ID}/manifest.json"
        s3.objects[prefixed] = manifest_bytes
        cache = ReleaseCache(
            str(tmp_path / "cache"),
            catalog_uri="s3://trusted-bucket/catalog/",
            s3_client=s3,
        )
        entry = make_entry(document, manifest_bytes, manifest_key=prefixed)
        reference = cache.resolve(entry)
        body = cache._fetch_manifest(reference)
        assert body == manifest_bytes
        assert s3.requested[-1] == prefixed
        assert set(s3.buckets) == {"trusted-bucket"}


# ---------------------------------------------------------------------------
# Subprocess environment isolation
# ---------------------------------------------------------------------------


def test_restricted_environment_omits_credentials(monkeypatch):
    secrets = {
        "AWS_ACCESS_KEY_ID": "AKIAFAKE",
        "AWS_SECRET_ACCESS_KEY": "fake-secret",
        "AWS_SESSION_TOKEN": "fake-token",
        "AWS_SECURITY_TOKEN": "fake-security-token",
        "AWS_PROFILE": "prod",
        "AWS_DEFAULT_PROFILE": "prod",
        "AWS_WEB_IDENTITY_TOKEN_FILE": "/tmp/token",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI": "/v2/creds",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI": "http://169.254.170.2/creds",
        "BOTO_CONFIG": "/tmp/boto",
        "PYTHONPATH": "/attack/path",
    }
    for key, value in secrets.items():
        monkeypatch.setenv(key, value)

    environment = _restricted_environment()

    for key in secrets:
        assert key not in environment
    assert environment["PYTHONNOUSERSITE"] == "1"


def test_child_process_cannot_observe_credentials(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAFAKE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "fake-token")
    monkeypatch.setenv("PYTHONPATH", "/attack/path")

    completed = subprocess.run(
        [sys.executable, "-c", "import os; print(sorted(os.environ))"],
        text=True,
        capture_output=True,
        env=_restricted_environment(),
        check=False,
    )

    assert completed.returncode == 0
    visible = completed.stdout
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "PYTHONPATH"):
        assert key not in visible


def test_install_and_smoke_receive_restricted_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAFAKE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "fake-secret")
    monkeypatch.setenv("PYTHONPATH", "/attack/path")
    s3, manifest_bytes, document = serve_release()
    runner = FakeRunner()
    cache = make_cache(tmp_path, s3, runner)
    cache.install(make_entry(document, manifest_bytes))

    assert runner.environments
    for environment in runner.environments:
        assert "AWS_ACCESS_KEY_ID" not in environment
        assert "AWS_SECRET_ACCESS_KEY" not in environment
        assert "PYTHONPATH" not in environment


# ---------------------------------------------------------------------------
# Admission / eviction
# ---------------------------------------------------------------------------


def test_insufficient_disk_rejected_before_download(tmp_path, monkeypatch):
    s3, manifest_bytes, document = serve_release()
    cache = make_cache(tmp_path, s3)
    monkeypatch.setattr(
        "bremen.platform.models.release_cache.shutil.disk_usage",
        lambda path: SimpleNamespace(total=1, used=1, free=1),
    )
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "insufficient_disk"
    assert s3.requested == [f"releases/{RELEASE_ID}/manifest.json"]


def test_declared_size_over_cache_budget_rejected(tmp_path):
    s3, manifest_bytes, document = serve_release()
    cache = make_cache(tmp_path, s3, max_cache_bytes=64)
    with pytest.raises(ReleaseCacheError) as excinfo:
        cache.install(make_entry(document, manifest_bytes))
    assert excinfo.value.category == "insufficient_cache_budget"


@pytest.mark.parametrize("factor", [0, -1, float("nan"), float("inf")])
def test_invalid_free_space_factor_rejected(tmp_path, factor):
    with pytest.raises(ReleaseCacheError) as excinfo:
        make_cache(tmp_path, FakeS3({}), free_space_factor=factor)
    assert excinfo.value.category == "invalid_configuration"


def _fake_entry(cache, digest: str, *, size: int) -> None:
    directory = Path(cache.root, digest)
    directory.mkdir(parents=True)
    (directory / "payload.bin").write_bytes(b"x" * size)
    ready = {
        "schema_version": "bremen.release-ready.v1",
        "release_id": f"release-{digest[:8]}",
        "model_id": f"model-{digest[:8]}",
        "manifest_sha256": digest,
        "main_python": str(directory / "env" / "bin" / "python"),
    }
    (directory / "env" / "bin").mkdir(parents=True)
    Path(ready["main_python"]).write_text("")
    (directory / READY_MARKER).write_text(json.dumps(ready))


def test_inactive_eviction(tmp_path):
    cache = make_cache(
        tmp_path, FakeS3({}), max_cache_bytes=10 * 1024,
    )
    old, new = "a" * 64, "b" * 64
    _fake_entry(cache, old, size=8192)
    _fake_entry(cache, new, size=8192)
    os.utime(Path(cache.root, old, READY_MARKER), (1, 1))

    removed = cache.evict()

    assert removed == [old]
    assert not os.path.exists(os.path.join(cache.root, old))
    assert os.path.exists(os.path.join(cache.root, new))


def test_protected_release_not_evicted(tmp_path):
    cache = make_cache(
        tmp_path, FakeS3({}), max_cache_bytes=10 * 1024,
    )
    old, new = "c" * 64, "d" * 64
    _fake_entry(cache, old, size=8192)
    _fake_entry(cache, new, size=8192)
    os.utime(Path(cache.root, old, READY_MARKER), (1, 1))

    removed = cache.evict(protected_digests=[old])

    assert removed == [new]
    assert os.path.exists(os.path.join(cache.root, old))


def test_partial_entries_never_evicted_or_used(tmp_path):
    cache = make_cache(tmp_path, FakeS3({}), max_cache_bytes=1)
    partial = "e" * 64
    Path(cache.root, partial).mkdir(parents=True)
    (Path(cache.root, partial, "payload.bin")).write_bytes(b"x" * 100)
    Path(cache.root, ".staging-deadbeef").mkdir(parents=True)

    assert cache.evict() == []
    assert os.path.exists(os.path.join(cache.root, partial))
    assert cache.read_ready(partial) is None


# ---------------------------------------------------------------------------
# Legacy compatibility
# ---------------------------------------------------------------------------


def test_runtime_release_stays_private_in_catalog_entry(tmp_path):
    s3, manifest_bytes, document = serve_release()
    entry = make_entry(document, manifest_bytes)
    safe = entry.to_safe_dict()
    assert "runtime_release" not in safe
    assert "manifest_key" not in json.dumps(safe)
    assert entry.get_runtime_release()["manifest_sha256"] == _sha(manifest_bytes)


# ---------------------------------------------------------------------------
# Cross-platform golden probability tolerance (PR0174)
# ---------------------------------------------------------------------------


class TestGoldenProbabilityTolerance:
    """Only continuous probability fields may use the narrow absolute
    tolerance; every discrete/contract field stays exact."""

    def _install_with(self, tmp_path, runner_result=None, runner_error=None, **expected):
        s3, manifest_bytes, document = _manifest_with_cases([_case(**expected)])
        runner = FakeRunner(
            golden_result=runner_result, golden_error=runner_error,
        )
        cache = make_cache(tmp_path, s3, runner)
        return cache, document, manifest_bytes

    def test_exact_probability_still_passes(self, tmp_path):
        cache, document, manifest_bytes = self._install_with(
            tmp_path,
            runner_result={
                "probability": GOLDEN_EXPECTED["probability"],
                "threshold_applied": GOLDEN_EXPECTED["threshold_applied"],
                "prediction": 1,
            },
        )
        installed = cache.install(make_entry(document, manifest_bytes))
        assert cache.read_ready(installed.manifest_sha256) is not None

    def test_observed_darwin_linux_probability_pair_passes(self, tmp_path):
        """The real B2 pair: Darwin 0.7726940329943811 vs Linux 0.7726940329943845."""
        cache, document, manifest_bytes = self._install_with(
            tmp_path,
            runner_result={
                "probability": 0.7726940329943845,
                "threshold_applied": 0.3585907282566089,
                "prediction": 1,
            },
            probability=0.7726940329943811,
            threshold_applied=0.3585907282566089,
            prediction=1,
        )
        installed = cache.install(make_entry(document, manifest_bytes))
        assert cache.read_ready(installed.manifest_sha256) is not None

    def test_difference_within_tolerance_passes(self, tmp_path):
        expected = 0.7726940329943811
        cache, document, manifest_bytes = self._install_with(
            tmp_path,
            runner_result={
                "probability": expected + 5e-13,
                "threshold_applied": GOLDEN_EXPECTED["threshold_applied"],
                "prediction": 1,
            },
            probability=expected,
        )
        assert cache.read_ready(
            cache.install(make_entry(document, manifest_bytes)).manifest_sha256
        ) is not None

    def test_difference_above_tolerance_fails(self, tmp_path):
        expected = 0.7726940329943811
        cache, document, manifest_bytes = self._install_with(
            tmp_path,
            runner_result={
                "probability": expected + 2e-12,
                "threshold_applied": GOLDEN_EXPECTED["threshold_applied"],
                "prediction": 1,
            },
            probability=expected,
        )
        with pytest.raises(ReleaseCacheError, match="smoke_failed"):
            cache.install(make_entry(document, manifest_bytes))

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_probability_fails(self, tmp_path, bad):
        cache, document, manifest_bytes = self._install_with(
            tmp_path,
            runner_result={
                "probability": bad,
                "threshold_applied": GOLDEN_EXPECTED["threshold_applied"],
                "prediction": 1,
            },
        )
        with pytest.raises(ReleaseCacheError, match="smoke_failed"):
            cache.install(make_entry(document, manifest_bytes))

    @pytest.mark.parametrize("bad", ["0.77", None, True, [0.77]])
    def test_non_numeric_probability_fails(self, tmp_path, bad):
        cache, document, manifest_bytes = self._install_with(
            tmp_path,
            runner_result={
                "probability": bad,
                "threshold_applied": GOLDEN_EXPECTED["threshold_applied"],
                "prediction": 1,
            },
        )
        with pytest.raises(ReleaseCacheError, match="smoke_failed"):
            cache.install(make_entry(document, manifest_bytes))

    def test_tiny_threshold_drift_still_fails(self, tmp_path):
        cache, document, manifest_bytes = self._install_with(
            tmp_path,
            runner_result={
                "probability": GOLDEN_EXPECTED["probability"],
                "threshold_applied": GOLDEN_EXPECTED["threshold_applied"] + 1e-15,
                "prediction": 1,
            },
        )
        with pytest.raises(ReleaseCacheError, match="smoke_failed"):
            cache.install(make_entry(document, manifest_bytes))

    def test_prediction_mismatch_still_fails(self, tmp_path):
        cache, document, manifest_bytes = self._install_with(
            tmp_path,
            runner_result={
                "probability": GOLDEN_EXPECTED["probability"],
                "threshold_applied": GOLDEN_EXPECTED["threshold_applied"],
                "prediction": 0,
            },
        )
        with pytest.raises(ReleaseCacheError, match="smoke_failed"):
            cache.install(make_entry(document, manifest_bytes))

    def test_target_class_mismatch_still_fails(self, tmp_path):
        expected = {
            "status": "ok",
            "risk_probability": 0.8693870739736473,
            "decision_threshold": 0.24665932038818544,
            "target_class_risk_level": 1,
        }
        s3, manifest_bytes, document = _manifest_with_cases([_case(**expected)])
        runner = FakeRunner(
            golden_result={
                "risk_probability": 0.869387073973647,
                "decision_threshold": 0.24665932038818544,
                "target_class_risk_level": 0,
            }
        )
        cache = make_cache(tmp_path, s3, runner)
        with pytest.raises(ReleaseCacheError, match="smoke_failed"):
            cache.install(make_entry(document, manifest_bytes))

    def test_error_code_mismatch_still_fails(self, tmp_path):
        expected = {
            "status": "error",
            "error_code": "QC_FAILED",
            "safe_reason": "raw_peak_gate_failed",
        }
        s3, manifest_bytes, document = _manifest_with_cases([_case(**expected)])
        runner = FakeRunner(
            golden_error={"code": "INPUT_INVALID", "safe_reason": "raw_peak_gate_failed"}
        )
        cache = make_cache(tmp_path, s3, runner)
        with pytest.raises(ReleaseCacheError, match="smoke_failed"):
            cache.install(make_entry(document, manifest_bytes))

    def test_safe_reason_mismatch_still_fails(self, tmp_path):
        expected = {
            "status": "error",
            "error_code": "QC_FAILED",
            "safe_reason": "raw_peak_gate_failed",
        }
        s3, manifest_bytes, document = _manifest_with_cases([_case(**expected)])
        runner = FakeRunner(
            golden_error={"code": "QC_FAILED", "safe_reason": "other_reason"}
        )
        cache = make_cache(tmp_path, s3, runner)
        with pytest.raises(ReleaseCacheError, match="smoke_failed"):
            cache.install(make_entry(document, manifest_bytes))

    def test_linux_risk_probability_drift_passes(self, tmp_path):
        """A1 Linux risk_probability differs in the last digits only."""
        expected = {
            "status": "ok",
            "risk_probability": 0.8693870739736473,
            "decision_threshold": 0.24665932038818544,
            "target_class_risk_level": 1,
        }
        case = {
            "case_id": "a1-linux-drift",
            "fixture": "benign_one_patient.h5",
            "fixture_release_path": "golden_tests/fixtures/benign_one_patient.h5",
            "expected": expected,
        }
        s3, manifest_bytes, document = _manifest_with_cases([case])
        runner = FakeRunner(
            golden_result={
                "risk_probability": 0.869387073973647,
                "decision_threshold": 0.24665932038818544,
                "target_class_risk_level": 1,
            }
        )
        cache = make_cache(tmp_path, s3, runner)
        installed = cache.install(make_entry(document, manifest_bytes))
        assert cache.read_ready(installed.manifest_sha256) is not None


def test_golden_tolerance_is_narrow_and_documented():
    from bremen.platform.models.release_cache import (
        GOLDEN_PROBABILITY_ABS_TOLERANCE,
    )

    assert GOLDEN_PROBABILITY_ABS_TOLERANCE == 1e-12
