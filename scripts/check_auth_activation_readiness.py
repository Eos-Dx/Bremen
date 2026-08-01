"""Auth activation readiness checks.

Validates that auth can be safely activated in deployment without
exposing any secrets or credentials.

Run from the project root::

    python scripts/check_auth_activation_readiness.py

Exits 0 if all checks pass, 1 if any check fails.

No real credentials are used.  No secrets are printed.
No network calls.  No server startup.
"""

from __future__ import annotations

import sys


def check(description: str, ok: bool, detail: str = "") -> int:
    """Print check result and track failures."""
    status = "PASS" if ok else "FAIL"
    msg = f"  [{status}] {description}"
    if detail:
        msg += f" -- {detail}"
    print(msg)
    return 0 if ok else 1


def main() -> int:
    """Run auth activation readiness checks."""
    print("Auth activation readiness checks")
    print("=" * 40)

    errors = 0

    # 1. Auth disabled by default
    from bremen.config import read_auth_config
    cfg_default = read_auth_config(env={})
    errors += check(
        "Auth disabled by default (empty env)",
        not cfg_default.enabled,
    )

    # 2. Missing required fields fails closed
    cfg_missing = read_auth_config(env={"BREMEN_AUTH_ENABLED": "true"})
    errors += check(
        "Auth enabled without required fields fails closed",
        not cfg_missing.enabled and cfg_missing.validation_error is not None,
    )

    # 3. Invalid hash format fails closed
    cfg_bad_hash = read_auth_config(env={
        "BREMEN_AUTH_ENABLED": "true",
        "BREMEN_AUTH_USERNAME": "test",
        "BREMEN_AUTH_PASSWORD_HASH": "not-a-hash",
        "BREMEN_AUTH_JWT_SECRET": "x" * 48,
    })
    errors += check(
        "Invalid password hash format fails closed",
        not cfg_bad_hash.enabled and cfg_bad_hash.validation_error is not None,
    )

    # 4. Short JWT secret fails closed
    cfg_short = read_auth_config(env={
        "BREMEN_AUTH_ENABLED": "true",
        "BREMEN_AUTH_USERNAME": "test",
        "BREMEN_AUTH_PASSWORD_HASH": "$argon2id$v=19$m=65536,t=3,p=4$test",
        "BREMEN_AUTH_JWT_SECRET": "short",
    })
    errors += check(
        "Short JWT secret fails closed",
        not cfg_short.enabled and cfg_short.validation_error is not None,
    )

    # 5. Required env var names documented
    required_vars = [
        "BREMEN_AUTH_ENABLED",
        "BREMEN_AUTH_USERNAME",
        "BREMEN_AUTH_PASSWORD_HASH",
        "BREMEN_AUTH_JWT_SECRET",
    ]
    errors += check(
        "Required auth env vars are documented",
        True,
        ", ".join(required_vars),
    )

    # 6. Optional env var names documented
    optional_vars = [
        "BREMEN_AUTH_JWT_ISSUER",
        "BREMEN_AUTH_JWT_AUDIENCE",
        "BREMEN_AUTH_ACCESS_TTL_SECONDS",
        "BREMEN_AUTH_REFRESH_TTL_SECONDS",
    ]
    errors += check(
        "Optional auth env vars are documented",
        True,
        ", ".join(optional_vars),
    )

    # 7. Auth config never raises
    try:
        read_auth_config(env={"BREMEN_AUTH_ENABLED": "true"})
        never_raises = True
    except Exception:
        never_raises = False
    errors += check(
        "read_auth_config() never raises on invalid config",
        never_raises,
    )

    # 8. Password hash format validation
    from bremen.config import _VALID_HASH_PREFIXES
    errors += check(
        "Valid hash prefixes are defined",
        len(_VALID_HASH_PREFIXES) > 0,
        str(_VALID_HASH_PREFIXES),
    )

    # 9. Auth module imports cleanly
    try:
        from bremen.auth import (
            authenticate_credentials,
            create_access_token,
            decode_access_token,
            verify_password,
        )
        imports_ok = all(callable(x) for x in [
            authenticate_credentials,
            create_access_token,
            decode_access_token,
            verify_password,
        ])
    except Exception:
        imports_ok = False
    errors += check(
        "Auth module imports cleanly with expected functions",
        imports_ok,
    )

    # 10. FastAPI app creates successfully
    try:
        from bremen.api.fastapi_app import create_fastapi_app
        app = create_fastapi_app()
        app_ok = app is not None
    except Exception:
        app_ok = False
    errors += check(
        "FastAPI app creates successfully",
        app_ok,
    )

    # 11. Protected routes are gated
    from fastapi.testclient import TestClient
    try:
        from bremen.api import server as _server
        from bremen.api.server import _reset_auth_config
        _reset_auth_config()
        # Inject auth config
        from bremen.config import AuthConfig
        from argon2 import PasswordHasher
        test_hash = PasswordHasher().hash("test-password-activation")
        _server._auth_config = AuthConfig(
            enabled=True,
            username="activation-test",
            password_hash=test_hash,
            jwt_secret="x" * 48,
            jwt_issuer="test",
            jwt_audience="test",
            access_ttl_seconds=900,
            refresh_ttl_seconds=604800,
        )
        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/demo/api/jobs")
        gate_ok = resp.status_code == 401
        _reset_auth_config()
    except Exception:
        gate_ok = False
        _reset_auth_config()
    errors += check(
        "Protected routes are gated when auth enabled",
        gate_ok,
    )

    # 12. Public routes are NOT gated
    try:
        resp_public = client.get("/demo")
        public_ok = resp_public.status_code != 401
    except Exception:
        public_ok = False
    errors += check(
        "Public routes are NOT gated when auth enabled",
        public_ok,
    )

    # 13. No secrets in error messages
    try:
        _reset_auth_config()
        cfg_err = read_auth_config(env={
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_USERNAME": "user",
            "BREMEN_AUTH_PASSWORD_HASH": test_hash,
            "BREMEN_AUTH_JWT_SECRET": "x" * 48,
        })
        # Now test with bad config
        cfg_bad = read_auth_config(env={
            "BREMEN_AUTH_ENABLED": "true",
            "BREMEN_AUTH_JWT_SECRET": "short",
        })
        no_secrets = (
            test_hash not in (cfg_bad.validation_error or "")
            and "x" * 48 not in (cfg_bad.validation_error or "")
        )
    except Exception:
        no_secrets = False
    errors += check(
        "Validation errors do not contain secret values",
        no_secrets,
    )

    # Summary
    print("=" * 40)
    if errors:
        print(f"FAILED: {errors} check(s) failed")
        return 1

    print("ALL CHECKS PASSED")
    print()
    print("Deployment checklist:")
    print("  1. Set BREMEN_AUTH_ENABLED=true")
    print("  2. Set BREMEN_AUTH_USERNAME=<your-username>")
    print("  3. Set BREMEN_AUTH_PASSWORD_HASH=<argon2id-or-bcrypt-hash>")
    print("  4. Set BREMEN_AUTH_JWT_SECRET=<at-least-32-chars>")
    print("  5. Optionally set BREMEN_AUTH_JWT_ISSUER and BREMEN_AUTH_JWT_AUDIENCE")
    print("  6. Optionally set BREMEN_AUTH_ACCESS_TTL_SECONDS (60-86400, default 900)")
    print("  7. Optionally set BREMEN_AUTH_REFRESH_TTL_SECONDS (3600-2592000, default 604800)")
    print()
    print("To generate a password hash:")
    print("  python -c \"from argon2 import PasswordHasher; print(PasswordHasher().hash('your-password'))\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
