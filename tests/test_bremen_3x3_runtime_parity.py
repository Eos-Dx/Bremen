"""Production parity with the independently frozen PR0151 reference."""
from copy import deepcopy
from dataclasses import replace
from itertools import permutations
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from bremen.api.workflow_bremen import BremenProvider
from bremen.api.workflow_orchestrator import run_workflow_request, _normalize_h5
from bremen.api.workflow_registry import WorkflowRegistry
from bremen.bremen_features import build_bremen_features, BremenFeatureError
from bremen.inference import adapt_model_package, predict_proba_portable
from tests.bremen_3x3_helpers import GOLD, MODEL, DETAIL, make_case, write_session_h5
from tests.reference_0151.features import build_feature_frame
from tests.reference_0151.prediction import predict_proba_portable as reference_score


def assert_close(actual, expected):
    np.testing.assert_allclose(actual, expected, atol=1e-10, rtol=0)


def reference_vector(measurements):
    frame = pd.DataFrame([
        dict(patientId='synthetic', side=m.side, q_range=m.q, radial_profile_data=m.intensity)
        for m in measurements
    ])
    features, errors = build_feature_frame(frame)
    assert errors.empty
    return features[GOLD['feature_names']].iloc[0].to_numpy()


def test_production_golden_features_and_probability():
    provider = BremenProvider(model_package=MODEL)
    features = provider.build_features(make_case())
    assert list(features.feature_names) == GOLD['feature_names']
    assert_close(features.feature_values, GOLD['expected_features'])
    result = provider.execute(make_case())
    assert result.status == 'completed'
    assert_close(result.payload['probability'], GOLD['expected_probability'])
    assert result.payload['threshold_applied'] == MODEL['portable_logreg']['threshold']
    assert result.payload['prediction'] == 1
    assert result.payload['left_measurement_count'] == 3
    assert result.payload['right_measurement_count'] == 3


@pytest.mark.parametrize('side_offset', [0, 3])
@pytest.mark.parametrize('order', list(permutations(range(3))))
def test_production_permutations(side_offset, order):
    case = make_case()
    ms = list(case.measurements)
    ms[side_offset:side_offset+3] = [case.measurements[side_offset+i] for i in order]
    provider = BremenProvider(model_package=MODEL)
    case = replace(case, measurements=tuple(ms))
    assert_close(provider.build_features(case).feature_values, GOLD['expected_features'])
    assert_close(provider.execute(case).payload['probability'], GOLD['expected_probability'])


@pytest.mark.parametrize('index', range(6))
def test_production_all_six_participate(index):
    ms = list(make_case().measurements)
    m = ms[index]
    ms[index] = replace(m, intensity=m.intensity+0.12*np.exp(-((m.q-14.1)/0.8)**2))
    actual = build_bremen_features(ms)
    assert_close(list(actual.values()), DETAIL['mutations'][index]['expected_features'])
    changed = [n for n, a, b in zip(actual, actual.values(), GOLD['expected_features'])
               if abs(a-b) > 1e-10]
    assert changed == DETAIL['mutations'][index]['changed_features']
    assert changed


@pytest.mark.parametrize('identical_sides', [('LEFT',), ('RIGHT',), ('LEFT', 'RIGHT')])
def test_identical_replicates_preserve_authoritative_variance(identical_sides):
    ms = list(make_case().measurements)
    for side in identical_sides:
        base = next(m for m in ms if m.side == side)
        ms = [replace(m, q=base.q.copy(), intensity=base.intensity.copy())
              if m.side == side else m for m in ms]
    actual = build_bremen_features(ms)
    assert_close(list(actual.values()), reference_vector(ms))
    for side in identical_sides:
        for band in [1, 2]:
            assert_close(actual[f'sigma_{side[0].lower()}{band}'], 0)
    expected_p = reference_score(MODEL['portable_logreg'],
                                pd.DataFrame([reference_vector(ms)]))[0]
    assert_close(predict_proba_portable(MODEL, list(actual.values()))['probability'], expected_p)


@pytest.mark.parametrize('left,right', [(3, 2), (2, 3), (4, 2), (2, 4), (1, 1), (0, 6),
                                       (6, 0), (3, 4), (0, 0)])
def test_invalid_shape_rejected_before_science_or_scoring(left, right, monkeypatch):
    case = make_case()
    ms = (case.measurements[0],)*left+(case.measurements[3],)*right
    provider = BremenProvider(model_package=MODEL)
    science = Mock(side_effect=AssertionError('must not reach science'))
    scorer = Mock(side_effect=AssertionError('must not reach scorer'))
    monkeypatch.setattr('bremen.bremen_runtime.build_bremen_features', science)
    monkeypatch.setattr(provider._runtime, 'score', scorer)
    result = provider.execute(replace(case, measurements=ms))
    assert result.status == 'failed'
    assert result.error == 'Incompatible: requires_exactly_3_left_3_right'
    science.assert_not_called()
    scorer.assert_not_called()
    with pytest.raises(BremenFeatureError, match='^requires_exactly_3_left_3_right$'):
        build_bremen_features(ms)


def test_scientific_failure_is_safe(monkeypatch):
    monkeypatch.setattr('bremen.bremen_runtime.build_bremen_features',
                        Mock(side_effect=ValueError('/private/source secret token traceback')))
    result = BremenProvider(model_package=MODEL).execute(make_case())
    assert result.status == 'failed'
    assert result.error == 'Feature construction failed: invalid_scientific_profiles'


def test_raw_peak_gate_is_preserved():
    ms = tuple(replace(m, intensity=m.intensity*0.01) for m in make_case().measurements)
    with pytest.raises(BremenFeatureError, match='raw_peak_gate_failed'):
        build_bremen_features(ms)


def test_synthetic_h5_production_job_path(tmp_path):
    path = write_session_h5(tmp_path/'synthetic-3x3.h5')
    before = path.read_bytes()
    case = _normalize_h5(str(path), workflow_id='bremen')
    assert len(case.measurements) == 6
    for side in ['LEFT', 'RIGHT']:
        actual = [m for m in case.measurements if m.side == side]
        expected = [m for m in make_case().measurements if m.side == side]
        for a, b in zip(actual, expected):
            np.testing.assert_array_equal(a.q, b.q)
            np.testing.assert_array_equal(a.intensity, b.intensity)
    provider = BremenProvider(model_package=MODEL)
    assert_close(provider.build_features(case).feature_values, GOLD['expected_features'])
    registry = WorkflowRegistry()
    registry.register(provider)
    result = run_workflow_request(str(path), workflow_id='bremen', registry=registry)
    assert result.normalization_status == 'completed'
    assert result.workflows['bremen'].status == 'completed'
    assert_close(result.workflows['bremen'].payload['probability'], GOLD['expected_probability'])
    assert path.read_bytes() == before


@pytest.mark.parametrize('left,right', [(3, 2), (2, 3), (4, 2), (2, 4), (1, 1), (0, 6), (6, 0)])
def test_h5_invalid_shape(tmp_path, left, right):
    ms = make_case().measurements
    path = write_session_h5(tmp_path/'invalid.h5', (ms[0],)*left+(ms[3],)*right)
    registry = WorkflowRegistry()
    provider = BremenProvider(model_package=MODEL)
    provider._runtime.score = Mock(side_effect=AssertionError('must not score'))
    registry.register(provider)
    result = run_workflow_request(str(path), registry=registry)
    if left == 0 or right == 0:
        # Pair-less session H5 fails the existing layout detector even earlier.
        assert result.overall_status == 'normalization_failed'
        assert result.workflows == {}
    else:
        assert result.workflows['bremen'].error == 'Incompatible: requires_exactly_3_left_3_right'
    provider._runtime.score.assert_not_called()


def test_paper_artifact_metadata_adaptation_does_not_mutate():
    plr = deepcopy(MODEL['portable_logreg'])
    columns, threshold = plr.pop('feature_columns'), plr.pop('threshold')
    artifact = dict(portable_logreg=plr, feature_schema={'feature_columns': columns},
                    decision={'threshold': threshold})
    before = deepcopy(artifact)
    adapted = adapt_model_package(artifact)
    assert adapted['portable_logreg'] == MODEL['portable_logreg']
    assert artifact == before


@pytest.mark.parametrize('classes', [[0, 1], [1, 0]])
def test_portable_imputation_zero_scale_and_class_order(classes):
    model = deepcopy(MODEL)
    plr = model['portable_logreg']
    plr['classes'] = classes
    plr['scaler_scale'][0] = 0
    plr['scaler_scale'][1] = 1e-12
    values = np.array(GOLD['expected_features'])
    values[2:5] = [np.nan, np.inf, -np.inf]
    expected = reference_score(plr, pd.DataFrame([values]))[0]
    actual = predict_proba_portable(model, values.tolist())
    assert_close(actual['probability'], expected)
    assert actual['prediction'] == int(expected >= plr['threshold'])


def test_runtime_owns_complete_sequence_and_structured_result():
    from bremen.bremen_runtime import BremenRuntime
    callback = Mock()
    result = BremenRuntime(MODEL).run(make_case().measurements, on_features=callback)
    assert_close(result.features.feature_values, GOLD['expected_features'])
    assert_close(result.probability, GOLD['expected_probability'])
    assert result.threshold == MODEL['portable_logreg']['threshold']
    assert result.decision.is_positive
    callback.assert_called_once_with(result.features)


def test_provider_executes_through_model_runtime_contract_v1(monkeypatch):
    # PR0153B wiring: provider.execute must route the frozen scientific
    # sequence through exactly one contract predict call; the runtime still
    # composes the exact PR0152 run() internally.
    from bremen.model_runtime import ModelRuntime, ModelInput, RuntimePrediction
    provider = BremenProvider(model_package=MODEL)
    runtime = provider.model_runtime()
    assert isinstance(runtime, ModelRuntime)
    predict = Mock(wraps=runtime.predict_model)
    run = Mock(wraps=runtime.run)
    monkeypatch.setattr(runtime, 'predict_model', predict)
    monkeypatch.setattr(runtime, 'run', run)
    result = provider.execute(make_case())
    assert result.status == 'completed'
    assert_close(result.payload['probability'], GOLD['expected_probability'])
    predict.assert_called_once()
    run.assert_called_once()
    passed_input = predict.call_args.args[0]
    assert isinstance(passed_input, ModelInput)
    assert len(passed_input.measurements) == 6
    fresh = runtime.predict_model(ModelInput(workflow_id='bremen',
                                             measurements=make_case().measurements))
    assert isinstance(fresh, RuntimePrediction)
    assert_close(fresh.result['probability'], GOLD['expected_probability'])


def test_runtime_rejects_reordered_features_and_invalid_classes():
    from bremen.bremen_runtime import BremenRuntime, BremenRuntimeError
    runtime = BremenRuntime(MODEL)
    with pytest.raises(BremenRuntimeError, match='invalid_feature_schema'):
        runtime.score(list(reversed(GOLD['feature_names'])), GOLD['expected_features'])
    invalid = deepcopy(MODEL)
    invalid['portable_logreg']['classes'] = [4, 9]
    with pytest.raises(BremenRuntimeError, match='model_execution_failed'):
        BremenRuntime(invalid).run(make_case().measurements)


def test_calibration_h5_retains_all_native_profiles(tmp_path):
    import h5py
    path = tmp_path/'synthetic-calibration.h5'
    with h5py.File(path, 'w') as f:
        for side, sample_id in [('LEFT', 'sample_1'), ('RIGHT', 'sample_2')]:
            sample = f.create_group(f'calib_synthetic/{sample_id}')
            sample.create_dataset('sample/sample_type', data=f'{side.lower()} breast')
            sample.create_dataset('sample/patient_name', data='synthetic-0152')
            for i, m in enumerate(m for m in make_case().measurements if m.side == side):
                group = sample.create_group(f'sets/set_{i}/integration')
                group.create_dataset('q', data=m.q)
                group.create_dataset('i', data=m.intensity)
    case = _normalize_h5(str(path), workflow_id='bremen')
    assert len(case.measurements) == 6
    provider = BremenProvider(model_package=MODEL)
    assert_close(provider.build_features(case).feature_values, GOLD['expected_features'])
    assert_close(provider.execute(case).payload['probability'], GOLD['expected_probability'])


def test_canonical_h5_preserves_physical_q_and_legacy_path(tmp_path):
    import h5py
    q = np.linspace(2, 23, 256)
    ms = [replace(m, q=q, intensity=np.interp(q, m.q, m.intensity))
          for m in make_case().measurements]
    path = tmp_path/'canonical-physical-q.h5'
    with h5py.File(path, 'w') as f:
        for side, label in [('LEFT', 'target'), ('RIGHT', 'contralateral')]:
            group = f.create_group(f'scans/{label}')
            group.create_dataset('q', data=q)
            group.create_dataset('measurements', data=[m.intensity for m in ms if m.side == side])
    case = _normalize_h5(str(path), workflow_id='bremen')
    assert len(case.measurements) == 6
    assert_close(BremenProvider().build_features(case).feature_values, reference_vector(ms))
    for m in case.measurements:
        np.testing.assert_array_equal(m.q, q)
    # The unrelated legacy workflow keeps its prior canonicalization semantics.
    legacy = _normalize_h5(str(path), workflow_id='aramina')
    np.testing.assert_array_equal(legacy.measurements[0].q, np.arange(256))
    with h5py.File(path, 'a') as f:
        del f['scans/target/q']
    with pytest.raises(Exception, match='Missing physical q coordinates'):
        _normalize_h5(str(path), workflow_id='bremen')


@pytest.mark.parametrize('offset', [0, 3])
def test_h5_enumeration_does_not_change_scientific_output(tmp_path, offset):
    for order in permutations(range(3)):
        ms = list(make_case().measurements)
        original = list(ms)
        ms[offset:offset+3] = [original[offset+i] for i in order]
        path = write_session_h5(tmp_path/'permuted.h5', ms)
        case = _normalize_h5(str(path), workflow_id='bremen')
        provider = BremenProvider(model_package=MODEL)
        assert_close(provider.build_features(case).feature_values, GOLD['expected_features'])
        assert_close(provider.execute(case).payload['probability'], GOLD['expected_probability'])


def test_actual_analysis_job_runs_runtime_once(tmp_path, monkeypatch):
    from bremen.api import job_api_handler as jobs
    from bremen.api import model_registry
    jobs.reset_for_tests()
    model_registry.reset_for_tests()
    try:
        path = write_session_h5(tmp_path/'job-input.h5')
        provider = BremenProvider(model_package=MODEL)
        run = Mock(wraps=provider._runtime.run)
        monkeypatch.setattr(provider._runtime, 'run', run)
        registry = WorkflowRegistry()
        registry.register(provider)
        job = jobs.create_analysis_job(h5_path=str(path), registry=registry, model_id='synthetic-model')
        assert job.overall_status == 'completed'
        result = job.workflow_runs['bremen'].result_summary
        assert_close(result['probability'], GOLD['expected_probability'])
        run.assert_called_once()
        features = provider._runtime.build_features(run.call_args.args[0])
        assert_close(features.feature_values, GOLD['expected_features'])
        events = jobs.get_job_events(job.job_id)
        assert len([e for e in events if e['event_type'] == 'runtime.features.completed']) == 1
    finally:
        jobs.reset_for_tests()
        model_registry.reset_for_tests()


def test_runtime_canonical_validation_and_feature_gate_fail_closed():
    from bremen.bremen_runtime import BremenRuntime
    ms = list(make_case().measurements)
    ms[0] = replace(ms[0], q=ms[0].q[::-1])
    with pytest.raises(BremenFeatureError, match='invalid_scientific_profiles'):
        BremenRuntime(MODEL).run(ms)
