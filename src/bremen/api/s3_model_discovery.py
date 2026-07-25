"""S3 model catalog discovery — startup bootstrap for multi-model support.

Discovers model packages under a configured S3 prefix, validates each
candidate through a complete pipeline, and produces a CatalogDiscoveryResult
for registry initialization.

Every discovered Joblib model package directory is surfaced — available
models are executable, and non-executable candidates appear as disabled
display-only entries with safe reason categories.

PR0085 — Startup S3 Model Discovery and Per-Job Model Selection.
PR0087 — Show Every Discovered Joblib Model Candidate as Available or Disabled.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .model_registry import (
    CatalogUnavailableEntry,
    RegistryModelEntry,
    REASON_CATEGORIES,
)
from ..inference import adapt_model_package  # noqa: PLC0415

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

# Generic candidate label prefix
_CANDIDATE_LABEL_PREFIX = "Discovered model package"


# ---------------------------------------------------------------------------
# Package directory info
# ---------------------------------------------------------------------------


@dataclass
class PackageDirectoryInfo:
    """Internal representation of a discovered package directory.

    Never exposed publicly. Directory name, manifest key, and
    joblib keys remain server-private.
    """

    name: str  # Directory name (never exposed publicly)
    manifest_key: str | None = None  # S3 key of manifest.json, if any
    joblib_keys: list[str] = field(default_factory=list)  # S3 keys of .joblib artifacts
    has_manifest: bool = False
    has_joblib: bool = False


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class CatalogDiscoveryResult:
    """Result of the full S3 model discovery process."""

    entries: list[RegistryModelEntry] = field(default_factory=list)
    unavailable_entries: list[CatalogUnavailableEntry] = field(default_factory=list)
    catalog_status: str = "not_configured"
    candidate_count: int = 0
    available_count: int = 0
    rejected_count: int = 0
    unavailable_count: int = 0
    last_discovery_at: str | None = None
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
# S3 listing — package directory discovery
# ---------------------------------------------------------------------------


def _discover_package_directories(
    s3_client: Any,
    bucket: str,
    prefix: str,
) -> list[PackageDirectoryInfo]:
    """Discover candidate package directories under the catalog prefix.

    A candidate directory is any immediate child directory of the prefix
    that contains at least one of:
    - manifest.json
    - one or more .joblib objects

    Returns sorted list (by directory name) for deterministic ordering.
    Does NOT recursively scan nested directories.
    """
    # Collect all objects under prefix and group by immediate child directory
    dirs: dict[str, PackageDirectoryInfo] = {}
    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

    for page in pages:
        for obj in page.get("Contents", []):
            key = str(obj["Key"])

            # Get relative path after prefix
            if not key.startswith(prefix):
                continue
            relative = key[len(prefix):]

            # Extract immediate child directory name
            parts = relative.split("/")
            if len(parts) < 2:
                continue
            dir_name = parts[0]
            filename = parts[1] if len(parts) >= 2 else ""

            if dir_name not in dirs:
                dirs[dir_name] = PackageDirectoryInfo(name=dir_name)

            info = dirs[dir_name]

            # Check for manifest.json
            if filename == "manifest.json" and len(parts) == 2:
                info.manifest_key = key
                info.has_manifest = True

            # Check for .joblib objects
            if filename.lower().endswith(".joblib") and len(parts) == 2:
                info.joblib_keys.append(key)
                info.has_joblib = True

    # Filter to only directories that are candidates
    candidates = [
        info for info in dirs.values()
        if info.has_manifest or info.has_joblib
    ]

    # Sort by directory name for deterministic ordering
    candidates.sort(key=lambda d: d.name)

    return candidates


def _generate_candidate_labels(unregistered_count: int) -> list[str]:
    """Generate deterministic generic labels for unregistered candidates.

    Labels are "Discovered model package 1", "Discovered model package 2", etc.
    Ordinal is deterministic within the response and does NOT encode
    S3 path, filename, checksum, or manifest contents.
    """
    return [
        f"{_CANDIDATE_LABEL_PREFIX} {i + 1}"
        for i in range(unregistered_count)
    ]


def _list_candidate_manifests(
    s3_client: Any,
    bucket: str,
    prefix: str,
) -> list[str]:
    """Backward-compatible wrapper — delegates to package directory discovery.

    Kept for test compatibility. Returns manifest keys sorted by
    directory name.
    """
    pkg_dirs = _discover_package_directories(s3_client, bucket, prefix)
    return sorted(
        [d.manifest_key for d in pkg_dirs if d.manifest_key is not None]
    )


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


def _apply_manifest_threshold_fallback(
    package: dict[str, Any],
    manifest_data: dict[str, Any],
) -> dict[str, Any]:
    """Temporary discovery-only fallback: copy validated manifest
    threshold_value into package portable_logreg.threshold when the
    package does not already provide threshold through either the
    portable_logreg nested location or the root-adapted path.

    This is a temporary compatibility shim for catalog packages whose
    threshold lives in validated manifest metadata.  Future model
    exporter should embed threshold into the package so this fallback
    can be removed.

    Precedence:
    1. Existing portable_logreg.threshold (already in package).
    2. Existing package root threshold (already adapted by
       adapt_model_package).
    3. Validated manifest threshold_value (fallback).

    Does NOT overwrite existing nested or root-adapted threshold.
    Does NOT backfill any other package fields.

    Returns the package (possibly patched).
    """
    if "portable_logreg" not in package:
        return package

    plr = package["portable_logreg"]
    if not isinstance(plr, dict):
        return package

    if plr.get("threshold") is not None:
        # Already has threshold — no fallback needed
        return package

    threshold_value = manifest_data.get("threshold_value")
    if threshold_value is None:
        # Manifest has no threshold_value — nothing to fall back on
        return package

    # Apply fallback
    plr = dict(plr)
    plr["threshold"] = threshold_value
    patched = dict(package)
    patched["portable_logreg"] = plr

    model_id = str(manifest_data.get("model_id", "unknown"))
    _log.info(
        "event=bremen.catalog.package.threshold_fallback_applied\t"
        "model_id=%s\tsource=manifest_metadata",
        model_id,
    )

    return patched


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

    Discovers package directories, validates manifests, detects
    duplicates, stages and validates artifacts. Every directory
    containing a .joblib artifact surfaces as a card (available or
    disabled). Manifest-only directories surface as identified
    disabled if identity validates.

    Parameters
    ----------
    catalog_uri : The BREMEN_MODEL_CATALOG_URI value.
    staging_dir : Optional temp directory for artifact staging.
    _s3_client : Optional injected S3 client for testing.

    Returns
    -------
    A CatalogDiscoveryResult with validated entries and disabled
    display-only entries.
    """
    from datetime import datetime as _dt  # noqa: PLC0415

    discovery_start = datetime.now(timezone.utc)

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

    # ---- Phase 0: Discover package directories ----
    try:
        pkg_dirs = _discover_package_directories(_s3_client, bucket, prefix)
    except Exception as exc:
        _log.error("bremen.catalog.discovery.failed\terror_category=s3_listing\tmessage=%s", exc)
        result.catalog_status = "discovery_failed"
        result.error_category = "s3_listing_failure"
        return result

    result.candidate_count = len(pkg_dirs)

    # Enforce candidate limit
    if len(pkg_dirs) > MAX_CANDIDATES:
        _log.error(
            "bremen.catalog.discovery.failed\t"
            "error_category=too_many_candidates\t"
            "candidate_count=%d\tmax_candidates=%d",
            len(pkg_dirs), MAX_CANDIDATES,
        )
        result.catalog_status = "discovery_failed"
        result.error_category = "too_many_candidates"
        return result

    # Create staging directory
    if staging_dir is None:
        staging_dir = tempfile.mkdtemp(prefix="bremen_model_staging_")

    # ---- Phase 1: Manifest validation per directory ----
    # phase1_data: dict mapping directory name to parsed manifest data (or None)
    phase1_data: dict[str, dict[str, Any] | None] = {}
    unregistered_dirs: list[PackageDirectoryInfo] = []

    for pkg_dir in pkg_dirs:
        if pkg_dir.manifest_key is None:
            # No manifest — if .joblib exists, mark as unregistered
            if pkg_dir.has_joblib:
                unregistered_dirs.append(pkg_dir)
                result.rejected_count += 1
            # No manifest and no .joblib — not a candidate (shouldn't happen)
            phase1_data[pkg_dir.name] = None
            continue

        # Attempt manifest download and validation
        try:
            response = _s3_client.get_object(Bucket=bucket, Key=pkg_dir.manifest_key)
            body_bytes = response["Body"].read()
        except Exception:
            _log.warning(
                "bremen.catalog.candidate.rejected\t"
                "reason_category=manifest_download_failed",
            )
            result.rejected_count += 1
            if pkg_dir.has_joblib:
                unregistered_dirs.append(pkg_dir)
            phase1_data[pkg_dir.name] = None
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

            phase1_data[pkg_dir.name] = data
        except Exception:
            _log.warning(
                "bremen.catalog.candidate.rejected\t"
                "reason_category=manifest_validation_failed",
            )
            result.rejected_count += 1
            if pkg_dir.has_joblib:
                unregistered_dirs.append(pkg_dir)
            phase1_data[pkg_dir.name] = None

    # ---- Create unregistered unavailable entries ----
    if unregistered_dirs:
        labels = _generate_candidate_labels(len(unregistered_dirs))
        for i, pkg_dir in enumerate(unregistered_dirs):
            entry = CatalogUnavailableEntry(
                kind="unregistered",
                reason_category="unregistered_package",
                candidate_label=labels[i],
            )
            result.unavailable_entries.append(entry)
        result.unavailable_count = len(result.unavailable_entries)

    # ---- Phase 2: Count model_id occurrences, reject duplicates ----
    # Collect valid manifest entries (passed Phase 1)
    phase2_candidates: list[tuple[str, dict[str, Any]]] = [
        (dname, data) for dname, data in phase1_data.items()
        if data is not None
    ]

    model_id_counts: dict[str, int] = {}
    for _, data in phase2_candidates:
        mid = str(data["model_id"])
        model_id_counts[mid] = model_id_counts.get(mid, 0) + 1

    duplicate_ids = {mid for mid, count in model_id_counts.items() if count > 1}

    # For duplicates: select lexicographically first display_name
    duplicate_display_names: dict[str, str] = {}
    for dname, data in phase2_candidates:
        mid = str(data["model_id"])
        if mid in duplicate_ids:
            dn = str(data.get("display_name", "")).strip()
            if mid not in duplicate_display_names or dn < duplicate_display_names[mid]:
                duplicate_display_names[mid] = dn if dn else mid

    # Create duplicate unavailable entries (one per duplicated model_id)
    for mid in sorted(duplicate_ids):
        display_name = duplicate_display_names.get(mid, mid)
        # Find first duplicate candidate for workflow_id
        workflow_id = "bremen"
        for _, data in phase2_candidates:
            if str(data["model_id"]) == mid:
                workflow_id = str(data.get("workflow_id", "bremen"))
                break
        entry = CatalogUnavailableEntry(
            kind="identified",
            reason_category="duplicate_entry",
            model_id=mid,
            display_name=display_name,
            workflow_id=workflow_id,
        )
        result.unavailable_entries.append(entry)
        _log.warning(
            "bremen.catalog.candidate.rejected\t"
            "reason_category=duplicate_entry\tmodel_id=%s",
            mid,
        )

    # Reject all duplicates — mark data as None
    for dname, data in phase2_candidates:
        if str(data["model_id"]) in duplicate_ids:
            phase1_data[dname] = None
            result.rejected_count += 1

    result.unavailable_count = len(result.unavailable_entries)

    # ---- Phase 3: Process unique candidates through full pipeline ----
    from .decision_contract import (  # noqa: PLC0415
        DECISION_POLICY_ID,
        DECISION_POLICY_VERSION,
    )

    entries: list[RegistryModelEntry] = []
    pkg_dir_map = {d.name: d for d in pkg_dirs}

    for dname, data in phase1_data.items():
        if data is None:
            continue

        pkg_dir = pkg_dir_map.get(dname)
        model_id = str(data["model_id"])
        display_name = str(data["display_name"]).strip()
        workflow_id = str(data["workflow_id"])

        # If no .joblib artifact but valid identity, create identified disabled
        if pkg_dir is None or not pkg_dir.has_joblib:
            entry = CatalogUnavailableEntry(
                kind="identified",
                reason_category="not_compatible",
                model_id=model_id,
                display_name=display_name,
                workflow_id=workflow_id,
            )
            result.unavailable_entries.append(entry)
            result.rejected_count += 1
            _log.warning(
                "bremen.catalog.candidate.rejected\t"
                "reason_category=not_compatible\tmodel_id=%s",
                model_id,
            )
            continue

        try:
            model_filename = str(data["model_filename"])
            expected_checksum = str(data["model_checksum"])

            # Resolve artifact key
            artifact_key = _resolve_artifact_key(
                pkg_dir.manifest_key, model_filename, prefix,
            )

            # Stage and load artifact
            package = _stage_and_load_artifact(
                _s3_client, bucket, artifact_key, expected_checksum, staging_dir,
            )

            # Adapt real package layout to runtime-expected format
            package = adapt_model_package(package)

            # PR0088: Apply manifest threshold_value fallback if
            # portable_logreg.threshold is still missing after adaptation
            package = _apply_manifest_threshold_fallback(package, data)

            # Validate loaded package
            entry_builder = {
                "feature_schema_version": str(data["feature_schema_version"]),
            }
            _validate_loaded_package(package, entry_builder)

            # Build entry
            model_version = str(data.get("model_version", "unknown"))
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
                "bremen.catalog.candidate.accepted\tmodel_id=%s",
                model_id,
            )
        except Exception:
            # Phase 3 failure — create identified disabled entry
            unavailable_entry = CatalogUnavailableEntry(
                kind="identified",
                reason_category="not_compatible",
                model_id=model_id,
                display_name=display_name,
                workflow_id=workflow_id,
            )
            result.unavailable_entries.append(unavailable_entry)
            result.rejected_count += 1
            _log.warning(
                "bremen.catalog.candidate.rejected\t"
                "reason_category=not_compatible\tmodel_id=%s",
                model_id,
            )

    # Update final counts
    result.unavailable_count = len(result.unavailable_entries)

    # Sort entries by model_id for deterministic ordering
    entries.sort(key=lambda e: e.model_id)

    result.entries = entries
    result.last_discovery_at = discovery_start.isoformat()

    if entries:
        result.catalog_status = "available"
    elif pkg_dirs and not entries:
        result.catalog_status = "no_valid_models"
    elif not pkg_dirs:
        result.catalog_status = "no_valid_models"
    else:
        result.catalog_status = "not_configured"

    _log.info(
        "bremen.catalog.discovery.completed\t"
        "catalog_status=%s\tcandidate_count=%d\t"
        "available_count=%d\trejected_count=%d\t"
        "unavailable_count=%d",
        result.catalog_status,
        result.candidate_count,
        result.available_count,
        result.rejected_count,
        result.unavailable_count,
    )

    return result


