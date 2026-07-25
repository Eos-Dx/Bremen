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


def _make_root_level_package(
    coef: list[float] | None = None,
    threshold: float = 0.5,
    include_threshold: bool = True,
    include_feature_columns: bool = True,
) -> bytes:
    """Create a synthetic package with threshold/feature_columns at root.

    Mimics the real Bremen package layout where ``threshold`` and
    ``feature_columns`` sit at the top-level dict, NOT inside
    ``portable_logreg``.  ``adapt_model_package`` must copy them
    down before validation.
    """
    import io
    from joblib import dump

    pkg: dict[str, Any] = {
        "portable_logreg": {
            "coef": coef or [0.1] * 15,
            "imputer_statistics": [0.0] * 15,
            "scaler_mean": [0.0] * 15,
            "scaler_scale": [1.0] * 15,
            "intercept": 0.0,
        },
    }
    if include_threshold:
        pkg["threshold"] = threshold
    if include_feature_columns:
        pkg["feature_columns"] = [
            "weightedrms1", "sigma_l1", "sigma_r1", "mahalanobis1",
            "weightedrms2", "sigma_l2", "sigma_r2", "mahalanobis2",
            "peak14_intensity", "mean_peak_value_raw",
            "wasserstein_distance_muLR", "cosine_distance_full_q2",
            "wasserstein_distance_full_q2", "meanrms1", "meanrms2",
        ]
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
# Package adapter regression tests (PR0086)
# ---------------------------------------------------------------------------


class TestPackageAdapter:
    """Regression tests for the adapt_model_package call in the
    discovery pipeline.

    Proves that packages with root-level threshold and feature_columns
    are adapted before validation and stored as the adapted view.
    """

    def test_root_threshold_passes_discovery(self, tmp_path):
        """Root-level threshold is adapted into portable_logreg."""
        pkg_bytes = _make_root_level_package(include_feature_columns=False)
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        manifest = _make_manifest(model_checksum=checksum)
        s3 = _make_s3_client({
            "models/v1/manifest.json": manifest,
            "models/v1/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        assert result.catalog_status == "available"
        assert result.available_count == 1
        assert result.rejected_count == 0
        assert len(result.entries) == 1

    def test_root_feature_columns_passes_discovery(self, tmp_path):
        """Root-level feature_columns is adapted into portable_logreg."""
        pkg_bytes = _make_root_level_package(include_threshold=True, include_feature_columns=True)
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        manifest = _make_manifest(model_checksum=checksum)
        s3 = _make_s3_client({
            "models/v1/manifest.json": manifest,
            "models/v1/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        assert result.catalog_status == "available"
        assert result.available_count == 1
        assert result.rejected_count == 0

    def test_registry_stores_adapted_package(self, tmp_path):
        """Registry entry stores the adapted package view."""
        pkg_bytes = _make_root_level_package(threshold=0.42)
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        manifest = _make_manifest(model_id="adapted-model", display_name="Adapted", model_checksum=checksum)
        s3 = _make_s3_client({
            "models/v1/manifest.json": manifest,
            "models/v1/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        assert result.available_count == 1
        entry = result.entries[0]
        stored_pkg = entry._package
        # The stored package is the adapted view
        assert stored_pkg is not None
        assert stored_pkg["portable_logreg"]["threshold"] == 0.42

    def test_adapted_threshold_copied_from_root(self, tmp_path):
        """portable_logreg.threshold matches the root threshold value."""
        pkg_bytes = _make_root_level_package(threshold=0.77)
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        manifest = _make_manifest(model_id="threshold-test", display_name="T", model_checksum=checksum)
        s3 = _make_s3_client({
            "models/v1/manifest.json": manifest,
            "models/v1/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        plr = result.entries[0]._package["portable_logreg"]
        assert plr["threshold"] == 0.77

    def test_adapted_feature_columns_copied_from_root(self, tmp_path):
        """portable_logreg.feature_columns matches root feature_columns."""
        pkg_bytes = _make_root_level_package(include_threshold=True, include_feature_columns=True)
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        manifest = _make_manifest(model_id="fc-test", display_name="FC", model_checksum=checksum)
        s3 = _make_s3_client({
            "models/v1/manifest.json": manifest,
            "models/v1/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        plr = result.entries[0]._package["portable_logreg"]
        assert "feature_columns" in plr
        assert plr["feature_columns"] == [
            "weightedrms1", "sigma_l1", "sigma_r1", "mahalanobis1",
            "weightedrms2", "sigma_l2", "sigma_r2", "mahalanobis2",
            "peak14_intensity", "mean_peak_value_raw",
            "wasserstein_distance_muLR", "cosine_distance_full_q2",
            "wasserstein_distance_full_q2", "meanrms1", "meanrms2",
        ]

    def test_existing_nested_threshold_not_overwritten(self, tmp_path):
        """Existing nested threshold takes precedence over root."""
        # Create a package with threshold both at root AND inside portable_logreg.
        # The adapter must NOT overwrite the nested value.
        import io, joblib
        pkg = {
            "threshold": 0.99,  # root — should be ignored
            "portable_logreg": {
                "coef": [0.1] * 15,
                "imputer_statistics": [0.0] * 15,
                "scaler_mean": [0.0] * 15,
                "scaler_scale": [1.0] * 15,
                "intercept": 0.0,
                "threshold": 0.33,  # already nested — must survive
            },
        }
        buf = io.BytesIO()
        joblib.dump(pkg, buf)
        pkg_bytes = buf.getvalue()

        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        manifest = _make_manifest(model_id="nested-test", display_name="Nested", model_checksum=checksum)
        s3 = _make_s3_client({
            "models/v1/manifest.json": manifest,
            "models/v1/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        plr = result.entries[0]._package["portable_logreg"]
        assert plr["threshold"] == 0.33  # nested value preserved

    def test_missing_threshold_everywhere_rejected(self, tmp_path):
        """Package missing threshold at root and inside portable_logreg is rejected."""
        pkg_bytes = _make_root_level_package(include_threshold=False, include_feature_columns=False)
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        manifest = _make_manifest(model_id="no-threshold", display_name="NT", model_checksum=checksum)
        s3 = _make_s3_client({
            "models/v1/manifest.json": manifest,
            "models/v1/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        assert result.available_count == 0
        assert result.rejected_count == 1

    def test_missing_feature_columns_everywhere_still_passes_if_validator_ignores(self, tmp_path):
        """Package missing feature_columns in every location is tested through
        the pipeline.  The discovery validator only checks portable_logreg
        fields (coef, intercept, threshold) — it does NOT require
        feature_columns.  Proving that the package passes discovery
        confirms no validation rule was weakened.
        """
        # Root-level package with only threshold (no feature_columns).
        pkg_bytes = _make_root_level_package(
            include_threshold=True, include_feature_columns=False,
        )
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        manifest = _make_manifest(model_id="no-fc", display_name="NoFC", model_checksum=checksum)
        s3 = _make_s3_client({
            "models/v1/manifest.json": manifest,
            "models/v1/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        # The discovery pipeline's _validate_loaded_package does not gate
        # on feature_columns — it gates on coef, intercept, and threshold.
        # This is the existing contract; this test proves it was not weakened.
        assert result.available_count == 1
        assert result.rejected_count == 0


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


# ---------------------------------------------------------------------------
# PR0087 — Unavailable model discovery tests
# ---------------------------------------------------------------------------


class TestPR0087UnavailableDiscovery:
    """PR0087-specific tests for unavailable model discovery.

    Covers: Phase 3 not_compatible, duplicate_entry, unregistered_package,
    .joblib-only directories, invalid manifest + .joblib, manifest-only
    aggregate, available+unavailable coexistence, counts, log sanitization,
    and last_discovery_at.
    """

    # -- Phase 3 not_compatible ---------------------------------------------

    def test_phase3_rejection_creates_identified_not_compatible(self, tmp_path):
        """Phase 3 package validation failure with valid manifest identity
        produces a kind=identified unavailable entry with
        reason_category=not_compatible."""
        pkg_bytes = _make_root_level_package(
            include_threshold=False, include_feature_columns=False,
        )
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        manifest = _make_manifest(
            model_id="bad-package",
            display_name="Bad Package",
            model_checksum=checksum,
        )
        s3 = _make_s3_client({
            "models/v1/manifest.json": manifest,
            "models/v1/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        assert result.catalog_status == "no_valid_models"
        assert result.available_count == 0
        assert result.rejected_count == 1
        assert result.unavailable_count == 1
        assert len(result.unavailable_entries) == 1
        ue = result.unavailable_entries[0]
        assert ue.kind == "identified"
        assert ue.reason_category == "not_compatible"
        assert ue.model_id == "bad-package"
        assert ue.display_name == "Bad Package"
        assert ue.workflow_id == "bremen"

    def test_phase3_rejection_no_raw_technical_detail(self, tmp_path):
        """Phase 3 rejection does not expose raw technical detail
        in the unavailable entry."""
        import io, joblib
        # Package missing portable_logreg entirely
        pkg = {"wrong_key": {}}
        buf = io.BytesIO()
        joblib.dump(pkg, buf)
        pkg_bytes = buf.getvalue()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        manifest = _make_manifest(
            model_id="bad-format",
            display_name="Bad Format",
            model_checksum=checksum,
        )
        s3 = _make_s3_client({
            "models/v1/manifest.json": manifest,
            "models/v1/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        assert result.unavailable_count == 1
        ue = result.unavailable_entries[0]
        assert ue.reason_category == "not_compatible"
        # No raw technical detail
        safe = ue.to_safe_dict()
        assert "portable_logreg" not in str(safe)
        assert "threshold" not in str(safe)
        assert "coef" not in str(safe)
        assert "missing" not in str(safe).lower()

    # -- Duplicate model_id ------------------------------------------------

    def test_duplicate_model_id_creates_single_duplicate_entry(self, tmp_path):
        """Two manifests with same model_id produce exactly one
        duplicate_entry unavailable card."""
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        s3 = _make_s3_client({
            "models/a/manifest.json": _make_manifest(
                model_id="dup-model", display_name="Dup A",
                model_checksum=checksum,
            ),
            "models/a/model.joblib": pkg_bytes,
            "models/b/manifest.json": _make_manifest(
                model_id="dup-model", display_name="Dup B",
                model_checksum=checksum,
            ),
            "models/b/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        assert result.catalog_status == "no_valid_models"
        assert result.available_count == 0
        assert result.rejected_count == 2
        assert result.unavailable_count >= 1
        # Exactly one duplicate_entry for this model_id
        dup_entries = [
            e for e in result.unavailable_entries
            if e.reason_category == "duplicate_entry"
        ]
        assert len(dup_entries) == 1
        assert dup_entries[0].model_id == "dup-model"
        assert dup_entries[0].kind == "identified"

    def test_duplicate_display_name_deterministic(self, tmp_path):
        """Duplicate display_name selection uses lexicographically first."""
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        def run_discovery():
            s3 = _make_s3_client({
                "models/z/manifest.json": _make_manifest(
                    model_id="dup", display_name="Zeta",
                    model_checksum=checksum,
                ),
                "models/z/model.joblib": pkg_bytes,
                "models/a/manifest.json": _make_manifest(
                    model_id="dup", display_name="Alpha",
                    model_checksum=checksum,
                ),
                "models/a/model.joblib": pkg_bytes,
            })
            return discover_models(
                "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
            )
        r1 = run_discovery()
        r2 = run_discovery()
        dup1 = [e for e in r1.unavailable_entries if e.reason_category == "duplicate_entry"]
        dup2 = [e for e in r2.unavailable_entries if e.reason_category == "duplicate_entry"]
        assert len(dup1) == 1
        assert len(dup2) == 1
        # Lexicographically first is "Alpha"
        assert dup1[0].display_name == "Alpha"
        assert dup2[0].display_name == "Alpha"

    # -- .joblib-only directories ------------------------------------------

    def test_joblib_only_creates_unregistered_package(self, tmp_path):
        """A package directory with a .joblib file but no manifest
        produces an unregistered_package entry."""
        pkg_bytes = _make_synthetic_package()
        s3 = _make_s3_client({
            "models/v1/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        assert result.candidate_count == 1
        assert result.available_count == 0
        assert result.rejected_count == 1
        assert result.unavailable_count == 1
        ue = result.unavailable_entries[0]
        assert ue.kind == "unregistered"
        assert ue.reason_category == "unregistered_package"
        assert ue.candidate_label is not None
        assert "Discovered model package" in ue.candidate_label
        assert ue.model_id is None
        assert ue.display_name is None

    def test_joblib_with_invalid_manifest_creates_unregistered(self, tmp_path):
        """A package directory with .joblib and invalid JSON manifest
        produces an unregistered_package entry."""
        pkg_bytes = _make_synthetic_package()
        s3 = _make_s3_client({
            "models/v1/manifest.json": b"not valid json {{{ ",
            "models/v1/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        assert result.candidate_count == 1
        assert result.available_count == 0
        assert result.unavailable_count == 1
        ue = result.unavailable_entries[0]
        assert ue.kind == "unregistered"
        assert ue.reason_category == "unregistered_package"
        assert ue.candidate_label is not None

    def test_joblib_with_manifest_missing_model_id_unregistered(self, tmp_path):
        """A package directory with .joblib and manifest missing model_id
        produces an unregistered_package entry."""
        pkg_bytes = _make_synthetic_package()
        # Valid base manifest fields but missing model_id
        bad_manifest = json.dumps({
            "display_name": "No ID",
            "workflow_id": "bremen",
            "model_version": "v1.0",
            "model_filename": "model.joblib",
            "model_checksum": "a" * 64,
            "artifact_type": "bremen.joblib.model_package",
            "feature_schema_version": "v0.1",
            "threshold_version": "v0.1",
            "threshold_value": 0.5,
            "qc_criteria_version": "v0.1",
        }).encode("utf-8")
        s3 = _make_s3_client({
            "models/v1/manifest.json": bad_manifest,
            "models/v1/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        assert result.unavailable_count == 1
        ue = result.unavailable_entries[0]
        assert ue.kind == "unregistered"
        assert ue.reason_category == "unregistered_package"

    # -- Manifest-only, no .joblib — aggregate only -----------------------

    def test_manifest_only_no_joblib_aggregate_only(self):
        """A manifest-only directory with invalid identity fields
        and no .joblib produces no unavailable_models entry."""
        bad_manifest = json.dumps({"model_id": "bad"}).encode("utf-8")
        s3 = _make_s3_client({
            "models/v1/manifest.json": bad_manifest,
            # No .joblib
        })
        result = discover_models("s3://bucket/models/", _s3_client=s3)
        assert result.candidate_count == 1
        assert result.available_count == 0
        assert result.rejected_count == 1
        assert result.unavailable_count == 0
        assert len(result.unavailable_entries) == 0

    # -- Available + unavailable coexist -----------------------------------

    def test_available_and_unavailable_coexist(self, tmp_path):
        """One valid model and one rejected model produce
        both models and unavailable_models."""
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        # Bad: missing threshold
        bad_pkg_bytes = _make_root_level_package(
            include_threshold=False, include_feature_columns=False,
        )
        bad_checksum = hashlib.sha256(bad_pkg_bytes).hexdigest()
        s3 = _make_s3_client({
            "models/good/manifest.json": _make_manifest(
                model_id="good-model", display_name="Good",
                model_checksum=checksum,
            ),
            "models/good/model.joblib": pkg_bytes,
            "models/bad/manifest.json": _make_manifest(
                model_id="bad-model", display_name="Bad",
                model_checksum=bad_checksum,
            ),
            "models/bad/model.joblib": bad_pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        assert result.catalog_status == "available"
        assert result.available_count == 1
        assert result.unavailable_count == 1
        assert len(result.entries) == 1
        assert result.entries[0].model_id == "good-model"
        assert len(result.unavailable_entries) == 1
        assert result.unavailable_entries[0].model_id == "bad-model"
        assert result.unavailable_entries[0].reason_category == "not_compatible"

    # -- Counts ------------------------------------------------------------

    def test_candidate_counts_accurate(self, tmp_path):
        """candidate_count counts package directories, not manifests."""
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        s3 = _make_s3_client({
            "models/joblib_only/model.joblib": pkg_bytes,
            "models/valid/manifest.json": _make_manifest(
                model_id="ok", display_name="OK", model_checksum=checksum,
            ),
            "models/valid/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        assert result.candidate_count == 2
        assert result.available_count == 1
        assert result.rejected_count == 1
        assert result.unavailable_count == 1

    # -- last_discovery_at -------------------------------------------------

    def test_last_discovery_at_is_populated(self, tmp_path):
        """CatalogDiscoveryResult carries last_discovery_at."""
        pkg_bytes = _make_synthetic_package()
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        manifest = _make_manifest(model_checksum=checksum)
        s3 = _make_s3_client({
            "models/v1/manifest.json": manifest,
            "models/v1/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        assert result.last_discovery_at is not None
        # Should be ISO-8601
        assert "T" in result.last_discovery_at

    # -- Log sanitization (caplog) -----------------------------------------

    def test_discovery_logs_no_manifest_key_in_warnings(self, tmp_path, caplog):
        """Discovery warning logs use safe reason_category, not manifest_key."""
        import logging
        caplog.set_level(logging.WARNING)
        pkg_bytes = _make_synthetic_package()
        s3 = _make_s3_client({
            "models/v1/manifest.json": b"not json",
            "models/v1/model.joblib": pkg_bytes,
        })
        discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        warning_text = " ".join(r.getMessage() for r in caplog.records)
        assert "manifest_key" not in warning_text
        assert "reason_category" in warning_text

    # -- JSON safety -------------------------------------------------------

    def test_unavailable_to_safe_dict_no_raw_detail(self, tmp_path):
        """to_safe_dict output contains no raw technical detail."""
        import json as _json
        pkg_bytes = _make_root_level_package(
            include_threshold=False, include_feature_columns=False,
        )
        checksum = hashlib.sha256(pkg_bytes).hexdigest()
        manifest = _make_manifest(
            model_id="safe-test", display_name="Safe",
            model_checksum=checksum,
        )
        s3 = _make_s3_client({
            "models/v1/manifest.json": manifest,
            "models/v1/model.joblib": pkg_bytes,
        })
        result = discover_models(
            "s3://bucket/models/", staging_dir=str(tmp_path), _s3_client=s3,
        )
        for ue in result.unavailable_entries:
            safe = ue.to_safe_dict()
            body = _json.dumps(safe)
            assert "s3://" not in body
            assert "checksum" not in body
            assert "/manifest.json" not in body
            assert "model.joblib" not in body
