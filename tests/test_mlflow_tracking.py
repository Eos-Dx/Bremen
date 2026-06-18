import pandas as pd

from aramis import dataset_fingerprint


def test_dataset_fingerprint_changes_when_values_change():
    left = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    right = pd.DataFrame({"a": [1, 3], "b": ["x", "y"]})

    assert dataset_fingerprint(left) != dataset_fingerprint(right)


def test_dataset_fingerprint_is_stable_for_same_frame():
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})

    assert dataset_fingerprint(df) == dataset_fingerprint(df.copy())
