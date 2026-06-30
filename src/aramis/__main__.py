"""Command-line entrypoint for Aramis product workflows."""

from __future__ import annotations

import argparse
from pathlib import Path

from .pipelines import run_preprocessing_from_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aramis")
    subparsers = parser.add_subparsers(dest="command", required=True)

    preprocess = subparsers.add_parser(
        "preprocess",
        help="Build an Aramis preprocessing DataFrame from a YAML config.",
    )
    preprocess.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to Aramis preprocessing YAML.",
    )

    args = parser.parse_args(argv)
    if args.command == "preprocess":
        df = run_preprocessing_from_config(args.config)
        print(f"rows={len(df)}")
        print(f"columns={len(df.columns)}")
        print(f"config={args.config}")
        return 0
    raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
