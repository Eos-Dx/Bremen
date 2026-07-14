"""CLI entrypoint for model package publication (dry-run / staging).

Usage:
    python -m bremen.training.publish_model_package \\
        --training-artifact <path> \\
        --output-dir <dir> \\
        --model-version <version> \\
        --feature-schema-version <version> \\
        --threshold-version <version> \\
        --qc-criteria-version <version> \\
        --threshold-key <key> \\
        [--dry-run]

This module is offline-only. Never imported by runtime API or service code.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bremen-publish",
        description="Stage a model package candidate from a training artifact",
    )
    parser.add_argument(
        "--training-artifact",
        required=True,
        type=Path,
        help="Path to training artifact joblib file",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for staged package output",
    )
    parser.add_argument(
        "--model-version",
        required=True,
        help="Runtime model version string",
    )
    parser.add_argument(
        "--feature-schema-version",
        required=True,
        help="Feature schema version string",
    )
    parser.add_argument(
        "--threshold-version",
        required=True,
        help="Threshold version string",
    )
    parser.add_argument(
        "--qc-criteria-version",
        required=True,
        help="QC criteria version string",
    )
    parser.add_argument(
        "--threshold-key",
        default=None,
        help="Key into artifact thresholds.  Default: first available.",
    )
    parser.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Actually write staged files (default is dry-run only)",
    )

    args = parser.parse_args(argv)

    from .model_release import stage_model_package  # noqa: PLC0415

    try:
        summary = stage_model_package(
            artifact_path=args.training_artifact,
            output_dir=args.output_dir,
            model_version=args.model_version,
            model_filename=f"model_{args.model_version}.joblib",
            feature_schema_version=args.feature_schema_version,
            threshold_version=args.threshold_version,
            threshold_key=args.threshold_key,
            qc_criteria_version=args.qc_criteria_version,
            dry_run=not args.no_dry_run,
        )

        print(json.dumps(summary, indent=2))
    except Exception as exc:
        print(f"Publication failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
