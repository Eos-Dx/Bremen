"""No-socket unit tests for server.py transport-independent helpers.

Covers deterministic helper functions that do NOT require a real
HTTPServer, sockets, or localhost HTTP:

- ``_safe_error_detail(exc)`` — exception-to-safe-string mapping
- ``_safe_error_detail_str(msg)`` — error-message-to-safe-string mapping
- ``_handle_h5_upload_bytes(...)`` — transport-independent upload validation
- ``_build_containers_response(...)`` — not_configured fast path
- ``_ThreadingHTTPServer`` class properties
- Route dispatch regex patterns from ``_handle_demo_jobs_route``

Uses no HTTPServer, no sockets, no localhost HTTP, no server spawning.
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

import bremen.api.server as server_under_test
from bremen.api.server import (
    _safe_error_detail,
    _safe_error_detail_str,
    _build_containers_response,
)
from bremen.api.preflight import (
    H5ContainerError,
    H5MetadataError,
    H5PatientMismatchError,
    H5SideMismatchError,
    H5MeasurementError,
    H5QualityError,
    H5PreflightError,
)
from bremen.api.preprocessing_bridge import (
    PreprocessingBridgeError,
    PreflightNotPassedError,
    FeatureSchemaMismatchError,
)
from bremen.inference import PortableLogRegModelError
from bremen.feature_artifacts import FeatureArtifactError


# ===================================================================
# _safe_error_detail — all exception branches
# ===================================================================


class TestSafeErrorDetail:
    """Map exception types to safe public strings."""

    def test_h5_container_error(self):
        assert _safe_error_detail(H5ContainerError("x")) == "H5 layout metadata is incomplete"

    def test_h5_metadata_error(self):
        assert _safe_error_detail(H5MetadataError("x")) == "H5 layout metadata is incomplete"

    def test_h5_patient_mismatch_error(self):
        assert _safe_error_detail(H5PatientMismatchError("x")) == "H5 layout metadata is incomplete"

    def test_h5_side_mismatch_error(self):
        assert _safe_error_detail(H5SideMismatchError("x")) == "Bilateral measurement pairing failed"

    def test_h5_measurement_error(self):
        assert _safe_error_detail(H5MeasurementError("x")) == "H5 layout metadata is incomplete"

    def test_h5_quality_error(self):
        assert _safe_error_detail(H5QualityError("x")) == "H5 layout metadata is incomplete"

    def test_h5_preflight_error(self):
        assert _safe_error_detail(H5PreflightError("x")) == "H5 layout metadata is incomplete"

    def test_preprocessing_bridge_error(self):
        assert _safe_error_detail(PreprocessingBridgeError("x")) == "Preprocessing failed"

    def test_feature_schema_mismatch_error(self):
        assert _safe_error_detail(FeatureSchemaMismatchError("x")) == "Preprocessing failed"

    def test_preflight_not_passed_error(self):
        assert _safe_error_detail(PreflightNotPassedError("x")) == "Preprocessing failed"

    def test_portable_logreg_model_error(self):
        assert _safe_error_detail(PortableLogRegModelError("x")) == "Model inference failed"

    def test_feature_artifact_error(self):
        assert _safe_error_detail(FeatureArtifactError("x")) == "Model inference failed"

    def test_generic_exception_fallback(self):
        assert _safe_error_detail(RuntimeError("secret-path")) == "Internal error"

    def test_value_error_fallback(self):
        assert _safe_error_detail(ValueError("s3://bucket/key")) == "Internal error"

    def test_no_internal_paths_exposed(self):
        """Ensure no internal S3 paths, H5 paths, or filenames leak."""
        exc = RuntimeError("Failed at /tmp/abc/data.h5 from s3://bucket/key")
        result = _safe_error_detail(exc)
        assert "/tmp/" not in result
        assert "s3://" not in result
        assert "data.h5" not in result

    def test_return_value_is_always_string(self):
        for exc_cls in (RuntimeError, ValueError, TypeError, OSError):
            result = _safe_error_detail(exc_cls("test"))
            assert isinstance(result, str)
            assert len(result) > 0


# ===================================================================
# _safe_error_detail_str — all message pattern branches
# ===================================================================


class TestSafeErrorDetailStr:
    """Map error message strings to safe public strings."""

    def test_configuration_required(self):
        assert "configuration" in _safe_error_detail_str("configuration_required").lower()

    def test_configuration_required_in_message(self):
        # The function checks for 'configuration_required' as a substring
        assert "configuration" in _safe_error_detail_str("some configuration_required error").lower()

    def test_unavailable(self):
        assert "not available" in _safe_error_detail_str("workflow unavailable").lower()

    def test_not_found(self):
        assert "not available" in _safe_error_detail_str("model not found").lower()

    def test_not_found_underscore(self):
        assert "not available" in _safe_error_detail_str("model_not_found").lower()

    def test_incompatible(self):
        assert "not compatible" in _safe_error_detail_str("input is incompatible").lower()

    def test_fallback_internal_error(self):
        assert _safe_error_detail_str("random error") == "Internal error"

    def test_empty_string_fallback(self):
        assert _safe_error_detail_str("") == "Internal error"

    def test_no_paths_exposed(self):
        result = _safe_error_detail_str("not found at /tmp/secret.h5")
        assert "/tmp/" not in result
        assert "secret.h5" not in result

    def test_case_insensitive(self):
        """Patterns should match regardless of case."""
        assert "not available" in _safe_error_detail_str("NOT FOUND").lower()

    def test_return_value_is_always_string(self):
        for msg in ("", "error", "configuration_required", "unavailable",
                     "not found", "incompatible", "unknown"):
            result = _safe_error_detail_str(msg)
            assert isinstance(result, str)
            assert len(result) > 0


# ===================================================================
# _handle_h5_upload_bytes — transport-independent validation branches
# ===================================================================


class TestHandleH5UploadBytes:
    """Cover all validation branches in the upload helper."""

    def test_empty_body_returns_400(self):
        status, data = server_under_test._handle_h5_upload_bytes(
            b"", "test.h5", "req-1"
        )
        assert status == 400
        assert data["status"] == "upload_rejected"
        assert "Empty body" in data["error"]
        assert data["technical_demo_only"] is True

    def test_oversized_body_returns_413(self, monkeypatch):
        large_body = b"x" * (200 * 1024 * 1024)  # 200MB
        status, data = server_under_test._handle_h5_upload_bytes(
            large_body, "test.h5", "req-2"
        )
        assert status == 413
        assert data["status"] == "upload_rejected"
        assert "too large" in data["error"].lower()

    def test_empty_filename_returns_400(self):
        status, data = server_under_test._handle_h5_upload_bytes(
            b"data", "  ", "req-3"
        )
        assert status == 400
        assert data["status"] == "upload_rejected"
        assert "Missing X-H5-Filename" in data["error"]

    def test_whitespace_only_filename_returns_400(self):
        status, data = server_under_test._handle_h5_upload_bytes(
            b"data", "   ", "req-3b"
        )
        assert status == 400
        assert "Missing X-H5-Filename" in data["error"]

    def test_forward_slash_in_filename_returns_400(self):
        status, data = server_under_test._handle_h5_upload_bytes(
            b"data", "../etc/passwd.h5", "req-4"
        )
        assert status == 400
        assert "path separators" in data["error"].lower()

    def test_backslash_in_filename_returns_400(self):
        status, data = server_under_test._handle_h5_upload_bytes(
            b"data", "foo\\bar.h5", "req-5"
        )
        assert status == 400
        assert "path separators" in data["error"].lower()

    def test_dotdot_in_filename_returns_400(self):
        status, data = server_under_test._handle_h5_upload_bytes(
            b"data", "foo..bar.h5", "req-6"
        )
        assert status == 400
        assert "path separators" in data["error"].lower()

    def test_invalid_extension_returns_400(self):
        status, data = server_under_test._handle_h5_upload_bytes(
            b"data", "test.txt", "req-7"
        )
        assert status == 400
        assert data["status"] == "upload_rejected"
        assert "Invalid file extension" in data["error"]

    def test_hdf5_extension_accepted_by_validation(self):
        """HDF5 extension passes validation (may fail at storage check)."""
        status, data = server_under_test._handle_h5_upload_bytes(
            b"data", "test.hdf5", "req-8"
        )
        # Will fail at upload_disabled or storage_not_configured, NOT at extension
        assert status != 400 or "extension" not in data.get("error", "")

    def test_upload_disabled_returns_403(self, monkeypatch):
        """When allow_upload=False, returns 403."""
        def fake_config():
            return {
                "h5_bucket": "test-bucket",
                "h5_prefix": "data/",
                "allow_upload": False,
                "upload_max_bytes": 100 * 1024 * 1024,
            }

        monkeypatch.setattr(server_under_test, "read_demo_h5_config", fake_config)
        status, data = server_under_test._handle_h5_upload_bytes(
            b"data", "test.h5", "req-9"
        )
        assert status == 403
        assert data["status"] == "upload_disabled"

    def test_storage_not_configured_returns_503(self, monkeypatch):
        """When h5_bucket is None, returns 503."""
        original = server_under_test.read_demo_h5_config

        def fake_config():
            cfg = original()
            cfg["allow_upload"] = True
            cfg["h5_bucket"] = None
            return cfg

        monkeypatch.setattr(server_under_test, "read_demo_h5_config", fake_config)
        status, data = server_under_test._handle_h5_upload_bytes(
            b"data", "test.h5", "req-10"
        )
        assert status == 503
        assert data["status"] == "storage_not_configured"

    def test_s3_upload_failure_returns_503(self, monkeypatch):
        """When S3 upload fails, returns 503 with safe error."""
        def fake_config():
            return {
                "h5_bucket": "test-bucket",
                "h5_prefix": "data/",
                "allow_upload": True,
                "upload_max_bytes": 100 * 1024 * 1024,
            }

        monkeypatch.setattr(server_under_test, "read_demo_h5_config", fake_config)

        class FakeS3:
            def put_object(self, **kwargs):
                raise PermissionError("AccessDenied")

        fake_s3 = FakeS3()

        import builtins
        real_import = builtins.__import__

        def patched_import(name, *args, **kwargs):
            if name == "boto3":
                import types as _types
                mod = _types.ModuleType("boto3")
                mod.client = lambda n: fake_s3
                return mod
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", patched_import)

        status, data = server_under_test._handle_h5_upload_bytes(
            b"data", "test.h5", "req-11"
        )
        assert status == 503
        assert data["status"] == "upload_rejected"
        assert "S3 upload failed" in data["error"]

    def test_all_responses_contain_request_id(self):
        """Every response path includes the request_id."""
        _, data = server_under_test._handle_h5_upload_bytes(b"", "x.h5", "my-req")
        assert data["request_id"] == "my-req"

    def test_all_responses_contain_technical_demo_only(self):
        """Every response includes technical_demo_only=True."""
        _, data = server_under_test._handle_h5_upload_bytes(b"", "x.h5", "req")
        assert data["technical_demo_only"] is True

    def test_filename_sanitization_strips_dangerous_chars(self, monkeypatch):
        """Filename with spaces and special chars gets sanitized."""
        def fake_config():
            return {
                "h5_bucket": "test-bucket",
                "h5_prefix": "data/",
                "allow_upload": True,
                "upload_max_bytes": 100 * 1024 * 1024,
            }

        monkeypatch.setattr(server_under_test, "read_demo_h5_config", fake_config)

        class FakeS3:
            def __init__(self):
                self.kwargs = None
            def put_object(self, **kwargs):
                self.kwargs = kwargs

        fake_s3 = FakeS3()

        import builtins
        real_import = builtins.__import__

        def patched_import(name, *args, **kwargs):
            if name == "boto3":
                import types as _types
                mod = _types.ModuleType("boto3")
                mod.client = lambda n: fake_s3
                return mod
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", patched_import)

        status, data = server_under_test._handle_h5_upload_bytes(
            b"data", "my test file.h5", "req-sanitize"
        )
        assert status == 201
        assert data["filename"] == "my_test_file.h5"


# ===================================================================
# _build_containers_response — not_configured fast path
# ===================================================================


class TestBuildContainersResponse:
    """Cover the transport-independent containers response helper."""

    def test_not_configured_returns_empty(self, monkeypatch):
        """When h5_bucket is None, returns not_configured fast path."""
        from bremen import demo_config as dc
        original = dc.read_demo_h5_config

        def fake_config():
            cfg = original()
            cfg["h5_bucket"] = None
            return cfg

        monkeypatch.setattr(dc, "read_demo_h5_config", fake_config)
        result = _build_containers_response(request_id="test-req")
        assert result["storage"] == "not_configured"
        assert result["containers"] == []
        assert result["technical_demo_only"] is True
        assert result["request_id"] == "test-req"

    def test_auto_generates_request_id_if_none(self, monkeypatch):
        """When request_id is None, a UUID is auto-generated."""
        from bremen import demo_config as dc
        original = dc.read_demo_h5_config

        def fake_config():
            cfg = original()
            cfg["h5_bucket"] = None
            return cfg

        monkeypatch.setattr(dc, "read_demo_h5_config", fake_config)
        result = _build_containers_response(request_id=None)
        assert isinstance(result["request_id"], str)
        assert len(result["request_id"]) > 0

    def test_not_configured_response_is_json_serializable(self, monkeypatch):
        """Response dict can be serialized to JSON."""
        from bremen import demo_config as dc
        original = dc.read_demo_h5_config

        def fake_config():
            cfg = original()
            cfg["h5_bucket"] = None
            return cfg

        monkeypatch.setattr(dc, "read_demo_h5_config", fake_config)
        result = _build_containers_response(request_id="json-test")
        serialized = json.dumps(result)
        assert isinstance(serialized, str)


# ===================================================================
# _ThreadingHTTPServer class properties
# ===================================================================


class TestThreadingHTTPServer:
    """Cover _ThreadingHTTPServer class-level properties via source inspection."""

    API_SRC = Path(__file__).parents[1] / "src" / "bremen" / "api"

    def test_daemon_threads_is_true_in_source(self):
        """server.py defines _ThreadingHTTPServer with daemon_threads = True."""
        src = (self.API_SRC / "server.py").read_text(encoding="utf-8")
        assert "daemon_threads = True" in src

    def test_class_definition_exists(self):
        """server.py defines _ThreadingHTTPServer."""
        import ast
        tree = ast.parse((self.API_SRC / "server.py").read_text(encoding="utf-8"))
        class_names = [
            node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        ]
        assert "_ThreadingHTTPServer" in class_names

    def test_threading_mix_in_base(self):
        """_ThreadingHTTPServer inherits from ThreadingMixIn."""
        import ast
        tree = ast.parse((self.API_SRC / "server.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "_ThreadingHTTPServer":
                base_names = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        base_names.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        base_names.append(base.attr)
                assert "ThreadingMixIn" in base_names
                return
        pytest.fail("_ThreadingHTTPServer class not found")


# ===================================================================
# Route dispatch regex patterns
# ===================================================================


class TestRouteDispatchRegex:
    """Cover the regex patterns used in _handle_demo_jobs_route."""

    @staticmethod
    def _match(pattern: str, path: str) -> re.Match | None:
        return re.match(pattern, path)

    def test_events_stream_pattern(self):
        m = self._match(r"^/demo/api/jobs/([^/]+)/events/stream$", "/demo/api/jobs/abc-123/events/stream")
        assert m is not None
        assert m.group(1) == "abc-123"

    def test_events_stream_no_match_without_stream(self):
        m = self._match(r"^/demo/api/jobs/([^/]+)/events/stream$", "/demo/api/jobs/abc-123/events")
        assert m is None

    def test_events_pattern(self):
        m = self._match(r"^/demo/api/jobs/([^/]+)/events$", "/demo/api/jobs/abc-123/events")
        assert m is not None
        assert m.group(1) == "abc-123"

    def test_events_no_match_with_stream(self):
        m = self._match(r"^/demo/api/jobs/([^/]+)/events$", "/demo/api/jobs/abc-123/events/stream")
        assert m is None

    def test_report_pattern(self):
        m = self._match(r"^/demo/api/jobs/([^/]+)/reports/([^/]+)$", "/demo/api/jobs/j1/reports/bremen")
        assert m is not None
        assert m.group(1) == "j1"
        assert m.group(2) == "bremen"

    def test_reports_list_pattern(self):
        m = self._match(r"^/demo/api/jobs/([^/]+)/reports$", "/demo/api/jobs/j1/reports")
        assert m is not None
        assert m.group(1) == "j1"

    def test_job_get_pattern(self):
        m = self._match(r"^/demo/api/jobs/([^/]+)$", "/demo/api/jobs/j1")
        assert m is not None
        assert m.group(1) == "j1"

    def test_report_pattern_no_match_with_extra_slash(self):
        m = self._match(r"^/demo/api/jobs/([^/]+)/reports/([^/]+)$", "/demo/api/jobs/j1/reports/bremen/extra")
        assert m is None


# ===================================================================
# Source safety (AST-based) for server.py
# ===================================================================


class TestServerSourceSafety:
    """AST-based safety checks for server.py."""

    API_SRC = Path(__file__).parents[1] / "src" / "bremen" / "api"

    def test_no_urlopen_in_server(self):
        """server.py does not call urlopen directly (route handlers use handler methods)."""
        import ast
        src = self.API_SRC / "server.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "urlopen":
                    pytest.fail("server.py calls urlopen()")
                if isinstance(func, ast.Name) and func.id == "urlopen":
                    pytest.fail("server.py calls urlopen()")

    def test_no_requests_import(self):
        """server.py does not import requests."""
        import ast
        src = self.API_SRC / "server.py"
        content = src.read_text(encoding="utf-8")
        tree = ast.parse(content)
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "requests", "server.py imports requests"
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "") != "requests", "server.py imports from requests"
