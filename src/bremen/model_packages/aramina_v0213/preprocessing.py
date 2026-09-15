"""Run artifact-owned raw H5 preprocessing without changing Bremen's XRD runtime."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pandas as pd
import yaml

# ---------------------------------------------------------------------------
# PR0142 — allowlisted preprocessing subdiagnostics
# ---------------------------------------------------------------------------

# Fixed worker stages. Anything else collapses to worker_process.
PREPROCESSING_STAGES = frozenset({
    "worker_imports",
    "worker_config",
    "worker_pipeline_build",
    "worker_pipeline_execution",
    "worker_output",
    "worker_empty_output",
    "worker_process",
})

# Fixed exception class names. Anything else becomes redacted.
PREPROCESSING_EXCEPTION_CLASSES = frozenset({
    "ValueError", "TypeError", "KeyError", "IndexError", "AttributeError",
    "ImportError", "ModuleNotFoundError", "RuntimeError", "OSError",
    "MemoryError",
})

# Fixed release tags. Anything else becomes redacted.
PREPROCESSING_RELEASES = frozenset({"v0.1.7-beta", "v0.1.9-beta"})

# Stable public reason codes, derived only from the allowlisted stage.
PREPROCESSING_REASON_CODES = {
    "worker_imports": "ARAMINA_PREPROCESSING_WORKER_IMPORTS_FAILED",
    "worker_config": "ARAMINA_PREPROCESSING_CONFIG_FAILED",
    "worker_pipeline_build": "ARAMINA_PREPROCESSING_PIPELINE_BUILD_FAILED",
    "worker_pipeline_execution": "ARAMINA_PREPROCESSING_PIPELINE_EXECUTION_FAILED",
    "worker_output": "ARAMINA_PREPROCESSING_OUTPUT_FAILED",
    "worker_empty_output": "ARAMINA_PREPROCESSING_EMPTY_OUTPUT",
    "worker_process": "ARAMINA_PREPROCESSING_PROCESS_FAILED",
}


def safe_preprocessing_diagnostic(
    diagnostic: object, release: str = "",
) -> dict[str, str]:
    """Collapse a raw worker diagnostic into allowlisted public values.

    Never returns exception text, stdout/stderr, paths, or measurement data.
    Unknown stages become ``worker_process``; unknown exception classes and
    transformers become ``redacted``.
    """
    from .aramina_preprocess_worker import _DIAGNOSTIC_TRANSFORMERS

    raw = diagnostic if isinstance(diagnostic, dict) else {}

    # Accept both the raw worker shape (stage/exception_class/transformer) and
    # an already-sanitized shape (preprocessing_*), so re-sanitizing is
    # idempotent and a caller cannot bypass the allowlist.
    stage = raw.get("stage", raw.get("preprocessing_stage"))
    if not isinstance(stage, str) or stage not in PREPROCESSING_STAGES:
        stage = "worker_process"

    name = raw.get("exception_class", raw.get("preprocessing_exception_class"))
    if not isinstance(name, str) or name not in PREPROCESSING_EXCEPTION_CLASSES:
        name = "redacted"

    transformer = raw.get("transformer", raw.get("preprocessing_transformer"))
    if not isinstance(transformer, str) or transformer not in _DIAGNOSTIC_TRANSFORMERS:
        transformer = "redacted"

    return {
        "preprocessing_stage": stage,
        "preprocessing_exception_class": name,
        "preprocessing_transformer": transformer,
        "preprocessing_release": release if release in PREPROCESSING_RELEASES else "redacted",
        "preprocessing_reason_code": PREPROCESSING_REASON_CODES[stage],
    }


def preprocessing_release_tag(config_yaml: str) -> str:
    """Return the artifact-declared release tag only when allowlisted.

    PR0141: used for safe public diagnostics. Never returns arbitrary
    artifact values, and never raises.
    """
    try:
        config = yaml.safe_load(config_yaml)
        release = config.get("xrd_preprocessing", {}).get("release_tag")
    except Exception:  # noqa: BLE001 -- diagnostics must never raise
        return ""
    return release if release in {"v0.1.7-beta", "v0.1.9-beta"} else ""


class AraminaPreprocessingError(ValueError):
    """A preprocessing failure carrying only allowlisted subdiagnostics.

    The message is a fixed safe string. ``diagnostic`` holds allowlisted
    values only and is safe to surface publicly.
    """

    def __init__(self, diagnostic: dict[str, str]) -> None:
        self.diagnostic = dict(diagnostic)
        super().__init__("Aramina preprocessing failed")


def preprocess_aramina(h5_path: str, config_yaml: str) -> pd.DataFrame:
    """Apply the artifact pipeline in the dedicated, pinned XRD environment.

    Do not resize canonical profiles or substitute feature statistics. No
    estimator or external Aramina package is loaded in the worker.
    """
    config = yaml.safe_load(config_yaml)
    if not isinstance(config, dict) or not config.get("pipeline", {}).get("steps"):
        raise AraminaPreprocessingError(
            safe_preprocessing_diagnostic({"stage": "worker_config"}),
        )
    release = config.get("xrd_preprocessing", {}).get("release_tag")
    environments = {
        "v0.1.7-beta": (
            "BREMEN_ARAMINA_PREPROCESS_PYTHON",
            "/opt/aramina-preprocess/bin/python",
        ),
        "v0.1.9-beta": (
            "BREMEN_ARAMINA_PREPROCESS_019_PYTHON",
            "/opt/aramina-preprocess-019/bin/python",
        ),
    }
    if release not in environments:
        raise AraminaPreprocessingError(
            safe_preprocessing_diagnostic({"stage": "worker_config"}),
        )
    variable, default = environments[release]
    executable = os.environ.get(variable, default)
    worker = Path(__file__).with_name("aramina_preprocess_worker.py")
    try:
        completed = subprocess.run(
            [executable, "-I", str(worker)],
            input=json.dumps({"h5": h5_path, "config_yaml": config_yaml}),
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
    except Exception:  # noqa: BLE001 -- boundary translation only
        # Missing interpreter, timeout, or OS-level spawn failure.
        _log_preprocessing_rejection({"stage": "worker_process"})
        raise AraminaPreprocessingError(
            safe_preprocessing_diagnostic({"stage": "worker_process"}, release),
        ) from None
    if completed.returncode:
        try:
            diagnostic = json.loads(completed.stdout).get("diagnostic", {})
        except (ValueError, AttributeError):
            diagnostic = {}
        _log_preprocessing_rejection(diagnostic)
        # PR0142: carry the allowlisted subdiagnostic to the caller so the
        # public failure can name the exact preprocessing stage.
        raise AraminaPreprocessingError(
            safe_preprocessing_diagnostic(diagnostic, release),
        )
    try:
        payload = json.loads(completed.stdout)
    except ValueError:
        _log_preprocessing_rejection({"stage": "worker_output"})
        raise AraminaPreprocessingError(
            safe_preprocessing_diagnostic({"stage": "worker_output"}, release),
        ) from None
    if set(payload) != {"rows"} or not payload["rows"]:
        _log_preprocessing_rejection({"stage": "worker_empty_output"})
        raise AraminaPreprocessingError(
            safe_preprocessing_diagnostic({"stage": "worker_empty_output"}, release),
        )
    return pd.DataFrame(payload["rows"])


def _log_preprocessing_rejection(diagnostic: dict) -> None:
    """Allowlisted worker diagnostics, never stdout/stderr or measurement data."""
    import logging

    safe = safe_preprocessing_diagnostic(diagnostic)
    try:
        logging.getLogger(__name__).warning(
            "aramina.preprocessing.rejected\tstage=%s\texception_class=%s\ttransformer=%s",
            safe["preprocessing_stage"],
            safe["preprocessing_exception_class"],
            safe["preprocessing_transformer"],
        )
    except Exception:  # noqa: BLE001, S110 -- diagnostics cannot change inference
        pass
