"""Bremen v0.1 package-owned preprocessing orchestrator (PR0160).

Runs the ACTIVE artifact's ``prediction_preprocessing_yaml`` in a dedicated,
pinned xrd-preprocessing environment (mirroring the Aramina isolated-worker
pattern).  The platform never reconstructs Bremen scientific preprocessing;
it hands the raw staged container path to the package and the package owns the
complete raw-H5 -> measurement-frame transformation.

The worker emits only safe columns (patientId, side, position,
q_range, radial_profile_data); no estimator
objects or probabilities cross the process boundary.

Release selection is authoritative from the artifact YAML.  The Bremen
paper-reference artifact declares xrd-preprocessing ``v0.1.7-beta``; this
module resolves the pinned interpreter exactly like the Aramina package does
(environment variable override, then a fixed /opt default).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pandas as pd

# The only xrd-preprocessing release declared by the active
# bremen 0.2.0-paper-reference artifact (prediction_preprocessing_yaml).
SUPPORTED_RELEASES: dict[str, tuple[str, str]] = {
    "v0.1.7-beta": (
        "BREMEN_PREPROCESS_PYTHON",
        "/opt/bremen-preprocess/bin/python",
    ),
}


class BremenPreprocessingError(ValueError):
    """A package-owned preprocessing failure with only safe diagnostics."""


def preprocessing_release_tag(config_yaml: str) -> str:
    """Return the artifact-declared release tag only when supported."""
    try:
        import yaml  # noqa: PLC0415

        config = yaml.safe_load(config_yaml)
        release = config.get("xrd_preprocessing", {}).get("release_tag")
    except Exception:  # noqa: BLE001 -- diagnostics must never raise
        return ""
    return release if isinstance(release, str) and release in SUPPORTED_RELEASES else ""


def preprocess_bremen(h5_path: str, config_yaml: str) -> pd.DataFrame:
    """Apply the artifact-owned preprocessing pipeline in the pinned environment.

    Returns authoritative radial profiles/q ranges and side labels.
    Source metadata remains in the existing package-owned PR0159 adapter.

    Raises ``BremenPreprocessingError`` on any failure with only allowlisted
    diagnostics (never exception text, paths, or measurement data).
    """
    try:
        import yaml  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        raise BremenPreprocessingError(
            "Bremen preprocessing configuration could not be loaded"
        ) from exc
    try:
        config = yaml.safe_load(config_yaml)
        steps = config["pipeline"]["steps"]
        release = config["xrd_preprocessing"]["release_tag"]
        supported = isinstance(release, str) and release in SUPPORTED_RELEASES
    except Exception:
        raise BremenPreprocessingError("Bremen preprocessing config is invalid") from None
    if not steps:
        raise BremenPreprocessingError("Bremen preprocessing config is incomplete")
    if not supported:
        raise BremenPreprocessingError("Unsupported Bremen preprocessing release")
    variable, default = SUPPORTED_RELEASES[release]
    executable = os.environ.get(variable, default)
    worker = Path(__file__).with_name("bremen_preprocess_worker.py")
    try:
        completed = subprocess.run(
            [executable, "-I", str(worker)],
            input=json.dumps({"h5": h5_path, "config_yaml": config_yaml}),
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001 -- boundary translation only
        raise BremenPreprocessingError(
            "Bremen preprocessing worker could not be started"
        ) from exc
    if completed.returncode:
        raise BremenPreprocessingError("Bremen preprocessing worker failed")
    try:
        payload = json.loads(completed.stdout)
    except ValueError:
        raise BremenPreprocessingError("Bremen preprocessing produced no output") from None
    if (not isinstance(payload, dict) or set(payload) != {"rows"}
            or not isinstance(payload["rows"], list) or not payload["rows"]):
        raise BremenPreprocessingError("Bremen preprocessing produced no measurement rows")
    return pd.DataFrame(payload["rows"])


__all__ = [
    "BremenPreprocessingError",
    "SUPPORTED_RELEASES",
    "preprocess_bremen",
    "preprocessing_release_tag",
]
