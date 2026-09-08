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
    _build_aramina_request_json,
    _resolve_aramina_provider_url,
    _safe_model_id_env_key,
    _normalize_aramina_provider_response,
    _ARAMINA_OFFICIAL_REQUEST_FIELDS,
    _ARAMINA_DEFAULT_ANALYSIS_AUTHOR,
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

    def test_readiness_manifest_backed_not_configured(self):
        """Manifest-backed Aramina is model_ready even without provider_url."""
        p = AraminaWorkflowProvider(model_id="test-aramina")
        r = p.readiness()
        assert r.configured is False
        # Manifest-gated: model_ready=True so orchestrator passes
        # through to execute() which handles the missing-URL failure.
        assert r.model_ready is True

    def test_readiness_configured(self):
        """With provider_url, readiness is configured and model_ready."""
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
        req = AraminaProviderRequest(
            container_id="c1",
            source_id="s1",
            patient_id="p1",
            target_side="left",
        )
        result = p.execute(MagicMock(), aramina_request=req)
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


# ---------------------------------------------------------------------------
# PR0132 — Provider-boundary failure tests
# ---------------------------------------------------------------------------


class TestAraminaProviderBoundary:
    """Missing provider_url should fail inside Aramina provider boundary,
    not at the generic orchestrator readiness gate.
    """

    def test_missing_provider_url_produces_provider_unavailable(self):
        """Missing BREMEN_ARAMINA_PROVIDER_URL yields safe provider-boundary failure."""
        p = AraminaWorkflowProvider(model_id="test-aramina")
        result = p.execute(MagicMock())
        assert result.status == "failed"
        assert result.error is not None
        # Must reference provider unavailability, not model-not-ready
        assert "not configured" in result.error.lower()
        assert "model" not in result.error.lower()

    def test_missing_provider_url_does_not_leak_internals(self):
        """Safe failure must not expose paths, S3, tokens, or traceback."""
        p = AraminaWorkflowProvider(model_id="test-aramina")
        result = p.execute(MagicMock())
        text = str(result)
        assert "/Users/" not in text
        assert "s3://" not in text
        assert "password" not in text.lower()
        assert "secret" not in text.lower()
        assert "traceback" not in text.lower()
        assert "checksum" not in text.lower()

    def test_manifest_backed_readiness_passes_orchestrator_gate(self):
        """Orchestrator readiness check should NOT block manifest-backed Aramina."""
        from bremen.api.model_registry import (
            RegistryModelEntry, ModelRegistry, initialize_registry,
            reset_for_tests,
        )
        try:
            entry = RegistryModelEntry(
                model_id="aramina-manifest-test",
                display_name="Aramina Manifest Test",
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
            provider = get_provider_for_model("aramina-manifest-test")
            readiness = provider.readiness()
            # Manifest-backed: model_ready=True even without provider_url
            assert readiness.model_ready is True
            assert readiness.configured is False  # No provider URL yet
        finally:
            reset_for_tests()

    def test_bremen_readiness_unchanged(self):
        """Bremen workflow readiness behavior is unchanged by PR0132."""
        from bremen.api.model_registry import (
            RegistryModelEntry, ModelRegistry, initialize_registry,
            reset_for_tests,
        )
        from bremen.api.workflow_bremen import BremenProvider
        try:
            entry = RegistryModelEntry(
                model_id="bremen-readiness-test",
                display_name="Bremen Readiness Test",
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
            provider = get_provider_for_model("bremen-readiness-test")
            assert isinstance(provider, BremenProvider)
            readiness = provider.readiness()
            # Bremen: model_ready depends on actual model package
            # With empty package, model_ready should be False (unchanged)
            assert readiness.model_ready is False
            assert readiness.configured is True
        finally:
            reset_for_tests()


# ---------------------------------------------------------------------------
# PR0133 — Aramina provider adapter contract alignment
# ---------------------------------------------------------------------------


class TestAraminaRequestJson:
    """Official Aramina /predict request_json builder."""

    def test_request_json_contains_only_official_fields(self):
        request_json = _build_aramina_request_json(
            patient_id="p1",
            target_side="left",
            analysis_author="Dr. Smith",
            prediction_comment="Routine",
        )
        assert set(request_json.keys()) == _ARAMINA_OFFICIAL_REQUEST_FIELDS

    def test_blank_analysis_author_defaults_to_bremen_platform(self):
        request_json = _build_aramina_request_json(
            patient_id="p1",
            target_side="left",
            analysis_author="   ",
        )
        assert request_json["analysis_author"] == _ARAMINA_DEFAULT_ANALYSIS_AUTHOR

    def test_missing_analysis_author_defaults_to_bremen_platform(self):
        request_json = _build_aramina_request_json(
            patient_id="p1",
            target_side="left",
        )
        assert request_json["analysis_author"] == _ARAMINA_DEFAULT_ANALYSIS_AUTHOR

    def test_patient_id_missing_raises(self):
        with pytest.raises(ValueError, match="patient_id"):
            _build_aramina_request_json(patient_id="", target_side="left")

    def test_invalid_target_side_raises(self):
        with pytest.raises(ValueError, match="target_side"):
            _build_aramina_request_json(patient_id="p1", target_side="anterior")

    def test_no_bremen_only_fields_forwarded(self):
        request_json = _build_aramina_request_json(
            patient_id="p1",
            target_side="left",
        )
        for field in (
            "container_id", "source_id", "workflow_id", "model_id",
            "job_id", "request_id",
        ):
            assert field not in request_json


class TestAraminaProviderUrlResolution:
    """Per-model provider URL resolution."""

    def test_safe_model_id_env_key(self):
        assert _safe_model_id_env_key("model-a") == "MODEL_A"
        assert _safe_model_id_env_key("Model.1") == "MODEL_1"

    def test_falls_back_to_base_url(self, monkeypatch):
        monkeypatch.setenv("BREMEN_ARAMINA_PROVIDER_URL", "http://base:8080")
        monkeypatch.delenv(
            "BREMEN_ARAMINA_PROVIDER_URL__MODEL_A", raising=False
        )
        assert _resolve_aramina_provider_url("model-a") == "http://base:8080"

    def test_per_model_url_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("BREMEN_ARAMINA_PROVIDER_URL", "http://base:8080")
        monkeypatch.setenv(
            "BREMEN_ARAMINA_PROVIDER_URL__MODEL_A", "http://model-a:9090"
        )
        assert _resolve_aramina_provider_url("model-a") == "http://model-a:9090"

    def test_two_model_ids_not_silently_shared(self, monkeypatch):
        """Two model_ids must not silently share a per-model URL."""
        monkeypatch.setenv("BREMEN_ARAMINA_PROVIDER_URL", "http://base:8080")
        monkeypatch.setenv(
            "BREMEN_ARAMINA_PROVIDER_URL__MODEL_A", "http://model-a:9090"
        )
        # model-a has an explicit per-model URL.
        assert _resolve_aramina_provider_url("model-a") == "http://model-a:9090"
        # model-b has no per-model URL and must fall back to the base URL.
        assert _resolve_aramina_provider_url("model-b") == "http://base:8080"

    def test_provider_init_resolves_per_model_url(self, monkeypatch):
        monkeypatch.setenv(
            "BREMEN_ARAMINA_PROVIDER_URL__MODEL_A", "http://model-a:9090"
        )
        p = AraminaWorkflowProvider(model_id="model-a")
        assert p.readiness().configured is True

    def test_provider_init_falls_back_to_base_url(self, monkeypatch):
        monkeypatch.setenv("BREMEN_ARAMINA_PROVIDER_URL", "http://base:8080")
        monkeypatch.delenv(
            "BREMEN_ARAMINA_PROVIDER_URL__MODEL_A", raising=False
        )
        p = AraminaWorkflowProvider(model_id="model-a")
        assert p.readiness().configured is True


class TestAraminaProviderCallContract:
    """_call_aramina_provider builds official request_json and calls the
    monkeypatchable HTTP boundary.
    """

    def test_provider_url_missing_keeps_safe_failure(self):
        req = AraminaProviderRequest(
            container_id="c1", source_id="s1",
            patient_id="p1", target_side="left",
        )
        with pytest.raises(AraminaProviderUnavailableError):
            _call_aramina_provider(
                _AraminaProviderConfig(provider_url=""),
                req,
            )

    def test_patient_id_missing_fails_before_provider_call(self):
        req = AraminaProviderRequest(
            container_id="c1", source_id="s1",
            patient_id="", target_side="left",
        )
        with patch(
            "bremen.api.workflow_aramina._post_aramina_predict"
        ) as mock_post:
            with pytest.raises(ValueError, match="patient_id"):
                _call_aramina_provider(
                    _AraminaProviderConfig(provider_url="http://localhost:8080"),
                    req,
                )
            mock_post.assert_not_called()

    def test_invalid_target_side_fails_before_provider_call(self):
        req = AraminaProviderRequest(
            container_id="c1", source_id="s1",
            patient_id="p1", target_side="anterior",
        )
        with patch(
            "bremen.api.workflow_aramina._post_aramina_predict"
        ) as mock_post:
            with pytest.raises(ValueError, match="target_side"):
                _call_aramina_provider(
                    _AraminaProviderConfig(provider_url="http://localhost:8080"),
                    req,
                )
            mock_post.assert_not_called()

    def test_provider_url_present_calls_mocked_provider_with_official_request_json(self):
        req = AraminaProviderRequest(
            container_id="c1", source_id="s1",
            patient_id="p1", target_side="left",
            analysis_author="Dr. Smith",
            prediction_comment="Routine",
        )
        with patch(
            "bremen.api.workflow_aramina._post_aramina_predict",
            return_value={
                "external_report": {"summary": "ok"},
                "internal_report": {"model": {"artifact_sha256": "abc"}},
            },
        ) as mock_post:
            result = _call_aramina_provider(
                _AraminaProviderConfig(provider_url="http://localhost:8080"),
                req,
                h5_path="/tmp/input.h5",
            )
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert args[0] == "http://localhost:8080"
            assert kwargs["h5_path"] == "/tmp/input.h5"
            request_json = kwargs["request_json"]
            assert set(request_json.keys()) == _ARAMINA_OFFICIAL_REQUEST_FIELDS
            assert request_json["analysis_author"] == "Dr. Smith"
            assert request_json["patient_id"] == "p1"
            assert request_json["target_side"] == "left"
            # No Bremen-only fields are forwarded to Aramina request_json.
            for field in (
                "container_id", "source_id", "workflow_id", "model_id",
                "job_id", "request_id",
            ):
                assert field not in request_json
            assert result.status == "passed"

    def test_normalized_payload_does_not_expose_internal_report_artifact_sha256(self):
        response = {
            "external_report": {"summary": "ok"},
            "internal_report": {
                "model": {"artifact_sha256": "abc123", "path": "/secret/model.joblib"},
                "token": "secret-token",
            },
        }
        report = _normalize_aramina_provider_response(response)
        text = str(report)
        assert "artifact_sha256" not in text
        assert "abc123" not in text
        assert "/secret/" not in text
        assert "token" not in text.lower()
        assert "internal_report" not in report
        assert report["external_report"]["summary"] == "ok"

    def test_execute_payload_does_not_expose_internal_report_artifact_sha256(self):
        p = AraminaWorkflowProvider(
            model_id="test-aramina",
            provider_url="http://localhost:8080",
        )
        req = AraminaProviderRequest(
            container_id="c1", source_id="s1",
            patient_id="p1", target_side="left",
        )
        with patch(
            "bremen.api.workflow_aramina._post_aramina_predict",
            return_value={
                "external_report": {"summary": "ok"},
                "internal_report": {
                    "model": {"artifact_sha256": "abc123"},
                },
            },
        ):
            result = p.execute(MagicMock(), aramina_request=req)
        assert result.status == "completed"
        text = str(result.payload)
        assert "artifact_sha256" not in text
        assert "abc123" not in text
        assert "internal_report" not in text
        assert result.payload["external_report"]["summary"] == "ok"


# ---------------------------------------------------------------------------
# PR0133 — Job summary/status consistency tests
# ---------------------------------------------------------------------------



class TestAraminaJobSummaryConsistency:
    """Aramina missing provider URL must produce consistent job status
    and execution trace, not misleading report_completed with 0 stages.
    """


    def test_job_status_matches_overall_status(self):
        """When orchestrator returns workflow_configuration_required,
        the job overall_status must match (not be overridden to 'failed')."""
        from bremen.api.job_api_handler import create_analysis_job
        from bremen.api.model_registry import (
            RegistryModelEntry, ModelRegistry, initialize_registry,
            reset_for_tests,
        )
        import os
        import tempfile
        import h5py
        import numpy as np

        try:
            reset_for_tests()
            entry = RegistryModelEntry(
                model_id="aramina-status-test",
                display_name="Aramina Status Test",
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

            # Create a valid Bremen XRD H5 layout so normalization succeeds
            # and the workflow reaches the Aramina provider boundary.
            q = np.linspace(2.0, 23.0, 100, dtype=np.float64)
            with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as f:
                h5_path = f.name
            try:
                with h5py.File(h5_path, "w") as h5:
                    target = h5.create_group("/scans/target")
                    target.create_dataset("measurements",
                                          data=np.random.default_rng(42).normal(1.0, 0.1, (1, 100)))
                    target.create_dataset("q", data=q)
                    target.attrs["side"] = "LEFT"
                    contra = h5.create_group("/scans/contralateral")
                    contra.create_dataset("measurements",
                                          data=np.random.default_rng(43).normal(0.8, 0.1, (1, 100)))
                    contra.create_dataset("q", data=q)
                    contra.attrs["side"] = "RIGHT"

                job = create_analysis_job(
                    container_id="test-container",
                    workflow_id="aramina",
                    h5_path=h5_path,
                    model_id="aramina-status-test",
                )

                assert job.overall_status == "workflow_configuration_required"
            finally:
                os.unlink(h5_path)
        finally:
            reset_for_tests()

    def test_events_no_workflow_unavailable(self):
        """Events must not include workflow_unavailable or model_ready=false
        for Aramina missing-provider case."""
        from bremen.api.event_store import BoundedEventStore
        from bremen.api.workflow_orchestrator import run_workflow_request
        import os
        import tempfile
        import h5py
        import numpy as np
        from bremen.api.model_registry import (
            RegistryModelEntry, ModelRegistry, initialize_registry,
            reset_for_tests,
        )
        try:
            reset_for_tests()
            entry = RegistryModelEntry(
                model_id="aramina-event-test",
                display_name="Aramina Event Test",
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

            # Create a valid Bremen XRD H5 layout so normalization succeeds
            # and the workflow reaches the Aramina provider boundary.
            q = np.linspace(2.0, 23.0, 100, dtype=np.float64)
            with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as f:
                h5_path = f.name
            try:
                with h5py.File(h5_path, "w") as h5:
                    target = h5.create_group("/scans/target")
                    target.create_dataset("measurements",
                                          data=np.random.default_rng(42).normal(1.0, 0.1, (1, 100)))
                    target.create_dataset("q", data=q)
                    target.attrs["side"] = "LEFT"
                    contra = h5.create_group("/scans/contralateral")
                    contra.create_dataset("measurements",
                                          data=np.random.default_rng(43).normal(0.8, 0.1, (1, 100)))
                    contra.create_dataset("q", data=q)
                    contra.attrs["side"] = "RIGHT"

                from bremen.api.workflow_aramina import AraminaWorkflowProvider
                from bremen.api.workflow_registry import WorkflowRegistry

                # Aramina must be registered in the workflow registry
                # (get_default_registry does not include Aramina).
                aramina_provider = AraminaWorkflowProvider(
                    model_id="aramina-event-test",
                    provider_url=None,  # no provider configured
                )
                wf_registry = WorkflowRegistry()
                wf_registry.register(aramina_provider)

                store = BoundedEventStore()
                result = run_workflow_request(
                    h5_path=h5_path,
                    workflow_id="aramina",
                    model_id="aramina-event-test",
                    event_store=store,
                    registry=wf_registry,
                )

                events = store.get_events(result.job_id, since_sequence=0)
                event_types = [e.event_type for e in events]

                assert "runtime.workflow.unavailable" not in event_types
                for ev in events:
                    if ev.details and "model_ready" in ev.details:
                        assert ev.details["model_ready"] is not False

                assert result.overall_status == "workflow_configuration_required"

                completed_events = [e for e in events if e.event_type == "runtime.request.completed"]
                assert len(completed_events) == 1
                assert completed_events[0].details.get("overall_status") == "workflow_configuration_required"
            finally:
                os.unlink(h5_path)
        finally:
            reset_for_tests()
