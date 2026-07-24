"""Tests for multi-model model-version endpoint behavior (PR0085).

Tests GET /model/version with zero, one, and multiple models.
Uses the registry directly. No real AWS calls.
"""

from __future__ import annotations

import pytest

from bremen.api.model_registry import (
    RegistryModelEntry,
    ModelRegistry,
    initialize_registry,
    reset_for_tests,
)
from bremen.api.app import handle_model_version


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(model_id: str = "test-model") -> RegistryModelEntry:
    return RegistryModelEntry(
        model_id=model_id,
        display_name="Test Model",
        workflow_id="bremen",
        model_version="v1.0",
        artifact_type="portable_logreg",
        feature_schema_version="v0.1",
        decision_policy_id="bremen_mri_continuation_threshold",
        decision_policy_version="0.1.0",
        technical_ready=True,
        scientifically_certified=False,
        technical_demo_only=True,
        availability="available",
        _package={},
        _checksum="a" * 64,
    )


# ---------------------------------------------------------------------------
# Zero models
# ---------------------------------------------------------------------------


class TestZeroModels:
    def teardown_method(self):
        reset_for_tests()

    def test_zero_models_not_configured(self):
        """Zero models preserves not_configured behavior."""
        reg = ModelRegistry()
        initialize_registry(reg)
        version = handle_model_version()
        assert version.model_configured is False
        assert version.model_status == "not_configured"
        assert version.model_version is None
        assert version.model_checksum is None
        assert version.feature_schema_version is None
        assert version.threshold_version is None
        assert version.threshold_value is None
        assert version.qc_criteria_version is None


# ---------------------------------------------------------------------------
# One model
# ---------------------------------------------------------------------------


class TestOneModel:
    def teardown_method(self):
        reset_for_tests()

    def test_one_model_returns_singular_metadata(self):
        """One model returns that model's safe metadata."""
        entry = _make_entry()
        reg = ModelRegistry(
            entries=(entry,),
            catalog_status="available",
            available_count=1,
        )
        initialize_registry(reg)
        version = handle_model_version()
        assert version.model_configured is True
        assert version.model_status == "ready"
        assert version.model_version == "v1.0"
        assert version.feature_schema_version == "v0.1"
        # Checksum is private — not exposed
        assert version.model_checksum is None


# ---------------------------------------------------------------------------
# Multiple models
# ---------------------------------------------------------------------------


class TestMultipleModels:
    def teardown_method(self):
        reset_for_tests()

    def test_multiple_models_selection_required(self):
        """Multiple models returns selection_required with null fields."""
        e1 = _make_entry(model_id="model-a")
        e2 = _make_entry(model_id="model-b")
        reg = ModelRegistry(
            entries=(e1, e2),
            catalog_status="available",
            available_count=2,
        )
        initialize_registry(reg)
        version = handle_model_version()
        assert version.model_configured is True
        assert version.model_status == "selection_required"
        assert version.model_version is None
        assert version.model_checksum is None
        assert version.feature_schema_version is None
        assert version.threshold_version is None
        assert version.threshold_value is None
        assert version.qc_criteria_version is None

    def test_no_arbitrary_model_selected(self):
        """No arbitrary model may be selected by ordering."""
        e1 = _make_entry(model_id="a-model")
        e2 = _make_entry(model_id="z-model")
        reg = ModelRegistry(
            entries=(e1, e2),
            catalog_status="available",
            available_count=2,
        )
        initialize_registry(reg)
        version = handle_model_version()
        # Neither model's data should be exposed
        assert version.model_version is None
        assert version.model_status == "selection_required"
