"""Transport-independent demo H5 storage helpers."""

from __future__ import annotations
import json, logging, os, re, uuid
from bremen.demo_config import read_demo_h5_config
from bremen.platform.sources.preflight import (H5ContainerError,H5MetadataError,H5PatientMismatchError,H5SideMismatchError,H5MeasurementError,H5QualityError,H5PreflightError)
from bremen.contracts.legacy_errors import PreprocessingBridgeError,PreflightNotPassedError,FeatureSchemaMismatchError
from bremen.model_packages.bremen_v01.predictor import PortableLogRegModelError
from bremen.feature_artifacts import FeatureArtifactError
_patient_name_cache = {}

def _list_s3_containers(bucket: str, prefix: str) -> list[dict]:
    """List H5/HDF5 objects under configured S3 prefix.

    Uses the existing boto3 dependency via lazy import.
    Returns a list of container dicts with safe metadata only:
    ``id`` (S3 key), ``filename`` (basename), ``size_bytes``,
    ``last_modified``.

    On S3 errors (AccessDenied, etc.), raises the exception.
    The caller sets ``storage: "list_failed"`` accordingly.
    """
    import re as _re  # noqa: PLC0415
    from boto3 import client as _s3_client  # noqa: PLC0415

    s3 = _s3_client("s3")
    containers: list[dict] = []
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
    for page in pages:
        for obj in page.get("Contents", []):
            key = str(obj["Key"])
            filename = key.split("/")[-1] if "/" in key else key
            # Only include H5/HDF5 files
            if not _re.search(r"\.h5$|\.hdf5$", key, _re.IGNORECASE):
                continue
            last_modified = obj.get("LastModified")
            if hasattr(last_modified, "isoformat"):
                last_modified_str = last_modified.isoformat()
            else:
                last_modified_str = str(last_modified or "")
            containers.append({
                "id": key,
                "filename": filename,
                "size_bytes": obj.get("Size", 0),
                "last_modified": last_modified_str,
            })
    return containers

def _build_containers_response(request_id: str | None = None) -> dict:
    """Build the GET /demo/api/h5/containers response dict.

    This is the transport-independent core extracted from
    ``_handle_demo_h5_containers_list``.  Both the ``http.server``
    handler and the FastAPI route call this helper so that the
    business logic lives in exactly one place.

    Returns
    -------
    A serialisable dict with ``storage``, ``containers``,
    ``upload_max_bytes``, ``technical_demo_only``, and ``request_id``.
    """
    import json as _json  # noqa: PLC0415
    import os as _os  # noqa: PLC0415
    import logging as _logging  # noqa: PLC0415

    if request_id is None:
        request_id = str(uuid.uuid4())

    config = read_demo_h5_config()

    if config["h5_bucket"] is None:
        # No bucket configured — return safe empty response
        return {
            "storage": "not_configured",
            "containers": [],
            "technical_demo_only": True,
            "request_id": request_id,
        }

    # 1. Env-configured catalog
    try:
        containers_json = _os.environ.get(
            "BREMEN_DEMO_H5_CONTAINERS", "[]"
        )
        env_containers = _json.loads(containers_json)
        if not isinstance(env_containers, list):
            env_containers = []
    except (_json.JSONDecodeError, TypeError):
        env_containers = []

    # 2. S3-listed containers
    s3_containers: list[dict] = []
    storage_status = "configured"
    try:
        s3_containers = _list_s3_containers(
            config["h5_bucket"], config["h5_prefix"],
        )
    except Exception:
        _log = _logging.getLogger(__name__)
        _log.exception(
            "bremen.demo.h5.containers.list_failed\t"
            "stage=containers\tstatus=failed\t"
            "bucket=%s\tprefix=%s",
            config["h5_bucket"], config["h5_prefix"],
        )
        storage_status = "list_failed"
        s3_containers = []

    # 3. Merge with deduplication by raw key (server-side only)
    seen_keys: set[str] = set()
    merged_raw: list[dict] = []
    for c in env_containers:
        cid = c.get("id") or c.get("key") or c.get("filename", "")
        if cid not in seen_keys:
            seen_keys.add(cid)
            merged_raw.append(c)
    for c in s3_containers:
        cid = c.get("id", "")
        if cid not in seen_keys:
            seen_keys.add(cid)
            merged_raw.append(c)

    # Filter oversized objects
    max_bytes = config["upload_max_bytes"]
    merged_raw = [c for c in merged_raw if c.get("size_bytes", 0) <= max_bytes]

    # Sort by last_modified descending (newest first)
    merged_raw.sort(key=lambda c: c.get("last_modified", ""), reverse=True)

    # Limit to 100 objects maximum
    merged_raw = merged_raw[:100]

    # Replace raw S3 keys with opaque source_ids from the registry.
    # The browser receives only source_id, display_name, size_bytes,
    # and last_modified — never the S3 key.
    from bremen.platform.sources.registry import register_source, get_stable_source_key, update_source_display_name  # noqa: PLC0415

    bucket = config["h5_bucket"]
    prefix = config["h5_prefix"]
    safe_containers: list[dict] = []
    for item in merged_raw:
        raw_key = item.get("id", "")
        filename = item.get("filename", "unknown.h5")
        size = item.get("size_bytes", 0)
        last_mod = item.get("last_modified", "")
        source_id = register_source(
            bucket=bucket,
            object_key=raw_key,
            filename=filename,
            size_bytes=size,
            prefix=prefix,
            patient_display_name=item.get("patient_display_name", ""),
            source_version=str(item.get("version_id") or item.get("etag") or last_mod),
        )
        # Determine workflow compatibility
        wf = item.get("workflow_id", "bremen")

        # Patient name from cache or extraction
        cache_key = (bucket, raw_key, size, last_mod)
        patient_name = item.get("patient_display_name", "")
        if patient_name:
            _patient_name_cache[cache_key] = patient_name
        elif cache_key in _patient_name_cache:
            cached = _patient_name_cache[cache_key]
            patient_name = cached or ""
        else:
            try:
                from bremen.h5_inputs import stage_h5_input as _stage  # noqa: PLC0415
                from bremen.platform.sources.service import extract_patient_display_name
                s3_uri = f"s3://{bucket}/{raw_key}"
                local_path = _stage(s3_uri)
                extracted = extract_patient_display_name(str(local_path))
                if extracted:
                    patient_name = extracted
                    _patient_name_cache[cache_key] = extracted
                else:
                    pass  # Missing metadata may become available on a later listing.
            except Exception:
                pass  # Transient staging failure must not poison future listings.

        update_source_display_name(source_id, patient_name)
        display_name = filename
        safe_containers.append({
            "source_id": source_id,
            "display_name": display_name,
            "patient_display_name": patient_name,
            "stable_source_key": get_stable_source_key(source_id),
            "size_bytes": size,
            "last_modified": last_mod,
            "workflow_id": wf,
        })

    return {
        "storage": storage_status,
        "containers": safe_containers,
        "upload_max_bytes": max_bytes,
        "technical_demo_only": True,
        "request_id": request_id,
    }

def _handle_h5_upload_bytes(
    raw_body: bytes,
    raw_filename: str,
    request_id: str,
) -> tuple[int, dict]:
    """Validate and upload H5 bytes to S3. Transport-independent.

    Parameters
    ----------
    raw_body : Raw file bytes.
    raw_filename : Original filename from the client.
    request_id : Request ID for the response.

    Returns
    -------
    A tuple of (http_status_code, response_dict).
    All validation errors return safe public messages only.
    """
    config = read_demo_h5_config()

    # ---- Input validation (before storage check) ----

    # Validate content length
    content_length = len(raw_body)
    if content_length == 0:
        return 400, {
            "status": "upload_rejected",
            "error": "Empty body",
            "request_id": request_id,
            "technical_demo_only": True,
        }

    if content_length > config["upload_max_bytes"]:
        return 413, {
            "status": "upload_rejected",
            "error": f"File too large: {content_length} bytes "
                     f"(max {config['upload_max_bytes']})",
            "request_id": request_id,
            "technical_demo_only": True,
        }

    # Validate filename
    raw_filename = raw_filename.strip()
    if not raw_filename:
        return 400, {
            "status": "upload_rejected",
            "error": "Missing X-H5-Filename header",
            "request_id": request_id,
            "technical_demo_only": True,
        }

    # Sanitize filename — reject path separators
    if "/" in raw_filename or "\\" in raw_filename or ".." in raw_filename:
        return 400, {
            "status": "upload_rejected",
            "error": "Invalid filename — path separators not allowed",
            "request_id": request_id,
            "technical_demo_only": True,
        }

    # Validate extension
    name_lower = raw_filename.lower()
    if not (name_lower.endswith(".h5") or name_lower.endswith(".hdf5")):
        return 400, {
            "status": "upload_rejected",
            "error": (
                f"Invalid file extension: {raw_filename!r}. "
                "Only .h5 and .hdf5 files are accepted."
            ),
            "request_id": request_id,
            "technical_demo_only": True,
        }

    # ---- Storage checks (after input is validated) ----

    # Check upload enabled
    if not config["allow_upload"]:
        return 403, {
            "status": "upload_disabled",
            "request_id": request_id,
            "technical_demo_only": True,
        }

    # Check storage configured
    if config["h5_bucket"] is None:
        return 503, {
            "status": "storage_not_configured",
            "request_id": request_id,
            "technical_demo_only": True,
        }

    # Sanitize filename (keep only safe characters)
    sanitized = "".join(
        c for c in raw_filename if c.isalnum() or c in "._- "
    )
    sanitized = sanitized.replace(" ", "_").strip("._")
    if not sanitized:
        sanitized = "uploaded.h5"
    # Ensure .h5 extension
    if not sanitized.lower().endswith(".h5"):
        sanitized += ".h5"

    # Upload to S3
    try:
        from boto3 import client as _s3_client  # noqa: PLC0415

        s3 = _s3_client("s3")
        key = f"{config['h5_prefix']}{sanitized}"
        s3.put_object(
            Bucket=config["h5_bucket"],
            Key=key,
            Body=raw_body,
        )

        return 201, {
            "status": "uploaded",
            "id": key,
            "filename": sanitized,
            "size_bytes": content_length,
            "request_id": request_id,
            "technical_demo_only": True,
        }
    except Exception as exc:
        return 503, {
            "status": "upload_rejected",
            "error": f"S3 upload failed: {type(exc).__name__}",
            "request_id": request_id,
            "technical_demo_only": True,
        }

def _safe_error_detail(exc: Exception) -> str:
    """Map an internal exception to a safe public error detail.

    No internal H5 paths, measurement filenames, S3 URIs,
    patient/sample identifiers, or attribute values are exposed.

    Returns a finite, generic detail string suitable for API
    responses.  The full stack trace is preserved in server logs
    via ``_log.exception()`` for debugging.
    """
    if isinstance(exc, (H5ContainerError,)):
        return "H5 layout metadata is incomplete"
    if isinstance(exc, (H5MetadataError,)):
        return "H5 layout metadata is incomplete"
    if isinstance(exc, (H5PatientMismatchError,)):
        return "H5 layout metadata is incomplete"
    if isinstance(exc, (H5SideMismatchError,)):
        return "Bilateral measurement pairing failed"
    if isinstance(exc, (H5MeasurementError, H5QualityError,)):
        return "H5 layout metadata is incomplete"
    if isinstance(exc, (H5PreflightError,)):
        return "H5 layout metadata is incomplete"
    if isinstance(exc, (PreprocessingBridgeError, FeatureSchemaMismatchError,
                        PreflightNotPassedError)):
        return "Preprocessing failed"
    if isinstance(exc, (PortableLogRegModelError, FeatureArtifactError)):
        return "Model inference failed"
    # Fallback for unexpected exceptions
    return "Internal error"

def _safe_error_detail_str(error_message: str) -> str:
    """Map a workflow error message to a safe public detail string.

    No internal paths, PONI text, raw arrays, or patient/specimen
    identifiers are exposed.
    """
    msg_lower = error_message.lower()
    if 'configuration_required' in msg_lower:
        return 'Workflow configuration is needed for this input'
    if 'unavailable' in msg_lower:
        return 'Requested workflow is not available'
    if 'not found' in msg_lower or 'not_found' in msg_lower:
        return 'Requested workflow is not available'
    if 'incompatible' in msg_lower:
        return 'Input is not compatible with the requested workflow'
    return 'Internal error'
