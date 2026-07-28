"""Tests for Bremen API Documentation Page — PR0100."""

from bremen.api_docs_ui import build_api_docs_page


class TestPR0100ApiDocsRoute:
    """PR0100: API docs route exists and serves correct content."""

    def test_api_docs_page_builds(self):
        """build_api_docs_page returns a non-empty HTML page."""
        page = build_api_docs_page()
        assert len(page) > 1000
        assert '<!DOCTYPE html>' in page

    def test_api_docs_page_title(self):
        """Page title references API documentation."""
        page = build_api_docs_page()
        assert 'Bremen API Documentation' in page

    def test_api_docs_has_nav_links(self):
        """Page has navigation links to Start, Control Room, Workspace."""
        page = build_api_docs_page()
        assert 'href="/demo"' in page
        assert 'href="/demo/control-room"' in page
        assert 'href="/demo/workspace"' in page


class TestPR0100AuthModelDocumented:
    """PR0100: Authentication model is documented."""

    def test_bearer_authentication_documented(self):
        """Page documents Bearer authentication."""
        page = build_api_docs_page()
        assert 'Bearer' in page
        assert 'Authorization: Bearer' in page

    def test_jwt_access_token_documented(self):
        """Page documents JWT access tokens."""
        page = build_api_docs_page()
        assert 'JWT' in page
        assert 'access_token' in page

    def test_refresh_token_documented(self):
        """Page documents refresh tokens."""
        page = build_api_docs_page()
        assert 'refresh_token' in page
        assert 'Refresh Endpoint' in page or 'Refresh endpoint' in page

    def test_short_ttl_documented(self):
        """Page documents short access token TTL (15 minutes)."""
        page = build_api_docs_page()
        assert '15 minutes' in page
        assert '900' in page

    def test_long_refresh_ttl_documented(self):
        """Page documents longer refresh token TTL (7 days)."""
        page = build_api_docs_page()
        assert '7 days' in page
        assert '604800' in page


class TestPR0100EnvCredentialsDocumented:
    """PR0100: Environment credential variables documented."""

    def test_auth_enabled_env_var(self):
        """Page documents BREMEN_AUTH_ENABLED."""
        page = build_api_docs_page()
        assert 'BREMEN_AUTH_ENABLED' in page

    def test_auth_username_env_var(self):
        """Page documents BREMEN_AUTH_USERNAME."""
        page = build_api_docs_page()
        assert 'BREMEN_AUTH_USERNAME' in page

    def test_auth_password_hash_env_var(self):
        """Page documents BREMEN_AUTH_PASSWORD_HASH."""
        page = build_api_docs_page()
        assert 'BREMEN_AUTH_PASSWORD_HASH' in page

    def test_jwt_secret_env_var(self):
        """Page documents BREMEN_AUTH_JWT_SECRET."""
        page = build_api_docs_page()
        assert 'BREMEN_AUTH_JWT_SECRET' in page

    def test_jwt_issuer_env_var(self):
        """Page documents BREMEN_AUTH_JWT_ISSUER."""
        page = build_api_docs_page()
        assert 'BREMEN_AUTH_JWT_ISSUER' in page

    def test_jwt_audience_env_var(self):
        """Page documents BREMEN_AUTH_JWT_AUDIENCE."""
        page = build_api_docs_page()
        assert 'BREMEN_AUTH_JWT_AUDIENCE' in page

    def test_jwt_access_ttl_env_var(self):
        """Page documents BREMEN_AUTH_ACCESS_TTL_SECONDS."""
        page = build_api_docs_page()
        assert 'BREMEN_AUTH_ACCESS_TTL_SECONDS' in page

    def test_jwt_refresh_ttl_env_var(self):
        """Page documents BREMEN_AUTH_REFRESH_TTL_SECONDS."""
        page = build_api_docs_page()
        assert 'BREMEN_AUTH_REFRESH_TTL_SECONDS' in page

    def test_password_hash_recommended(self):
        """Page recommends password hash rather than plaintext."""
        page = build_api_docs_page()
        assert 'password hash' in page.lower() or 'password_hash' in page.lower()
        assert 'not plaintext' in page.lower() or 'not a plaintext' in page.lower() or 'Store password hash' in page

    def test_no_default_credentials_in_repo(self):
        """Page says no default credentials in repository."""
        page = build_api_docs_page()
        assert 'No default credentials in repository' in page

    def test_no_credentials_in_frontend(self):
        """Page says no credentials in frontend JavaScript."""
        page = build_api_docs_page()
        assert 'No credentials in frontend JavaScript' in page

    def test_no_credentials_in_logs(self):
        """Page says no credentials in logs."""
        page = build_api_docs_page()
        assert 'No credentials in logs' in page

    def test_auth_fails_closed(self):
        """Page documents that auth fails closed if env vars missing."""
        page = build_api_docs_page()
        assert 'fails closed' in page


class TestPR0100EndpointGroupsDocumented:
    """PR0100: Safe API endpoint groups documented."""

    def test_token_endpoint_documented(self):
        """Page documents planned POST /api/auth/token."""
        page = build_api_docs_page()
        assert '/api/auth/token' in page

    def test_refresh_endpoint_documented(self):
        """Page documents planned POST /api/auth/refresh."""
        page = build_api_docs_page()
        assert '/api/auth/refresh' in page

    def test_models_endpoint_documented(self):
        """Page documents GET /api/models."""
        page = build_api_docs_page()
        assert '/api/models' in page

    def test_patients_endpoint_documented(self):
        """Page documents GET /api/patients."""
        page = build_api_docs_page()
        assert '/api/patients' in page

    def test_jobs_endpoint_documented(self):
        """Page documents POST and GET /api/jobs."""
        page = build_api_docs_page()
        assert '/api/jobs' in page

    def test_reports_endpoint_documented(self):
        """Page documents GET /api/reports."""
        page = build_api_docs_page()
        assert '/api/reports' in page


class TestPR0100ForbiddenExposures:
    """PR0100: Forbidden exposure items documented."""

    def test_no_raw_s3_bucket_names(self):
        """Page documents that raw S3 bucket names must not be exposed."""
        page = build_api_docs_page()
        assert 'S3 bucket names' in page

    def test_no_raw_s3_object_keys(self):
        """Page documents that raw S3 object keys must not be exposed."""
        page = build_api_docs_page()
        assert 'S3 object keys' in page

    def test_no_filesystem_paths(self):
        """Page documents that filesystem paths must not be exposed."""
        page = build_api_docs_page()
        assert 'Filesystem paths' in page or 'filesystem paths' in page

    def test_no_raw_h5_internals(self):
        """Page documents that raw H5 internals must not be exposed."""
        page = build_api_docs_page()
        assert 'H5 internals' in page

    def test_no_phi(self):
        """Page documents that PHI must not be exposed."""
        page = build_api_docs_page()
        assert 'PHI' in page

    def test_no_raw_exception_traces(self):
        """Page documents that raw exception traces must not be exposed."""
        page = build_api_docs_page()
        assert 'exception traces' in page

    def test_no_model_coefficients(self):
        """Page documents that model coefficients must not be exposed."""
        page = build_api_docs_page()
        assert 'Model coefficients' in page or 'model coefficients' in page

    def test_no_feature_values(self):
        """Page documents that feature values must not be exposed."""
        page = build_api_docs_page()
        assert 'Feature values' in page or 'feature values' in page

    def test_no_credentials_exposed(self):
        """Page documents that credentials must not be exposed."""
        page = build_api_docs_page()
        assert 'Credentials' in page or 'credentials' in page

    def test_no_jwt_secrets_exposed(self):
        """Page documents that JWT secrets must not be exposed."""
        page = build_api_docs_page()
        assert 'JWT secrets' in page


class TestPR0100AllowedSafeFields:
    """PR0100: Allowed safe identifiers documented."""

    def test_job_id_allowed(self):
        """Page documents job_id as allowed safe field."""
        page = build_api_docs_page()
        assert 'job_id' in page

    def test_model_id_allowed(self):
        """Page documents model_id as allowed safe field."""
        page = build_api_docs_page()
        assert 'model_id' in page

    def test_workflow_id_allowed(self):
        """Page documents workflow_id as allowed safe field."""
        page = build_api_docs_page()
        assert 'workflow_id' in page

    def test_opaque_source_ids_allowed(self):
        """Page documents opaque source IDs as allowed."""
        page = build_api_docs_page()
        assert 'Opaque source' in page or 'opaque source' in page

    def test_stable_source_key_allowed(self):
        """Page documents stable_source_key as allowed."""
        page = build_api_docs_page()
        assert 'stable_source_key' in page


class TestPR0100PlannedVsImplemented:
    """PR0100: Auth enforcement clearly marked as planned."""

    def test_auth_enforcement_marked_planned(self):
        """Page clearly marks auth enforcement as planned."""
        page = build_api_docs_page()
        assert 'Planned' in page or 'planned' in page

    def test_enforcement_follow_up_noted(self):
        """Page notes enforcement in follow-up PR."""
        page = build_api_docs_page()
        assert 'follow-up PR' in page

    def test_no_auth_enforcement_implemented(self):
        """Page does not claim auth is already active."""
        page = build_api_docs_page()
        # Should not say "Authentication is active" or "enforced"
        lower = page.lower()
        assert 'authentication is active' not in lower
        assert 'auth is enforced' not in lower


class TestPR0100SafetyDisclaimer:
    """PR0100: Technical demo disclaimer preserved."""

    def test_technical_demo_only(self):
        """Page states technical demo only."""
        page = build_api_docs_page()
        assert 'Technical demo only' in page or 'technical demo only' in page

    def test_not_clinically_validated(self):
        """Page states not clinically validated."""
        page = build_api_docs_page()
        assert 'Not clinically validated' in page or 'not clinically validated' in page

    def test_not_a_diagnosis(self):
        """Page states not a diagnosis."""
        page = build_api_docs_page()
        assert 'Not a diagnosis' in page or 'not a diagnosis' in page

    def test_does_not_replace_clinical_judgment(self):
        """Page states does not replace clinical judgment."""
        page = build_api_docs_page()
        assert 'clinician' in page or 'clinical judgment' in page


class TestPR0100NoSecretsOrDefaults:
    """PR0100: No actual secrets or default credentials present."""

    def test_no_real_credentials(self):
        """Page contains no real credentials or default passwords."""
        page = build_api_docs_page()
        lower = page.lower()
        assert 'demo-password' not in lower
        assert 'changeme' not in lower
        assert 'secret123' not in lower
        assert 'password123' not in lower
        assert 'admin:admin' not in lower

    def test_no_real_jwt_secret(self):
        """Page contains no real JWT signing secret."""
        page = build_api_docs_page()
        # Should only have placeholder syntax, not actual secret values
        assert 'BREMEN_AUTH_JWT_SECRET' in page
        # Should not have a hardcoded secret value
        assert 'secret-key-' not in page.lower()
        assert 'my-secret' not in page.lower()


class TestPR0100FutureHardening:
    """PR0100: Future production hardening documented."""

    def test_database_backed_users_mentioned(self):
        """Page mentions future database-backed user management."""
        page = build_api_docs_page()
        assert 'Database-backed user management' in page or 'database-backed user' in page

    def test_roles_scopes_mentioned(self):
        """Page mentions future per-user roles and scopes."""
        page = build_api_docs_page()
        assert 'roles' in page

    def test_token_revocation_mentioned(self):
        """Page mentions future token revocation."""
        page = build_api_docs_page()
        assert 'revocation' in page or 'revoke' in page

    def test_secret_rotation_mentioned(self):
        """Page mentions future JWT signing secret rotation."""
        page = build_api_docs_page()
        assert 'Rotation' in page or 'rotation' in page


class TestPR0100ControlRoomNavLink:
    """PR0100: API docs link added to Control Room navigation."""

    def test_api_docs_link_in_control_room(self):
        """Control Room has API docs link."""
        from bremen.control_room_ui import build_control_room_page
        page = build_control_room_page()
        assert '/demo/api-docs' in page
        assert 'API docs' in page

    def test_api_docs_link_in_header(self):
        """API docs link appears in header area."""
        from bremen.control_room_ui import build_control_room_page
        page = build_control_room_page()
        # Find the actual HTML header-right div (not CSS)
        header_start = page.find('<div class="cr-header-right">')
        header_end = page.find('</div>', header_start + 20)
        header_section = page[header_start:header_end]
        assert 'api-docs' in header_section


class TestPR0100NoDependencies:
    """PR0100: No new dependencies added."""

    def test_no_new_imports_in_api_docs_ui(self):
        """api_docs_ui.py has no external library imports."""
        import inspect
        from bremen import api_docs_ui
        src = inspect.getsource(api_docs_ui)
        # Should not import any third-party libraries
        assert 'import requests' not in src
        assert 'import flask' not in src
        assert 'import fastapi' not in src
        assert 'import jwt' not in src
        assert 'import bcrypt' not in src


class TestPR0100ArchitectureDecisions:
    """PR0100: Authentication architecture decisions section exists and is complete."""

    def test_architecture_section_exists(self):
        """Page contains 'Authentication Architecture Decisions' section."""
        page = build_api_docs_page()
        assert 'Authentication Architecture Decisions' in page

    def test_confirmed_current_state(self):
        """Page confirms current /demo/* routes are unauthenticated."""
        page = build_api_docs_page()
        assert 'unauthenticated' in page

    def test_no_jwt_dependency_currently(self):
        """Page states no JWT/password hashing dependency is currently present."""
        page = build_api_docs_page()
        assert 'No JWT' in page or 'no JWT' in page
        assert 'No dependencies' in page or 'no dependencies' in page or 'dependency is currently present' in page

    def test_open_decision_1_auth_scope(self):
        """Page documents Open Decision 1: auth gates actions only."""
        page = build_api_docs_page()
        assert 'Open Decision 1' in page
        assert 'Auth gates actions only' in page

    def test_open_decision_1_no_fuller_view(self):
        """Page states no raw data unlocked by login."""
        page = build_api_docs_page()
        assert 'not unlocked by login' in page.lower() or 'are unlocked by login' in page

    def test_open_decision_2_credential_source(self):
        """Page documents Open Decision 2: single demo credential from env."""
        page = build_api_docs_page()
        assert 'Open Decision 2' in page

    def test_open_decision_2_password_hash(self):
        """Page states password must be stored as hash, not plaintext."""
        page = build_api_docs_page()
        assert 'Open Decision 2' in page
        # Already tested in test_password_hash_recommended

    def test_open_decision_2_jwt_secret_distinct(self):
        """Page states JWT secret must be distinct from password hash."""
        page = build_api_docs_page()
        assert 'distinct from the password hash' in page

    def test_open_decision_3_refresh_storage(self):
        """Page documents Open Decision 3: refresh-token storage options."""
        page = build_api_docs_page()
        assert 'Open Decision 3' in page

    def test_open_decision_3_options_listed(self):
        """Page lists all three refresh storage options."""
        page = build_api_docs_page()
        assert 'In-memory store' in page
        assert 'Stateless refresh JWT' in page
        assert 'Persistent store' in page

    def test_open_decision_3_stateless_default(self):
        """Page recommends stateless refresh JWT as demo default."""
        page = build_api_docs_page()
        assert 'Stateless refresh JWT' in page
        assert 'no-server-side-revocation' in page or 'server-side revocation is not' in page

    def test_jwt_mechanics_section(self):
        """Page documents JWT mechanics: PyJWT, HS256, claims."""
        page = build_api_docs_page()
        assert 'PyJWT' in page
        assert 'HS256' in page

    def test_jwt_claims_documented(self):
        """Page documents planned JWT claims."""
        page = build_api_docs_page()
        assert 'token_type' in page
        # sub, iat, exp, iss, aud should be in claims list
        assert 'sub' in page
        assert 'iat' in page
        assert 'exp' in page

    def test_jwt_decode_algorithm_safety(self):
        """Page states decode must not trust token header algorithm."""
        page = build_api_docs_page()
        assert 'must not trust token header algorithm' in page

    def test_safety_invariant(self):
        """Page states authentication does not expand data visibility."""
        page = build_api_docs_page()
        assert 'does not by itself expand data visibility' in page

    def test_fuller_view_requires_separate_pr(self):
        """Page states fuller authenticated view requires separate PR."""
        page = build_api_docs_page()
        assert 'separate PR and safety review' in page

    def test_planning_status_all_planned(self):
        """Page marks every auth endpoint as planned/follow-up."""
        page = build_api_docs_page()
        assert 'Every auth endpoint' in page or 'every auth endpoint' in page
        assert 'Auth is not active' in page or 'auth is not active' in page

    def test_no_auth_active_claim(self):
        """Page does not claim auth is active."""
        page = build_api_docs_page()
        lower = page.lower()
        assert 'authentication is active' not in lower
        assert 'auth is enforced' not in lower

    def test_fuller_view_requires_safety_review(self):
        """Any future fuller view requires its own safety review."""
        page = build_api_docs_page()
        assert 'safety review' in page
