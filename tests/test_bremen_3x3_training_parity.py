"""PR0151 source-backed contract; deliberately does not fix runtime features."""
from itertools import permutations
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tests.reference_0151 import reference_features as ref
from tests.reference_0151.features import analysis_config, build_feature_frame
from tests.reference_0151.prediction import predict_proba_portable

FIXTURES = Path(__file__).parent / 'fixtures' / 'bremen_3x3'
GOLD = json.loads((FIXTURES / 'golden.json').read_text())
MODEL = json.loads((FIXTURES / 'model.json').read_text())
DETAIL = json.loads((FIXTURES / 'intermediates.json').read_text())
TOL = GOLD['absolute_tolerance']


def profiles():
    return pd.DataFrame([
        dict(patientId=GOLD['fixture_id'], side=m['side'],
             q_range=np.array(m['q']), radial_profile_data=np.array(m['intensity']))
        for m in GOLD['measurements']
    ])


def vector(frame):
    result, errors = build_feature_frame(frame)
    assert errors.empty
    assert len(result) == 1
    return result[GOLD['feature_names']]


def assert_close(actual, expected):
    np.testing.assert_allclose(actual, expected, atol=TOL, rtol=0)


def test_golden_features():
    assert GOLD['feature_names'] == ref.FEATURE_COLS
    assert_close(vector(profiles()).iloc[0], GOLD['expected_features'])


def test_golden_probability():
    frozen = pd.DataFrame([GOLD['expected_features']], columns=GOLD['feature_names'])
    assert_close(predict_proba_portable(MODEL['portable_logreg'], frozen),
                 [GOLD['expected_probability']])


@pytest.mark.parametrize('side', ['LEFT', 'RIGHT'])
@pytest.mark.parametrize('order', list(permutations(range(3))))
def test_side_permutation_invariance(side, order):
    indices = list(range(6))
    offset = 0 if side == 'LEFT' else 3
    indices[offset:offset+3] = [offset+i for i in order]
    values = vector(profiles().iloc[indices])
    assert_close(values.iloc[0], GOLD['expected_features'])
    assert_close(predict_proba_portable(MODEL['portable_logreg'], values),
                 [GOLD['expected_probability']])


@pytest.mark.parametrize('index', range(6))
def test_every_replicate_participates(index):
    frame = profiles()
    q = frame.at[index, 'q_range']
    frame.at[index, 'radial_profile_data'] = (
        frame.at[index, 'radial_profile_data'] + 0.12*np.exp(-((q-14.1)/0.8)**2)
    )
    values = vector(frame).iloc[0].to_numpy()
    expected = DETAIL['mutations'][index]
    assert_close(values, expected['expected_features'])
    changed = [name for name, a, b in zip(GOLD['feature_names'], values,
               GOLD['expected_features']) if abs(a-b) > TOL]
    assert changed == expected['changed_features']
    assert 'weightedrms1' in changed
    assert ('sigma_l1' if index < 3 else 'sigma_r1') in changed
    assert ('sigma_r1' if index < 3 else 'sigma_l1') not in changed


@pytest.mark.parametrize('name,roi', [('narrow', (7.5, 23)), ('wide', (2, 23))])
def test_nonidentical_grids_and_intermediate_arrays(name, roi):
    frame = ref.prepare_one_to_one_dataframe(profiles())
    actual = ref.patient_lr_mean_metrics(frame, GOLD['fixture_id'], analysis_config(), roi)
    for key, expected in DETAIL['metrics'][name].items():
        assert_close(actual[key], expected)
    assert actual['n_left'] == actual['n_right'] == 3


def test_sample_std_and_mean_independently():
    q = np.linspace(7.5, 23, 100)
    frame = pd.DataFrame([
        dict(patient_id='variance', side=side, q_range=q,
             radial_profile_data=np.full(100, value))
        for side, values in [('LEFT', [1, 2, 6]), ('RIGHT', [2, 4, 9])]
        for value in values
    ])
    cfg = ref.AnalysisConfig(smooth=False)
    metrics = ref.patient_lr_mean_metrics(frame, 'variance', cfg, cfg.q_roi)
    assert_close(metrics['mu_left'], 3)
    assert_close(metrics['mu_right'], 5)
    assert_close(metrics['std_left'], np.sqrt(7))
    assert_close(metrics['std_right'], np.sqrt(13))
    assert_close(ref.sigma_rms_band(metrics['std_left'], np.ones(100, bool)), np.sqrt(7))


def test_common_grid_intersection_finest_step_and_out_of_range():
    q = ref.build_common_grid([np.linspace(0, 10, 101), np.linspace(1, 9, 41)])
    assert_close(q, np.linspace(1, 9, 81))
    assert_close(ref.resample_to_common(np.array([2, 0, 1]),
                 np.array([20, 0, 10]), np.array([0.5, 1.5])), [5, 15])
    assert np.isnan(ref.resample_to_common(np.array([0, 1]),
                    np.array([0, 10]), np.array([-0.1, 1.1]))).all()
    with pytest.raises(ValueError, match='No overlapping'):
        ref.build_common_grid([np.array([0, 1]), np.array([2, 3])])
    assert len(ref.build_common_grid([np.array([0, 1])])) == 50
    assert len(ref.build_common_grid([np.linspace(0, 1, 6000)])) == 5000


def test_roi_precedes_normalization_and_raw_peaks_precede_aggregation():
    frame = profiles()
    row = frame.iloc[0]
    q, y = ref.apply_roi(row.q_range, row.radial_profile_data, (7.5, 23))
    smoothed = ref.safe_savgol(y, 11, 3)
    assert np.isnan(ref.minimum_reference_value(q, smoothed))
    assert_close(ref.normalize_by_minimum(q, smoothed), smoothed)
    peaks = [np.max(r.radial_profile_data[(r.q_range >= 13) & (r.q_range <= 14.8)])
             for r in frame.itertuples()]
    assert_close(np.mean(peaks), GOLD['expected_features'][9])
    assert abs(GOLD['expected_features'][8] - np.mean(peaks)) > TOL


@pytest.mark.parametrize('sides,valid', [
    (['LEFT']*3+['RIGHT']*3, True),
    (['LEFT']*3+['RIGHT']*2, False),
    (['LEFT']*2+['RIGHT']*4, False),
    (['LEFT']*3+['RIGHT']*3+['UNKNOWN'], False),
])
def test_product_shape_contract(sides, valid):
    # Product requirement only. Upstream and runtime do not enforce this yet.
    assert (len(sides) == 6 and sides.count('LEFT') == sides.count('RIGHT') == 3) == valid


def test_current_platform_probability_against_training_golden():
    from bremen.model_packages.bremen_v01.predictor import predict_proba_portable as platform_predict

    result = platform_predict(MODEL, GOLD['expected_features'])
    assert_close(result['probability'], GOLD['expected_probability'])


def test_q_encoding_and_normalization_fallbacks():
    assert_close(ref.parse_q_grid([2, 23], 100), np.linspace(2, 23, 100))
    assert_close(ref.parse_q_grid('2:23', 100), np.linspace(2, 23, 100))
    with pytest.raises(ValueError, match='length'):
        ref.parse_q_grid(np.array([2, 23]), 100)
    q = np.linspace(6.45, 6.95, 11)
    y = np.arange(1, 12, dtype=float)
    assert_close(ref.normalize_by_minimum(q, y), y/1.5)
    assert_close(ref.normalize_by_minimum(q, y*0), y*0)
    assert_close(ref.normalize_by_minimum(q, y*1e-5), y*1e-2)
    with pytest.raises(ValueError, match='too few'):
        ref.apply_roi(q, y, (15, 23))


def test_peak_is_mean_of_original_maxima():
    q = np.linspace(13, 14.8, 19)
    rows = []
    for i in range(6):
        y = np.ones(19)
        y[i+3] = 2+i
        rows.append(dict(patient_id='peaks', side='LEFT' if i<3 else 'RIGHT',
                         q_range=q, radial_profile_data=y))
    frame = pd.DataFrame(rows)
    raw = ref.patient_mean_raw_peak14(frame, 'peaks', analysis_config())
    assert_close(raw, 4.5)
    assert raw != np.max(np.mean([r['radial_profile_data'] for r in rows], axis=0))
