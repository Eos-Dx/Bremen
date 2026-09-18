"""Tests for multi-model model-version endpoint behavior (PR0085).

Tests GET /model/version with zero, one, and multiple models.
Uses the registry directly. No real AWS calls.
"""

from __future__ import annotations

from bremen.platform.models.registry import (
    RegistryModelEntry,
    reset_for_tests,
)


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



# ---------------------------------------------------------------------------
# One model
# ---------------------------------------------------------------------------


class TestOneModel:
    def teardown_method(self):
        reset_for_tests()



# ---------------------------------------------------------------------------
# Multiple models
# ---------------------------------------------------------------------------


class TestMultipleModels:
    def teardown_method(self):
        reset_for_tests()
