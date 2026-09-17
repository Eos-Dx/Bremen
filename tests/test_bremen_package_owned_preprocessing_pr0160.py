"""Portable ownership regressions and opt-in private raw-H5 evidence checks.

Private inputs are never committed. Set BREMEN_EVIDENCE_ARTIFACT,
BREMEN_EVIDENCE_NOVA378, BREMEN_EVIDENCE_NOVA227 and BREMEN_PREPROCESS_PYTHON
for the real evidence checks. Synthetic fixtures test wiring, not H5 parity.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace

import h5py
import joblib
import numpy as np
import pandas as pd
import pytest

from bremen.model_packages.bremen_v01 import preprocessing as prep
from bremen.model_packages.bremen_v01.bremen_preprocess_worker import _legacy_container_compat_path
from bremen.model_packages.bremen_v01.features import (
    AnalysisConfig, BremenFeatureError, build_bremen_features_from_frame,
    local_peak_in_window, parse_q_grid, patient_mean_raw_peak14,
)
from bremen.model_packages.bremen_v01.manifest import ARTIFACT_SHA256
from bremen.model_packages.bremen_v01.runtime import BremenRuntime
from bremen.model_runtime import ModelInput, ModelInputInvalidError, ModelPreprocessingFailedError
from tests.bremen_3x3_helpers import GOLD, MODEL, make_case

CONFIG = "xrd_preprocessing: {release_tag: v0.1.7-beta}\npipeline: {steps: [artifact-owned]}\n"


def _frame():
    return pd.DataFrame([
        dict(patientId="case", side=m.side, position=m.position,
             q_range=m.q, radial_profile_data=m.intensity)
        for m in make_case().measurements
    ])


def _runtime():
    return BremenRuntime({**MODEL, "prediction_preprocessing_yaml": CONFIG})


def test_orchestrator_passes_raw_source_without_platform_science(tmp_path, monkeypatch):
    from bremen.api import workflow_orchestrator as orchestrator
    from bremen.api.workflow_bremen import BremenProvider
    from bremen.api.workflow_registry import WorkflowRegistry
    path = tmp_path / "opaque.h5"
    path.write_bytes(b"source parsing belongs to the package")
    calls = []

    def preprocess(raw, config):
        calls.append((raw, config))
        return _frame()

    def forbidden(*args, **kwargs):
        pytest.fail("platform scientific normalization executed")

    monkeypatch.setattr(prep, "preprocess_bremen", preprocess)
    monkeypatch.setattr(orchestrator, "_normalize_h5", forbidden)
    monkeypatch.setattr(orchestrator, "detect_layout", forbidden)
    registry = WorkflowRegistry()
    registry.register(BremenProvider(runtime=_runtime()))
    result = orchestrator.run_workflow_request(str(path), registry=registry)
    assert result.overall_status == "completed"
    assert result.source_checksum == hashlib.sha256(path.read_bytes()).hexdigest()
    assert calls == [(str(path), CONFIG)]
    assert result.workflows['bremen'].payload['left_measurement_count'] == 3
    assert result.workflows['bremen'].payload['right_measurement_count'] == 3
    assert math.isclose(result.workflows['bremen'].payload['probability'],
                        GOLD['expected_probability'], rel_tol=0, abs_tol=1e-10)


def test_raw_artifact_cannot_fall_back_to_integrated_profiles():
    with pytest.raises(ModelInputInvalidError, match="raw_container_required"):
        _runtime().predict_model(ModelInput(workflow_id="bremen", measurements=make_case().measurements))


def test_preprocessing_failure_has_safe_runtime_category(monkeypatch):
    def fail(*args):
        raise prep.BremenPreprocessingError("private detail")
    monkeypatch.setattr(prep, 'preprocess_bremen', fail)
    with pytest.raises(ModelPreprocessingFailedError, match="invalid_scientific_profiles"):
        _runtime().predict_model(ModelInput(workflow_id="bremen", container_path="raw.h5"))


@pytest.mark.parametrize('change', ['count', 'patient', 'side'])
def test_frame_rejects_mixed_patient_or_invalid_shape(change):
    frame = _frame()
    if change == 'count':
        frame = frame.iloc[:-1]
    elif change == 'patient':
        frame.loc[0, 'patientId'] = 'another'
    else:
        frame.loc[0, 'side'] = 'random'
    with pytest.raises(BremenFeatureError):
        build_bremen_features_from_frame(frame)


@pytest.mark.parametrize('config', ['', '[', '[]', 'pipeline: {}',
    'pipeline: {steps: [x]}\nxrd_preprocessing: {release_tag: v0.1.9-beta}',
    'pipeline: {steps: [x]}\nxrd_preprocessing: {release_tag: []}'])
def test_invalid_or_unsupported_config_never_launches_worker(config, monkeypatch):
    monkeypatch.setattr(prep.subprocess, 'run', lambda *a, **k: pytest.fail('worker launched'))
    with pytest.raises(prep.BremenPreprocessingError):
        prep.preprocess_bremen('raw.h5', config)
    assert prep.preprocessing_release_tag(config) == ''


@pytest.mark.parametrize('override,expected', [
    (None, '/opt/bremen-preprocess/bin/python'),
    ('/configured/python', '/configured/python'),
])
def test_worker_receives_exact_artifact_yaml_and_pinned_interpreter(monkeypatch, override, expected):
    def run(command, **kwargs):
        assert command[0:2] == [expected, '-I']
        assert json.loads(kwargs['input']) == {'h5': 'raw.h5', 'config_yaml': CONFIG}
        return SimpleNamespace(returncode=0, stdout='{"rows": [{"side": "Left"}]}')
    monkeypatch.delenv('BREMEN_PREPROCESS_PYTHON', raising=False)
    if override is not None:
        monkeypatch.setenv('BREMEN_PREPROCESS_PYTHON', override)
    monkeypatch.setattr(prep.subprocess, 'run', run)
    assert prep.preprocess_bremen('raw.h5', CONFIG).side.tolist() == ['Left']
    assert prep.preprocessing_release_tag(CONFIG) == 'v0.1.7-beta'


@pytest.mark.parametrize('output,code', [('[]',0), ('null',0), ('{}',0),
    ('bad json',0), ('{"rows": []}',0), ('private worker text',1)])
def test_worker_bad_output_is_safely_rejected(output, code, monkeypatch):
    monkeypatch.setattr(prep.subprocess, 'run', lambda *a, **k: SimpleNamespace(
        returncode=code, stdout=output))
    with pytest.raises(prep.BremenPreprocessingError) as error:
        prep.preprocess_bremen('private.h5', CONFIG)
    assert 'private' not in str(error.value)


def test_legacy_adapter_preserves_original_and_rejects_conflicting_identity(tmp_path):
    src = tmp_path / 'legacy.h5'
    with h5py.File(src, 'w') as f:
        f.create_group('session')
    before = src.read_bytes()
    compat = Path(_legacy_container_compat_path(str(src)))
    try:
        with h5py.File(compat) as f:
            assert f.attrs['format'] == 'xrd-session'
            assert f.attrs['schema_version'] == '0.3'
        assert _legacy_container_compat_path(str(compat)) == str(compat)
    finally:
        compat.unlink()
    assert src.read_bytes() == before
    with h5py.File(src, 'a') as f:
        f.attrs['schema_version'] = 'unsupported'
    with pytest.raises(ValueError):
        _legacy_container_compat_path(str(src))


def test_packages_do_not_import_platform_api():
    for root in ('aramina_v0213',):
        for path in Path('src/bremen/model_packages', root).glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                names = ([node.module or ''] if isinstance(node, ast.ImportFrom)
                         else [a.name for a in node.names] if isinstance(node, ast.Import) else [])
                assert not any(n.startswith('bremen.api') for n in names), path


def _evidence(name):
    artifact = os.environ.get('BREMEN_EVIDENCE_ARTIFACT')
    source = os.environ.get('BREMEN_EVIDENCE_' + name)
    if not artifact or not source or not os.environ.get('BREMEN_PREPROCESS_PYTHON'):
        pytest.skip('private raw-H5 evidence and pinned interpreter not configured')
    assert hashlib.sha256(Path(artifact).read_bytes()).hexdigest() == ARTIFACT_SHA256
    return joblib.load(artifact), source


def test_nova378_authoritative_raw_preprocessing_and_gate():
    artifact, source = _evidence('NOVA378')
    frame = prep.preprocess_bremen(source, artifact['prediction_preprocessing_yaml'])
    expected = {
        ('Right','P1'): 0.3635513484477997, ('Right','P2'): 0.355907678604126,
        ('Right','P3'): 0.49898195266723633, ('Left','P1'): 0.42200028896331787,
        ('Left','P2'): 0.459202378988266, ('Left','P3'): 0.6773958802223206,
    }
    assert len(frame) == 6
    for row in frame.itertuples():
        q = parse_q_grid(np.asarray(row.q_range), len(row.radial_profile_data))
        peak = local_peak_in_window(q, np.asarray(row.radial_profile_data))
        assert peak == pytest.approx(expected[(row.side,row.position)], rel=0, abs=1e-10)
    mean = patient_mean_raw_peak14(frame.assign(patient_id='case'), 'case', AnalysisConfig())
    assert mean == pytest.approx(0.46283992131551105, rel=0, abs=1e-10)
    assert AnalysisConfig().raw_peak_threshold == 0.6
    with pytest.raises(BremenFeatureError, match='raw_peak_gate_failed'):
        build_bremen_features_from_frame(frame)
    with pytest.raises(ModelPreprocessingFailedError, match='raw_peak_gate_failed'):
        BremenRuntime(artifact).predict_model(ModelInput(workflow_id='bremen', container_path=source))


def test_nova227_raw_preprocessing_matches_frozen_training_record():
    artifact, source = _evidence('NOVA227')
    result = BremenRuntime(artifact).predict_model(ModelInput(workflow_id='bremen', container_path=source))
    # Independently reproduced authoritative package-owned baseline (W2).
    # Old platform-owned path: 0.9804625872094516; see IMPLEMENTATION_REPORT.md.
    assert math.isclose(result.result['probability'], 0.7726940329943811,
                        rel_tol=0, abs_tol=1e-10)
    assert result.result['threshold_applied'] == 0.3585907282566089


@pytest.mark.parametrize('commit,version,release,valid', [
    ('45d5568248e9774b7938a36e028d80e72b130b19','0.1.7b0','v0.1.7-beta',True),
    ('different','0.1.7b0','v0.1.7-beta',False),
    ('45d5568248e9774b7938a36e028d80e72b130b19','0.1.9b0','v0.1.7-beta',False),
    ('45d5568248e9774b7938a36e028d80e72b130b19','0.1.7b0','v0.1.9-beta',False),
])
def test_dependency_commit_and_release_are_enforced(monkeypatch, commit, version, release, valid):
    from bremen.model_packages.bremen_v01.bremen_preprocess_worker import _validate_dependency
    monkeypatch.setattr('importlib.metadata.distribution', lambda name: SimpleNamespace(
        version=version, read_text=lambda name: json.dumps({'vcs_info': {'commit_id': commit}})))
    if valid:
        _validate_dependency(release)
    else:
        with pytest.raises(ValueError):
            _validate_dependency(release)


@pytest.mark.parametrize('binding', ['match', 'checksum', 'patient', 'missing_checksum'])
def test_aramina_platform_binding_precedes_package(tmp_path, monkeypatch, binding):
    from bremen.api.workflow_aramina import AraminaWorkflowProvider
    from bremen.model_runtime import RuntimePrediction
    path = tmp_path / 'source.h5'
    path.write_bytes(b'staged source')
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    # Identity extraction is an existing platform concern, tested independently
    # by the Aramina workflow suite; here isolate its ordering and integrity gate.
    monkeypatch.setattr('bremen.api.workflow_orchestrator.h5py.File',
                        lambda *a, **k: _Context())
    monkeypatch.setattr('bremen.api.preflight.resolve_patient_metadata',
                        lambda f: SimpleNamespace(patient_identifier='p1'))
    provider = AraminaWorkflowProvider(entry=SimpleNamespace(
        model_id='aramina', model_version='test', _clinical_stage='research draft'))
    calls = []
    def predict(model_input):
        calls.append(model_input)
        return RuntimePrediction(workflow_id='aramina', result={}, model_version='test')
    monkeypatch.setattr(provider._runtime, 'predict_model', predict)
    result = provider.execute(
        SimpleNamespace(measurements=(), source_checksum=(
            'wrong' if binding == 'checksum' else '' if binding == 'missing_checksum' else checksum)),
        h5_path=str(path), aramina_request=SimpleNamespace(
            patient_id='other' if binding == 'patient' else 'p1', target_side='left',
            analysis_author='', prediction_comment='', container_id='c', source_id='s'),
    )
    assert bool(calls) == (binding == 'match')
    if binding == 'match':
        assert result.status == 'completed'
    else:
        assert result.error == 'ARAMINA_UNSUPPORTED_INPUT'
        assert result.failure_stage == 'h5_patient_contract'


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass
