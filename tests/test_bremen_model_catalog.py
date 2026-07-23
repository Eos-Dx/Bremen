"""Tests for the Bremen model catalog (PR0082a).

Tests the ModelEntry dataclass, build_model_catalog(), and resolve_model()
with various ModelState configurations.  Uses synthetic non-private fixtures.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_model_package() -> dict[str, Any]:
    """Return a synthetic minimal model package for catalog tests."""
    return {
        "portable_logreg": {
            "coef": [0.1] * 15,
            "imputer_statistics": [0.0] * 15,
            "scaler_mean": [0.0] * 15,
            "scaler_scale": [1.0] * 15,
            "intercept": 0.0,
            "threshold": 0.5,
            "model_version": "smoke-v0.1",
            "feature_schema_version": "v0.1",
        },
        "model_version": "smoke-v0.1",
        "model_checksum": "abc123",
    }


@pytest.fixture
def mock_model_state_ready(monkeypatch, minimal_model_package):
    """Mock ModelState to appear as fully loaded and ready."""
    from bremen.api import model_state as ms

    class FakeState:
        _model_version = "smoke-v0.1"
        _model_checksum = "abc123"

        @staticmethod
        def get_model():
            return minimal_model_package

        @staticmethod
        def is_ready():
            return True

        @staticmethod
        def get_instance():
            return FakeState()

        @staticmethod
        def was_load_attempted():
            return True

        @staticmethod
        def get_load_error():
            return None

    for attr in ("get_model", "is_ready", "get_instance",
                 "was_load_attempted", "get_load_error"):
        monkeypatch.setattr(ms.ModelState, attr, getattr(FakeState, attr))


@pytest.fixture
def mock_model_state_not_configured(monkeypatch):
    """Mock ModelState to appear as not configured."""
    from bremen.api import model_state as ms

    class FakeState:
        _model_version = None
        _model_checksum = None

        @staticmethod
        def get_model():
            return None

        @staticmethod
        def is_ready():
            return False

        @staticmethod
        def get_instance():
            return FakeState()

        @staticmethod
        def was_load_attempted():
            return False

        @staticmethod
        def get_load_error():
            return None

    for attr in ("get_model", "is_ready", "get_instance",
                 "was_load_attempted", "get_load_error"):
        monkeypatch.setattr(ms.ModelState, attr, getattr(FakeState, attr))


@pytest.fixture
def mock_model_state_unavailable(monkeypatch, minimal_model_package):
    """Mock ModelState where model exists but is not ready."""
    from bremen.api import model_state as ms

    class FakeState:
        _model_version = "smoke-v0.1"
        _model_checksum = "abc123"

        @staticmethod
        def get_model():
            return minimal_model_package

        @staticmethod
        def is_ready():
            return False

        @staticmethod
        def get_instance():
            return FakeState()

        @staticmethod
        def was_load_attempted():
            return True

        @staticmethod
        def get_load_error():
            return None

    for attr in ("get_model", "is_ready", "get_instance",
                 "was_load_attempted", "get_load_error"):
        monkeypatch.setattr(ms.ModelState, attr, getattr(FakeState, attr))


# ---------------------------------------------------------------------------
# ModelEntry tests
# ---------------------------------------------------------------------------


class TestModelEntry:
    """ModelEntry dataclass behaves correctly."""

    def test_model_entry_to_dict(self):
        """to_dict() returns safe fields only."""
        from bremen.api.model_catalog import ModelEntry

        entry = ModelEntry(
            model_id="test-model",
            display_name="Test Model",
            workflow_id="bremen",
            model_version="v0.1",
            artifact_type="portable_logreg",
            feature_schema_version="v0.1",
            decision_policy_id="bremen_mri_continuation_threshold",
            decision_policy_version="0.1.0",
            technical_ready=True,
            scientifically_certified=False,
            technical_demo_only=True,
            availability="available",
        )

        d = entry.to_dict()
        assert d["model_id"] == "test-model"
        assert d["display_name"] == "Test Model"
        assert d["workflow_id"] == "bremen"
        assert d["availability"] == "available"

        # No private fields exposed
        assert "artifact_uri" not in d
        assert "checksum" not in d
        assert "path" not in d

    def test_model_entry_frozen(self):
        """ModelEntry is frozen (immutable)."""
        from bremen.api.model_catalog import ModelEntry

        entry = ModelEntry(
            model_id="test", display_name="Test", workflow_id="bremen",
            model_version="v0.1", artifact_type="plr",
            feature_schema_version="v0.1",
            decision_policy_id="policy", decision_policy_version="0.1",
            technical_ready=True, scientifically_certified=False,
            technical_demo_only=True, availability="available",
        )
        with pytest.raises((AttributeError, TypeError)):
            entry.model_id = "changed"


# ---------------------------------------------------------------------------
# build_model_catalog tests
# ---------------------------------------------------------------------------


class TestBuildModelCatalog:
    """build_model_catalog() produces correct catalog."""

    def test_catalog_returns_one_entry_when_configured(
        self, mock_model_state_ready,
    ):
        """Catalog returns one entry when ModelState has a model."""
        from bremen.api.model_catalog import build_model_catalog

        catalog = build_model_catalog()
        assert catalog["status"] == "available"
        assert len(catalog["models"]) == 1
        assert catalog["models"][0]["model_id"] == "bremen-current"
        assert catalog["models"][0]["availability"] == "available"
        assert catalog["default_model_id"] == "bremen-current"
        assert catalog["schema_version"] == "v1"
        assert "catalog_timestamp" in catalog

    def test_catalog_timestamp_is_iso8601(self, mock_model_state_ready):
        """catalog_timestamp is a valid ISO-8601 date string."""
        from bremen.api.model_catalog import build_model_catalog

        catalog = build_model_catalog()
        ts = catalog["catalog_timestamp"]
        # Should parse as datetime
        dt = datetime.fromisoformat(ts)
        assert dt.tzinfo is not None or dt.tzinfo == timezone.utc

    def test_catalog_empty_when_not_configured(
        self, mock_model_state_not_configured,
    ):
        """Catalog returns empty when no model configured."""
        from bremen.api.model_catalog import build_model_catalog

        catalog = build_model_catalog()
        assert catalog["status"] == "not_configured"
        assert len(catalog["models"]) == 0
        assert catalog["default_model_id"] is None

    def test_catalog_unavailable_when_not_ready(
        self, mock_model_state_unavailable,
    ):
        """Model shows as unavailable when model exists but is not ready."""
        from bremen.api.model_catalog import build_model_catalog

        catalog = build_model_catalog()
        assert len(catalog["models"]) == 1
        assert catalog["models"][0]["availability"] == "unavailable"
        assert catalog["models"][0]["technical_ready"] is False
        # default_model_id should be None when the only model is unavailable
        assert catalog["default_model_id"] is None

    def test_catalog_no_artifact_uris(self, mock_model_state_ready):
        """Catalog entries do not expose artifact URIs or paths."""
        from bremen.api.model_catalog import build_model_catalog

        catalog = build_model_catalog()
        body_str = json.dumps(catalog)
        assert "s3://" not in body_str
        assert "joblib" not in body_str.lower()
        assert "/tmp" not in body_str
        assert "local_path" not in body_str.lower()
        assert "model_checksum" not in body_str.lower()
        assert "checksum" not in body_str.lower()

    def test_catalog_no_model_internals(self, mock_model_state_ready):
        """Catalog does not expose model internal parameters."""
        from bremen.api.model_catalog import build_model_catalog

        catalog = build_model_catalog()
        body_str = json.dumps(catalog)
        assert "coef" not in body_str
        assert "intercept" not in body_str
        assert "scaler" not in body_str.lower()
        assert "imputer" not in body_str.lower()
        assert "weight" not in body_str.lower()


# ---------------------------------------------------------------------------
# resolve_model tests
# ---------------------------------------------------------------------------


class TestResolveModel:
    """resolve_model() correctly validates model selection."""

    def test_resolve_default_when_one_available(
        self, mock_model_state_ready,
    ):
        """When no model_id given and exactly one available, return default."""
        from bremen.api.model_catalog import resolve_model

        resolved = resolve_model(None)
        assert resolved == "bremen-current"

    def test_resolve_explicit_valid_model(self, mock_model_state_ready):
        """Explicit valid model_id returns the model."""
        from bremen.api.model_catalog import resolve_model

        resolved = resolve_model("bremen-current")
        assert resolved == "bremen-current"

    def test_resolve_unknown_model_raises(self, mock_model_state_ready):
        """Unknown model_id raises ModelNotFoundError."""
        from bremen.api.model_catalog import (
            resolve_model, ModelNotFoundError,
        )

        with pytest.raises(ModelNotFoundError):
            resolve_model("nonexistent-model")

    def test_resolve_unavailable_model_raises(
        self, mock_model_state_unavailable,
    ):
        """Unavailable model with require_availability=True raises."""
        from bremen.api.model_catalog import (
            resolve_model, ModelUnavailableError,
        )

        with pytest.raises(ModelUnavailableError):
            resolve_model("bremen-current", require_availability=True)

    def test_resolve_default_none_configured(
        self, mock_model_state_not_configured,
    ):
        """No model configured — default resolution raises."""
        from bremen.api.model_catalog import (
            resolve_model, AmbiguousModelSelectionError,
        )

        with pytest.raises(AmbiguousModelSelectionError):
            resolve_model(None)

    def test_resolve_wrong_workflow_raises(self, mock_model_state_ready):
        """Model with wrong workflow_id raises ModelIncompatibleError."""
        from bremen.api.model_catalog import (
            resolve_model, ModelIncompatibleError,
        )

        with pytest.raises(ModelIncompatibleError):
            resolve_model("bremen-current", workflow_id="aramis")
