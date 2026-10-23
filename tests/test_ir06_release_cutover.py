"""IR-06 release-runtime cutover boundaries."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "model_id",
    [
        "aramina_target_breast_risk_0_2_12-beta_9bb911189af6",
        "aramina_target_breast_risk_0_2_13-beta_f5e4a04cad11",
        "bremen-mri-triage-logreg-v0-1",
        "bremen-paper-reference-v0-2-0",
        "bremen-v0-2-0-symmetry-candidate",
    ],
)
def test_all_five_release_entries_route_without_candidate_allowlist(monkeypatch, model_id):
    monkeypatch.delenv("BREMEN_CANDIDATE_SUBPROCESS_MODELS", raising=False)
    monkeypatch.setenv("BREMEN_MODEL_CATALOG_URI", "s3://bucket/catalog/")
    from bremen.platform.runtime.registry import _candidate_runtime_for

    entry = type(
        "Entry",
        (),
        {"model_id": model_id, "get_runtime_release": lambda self: {"release_id": model_id}},
    )()
    assert _candidate_runtime_for(entry).__class__.__name__ == "SubprocessRuntime"


def test_discovery_import_has_no_scientific_import_boundary():
    code = """
import sys
import bremen.platform.models.discovery
assert 'bremen.model_packages.bremen_v01' not in sys.modules
assert 'bremen.model_packages.aramina_v0213' not in sys.modules
assert 'bremen.ml_plugin' not in sys.modules
"""
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
    completed = subprocess.run([sys.executable, "-c", code], check=False, capture_output=True, text=True, env=env)
    assert completed.returncode == 0, completed.stderr


def test_supplied_release_runtime_does_not_import_legacy_runtime_classes():
    code = """
import sys
from bremen.platform.runtime.registry import bremen_descriptor, aramina_descriptor

class Runtime:
    requires_raw_container = True
    def model_ready(self): return True

class Entry:
    model_id = 'release-model'
    model_version = 'v1'
    _clinical_stage = 'research draft'
    def get_runtime_release(self): return {'schema_version': 'bremen.inference-release.v1'}

bremen_descriptor(runtime=Runtime(), model_id='release-model')
aramina_descriptor(entry=Entry(), runtime=Runtime())
assert 'bremen.model_packages.bremen_v01' not in sys.modules
assert 'bremen.model_packages.aramina_v0213' not in sys.modules
"""
    env = dict(__import__("os").environ)
    env["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
    completed = subprocess.run([sys.executable, "-c", code], check=False, capture_output=True, text=True, env=env)
    assert completed.returncode == 0, completed.stderr
