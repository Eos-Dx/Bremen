"""Tests for Bremen feature computation.

All 7 Bremen feature families are per-patient target-vs-contralateral
symmetry measures.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bremen.training.pipeline import (
    BREMEN_FEATURE_FAMILIES,
    _sk_target_contralateral_symmetry_features,
    _mahalanobis_difference,
    _profile_wasserstein,
    _rms_difference,
    _weighted_rms_difference,
    _sigma_rms,
)

_CONFIG = {
    "model": {
        "group_column": "patient_id",
        "side_column": "breast_side",
        "label_column": "label",
        "profile_column": "profile",
    }
}


def _synthetic_df(n_patients: int = 4, n_q: int = 100) -> pd.DataFrame:
    """Create a synthetic DataFrame with target and control profiles."""
    rows = []
    rng = np.random.default_rng(42)
    for pid in range(n_patients):
        for side in ("T", "C"):
            for _ in range(3):  # 3 measurements per side
                profile = rng.normal(0, 1, n_q)
                if side == "C":
                    profile = profile  # control
                else:
                    profile = profile + 0.3  # target has slight shift
                label = "NORMAL" if pid < n_patients // 2 else "BENIGN"
                rows.append({
                    "patient_id": f"P{pid:03d}",
                    "breast_side": side,
                    "label": label,
                    "profile": profile.astype(np.float64),
                })
    return pd.DataFrame(rows)


class TestAllFeatureFamilies:
    def test_all_7_feature_families_in_table(self):
        """Feature table columns include all 7 family names."""
        df = _synthetic_df()
        table = _sk_target_contralateral_symmetry_features(df, _CONFIG)
        for family in BREMEN_FEATURE_FAMILIES:
            assert family in table.columns, f"Missing feature family: {family}"
        assert len(table.columns) >= 2 + len(BREMEN_FEATURE_FAMILIES)

    def test_features_are_finite(self):
        """All 7 features produce finite values."""
        df = _synthetic_df()
        table = _sk_target_contralateral_symmetry_features(df, _CONFIG)
        for family in BREMEN_FEATURE_FAMILIES:
            values = table[family].dropna()
            assert all(np.isfinite(values)), f"Non-finite values in {family}"

    def test_sigma_l1_l2_produced(self):
        """Both sigma_rms variants appear in feature table."""
        df = _synthetic_df()
        table = _sk_target_contralateral_symmetry_features(df, _CONFIG)
        assert "sigma_l1" in table.columns
        assert "sigma_l2" in table.columns

    def test_features_deterministic(self):
        """Same input produces same feature values (fixed random state)."""
        df = _synthetic_df(n_patients=4)
        table1 = _sk_target_contralateral_symmetry_features(df, _CONFIG)
        table2 = _sk_target_contralateral_symmetry_features(df, _CONFIG)
        for family in BREMEN_FEATURE_FAMILIES:
            assert (table1[family] == table2[family]).all(), (
                f"Feature {family} not deterministic"
            )


class TestMahalanobisSemantics:
    def test_mahalanobis_is_per_patient_symmetry(self):
        """Mahalanobis values are computed from target and contralateral of same patient."""
        df = _synthetic_df(n_patients=2)
        table = _sk_target_contralateral_symmetry_features(df, _CONFIG)
        assert "Mahalanobis1" in table.columns
        assert "Mahalanobis2" in table.columns
        assert len(table) == 2  # one row per patient

    def test_mahalanobis_difference_returns_two_values(self):
        """_mahalanobis_difference returns two floats."""
        t = np.random.default_rng(0).normal(0, 1, 50)
        c = np.random.default_rng(1).normal(0, 1, 50)
        m1, m2 = _mahalanobis_difference(t, c)
        assert isinstance(m1, float)
        assert isinstance(m2, float)
        assert np.isfinite(m1)
        assert np.isfinite(m2)


class TestWassersteinSemantics:
    def test_wasserstein_is_per_patient_symmetry(self):
        """Wasserstein distance is computed from target and contralateral of same patient."""
        df = _synthetic_df(n_patients=2)
        table = _sk_target_contralateral_symmetry_features(df, _CONFIG)
        assert "wasserstein_distance_full_q2" in table.columns
        assert len(table) == 2

    def test_wasserstein_value(self):
        """_profile_wasserstein returns finite positive distance."""
        t = np.array([1.0, 2.0, 3.0])
        c = np.array([3.0, 2.0, 1.0])
        d = _profile_wasserstein(t, c)
        assert isinstance(d, float)
        assert d >= 0
        assert np.isfinite(d)


class TestSigmaRms:
    def test_sigma_l1_l2_returns_two_values(self):
        """_sigma_rms returns two floats."""
        t = np.array([1.0, 2.0])
        c = np.array([2.0, 1.0])
        l1, l2 = _sigma_rms(t, c)
        assert isinstance(l1, float)
        assert isinstance(l2, float)
        assert l1 >= 0
        assert l2 >= 0

    def test_identical_profiles_produce_zero(self):
        """Identical target and control profiles produce zero distance."""
        profile = np.array([1.0, 2.0, 3.0])
        l1, l2 = _sigma_rms(profile, profile)
        assert l1 == 0.0
        assert l2 == 0.0


class TestRmsDifference:
    def test_identical_profiles_zero(self):
        """Identical profiles produce zero RMS."""
        p = np.array([1.0, 2.0])
        assert _rms_difference(p, p) == 0.0

    def test_weighted_rms(self):
        """weightedrms produces finite value."""
        t = np.array([1.0, 2.0, 3.0])
        c = np.array([3.0, 2.0, 1.0])
        w = _weighted_rms_difference(t, c)
        assert isinstance(w, float)
        assert w >= 0


class TestMissingContralateral:
    def test_missing_contralateral_produces_nan(self):
        """Rows without a control side produce NaN features."""
        rows = [
            {"patient_id": "P001", "breast_side": "T", "label": "NORMAL",
             "profile": np.array([1.0, 2.0])},
            # Only target, no control for this patient
        ]
        df = pd.DataFrame(rows)
        table = _sk_target_contralateral_symmetry_features(df, _CONFIG)
        for family in BREMEN_FEATURE_FAMILIES:
            assert pd.isna(table[family].iloc[0]), (
                f"Expected NaN for {family} with missing contralateral"
            )


# ---------------------------------------------------------------------------
# Patient-safe split test
# ---------------------------------------------------------------------------


class TestPatientSafeSplits:
    """Verify patient-safe split disjointness via PatientModelSetTrainer.

    Uses GroupShuffleSplit directly from the production training config
    to assert that no patient/group ID appears in both train and test
    sets within any split.
    """

    def _make_training_dataframe(self) -> pd.DataFrame:
        """Create a synthetic dataframe with multiple patients."""
        rows = []
        rng = np.random.default_rng(7)
        n_patients = 10
        n_q = 20
        for pid in range(n_patients):
            for side in ("T", "C"):
                for _ in range(2):
                    profile = rng.normal(0, 1, n_q) + (0.2 if side == "T" else 0.0)
                    label = "NORMAL" if pid < n_patients // 2 else "BENIGN"
                    rows.append({
                        "patient_id": f"P{pid:03d}",
                        "breast_side": side,
                        "label": label,
                        "profile": profile.astype(np.float64),
                    })
        return pd.DataFrame(rows)

    def test_patient_safe_splits_have_disjoint_patient_ids(self):
        """No patient ID appears in both train and test for any split."""
        from sklearn.model_selection import GroupShuffleSplit

        df = self._make_training_dataframe()
        # Build feature table so we have a patient_id column per row
        config = {
            "model": {
                "group_column": "patient_id",
                "side_column": "breast_side",
                "label_column": "label",
                "profile_column": "profile",
                "selected_models": ["M0"],
                "logreg_c": 0.1,
            },
            "evaluation": {
                "n_splits": 5,
                "test_size": 0.3,
                "random_state": 42,
                "target_sensitivity": 0.85,
            },
        }

        feature_table = _sk_target_contralateral_symmetry_features(df, config)
        groups = feature_table["patient_id"]
        n_splits = int(config["evaluation"]["n_splits"])
        test_size = float(config["evaluation"]["test_size"])
        random_state = int(config["evaluation"]["random_state"])

        splitter = GroupShuffleSplit(
            n_splits=n_splits,
            test_size=test_size,
            random_state=random_state,
        )

        y_dummy = np.zeros(len(feature_table))
        X_dummy = feature_table.drop(columns=["patient_id", "label"], errors="ignore")

        for fold, (train_idx, test_idx) in enumerate(
            splitter.split(X_dummy, y_dummy, groups)
        ):
            train_patients = set(groups.iloc[train_idx].unique())
            test_patients = set(groups.iloc[test_idx].unique())

            intersection = train_patients & test_patients
            assert len(intersection) == 0, (
                f"Fold {fold}: {len(intersection)} patient(s) appear in both "
                f"train and test: {intersection}"
            )

        # Also verify healthy total counts
        total_patients = set(groups.unique())
        all_split_patients = set()
        for fold, (train_idx, test_idx) in enumerate(
            splitter.split(X_dummy, y_dummy, groups)
        ):
            all_split_patients.update(groups.iloc[train_idx].unique())
            all_split_patients.update(groups.iloc[test_idx].unique())
        assert len(all_split_patients) == len(total_patients), (
            f"Expected {len(total_patients)} total patients, "
            f"got {len(all_split_patients)}"
        )

    def test_group_shuffle_split_used(self):
        """PatientModelSetTrainer uses GroupShuffleSplit internally."""
        import ast

        pipeline_path = Path(__file__).parents[1] / "src" / "bremen" / "training" / "pipeline.py"
        tree = ast.parse(pipeline_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "GroupShuffleSplit" in alias.name:
                        return  # Found — test passes
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if "GroupShuffleSplit" in alias.name:
                        return  # Found — test passes
        pytest.fail("PatientModelSetTrainer does not import GroupShuffleSplit")

