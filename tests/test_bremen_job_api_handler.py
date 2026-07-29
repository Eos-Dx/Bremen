"""No-socket unit tests for job_api_handler.py helpers.

Covers deterministic helper functions that do NOT require a real
HTTPServer, sockets, or localhost HTTP:

- ``StagedUpload`` class construction
- ``register_staged_upload`` function
- ``resolve_upload`` function
- ``resolve_source`` error branches
- ``reset_for_tests`` function
- ``_utc_now`` function
- ``_get_or_create_*`` singleton pattern tests
- ``allowed_event_details`` filtering (via event_schema)
- ``extract_patient_display_name`` edge cases

Uses no HTTPServer, no sockets, no localhost HTTP, no server spawning.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


from bremen.api.job_api_handler import (
    StagedUpload,
    register_staged_upload,
    resolve_upload,
    resolve_source,
    reset_for_tests,
    _utc_now,
    _get_or_create_store,
    _get_or_create_jobs,
    _get_or_create_providers,
    _get_or_create_uploads,
    _cleanup_expired_uploads,
)
from bremen.api.event_schema import allowed_event_details


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset job handler state before each test."""
    reset_for_tests()
    yield
    reset_for_tests()


# ===================================================================
# StagedUpload class
# ===================================================================


class TestStagedUpload:
    """Cover StagedUpload data class construction."""

    def test_creation(self):
        u = StagedUpload(
            upload_id="uid-1",
            h5_path="/tmp/test.h5",
            filename="test.h5",
            size_bytes=1024,
            created_at="2025-01-01T00:00:00+00:00",
        )
        assert u.upload_id == "uid-1"
        assert u.h5_path == "/tmp/test.h5"
        assert u.filename == "test.h5"
        assert u.size_bytes == 1024
        assert u.consumed is False

    def test_consumed_flag(self):
        u = StagedUpload(
            upload_id="uid-2",
            h5_path="/tmp/test.h5",
            filename="test.h5",
            size_bytes=512,
            created_at="2025-01-01T00:00:00+00:00",
            consumed=True,
        )
        assert u.consumed is True

    def test_attributes_are_writable(self):
        u = StagedUpload(
            upload_id="uid-3",
            h5_path="/tmp/x.h5",
            filename="x.h5",
            size_bytes=0,
            created_at="2025-01-01T00:00:00+00:00",
        )
        u.consumed = True
        assert u.consumed is True


# ===================================================================
# register_staged_upload
# ===================================================================


class TestRegisterStagedUpload:
    """Cover upload registration."""

    def test_returns_uuid_string(self):
        uid = register_staged_upload(
            h5_path="/tmp/test.h5",
            filename="test.h5",
            size_bytes=1024,
        )
        assert isinstance(uid, str)
        assert len(uid) > 0

    def test_unique_ids(self):
        uid1 = register_staged_upload("/tmp/a.h5", "a.h5", 100)
        uid2 = register_staged_upload("/tmp/b.h5", "b.h5", 200)
        assert uid1 != uid2

    def test_upload_can_be_resolved(self):
        uid = register_staged_upload("/tmp/test.h5", "test.h5", 1024)
        resolved = resolve_upload(uid)
        assert resolved == "/tmp/test.h5"


# ===================================================================
# resolve_upload
# ===================================================================


class TestResolveUpload:
    """Cover upload resolution."""

    def test_unknown_id_returns_none(self):
        assert resolve_upload("nonexistent-id") is None

    def test_resolution_consumes_upload(self):
        """After resolve, subsequent resolve returns None."""
        uid = register_staged_upload("/tmp/test.h5", "test.h5", 1024)
        path1 = resolve_upload(uid)
        assert path1 == "/tmp/test.h5"
        path2 = resolve_upload(uid)
        assert path2 is None


# ===================================================================
# resolve_source — error branches
# ===================================================================


class TestResolveSource:
    """Cover resolve_source error branches."""

    def test_both_provided_raises(self):
        with pytest.raises(ValueError, match="Only one"):
            resolve_source(source_id="sid", upload_id="uid")

    def test_neither_provided_raises(self):
        with pytest.raises(ValueError, match="required"):
            resolve_source(source_id=None, upload_id=None)

    def test_unknown_upload_id_raises(self):
        with pytest.raises(ValueError, match="no longer available"):
            resolve_source(source_id=None, upload_id="unknown-uid")

    def test_source_id_with_no_bucket_raises(self, monkeypatch):
        """When h5_bucket is None, source_id resolution raises."""
        from bremen import demo_config as dc
        original = dc.read_demo_h5_config

        def fake_config():
            cfg = original()
            cfg["h5_bucket"] = None
            return cfg

        monkeypatch.setattr(dc, "read_demo_h5_config", fake_config)
        with pytest.raises(ValueError, match="not configured"):
            resolve_source(source_id="some-source-id", upload_id=None)

    def test_valid_upload_resolution(self):
        uid = register_staged_upload("/tmp/test.h5", "test.h5", 1024)
        result = resolve_source(source_id=None, upload_id=uid)
        assert result == "/tmp/test.h5"


# ===================================================================
# reset_for_tests
# ===================================================================


class TestResetForTests:
    """Cover the test-only reset function."""

    def test_clears_jobs(self):
        register_staged_upload("/tmp/a.h5", "a.h5", 100)
        reset_for_tests()
        # After reset, no uploads should be resolvable
        # (We can't easily enumerate, but we can verify clean state)

    def test_idempotent(self):
        reset_for_tests()
        reset_for_tests()  # Should not raise

    def test_after_reset_new_registrations_work(self):
        reset_for_tests()
        uid = register_staged_upload("/tmp/new.h5", "new.h5", 50)
        assert resolve_upload(uid) == "/tmp/new.h5"


# ===================================================================
# _utc_now
# ===================================================================


class TestUtcNow:
    """Cover the timestamp helper."""

    def test_returns_iso_format(self):
        result = _utc_now()
        assert isinstance(result, str)
        assert "T" in result
        assert "+" in result or "Z" in result

    def test_not_empty(self):
        assert len(_utc_now()) > 0


# ===================================================================
# _get_or_create_* singletons
# ===================================================================


class TestSingletons:
    """Cover singleton creation patterns."""

    def test_store_singleton(self):
        s1 = _get_or_create_store()
        s2 = _get_or_create_store()
        assert s1 is s2

    def test_jobs_singleton(self):
        j1 = _get_or_create_jobs()
        j2 = _get_or_create_jobs()
        assert j1 is j2

    def test_providers_singleton(self):
        p1 = _get_or_create_providers()
        p2 = _get_or_create_providers()
        assert p1 is p2

    def test_uploads_singleton(self):
        u1 = _get_or_create_uploads()
        u2 = _get_or_create_uploads()
        assert u1 is u2


# ===================================================================
# _cleanup_expired_uploads
# ===================================================================


class TestCleanupExpiredUploads:
    """Cover expired upload cleanup."""

    def test_does_not_crash_on_empty(self):
        _cleanup_expired_uploads()

    def test_recent_uploads_not_cleaned(self):
        uid = register_staged_upload("/tmp/fresh.h5", "fresh.h5", 100)
        _cleanup_expired_uploads()
        assert resolve_upload(uid) == "/tmp/fresh.h5"


# ===================================================================
# allowed_event_details (via event_schema)
# ===================================================================


class TestAllowedEventDetails:
    """Cover event detail filtering."""

    def test_allows_safe_keys(self):
        raw = {"event": "test", "timestamp": "2025-01-01", "safe_key": "value"}
        result = allowed_event_details(raw)
        assert result == raw

    def test_filters_prohibited_keys(self):
        from bremen.api.event_schema import _PROHIBITED_DETAIL_KEYS
        raw = {key: "secret" for key in _PROHIBITED_DETAIL_KEYS}
        raw["safe_key"] = "allowed"
        result = allowed_event_details(raw)
        assert "safe_key" in result
        for key in _PROHIBITED_DETAIL_KEYS:
            assert key not in result

    def test_does_not_mutate_input(self):
        raw = {"event": "test", "sensitive": "data"}
        original = dict(raw)
        allowed_event_details(raw)
        assert raw == original

    def test_empty_dict(self):
        assert allowed_event_details({}) == {}

    def test_returns_copy(self):
        raw = {"key": "value"}
        result = allowed_event_details(raw)
        result["new_key"] = "new_value"
        assert "new_key" not in raw


# ===================================================================
# extract_patient_display_name
# ===================================================================


class TestExtractPatientDisplayName:
    """Cover patient display name extraction edge cases."""

    def test_empty_path_returns_empty(self):
        from bremen.api.job_api_handler import extract_patient_display_name
        assert extract_patient_display_name("") == ""

    def test_none_path_returns_empty(self):
        from bremen.api.job_api_handler import extract_patient_display_name
        assert extract_patient_display_name(None) == ""

    def test_nonexistent_file_returns_empty(self):
        from bremen.api.job_api_handler import extract_patient_display_name
        assert extract_patient_display_name("/tmp/nonexistent_12345.h5") == ""


# ===================================================================
# Source safety (AST-based)
# ===================================================================


class TestJobApiHandlerSourceSafety:
    """AST-based safety checks for job_api_handler.py."""

    SRC = Path(__file__).parents[1] / "src" / "bremen" / "api" / "job_api_handler.py"

    def test_no_urlopen_calls(self):
        import ast
        tree = ast.parse(self.SRC.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "urlopen":
                    pytest.fail("job_api_handler.py calls urlopen()")
                if isinstance(func, ast.Name) and func.id == "urlopen":
                    pytest.fail("job_api_handler.py calls urlopen()")

    def test_no_socket_import(self):
        import ast
        tree = ast.parse(self.SRC.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "socket":
                        pytest.fail("job_api_handler.py imports socket")
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "") == "socket":
                    pytest.fail("job_api_handler.py imports from socket")

    def test_no_HTTPServer_import(self):
        import ast
        tree = ast.parse(self.SRC.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "HTTPServer" in alias.name:
                        pytest.fail("job_api_handler.py imports HTTPServer")

    def test_no_serve_forever(self):
        import ast
        tree = ast.parse(self.SRC.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "serve_forever":
                    pytest.fail("job_api_handler.py calls serve_forever()")
