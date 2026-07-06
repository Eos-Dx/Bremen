"""Model package release helpers — offline publication tooling only.

Converts a Bremen training artifact into an ADR-0007-compatible runtime
model package candidate. No AWS calls, no network access, no inference.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from bremen.model_package import EXPECTED_ARTIFACT_TYPE

from .pipeline import REQUIRED_TRAINING_ARTIFACT_FIELDS


REQUIRED_RUNTIME_MANIFEST_FIELDS = (
    "artifact_type",
    "model_version",
    "model_checksum",
    "model_filename",
    "feature_schema_version",
    "threshold_version",
    "threshold_value",
    "qc_criteria_version",
)

MANIFEST_FILENAME = "manifest.json"


# ---------------------------------------------------------------------------
# Training artifact validation
# ---------------------------------------------------------------------------


def load_training_artifact(path: str | Path) -> dict[str, Any]:
    """Load and validate a Bremen training artifact joblib file.

    Verifies:
    - File exists and is a valid joblib file.
    - Loaded object is a dict.
    - ``kind == "bremen_training_artifact"``.
    - All required training artifact fields are present.

    Raises ``ValueError`` with descriptive message on any failure.
    Does NOT load arbitrary joblib files — only validated training artifacts.
    """
    path = Path(path)
    if not path.exists():
        raise ValueError(f"Training artifact not found: {path}")

    from joblib import load as _jl  # noqa: PLC0415

    obj = _jl(path)

    if not isinstance(obj, dict):
        raise ValueError(
            f"Training artifact must be a dict, got {type(obj).__name__}"
        )

    return validate_training_artifact(obj)


def validate_training_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    """Validate a training artifact dict in memory.

    Checks all ``REQUIRED_TRAINING_ARTIFACT_FIELDS`` are present.
    Checks ``kind == "bremen_training_artifact"``.

    Returns the validated artifact.
    Raises ``ValueError`` on failure.
    """
    if artifact.get("kind") != "bremen_training_artifact":
        raise ValueError(
            f"Invalid training artifact kind: "
            f"'{artifact.get('kind', '(missing)')}'. "
            f"Expected 'bremen_training_artifact'."
        )

    missing: list[str] = []
    for field in REQUIRED_TRAINING_ARTIFACT_FIELDS:
        if field not in artifact:
            missing.append(field)

    if missing:
        raise ValueError(
            f"Training artifact missing required fields: {missing}"
        )

    return artifact


# ---------------------------------------------------------------------------
# Runtime manifest construction
# ---------------------------------------------------------------------------


def build_runtime_manifest(
    artifact: dict[str, Any],
    *,
    model_version: str,
    model_filename: str,
    feature_schema_version: str,
    threshold_version: str,
    threshold_key: str | None,
    qc_criteria_version: str,
    model_checksum: str,
) -> dict[str, Any]:
    """Build an ADR-0007-compatible runtime model package manifest dict.

    Parameters
    ----------
    artifact : The validated training artifact dict.
    model_version : Explicit model version for the runtime manifest.
    model_filename : The filename of the staged model artifact
        (relative path within the package directory).
    feature_schema_version : Explicit feature schema version.
    threshold_version : Explicit threshold version string.
    threshold_key : Key into ``artifact["thresholds"]`` for the
        threshold value.  If ``None``, use the first available.
    qc_criteria_version : Explicit QC criteria version.
    model_checksum : SHA-256 hex digest of the staged model joblib file.

    Returns a dict with the exact field names and types expected by
    ``model_package.py``::

        {
            "artifact_type": "bremen.joblib.model_package",
            "model_version": str,
            "model_checksum": str,
            "model_filename": str,
            "feature_schema_version": str,
            "threshold_version": str,
            "threshold_value": float,
            "qc_criteria_version": str,
        }

    Raises ``ValueError`` if required inputs are missing or invalid.
    """
    if not model_version or not isinstance(model_version, str):
        raise ValueError("model_version is required and must be a string")

    if not model_filename or not isinstance(model_filename, str):
        raise ValueError("model_filename is required and must be a string")

    if model_filename.startswith("/"):
        raise ValueError(
            f"model_filename must be relative, got absolute: {model_filename}"
        )

    if not isinstance(model_checksum, str) or len(model_checksum) != 64:
        raise ValueError(
            f"model_checksum must be a 64-char hex string, "
            f"got {len(model_checksum)} chars"
        )

    # Select threshold
    thresholds = artifact.get("thresholds", {})
    if not isinstance(thresholds, dict):
        raise ValueError(
            f"artifact['thresholds'] must be a dict, "
            f"got {type(thresholds).__name__}"
        )
    if not thresholds:
        raise ValueError(
            "artifact['thresholds'] is empty — at least one threshold required"
        )

    if threshold_key is not None:
        if threshold_key not in thresholds:
            raise ValueError(
                f"Threshold key '{threshold_key}' not found in artifact "
                f"thresholds. Available keys: {list(thresholds.keys())}"
            )
        threshold_value = float(thresholds[threshold_key])
    else:
        # Use first available threshold value
        first_key = next(iter(thresholds))
        threshold_value = float(thresholds[first_key])

    manifest = {
        "artifact_type": EXPECTED_ARTIFACT_TYPE,
        "model_version": model_version,
        "model_checksum": model_checksum,
        "model_filename": model_filename,
        "feature_schema_version": feature_schema_version,
        "threshold_version": threshold_version,
        "threshold_value": threshold_value,
        "qc_criteria_version": qc_criteria_version,
    }

    return manifest


# ---------------------------------------------------------------------------
# Local staging
# ---------------------------------------------------------------------------


def stage_model_package(
    artifact_path: str | Path,
    output_dir: str | Path,
    *,
    model_version: str,
    model_filename: str | None,
    feature_schema_version: str,
    threshold_version: str,
    threshold_key: str | None,
    qc_criteria_version: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Stage a local model package candidate from a training artifact.

    Steps:
    1. Load and validate the training artifact.
    2. Compute SHA-256 of the artifact file (or copied joblib).
    3. Build the runtime manifest.
    4. Write ``manifest.json`` and the model joblib file.
    5. Return a dry-run summary dict.

    Parameters
    ----------
    artifact_path : Path to the training artifact joblib file.
    output_dir : Directory where package files will be staged.
    model_version : Runtime model version for the manifest.
    model_filename : Filename for the copied model joblib file.
        Defaults to ``f"model_{model_version}.joblib"`` if not provided.
    feature_schema_version : Feature schema version.
    threshold_version : Threshold version string.
    threshold_key : Key into artifact thresholds.
    qc_criteria_version : QC criteria version.
    dry_run : When ``True`` (default), validate inputs and print plan
        but do NOT write files.  Writes files only when ``False``.

    Returns
    -------
    A dry-run summary dict containing the publication plan (intended
    paths, filenames, manifest fields, S3 URIs).  No files are written
    when ``dry_run=True``.
    """
    artifact_path = Path(artifact_path)
    output_dir = Path(output_dir)

    # 1. Load and validate the training artifact
    artifact = load_training_artifact(artifact_path)

    # 2. Determine model filename
    if model_filename is None:
        model_filename = f"model_{model_version}.joblib"

    # 3. Compute SHA-256 of the artifact file
    model_checksum = _compute_file_sha256(artifact_path)

    # 4. Build the runtime manifest
    manifest = build_runtime_manifest(
        artifact=artifact,
        model_version=model_version,
        model_filename=model_filename,
        feature_schema_version=feature_schema_version,
        threshold_version=threshold_version,
        threshold_key=threshold_key,
        qc_criteria_version=qc_criteria_version,
        model_checksum=model_checksum,
    )

    # 5. Stage files (or dry-run)
    if not dry_run:
        _write_staged_package(
            artifact_path=artifact_path,
            output_dir=output_dir,
            model_filename=model_filename,
            manifest=manifest,
        )

    summary = _build_dry_run_summary(
        manifest=manifest,
        output_dir=output_dir,
        model_filename=model_filename,
        files_written=not dry_run,
    )

    return summary


def _write_staged_package(
    *,
    artifact_path: Path,
    output_dir: Path,
    model_filename: str,
    manifest: dict[str, Any],
) -> None:
    """Write manifest.json and copy model joblib to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy the training artifact as the model artifact
    model_path = output_dir / model_filename
    shutil.copy2(artifact_path, model_path)

    # Write manifest.json
    manifest_path = output_dir / MANIFEST_FILENAME
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _build_dry_run_summary(
    *,
    manifest: dict[str, Any],
    output_dir: Path,
    model_filename: str,
    files_written: bool,
) -> dict[str, Any]:
    """Build the dry-run summary dict."""
    return {
        "package_staging_dir": str(output_dir.resolve()),
        "manifest_path": str(output_dir / MANIFEST_FILENAME),
        "model_path": str(output_dir / model_filename),
        "intended_s3_uri": None,
        "manifest_fields": dict(manifest),
        "files_written": files_written,
    }


# ---------------------------------------------------------------------------
# Dry-run S3 publication summary
# ---------------------------------------------------------------------------


def dry_run_publication_summary(
    manifest: dict[str, Any],
    output_dir: str | Path,
    *,
    bucket: str | None = None,
    prefix: str | None = None,
) -> dict[str, Any]:
    """Generate a dry-run S3 publication summary without network calls.

    Parameters
    ----------
    manifest : The built runtime manifest dict.
    output_dir : Local staging directory.
    bucket : Intended S3 bucket name (optional, for URI generation).
    prefix : Intended S3 key prefix (optional, for URI generation).

    Returns a dict with::

        {
            "package_staging_dir": str,
            "manifest_path": str,
            "model_path": str,
            "intended_s3_uri": str or None,
            "manifest_fields": dict,
        }

    No AWS calls, no network access, no file writes.
    """
    output_dir = Path(output_dir)

    intended_s3_uri: str | None = None
    if bucket:
        prefix_str = f"{prefix}/" if prefix else ""
        intended_s3_uri = (
            f"s3://{bucket}/{prefix_str}{manifest.get('model_version', 'unknown')}/"
        )

    return {
        "package_staging_dir": str(output_dir.resolve()),
        "manifest_path": str(output_dir / MANIFEST_FILENAME),
        "model_path": str(
            output_dir / manifest.get("model_filename", "model.joblib")
        ),
        "intended_s3_uri": intended_s3_uri,
        "manifest_fields": dict(manifest),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_file_sha256(path: str | Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
