"""Bremen training pipeline CLI entrypoint.

Usage:
    python -m bremen.training.train_classifier --config <training.yaml>

This module is offline-only. Never imported by runtime API or service code.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bremen-training")
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to training config YAML",
    )
    args = parser.parse_args(argv)

    from .pipeline import run_training_from_config  # noqa: PLC0415

    try:
        artifact = run_training_from_config(args.config)
    except Exception as exc:
        print(f"Training failed: {exc}", file=sys.stderr)
        return 1

    print(f"Training complete. Artifact kind: {artifact.get('kind')}")
    print(f"Model version: {artifact.get('version')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
