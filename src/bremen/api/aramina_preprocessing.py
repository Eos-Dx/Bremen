"""Run artifact-owned raw H5 preprocessing without changing Bremen's XRD runtime."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pandas as pd
import yaml


def preprocess_aramina(h5_path: str, config_yaml: str) -> pd.DataFrame:
    """Apply the artifact pipeline in the dedicated, pinned XRD environment.

    Do not resize canonical profiles or substitute feature statistics. No
    estimator or external Aramina package is loaded in the worker.
    """
    config = yaml.safe_load(config_yaml)
    if not isinstance(config, dict) or not config.get("pipeline", {}).get("steps"):
        raise ValueError("Missing artifact preprocessing pipeline")
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
        raise ValueError("Unsupported artifact preprocessing release")
    variable, default = environments[release]
    executable = os.environ.get(variable, default)
    worker = Path(__file__).with_name("aramina_preprocess_worker.py")
    completed = subprocess.run(
        [executable, "-I", str(worker)],
        input=json.dumps({"h5": h5_path, "config_yaml": config_yaml}),
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    if completed.returncode:
        try:
            diagnostic = json.loads(completed.stdout).get("diagnostic", {})
        except (ValueError, AttributeError):
            diagnostic = {}
        _log_preprocessing_rejection(diagnostic)
        raise ValueError("Aramina preprocessing failed")
    payload = json.loads(completed.stdout)
    if set(payload) != {"rows"} or not payload["rows"]:
        _log_preprocessing_rejection({"stage": "worker_empty_output"})
        raise ValueError("No valid Aramina measurements")
    return pd.DataFrame(payload["rows"])


def _log_preprocessing_rejection(diagnostic: dict) -> None:
    """Allowlisted worker diagnostics, never stdout/stderr or measurement data."""
    import logging

    if not isinstance(diagnostic, dict):
        diagnostic = {}
    stage = diagnostic.get("stage")
    if not isinstance(stage, str) or stage not in {"worker_imports", "worker_config", "worker_pipeline_build",
                     "worker_pipeline_execution", "worker_output", "worker_empty_output"}:
        stage = "worker_process"
    name = diagnostic.get("exception_class")
    if not isinstance(name, str) or name not in {"ValueError", "TypeError", "KeyError", "IndexError", "AttributeError",
                    "ImportError", "ModuleNotFoundError", "RuntimeError", "OSError", "MemoryError"}:
        name = "redacted"
    from .aramina_preprocess_worker import _DIAGNOSTIC_TRANSFORMERS
    transformer = diagnostic.get("transformer")
    if not isinstance(transformer, str) or transformer not in _DIAGNOSTIC_TRANSFORMERS:
        transformer = "redacted"
    try:
        logging.getLogger(__name__).warning(
            "aramina.preprocessing.rejected\tstage=%s\texception_class=%s\ttransformer=%s",
            stage, name, transformer,
        )
    except Exception:  # noqa: BLE001, S110 -- diagnostics cannot change inference
        pass
