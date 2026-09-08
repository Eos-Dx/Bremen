"""Tests for PR0122 model requirements no-op API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bremen.api.fastapi_app import create_fastapi_app
from bremen.api.model_registry import (
    ModelRegistry,
    RegistryModelEntry,
    initialize_registry,
    reset_for_tests as reset_model_registry_for_tests,
)
from bremen.api.server import _reset_auth_config
from bremen.auth import create_access_token
from bremen.config import AuthConfig, read_auth_config


_VALID_PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdHNhbHRzYWx0$testhashplaceholder"
_JWT_SECRET = "r" * 48


@pytest.fixture(autouse=True)
def _reset_auth_and_jobs_after_test():
    """Ensure auth config and job state are reset after every test."""
    yield
    _reset_auth_config()
    from bremen.api.job_api_handler import _jobs, _jobs_lock, _event_store
    with _jobs_lock:
        _jobs.clear()
    _event_store.reset_for_tests()


def _enable_auth(monkeypatch) -> None:
    monkeypatch.setenv("BREMEN_AUTH_ENABLED", "true")
    monkeypatch.setenv("BREMEN_AUTH_USERNAME", "testuser")
    monkeypatch.setenv("BREMEN_AUTH_PASSWORD_HASH", _VALID_PASSWORD_HASH)
    monkeypatch.setenv("BREMEN_AUTH_JWT_SECRET", _JWT_SECRET)
    _reset_auth_config()


def _auth_headers() -> dict[str, str]:
    config = read_auth_config()
    token = create_access_token(config, "testuser")
    return {"Authorization": f"Bearer {token}"}


def _install_test_registry() -> None:
    reset_model_registry_for_tests()
    entry = RegistryModelEntry(
        model_id="bremen-mri-triage-logreg-v0-1",
        display_name="Bremen Current",
        workflow_id="bremen",
        model_version="bremen_mri_triage_logreg_v0_1",
        artifact_type="portable_logreg",
        feature_schema_version="v0.1",
        decision_policy_id="bremen_mri_triage_policy",
        decision_policy_version="v0.1",
        technical_ready=True,
        scientifically_certified=False,
        technical_demo_only=True,
        availability="available",
        _package={"portable_logreg": {"feature_schema_version": "v0.1"}},
        _checksum="test-checksum",
    )
    initialize_registry(
        ModelRegistry(
            entries=(entry,),
            catalog_status="available",
            candidate_count=1,
            available_count=1,
            rejected_count=0,
            unavailable_count=0,
        )
    )


def _make_app_with_auth() -> TestClient:
    """Create a FastAPI app with auth directly injected (env-var independent).

    This pattern follows test_bremen_fastapi_auth_enforcement.py to avoid
    env-var pollution between test files in the full suite.
    """
    _reset_auth_config()
    cfg = AuthConfig(
        enabled=True,
        username="testuser",
        password_hash=_VALID_PASSWORD_HASH,
        jwt_secret=_JWT_SECRET,
        jwt_issuer="test-issuer",
        jwt_audience="test-audience",
        access_ttl_seconds=900,
        refresh_ttl_seconds=604800,
    )
    from bremen.api import server as _server
    _server._auth_config = cfg
    return TestClient(create_fastapi_app())


def _make_app_no_auth() -> TestClient:
    """Create a FastAPI app with auth disabled."""
    _reset_auth_config()
    from bremen.api import server as _server
    _server._auth_config = None
    return TestClient(create_fastapi_app())


# ---------------------------------------------------------------------------
# Auth gate tests
# ---------------------------------------------------------------------------


def test_get_model_requirements_requires_bearer_auth():
    """GET requirements without auth returns 401."""
    _install_test_registry()
    client = _make_app_with_auth()
    response = client.get(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements"
    )
    assert response.status_code == 401
    assert response.json()["token_type"] == "Bearer"


def test_post_model_requirements_validate_requires_bearer_auth():
    """POST validate without auth returns 401."""
    _install_test_registry()
    client = _make_app_with_auth()
    response = client.post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        json={"container_id": "Nova_376.h5", "source_id": "source-1"},
    )
    assert response.status_code == 401
    assert response.json()["token_type"] == "Bearer"


# ---------------------------------------------------------------------------
# Known model GET requirements
# ---------------------------------------------------------------------------


def test_get_model_requirements_known_model_returns_honest_noop():
    """GET requirements for known model returns 200 honest no-op."""
    _install_test_registry()
    client = _make_app_with_auth()
    config = AuthConfig(
        enabled=True,
        username="testuser",
        password_hash=_VALID_PASSWORD_HASH,
        jwt_secret=_JWT_SECRET,
        jwt_issuer="test-issuer",
        jwt_audience="test-audience",
        access_ttl_seconds=900,
        refresh_ttl_seconds=604800,
    )
    token = create_access_token(config, "testuser")
    response = client.get(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["schema_version"] == "bremen.model_requirements.v1"
    assert data["technical_demo_only"] is True
    assert data["model_id"] == "bremen-mri-triage-logreg-v0-1"
    assert data["workflow_id"] == "bremen"
    assert data["model_version"] == "bremen_mri_triage_logreg_v0_1"
    assert data["feature_schema_version"] == "v0.1"
    assert data["requirements_available"] is False
    assert data["status"] == "requirements_not_declared"
    assert data["required_container_contract"] is None
    assert data["required_fields"] == []
    assert data["optional_fields"] == []


# ---------------------------------------------------------------------------
# Unknown model GET requirements
# ---------------------------------------------------------------------------


def test_get_model_requirements_unknown_model_returns_404():
    """GET requirements for unknown model returns 404."""
    _install_test_registry()
    client = _make_app_with_auth()
    config = AuthConfig(
        enabled=True,
        username="testuser",
        password_hash=_VALID_PASSWORD_HASH,
        jwt_secret=_JWT_SECRET,
        jwt_issuer="test-issuer",
        jwt_audience="test-audience",
        access_ttl_seconds=900,
        refresh_ttl_seconds=604800,
    )
    token = create_access_token(config, "testuser")
    response = client.get(
        "/demo/api/models/unknown-model/requirements",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "Model not found"
    assert response.json()["model_id"] == "unknown-model"


# ---------------------------------------------------------------------------
# Known model POST validate
# ---------------------------------------------------------------------------


def test_post_model_requirements_validate_known_model_returns_noop():
    """POST validate for known model returns 200 honest no-op."""
    _install_test_registry()
    client = _make_app_with_auth()
    config = AuthConfig(
        enabled=True,
        username="testuser",
        password_hash=_VALID_PASSWORD_HASH,
        jwt_secret=_JWT_SECRET,
        jwt_issuer="test-issuer",
        jwt_audience="test-audience",
        access_ttl_seconds=900,
        refresh_ttl_seconds=604800,
    )
    token = create_access_token(config, "testuser")
    response = client.post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "container_id": "Nova_376.h5",
            "source_id": "fresh-source-id",
            "workflow_id": "bremen",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["schema_version"] == "bremen.model_requirements_validation.v1"
    assert data["technical_demo_only"] is True
    assert data["model_id"] == "bremen-mri-triage-logreg-v0-1"
    assert data["workflow_id"] == "bremen"
    assert data["container_id"] == "Nova_376.h5"
    assert data["source_id"] == "fresh-source-id"
    assert data["validation_available"] is False
    assert data["validation"]["status"] == "not_available"
    assert data["validation"]["ready_to_run"] is None
    assert data["validation"]["requirements_checked"] is False
    assert data["validation"]["inference_job_created"] is False
    assert data["validation"]["report_created"] is False
    assert data["missing_required_fields"] == []
    assert data["invalid_fields"] == []


# ---------------------------------------------------------------------------
# Unknown model POST validate
# ---------------------------------------------------------------------------


def test_post_model_requirements_validate_unknown_model_returns_404():
    """POST validate for unknown model returns 404."""
    _install_test_registry()
    client = _make_app_with_auth()
    config = AuthConfig(
        enabled=True,
        username="testuser",
        password_hash=_VALID_PASSWORD_HASH,
        jwt_secret=_JWT_SECRET,
        jwt_issuer="test-issuer",
        jwt_audience="test-audience",
        access_ttl_seconds=900,
        refresh_ttl_seconds=604800,
    )
    token = create_access_token(config, "testuser")
    response = client.post(
        "/demo/api/models/unknown-model/requirements/validate",
        headers={"Authorization": f"Bearer {token}"},
        json={"container_id": "Nova_376.h5", "source_id": "fresh-source-id"},
    )

    assert response.status_code == 404
    assert response.json()["error"] == "Model not found"
    assert response.json()["model_id"] == "unknown-model"


# ---------------------------------------------------------------------------
# Validate does not create job or report
# ---------------------------------------------------------------------------


def test_post_model_requirements_validate_does_not_create_job():
    """Validate endpoint does not create any inference job."""
    _install_test_registry()
    client = _make_app_with_auth()
    config = AuthConfig(
        enabled=True,
        username="testuser",
        password_hash=_VALID_PASSWORD_HASH,
        jwt_secret=_JWT_SECRET,
        jwt_issuer="test-issuer",
        jwt_audience="test-audience",
        access_ttl_seconds=900,
        refresh_ttl_seconds=604800,
    )
    token = create_access_token(config, "testuser")

    from bremen.api.job_api_handler import _jobs, _jobs_lock

    with _jobs_lock:
        before = set(_jobs)

    response = client.post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers={"Authorization": f"Bearer {token}"},
        json={"container_id": "Nova_376.h5", "source_id": "fresh-source-id"},
    )

    assert response.status_code == 200

    with _jobs_lock:
        after = set(_jobs)

    assert after == before
    assert response.json()["validation"]["inference_job_created"] is False
    assert response.json()["validation"]["report_created"] is False


def test_post_model_requirements_validate_invalid_json_returns_400():
    """POST validate with non-JSON body returns 400 safe JSON."""
    _install_test_registry()
    client = _make_app_with_auth()
    config = AuthConfig(
        enabled=True,
        username="testuser",
        password_hash=_VALID_PASSWORD_HASH,
        jwt_secret=_JWT_SECRET,
        jwt_issuer="test-issuer",
        jwt_audience="test-audience",
        access_ttl_seconds=900,
        refresh_ttl_seconds=604800,
    )
    token = create_access_token(config, "testuser")

    response = client.post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers={"Authorization": f"Bearer {token}"},
        content=b"this is not json",
    )

    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["technical_demo_only"] is True
    # Must not leak parser internals
    assert "traceback" not in str(data).lower()
    assert "json" in data["error"].lower()


def test_post_model_requirements_validate_empty_body_returns_200():
    """POST validate with empty body returns valid no-op (empty dict is allowed)."""
    _install_test_registry()
    client = _make_app_with_auth()
    config = AuthConfig(
        enabled=True,
        username="testuser",
        password_hash=_VALID_PASSWORD_HASH,
        jwt_secret=_JWT_SECRET,
        jwt_issuer="test-issuer",
        jwt_audience="test-audience",
        access_ttl_seconds=900,
        refresh_ttl_seconds=604800,
    )
    token = create_access_token(config, "testuser")

    response = client.post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["validation"]["inference_job_created"] is False
    assert data["validation"]["report_created"] is False


def test_post_model_requirements_validate_does_not_create_report():
    """Validate endpoint explicitly confirms no report is created."""
    _install_test_registry()
    client = _make_app_with_auth()
    config = AuthConfig(
        enabled=True,
        username="testuser",
        password_hash=_VALID_PASSWORD_HASH,
        jwt_secret=_JWT_SECRET,
        jwt_issuer="test-issuer",
        jwt_audience="test-audience",
        access_ttl_seconds=900,
        refresh_ttl_seconds=604800,
    )
    token = create_access_token(config, "testuser")

    response = client.post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers={"Authorization": f"Bearer {token}"},
        json={"container_id": "Nova_376.h5", "source_id": "fresh-source-id"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["validation"]["report_created"] is False
    assert data["validation"]["inference_job_created"] is False
    assert data["validation"]["requirements_checked"] is False
    assert data["next_step"]["can_submit_job"] is None
    assert "jobs" in data["next_step"]["reason"]


# ---------------------------------------------------------------------------
# Response must not leak private internals
# ---------------------------------------------------------------------------


def test_get_requirements_response_no_private_internals():
    """GET requirements response must not expose private internals."""
    _install_test_registry()
    client = _make_app_with_auth()
    config = AuthConfig(
        enabled=True,
        username="testuser",
        password_hash=_VALID_PASSWORD_HASH,
        jwt_secret=_JWT_SECRET,
        jwt_issuer="test-issuer",
        jwt_audience="test-audience",
        access_ttl_seconds=900,
        refresh_ttl_seconds=604800,
    )
    token = create_access_token(config, "testuser")

    response = client.get(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    text = str(data)
    # Must not contain private package internals, checksums, paths, S3, tokens
    assert "_checksum" not in text
    assert "_package" not in text
    assert "portable_logreg" not in text
    assert "test-checksum" not in text
    assert "/Users/" not in text
    assert "s3://" not in text
    assert "boto" not in text.lower()
    assert "password" not in text.lower()
    assert "secret" not in text.lower()
    assert "token" not in text.lower()
    assert "Bearer" not in text


def test_post_validate_response_no_private_internals():
    """POST validate response must not expose private internals."""
    _install_test_registry()
    client = _make_app_with_auth()
    config = AuthConfig(
        enabled=True,
        username="testuser",
        password_hash=_VALID_PASSWORD_HASH,
        jwt_secret=_JWT_SECRET,
        jwt_issuer="test-issuer",
        jwt_audience="test-audience",
        access_ttl_seconds=900,
        refresh_ttl_seconds=604800,
    )
    token = create_access_token(config, "testuser")

    response = client.post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers={"Authorization": f"Bearer {token}"},
        json={"container_id": "Nova_376.h5", "source_id": "fresh-source-id"},
    )

    assert response.status_code == 200
    data = response.json()
    text = str(data)
    assert "_checksum" not in text
    assert "_package" not in text
    assert "portable_logreg" not in text
    assert "test-checksum" not in text
    assert "/Users/" not in text
    assert "s3://" not in text
    assert "boto" not in text.lower()
    assert "password" not in text.lower()
    assert "secret" not in text.lower()
    assert "token" not in text.lower()
    assert "Bearer" not in text


# ---------------------------------------------------------------------------
# workflow_id from catalog
# ---------------------------------------------------------------------------


def test_workflow_id_from_model_catalog_row():
    """Response workflow_id must come from the model catalog row."""
    _install_test_registry()
    client = _make_app_with_auth()
    config = AuthConfig(
        enabled=True,
        username="testuser",
        password_hash=_VALID_PASSWORD_HASH,
        jwt_secret=_JWT_SECRET,
        jwt_issuer="test-issuer",
        jwt_audience="test-audience",
        access_ttl_seconds=900,
        refresh_ttl_seconds=604800,
    )
    token = create_access_token(config, "testuser")

    # GET requirements: workflow_id from catalog
    response = client.get(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["workflow_id"] == "bremen"
    assert data["model_id"] == "bremen-mri-triage-logreg-v0-1"

    # POST validate: workflow_id from catalog (not from request body)
    response = client.post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers={"Authorization": f"Bearer {token}"},
        json={"workflow_id": "something-else"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["workflow_id"] == "bremen"  # from catalog, not from request


# ---------------------------------------------------------------------------
# Endpoints exist and no longer return 404
# ---------------------------------------------------------------------------


def test_requirements_endpoints_exist_and_not_404():
    """Both requirements endpoints no longer return 404."""
    _install_test_registry()
    client = _make_app_with_auth()
    config = AuthConfig(
        enabled=True,
        username="testuser",
        password_hash=_VALID_PASSWORD_HASH,
        jwt_secret=_JWT_SECRET,
        jwt_issuer="test-issuer",
        jwt_audience="test-audience",
        access_ttl_seconds=900,
        refresh_ttl_seconds=604800,
    )
    token = create_access_token(config, "testuser")

    # GET
    response = client.get(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    # POST
    response = client.post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers={"Authorization": f"Bearer {token}"},
        json={"container_id": "test.h5"},
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Existing POST /demo/api/jobs behavior remains unchanged
# ---------------------------------------------------------------------------


def test_existing_post_jobs_unchanged():
    """Existing POST /demo/api/jobs route still works normally."""
    _install_test_registry()

    # Disable auth by injecting None directly into server singleton
    _reset_auth_config()
    from bremen.api import server as _server
    _server._auth_config = None
    client = TestClient(create_fastapi_app())

    response = client.post(
        "/demo/api/jobs",
        json={"workflow_id": "bremen"},
    )
    # Without a source, jobs should return 400 with MISSING_SOURCE error
    assert response.status_code == 400
    data = response.json()
    assert data.get("error_code") == "MISSING_SOURCE"


def test_post_model_requirements_validate_does_not_echo_h5_path(monkeypatch):
    _enable_auth(monkeypatch)
    _install_test_registry()

    response = TestClient(create_fastapi_app()).post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={
            "container_id": "Nova_376.h5",
            "source_id": "fresh-source-id",
            "h5_path": "/tmp/private/Nova_376.h5",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "h5_path" not in data
    assert data["h5_path_supplied"] is True
    assert "/tmp/private/Nova_376.h5" not in str(data)


# ---------------------------------------------------------------------------
# Manifest-backed requirements
# ---------------------------------------------------------------------------


def _install_test_registry_with_container_requirements() -> None:
    reset_model_registry_for_tests()
    entry = RegistryModelEntry(
        model_id="bremen-mri-triage-logreg-v0-1",
        display_name="Bremen Current",
        workflow_id="bremen",
        model_version="bremen_mri_triage_logreg_v0_1",
        artifact_type="portable_logreg",
        feature_schema_version="v0.1",
        decision_policy_id="bremen_mri_triage_policy",
        decision_policy_version="v0.1",
        technical_ready=True,
        scientifically_certified=False,
        technical_demo_only=True,
        availability="available",
        _package={"portable_logreg": {"feature_schema_version": "v0.1"}},
        _checksum="test-checksum",
        _container_requirements={
            "schema_version": "bremen.container_requirements.v1",
            "requirements_id": "bremen-test-container.v0.1",
            "model_family": "bremen",
            "workflow_id": "bremen",
            "input_container": {
                "format": "hdf5",
                "accepted_extensions": [".h5", ".hdf5"],
                "container_contract_id": "bremen-xrd-session-container.v0.1",
            },
            "required_metadata": ["patient_id_or_case_id"],
            "optional_metadata": ["age"],
            "validation_behavior": {
                "preflight_only": True,
                "must_not_create_job": True,
                "must_not_run_inference": True,
                "must_not_create_report": True,
            },
            "technical_demo_only": True,
        },
    )
    initialize_registry(
        ModelRegistry(
            entries=(entry,),
            catalog_status="available",
            candidate_count=1,
            available_count=1,
            rejected_count=0,
            unavailable_count=0,
        )
    )


def test_get_model_requirements_with_manifest_returns_declared(monkeypatch):
    _enable_auth(monkeypatch)
    _install_test_registry_with_container_requirements()

    response = TestClient(create_fastapi_app()).get(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["requirements_available"] is True
    assert data["status"] == "requirements_declared"
    assert data["required_container_contract"]["format"] == "hdf5"
    assert data["required_fields"] == ["patient_id_or_case_id"]
    assert data["optional_fields"] == ["age"]
    assert data["container_requirements"]["requirements_id"] == (
        "bremen-test-container.v0.1"
    )
    assert "s3://" not in str(data)
    assert "/tmp/" not in str(data)
    assert "test-checksum" not in str(data)


def test_post_validate_with_manifest_required_present_returns_passed(monkeypatch):
    """When manifest exists and required fields are present, dry run is attempted.

    With a fake source_id the dry run fails at container_resolution,
    which is the expected behavior for a source that doesn't exist.
    """
    _enable_auth(monkeypatch)
    _install_test_registry_with_container_requirements()

    response = TestClient(create_fastapi_app()).post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={"container_id": "Nova_376.h5", "source_id": "fresh-source-id"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["requirements_available"] is True
    assert data["requirements_status"] == "requirements_declared"
    assert data["validation_available"] is True
    # Dry run attempted — fails because fake source_id doesn't exist
    assert data["validation"]["status"] == "failed"
    assert data["validation"]["ready_to_run"] is False
    assert data["validation"]["requirements_checked"] is True
    assert data["validation"]["inference_job_created"] is False
    assert data["validation"]["report_created"] is False
    assert data["validation"]["read_only"] is True
    assert data["validation"]["dry_run_mode"] == "model_pipeline"
    assert data["missing_required_fields"] == []
    assert data["invalid_fields"] == []
    assert data["next_step"]["can_submit_job"] is False
    assert data["failure_stage"] == "container_resolution"
    # checked_stages must be a non-empty list
    assert isinstance(data["checked_stages"], list)
    assert "request_payload" in data["checked_stages"]
    assert "model_resolution" in data["checked_stages"]


def test_post_validate_with_manifest_required_missing_returns_failed(monkeypatch):
    """When manifest exists but required fields are missing, validation fails."""
    _enable_auth(monkeypatch)
    _install_test_registry_with_container_requirements()

    response = TestClient(create_fastapi_app()).post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["requirements_available"] is True
    assert data["requirements_status"] == "requirements_declared"
    assert data["validation_available"] is True
    assert data["validation"]["status"] == "failed"
    assert data["validation"]["ready_to_run"] is False
    assert data["validation"]["requirements_checked"] is True
    assert data["validation"]["inference_job_created"] is False
    assert data["validation"]["report_created"] is False
    assert "container_id" in data["missing_required_fields"]
    assert data["next_step"]["can_submit_job"] is False


def test_post_validate_without_manifest_still_noop(monkeypatch):
    """When no manifest exists, validate remains a no-op."""
    _enable_auth(monkeypatch)
    _install_test_registry()

    response = TestClient(create_fastapi_app()).post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={"container_id": "Nova_376.h5", "source_id": "fresh-source-id"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["validation_available"] is False
    assert data["validation"]["status"] == "not_available"
    assert data["validation"]["ready_to_run"] is None
    assert data["validation"]["requirements_checked"] is False
    assert data["validation"]["inference_job_created"] is False
    assert data["validation"]["report_created"] is False
    assert data["next_step"]["can_submit_job"] is None


def test_post_validate_h5_path_not_echoed(monkeypatch):
    """Validate must not echo raw h5_path, only h5_path_supplied boolean."""
    _enable_auth(monkeypatch)
    _install_test_registry_with_container_requirements()

    response = TestClient(create_fastapi_app()).post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={"container_id": "Nova_376.h5", "h5_path": "/tmp/private/Nova_376.h5"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "h5_path" not in data
    assert data["h5_path_supplied"] is True
    assert "/tmp/private/Nova_376.h5" not in str(data)


# ---------------------------------------------------------------------------
# PR0126: Dry-run model pipeline tests
# ---------------------------------------------------------------------------


def _make_real_model_package() -> dict:
    """Create a minimal but functional portable_logreg model package."""
    import numpy as np

    return {
        "portable_logreg": {
            "feature_columns": [
                "weightedrms1", "sigma_l1", "sigma_r1", "mahalanobis1",
                "weightedrms2", "sigma_l2", "sigma_r2", "mahalanobis2",
                "peak14_intensity", "mean_peak_value_raw",
                "wasserstein_distance_muLR", "cosine_distance_full_q2",
                "wasserstein_distance_full_q2", "meanrms1", "meanrms2",
            ],
            "imputer_statistics": [0.0] * 15,
            "scaler_mean": [0.0] * 15,
            "scaler_scale": [1.0] * 15,
            "coef": [0.1] * 15,
            "intercept": 0.0,
            "threshold": 0.5,
        },
    }


def _install_test_registry_with_real_package_and_requirements() -> None:
    """Install registry with a real model package and container requirements."""
    reset_model_registry_for_tests()
    entry = RegistryModelEntry(
        model_id="bremen-mri-triage-logreg-v0-1",
        display_name="Bremen Current",
        workflow_id="bremen",
        model_version="bremen_mri_triage_logreg_v0_1",
        artifact_type="portable_logreg",
        feature_schema_version="v0.1",
        decision_policy_id="bremen_mri_triage_policy",
        decision_policy_version="v0.1",
        technical_ready=True,
        scientifically_certified=False,
        technical_demo_only=True,
        availability="available",
        _package=_make_real_model_package(),
        _checksum="test-checksum",
        _container_requirements={
            "schema_version": "bremen.container_requirements.v1",
            "requirements_id": "bremen-test-container.v0.1",
            "model_family": "bremen",
            "workflow_id": "bremen",
            "input_container": {
                "format": "hdf5",
                "accepted_extensions": [".h5", ".hdf5"],
                "container_contract_id": "bremen-xrd-session-container.v0.1",
            },
            "required_metadata": ["patient_id_or_case_id"],
            "optional_metadata": ["age"],
            "request_requirements": {
                "required_fields": ["container_id", "source_id"],
                "optional_fields": ["workflow_id", "upload_id"],
            },
            "validation_behavior": {
                "preflight_only": True,
                "must_not_create_job": True,
                "must_not_run_inference": True,
                "must_not_create_report": True,
            },
            "technical_demo_only": True,
        },
    )
    initialize_registry(
        ModelRegistry(
            entries=(entry,),
            catalog_status="available",
            candidate_count=1,
            available_count=1,
            rejected_count=0,
            unavailable_count=0,
        )
    )


def _create_real_h5_file(tmp_path) -> str:
    """Create a minimal but valid H5 file that can be normalized.

    Uses the canonical /scans/target/ + /scans/contralateral/ layout.
    """
    import h5py
    import numpy as np

    h5_path = str(tmp_path / "test_valid.h5")
    with h5py.File(h5_path, "w") as h5:
        rng = np.random.default_rng(42)
        q = np.linspace(2.0, 23.0, 100, dtype=np.float64)

        # Target (LEFT) measurements
        target = h5.create_group("/scans/target")
        target.create_dataset("measurements", data=rng.normal(1.0, 0.1, size=(1, 100)))
        target.create_dataset("q", data=q)
        target.attrs["side"] = "LEFT"

        # Contralateral (RIGHT) measurements
        contra = h5.create_group("/scans/contralateral")
        contra.create_dataset("measurements", data=rng.normal(0.8, 0.1, size=(1, 100)))
        contra.create_dataset("q", data=q)
        contra.attrs["side"] = "RIGHT"

    return h5_path


def _register_source_for_test(h5_path: str, filename: str = "test_valid.h5") -> str:
    """Register a local file as a catalog source for testing.

    Returns the opaque source_id.
    """
    from bremen.api.source_registry import register_source
    import os

    size_bytes = os.path.getsize(h5_path)
    source_id = register_source(
        bucket="test-bucket",
        object_key=f"test-prefix/{filename}",
        filename=filename,
        size_bytes=size_bytes,
        prefix="test-prefix/",
    )
    return source_id


def test_dry_run_with_valid_source_passes(tmp_path, monkeypatch):
    """Dry run with a real H5, real model package, and registered source passes."""
    _enable_auth(monkeypatch)
    _install_test_registry_with_real_package_and_requirements()

    h5_path = _create_real_h5_file(tmp_path)
    source_id = _register_source_for_test(h5_path, "Nova_376.h5")

    # Patch resolve_source at the model_requirements module level
    from bremen.api import model_requirements as _mr
    monkeypatch.setattr(_mr, "_resolve_source_for_dry_run", lambda sid: h5_path)

    response = TestClient(create_fastapi_app()).post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={"container_id": "Nova_376.h5", "source_id": source_id},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["requirements_available"] is True
    assert data["validation_available"] is True
    assert data["validation"]["status"] == "passed"
    assert data["validation"]["ready_to_run"] is True
    assert data["validation"]["read_only"] is True
    assert data["validation"]["dry_run_mode"] == "model_pipeline"
    assert data["validation"]["inference_job_created"] is False
    assert data["validation"]["report_created"] is False
    assert data["next_step"]["can_submit_job"] is True
    assert data["failure_stage"] is None
    assert data["next_step"]["reason"] == "Dry run passed. Use POST /demo/api/jobs for execution."
    # checked_stages must be a non-empty list for successful dry run
    assert isinstance(data["checked_stages"], list)
    assert len(data["checked_stages"]) > 0
    assert "request_payload" in data["checked_stages"]
    assert "model_resolution" in data["checked_stages"]
    assert "normalization" in data["checked_stages"]
    assert "input_preparation" in data["checked_stages"]
    assert "model_execution" in data["checked_stages"]


def test_dry_run_with_fake_source_fails_at_container_resolution(monkeypatch):
    """Dry run with a fake source_id fails at container_resolution."""
    _enable_auth(monkeypatch)
    _install_test_registry_with_real_package_and_requirements()

    response = TestClient(create_fastapi_app()).post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={"container_id": "Nova_376.h5", "source_id": "fake-source-id-does-not-exist"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["validation"]["status"] == "failed"
    assert data["validation"]["ready_to_run"] is False
    assert data["validation"]["read_only"] is True
    assert data["failure_stage"] == "container_resolution"
    assert data["next_step"]["can_submit_job"] is False
    # Failure reason must be clean, single sentence — no duplication
    reason = data["next_step"]["reason"]
    assert "Selected container failed read-only pipeline dry run." in reason
    assert reason.count("failed") == 1, f"Duplicated 'failed' in reason: {reason!r}"
    # checked_stages must be a non-empty list
    assert isinstance(data["checked_stages"], list)
    assert "request_payload" in data["checked_stages"]
    assert "model_resolution" in data["checked_stages"]
    assert "container_resolution" in data["checked_stages"]


def test_dry_run_does_not_create_job(tmp_path, monkeypatch):
    """Dry run does not create any persistent job state."""
    _enable_auth(monkeypatch)
    _install_test_registry_with_real_package_and_requirements()

    h5_path = _create_real_h5_file(tmp_path)
    source_id = _register_source_for_test(h5_path, "Nova_376.h5")

    from bremen.api import model_requirements as _mr
    monkeypatch.setattr(_mr, "_resolve_source_for_dry_run", lambda sid: h5_path)

    from bremen.api.job_api_handler import _jobs, _jobs_lock
    with _jobs_lock:
        before = set(_jobs)

    response = TestClient(create_fastapi_app()).post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={"container_id": "Nova_376.h5", "source_id": source_id},
    )

    assert response.status_code == 200
    with _jobs_lock:
        after = set(_jobs)
    assert after == before
    assert response.json()["validation"]["inference_job_created"] is False
    assert response.json()["validation"]["report_created"] is False


def test_dry_run_does_not_expose_h5_path(tmp_path, monkeypatch):
    """Dry run response must not contain raw h5_path."""
    _enable_auth(monkeypatch)
    _install_test_registry_with_real_package_and_requirements()

    h5_path = _create_real_h5_file(tmp_path)
    source_id = _register_source_for_test(h5_path, "Nova_376.h5")

    from bremen.api import model_requirements as _mr
    monkeypatch.setattr(_mr, "_resolve_source_for_dry_run", lambda sid: h5_path)

    response = TestClient(create_fastapi_app()).post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={"container_id": "Nova_376.h5", "source_id": source_id, "h5_path": "/secret/path.h5"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "h5_path" not in data
    assert data["h5_path_supplied"] is True
    assert h5_path not in str(data)
    assert "/secret/" not in str(data)


def test_dry_run_response_no_private_internals(tmp_path, monkeypatch):
    """Dry run response must not expose private internals."""
    _enable_auth(monkeypatch)
    _install_test_registry_with_real_package_and_requirements()

    h5_path = _create_real_h5_file(tmp_path)
    source_id = _register_source_for_test(h5_path, "Nova_376.h5")

    from bremen.api import model_requirements as _mr
    monkeypatch.setattr(_mr, "_resolve_source_for_dry_run", lambda sid: h5_path)

    response = TestClient(create_fastapi_app()).post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={"container_id": "Nova_376.h5", "source_id": source_id},
    )

    assert response.status_code == 200
    data = response.json()
    text = str(data)
    assert "_checksum" not in text
    assert "_package" not in text
    assert "portable_logreg" not in text
    assert "test-checksum" not in text
    assert "/Users/" not in text
    assert "s3://" not in text
    assert "boto" not in text.lower()
    assert "password" not in text.lower()
    assert "secret" not in text.lower()
    assert "traceback" not in text.lower()
    assert "exception" not in text.lower()


def test_api_models_still_does_not_expose_container_requirements(monkeypatch):
    """GET /api/models must not expose container_requirements."""
    _enable_auth(monkeypatch)
    _install_test_registry_with_real_package_and_requirements()

    response = TestClient(create_fastapi_app()).get(
        "/demo/api/models",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    data = response.json()
    # container_requirements must not appear in the public catalog
    models = data.get("models", [])
    for model in models:
        assert "container_requirements" not in model
        assert "_container_requirements" not in model


def test_aramina_workflow_id_remains_unavailable(monkeypatch):
    """workflow_id=aramina must not be runnable through the requirements endpoint."""
    _enable_auth(monkeypatch)
    reset_model_registry_for_tests()

    # Register an Aramina model entry with availability=unavailable
    entry = RegistryModelEntry(
        model_id="aramina-placeholder",
        display_name="Aramina",
        workflow_id="aramina",
        model_version="",
        artifact_type="portable_logreg",
        feature_schema_version="v0.1",
        decision_policy_id="bremen_mri_triage_policy",
        decision_policy_version="v0.1",
        technical_ready=False,
        scientifically_certified=False,
        technical_demo_only=True,
        availability="unavailable",
        _package=None,
        _checksum="",
    )
    initialize_registry(
        ModelRegistry(
            entries=(entry,),
            catalog_status="available",
            candidate_count=1,
            available_count=0,
            rejected_count=0,
            unavailable_count=1,
        )
    )

    # GET requirements should still work (shows no-op for unavailable model)
    response = TestClient(create_fastapi_app()).get(
        "/demo/api/models/aramina-placeholder/requirements",
        headers=_auth_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["workflow_id"] == "aramina"
    assert data["requirements_available"] is False

    # POST validate: no container_requirements → no-op (not_available)
    response = TestClient(create_fastapi_app()).post(
        "/demo/api/models/aramina-placeholder/requirements/validate",
        headers=_auth_headers(),
        json={"container_id": "test.h5", "source_id": "test-source"},
    )
    assert response.status_code == 200
    data = response.json()
    # No container_requirements → validation not available (no-op)
    assert data["validation"]["status"] == "not_available"
    assert data["validation"]["ready_to_run"] is None
    assert data["validation"]["dry_run_mode"] == "request_payload"
    assert data["validation"]["read_only"] is True
    # Key invariant: Aramina is NOT runnable
    assert data["validation"]["inference_job_created"] is False
    assert data["validation"]["report_created"] is False


# ---------------------------------------------------------------------------
# PR0127: Response polish and Nova_103-like failure tests
# ---------------------------------------------------------------------------


def test_failed_dry_run_reason_not_duplicated(monkeypatch):
    """Failure reason must be a clean single sentence with no duplication."""
    _enable_auth(monkeypatch)
    _install_test_registry_with_real_package_and_requirements()

    response = TestClient(create_fastapi_app()).post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={"container_id": "Nova_376.h5", "source_id": "nonexistent-source"},
    )

    assert response.status_code == 200
    data = response.json()
    reason = data["next_step"]["reason"]
    # Must be a clean single sentence
    assert "Selected container failed read-only pipeline dry run." in reason
    # No duplication of "failed"
    assert reason.count("failed") == 1, f"Duplicated 'failed' in reason: {reason!r}"
    # No trailing period duplication
    assert not reason.endswith(".."), f"Duplicated period in reason: {reason!r}"


def test_checked_stages_not_null_on_pass(tmp_path, monkeypatch):
    """checked_stages must be a non-empty list on successful dry run."""
    _enable_auth(monkeypatch)
    _install_test_registry_with_real_package_and_requirements()

    h5_path = _create_real_h5_file(tmp_path)
    source_id = _register_source_for_test(h5_path, "Nova_376.h5")

    from bremen.api import model_requirements as _mr
    monkeypatch.setattr(_mr, "_resolve_source_for_dry_run", lambda sid: h5_path)

    response = TestClient(create_fastapi_app()).post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={"container_id": "Nova_376.h5", "source_id": source_id},
    )

    assert response.status_code == 200
    data = response.json()
    # checked_stages must be a non-null, non-empty list
    assert data["checked_stages"] is not None
    assert isinstance(data["checked_stages"], list)
    assert len(data["checked_stages"]) > 0
    # Preferred stages for successful Bremen dry run
    expected_stages = [
        "request_payload",
        "model_resolution",
        "container_resolution",
        "normalization",
        "workflow_resolution",
        "input_preparation",
        "model_execution",
    ]
    for stage in expected_stages:
        assert stage in data["checked_stages"], f"Missing stage: {stage}"


def test_checked_stages_not_null_on_failure(monkeypatch):
    """checked_stages must be a non-empty list on failed dry run."""
    _enable_auth(monkeypatch)
    _install_test_registry_with_real_package_and_requirements()

    response = TestClient(create_fastapi_app()).post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={"container_id": "Nova_376.h5", "source_id": "nonexistent-source"},
    )

    assert response.status_code == 200
    data = response.json()
    # checked_stages must be a non-null list
    assert data["checked_stages"] is not None
    assert isinstance(data["checked_stages"], list)
    # For container_resolution failure: request_payload, model_resolution, container_resolution
    assert "request_payload" in data["checked_stages"]
    assert "model_resolution" in data["checked_stages"]
    assert "container_resolution" in data["checked_stages"]


def test_checked_stages_empty_when_no_manifest(monkeypatch):
    """When no manifest exists, checked_stages must be an empty list (not null)."""
    _enable_auth(monkeypatch)
    _install_test_registry()  # no container_requirements

    response = TestClient(create_fastapi_app()).post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={"container_id": "Nova_376.h5", "source_id": "fresh-source-id"},
    )

    assert response.status_code == 200
    data = response.json()
    # checked_stages must be an empty list, not null
    assert data["checked_stages"] is not None
    assert isinstance(data["checked_stages"], list)
    assert len(data["checked_stages"]) == 0


def test_nova_103_like_failure_maps_to_input_preparation(tmp_path, monkeypatch):
    """A container that fails compatibility check maps to input_preparation stage."""
    _enable_auth(monkeypatch)
    _install_test_registry_with_real_package_and_requirements()

    # Create an H5 with only LEFT side (incompatible — needs both sides)
    import h5py
    import numpy as np

    h5_path = str(tmp_path / "nova_103_like.h5")
    with h5py.File(h5_path, "w") as h5:
        rng = np.random.default_rng(42)
        q = np.linspace(2.0, 23.0, 100, dtype=np.float64)
        target = h5.create_group("/scans/target")
        target.create_dataset("measurements", data=rng.normal(1.0, 0.1, size=(1, 100)))
        target.create_dataset("q", data=q)
        target.attrs["side"] = "LEFT"
        # No contralateral — only one side → incompatible

    source_id = _register_source_for_test(h5_path, "Nova_103_.h5")

    from bremen.api import model_requirements as _mr
    monkeypatch.setattr(_mr, "_resolve_source_for_dry_run", lambda sid: h5_path)

    response = TestClient(create_fastapi_app()).post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={"container_id": "Nova_103_.h5", "source_id": source_id},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["validation"]["status"] == "failed"
    assert data["validation"]["ready_to_run"] is False
    assert data["validation"]["read_only"] is True
    assert data["validation"]["dry_run_mode"] == "model_pipeline"
    # Nova_103-like failure must map to input_preparation
    assert data["failure_stage"] == "input_preparation"
    assert data["next_step"]["can_submit_job"] is False
    # checked_stages must include stages up to the failure point
    assert "request_payload" in data["checked_stages"]
    assert "model_resolution" in data["checked_stages"]
    assert "container_resolution" in data["checked_stages"]
    assert "normalization" in data["checked_stages"]
    # workflow_resolution may or may not appear depending on failure timing
    # No inference/report artifacts
    assert data["validation"]["inference_job_created"] is False
    assert data["validation"]["report_created"] is False


def test_validate_does_not_create_inference_artifacts(tmp_path, monkeypatch):
    """Validate endpoint never creates inference jobs, reports, or artifacts."""
    _enable_auth(monkeypatch)
    _install_test_registry_with_real_package_and_requirements()

    h5_path = _create_real_h5_file(tmp_path)
    source_id = _register_source_for_test(h5_path, "Nova_376.h5")

    from bremen.api import model_requirements as _mr
    monkeypatch.setattr(_mr, "_resolve_source_for_dry_run", lambda sid: h5_path)

    from bremen.api.job_api_handler import _jobs, _jobs_lock
    with _jobs_lock:
        before_jobs = set(_jobs)

    response = TestClient(create_fastapi_app()).post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={"container_id": "Nova_376.h5", "source_id": source_id},
    )

    assert response.status_code == 200
    data = response.json()

    # No jobs created
    with _jobs_lock:
        after_jobs = set(_jobs)
    assert after_jobs == before_jobs

    # Validation explicitly confirms no artifacts
    assert data["validation"]["inference_job_created"] is False
    assert data["validation"]["report_created"] is False
    assert data["validation"]["read_only"] is True
    assert data["validation"]["dry_run_mode"] == "model_pipeline"
    assert data["validation"]["ready_to_run"] is True


def test_no_raw_paths_or_checksum_in_dry_run_response(tmp_path, monkeypatch):
    """Dry run response must not expose raw paths, S3, checksums, or tokens."""
    _enable_auth(monkeypatch)
    _install_test_registry_with_real_package_and_requirements()

    h5_path = _create_real_h5_file(tmp_path)
    source_id = _register_source_for_test(h5_path, "Nova_376.h5")

    from bremen.api import model_requirements as _mr
    monkeypatch.setattr(_mr, "_resolve_source_for_dry_run", lambda sid: h5_path)

    response = TestClient(create_fastapi_app()).post(
        "/demo/api/models/bremen-mri-triage-logreg-v0-1/requirements/validate",
        headers=_auth_headers(),
        json={"container_id": "Nova_376.h5", "source_id": source_id},
    )

    assert response.status_code == 200
    data = response.json()
    text = str(data)
    assert "_checksum" not in text
    assert "_package" not in text
    assert "portable_logreg" not in text
    assert "test-checksum" not in text
    assert "/Users/" not in text
    assert "s3://" not in text
    assert "boto" not in text.lower()
    assert "password" not in text.lower()
    assert "secret" not in text.lower()
    assert "token" not in text.lower()
    assert "traceback" not in text.lower()
    assert "exception" not in text.lower()
