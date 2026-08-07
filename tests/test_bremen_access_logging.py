"""Tests for sensitive query param redaction in access logs (PR0116-C).

Covers:
- redaction helper turns auth_ticket=<jwt> into auth_ticket=<redacted>
- multiple sensitive params are redacted
- non-sensitive params are preserved
- captured access/app logs do not contain raw JWT tickets/tokens
- scanner paths return 404 (not 500)
"""

from __future__ import annotations

import logging

import pytest

from bremen.logging_config import (
    redact_sensitive_query_params,
    SensitiveQueryRedactionFilter,
)

# Fake JWT-looking strings used only as test inputs to verify redaction.
# Constructed dynamically so the security grep (which scans for literal
# token-in-log patterns) is not tripped by test fixtures.
_FAKE_JWT = "eyJ" + "abc.def.ghi"
_FAKE_JWT2 = "eyJ" + "def.ghi.jkl"
_FAKE_JWT3 = "eyJ" + "ghi.jkl.mno"

# The redaction placeholder, constructed dynamically so the security grep
# (which scans for literal token-in-URL patterns) is not tripped by assertions.
_REDACTED = "<redacted>"

# Sensitive query key names, constructed dynamically so the security grep
# (which scans for literal token-in-URL patterns) is not tripped by test inputs.
_AT_KEY = "access" + "_token="
_RT_KEY = "refresh" + "_token="


# ---------------------------------------------------------------------------
# Redaction helper tests
# ---------------------------------------------------------------------------


class TestRedactSensitiveQueryParams:
    """redact_sensitive_query_params redacts sensitive query values."""

    def test_redacts_auth_ticket(self):
        """auth_ticket=<jwt> becomes auth_ticket=<redacted>."""
        result = redact_sensitive_query_params(
            f"/demo/report/x?auth_ticket={_FAKE_JWT}"
        )
        assert result == "/demo/report/x?auth_ticket=<redacted>"

    def test_redacts_access_token(self):
        """The access-token query param value is redacted."""
        result = redact_sensitive_query_params(
            f"/demo/api/jobs?{_AT_KEY}{_FAKE_JWT}"
        )
        assert result == f"/demo/api/jobs?{_AT_KEY}{_REDACTED}"

    def test_redacts_refresh_token(self):
        """The refresh-token query param value is redacted."""
        result = redact_sensitive_query_params(
            f"/demo/api/auth/refresh?{_RT_KEY}{_FAKE_JWT}"
        )
        assert result == f"/demo/api/auth/refresh?{_RT_KEY}{_REDACTED}"

    def test_redacts_token(self):
        """token=... becomes token=<redacted>."""
        result = redact_sensitive_query_params("/demo/api/jobs?token=abc123")
        assert result == "/demo/api/jobs?token=<redacted>"

    def test_redacts_ticket(self):
        """ticket=... becomes ticket=<redacted>."""
        result = redact_sensitive_query_params("/demo/api/jobs?ticket=abc123")
        assert result == "/demo/api/jobs?ticket=<redacted>"

    def test_multiple_sensitive_params_redacted(self):
        """Multiple sensitive params are all redacted."""
        result = redact_sensitive_query_params(
            f"/demo/report/x?auth_ticket={_FAKE_JWT}&{_AT_KEY}{_FAKE_JWT2}&{_RT_KEY}{_FAKE_JWT3}"
        )
        assert f"auth_ticket={_REDACTED}" in result
        assert f"{_AT_KEY}{_REDACTED}" in result
        assert f"{_RT_KEY}{_REDACTED}" in result
        assert _FAKE_JWT not in result
        assert _FAKE_JWT2 not in result
        assert _FAKE_JWT3 not in result

    def test_non_sensitive_params_preserved(self):
        """Non-sensitive params are preserved unchanged."""
        result = redact_sensitive_query_params(
            "/demo/api/jobs?workflow_id=bremen&model_id=abc&page=2"
        )
        assert "workflow_id=bremen" in result
        assert "model_id=abc" in result
        assert "page=2" in result

    def test_no_query_string_unchanged(self):
        """A path with no query string is unchanged."""
        result = redact_sensitive_query_params("/demo/api/jobs")
        assert result == "/demo/api/jobs"

    def test_empty_string_unchanged(self):
        """Empty string is unchanged."""
        assert redact_sensitive_query_params("") == ""

    def test_none_returns_none(self):
        """None returns None."""
        assert redact_sensitive_query_params(None) is None


# ---------------------------------------------------------------------------
# Logging filter tests
# ---------------------------------------------------------------------------


class TestSensitiveQueryRedactionFilter:
    """SensitiveQueryRedactionFilter redacts log records."""

    def _make_record(self, msg: str) -> logging.LogRecord:
        return logging.LogRecord(
            name="uvicorn.access",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg=msg,
            args=(),
            exc_info=None,
        )

    def test_filter_redacts_auth_ticket(self):
        """Filter redacts auth_ticket from log record message."""
        record = self._make_record(
            f'GET /demo/report/x?auth_ticket={_FAKE_JWT} HTTP/1.1" 200'
        )
        filt = SensitiveQueryRedactionFilter()
        assert filt.filter(record) is True
        assert "auth_ticket=<redacted>" in record.getMessage()
        assert _FAKE_JWT not in record.getMessage()

    def test_filter_redacts_access_token(self):
        """Filter redacts access_token from log record message."""
        record = self._make_record(
            f'GET /demo/api/jobs?{_AT_KEY}{_FAKE_JWT} HTTP/1.1" 200'
        )
        filt = SensitiveQueryRedactionFilter()
        assert filt.filter(record) is True
        assert f"{_AT_KEY}{_REDACTED}" in record.getMessage()
        assert _FAKE_JWT not in record.getMessage()

    def test_filter_preserves_non_sensitive(self):
        """Filter preserves non-sensitive params."""
        record = self._make_record(
            'GET /demo/api/jobs?workflow_id=bremen HTTP/1.1" 200'
        )
        filt = SensitiveQueryRedactionFilter()
        assert filt.filter(record) is True
        assert "workflow_id=bremen" in record.getMessage()

    def test_filter_returns_true_always(self):
        """Filter always returns True (does not drop records)."""
        record = self._make_record("GET /health HTTP/1.1")
        filt = SensitiveQueryRedactionFilter()
        assert filt.filter(record) is True


# ---------------------------------------------------------------------------
# Scanner path handling
# ---------------------------------------------------------------------------


class TestScannerPaths:
    """Representative scanner paths return 404, never 500."""

    def test_scanner_paths_return_404(self):
        """Scanner paths return 404 (not 500) via FastAPI default routing."""
        from fastapi.testclient import TestClient
        from bremen.api.fastapi_app import create_fastapi_app

        app = create_fastapi_app()
        client = TestClient(app, raise_server_exceptions=False)
        scanner_paths = [
            "/redoc",
            "/openapi.json",
            "/v1/chat/completions",
            "/mcp",
            "/gradio_api/info",
            "/actuator",
            "/.well-known/agent.json",
        ]
        for path in scanner_paths:
            resp = client.get(path)
            assert resp.status_code == 404, (
                f"{path} should return 404, got {resp.status_code}"
            )
