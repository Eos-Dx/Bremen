"""Allowlisted file-based Worker entrypoint for the ML plugin.

Usage (the Harness/parity runner stages these files first)::

    python -m bremen.ml_plugin.entrypoint \
        --release-dir /path/to/release \
        --job-dir /path/to/job

``<job>/request.json`` is the ``bremen.worker.v1`` request; ``<job>/input.h5``
is the staged measurement file (required for ``validate``/``predict``).  The
authoritative output is ``<job>/result.json``.  stdout/stderr are diagnostics
only and are never parsed as a result channel.

A malformed request cannot produce a trustworthy result identity, so the
process exits nonzero without writing ``result.json``; the Harness maps that
to ``PROTOCOL_ERROR``.  Scientific failures are normal ``status=error``
results and exit 0.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from typing import Sequence

from bremen.contracts.worker_protocol import (
    STAGED_INPUT_FILENAME,
    STAGED_REQUEST_FILENAME,
    STAGED_RESULT_FILENAME,
    WorkerProtocolError,
    encode_worker_result,
    validate_worker_request,
)
from bremen.ml_plugin.errors import PluginReleaseError
from bremen.ml_plugin.inference import execute_operation

__all__ = ["main"]

_EXIT_PROTOCOL_ERROR = 2
_EXIT_RELEASE_ERROR = 3


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Standalone bremen.ml-plugin Worker entrypoint",
    )
    parser.add_argument("--release-dir", required=True)
    parser.add_argument("--job-dir", required=True)
    return parser.parse_args(argv)


def _read_request(job_dir: str) -> object:
    path = os.path.join(job_dir, STAGED_REQUEST_FILENAME)
    with open(path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def _write_result(job_dir: str, encoded: str) -> None:
    """Atomically write ``result.json`` inside the job directory."""
    job_real = os.path.realpath(job_dir)
    destination = os.path.join(job_real, STAGED_RESULT_FILENAME)
    if os.path.commonpath([job_real, os.path.realpath(destination)]) != job_real:
        raise PluginReleaseError("result_path_escaped_job_directory")
    handle, temporary = tempfile.mkstemp(
        prefix=".result-", suffix=".json.tmp", dir=job_real,
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    job_dir = os.path.realpath(args.job_dir)
    release_dir = os.path.realpath(args.release_dir)
    if not os.path.isdir(job_dir):
        return _EXIT_RELEASE_ERROR
    if not os.path.isdir(release_dir):
        return _EXIT_RELEASE_ERROR

    try:
        raw_request = _read_request(job_dir)
        request = validate_worker_request(raw_request)  # type: ignore[arg-type]
    except (OSError, ValueError, WorkerProtocolError):
        return _EXIT_PROTOCOL_ERROR

    if request.operation in {"validate", "predict"}:
        staged_input = os.path.join(job_dir, STAGED_INPUT_FILENAME)
        if not os.path.isfile(staged_input) or os.path.islink(staged_input):
            # The request contract already required container_path=="input.h5";
            # its absence is a staging/protocol failure, not a scientific one.
            return _EXIT_PROTOCOL_ERROR

    result = execute_operation(
        request, release_dir=release_dir, job_dir=job_dir,
    )
    encoded = encode_worker_result(result)
    try:
        _write_result(job_dir, encoded)
    except Exception:
        return _EXIT_RELEASE_ERROR
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
