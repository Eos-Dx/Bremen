"""IR-03 five-model frozen-baseline parity (real artifacts, opt-in).

This test requires the operator-supplied IR-01 local evidence:

- ``/tmp/ir03/releases-final`` (or ``$BREMEN_IR03_RELEASES``) with one
  assembled release directory per variant (``a1``, ``a2``, ``b1``, ``b2``,
  ``b3``)
- ``/tmp/bremen-ir01-fixtures/v0.1`` (or ``$BREMEN_IR03_FIXTURES``)

It is skipped when those inputs are absent.  The clean-environment run of the
same cases is recorded in ``PARITY_EVIDENCE.md``; this test guards the parity
while developing in the repository environment.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from bremen.contracts.inference_release import validate_release_manifest

ROOT = Path(__file__).resolve().parents[1]
RELEASES = Path(os.environ.get("BREMEN_IR03_RELEASES", "/tmp/ir03/releases-final"))
FIXTURES = Path(
    os.environ.get("BREMEN_IR03_FIXTURES", "/tmp/bremen-ir01-fixtures/v0.1")
)
AUX_ENV_ROOT = os.environ.get(
    "BREMEN_IR03_AUX_ENV_ROOT", "/tmp/ir03/aux-env-root"
)
VARIANTS = ("a1", "a2", "b1", "b2", "b3")

pytestmark = pytest.mark.skipif(
    not all((RELEASES / key / "manifest.json").is_file() for key in VARIANTS)
    or not FIXTURES.is_dir(),
    reason="IR-03 local releases/fixtures are not available",
)

_AVAILABLE = all(
    (RELEASES / key / "manifest.json").is_file() for key in VARIANTS
) and FIXTURES.is_dir()


def _cases() -> list[tuple[str, dict]]:
    collected: list[tuple[str, dict]] = []
    for key in VARIANTS:
        path = RELEASES / key / "golden_tests" / "cases.json"
        data = json.loads(path.read_text())
        for case in data["cases"]:
            collected.append((key, case))
    return collected


def _run_case(tmp_path: Path, key: str, case: dict) -> dict:
    release = RELEASES / key
    manifest_bytes = (release / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    digest = hashlib.sha256(manifest_bytes).hexdigest()
    job = tmp_path / f"{key}-{case['case_id']}"
    job.mkdir()
    shutil.copyfile(FIXTURES / case["fixture"], job / "input.h5")

    payload = {
        "workflow_id": manifest["model"]["workflow_id"],
        "container_path": "input.h5",
        "parameters": {},
    }
    for field in ("patient_id", "target_side"):
        if case.get(field):
            payload[field] = case[field]
    request = {
        "protocol": "bremen.worker.v1",
        "request_id": f"req-{case['case_id']}",
        "operation": "predict",
        "model_id": manifest["model"]["model_id"],
        "release_digest": digest,
        "payload": payload,
    }
    (job / "request.json").write_text(json.dumps(request), encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    env.setdefault("BREMEN_IR03_AUX_ENV_ROOT", AUX_ENV_ROOT)
    completed = subprocess.run(
        [
            sys.executable, "-m", "bremen.ml_plugin.entrypoint",
            "--release-dir", str(release), "--job-dir", str(job),
        ],
        text=True, capture_output=True, check=False, env=env,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads((job / "result.json").read_text())


@pytest.mark.parametrize(
    "key,case",
    _cases() if _AVAILABLE else [],
    ids=[
        f"{key}-{case['case_id']}" for key, case in (_cases() if _AVAILABLE else [])
    ],
)
def test_frozen_baseline_case(tmp_path, key, case):
    result = _run_case(tmp_path, key, case)
    expected = case["expected"]
    assert result["status"] == expected["status"]
    if expected["status"] == "error":
        assert result["error"]["code"] == expected["error_code"]
        assert result["error"]["safe_reason"] == expected["safe_reason"]
        return

    payload = result["payload"]["result"]
    if key in {"a1", "a2"}:
        assert math.isclose(
            payload["risk_probability"], expected["risk_probability"],
            rel_tol=0, abs_tol=0,
        )
        assert math.isclose(
            payload["decision_threshold"], expected["decision_threshold"],
            rel_tol=0, abs_tol=0,
        )
        assert payload["target_class_risk_level"] == expected["target_class_risk_level"]
    else:
        assert math.isclose(
            payload["probability"], expected["probability"], rel_tol=0, abs_tol=0,
        )
        assert math.isclose(
            payload["threshold_applied"], expected["threshold_applied"],
            rel_tol=0, abs_tol=0,
        )
        assert payload["prediction"] == expected["prediction"]


@pytest.mark.parametrize("key", VARIANTS)
def test_release_manifest_is_valid(key):
    manifest = json.loads((RELEASES / key / "manifest.json").read_text())
    validated = validate_release_manifest(manifest)
    assert validated.release_id == manifest["release_id"]
    for ref in validated.files:
        path = RELEASES / key / ref.relative_path
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == ref.sha256


@pytest.mark.parametrize("key", VARIANTS)
def test_release_artifact_checksum_matches_release(tmp_path, key):
    release = RELEASES / key
    manifest = json.loads((release / "manifest.json").read_text())
    artifact_ref = next(
        ref for ref in manifest["files"] if ref["role"] == "model_artifact"
    )
    artifact = release / artifact_ref["relative_path"]
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == (
        manifest["scientific_metadata"]["artifact_checksum"]
    )
