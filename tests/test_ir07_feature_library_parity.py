"""IR-07 differential parity: embedded Bremen/Aramina feature code vs the
standalone ``xrd_inference_features`` extraction.

This is the hard gate required before release-backed Worker execution may
switch to the external feature library: every value produced by the
byte-identical extraction must equal the frozen embedded implementation's
output, in exact order, on representative frozen fixtures. No scientific
tolerance is invented here — exact equality is required because both
implementations are deterministic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# The standalone feature library is never a Bremen/App Runner application
# dependency (it is release-bound only, see IR-07); it is not installed into
# this repo's app venv. This test module needs it importable purely to run
# the differential comparison, so it adds the package's own src/ directory to
# sys.path for this test file only, instead of installing the distribution.
_FEATURE_LIBRARY_SRC = (
    Path(__file__).resolve().parents[1]
    / "packages" / "xrd-inference-features" / "src"
)
if str(_FEATURE_LIBRARY_SRC) not in sys.path:
    sys.path.insert(0, str(_FEATURE_LIBRARY_SRC))

from bremen.model_packages.bremen_v01.features import (
    FEATURE_COLS as EMBEDDED_FEATURE_COLS,
    build_bremen_features as embedded_build_bremen_features,
)
from bremen.model_packages.aramina_v0213.symmetry import (
    CORE4 as EMBEDDED_CORE4,
    symmetry_features as embedded_symmetry_features,
)

from xrd_inference_features.bremen_contract import (
    FEATURE_COLS as LIBRARY_FEATURE_COLS,
    build_bremen_features as library_build_bremen_features,
)
from xrd_inference_features.aramina_symmetry import (
    CORE4 as LIBRARY_CORE4,
    symmetry_features as library_symmetry_features,
)

from tests.bremen_3x3_helpers import make_case


def test_feature_order_identical() -> None:
    assert EMBEDDED_FEATURE_COLS == LIBRARY_FEATURE_COLS


def test_core4_identical() -> None:
    assert EMBEDDED_CORE4 == LIBRARY_CORE4


def test_bremen_15_features_exact_parity_on_frozen_fixture() -> None:
    measurements = make_case().measurements
    embedded = embedded_build_bremen_features(measurements)
    library = library_build_bremen_features(measurements)
    assert list(embedded) == list(library) == EMBEDDED_FEATURE_COLS
    for name in EMBEDDED_FEATURE_COLS:
        np.testing.assert_allclose(
            library[name], embedded[name], rtol=0, atol=0,
            err_msg=f"feature {name!r} diverged between embedded and library implementations",
        )


def test_bremen_15_features_exact_parity_left_right_permuted() -> None:
    """Permuting the order measurements are supplied in must not matter, and
    both implementations must agree on that invariance identically."""
    measurements = make_case().measurements
    permuted = tuple(reversed(measurements))
    embedded = embedded_build_bremen_features(permuted)
    library = library_build_bremen_features(permuted)
    for name in EMBEDDED_FEATURE_COLS:
        np.testing.assert_allclose(library[name], embedded[name], rtol=0, atol=0)


def _symmetry_frame(seed: int, n_target: int, n_contralateral: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    q = np.linspace(2.0, 25.0, 400)
    rows = []
    for _ in range(n_target):
        y = 1.0 + 0.05 * rng.standard_normal(q.size) + np.exp(-((q - 14.0) ** 2) / (2 * 0.3**2))
        rows.append({"side": "LEFT", "q_range": q, "radial_profile_data": y})
    for _ in range(n_contralateral):
        y = 1.0 + 0.05 * rng.standard_normal(q.size) + 0.8 * np.exp(-((q - 14.0) ** 2) / (2 * 0.3**2))
        rows.append({"side": "RIGHT", "q_range": q, "radial_profile_data": y})
    return pd.DataFrame(rows)


@pytest.mark.parametrize("contract", ["aramina_sk_symmetry_v0_1", "aramina_sk_symmetry_v0_2"])
@pytest.mark.parametrize("n_target,n_contralateral", [(1, 1), (2, 2), (3, 3)])
def test_aramina_symmetry_exact_parity(contract, n_target, n_contralateral) -> None:
    frame = _symmetry_frame(seed=hash((contract, n_target, n_contralateral)) % (2**31), n_target=n_target, n_contralateral=n_contralateral)
    embedded = embedded_symmetry_features(frame, "left", contract)
    library = library_symmetry_features(frame, "left", contract)
    assert set(embedded) == set(library) == set(EMBEDDED_CORE4) | {"symmetry_available"}
    for name in embedded:
        np.testing.assert_allclose(library[name], embedded[name], rtol=0, atol=0)


@pytest.mark.parametrize("contract", ["aramina_sk_symmetry_v0_1", "aramina_sk_symmetry_v0_2"])
def test_aramina_symmetry_exact_parity_neutral_no_contralateral(contract) -> None:
    q = np.linspace(2.0, 25.0, 400)
    frame = pd.DataFrame(
        [{"side": "LEFT", "q_range": q, "radial_profile_data": np.ones(q.size)}]
    )
    embedded = embedded_symmetry_features(frame, "left", contract)
    library = library_symmetry_features(frame, "left", contract)
    assert embedded == library


# ---------------------------------------------------------------------------
# Backend selection is explicit and release-scoped (not import-presence based)
# ---------------------------------------------------------------------------


def test_backend_default_is_embedded_even_with_library_importable() -> None:
    """Regression guard: this test file makes xrd_inference_features
    importable (via the sys.path insertion above) for its own differential
    checks. That must never silently flip bremen_v01/aramina_v0213 runtime
    behavior for legacy (non-release) execution — only the explicit
    BREMEN_FEATURE_LIBRARY_BACKEND env var may do that."""
    import os

    from bremen.model_packages.bremen_v01 import runtime as bremen_runtime
    from bremen.model_packages.aramina_v0213 import inference as aramina_inference

    assert os.environ.get("BREMEN_FEATURE_LIBRARY_BACKEND") is None
    assert bremen_runtime._use_external_feature_backend() is False
    assert aramina_inference._use_external_feature_backend() is False


def test_backend_flips_on_explicit_env_var(monkeypatch) -> None:
    from bremen.model_packages.bremen_v01 import runtime as bremen_runtime
    from bremen.model_packages.aramina_v0213 import inference as aramina_inference

    monkeypatch.setenv("BREMEN_FEATURE_LIBRARY_BACKEND", "xrd_inference_features")
    assert bremen_runtime._use_external_feature_backend() is True
    assert aramina_inference._use_external_feature_backend() is True


# ---------------------------------------------------------------------------
# Harness/platform parent import boundary (NEXT 5): must never import the
# standalone feature library, with or without it installed.
# ---------------------------------------------------------------------------


def test_platform_parent_modules_do_not_import_feature_library() -> None:
    import ast

    repo_root = Path(__file__).resolve().parents[1]
    parent_modules = [
        repo_root / "src" / "bremen" / "platform" / "models" / "discovery.py",
        repo_root / "src" / "bremen" / "platform" / "models" / "release_cache.py",
        repo_root / "src" / "bremen" / "platform" / "runtime" / "registry.py",
        repo_root / "src" / "bremen" / "platform" / "runtime" / "subprocess_runtime.py",
        repo_root / "src" / "bremen" / "contracts" / "inference_release.py",
    ]
    for path in parent_modules:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("xrd_inference_features"), path
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not module.startswith("xrd_inference_features"), path


def test_platform_discovery_and_registry_import_without_feature_library() -> None:
    """The Harness/platform parent must work with xrd_inference_features
    unavailable in the parent environment.

    Runs in a fresh subprocess (not this test process) so that blocking the
    import can never corrupt shared module-level singleton state (e.g. the
    runtime registry) for other tests running later in the same session.
    """
    import subprocess
    import sys as _sys

    script = (
        "import builtins, importlib, sys\n"
        "real_import = builtins.__import__\n"
        "def _blocking_import(name, *a, **kw):\n"
        "    if name == 'xrd_inference_features' or name.startswith('xrd_inference_features.'):\n"
        "        raise ImportError('blocked for parent-boundary test: ' + name)\n"
        "    return real_import(name, *a, **kw)\n"
        "builtins.__import__ = _blocking_import\n"
        "for name in ("
        "    'bremen.platform.models.discovery',"
        "    'bremen.platform.models.release_cache',"
        "    'bremen.platform.runtime.registry',"
        "    'bremen.platform.runtime.subprocess_runtime',"
        "    'bremen.contracts.inference_release',"
        "):\n"
        "    importlib.import_module(name)\n"
        "    assert 'xrd_inference_features' not in sys.modules, name\n"
        "print('OK')\n"
    )
    repo_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [_sys.executable, "-c", script],
        cwd=str(repo_root),
        env={"PYTHONPATH": str(repo_root / "src")},
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == "OK"
