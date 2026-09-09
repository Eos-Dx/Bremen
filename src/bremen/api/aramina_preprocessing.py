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
        raise ValueError("Aramina preprocessing failed")
    payload = json.loads(completed.stdout)
    if set(payload) != {"rows"} or not payload["rows"]:
        raise ValueError("No valid Aramina measurements")
    return pd.DataFrame(payload["rows"])
