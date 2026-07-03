"""Local Bremen model package contract and validation helpers.

Bremen — XRD-based ML decision-support workflow foundation.
Not a diagnostic replacement.

This module validates the local model package contract defined in
ADR-0007 (Model Artifact Lifecycle).  It does NOT deserialise joblib
or pickle files, does NOT load models for inference, and does NOT
read H5/HDF5 data.  All file I/O is limited to JSON manifest reading
and SHA-256 computation via the Python standard library.

Security boundaries:
- No ``joblib`` import.
- No ``pickle`` import.
- Path traversal prevention for ``model_filename``.
- SHA-256 checksum verification before any downstream use.
- Fail-closed on any validation failure.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_ARTIFACT_TYPE = "bremen.joblib.model_package"

_REQUIRED_MANIFEST_FIELDS: dict[str, type] = {
    "artifact_type": str,
    "model_version": str,
    "model_checksum": str,
    "model_filename": str,
    "feature_schema_version": str,
    "threshold_version": str,
    "threshold_value": (int, float),
    "qc_criteria_version": str,
}

_SHA256_HEX_PATTERN = re.compile(r"^[a-f0-9]{64}$")

_MANIFEST_FILENAME = "manifest.json"


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class ModelPackageError(Exception):
    """Base exception for model package errors."""


class ModelPackageNotFoundError(ModelPackageError):
    """Model package or required file not found."""


class ModelPackageManifestError(ModelPackageError):
    """Manifest is missing, invalid JSON, or has missing/damaged fields."""


class ModelPackageChecksumError(ModelPackageError):
    """Computed SHA-256 does not match manifest model_checksum."""


class ModelPackageSecurityError(ModelPackageError):
    """Security violation — e.g. path traversal in model_filename."""


# ---------------------------------------------------------------------------
# Public data type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelPackageSummary:
    """Safe summary of a validated model package (no clinical data)."""

    package_dir: Path
    manifest_path: Path
    model_path: Path
    model_version: str
    model_checksum: str
    feature_schema_version: str
    threshold_version: str
    threshold_value: float
    qc_criteria_version: str
    training_config_ref: str | None
    created_at: str | None
    artifact_type: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_sha256(path: str | Path) -> str:
    """Compute the SHA-256 hex digest of a file.

    Parameters
    ----------
    path : Filesystem path to the file.

    Returns
    -------
    The 64-character lowercase hex digest.

    Raises
    ------
    ModelPackageNotFoundError
        If the file does not exist or is not a regular file.
    """
    p = Path(path)
    if not p.exists():
        raise ModelPackageNotFoundError(f"File not found: {p}")
    if not p.is_file():
        raise ModelPackageNotFoundError(f"Not a regular file: {p}")

    h = hashlib.sha256()
    with p.open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def read_model_manifest(path: str | Path) -> dict[str, Any]:
    """Read and parse a ``manifest.json`` file.

    Parameters
    ----------
    path : Filesystem path to the manifest file.

    Returns
    -------
    The parsed manifest as a ``dict``.

    Raises
    ------
    ModelPackageNotFoundError
        If the file does not exist.
    ModelPackageManifestError
        If the file is not valid JSON.
    """
    p = Path(path)
    if not p.exists():
        raise ModelPackageNotFoundError(f"Manifest not found: {p}")
    try:
        raw = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ModelPackageManifestError(
            f"Failed to read manifest {p}: {exc}"
        ) from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ModelPackageManifestError(
            f"Invalid JSON in manifest {p}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ModelPackageManifestError(
            f"Manifest must be a JSON object, got {type(data).__name__}: {p}"
        )

    return dict(data)


def validate_model_manifest(data: dict[str, Any]) -> dict[str, Any]:
    """Validate a manifest dict against the required schema.

    Parameters
    ----------
    data : Parsed manifest dict.

    Returns
    -------
    The validated manifest dict (unchanged).

    Raises
    ------
    ModelPackageManifestError
        If required fields are missing or have invalid types.
    """
    errors: list[str] = []

    for field, expected_type in _REQUIRED_MANIFEST_FIELDS.items():
        if field not in data:
            errors.append(f"Missing required field: '{field}'")
            continue

        value = data[field]

        if field == "threshold_value":
            if not isinstance(value, (int, float)):
                errors.append(
                    f"'{field}' must be numeric, "
                    f"got {type(value).__name__}: {value!r}"
                )
            continue

        if not isinstance(value, str):
            errors.append(
                f"'{field}' must be a string, "
                f"got {type(value).__name__}: {value!r}"
            )
            continue

        if not value.strip():
            errors.append(f"'{field}' must not be empty")

    if "artifact_type" in data and isinstance(data["artifact_type"], str):
        if data["artifact_type"] != EXPECTED_ARTIFACT_TYPE:
            errors.append(
                f"'artifact_type' is '{data['artifact_type']}', "
                f"expected '{EXPECTED_ARTIFACT_TYPE}'"
            )

    if "model_checksum" in data and isinstance(data["model_checksum"], str):
        if not _SHA256_HEX_PATTERN.match(data["model_checksum"]):
            errors.append(
                f"'model_checksum' is not a valid 64-char hex string: "
                f"'{data['model_checksum']}'"
            )

    if errors:
        raise ModelPackageManifestError("; ".join(errors))

    return data


def validate_model_package(package_dir: str | Path) -> dict[str, Any]:
    """Validate an entire model package directory.

    Checks in order:
    1. ``package_dir`` exists and is a directory.
    2. ``manifest.json`` exists and is valid JSON.
    3. All required manifest fields are present and have correct types.
    4. ``model_filename`` does not escape ``package_dir`` (no path
       traversal).
    5. The model artifact file named by ``model_filename`` exists.
    6. Computed SHA-256 matches ``manifest.model_checksum``.

    Parameters
    ----------
    package_dir : Directory containing the model package.

    Returns
    -------
    The validated manifest dict.

    Raises
    ------
    ModelPackageNotFoundError
        If the directory, manifest, or artifact file is missing.
    ModelPackageManifestError
        If the manifest is invalid or has missing/damaged fields.
    ModelPackageSecurityError
        If ``model_filename`` escapes the package directory.
    ModelPackageChecksumError
        If the computed SHA-256 does not match.
    """
    pkg = Path(package_dir)

    # 1. Directory exists
    if not pkg.exists():
        raise ModelPackageNotFoundError(f"Package directory not found: {pkg}")
    if not pkg.is_dir():
        raise ModelPackageManifestError(
            f"Package path is not a directory: {pkg}"
        )

    # 2. Manifest exists and is valid JSON
    manifest_path = pkg / _MANIFEST_FILENAME
    manifest = read_model_manifest(manifest_path)

    # 3. Required fields
    validate_model_manifest(manifest)

    model_filename = str(manifest["model_filename"])
    model_path = _resolve_safe(pkg, model_filename)

    # 4. Artifact exists
    if not model_path.exists():
        raise ModelPackageNotFoundError(
            f"Model artifact not found: {model_path}"
        )
    if not model_path.is_file():
        raise ModelPackageNotFoundError(
            f"Model artifact is not a regular file: {model_path}"
        )

    # 5. Checksum verification
    computed = compute_sha256(model_path)
    expected = str(manifest["model_checksum"])
    if computed != expected:
        raise ModelPackageChecksumError(
            f"SHA-256 mismatch for {model_path}: "
            f"computed {computed}, expected {expected}"
        )

    return manifest


def summarize_model_package(
    package_dir: str | Path,
) -> ModelPackageSummary:
    """Return a safe summary of a validated model package.

    Parameters
    ----------
    package_dir : Directory containing the model package.

    Returns
    -------
    A ``ModelPackageSummary`` dataclass instance.
    """
    pkg = Path(package_dir)
    manifest = validate_model_package(pkg)
    model_filename = str(manifest["model_filename"])
    model_path = _resolve_safe(pkg, model_filename)

    return ModelPackageSummary(
        package_dir=pkg.resolve(),
        manifest_path=(pkg / _MANIFEST_FILENAME).resolve(),
        model_path=model_path.resolve(),
        model_version=str(manifest.get("model_version", "")),
        model_checksum=str(manifest.get("model_checksum", "")),
        feature_schema_version=str(manifest.get("feature_schema_version", "")),
        threshold_version=str(manifest.get("threshold_version", "")),
        threshold_value=float(manifest.get("threshold_value", 0.0)),
        qc_criteria_version=str(manifest.get("qc_criteria_version", "")),
        training_config_ref=(
            str(manifest["training_config_ref"])
            if "training_config_ref" in manifest
            else None
        ),
        created_at=(
            str(manifest["created_at"]) if "created_at" in manifest else None
        ),
        artifact_type=str(manifest.get("artifact_type", "")),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_safe(base_dir: Path, filename: str) -> Path:
    """Resolve ``filename`` relative to ``base_dir`` with traversal check.

    Raises
    ------
    ModelPackageSecurityError
        If the resolved path escapes ``base_dir`` or is absolute.
    """
    if not filename:
        raise ModelPackageSecurityError("model_filename must not be empty")

    candidate = Path(filename)

    if candidate.is_absolute():
        raise ModelPackageSecurityError(
            f"model_filename must be relative, got absolute path: {filename}"
        )

    # Check for path traversal components
    try:
        resolved = (base_dir / candidate).resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise ModelPackageSecurityError(
            f"Path resolution failed for '{filename}': {exc}"
        ) from exc

    # Ensure the resolved path is within (or equal to) base_dir
    base_resolved = base_dir.resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        raise ModelPackageSecurityError(
            f"model_filename '{filename}' escapes the package directory "
            f"{base_resolved}"
        ) from None

    return resolved
