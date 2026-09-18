"""Tests for multi-model health endpoint behavior (PR0085).

Tests GET /health with zero, one, and multiple models.
Uses the registry directly. No real AWS calls.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from bremen.api.http.app import create_app

import pytest

from bremen.platform.models.registry import (
    RegistryModelEntry,
    ModelRegistry,
    initialize_registry,
    reset_for_tests,
)
from bremen.platform.models.state import ModelState


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


@pytest.mark.parametrize("count", [0, 1, 2])
def test_catalog_health_contract(count):
    initialize_registry(ModelRegistry(
        entries=tuple(_make_entry(str(i)) for i in range(count)),
        available_count=count, catalog_status="available",
    ))
    client = TestClient(create_app(version="contract-test"))
    try:
        response = client.get("/health")
    finally:
        client.close()
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"status", "service", "version", "timestamp", "model_ready"}
    assert body["status"] == "ok"
    assert body["service"] == "bremen"
    assert body["version"] == "contract-test"
    assert body["model_ready"] is (count > 0)
    from datetime import datetime
    assert datetime.fromisoformat(body["timestamp"]).tzinfo is not None


@pytest.mark.parametrize("ready", [False, True])
def test_uncatalogued_health_uses_model_state(monkeypatch, ready):
    monkeypatch.setattr(ModelState, "is_ready", lambda: ready)
    client = TestClient(create_app())
    try:
        assert client.get("/health").json()["model_ready"] is ready
    finally:
        client.close()
