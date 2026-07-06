"""Publish the human-provided bremen_v0.1.joblib as a runtime model package.

Usage:
    python -m bremen.training.publish_v01 --joblib-path <path> --output-dir <dir>

Requires explicit metadata flags or will derive from defaults.
Dry-run by default. Use --no-dry-run to stage files locally.

This module is offline-only tooling. Never imported by runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

MANIFEST_FILENAME = "manifest.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bremen-publish-v01",
        description="Package bremen_v0.1.joblib into a runtime model package",
    )
    parser.add_argument(
        "--joblib-path",
        required=True,
        type=Path,
        help="Path to the bremen_v0.1.joblib file (outside repo)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Output directory for the staged model package",
    )
    parser.add_argument(
        "--model-version",
        default="v0.1",
        help="Model version (default: v0.1)",
    )
    parser.add_argument(
        "--feature-schema-version",
        required=True,
        help="Feature schema version string (required)",
    )
    parser.add_argument(
        "--threshold-version",
        default="v0.1",
        help="Threshold version (default: v0.1)",
    )
    parser.add_argument(
        "--threshold-value",
        type=float,
        default=0.5,
        help="Decision threshold value (default: 0.5)",
    )
    parser.add_argument(
        "--qc-criteria-version",
        default="v0.1",
        help="QC criteria version (default: v0.1)",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Actually stage files (default is dry-run only)",
    )
    args = parser.parse_args(argv)

    joblib_path = Path(args.joblib_path)
    if not joblib_path.exists():
        print(f"Error: joblib not found: {joblib_path}", file=sys.stderr)
        return 1

    # Compute checksum
    checksum = _sha256(joblib_path)

    # Build manifest
    manifest = _build_manifest(
        model_version=args.model_version,
        model_checksum=checksum,
        model_filename=joblib_path.name,
        feature_schema_version=args.feature_schema_version,
        threshold_version=args.threshold_version,
        threshold_value=args.threshold_value,
        qc_criteria_version=args.qc_criteria_version,
    )

    output_dir = Path(args.output_dir)

    # Stage or dry-run
    if not args.no_dry_run:
        print("=== DRY RUN ===")
        print(json.dumps(manifest, indent=2))
        print(f"Would stage to: {output_dir.resolve()}")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        model_target = output_dir / joblib_path.name
        shutil.copy2(joblib_path, model_target)
        (output_dir / MANIFEST_FILENAME).write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        print(f"Staged model package to: {output_dir.resolve()}")
        print(f"Manifest: {output_dir / MANIFEST_FILENAME}")
        print(f"Model: {model_target}")

    print(f"\nChecksum (SHA-256): {checksum}")
    print(f"Model version: {args.model_version}")

    return 0


def _build_manifest(
    *,
    model_version: str,
    model_checksum: str,
    model_filename: str,
    feature_schema_version: str,
    threshold_version: str,
    threshold_value: float,
    qc_criteria_version: str,
) -> dict[str, Any]:
    """Build ADR-0007-compatible manifest for v0.1."""
    return {
        "artifact_type": "bremen.joblib.model_package",
        "model_version": model_version,
        "model_checksum": model_checksum,
        "model_filename": model_filename,
        "feature_schema_version": feature_schema_version,
        "threshold_version": threshold_version,
        "threshold_value": threshold_value,
        "qc_criteria_version": qc_criteria_version,
    }


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
