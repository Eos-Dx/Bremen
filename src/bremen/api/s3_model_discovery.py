"""S3 model catalog discovery — startup bootstrap for multi-model support.

Discovers model manifests under a configured S3 prefix, validates each
candidate through a complete pipeline, and produces a CatalogDiscoveryResult
for registry initialization.

PR0085 — Startup S3 Model Discovery and Per-Job Model Selection.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import Any

from .model_registry import RegistryModelEntry

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CANDIDATES = 50
MAX_MANIFEST_BYTES = 65536

# Required discovery-specific fields (NOT added to _REQUIRED_MANIFEST_FIELDS)
_DISCOVERY_REQUIRED_FIELDS = frozenset({
    "model_id",
    "display_name",
    "workflow_id",
})

# Allowed artifact types
_ALLOWED_ARTIFACT_TYPES = frozenset({"portable_logreg"})

# Allowed workflow IDs
_ALLOWED_WORKFLOW_IDS = frozenset({"bremen"})

# model_id pattern: lowercase alphanumeric start, max 64 chars
_MODEL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

# Supported feature schema versions
_SUPPORTED_FEATURE_SCHEMA_VERSIONS = frozenset({"v0.1"})


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class CatalogDiscoveryResult:
    """Result of the full S3 model discovery process."""

    entries: list[RegistryModelEntry] = field(default_factory=list)
    catalog_status: str = "not_configured"
    candidate_count: int = 0
    available_count: int = 0
    rejected_count: int = 0
    error_category: str | None = None


# ---------------------------------------------------------------------------
# URI parsing
# ---------------------------------------------------------------------------


def _validate_catalog_uri(uri: str) -> tuple[str, str]:
    """Parse and validate a BREMEN_MODEL_CATALOG_URI.

    Returns (bucket, prefix).
    Raises ValueError on invalid URI.
    """
    if not uri or not isinstance(uri, str):
        raise ValueError("BREMEN_MODEL_CATALOG_URI must be a non-empty string")

    if not uri.startswith("s3://"):
        raise ValueError(
            "BREMEN_MODEL_CATALOG_URI must start with s3://"
        )

    path_part = uri[5:]  # strip s3://
    if not path_part:
        raise ValueError("BREMEN_MODEL_CATALOG_URI has no bucket")

    parts = path_part.split("/", 1)
    bucket = parts[0]
    if not bucket:
        raise ValueError("BREMEN_MODEL_CATALOG_URI has empty bucket")

    prefix = ""
    if len(parts) > 1 and parts[1]:
        prefix = parts[1]
        if not prefix.endswith("/"):
            prefix += "/"

    return bucket, prefix


# ---------------------------------------------------------------------------
# S3 listing
# ---------------------------------------------------------------------------


def _list_candidate_manifests(
    s3_client: Any,
    bucket: str,
    prefix: str,
) -> list[str]:
    """List candidate manifest keys under the configured prefix.

    Uses ListObjectsV2 without Delimiter. Filters for keys matching:
    {prefix}{package_dir}/manifest.json where package_dir is exactly
    one level below prefix.

    Returns sorted list of manifest keys (lexicographic order).
    """
    manifest_keys: list[str] = []
    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

    for page in pages:
        for obj in page.get("Contents", []):
            key = str(obj["Key"])

            # Must end with /manifest.json
            if not key.endswith("/manifest.json"):
                continue

            # Must be exactly one level below prefix
            relative = key[len(prefix):] if key.startswith(prefix) else key
            parts = relative.split("/")
            # Expected: ["package-dir", "manifest.json"]
            if len(parts) != 2 or parts[1] != "manifest.json":
                continue

            manifest_keys.append(key)

    manifest_keys.sort()
    return manifest_keys


# ---------------------------------------------------------------------------
# Manifest validation
# ---------------------------------------------------------------------------


def _validate_manifest_body(body_bytes: bytes) -> dict[str, Any]:
    """Parse and validate the manifest body.

    Checks size, JSON parse, then calls the existing base manifest
    validator from model_package.py for all authoritative base fields
    including threshold_version, threshold_value, qc_criteria_version,
    feature_schema_version, artifact_type, model_checksum,
    model_filename, and model_version.

    Returns the parsed manifest dict.
    Raises ValueError with a safe message on failure.
    """
    if len(body_bytes) > MAX_MANIFEST_BYTES:
        raise ValueError(
            f"Manifest exceeds maximum size of {MAX_MANIFEST_BYTES} bytes"
        )

    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Invalid manifest JSON: {type(exc).__name__}") from exc

    if not isinstance(data, dict):
        raise ValueError("Manifest must be a JSON object")

    # Call the existing base manifest validator from model_package
    from ..model_package import validate_model_manifest  # noqa: PLC0415
    try:
        validate_model_manifest(data)
    except Exception as exc:
        raise ValueError(f"Base manifest validation failed: {type(exc).__name__}") from exc

    return data


def _validate_discovery_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Validate discovery-specific fields.

    Returns the validated data dict.
    Raises ValueError with a safe message on failure.
    """
    for field_name in _DISCOVERY_REQUIRED_FIELDS:
        if field_name not in data:
            raise ValueError(f"Manifest missing discovery field: {field_name}")

    # model_id validation
    model_id = str(data["model_id"])
    if not _MODEL_ID_PATTERN.match(model_id):
        raise ValueError(
            f"Invalid model_id: {model_id!r}. Must match "
            r"^[a-z0-9][a-z0-9._-]{0,63}$"
        )

    # display_name validation
    display_name = str(data["display_name"]).strip()
    if not display_name or len(display_name) > 80:
        raise ValueError(
            "display_name must be non-empty and at most 80 characters"
        )

    # workflow_id validation
    workflow_id = str(data["workflow_id"])
    if workflow_id not in _ALLOWED_WORKFLOW_IDS:
        raise ValueError(
            f"Unsupported workflow_id: {workflow_id!r}. "
            f"Allowed: {sorted(_ALLOWED_WORKFLOW_IDS)}"
        )

    return data


# ---------------------------------------------------------------------------
# Artifact resolution
# ---------------------------------------------------------------------------


def _resolve_artifact_key(
    manifest_key: str,
    model_filename: str,
    catalog_prefix: str,
) -> str:
    """Resolve the S3 key for the model artifact.

    The artifact must be in the same package directory as the manifest.
    Path traversal is rejected.
    """
    # Get the package directory from the manifest key
    # manifest_key = "prefix/package-dir/manifest.json"
    # package_dir = "prefix/package-dir/"
    if not manifest_key.endswith("/manifest.json"):
        raise ValueError("Invalid manifest key structure")

    package_dir = manifest_key[: -len("/manifest.json")]

    # Reject path traversal in model_filename
    if ".." in model_filename or "/" in model_filename or "\\" in model_filename:
        raise ValueError("Invalid model_filename: path traversal detected")

    artifact_key = f"{package_dir}/{model_filename}"

    # Verify artifact is within the catalog prefix
    if not artifact_key.startswith(catalog_prefix):
        raise ValueError("Artifact is outside the catalog prefix")

    return artifact_key


# ---------------------------------------------------------------------------
# Artifact staging and loading
# ---------------------------------------------------------------------------


def _stage_and_load_artifact(
    s3_client: Any,
    bucket: str,
    artifact_key: str,
    expected_checksum: str,
    staging_dir: str,
) -> dict[str, Any]:
    """Download, verify checksum, and load a model artifact.

    Returns the loaded model package dict.
    Raises ValueError on failure.
    """
    # Download to staging
    local_path = os.path.join(staging_dir, os.path.basename(artifact_key))
    s3_client.download_file(bucket, artifact_key, local_path)

    # SHA-256 verification before deserialization
    sha256 = hashlib.sha256()
    with open(local_path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha256.update(chunk)
    actual_checksum = sha256.hexdigest()

    if expected_checksum and actual_checksum != expected_checksum:
        os.unlink(local_path)
        raise ValueError("Checksum mismatch: expected "
                         f"{expected_checksum}, got {actual_checksum}")

    # Controlled joblib loading
    try:
        from joblib import load as joblib_load  # noqa: PLC0415
        package = joblib_load(local_path)
    except Exception as exc:
        os.unlink(local_path)
        raise ValueError(f"Failed to load model artifact: {type(exc).__name__}") from exc
    finally:
        if os.path.exists(local_path):
            os.unlink(local_path)

    if not isinstance(package, dict):
        raise ValueError("Loaded model package must be a dict")

    return package


# ---------------------------------------------------------------------------
# Package validation
# ---------------------------------------------------------------------------


def _validate_loaded_package(
    package: dict[str, Any],
    entry_builder: dict[str, Any],
) -> bool:
    """Validate a loaded model package.

    Checks:
    - Supported portable_logreg structure
    - Feature schema compatibility
    - Threshold and decision policy compatibility

    Returns True if valid.
    Raises ValueError on failure.
    """
    plr = package.get("portable_logreg")
    if plr is None:
        raise ValueError("Package missing portable_logreg key")

    if not isinstance(plr, dict):
        raise ValueError("portable_logreg must be a dict")

    # Check required portable_logreg fields
    required_plr = {"coef", "intercept", "threshold"}
    missing = required_plr - set(plr.keys())
    if missing:
        raise ValueError(
            f"portable_logreg missing required fields: {missing}"
        )

    # Feature schema compatibility
    fs_version = entry_builder.get("feature_schema_version", "")
    if fs_version not in _SUPPORTED_FEATURE_SCHEMA_VERSIONS:
        raise ValueError(
            f"Unsupported feature schema version: {fs_version!r}. "
            f"Supported: {sorted(_SUPPORTED_FEATURE_SCHEMA_VERSIONS)}"
        )

    # Threshold validation
    threshold = plr.get("threshold")
    if threshold is None or not isinstance(threshold, (int, float)):
        raise ValueError("portable_logreg threshold must be a number")

    if float(threshold) <= 0:
        raise ValueError("portable_logreg threshold must be positive")

    return True


# ---------------------------------------------------------------------------
# Main discovery function
# ---------------------------------------------------------------------------


def discover_models(
    catalog_uri: str,
    staging_dir: str | None = None,
    *,
    _s3_client: Any = None,
) -> CatalogDiscoveryResult:
    """Run the full S3 model discovery pipeline.

    Two-phase duplicate handling:
    Phase 1: Download, parse, base-validate, and discovery-validate
             candidate manifests.
    Phase 2: Count model_id occurrences among otherwise valid manifests.
             Reject every candidate whose model_id occurs more than once.
             Only unique model_ids proceed to artifact staging, checksum
             verification, deserialization, package validation, and
             registry insertion.

    Parameters
    ----------
    catalog_uri : The BREMEN_MODEL_CATALOG_URI value.
    staging_dir : Optional temp directory for artifact staging.
    _s3_client : Optional injected S3 client for testing.

    Returns
    -------
    A CatalogDiscoveryResult with validated entries.
    """
    result = CatalogDiscoveryResult()

    try:
        bucket, prefix = _validate_catalog_uri(catalog_uri)
    except ValueError as exc:
        _log.error("bremen.catalog.discovery.failed\terror_category=invalid_uri\tmessage=%s", exc)
        result.catalog_status = "discovery_failed"
        result.error_category = "invalid_uri"
        return result

    # Create S3 client if not injected
    if _s3_client is None:
        try:
            from boto3 import client as _s3_client_builder  # noqa: PLC0415
            _s3_client = _s3_client_builder("s3")
        except Exception as exc:
            _log.error("bremen.catalog.discovery.failed\terror_category=s3_client\tmessage=%s", exc)
            result.catalog_status = "discovery_failed"
            result.error_category = "s3_client_failure"
            return result

    # List candidate manifests
    try:
        manifest_keys = _list_candidate_manifests(_s3_client, bucket, prefix)
    except Exception as exc:
        _log.error("bremen.catalog.discovery.failed\terror_category=s3_listing\tmessage=%s", exc)
        result.catalog_status = "discovery_failed"
        result.error_category = "s3_listing_failure"
        return result

    result.candidate_count = len(manifest_keys)

    # Enforce candidate limit
    if len(manifest_keys) > MAX_CANDIDATES:
        _log.error(
            "bremen.catalog.discovery.failed\t"
            "error_category=too_many_candidates\t"
            "candidate_count=%d\tmax_candidates=%d",
            len(manifest_keys), MAX_CANDIDATES,
        )
        result.catalog_status = "discovery_failed"
        result.error_category = "too_many_candidates"
        return result

    # Create staging directory
    if staging_dir is None:
        staging_dir = tempfile.mkdtemp(prefix="bremen_model_staging_")

    # ---- Phase 1: Download, parse, and validate all manifests ----
    # Each entry: (manifest_key, data_dict) or None if rejected
    phase1_results: list[tuple[str, dict[str, Any] | None]] = []
    for manifest_key in manifest_keys:
        try:
            response = _s3_client.get_object(Bucket=bucket, Key=manifest_key)
            body_bytes = response["Body"].read()
        except Exception as exc:
            _log.warning(
                "bremen.catalog.candidate.rejected\t"
                "manifest_key=%s\terror_category=manifest_download_failed",
                manifest_key,
            )
            result.rejected_count += 1
            phase1_results.append((manifest_key, None))
            continue

        try:
            # Size check + JSON parse
            if len(body_bytes) > MAX_MANIFEST_BYTES:
                raise ValueError("manifest_too_large")
            data = json.loads(body_bytes.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("manifest_not_object")

            # Call the existing base manifest validator from model_package
            from ..model_package import validate_model_manifest  # noqa: PLC0415
            validate_model_manifest(data)

            # Discovery-specific validation
            data = _validate_discovery_fields(data)

            phase1_results.append((manifest_key, data))
        except Exception as exc:
            _log.warning(
                "bremen.catalog.candidate.rejected\t"
                "manifest_key=%s\terror_category=%s",
                manifest_key, str(exc)[:100],
            )
            result.rejected_count += 1
            phase1_results.append((manifest_key, None))

    # ---- Phase 2: Count model_id occurrences, reject duplicates ----
    model_id_counts: dict[str, int] = {}
    for manifest_key, data in phase1_results:
        if data is not None:
            mid = str(data["model_id"])
            model_id_counts[mid] = model_id_counts.get(mid, 0) + 1

    duplicate_ids = {mid for mid, count in model_id_counts.items() if count > 1}

    # Reject all duplicates
    for i, (manifest_key, data) in enumerate(phase1_results):
        if data is not None and str(data["model_id"]) in duplicate_ids:
            _log.warning(
                "bremen.catalog.candidate.rejected\t"
                "manifest_key=%s\terror_category=duplicate_model_id\t"
                "model_id=%s",
                manifest_key, str(data["model_id"]),
            )
            phase1_results[i] = (manifest_key, None)
            result.rejected_count += 1

    # ---- Phase 3: Process unique candidates through full pipeline ----
    from .decision_contract import (  # noqa: PLC0415
        DECISION_POLICY_ID,
        DECISION_POLICY_VERSION,
    )

    entries: list[RegistryModelEntry] = []

    for manifest_key, data in phase1_results:
        if data is None:
            continue

        try:
            model_id = str(data["model_id"])
            model_filename = str(data["model_filename"])
            expected_checksum = str(data["model_checksum"])

            # Resolve artifact key
            artifact_key = _resolve_artifact_key(
                manifest_key, model_filename, prefix,
            )

            # Stage and load artifact
            package = _stage_and_load_artifact(
                _s3_client, bucket, artifact_key, expected_checksum, staging_dir,
            )

            # Validate loaded package
            entry_builder = {
                "feature_schema_version": str(data["feature_schema_version"]),
            }
            _validate_loaded_package(package, entry_builder)

            # Build entry
            model_version = str(data.get("model_version", "unknown"))
            display_name = str(data["display_name"]).strip()
            workflow_id = str(data["workflow_id"])
            artifact_type = str(data.get("artifact_type", "portable_logreg"))
            feature_schema_version = str(data.get("feature_schema_version", "v0.1"))

            entry = RegistryModelEntry(
                model_id=model_id,
                display_name=display_name,
                workflow_id=workflow_id,
                model_version=model_version,
                artifact_type=artifact_type,
                feature_schema_version=feature_schema_version,
                decision_policy_id=DECISION_POLICY_ID,
                decision_policy_version=DECISION_POLICY_VERSION,
                technical_ready=True,
                scientifically_certified=False,
                technical_demo_only=True,
                availability="available",
                _package=package,
                _checksum=expected_checksum,
            )

            entries.append(entry)
            result.available_count += 1

            _log.info(
                "bremen.catalog.candidate.accepted\t"
                "model_id=%s\tmanifest_key=%s",
                model_id, manifest_key,
            )
        except Exception as exc:
            _log.warning(
                "bremen.catalog.candidate.rejected\t"
                "manifest_key=%s\terror_category=%s",
                manifest_key, str(exc)[:100],
            )
            result.rejected_count += 1

    # Sort entries by model_id for deterministic ordering
    entries.sort(key=lambda e: e.model_id)

    result.entries = entries
    result.catalog_status = "available" if entries else "no_valid_models"

    _log.info(
        "bremen.catalog.discovery.completed\t"
        "catalog_status=%s\tcandidate_count=%d\t"
        "available_count=%d\trejected_count=%d",
        result.catalog_status,
        result.candidate_count,
        result.available_count,
        result.rejected_count,
    )

    return result


