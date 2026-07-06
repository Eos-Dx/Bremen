"""Tests for v0.1 feature schema rebaseline.

Verifies the 15-column v0.1 schema, lowercase mahalanobis1/2,
and that the old 7-feature assumption is rejected.
"""

from __future__ import annotations

import pytest

from bremen.api.preprocessing_bridge import (
    BREMEN_V01_FEATURE_COLUMNS,
    BREMEN_FEATURE_COLUMNS,
    FEATURE_SCHEMA_VERSION,
    BremenFeatureVector,
    validate_feature_schema,
    FeatureSchemaMismatchError,
)


class TestV01FeatureSchema:
    def test_exact_15_feature_names_and_order(self):
        """BREMEN_V01_FEATURE_COLUMNS matches the delivered 15-column list exactly."""
        expected = [
            "weightedrms1",
            "sigma_l1",
            "sigma_r1",
            "mahalanobis1",
            "weightedrms2",
            "sigma_l2",
            "sigma_r2",
            "mahalanobis2",
            "peak14_intensity",
            "mean_peak_value_raw",
            "wasserstein_distance_muLR",
            "cosine_distance_full_q2",
            "wasserstein_distance_full_q2",
            "meanrms1",
            "meanrms2",
        ]
        assert list(BREMEN_V01_FEATURE_COLUMNS) == expected

    def test_mahalanobis_is_lowercase(self):
        """Entries 4 and 8 are lowercase mahalanobis1 and mahalanobis2."""
        assert BREMEN_V01_FEATURE_COLUMNS[3] == "mahalanobis1"
        assert BREMEN_V01_FEATURE_COLUMNS[7] == "mahalanobis2"
        assert "Mahalanobis1" not in BREMEN_V01_FEATURE_COLUMNS
        assert "Mahalanobis2" not in BREMEN_V01_FEATURE_COLUMNS

    def test_old_7_feature_schema_rejected(self):
        """A feature vector with the old 7 columns fails validation."""
        old_7 = [
            "sigma_l1", "sigma_l2", "Mahalanobis1", "Mahalanobis2",
            "wasserstein_distance_full_q2", "meanrms2", "weightedrms1",
        ]
        vec = BremenFeatureVector(
            features=[0.1] * 7,
            feature_names=old_7,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            patient_id=None,
            target_side=None,
            contralateral_side=None,
        )
        with pytest.raises(FeatureSchemaMismatchError, match="15.*7"):
            validate_feature_schema(vec)

    def test_15_lowercase_schema_accepted(self):
        """A feature vector matching the new 15-column lowercase schema passes."""
        vec = BremenFeatureVector(
            features=[0.1] * 15,
            feature_names=list(BREMEN_V01_FEATURE_COLUMNS),
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            patient_id=None,
            target_side=None,
            contralateral_side=None,
        )
        # Should not raise
        validate_feature_schema(vec)

    def test_feature_schema_version_is_v0_1(self):
        """FEATURE_SCHEMA_VERSION is 'v0.1'."""
        assert FEATURE_SCHEMA_VERSION == "v0.1"

    def test_BREMEN_FEATURE_COLUMNS_alias_matches_v01(self):
        """BREMEN_FEATURE_COLUMNS alias matches BREMEN_V01_FEATURE_COLUMNS."""
        assert BREMEN_FEATURE_COLUMNS == BREMEN_V01_FEATURE_COLUMNS
