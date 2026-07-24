"""Tests for S3 model catalog discovery (PR0085).

Uses fake S3 clients and synthetic model packages only.
No real AWS calls. No real model artifacts.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from bremen.api.s3_model_discovery import (
    discover_models,
    _validate_catalog_uri,
    _list_candidate_manifests,
    _validate_manifest_body,
    _validate_discovery_fields,
    _resolve_artifact_key,
    _validate_loaded_package,
    CatalogDiscoveryResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_s3_client(files: dict[str, bytes]) -> Any:
    """Create a fake S3 client with pre-populated files."""
    class FakeS3Object:
        def __init__(self, body: bytes):
            self._body = body
        def read(self) -> bytes:
            return self._body

    class FakeS3Paginator:
        def __init__(self, bucket: str, prefix: str):
            self._bucket = bucket
            self._prefix = prefix
        def paginate(self, Bucket=None, Prefix=None):
            matching = []
            for key, body in files.items():
                if key.startswith(Prefix or self._prefix):
                    matching.append({"Key": key, "Size": len(body)})
            matching.sort(key=lambda x: x["Key"])
            yield {"Contents": matching}

    class FakeS3Client:
        def get_paginator(self, name):
            assert name == "list_objects_v2"
            return self
        def paginate(self, Bucket=None, Prefix=None):
            matching = []
            for key, body in files.items():
                if key.startswith(Prefix or ""):
                    matching.append({"Key": key, "Size": len(body)})
            matching.sort(key=lambda x: x["Key"])
            yield {"Contents": matching}
        def get_object(self, Bucket=None, Key=None):
            body = files.get(Key)
            if body is None:
                raise Exception(f"NoSuchKey: {Key}")
            return {"Body": FakeS3Object(body)}
        def download_file(self, Bucket=None, Key=None, Filename=None):
            body = files.get(Key)
            if body is None:
                raise Exception(f"NoSuchKey: {Key}")
            with open(Filename, "wb") as f:
                f.write(body)

    return FakeS3Client()


def _make_manifest(
    model_id: str = "test-model",
    display_name: str = "Test Model",
    workflow_id: str = "bremen",
    model_version: str = "v1.0",
    model_filename: str = "model.joblib",
    model_checksum: str | None = None,
    artifact_type: str = "bremen.joblib.model_package",
    feature_schema_version: str = "v0.1",
    threshold_version: str = "v0.1",
    threshold_value: float = 0.5,
    qc_criteria_version: str = "v0.1",
) -> bytes:
    """Create a valid manifest JSON bytes."""
    manifest = {
        "model_id": model_id,
        "display_name": display_name,
        "workflow_id": workflow_id,
        "model_version": model_version,
        "model_filename": model_filename,
        "model_checksum": model_checksum or "a" * 64,
        "artifact_type": artifact_type,
        "feature_schema_version": feature_schema_version,
        "threshold_version": threshold_version,
        "threshold_value": threshold_value,
        "qc_criteria_version": qc_criteria_version,
    }
    return json.dumps(manifest).encode("utf-8")


def _make_synthetic_package(
    coef: list[float] | None = None,
    threshold: float = 0.5,
) -> bytes:
    """Create a synthetic model package and return joblib bytes."""
    import io
    from joblib import dump

    pkg = {
        "portable_logreg": {
            "coef": coef or [0.1] * 15,
            "imputer_statistics": [0.0] * 15,
            "scaler_mean": [0.0] * 15,
            "scaler_scale": [1.0] * 15,
            "intercept": 0.0,
            "threshold": threshold,
        }
    }
    buf = io.BytesIO()
    dump(pkg, buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Catalog URI validation
# ---------------------------------------------------------------------------


class TestCatalogUriValidation:
    def test_valid_uri(self):
        bucket, prefix = _validate_catalog_uri("s3://my-bucket/models/")
        assert bucket == "my-bucket"
        assert prefix == "models/"

    def test_valid_uri_no_trailing_slash(self):
        bucket, prefix = _validate_catalog_uri("s3://my-bucket/models")
        assert bucket == "my-bucket"
        assert prefix == "models/"

    def test_valid_uri_root_prefix(self):
        bucket, prefix = _validate_catalog_uri("s3://my-bucket/")
        assert bucket == "my-bucket"
        assert prefix == ""

    def test_invalid_uri_empty(self):
        with pytest.raises(ValueError, match="non-empty"):
            _validate_catalog_uri("")

    def test_invalid_uri_not_s3(self):
        with pytest.raises(ValueError, match="s3://"):
            _validate_catalog_uri("https://example.com/models/")

    def test_invalid_uri_no_bucket(self):
        with pytest.raises(ValueError, match="no bucket"):
            _validate_catalog_uri("s3://")


# ---------------------------------------------------------------------------
# S3 listing
# ---------------------------------------------------------------------------


class TestS3Listing:
    def test_list_immediate_child_manifests(self):
        """Only manifest.json at depth prefix + one directory level."""
        s3 = _make_s3_client({
            "models/v1/manifest.json": b"{}",
            "models/v2/manifest.json": b"{}",
            "models/v1/model.joblib": b"binary",
            "models/deep/nested/manifest.json": b"{}",
            "models/other.txt": b"text",
        })
        keys = _list_candidate_manifests(s3, "bucket", "models/")
        assert len(keys) == 2
        assert "models/v1/manifest.json" in keys
        assert "models/v2/manifest.json" in keys
        assert "models/deep/nested/manifest.json" not in keys

    def test_deterministic_lexicographic_order(self):
        """Keys are sorted lexicographically."""
        s3 = _make_s3_client({
            "models/z/manifest.json": b"{}",
            "models/a/manifest.json": b"{}",
            "models/m/manifest.json": b"{}",
        })
        keys = _list_candidate_manifests(s3, "bucket", "models/")
        assert keys == ["models/a/manifest.json", "models/m/manifest.json", "models/z/manifest.json"]

    def test_pagination(self):
        """All pages are discovered."""
        files = {}
        for i in range(15):
            files[f"models/v{i}/manifest.json"] = b"{}"
        s3 = _make_s3_client(files)
        keys = _list_candidate_manifests(s3, "bucket", "models/")
        assert len(keys) == 15

    def test_zero_candidates(self):
        s3 = _make_s3_client({})
        keys = _list_candidate_manifests(s3, "bucket", "models/")
        assert keys == []


# ---------------------------------------------------------------------------
# Manifest validation
# ---------------------------------------------------------------------------


class TestManifestValidation:
    def test_valid_manifest_passes(self):
        manifest = _make_manifest()
        data = _validate_manifest_body(manifest)
        assert data["model_id"] == "test-model"

    def test_oversized_manifest_rejected(self):
        data = b"x" * 70000
        with pytest.raises(ValueError, match="exceeds maximum size"):
            _validate_manifest_body(data)

    def test_invalid_json_rejected(self):
        with pytest.raises(ValueError, match="JSON"):
            _validate_manifest_body(b"not json")

    def test_missing_base_fields_rejected(self):
        manifest = json.dumps({"model_id": "test"}).encode("utf-8")
        with pytest.raises(ValueError, match="validation failed"):
            _validate_manifest_body(manifest)

    def test_invalid_threshold_version_rejected(self):
        manifest = _make_manifest(threshold_version="")
        with pytest.raises(ValueError, match="validation failed"):
            _validate_manifest_body(manifest)

    def test_invalid_threshold_value_rejected(self):
        manifest = _make_manifest(threshold_value="not-a-number")
        with pytest.raises(ValueError, match="validation failed"):
            _validate_manifest_body(manifest)


# ---------------------------------------------------------------------------
# Discovery field validation
# ---------------------------------------------------------------------------


class TestDiscoveryFieldValidation:
    def test_valid_discovery_fields(self):
        data = {"model_id": "my-model", "display_name": "My Model", "workflow_id": "bremen"}
        result = _validate_discovery_fields(data)
        assert result["model_id"] == "my-model"

    def test_missing_model_id(self):
        with pytest.raises(ValueError, match="model_id"):
            _validate_discovery_fields({"display_name": "Test", "workflow_id": "bremen"})

    def test_missing_display_name(self):
        with pytest.raises(ValueError, match="display_name"):
            _validate_discovery_fields({"model_id": "test", "workflow_id": "bremen"})

    def test_missing_workflow_id(self):
        with pytest.raises(ValueError, match="workflow_id"):
            _validate_discovery_fields({"model_id": "test", "display_name": "Test"})

    def test_invalid_model_id_pattern(self):
        with pytest.raises(ValueError, match="model_id"):
            _validate_discovery_fields({
                "model_id": "UPPERCASE", "display_name": "Test", "workflow_id": "bremen",
            })

    def test_invalid_model_id_start_with_number(self):
        result = _validate_discovery_fields({
            "model_id": "1test", "display_name": "Test", "workflow_id": "bremen",
        })
        assert result["model_id"] == "1test"

    def test_model_id_too_long(self):
        with pytest.raises(ValueError, match="model_id"):
            _validate_discovery_fields({
                "model_id": "a" * 65, "display_name": "Test", "workflow_id": "bremen",
            })

    def test_empty_display_name(self):
        with pytest.raises(ValueError, match="display_name"):
            _validate_discovery_fields({
                "model_id": "test", "display_name": "  ", "workflow_id": "bremen",
            })

    def test_display_name_too_long(self):
        with pytest.raises(ValueError, match="display_name"):
            _validate_discovery_fields({
                "model_id": "test", "display_name": "x" * 81, "workflow_id": "bremen",
            })

    def test_wrong_workflow_id(self):
        with pytest.raises(ValueError, match="workflow_id"):
            _validate_discovery_fields({
                "model_id": "test", "display_name": "Test", "workflow_id": "aramis",
            })


# ---------------------------------------------------------------------------
# Artifact resolution
# ---------------------------------------------------------------------------


class TestArtifactResolution:
    def test_valid_artifact_key(self):
        key = _resolve_artifact_key(
            "models/v1/manifest.json", "model.joblib", "models/"
        )
        assert key == "models/v1/model.joblib"

    def test_path_traversal_rejected(self):
        with pytest.raises(ValueError, match="path traversal"):
            _resolve_artifact_key(
                "models/v1/manifest.json", "../outside.joblib", "models/"
            )

    def test_absolute_path_rejected(self):
        with pytest.raises(ValueError, match="path traversal"):
            _resolve_artifact_key(
                "models/v1/manifest.json", "/etc/passwd", "models/"
            )

    def test_artifact_outside_prefix_rejected(self):
        with pytest.raises(ValueError, match="outside"):
            _resolve_artifact_key(
                "other/v1/manifest.json", "model.joblib", "models/"
            )


# ---------------------------------------------------------------------------
# Package validation
# ---------------------------------------------------------------------------


class TestPackageValidation:
    def test_valid_package(self):
        pkg = {"portable_logreg": {"coef": [0.1]*15, "intercept": 0.0, "threshold": 0.5}}
        assert _validate_loaded_package(pkg, {"feature_schema_version": "v0.1"})

    def test_missing_portable_logreg(self):
        with pytest.raises(ValueError, match="portable_logreg"):
            _validate_loaded_package({}, {"feature_schema_version": "v0.1"})

    def test_missing_coef(self):
        with pytest.raises(ValueError, match="coef"):
            _validate_loaded_package(
                {"portable_logreg": {"intercept": 0.0, "threshold": 0.5}},
                {"feature_schema_version": "v0.1"},
            )

    def test_unsupported_feature_schema(self):
        with pytest.raises(ValueError, match="feature schema"):
            _validate_loaded_package(
                {"portable_logreg": {"coef": [0.1]*15, "intercept": 0.0, "threshold": 0.5}},
                {"feature_schema_version": "v99.0"},
            )

    def test_invalid_threshold(self):
        with pytest.raises(ValueError, match="threshold"):
            _validate_loaded_package(
                {"portable_logreg": {"coef": [0.1]*15, "intercept": 0.0, "threshold": -1}},
                {"feature_schema_version": "v0.1"},
            )


# ---------------------------------------------------------------------------
# Full discovery pipeline
# ---------------------------------------------------------------------------


class TestFullDiscovery:
    def test_zero_candidates(self):
        s3 = _make_s3_client({})
        result = discover_models("s3://bucket/models/", _s3_client=s3)
        assert result.catalog_status == "no_valid_models"
        assert result.candidate_count == 0
        assert result.available_count == 0

    def test_one_valid_candidate(self, tmp_path):
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        manifest = _make_manifest(model_checksum=checksum)
        s3 = _make_s3_client({
            "models/v1/manifest.json": manifest,
            "models/v1/model.joblib": pkg_bytes,
        })
        result = discover_models("s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3)
        assert result.catalog_status == "available"
        assert result.candidate_count == 1
        assert result.available_count == 1
        assert result.rejected_count == 0
        assert len(result.entries) == 1
        assert result.entries[0].model_id == "test-model"

    def test_multiple_valid_candidates(self, tmp_path):
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        s3 = _make_s3_client({
            "models/a/manifest.json": _make_manifest(model_id="model-a", display_name="Model A", model_checksum=checksum),
            "models/a/model.joblib": pkg_bytes,
            "models/b/manifest.json": _make_manifest(model_id="model-b", display_name="Model B", model_checksum=checksum),
            "models/b/model.joblib": pkg_bytes,
        })
        result = discover_models("s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3)
        assert result.catalog_status == "available"
        assert result.candidate_count == 2
        assert result.available_count == 2
        assert len(result.entries) == 2
        assert result.entries[0].model_id == "model-a"
        assert result.entries[1].model_id == "model-b"

    def test_more_than_50_candidates(self):
        files = {}
        for i in range(55):
            files[f"models/v{i}/manifest.json"] = b"{}"
        s3 = _make_s3_client(files)
        result = discover_models("s3://bucket/models/", _s3_client=s3)
        assert result.catalog_status == "discovery_failed"
        assert result.error_category == "too_many_candidates"
        assert result.available_count == 0

    def test_oversized_manifest_skipped(self, tmp_path):
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        oversized = b"x" * 70000
        s3 = _make_s3_client({
            "models/v1/manifest.json": oversized,
            "models/v2/manifest.json": _make_manifest(model_id="model-b", display_name="Model B", model_checksum=checksum),
            "models/v2/model.joblib": pkg_bytes,
        })
        result = discover_models("s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3)
        assert result.catalog_status == "available"
        assert result.candidate_count == 2
        assert result.available_count == 1
        assert result.rejected_count == 1

    def test_invalid_json_skipped(self, tmp_path):
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        s3 = _make_s3_client({
            "models/v1/manifest.json": b"not json",
            "models/v2/manifest.json": _make_manifest(model_id="model-b", display_name="Model B", model_checksum=checksum),
            "models/v2/model.joblib": pkg_bytes,
        })
        result = discover_models("s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3)
        assert result.catalog_status == "available"
        assert result.available_count == 1
        assert result.rejected_count == 1

    def test_missing_base_fields_skipped(self, tmp_path):
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        bad_manifest = json.dumps({"model_id": "bad"}).encode("utf-8")
        s3 = _make_s3_client({
            "models/v1/manifest.json": bad_manifest,
            "models/v2/manifest.json": _make_manifest(model_id="model-b", display_name="Model B", model_checksum=checksum),
            "models/v2/model.joblib": pkg_bytes,
        })
        result = discover_models("s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3)
        assert result.catalog_status == "available"
        assert result.available_count == 1
        assert result.rejected_count == 1

    def test_missing_discovery_fields_skipped(self, tmp_path):
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        # Valid base fields but missing discovery fields
        bad_manifest = json.dumps({
            "model_version": "v1.0",
            "model_filename": "model.joblib",
            "model_checksum": checksum,
            "artifact_type": "bremen.joblib.model_package",
            "feature_schema_version": "v0.1",
            "threshold_version": "v0.1",
            "threshold_value": 0.5,
            "qc_criteria_version": "v0.1",
        }).encode("utf-8")
        s3 = _make_s3_client({
            "models/v1/manifest.json": bad_manifest,
            "models/v2/manifest.json": _make_manifest(model_id="model-b", display_name="Model B", model_checksum=checksum),
            "models/v2/model.joblib": pkg_bytes,
        })
        result = discover_models("s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3)
        assert result.catalog_status == "available"
        assert result.available_count == 1
        assert result.rejected_count == 1

    def test_checksum_mismatch_rejected(self, tmp_path):
        pkg_bytes = _make_synthetic_package()
        wrong_checksum = "b" * 64
        manifest = _make_manifest(model_checksum=wrong_checksum)
        s3 = _make_s3_client({
            "models/v1/manifest.json": manifest,
            "models/v1/model.joblib": pkg_bytes,
        })
        result = discover_models("s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3)
        assert result.catalog_status == "no_valid_models"
        assert result.available_count == 0
        assert result.rejected_count == 1

    def test_missing_artifact_rejected(self, tmp_path):
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        manifest = _make_manifest(model_checksum=checksum)
        s3 = _make_s3_client({
            "models/v1/manifest.json": manifest,
            # No model.joblib file
        })
        result = discover_models("s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3)
        assert result.catalog_status == "no_valid_models"
        assert result.available_count == 0
        assert result.rejected_count == 1

    def test_s3_listing_failure(self):
        class FailingS3Client:
            def get_paginator(self, name):
                raise Exception("AccessDenied")
        result = discover_models("s3://bucket/models/", _s3_client=FailingS3Client())
        assert result.catalog_status == "discovery_failed"
        assert result.error_category == "s3_listing_failure"

    def test_invalid_catalog_uri(self):
        result = discover_models("invalid-uri")
        assert result.catalog_status == "discovery_failed"
        assert result.error_category == "invalid_uri"

    def test_partial_success(self, tmp_path):
        """2 valid, 2 invalid -> 2 available, 2 rejected."""
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        s3 = _make_s3_client({
            "models/a/manifest.json": _make_manifest(model_id="model-a", display_name="Model A", model_checksum=checksum),
            "models/a/model.joblib": pkg_bytes,
            "models/b/manifest.json": _make_manifest(model_id="model-b", display_name="Model B", model_checksum=checksum),
            "models/b/model.joblib": pkg_bytes,
            "models/c/manifest.json": b"invalid json",
            "models/d/manifest.json": json.dumps({"model_id": "bad"}).encode("utf-8"),
        })
        result = discover_models("s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3)
        assert result.catalog_status == "available"
        assert result.candidate_count == 4
        assert result.available_count == 2
        assert result.rejected_count == 2
        assert len(result.entries) == 2


# ---------------------------------------------------------------------------
# Base manifest rejection via full discovery pipeline
# ---------------------------------------------------------------------------


class TestBaseManifestRejectionPipeline:
    """Pipeline-level rejection of base manifest fields.

    Each test pairs one bad manifest with one good manifest and
    runs ``discover_models()`` to prove the bad manifest is rejected
    before artifact staging or registry insertion.
    """

    def test_invalid_qc_criteria_version_rejected(self, tmp_path):
        """Empty qc_criteria_version is rejected by the discovery pipeline."""
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        # Bad: empty qc_criteria_version. All other fields are valid.
        bad_manifest = _make_manifest(
            model_id="bad-qc",
            display_name="Bad QC",
            model_checksum=checksum,
            qc_criteria_version="",
        )
        s3 = _make_s3_client({
            "models/v1/manifest.json": bad_manifest,
            # No artifact for v1 — rejection happens in Phase 1 before staging.
            "models/v2/manifest.json": _make_manifest(
                model_id="good-model",
                display_name="Good",
                model_checksum=checksum,
            ),
            "models/v2/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        assert result.catalog_status == "available"
        assert result.candidate_count == 2
        assert result.available_count == 1
        assert result.rejected_count == 1
        assert len(result.entries) == 1
        assert result.entries[0].model_id == "good-model"
        # Confirm no private storage exposed in result
        assert result.error_category is None

    def test_invalid_artifact_type_rejected(self, tmp_path):
        """Wrong artifact_type is rejected by the discovery pipeline."""
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        # Bad: artifact_type is not bremen.joblib.model_package.
        bad_manifest = _make_manifest(
            model_id="bad-art",
            display_name="Bad Artifact",
            model_checksum=checksum,
            artifact_type="wrong.business.type",
        )
        s3 = _make_s3_client({
            "models/v1/manifest.json": bad_manifest,
            "models/v2/manifest.json": _make_manifest(
                model_id="good-model",
                display_name="Good",
                model_checksum=checksum,
            ),
            "models/v2/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        assert result.catalog_status == "available"
        assert result.candidate_count == 2
        assert result.available_count == 1
        assert result.rejected_count == 1
        assert len(result.entries) == 1
        assert result.entries[0].model_id == "good-model"
        assert result.error_category is None

    def test_invalid_model_version_rejected(self, tmp_path):
        """Empty model_version is rejected by the discovery pipeline."""
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        # Bad: empty model_version.
        bad_manifest = _make_manifest(
            model_id="bad-ver",
            display_name="Bad Version",
            model_checksum=checksum,
            model_version="",
        )
        s3 = _make_s3_client({
            "models/v1/manifest.json": bad_manifest,
            "models/v2/manifest.json": _make_manifest(
                model_id="good-model",
                display_name="Good",
                model_checksum=checksum,
            ),
            "models/v2/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        assert result.catalog_status == "available"
        assert result.candidate_count == 2
        assert result.available_count == 1
        assert result.rejected_count == 1
        assert len(result.entries) == 1
        assert result.entries[0].model_id == "good-model"
        assert result.error_category is None


# ---------------------------------------------------------------------------
# Duplicate model_id tests
# ---------------------------------------------------------------------------


class TestDuplicateModelId:
    def test_two_duplicates_no_unique(self, tmp_path):
        """Two duplicate entries and no unique entries -> 0 available."""
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        s3 = _make_s3_client({
            "models/a/manifest.json": _make_manifest(model_id="dup-model", display_name="Dup A", model_checksum=checksum),
            "models/a/model.joblib": pkg_bytes,
            "models/b/manifest.json": _make_manifest(model_id="dup-model", display_name="Dup B", model_checksum=checksum),
            "models/b/model.joblib": pkg_bytes,
        })
        result = discover_models("s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3)
        assert result.catalog_status == "no_valid_models"
        assert result.available_count == 0
        assert result.rejected_count == 2

    def test_two_duplicates_plus_one_unique(self, tmp_path):
        """Two duplicates plus one unique -> 1 available, 2 rejected."""
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        s3 = _make_s3_client({
            "models/a/manifest.json": _make_manifest(model_id="dup-model", display_name="Dup A", model_checksum=checksum),
            "models/a/model.joblib": pkg_bytes,
            "models/b/manifest.json": _make_manifest(model_id="dup-model", display_name="Dup B", model_checksum=checksum),
            "models/b/model.joblib": pkg_bytes,
            "models/c/manifest.json": _make_manifest(model_id="unique-model", display_name="Unique", model_checksum=checksum),
            "models/c/model.joblib": pkg_bytes,
        })
        result = discover_models("s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3)
        assert result.catalog_status == "available"
        assert result.available_count == 1
        assert result.rejected_count == 2
        assert len(result.entries) == 1
        assert result.entries[0].model_id == "unique-model"

    def test_three_occurrences_of_one_duplicate(self, tmp_path):
        """Three occurrences of one duplicate model_id -> all rejected."""
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        s3 = _make_s3_client({
            "models/a/manifest.json": _make_manifest(model_id="dup-model", display_name="Dup A", model_checksum=checksum),
            "models/a/model.joblib": pkg_bytes,
            "models/b/manifest.json": _make_manifest(model_id="dup-model", display_name="Dup B", model_checksum=checksum),
            "models/b/model.joblib": pkg_bytes,
            "models/c/manifest.json": _make_manifest(model_id="dup-model", display_name="Dup C", model_checksum=checksum),
            "models/c/model.joblib": pkg_bytes,
        })
        result = discover_models("s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3)
        assert result.catalog_status == "no_valid_models"
        assert result.available_count == 0
        assert result.rejected_count == 3

    def test_deterministic_rejected_count(self, tmp_path):
        """Duplicate rejection produces deterministic counts."""
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        s3 = _make_s3_client({
            "models/a/manifest.json": _make_manifest(model_id="dup-model", display_name="Dup A", model_checksum=checksum),
            "models/a/model.joblib": pkg_bytes,
            "models/b/manifest.json": _make_manifest(model_id="unique", display_name="Unique", model_checksum=checksum),
            "models/b/model.joblib": pkg_bytes,
        })
        result1 = discover_models("s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3)
        result2 = discover_models("s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3)
        assert result1.available_count == result2.available_count
        assert result1.rejected_count == result2.rejected_count


# ---------------------------------------------------------------------------
# No S3 work after startup
# ---------------------------------------------------------------------------


class TestNoPostStartupS3:
    def test_discovery_does_not_call_s3_after_return(self, tmp_path):
        """After discover_models returns, no S3 calls are made."""
        call_count = [0]

        class TrackingS3Client:
            def get_paginator(self, name):
                call_count[0] += 1
                return self
            def paginate(self, Bucket=None, Prefix=None):
                return [{"Contents": []}]

        discover_models("s3://bucket/models/", _s3_client=TrackingS3Client())
        # No further S3 calls after discovery
        assert call_count[0] == 1
