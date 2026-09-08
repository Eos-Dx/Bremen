"""Tests for the Aramina manifest-gated workflow runtime (PR0129).

Tests Aramina workflow provider, manifest-gated routing, Aramina manifest
acceptance in catalog discovery, and provider boundary.

No real external provider calls are made.  No model.joblib is vendored.
No clinical/regulatory claims are made.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from bremen.api.workflow_aramina import (
    AraminaWorkflowProvider,
    AraminaWorkflowError,
    AraminaProviderUnavailableError,
    _AraminaProviderConfig,
    _load_aramina_provider_config,
    _call_aramina_provider,
)
from bremen.api.aramina_provider import (
    AraminaProviderRequest,
    AraminaProviderResult,
    validate_aramina_provider_request,
)


# ---------------------------------------------------------------------------
# AraminaWorkflowProvider
# ---------------------------------------------------------------------------


class TestAraminaWorkflowProvider:
    """Tests for the AraminaWorkflowProvider class."""

    def test_provider_workflow_id(self):
        p = AraminaWorkflowProvider(model_id="test-aramina")
        assert p.workflow_id == "aramina"

    def test_readiness_not_configured(self):
        p = AraminaWorkflowProvider(model_id="test-aramina")
        r = p.readiness()
        assert r.configured is False
        assert r.model_ready is False

    def test_readiness_configured(self):
        p = AraminaWorkflowProvider(
            model_id="test-aramina",
            provider_url="http://localhost:8080",
        )
        r = p.readiness()
        assert r.configured is True
        assert r.model_ready is True

    def test_validate_compatibility_always_true(self):
        p = AraminaWorkflowProvider(model_id="test-aramina")
        result = p.validate_compatibility(None)
        assert result.compatible is True
        assert result.reason == "aramina_manifest_gated"

    def test_build_features_raises(self):
        p = AraminaWorkflowProvider(model_id="test-aramina")
        with pytest.raises(AraminaWorkflowError, match="Bremen feature"):
            p.build_features(None)

    def test_run_inference_returns_failed(self):
        from bremen.api.workflow_provider import WorkflowFeatureVector
        p = AraminaWorkflowProvider(model_id="test-aramina")
        result = p.run_inference(
            WorkflowFeatureVector(
                workflow_id="aramina",
                feature_names=(),
                feature_values=(),
            )
        )
        assert result.status == "failed"
        assert "Bremen feature" in result.error

    def test_execute_provider_unavailable_returns_failed(self):
        p = AraminaWorkflowProvider(model_id="test-aramina")
        result = p.execute(MagicMock())
        assert result.status == "failed"
        assert "not configured" in result.error

    def test_execute_provider_url_configured_returns_completed(self):
        p = AraminaWorkflowProvider(
            model_id="test-aramina",
            provider_url="http://localhost:8080",
        )
        result = p.execute(MagicMock())
        assert result.status == "completed"
        assert result.payload is not None
        assert result.payload["model_family"] == "aramina"
        assert result.payload["clinical_stage"] == "research draft"
        assert result.payload["technical_demo_only"] is True

    def test_execute_with_custom_request(self):
        p = AraminaWorkflowProvider(
            model_id="test-aramina",
            provider_url="http://localhost:8080",
        )
        req = AraminaProviderRequest(
            container_id="c1",
            source_id="s1",
            patient_id="p1",
            target_side="left",
        )
        result = p.execute(MagicMock(), aramina_request=req)
        assert result.status == "completed"
        assert result.payload["target_side"] == "left"

    def test_does_not_use_bremen_provider(self):
        """Aramina workflow does not import or use BremenProvider."""
        from bremen.api.workflow_aramina import AraminaWorkflowProvider
        import inspect
        source = inspect.getsource(AraminaWorkflowProvider.execute)
        assert "BremenProvider" not in source
        assert "bremen" not in source.lower().replace("aramina", "")


# ---------------------------------------------------------------------------
# Provider config
# ---------------------------------------------------------------------------


class TestProviderConfig:
    def test_default_config(self):
        cfg = _AraminaProviderConfig()
        assert cfg.provider_url == ""
        assert cfg.timeout_seconds == 300

    def test_load_config_from_env(self, monkeypatch):
        monkeypatch.setenv("BREMEN_ARAMINA_PROVIDER_URL", "http://localhost:9090")
        monkeypatch.setenv("BREMEN_ARAMINA_TIMEOUT", "60")
        cfg = _load_aramina_provider_config()
        assert cfg.provider_url == "http://localhost:9090"
        assert cfg.timeout_seconds == 60

    def test_load_config_default(self, monkeypatch):
        monkeypatch.delenv("BREMEN_ARAMINA_PROVIDER_URL", raising=False)
        monkeypatch.delenv("BREMEN_ARAMINA_TIMEOUT", raising=False)
        cfg = _load_aramina_provider_config()
        assert cfg.provider_url == ""
        assert cfg.timeout_seconds == 300


# ---------------------------------------------------------------------------
# Provider call
# ---------------------------------------------------------------------------


class TestProviderCall:
    def test_call_without_url_raises(self):
        req = AraminaProviderRequest(
            container_id="c1", source_id="s1",
            patient_id="p1", target_side="left",
        )
        with pytest.raises(AraminaProviderUnavailableError):
            _call_aramina_provider(
                _AraminaProviderConfig(provider_url=""),
                req,
            )

    def test_call_with_url_returns_result(self):
        req = AraminaProviderRequest(
            container_id="c1", source_id="s1",
            patient_id="p1", target_side="right",
        )
        result = _call_aramina_provider(
            _AraminaProviderConfig(provider_url="http://localhost:8080"),
            req,
        )
        assert result.status == "passed"
        assert result.target_side == "right"
        assert result.clinical_stage == "research draft"

    def test_call_exposes_no_internals(self):
        req = AraminaProviderRequest(
            container_id="c1", source_id="s1",
            patient_id="p1", target_side="left",
        )
        result = _call_aramina_provider(
            _AraminaProviderConfig(provider_url="http://localhost:8080"),
            req,
        )
        text = str(result)
        assert "/Users/" not in text
        assert "s3://" not in text
        assert "password" not in text.lower()
        assert "secret" not in text.lower()
        assert "traceback" not in text.lower()


# ---------------------------------------------------------------------------
# Manifest-gated routing
# ---------------------------------------------------------------------------


class TestManifestGatedRouting:
    """Tests that Aramina entries are accepted in catalog discovery."""

    def test_aramina_artifact_type_in_allowed(self):
        from bremen.api.s3_model_discovery import _ARAMINA_ARTIFACT_TYPE
        assert _ARAMINA_ARTIFACT_TYPE == "aramina.joblib.model_package"

    def test_aramina_workflow_id_in_allowed(self):
        from bremen.api.s3_model_discovery import _ALLOWED_WORKFLOW_IDS
        assert "aramina" in _ALLOWED_WORKFLOW_IDS
        assert "bremen" in _ALLOWED_WORKFLOW_IDS

    def test_aramina_validation_rejects_missing_model_version(self):
        from bremen.api.s3_model_discovery import _validate_aramina_discovery_fields
        with pytest.raises(ValueError, match="model_version"):
            _validate_aramina_discovery_fields({
                "model_id": "test-model",
                "display_name": "Test",
                "workflow_id": "aramina",
                "model_version": "",
                "model_filename": "model.joblib",
                "model_checksum": "abc123",
                "feature_schema_version": "v0.1",
                "clinical_stage": "research draft",
                "provider_contract": "aramina_provider.v0.1",
            })

    def test_aramina_validation_rejects_wrong_provider_contract(self):
        from bremen.api.s3_model_discovery import _validate_aramina_discovery_fields
        with pytest.raises(ValueError, match="provider_contract"):
            _validate_aramina_discovery_fields({
                "model_id": "test-model",
                "display_name": "Test",
                "workflow_id": "aramina",
                "model_version": "1.0",
                "model_filename": "model.joblib",
                "model_checksum": "a" * 64,
                "feature_schema_version": "v0.1",
                "clinical_stage": "research draft",
                "provider_contract": "wrong_contract",
            })

    def test_aramina_validation_passes_valid_manifest(self):
        from bremen.api.s3_model_discovery import _validate_aramina_discovery_fields
        result = _validate_aramina_discovery_fields({
            "model_id": "test-model",
            "display_name": "Test",
            "workflow_id": "aramina",
            "model_version": "1.0",
            "model_filename": "model.joblib",
            "model_checksum": "a" * 64,
            "feature_schema_version": "v0.1",
            "clinical_stage": "research draft",
            "provider_contract": "aramina_provider.v0.1",
        })
        assert result["model_id"] == "test-model"

    def test_workflow_orchestrator_resolves_aramina_provider(self):
        """get_provider_for_model returns AraminaWorkflowProvider for aramina entries."""
        from bremen.api.model_registry import (
            RegistryModelEntry, ModelRegistry, initialize_registry,
            reset_for_tests,
        )
        try:
            entry = RegistryModelEntry(
                model_id="aramina-test",
                display_name="Aramina Test",
                workflow_id="aramina",
                model_version="1.0",
                artifact_type="aramina.joblib.model_package",
                feature_schema_version="v0.1",
                decision_policy_id="",
                decision_policy_version="",
                technical_ready=True,
                scientifically_certified=False,
                technical_demo_only=True,
                availability="available",
                _package={},
                _checksum="abc123",
            )
            reg = ModelRegistry(
                entries=(entry,),
                catalog_status="available",
                available_count=1,
            )
            initialize_registry(reg)

            from bremen.api.workflow_orchestrator import get_provider_for_model
            provider = get_provider_for_model("aramina-test")
            assert isinstance(provider, AraminaWorkflowProvider)
            assert provider.workflow_id == "aramina"
        finally:
            reset_for_tests()

    def test_workflow_orchestrator_resolves_bremen_provider_for_bremen(self):
        """get_provider_for_model returns BremenProvider for bremen entries."""
        from bremen.api.model_registry import (
            RegistryModelEntry, ModelRegistry, initialize_registry,
            reset_for_tests,
        )
        from bremen.api.workflow_bremen import BremenProvider
        try:
            entry = RegistryModelEntry(
                model_id="bremen-test",
                display_name="Bremen Test",
                workflow_id="bremen",
                model_version="1.0",
                artifact_type="portable_logreg",
                feature_schema_version="v0.1",
                decision_policy_id="test",
                decision_policy_version="1.0",
                technical_ready=True,
                scientifically_certified=False,
                technical_demo_only=True,
                availability="available",
                _package={"portable_logreg": {"coef": [0.1]*15, "intercept": 0.0, "threshold": 0.5}},
                _checksum="abc123",
            )
            reg = ModelRegistry(
                entries=(entry,),
                catalog_status="available",
                available_count=1,
            )
            initialize_registry(reg)

            from bremen.api.workflow_orchestrator import get_provider_for_model
            provider = get_provider_for_model("bremen-test")
            assert isinstance(provider, BremenProvider)
            assert provider.workflow_id == "bremen"
        finally:
            reset_for_tests()

    def test_unknown_workflow_id_not_routed(self):
        """Unknown workflow_id raises ValueError."""
        from bremen.api.model_registry import (
            RegistryModelEntry, ModelRegistry, initialize_registry,
            reset_for_tests,
        )
        try:
            entry = RegistryModelEntry(
                model_id="unknown-test",
                display_name="Unknown",
                workflow_id="unknown",
                model_version="1.0",
                artifact_type="portable_logreg",
                feature_schema_version="v0.1",
                decision_policy_id="test",
                decision_policy_version="1.0",
                technical_ready=True,
                scientifically_certified=False,
                technical_demo_only=True,
                availability="available",
                _package={"portable_logreg": {"coef": [0.1]*15, "intercept": 0.0, "threshold": 0.5}},
                _checksum="abc123",
            )
            reg = ModelRegistry(
                entries=(entry,),
                catalog_status="available",
                available_count=1,
            )
            initialize_registry(reg)

            from bremen.api.workflow_orchestrator import get_provider_for_model
            with pytest.raises(ValueError):
                get_provider_for_model("unknown-test")
        finally:
            reset_for_tests()


# ---------------------------------------------------------------------------
# Requirements endpoint integration
# ---------------------------------------------------------------------------


class TestAraminaRequirements:
    """Aramina model requirements include patient_id and target_side."""

    def test_aramina_requirements_includes_patient_fields(self):
        """Aramina manifest-backed requirements declare patient_id and target_side."""
        from bremen.api.model_requirements import (
            _build_declared_requirements_response,
            _find_container_requirements,
        )
        row = {
            "model_id": "aramina-test",
            "workflow_id": "aramina",
            "model_version": "1.0",
            "feature_schema_version": "v0.1",
        }
        requirements = {
            "schema_version": "bremen.container_requirements.v1",
            "workflow_id": "aramina",
        }
        resp = _build_declared_requirements_response(
            "aramina-test", row, requirements,
        )
        assert resp["requirements_available"] is True
        assert resp["workflow_id"] == "aramina"
        # Aramina default required fields
        assert "patient_id" in resp["required_fields"]
        assert "target_side" in resp["required_fields"]
        assert "container_id" in resp["required_fields"]
        assert "source_id" in resp["required_fields"]
        # Optional fields
        assert "analysis_author" in resp["optional_fields"]
        assert "prediction_comment" in resp["optional_fields"]

    def test_bremen_requirements_unchanged(self):
        """Bremen manifest-backed requirements are unchanged."""
        from bremen.api.model_requirements import (
            _build_declared_requirements_response,
        )
        row = {
            "model_id": "bremen-test",
            "workflow_id": "bremen",
            "model_version": "1.0",
            "feature_schema_version": "v0.1",
        }
        requirements = {
            "schema_version": "bremen.container_requirements.v1",
            "required_metadata": ["patient_id_or_case_id"],
            "optional_metadata": ["age"],
        }
        resp = _build_declared_requirements_response(
            "bremen-test", row, requirements,
        )
        assert resp["requirements_available"] is True
        assert resp["workflow_id"] == "bremen"
        assert "patient_id_or_case_id" in resp["required_fields"]
        assert "age" in resp["optional_fields"]
