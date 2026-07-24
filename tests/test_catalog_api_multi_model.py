"""Tests for multi-model catalog API behavior (PR0085).

Tests GET /demo/api/models with zero, one, and multiple models.
Uses the registry directly. No real AWS calls.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from bremen.api.model_registry import (
    RegistryModelEntry,
    ModelRegistry,
    initialize_registry,
    reset_for_tests,
)
from bremen.api.model_catalog import build_model_catalog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    model_id: str = "test-model",
    display_name: str = "Test Model",
    availability: str = "available",
) -> RegistryModelEntry:
    return RegistryModelEntry(
        model_id=model_id,
        display_name=display_name,
        workflow_id="bremen",
        model_version="v1.0",
        artifact_type="portable_logreg",
        feature_schema_version="v0.1",
        decision_policy_id="bremen_mri_continuation_threshold",
        decision_policy_version="0.1.0",
        technical_ready=True,
        scientifically_certified=False,
        technical_demo_only=True,
        availability=availability,
        _package={},
        _checksum="a" * 64,
    )


# ---------------------------------------------------------------------------
# Zero-model response
# ---------------------------------------------------------------------------


class TestZeroModelCatalog:
    def teardown_method(self):
        reset_for_tests()

    def test_not_configured(self):
        reg = ModelRegistry()
        initialize_registry(reg)
        catalog = build_model_catalog()
        assert catalog["status"] == "not_configured"
        assert catalog["models"] == []
        assert catalog["default_model_id"] is None
        assert "candidate_count" not in catalog

    def test_no_valid_models(self):
        reg = ModelRegistry(
            catalog_status="no_valid_models",
            candidate_count=2,
            available_count=0,
            rejected_count=2,
        )
        initialize_registry(reg)
        catalog = build_model_catalog()
        assert catalog["status"] == "no_valid_models"
        assert catalog["models"] == []
        assert catalog["default_model_id"] is None
        assert catalog["candidate_count"] == 2
        assert catalog["available_count"] == 0
        assert catalog["rejected_count"] == 2

    def test_discovery_failed(self):
        reg = ModelRegistry(catalog_status="discovery_failed")
        initialize_registry(reg)
        catalog = build_model_catalog()
        assert catalog["status"] == "discovery_failed"
        assert catalog["models"] == []


# ---------------------------------------------------------------------------
# One-model response
# ---------------------------------------------------------------------------


class TestOneModelCatalog:
    def teardown_method(self):
        reset_for_tests()

    def test_one_model_available(self):
        entry = _make_entry()
        reg = ModelRegistry(
            entries=(entry,),
            catalog_status="available",
            candidate_count=1,
            available_count=1,
            rejected_count=0,
        )
        initialize_registry(reg)
        catalog = build_model_catalog()
        assert catalog["status"] == "available"
        assert len(catalog["models"]) == 1
        assert catalog["models"][0]["model_id"] == "test-model"
        assert catalog["default_model_id"] == "test-model"
        assert catalog["candidate_count"] == 1
        assert catalog["available_count"] == 1
        assert catalog["rejected_count"] == 0

    def test_one_model_unavailable(self):
        entry = _make_entry(availability="unavailable")
        reg = ModelRegistry(
            entries=(entry,),
            catalog_status="available",
            candidate_count=1,
            available_count=0,
            rejected_count=0,
        )
        initialize_registry(reg)
        catalog = build_model_catalog()
        assert catalog["status"] == "no_valid_models"
        assert len(catalog["models"]) == 1
        assert catalog["models"][0]["availability"] == "unavailable"
        assert catalog["default_model_id"] is None


# ---------------------------------------------------------------------------
# Multiple-model response
# ---------------------------------------------------------------------------


class TestMultipleModelCatalog:
    def teardown_method(self):
        reset_for_tests()

    def test_two_models(self):
        e1 = _make_entry(model_id="model-a", display_name="Model A")
        e2 = _make_entry(model_id="model-b", display_name="Model B")
        reg = ModelRegistry(
            entries=(e1, e2),
            catalog_status="available",
            candidate_count=2,
            available_count=2,
            rejected_count=0,
        )
        initialize_registry(reg)
        catalog = build_model_catalog()
        assert catalog["status"] == "available"
        assert len(catalog["models"]) == 2
        assert catalog["default_model_id"] is None
        assert catalog["candidate_count"] == 2
        assert catalog["available_count"] == 2

    def test_deterministic_ordering(self):
        e1 = _make_entry(model_id="z-model", display_name="Z")
        e2 = _make_entry(model_id="a-model", display_name="A")
        e3 = _make_entry(model_id="m-model", display_name="M")
        reg = ModelRegistry(
            entries=(e1, e2, e3),
            catalog_status="available",
            available_count=3,
        )
        initialize_registry(reg)
        catalog = build_model_catalog()
        ids = [m["model_id"] for m in catalog["models"]]
        assert ids == sorted(ids), f"Expected sorted model_ids, got {ids}"

    def test_no_private_fields(self):
        entry = _make_entry()
        reg = ModelRegistry(
            entries=(entry,),
            catalog_status="available",
            available_count=1,
        )
        initialize_registry(reg)
        catalog = build_model_catalog()
        body_str = json.dumps(catalog)
        assert "coef" not in body_str
        assert "intercept" not in body_str
        assert "_package" not in body_str
        assert "_checksum" not in body_str
        assert "s3://" not in body_str

    def test_only_technically_valid_models_appear(self):
        """Only models with availability='available' count toward available_count."""
        e1 = _make_entry(model_id="good-model", display_name="Good", availability="available")
        e2 = _make_entry(model_id="bad-model", display_name="Bad", availability="unavailable")
        reg = ModelRegistry(
            entries=(e1, e2),
            catalog_status="available",
            candidate_count=2,
            available_count=1,
            rejected_count=1,
        )
        initialize_registry(reg)
        catalog = build_model_catalog()
        assert catalog["available_count"] == 1
        assert len(catalog["models"]) == 2  # Both entries appear, but only one is available

    def test_rejected_duplicates_do_not_appear(self):
        """Rejected duplicates do not appear in catalog entries."""
        reg = ModelRegistry(
            catalog_status="no_valid_models",
            candidate_count=2,
            available_count=0,
            rejected_count=2,
        )
        initialize_registry(reg)
        catalog = build_model_catalog()
        assert len(catalog["models"]) == 0
        assert catalog["rejected_count"] == 2
