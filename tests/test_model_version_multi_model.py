"""Tests for multi-model model-version endpoint behavior (PR0085).

Tests GET /model/version with zero, one, and multiple models.
Uses the registry directly. No real AWS calls.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from bremen.api.http.app import create_app

import pytest
from bremen.platform.models.state import ModelState

from bremen.platform.models.registry import (
    RegistryModelEntry,
    ModelRegistry,
    initialize_registry,
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


@pytest.fixture(autouse=True)
def reset_model_state():
    reset_for_tests()
    ModelState.reset_for_tests()
    yield
    reset_for_tests()
    ModelState.reset_for_tests()


@pytest.mark.parametrize("count,status", [(0, "not_configured"), (1, "ready"), (2, "selection_required")])
def test_catalog_model_version_contract(count, status):
    initialize_registry(ModelRegistry(
        entries=tuple(_make_entry(str(i)) for i in range(count)),
        available_count=count, catalog_status="available",
    ))
    client = TestClient(create_app())
    try:
        response = client.get("/model/version")
    finally:
        client.close()
    assert response.status_code == 200
    assert response.json() == {
        "model_configured": count > 0,
        "model_version": "v1.0" if count == 1 else None,
        "model_checksum": None,
        "feature_schema_version": "v0.1" if count == 1 else None,
        "threshold_version": None,
        "threshold_value": None,
        "qc_criteria_version": None,
        "model_status": status,
    }


def test_explicit_package_metadata_without_deserialization(tmp_path):
    from bremen.api.http.system_support import handle_model_version
    from tests.test_bremen_model_package_source import _make_package

    package = _make_package(tmp_path)  # Deliberately invalid pickle bytes.
    response = handle_model_version(explicit_path=package)
    assert response.model_configured is True
    assert response.model_version == "1.0.0"
    assert response.feature_schema_version == "1.0"
    assert response.threshold_value == 0.5
