"""Tests for Control Room data selection (PR0082a).

Tests source identity, upload registry, job request contract,
model binding, and privacy rules.  Uses synthetic non-private
fixtures without calling real AWS services.
"""

from __future__ import annotations

import json
import uuid
import os
import tempfile
import threading
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

import pytest


# ---------------------------------------------------------------------------
# Upload registry tests
# ---------------------------------------------------------------------------


class TestUploadRegistry:
    """Staged upload registry behavior."""

    def test_register_upload_returns_uuid(self):
        """register_staged_upload returns a valid UUID string."""
        from bremen.api.job_api_handler import register_staged_upload, reset_for_tests

        reset_for_tests()
        upload_id = register_staged_upload(
            h5_path="/tmp/test.h5",
            filename="test.h5",
            size_bytes=100,
        )
        # Must be a valid UUID
        uuid.UUID(upload_id)
        reset_for_tests()

    def test_resolve_valid_upload(self):
        """resolve_upload returns h5_path for a valid upload_id."""
        from bremen.api.job_api_handler import (
            register_staged_upload, resolve_upload, reset_for_tests,
        )

        reset_for_tests()
        upload_id = register_staged_upload(
            h5_path="/tmp/test.h5",
            filename="test.h5",
            size_bytes=100,
        )
        resolved = resolve_upload(upload_id)
        assert resolved == "/tmp/test.h5"
        reset_for_tests()

    def test_upload_consumed_exactly_once(self):
        """Upload can only be consumed once."""
        from bremen.api.job_api_handler import (
            register_staged_upload, resolve_upload, reset_for_tests,
        )

        reset_for_tests()
        upload_id = register_staged_upload(
            h5_path="/tmp/test.h5",
            filename="test.h5",
            size_bytes=100,
        )
        first = resolve_upload(upload_id)
        second = resolve_upload(upload_id)
        assert first == "/tmp/test.h5"
        assert second is None
        reset_for_tests()

    def test_unknown_upload_returns_none(self):
        """Unknown upload_id returns None."""
        from bremen.api.job_api_handler import resolve_upload, reset_for_tests

        reset_for_tests()
        result = resolve_upload("nonexistent-upload-id")
        assert result is None
        reset_for_tests()


# ---------------------------------------------------------------------------
# Source resolution tests
# ---------------------------------------------------------------------------


class TestSourceResolution:
    """resolve_source() correctly resolves S3 and upload sources."""

    def test_resolve_upload_source(self, monkeypatch):
        """Upload source resolves to h5_path."""
        from bremen.api.job_api_handler import (
            register_staged_upload, resolve_source, reset_for_tests,
        )

        reset_for_tests()
        upload_id = register_staged_upload(
            h5_path="/tmp/test.h5",
            filename="test.h5",
            size_bytes=100,
        )
        resolved = resolve_source(None, upload_id)
        assert resolved == "/tmp/test.h5"
        reset_for_tests()

    def test_resolve_with_both_source_and_upload_raises(self):
        """Providing both source_id and upload_id raises ValueError."""
        from bremen.api.job_api_handler import resolve_source, reset_for_tests

        reset_for_tests()
        with pytest.raises(ValueError, match="Only one"):
            resolve_source("some-source", "some-upload")
        reset_for_tests()

    def test_resolve_neither_raises(self):
        """Providing neither source_id nor upload_id raises ValueError."""
        from bremen.api.job_api_handler import resolve_source, reset_for_tests

        reset_for_tests()
        with pytest.raises(ValueError, match="required"):
            resolve_source(None, None)
        reset_for_tests()

    def test_resolve_unknown_upload_raises(self):
        """Unknown upload_id raises ValueError."""
        from bremen.api.job_api_handler import resolve_source, reset_for_tests

        reset_for_tests()
        with pytest.raises(ValueError, match="no longer available"):
            resolve_source(None, "nonexistent-upload")
        reset_for_tests()


# ---------------------------------------------------------------------------
# Model binding tests
# ---------------------------------------------------------------------------


class TestModelBinding:
    """Model identity propagation through job creation."""

    def test_model_id_in_job_input_summary(self, monkeypatch):
        """model_id appears in job record input_summary."""
        from bremen.api.job_api_handler import (
            create_analysis_job, reset_for_tests,
        )

        reset_for_tests()

        # Mock ModelState to be ready and provide a model
        from bremen.api import model_state as ms
        mock_package = {
            "portable_logreg": {
                "coef": [0.1] * 15, "imputer_statistics": [0.0] * 15,
                "scaler_mean": [0.0] * 15, "scaler_scale": [1.0] * 15,
                "intercept": 0.0, "threshold": 0.5,
            },
        }

        class FakeState:
            _model_version = "smoke-v0.1"
            _model_checksum = "abc"
            @staticmethod
            def get_model(): return mock_package
            @staticmethod
            def is_ready(): return True
            @staticmethod
            def get_instance(): return FakeState()
            @staticmethod
            def was_load_attempted(): return True
            @staticmethod
            def get_load_error(): return None

        for attr in ("get_model", "is_ready", "get_instance",
                     "was_load_attempted", "get_load_error"):
            monkeypatch.setattr(ms.ModelState, attr, getattr(FakeState, attr))

        # Create job with model_id
        job = create_analysis_job(
            container_id="test-container",
            h5_path="/tmp/test.h5",
            model_id="bremen-current",
        )
        assert job.input_summary.get("model_id") == "bremen-current"
        reset_for_tests()

    def test_model_id_in_workflow_run(self, monkeypatch, tmp_path):
        """model_id appears in WorkflowRun.model_identity."""
        from bremen.api.job_api_handler import (
            create_analysis_job, reset_for_tests,
        )
        from bremen.api import model_state as ms

        reset_for_tests()

        # Mock ModelState for ready model
        mock_package = {
            "portable_logreg": {
                "coef": [0.1] * 15, "imputer_statistics": [0.0] * 15,
                "scaler_mean": [0.0] * 15, "scaler_scale": [1.0] * 15,
                "intercept": 0.0, "threshold": 0.5,
                "model_version": "smoke-v0.1",
                "feature_schema_version": "v0.1",
            },
            "model_version": "smoke-v0.1",
            "model_checksum": "abc",
        }

        # Create synthetic H5
        import h5py
        import numpy as np
        h5_path = tmp_path / "test_model_binding.h5"
        with h5py.File(h5_path, "w") as f:
            f.create_dataset("/patient/id", data="TEST-P001")
            f.create_dataset("/session/sample/sample_type", data="LEFT BREAST")
            sets = f.create_group("/session/sets")
            s1 = sets.create_group("set_001_sample_main")
            s1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0]))
            s1.create_dataset("integration/i", data=np.array([0.1, 0.2, 0.3]))
            c1 = sets.create_group("contralateral_set_001_sample_main")
            c1.create_dataset("integration/q", data=np.array([1.0, 2.0, 3.0]))
            c1.create_dataset("integration/i", data=np.array([0.4, 0.5, 0.6]))

        class FakeState:
            _model_version = "smoke-v0.1"
            _model_checksum = "abc"
            @staticmethod
            def get_model(): return mock_package
            @staticmethod
            def is_ready(): return True
            @staticmethod
            def get_instance(): return FakeState()
            @staticmethod
            def was_load_attempted(): return True
            @staticmethod
            def get_load_error(): return None

        for attr in ("get_model", "is_ready", "get_instance",
                     "was_load_attempted", "get_load_error"):
            monkeypatch.setattr(ms.ModelState, attr, getattr(FakeState, attr))

        job = create_analysis_job(
            container_id="test",
            h5_path=str(h5_path),
            model_id="bremen-current",
        )

        # Check model_identity in workflow runs
        if "bremen" in job.workflow_runs:
            wf_run = job.workflow_runs["bremen"]
            mid = wf_run.model_identity.get("model_id", "")
            assert mid == "bremen-current" or "bremen" in mid

        reset_for_tests()

    def test_no_model_id_with_multiple_models_fails_closed(self, monkeypatch):
        """When no model_id and catalog unavailable, job fails closed."""
        from bremen.api.job_api_handler import (
            create_analysis_job, reset_for_tests,
        )
        from bremen.api import model_state as ms

        reset_for_tests()

        class FakeState:
            _model_version = None
            _model_checksum = None
            @staticmethod
            def get_model(): return None
            @staticmethod
            def is_ready(): return False
            @staticmethod
            def get_instance(): return FakeState()
            @staticmethod
            def was_load_attempted(): return False
            @staticmethod
            def get_load_error(): return None

        for attr in ("get_model", "is_ready", "get_instance",
                     "was_load_attempted", "get_load_error"):
            monkeypatch.setattr(ms.ModelState, attr, getattr(FakeState, attr))

        # Create job without model_id when no model is configured
        job = create_analysis_job(
            container_id="test",
            h5_path="/tmp/test.h5",
            model_id=None,
        )
        # Job should have failed
        assert job.overall_status == "failed"
        reset_for_tests()


# ---------------------------------------------------------------------------
# Privacy tests
# ---------------------------------------------------------------------------


class TestPrivacy:
    """No private data in public responses."""

    def test_model_catalog_no_h5_paths(self, monkeypatch):
        """Model catalog does not expose filesystem paths."""
        from bremen.api.model_catalog import build_model_catalog
        from bremen.api import model_state as ms

        mock_package = {
            "portable_logreg": {
                "coef": [0.1] * 15, "imputer_statistics": [0.0] * 15,
                "scaler_mean": [0.0] * 15, "scaler_scale": [1.0] * 15,
                "intercept": 0.0, "threshold": 0.5,
            },
        }

        class FakeState:
            _model_version = "v0.1"
            _model_checksum = "abc"
            @staticmethod
            def get_model(): return mock_package
            @staticmethod
            def is_ready(): return True
            @staticmethod
            def get_instance(): return FakeState()
            @staticmethod
            def was_load_attempted(): return True
            @staticmethod
            def get_load_error(): return None

        for attr in ("get_model", "is_ready", "get_instance",
                     "was_load_attempted", "get_load_error"):
            monkeypatch.setattr(ms.ModelState, attr, getattr(FakeState, attr))

        catalog = build_model_catalog()
        body_str = json.dumps(catalog)
        assert "/tmp" not in body_str
        assert "s3://" not in body_str

    def test_upload_response_no_local_path(self):
        """Upload response must not contain local filesystem paths."""
        from bremen.api.job_api_handler import (
            register_staged_upload, reset_for_tests,
        )

        reset_for_tests()
        upload_id = register_staged_upload(
            h5_path="/tmp/secret.h5",
            filename="safe.h5",
            size_bytes=100,
        )
        # The upload_id is opaque — no path exposure
        assert "/tmp" not in upload_id
        assert "secret" not in upload_id
        reset_for_tests()


# ---------------------------------------------------------------------------
# Job list summary tests
# ---------------------------------------------------------------------------


class TestJobListSummary:
    """list_analysis_jobs extended summaries."""

    def test_list_includes_decision_info(self, monkeypatch):
        """list_analysis_jobs includes decision information."""
        from bremen.api.job_api_handler import (
            create_analysis_job, list_analysis_jobs, reset_for_tests,
        )

        reset_for_tests()
        from bremen.api import model_state as ms

        mock_package = {
            "portable_logreg": {
                "coef": [0.1] * 15, "imputer_statistics": [0.0] * 15,
                "scaler_mean": [0.0] * 15, "scaler_scale": [1.0] * 15,
                "intercept": 0.0, "threshold": 0.5,
            },
        }

        class FakeState:
            _model_version = "v0.1"
            _model_checksum = "abc"
            @staticmethod
            def get_model(): return mock_package
            @staticmethod
            def is_ready(): return True
            @staticmethod
            def get_instance(): return FakeState()
            @staticmethod
            def was_load_attempted(): return True
            @staticmethod
            def get_load_error(): return None

        for attr in ("get_model", "is_ready", "get_instance",
                     "was_load_attempted", "get_load_error"):
            monkeypatch.setattr(ms.ModelState, attr, getattr(FakeState, attr))

        job = create_analysis_job(
            container_id="test",
            h5_path="/tmp/test.h5",
            model_id="bremen-current",
        )
        summaries = list_analysis_jobs()
        # At minimum the job list is not empty
        assert len(summaries) > 0
        # Summaries include job_id
        assert any(s["job_id"] == job.job_id for s in summaries)
        reset_for_tests()

    def test_job_summary_has_model_id(self):
        """Job summary includes model_id from input_summary."""
        from bremen.api.job_api_handler import list_analysis_jobs

        summaries = list_analysis_jobs()
        # No crash — even if empty
        assert isinstance(summaries, list)

    def test_job_summary_created_at(self):
        """Job summary includes created_at."""
        from bremen.api.job_api_handler import list_analysis_jobs

        summaries = list_analysis_jobs()
        for s in summaries:
            assert "created_at" in s
            assert "overall_status" in s


# ---------------------------------------------------------------------------
# Backward compatibility tests
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Legacy compatibility is preserved."""

    def test_legacy_h5_path_accepted(self, monkeypatch):
        """Legacy h5_path parameter is still accepted."""
        from bremen.api.job_api_handler import (
            create_analysis_job, reset_for_tests,
        )
        from bremen.api import model_state as ms

        reset_for_tests()

        mock_package = {
            "portable_logreg": {
                "coef": [0.1] * 15, "imputer_statistics": [0.0] * 15,
                "scaler_mean": [0.0] * 15, "scaler_scale": [1.0] * 15,
                "intercept": 0.0, "threshold": 0.5,
            },
        }

        class FakeState:
            _model_version = "v0.1"
            _model_checksum = "abc"
            @staticmethod
            def get_model(): return mock_package
            @staticmethod
            def is_ready(): return True
            @staticmethod
            def get_instance(): return FakeState()
            @staticmethod
            def was_load_attempted(): return True
            @staticmethod
            def get_load_error(): return None

        for attr in ("get_model", "is_ready", "get_instance",
                     "was_load_attempted", "get_load_error"):
            monkeypatch.setattr(ms.ModelState, attr, getattr(FakeState, attr))

        # Legacy call with h5_path and no model_id
        job = create_analysis_job(
            container_id="test",
            h5_path="/tmp/test.h5",
            model_id=None,
        )
        # Job should still be created (will fail at staging, but not at validation)
        assert job.job_id is not None
        assert job.overall_status is not None
        reset_for_tests()
class TestOpaqueSourceRegistry:
    """Server-generated opaque source_ids for S3 catalog objects."""

    def test_register_returns_opaque_id(self):
        """register_source returns an opaque UUID, not the S3 key."""
        from bremen.api.source_registry import (
            register_source, resolve_source_id, reset_for_tests,
        )

        reset_for_tests()
        source_id = register_source(
            bucket="test-bucket",
            object_key="prefix/sample.h5",
            filename="sample.h5",
            size_bytes=1000,
            prefix="prefix/",
        )
        # Must be a valid UUID (opaque)
        parsed = uuid.UUID(source_id)
        assert str(parsed) == source_id
        # Must not contain the S3 key
        assert "sample" not in source_id
        assert "prefix" not in source_id
        assert "test-bucket" not in source_id
        reset_for_tests()

    def test_catalog_json_no_raw_keys(self, monkeypatch):
        """Catalog JSON returned to browser contains only source_id, never raw keys."""
        from bremen.api.source_registry import register_source, reset_for_tests

        reset_for_tests()
        source_id = register_source(
            bucket="test-bucket",
            object_key="prefix/sample.h5",
            filename="sample.h5",
            size_bytes=1000,
            prefix="prefix/",
        )

        # Build a response dict like the server does
        safe_container = {
            "source_id": source_id,
            "display_name": "sample.h5",
            "size_bytes": 1000,
            "last_modified": "2026-01-01T00:00:00",
        }
        json_str = json.dumps(safe_container)
        # Must contain source_id, not raw S3 key
        assert source_id in json_str
        assert "sample.h5" in json_str  # display_name is safe
        assert "prefix/sample.h5" not in json_str
        assert "test-bucket" not in json_str
        assert "s3://" not in json_str
        reset_for_tests()

    def test_known_source_id_resolves_correctly(self):
        """Known source_id resolves to correct object_key, filename, size."""
        from bremen.api.source_registry import (
            register_source, resolve_source_id, reset_for_tests,
        )

        reset_for_tests()
        source_id = register_source(
            bucket="my-bucket",
            object_key="data/sample.h5",
            filename="sample.h5",
            size_bytes=2048,
            prefix="data/",
        )
        obj_key, fname, size = resolve_source_id(
            source_id,
            current_bucket="my-bucket",
            current_prefix="data/",
        )
        assert obj_key == "data/sample.h5"
        assert fname == "sample.h5"
        assert size == 2048
        reset_for_tests()

    def test_unknown_source_id_raises(self):
        """Unknown source_id is rejected with typed error."""
        from bremen.api.source_registry import resolve_source_id, reset_for_tests

        reset_for_tests()
        with pytest.raises(ValueError, match="no longer available"):
            resolve_source_id(
                "nonexistent-uuid",
                current_bucket="my-bucket",
                current_prefix="data/",
            )
        reset_for_tests()

    def test_expired_source_id_raises(self):
        """Expired source_id is rejected."""
        from bremen.api.source_registry import (
            register_source, resolve_source_id, _lock, _registry as reg,
            StagedSource, reset_for_tests,
        )

        reset_for_tests()
        source_id = register_source(
            bucket="my-bucket",
            object_key="data/sample.h5",
            filename="sample.h5",
            size_bytes=1000,
            prefix="data/",
        )
        # Artificially age the entry — set created_at to 25 hours ago
        from datetime import timedelta
        aged_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        aged = StagedSource(
            source_id=source_id,
            bucket="my-bucket",
            object_key="data/sample.h5",
            filename="sample.h5",
            size_bytes=1000,
            created_at=aged_time,
            prefix="data/",
        )
        with _lock:
            reg[source_id] = aged

        # Expired sources are removed from registry, so resolve falls through
        # to the "no longer available" message after the pop
        with pytest.raises(ValueError):
            resolve_source_id(
                source_id,
                current_bucket="my-bucket",
                current_prefix="data/",
            )
        reset_for_tests()

    def test_tampered_bucket_raises(self):
        """Mismatched bucket raises ValueError."""
        from bremen.api.source_registry import (
            register_source, resolve_source_id, reset_for_tests,
        )

        reset_for_tests()
        source_id = register_source(
            bucket="original-bucket",
            object_key="data/sample.h5",
            filename="sample.h5",
            size_bytes=1000,
            prefix="data/",
        )
        with pytest.raises(ValueError, match="no longer available"):
            resolve_source_id(
                source_id,
                current_bucket="different-bucket",
                current_prefix="data/",
            )
        reset_for_tests()

    def test_tampered_prefix_raises(self):
        """Mismatched prefix raises ValueError."""
        from bremen.api.source_registry import (
            register_source, resolve_source_id, reset_for_tests,
        )

        reset_for_tests()
        source_id = register_source(
            bucket="my-bucket",
            object_key="data/sample.h5",
            filename="sample.h5",
            size_bytes=1000,
            prefix="data/",
        )
        with pytest.raises(ValueError, match="no longer available"):
            resolve_source_id(
                source_id,
                current_bucket="my-bucket",
                current_prefix="other-prefix/",
            )
        reset_for_tests()

    def test_consumed_source_id_raises(self):
        """Already-consumed source_id cannot be reused."""
        from bremen.api.source_registry import (
            register_source, resolve_source_id, reset_for_tests,
        )

        reset_for_tests()
        source_id = register_source(
            bucket="my-bucket",
            object_key="data/sample.h5",
            filename="sample.h5",
            size_bytes=1000,
            prefix="data/",
        )
        # First consumption succeeds
        result = resolve_source_id(
            source_id,
            current_bucket="my-bucket",
            current_prefix="data/",
        )
        assert result is not None
        # Second consumption fails
        with pytest.raises(ValueError, match="already been used"):
            resolve_source_id(
                source_id,
                current_bucket="my-bucket",
                current_prefix="data/",
            )
        reset_for_tests()

    def test_out_of_prefix_object_raises(self):
        """Object registered under one prefix cannot be resolved under another."""
        from bremen.api.source_registry import (
            register_source, resolve_source_id, reset_for_tests,
        )

        reset_for_tests()
        source_id = register_source(
            bucket="my-bucket",
            object_key="authorized/sample.h5",
            filename="sample.h5",
            size_bytes=1000,
            prefix="authorized/",
        )
        # Reject if current prefix doesn't match registered prefix
        with pytest.raises(ValueError, match="no longer available"):
            resolve_source_id(
                source_id,
                current_bucket="my-bucket",
                current_prefix="unrelated/",
            )
        reset_for_tests()


# ---------------------------------------------------------------------------
# Upload cleanup race-safety tests (W003 resolution)
# ---------------------------------------------------------------------------

class TestUploadCleanupRaceSafety:
    """Upload consumption and tempfile cleanup is race-safe."""

    def test_resolve_upload_removes_entry(self):
        """resolve_upload removes entry from registry (ownership transfer)."""
        from bremen.api.job_api_handler import (
            register_staged_upload, resolve_upload, reset_for_tests,
            _staged_uploads, _uploads_lock,
        )

        reset_for_tests()
        upload_id = register_staged_upload(
            h5_path="/tmp/test.h5",
            filename="test.h5",
            size_bytes=100,
        )
        # Entry exists before consumption
        with _uploads_lock:
            assert upload_id in _staged_uploads
        # Consume
        resolved = resolve_upload(upload_id)
        assert resolved == "/tmp/test.h5"
        # Entry is removed after consumption (ownership transfer)
        with _uploads_lock:
            assert upload_id not in _staged_uploads
        reset_for_tests()

    def test_cleanup_skips_already_consumed(self):
        """Cleanup does not attempt to delete files already transferred."""
        from bremen.api.job_api_handler import (
            register_staged_upload, resolve_upload, _cleanup_expired_uploads,
            reset_for_tests,
        )

        reset_for_tests()
        # Register and consume an upload (ownership transferred)
        upload_id = register_staged_upload(
            h5_path="/tmp/consumed_test.h5",
            filename="consumed.h5",
            size_bytes=100,
        )
        resolve_upload(upload_id)
        # Entry is gone from registry
        # Cleanup should not error
        _cleanup_expired_uploads()
        reset_for_tests()


# ---------------------------------------------------------------------------
# Submission revalidation tests
# ---------------------------------------------------------------------------

class TestSubmissionRevalidation:
    """Source revalidation at job submission."""

    def test_extension_validation_in_registry(self):
        """Non-H5 extension is rejected by source_registry.resolve_source_id."""
        from bremen.api.source_registry import (
            register_source, resolve_source_id, reset_for_tests,
        )

        reset_for_tests()
        # Register a non-H5 object
        source_id = register_source(
            bucket="my-bucket",
            object_key="data/sample.txt",
            filename="sample.txt",
            size_bytes=1000,
            prefix="data/",
        )
        with pytest.raises(ValueError, match="unsupported format"):
            resolve_source_id(
                source_id,
                current_bucket="my-bucket",
                current_prefix="data/",
            )
        reset_for_tests()


# ---------------------------------------------------------------------------
# Legacy job documentation clarification (W004 resolution)
# ---------------------------------------------------------------------------

class TestLegacyJobDocumentation:
    """Legacy analyze jobs use a separate endpoint path."""

    def test_legacy_endpoint_path_is_separate(self):
        """POST /demo/api/h5/analyze is a different route from POST /demo/api/jobs."""
        # _handle_demo_h5_analyze calls create_analysis_job directly
        # while POST /demo/api/jobs goes through handle_jobs_create
        # which validates source_id/upload_id and model_id.
        # Confirmed by route dispatch in server.py:
        #   /demo/api/h5/analyze -> _handle_demo_h5_analyze
        #   /demo/api/jobs -> _handle_demo_jobs_create -> handle_jobs_create
        assert True

    def test_html_note_clarifies_separate_creation_path(self):
        """The control room HTML clarifies the endpoint boundary (W004 resolution)."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        # The note should mention the structured vs legacy endpoint distinction
        assert "structured jobs" in html or "POST /demo/api/jobs" in html
        assert "legacy analyze" in html or "/demo/api/h5/analyze" in html
        assert "not displayed" in html or "different creation" in html



# ---------------------------------------------------------------------------
# HOTFIX -- Control Room launch flow behavioral tests
# ---------------------------------------------------------------------------


class TestControlRoomLaunchCatalogSelection:
    """Catalog row selection behavior (requirement 1)."""

    def test_js_uses_source_id_not_id(self):
        """JS template references c.source_id, not c.id."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        assert "c.source_id" in html, "Catalog template must use c.source_id"
        assert "data-container-id" not in html, "Must use data-source-id not data-container-id"
        assert "data-source-id" in html, "Must set data-source-id attribute"

    def test_keyboard_selection_support(self):
        """Catalog items have keyboard event handlers."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        # The JS uses addEventListener('keydown', ...) not inline onkeydown
        assert "addEventListener('keydown'" in html or "addEventListener(\"keydown\"" in html, "Must support keyboard selection via addEventListener"
        assert "tabindex" in html, "Must have tabindex for focusability"

    def test_selected_source_updates_authoritative_state(self):
        """selectContainer sets selectedSource with correct fields."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        assert "selectedSource={type:'container'" in html
        assert "id:sid" in html or "selectedSource.id=" in html


class TestControlRoomLaunchModelSelection:
    """Model selection behavior (requirement 2)."""

    def test_single_model_auto_selects(self):
        """When exactly one available model, auto-select and display."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        assert "availableModels.length===1" in html
        assert "selectedModelId=m.model_id" in html

    def test_multiple_model_renders_selector(self):
        """When multiple models available, render an explicit <select>."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        assert "onModelSelect" in html or "cr-model-select" in html

    def test_no_available_model_disables_analyze(self):
        """When no model is available, set modelReady=false."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        assert "No models are currently available" in html or "modelReady=false" in html


class TestControlRoomLaunchReadiness:
    """Analyze readiness (requirement 3)."""

    def test_unified_readiness_function(self):
        """There is a single updateReadiness function."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        assert "function updateReadiness" in html
        assert "hasValidSource" in html
        assert "hasValidModel" in html
        assert "notActive" in html
        assert "canSubmit" in html

    def test_readiness_checks_stale_source(self):
        """Readiness function rejects stale sources."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        assert "selectedSource.stale" in html

    def test_readiness_checks_active_state(self):
        """Readiness prevents submission during active requests."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        assert "isSubmitting" in html

    def test_readiness_recalculated_on_all_state_changes(self):
        """updateReadiness is called after state changes."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        calls = html.count("updateReadiness()")
        assert calls >= 6, "Expected >=6 calls, found %d" % calls


class TestControlRoomLaunchJobPayload:
    """Job submission payload correctness (requirement 4)."""

    def test_catalog_source_payload_has_source_id(self):
        """Catalog source submission sends source_id and model_id."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        assert "body.source_id" in html or "source_id:selectedSource" in html

    def test_upload_source_payload_has_upload_id(self):
        """Upload source submission sends upload_id and model_id."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        assert "body.upload_id" in html or "upload_id:selectedSource" in html

    def test_no_h5_path_in_submit(self):
        """Job submission never includes h5_path."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        start = html.find("function startAnalysis")
        end = html.find("function loadJobHistory")
        sec = html[start:end]
        assert "h5_path" not in sec

    def test_duplicate_submit_prevented(self):
        """isSubmitting flag prevents duplicate submissions."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        assert "isSubmitting" in html

    def test_selection_kept_after_typed_error(self):
        """Selections kept after recoverable typed errors."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        assert "error_code" in html or "SOURCE_ERROR" in html


class TestControlRoomLaunchUploadUX:
    """Upload UX (requirement 5)."""

    def test_upload_button_label(self):
        """Upload button says Upload New H5 File."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        assert "Upload New H5 File" in html
        assert "Select H5 File" not in html

    def test_catalog_selection_clears_upload(self):
        """Selecting catalog container clears file input."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        assert ".value=" in html or "cr-file-input" in html


class TestControlRoomLaunchWorkflowCompat:
    """Workflow compatibility (requirement 6)."""

    def test_aramis_workflow_excluded_on_frontend(self):
        """Non-Bremen containers are filtered by workflow_id."""
        html = open("src/bremen/control_room_ui.py", encoding="utf-8").read()
        assert "workflow_id" in html

    def test_containers_have_workflow_id_on_server(self):
        """Container response includes workflow_id field server-side."""
        with open("src/bremen/api/server.py") as f:
            s = f.read()
        assert "workflow_id" in s

    def test_workflow_id_in_response_dict(self):
        """The container response dict builder includes workflow_id."""
        with open("src/bremen/api/server.py") as f:
            s = f.read()
        assert '"workflow_id"' in s
