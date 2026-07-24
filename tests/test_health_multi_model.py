"""Tests for multi-model health endpoint behavior (PR0085).

Tests GET /health with zero, one, and multiple models.
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
from bremen.api.model_state import ModelState
from bremen.api.app import handle_health


@pytest.fixture(autouse=True)
def _auto_reset_registry():
    """Reset the registry and ModelState before and after each test."""
    reset_for_tests()
    ModelState.reset_for_tests()
    yield
    reset_for_tests()
    ModelState.reset_for_tests()


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
    def test_zero_models_returns_200(self):
        """Zero models gives HTTP 200 and model_ready false."""
        reset_for_tests()
        reg = ModelRegistry()
        initialize_registry(reg)
        health = handle_health()
        assert health.status == "ok"
        assert health.model_ready is False

    def test_discovery_failure_returns_200(self):
        """Discovery failure gives HTTP 200 and model_ready false."""
        reset_for_tests()
        reg = ModelRegistry(catalog_status="discovery_failed")
        initialize_registry(reg)
        health = handle_health()
        assert health.status == "ok"
        assert health.model_ready is False


# ---------------------------------------------------------------------------
# One model
# ---------------------------------------------------------------------------


class TestOneModel:
    def test_one_model_ready(self):
        """One model gives model_ready true."""
        reset_for_tests()
        entry = _make_entry()
        reg = ModelRegistry(
            entries=(entry,),
            catalog_status="available",
            available_count=1,
        )
        initialize_registry(reg)
        health = handle_health()
        assert health.status == "ok"
        assert health.model_ready is True


# ---------------------------------------------------------------------------
# Multiple models
# ---------------------------------------------------------------------------


class TestMultipleModels:
    def test_multiple_models_ready(self):
        """Multiple models gives model_ready true."""
        reset_for_tests()
        e1 = _make_entry(model_id="model-a")
        e2 = _make_entry(model_id="model-b")
        reg = ModelRegistry(
            entries=(e1, e2),
            catalog_status="available",
            available_count=2,
        )
        initialize_registry(reg)
        health = handle_health()
        assert health.status == "ok"
        assert health.model_ready is True
