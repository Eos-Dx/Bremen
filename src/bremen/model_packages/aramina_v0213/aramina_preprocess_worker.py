"""Isolated artifact-versioned XRD preprocessing worker; no Bremen or Aramina imports.

Invoked by filename in an Aramina-only Python environment. Input/output are
private JSON over pipes; estimator objects and probabilities never cross it.
"""

from __future__ import annotations

import contextlib
import io
import json
import logging
import os
import sys

_DIAGNOSTIC_TRANSFORMERS = frozenset({
    "H5PoniGeometryCalculatorTransformer", "H5SessionSelectorTransformer",
    "H5ToDataFrameTransformer", "ProductColumnBuilder", "ColumnValueFilter",
    "GroupValueFilter", "ProductStatusGroupFilter", "PairedGroupFilter",
    "FaultyPixelDetector", "ConstantQRangeTransformer", "AzimuthalIntegration",
    "SNRTransformer", "SNRFilter", "PatientSpecimenValidityFilter",
    "QRangeValueNormalizer", "RadialProfileValueFilter", "KeepColumnsTransformer",
})


def _read_explicit_provenance(variable: str) -> dict | None:
    """Read release-shipped, wheel-suitable preprocessing provenance."""
    path = os.environ.get(variable, "")
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as stream:
            record = json.load(stream)
    except Exception:
        raise ValueError("Unreadable preprocessing provenance") from None
    if not isinstance(record, dict):
        raise ValueError("Invalid preprocessing provenance")
    return record


def _validate_provenance(
    release: str, installed_version: str, expected_version: str,
) -> None:
    """Validate the explicit record; preserve the known v0.1.7 commit pin."""
    record = _read_explicit_provenance("BREMEN_ARAMINA_PREPROCESS_PROVENANCE")
    if record is None:
        return
    from importlib.metadata import distribution

    direct = {}
    try:
        direct = json.loads(
            distribution("xrd-preprocessing").read_text("direct_url.json") or "{}"
        )
    except Exception:
        direct = {}
    direct_commit = (direct.get("vcs_info") or {}).get("commit_id")
    known_commits = {
        "v0.1.7-beta": "45d5568248e9774b7938a36e028d80e72b130b19",
        "v0.1.9-beta": "88dcaa277c5a0d4be2ab637bc5827a14bd106bea",
    }
    expected_commit = known_commits[release]
    if (record.get("release_tag") != release
            or record.get("version") != installed_version
            or installed_version != expected_version
            or (direct_commit is not None
                and direct_commit != record.get("source_commit"))
            or record.get("source_commit") != expected_commit):
        raise ValueError("Unsupported preprocessing provenance")


def main() -> None:
    request = json.load(sys.stdin)
    stage = "worker_imports"
    try:
        # Third-party progress and exceptions must not expose source metadata.
        logging.disable(logging.CRITICAL)
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            from importlib.metadata import version

            import numpy as np
            import pandas as pd
            import yaml
            from xrd_preprocessing import build_pipeline_from_config

            stage = "worker_config"
            config = yaml.safe_load(request["config_yaml"])
            expected = {"v0.1.7-beta": "0.1.7b0", "v0.1.9-beta": "0.1.9b0"}.get(
                config.get("xrd_preprocessing", {}).get("release_tag"),
            )
            if expected is None or version("xrd-preprocessing") != expected:
                raise ValueError("Unsupported preprocessing version")
            _validate_provenance(
                config.get("xrd_preprocessing", {}).get("release_tag"),
                version("xrd-preprocessing"), expected,
            )
            stage = "worker_pipeline_build"
            config["io"] = {}
            pipeline = build_pipeline_from_config(config, verbose=False)
            stage = "worker_pipeline_execution"
            df = pipeline.fit_transform(request["h5"])
            stage = "worker_output"
            rows = []
            for _, row in df.iterrows():
                age = pd.to_numeric(row.get("age"), errors="coerce")
                rows.append(
                    {
                        "patientId": str(row["patientId"]),
                        "side": str(row["side"]),
                        "age": float(age) if pd.notna(age) else None,
                        "radial_profile_data": np.asarray(
                            row["radial_profile_data"], dtype=float
                        ).tolist(),
                        "q_range": np.asarray(row["q_range"], dtype=float).tolist(),
                    }
                )
        print(json.dumps({"rows": rows}, allow_nan=False))
    except Exception as exc:  # noqa: BLE001 -- never emit exception messages
        name = type(exc).__name__
        if name not in {"ValueError", "TypeError", "KeyError", "IndexError", "AttributeError",
                        "ImportError", "ModuleNotFoundError", "RuntimeError", "OSError", "MemoryError"}:
            name = "redacted"
        transformer = "redacted"
        frame = exc.__traceback__
        while frame is not None:
            candidate = type(frame.tb_frame.f_locals.get("self")).__name__
            if candidate in _DIAGNOSTIC_TRANSFORMERS:
                transformer = candidate
            frame = frame.tb_next
        print(json.dumps({"error": "ARAMINA_PREPROCESSING_FAILED",
                          "diagnostic": {"stage": stage, "exception_class": name,
                                         "transformer": transformer}}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
