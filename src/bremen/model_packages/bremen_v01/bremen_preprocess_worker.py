"""Isolated artifact-versioned Bremen preprocessing worker; no platform imports.

Invoked by filename in a Bremen-only Python environment pinned to the
xrd-preprocessing release declared by the active artifact.  Input/output are
private JSON over pipes; estimator objects, probabilities, and decision logic
never cross it.  The worker applies the artifact-owned
``prediction_preprocessing_yaml`` (the authoritative frozen paper-reference
route) and returns only the measurement columns required by feature construction.

This module must NOT import bremen.* (including the platform ``bremen.api``),
mirroring the Aramina ``aramina_preprocess_worker`` isolation rule.
"""

from __future__ import annotations

import contextlib
import io
import json
import logging
import os
import sys
import tempfile

_DIAGNOSTIC_TRANSFORMERS = frozenset({
    "H5ToDataFrameTransformer", "ProductColumnBuilder", "ColumnValueFilter",
    "AzimuthalIntegration", "SNRTransformer", "KeepColumnsTransformer",
})

# Allowlisted failure class names (never raw exception text).
_ALLOWED_EXCEPTION_NAMES = frozenset({
    "ValueError", "TypeError", "KeyError", "IndexError", "AttributeError",
    "ImportError", "ModuleNotFoundError", "RuntimeError", "OSError",
    "MemoryError",
})


def _legacy_container_compat_path(h5_path: str) -> str:
    """Read the source without mutation; add missing identity attrs to a copy.

    The authoritative upstream reader (``xrd_preprocessing.list_h5_sessions``)
    requires root ``schema_version=0.3`` and ``format=xrd-session``.  Some
    supported containers (e.g. Nova_378) carry those attrs only on the
    ``/session`` group.  This package-owned adapter makes a temporary copy with
    the root identity attrs added (when absent) so the artifact-owned pipeline
    can run; the original file is never modified.
    """
    import h5py  # noqa: PLC0415

    with h5py.File(h5_path, "r") as f_in:
        root_attrs = dict(f_in.attrs)
        if root_attrs.get("schema_version") == "0.3" and root_attrs.get("format") in {
            "xrd-session", "xrd-session-archive",
        }:
            return h5_path
        # Only the established single-session legacy layout is supported.
        if "session" not in f_in or any(
            key in root_attrs and root_attrs[key] != expected
            for key, expected in (("format", "xrd-session"), ("schema_version", "0.3"))
        ):
            raise ValueError("Unsupported container identity")
    fd, tmp_path = tempfile.mkstemp(suffix=".h5", prefix="bremen-preprocess-")
    os.close(fd)
    try:
        with h5py.File(h5_path, "r") as f_in, h5py.File(tmp_path, "w") as f_out:
            f_in.copy("/session", f_out, "session")
            for key, value in root_attrs.items():
                f_out.attrs[key] = value
            f_out.attrs.setdefault("schema_version", "0.3")
            f_out.attrs.setdefault("format", "xrd-session")
        return tmp_path
    except Exception:
        os.unlink(tmp_path)
        raise


def _validate_dependency(release: str) -> None:
    """Require the frozen release and exact source commit in the worker."""
    from importlib.metadata import distribution

    installed = distribution("xrd-preprocessing")
    provenance = json.loads(installed.read_text("direct_url.json") or "{}")
    if (release != "v0.1.7-beta" or installed.version != "0.1.7b0"
            or provenance.get("vcs_info", {}).get("commit_id") !=
            "45d5568248e9774b7938a36e028d80e72b130b19"):
        raise ValueError("Unsupported preprocessing dependency")


def main() -> None:
    request = json.load(sys.stdin)
    stage = "worker_imports"
    compat_path: str | None = None
    try:
        # Third-party progress and exceptions must not expose source metadata.
        logging.disable(logging.CRITICAL)
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            import numpy as np
            import yaml
            from xrd_preprocessing import build_pipeline_from_config

            stage = "worker_config"
            config = yaml.safe_load(request["config_yaml"])
            _validate_dependency(config.get("xrd_preprocessing", {}).get("release_tag"))
            stage = "worker_compat"
            h5_path = request["h5"]
            compat_path = _legacy_container_compat_path(h5_path)
            stage = "worker_pipeline_build"
            pipeline = build_pipeline_from_config(config, verbose=False)
            stage = "worker_pipeline_execution"
            df = pipeline.fit_transform(compat_path)
            stage = "worker_output"
            rows = []
            for _, row in df.iterrows():
                rows.append(
                    {
                        "patientId": str(row["patientId"]),
                        "side": str(row["side"]),
                        "position": str(row.get("position", "")),
                        "q_range": np.asarray(
                            row["q_range"], dtype=float
                        ).tolist(),
                        "radial_profile_data": np.asarray(
                            row["radial_profile_data"], dtype=float
                        ).tolist(),
                    }
                )
        print(
            json.dumps(
                {"rows": rows},
                allow_nan=False,
            )
        )
    except Exception as exc:  # noqa: BLE001 -- never emit exception messages
        name = type(exc).__name__
        if name not in _ALLOWED_EXCEPTION_NAMES:
            name = "redacted"
        transformer = "redacted"
        frame = exc.__traceback__
        while frame is not None:
            candidate = type(frame.tb_frame.f_locals.get("self")).__name__
            if candidate in _DIAGNOSTIC_TRANSFORMERS:
                transformer = candidate
            frame = frame.tb_next
        print(json.dumps({
            "error": "BREMEN_PREPROCESSING_FAILED",
            "diagnostic": {"stage": stage, "exception_class": name,
                           "transformer": transformer},
        }))
        raise SystemExit(1) from None
    finally:
        if compat_path and compat_path != request.get("h5"):
            try:
                os.unlink(compat_path)
            except OSError:
                pass


if __name__ == "__main__":
    main()
