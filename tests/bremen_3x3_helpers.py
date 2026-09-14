"""Valid synthetic Bremen product inputs, derived from frozen PR0151 profiles."""
from pathlib import Path
import json

import h5py
import numpy as np

from bremen.api.xrd_normalization import CanonicalXRDCase, CanonicalXRDMeasurement

FIXTURES = Path(__file__).parent / 'fixtures' / 'bremen_3x3'
GOLD = json.loads((FIXTURES / 'golden.json').read_text())
MODEL = json.loads((FIXTURES / 'model.json').read_text())
DETAIL = json.loads((FIXTURES / 'intermediates.json').read_text())


def make_case(**overrides):
    values = dict(
        source_layout='synthetic', source_layout_version='v1',
        source_checksum='synthetic', calibration_provenance='session_pre_integrated',
        measurements=tuple(CanonicalXRDMeasurement(
            side=m['side'], position=f'P{i % 3 + 1}',
            q=np.array(m['q']), intensity=np.array(m['intensity']),
        ) for i, m in enumerate(GOLD['measurements'])),
    )
    values.update(overrides)
    return CanonicalXRDCase(**values)


def write_session_h5(path, measurements=None):
    """Write actual H5 bytes with native, unequal q/profile arrays and metadata."""
    measurements = make_case().measurements if measurements is None else measurements
    with h5py.File(path, 'w') as f:
        f.create_dataset('/session/sample/sample_type', data='left breast')
        counts = {'LEFT': 0, 'RIGHT': 0}
        for m in measurements:
            counts[m.side] += 1
            prefix = '' if m.side == 'LEFT' else 'contralateral_'
            group = f.create_group(
                f'/session/sets/{prefix}set_{counts[m.side]:03d}_sample_main/integration'
            )
            group.create_dataset('q', data=m.q)
            group.create_dataset('i', data=m.intensity)
    return path
