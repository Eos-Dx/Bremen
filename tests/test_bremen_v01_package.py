"""Direct Bremen v0.1 model-package golden tests (PR0154).

These invoke the inference-complete package runtime WITHOUT the
WorkflowProvider, proving the package can execute model science
independently of platform orchestration:

- exact 15 features and probability vs the PR0151 frozen fixture
  (atol 1e-10, rtol 0),
- decision/threshold behavior,
- exact 3+3 requirements and validation, invalid-shape behavior,
- all-six participation, LEFT/RIGHT permutation invariance,
- replicate variance and peak semantics,
- portable estimator + threshold parity,
- import-direction guarantees.

Research decision support requiring radiologist review; no clinical claim.
"""
from __future__ import annotations

import ast
import math
from dataclasses import replace
from itertools import permutations
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from bremen.model_packages import bremen_v01
from bremen.model_packages.bremen_v01 import manifest
from bremen.model_packages.bremen_v01.features import (
    FEATURE_COLS, build_bremen_features, validate_bremen_shape,
)
from bremen.model_packages.bremen_v01.predictor import (
    predict_proba_portable, validate_portable_logreg_model,
)
from bremen.model_packages.bremen_v01.runtime import (
    BremenFeatureError, BremenRuntime,
)
from bremen.contracts.model_runtime import (
    ModelInput, ModelRequirements, ModelRuntime, RuntimePrediction,
)
from tests.bremen_3x3_helpers import DETAIL, GOLD, MODEL, make_case
from tests.reference_0151.features import build_feature_frame
from tests.reference_0151.prediction import predict_proba_portable as reference_score


SRC = Path(__file__).parents[1] / "src" / "bremen"
PKG = SRC / "model_packages" / "bremen_v01"


def assert_close(actual, expected):
    np.testing.assert_allclose(actual, expected, atol=1e-10, rtol=0)


def reference_vector(measurements):
    frame = pd.DataFrame([
        dict(patientId="synthetic", side=m.side, q_range=m.q, radial_profile_data=m.intensity)
        for m in measurements
    ])
    features, errors = build_feature_frame(frame)
    assert errors.empty
    return features[GOLD["feature_names"]].iloc[0].to_numpy()


# ---------------------------------------------------------------------------
# Entry point + contract
# ---------------------------------------------------------------------------


def test_package_exposes_single_runtime_entry_point():
    assert hasattr(bremen_v01, "BremenRuntime")
    runtime = bremen_v01.BremenRuntime(MODEL)
    assert isinstance(runtime, ModelRuntime)


def test_package_runtime_satisfies_contract_without_provider():
    runtime = BremenRuntime(MODEL)
    for member in ("model_requirements", "validate_model_input", "predict_model"):
        assert callable(getattr(runtime, member))


# ---------------------------------------------------------------------------
# Direct golden inference (no WorkflowProvider)
# ---------------------------------------------------------------------------


def test_package_golden_features_and_probability_no_provider():
    runtime = BremenRuntime(MODEL)
    features = runtime.build_features(make_case().measurements)
    assert list(features.feature_names) == GOLD["feature_names"]
    assert_close(features.feature_values, GOLD["expected_features"])

    result = runtime.run(make_case().measurements)
    assert_close(result.probability, GOLD["expected_probability"])
    assert result.probability == pytest.approx(0.7388733541967353, abs=1e-10)
    assert result.threshold == MODEL["portable_logreg"]["threshold"]
    assert result.prediction == 1
    assert result.decision.is_positive


def test_package_predict_model_contract_no_provider():
    prediction = BremenRuntime(MODEL).predict_model(
        ModelInput(workflow_id="bremen", measurements=make_case().measurements),
    )
    assert isinstance(prediction, RuntimePrediction)
    assert prediction.workflow_id == "bremen"
    assert prediction.model_id == manifest.MODEL_ID
    assert math.isclose(
        prediction.result["probability"], GOLD["expected_probability"], abs_tol=1e-10,
    )
    assert prediction.result["decision_code"] == "CONTINUE_MRI"
    assert prediction.result["threshold_applied"] == MODEL["portable_logreg"]["threshold"]


# ---------------------------------------------------------------------------
# Requirements ownership (package manifest authoritative)
# ---------------------------------------------------------------------------


def test_package_requirements_exact_three_plus_three():
    req = BremenRuntime(MODEL).model_requirements()
    assert isinstance(req, ModelRequirements)
    assert req.workflow_id == "bremen"
    assert req.model_id == manifest.MODEL_ID == "bremen-paper-reference-v0-2-0"
    assert req.model_version == manifest.MODEL_VERSION == "0.2.0-paper-reference"
    assert req.feature_schema_version == "v0.1"
    assert dict(req.measurement_sides) == {"LEFT": 3, "RIGHT": 3}
    assert req.total_measurements == 6
    assert req.requires_target_side is False


def test_manifest_identity_matches_pr0151_evidence():
    assert manifest.MODEL_ID == "bremen-paper-reference-v0-2-0"
    assert manifest.MODEL_NAME == "bremen_paper_reference_symmetry_logreg"
    assert manifest.MODEL_VERSION == "0.2.0-paper-reference"
    assert manifest.THRESHOLD_VALUE == 0.3585907282566089
    assert manifest.ARTIFACT_SHA256 == (
        "65866f441a119cddeb965e5c414c9f87aafd46ec5fd7a866cf9f0fef408df3b0"
    )
    assert manifest.MEASUREMENT_SIDES == (("LEFT", 3), ("RIGHT", 3))
    assert manifest.TOTAL_MEASUREMENTS == 6


# ---------------------------------------------------------------------------
# Validation: exact 3+3 and invalid shapes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("left,right", [
    (3, 2), (2, 3), (4, 2), (2, 4), (1, 1), (0, 6), (6, 0), (3, 4), (0, 0),
])
def test_package_validation_invalid_shapes(left, right):
    case = make_case()
    ms = (case.measurements[0],) * left + (case.measurements[3],) * right
    validation = BremenRuntime(MODEL).validate_model_input(
        ModelInput(workflow_id="bremen", measurements=ms),
    )
    assert validation.compatible is False
    assert validation.safe_reason == "requires_exactly_3_left_3_right"
    with pytest.raises(BremenFeatureError, match="^requires_exactly_3_left_3_right$"):
        validate_bremen_shape(ms)


def test_package_validation_accepts_valid_3plus3():
    validation = BremenRuntime(MODEL).validate_model_input(
        ModelInput(workflow_id="bremen", measurements=make_case().measurements),
    )
    assert validation.compatible is True


def test_package_scientific_failure_is_safe_constant(monkeypatch):
    # A raw exception from the science module maps, through the contract
    # predict path, to the fixed safe category with no source text leaking.
    from bremen.contracts.model_runtime import ModelPreprocessingFailedError

    monkeypatch.setattr(
        "bremen.model_packages.bremen_v01.runtime.build_bremen_features",
        Mock(side_effect=ValueError("/private/source secret token traceback")),
    )
    with pytest.raises(ModelPreprocessingFailedError) as exc:
        BremenRuntime(MODEL).predict_model(
            ModelInput(workflow_id="bremen", measurements=make_case().measurements),
        )
    assert exc.value.safe_reason == "invalid_scientific_profiles"
    assert "secret" not in str(exc.value)
    assert "/private" not in str(exc.value)


def test_package_raw_canonical_validation_fail_closed():
    ms = list(make_case().measurements)
    ms[0] = replace(ms[0], q=ms[0].q[::-1])
    with pytest.raises(BremenFeatureError, match="invalid_scientific_profiles"):
        BremenRuntime(MODEL).run(ms)


# ---------------------------------------------------------------------------
# All-six participation, permutation invariance, replicate variance, peaks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("index", range(6))
def test_package_all_six_participate(index):
    ms = list(make_case().measurements)
    m = ms[index]
    ms[index] = replace(m, intensity=m.intensity + 0.12 * np.exp(-((m.q - 14.1) / 0.8) ** 2))
    actual = build_bremen_features(ms)
    assert_close(list(actual.values()), DETAIL["mutations"][index]["expected_features"])
    changed = [n for n, a, b in zip(actual, actual.values(), GOLD["expected_features"])
               if abs(a - b) > 1e-10]
    assert changed == DETAIL["mutations"][index]["changed_features"]
    assert changed


@pytest.mark.parametrize("side_offset", [0, 3])
@pytest.mark.parametrize("order", list(permutations(range(3))))
def test_package_permutation_invariance(side_offset, order):
    case = make_case()
    ms = list(case.measurements)
    ms[side_offset:side_offset + 3] = [case.measurements[side_offset + i] for i in order]
    runtime = BremenRuntime(MODEL)
    assert_close(runtime.build_features(ms).feature_values, GOLD["expected_features"])
    assert_close(runtime.run(ms).probability, GOLD["expected_probability"])


@pytest.mark.parametrize("identical_sides", [("LEFT",), ("RIGHT",), ("LEFT", "RIGHT")])
def test_package_replicate_variance_ddof1(identical_sides):
    ms = list(make_case().measurements)
    for side in identical_sides:
        base = next(m for m in ms if m.side == side)
        ms = [replace(m, q=base.q.copy(), intensity=base.intensity.copy())
              if m.side == side else m for m in ms]
    actual = build_bremen_features(ms)
    assert_close(list(actual.values()), reference_vector(ms))
    for side in identical_sides:
        for band in (1, 2):
            assert_close(actual[f"sigma_{side[0].lower()}{band}"], 0)


def test_package_peak_semantics_are_original_maxima():
    # mean_peak_value_raw is computed on original per-profile maxima in
    # [13, 14.8] before aggregation: scaling every profile scales it.
    case = make_case()
    base = build_bremen_features(case.measurements)["mean_peak_value_raw"]
    scaled = build_bremen_features(
        tuple(replace(m, intensity=m.intensity * 2) for m in case.measurements)
    )["mean_peak_value_raw"]
    assert scaled == pytest.approx(base * 2, abs=1e-9)


def test_package_raw_peak_gate_preserved():
    ms = tuple(replace(m, intensity=m.intensity * 0.01) for m in make_case().measurements)
    with pytest.raises(BremenFeatureError, match="raw_peak_gate_failed"):
        build_bremen_features(ms)


# ---------------------------------------------------------------------------
# Portable estimator + threshold parity
# ---------------------------------------------------------------------------


def test_package_portable_estimator_and_threshold_parity():
    features = build_bremen_features(make_case().measurements)
    scored = predict_proba_portable(MODEL, list(features.values()))
    expected = reference_score(MODEL["portable_logreg"],
                               pd.DataFrame([list(features.values())]))[0]
    assert_close(scored["probability"], expected)
    assert scored["threshold_applied"] == MODEL["portable_logreg"]["threshold"]
    # threshold identity from PR0151 evidence
    assert scored["threshold_applied"] == pytest.approx(manifest.THRESHOLD_VALUE, abs=0)
    validate_portable_logreg_model(MODEL)  # no raise


def test_package_feature_columns_frozen_single_source():
    assert FEATURE_COLS == GOLD["feature_names"]
    assert BremenRuntime.feature_names == tuple(FEATURE_COLS)


# ---------------------------------------------------------------------------
# Import-direction guarantees
# ---------------------------------------------------------------------------


def _module_imports(rel: str) -> set[str]:
    tree = ast.parse((PKG / rel).read_text(encoding="utf-8"))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mods.add(("." * node.level) + (node.module or ""))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name)
    return mods


@pytest.mark.parametrize("rel", ["features.py", "predictor.py", "manifest.py"])
def test_package_science_has_no_platform_imports(rel):
    mods = _module_imports(rel)
    for module in mods:
        assert not module.startswith("bremen.api"), f"{rel} imports platform: {module}"
        assert "workflow" not in module
        assert "fastapi" not in module.lower()


def test_package_never_imports_workflow_or_service_layers():
    forbidden = (
        "workflow_bremen", "workflow_aramina", "report_bremen", "report_aramina",
        "report_provider", "job_api_handler", "jobs", "fastapi_app", "auth",
        "s3_model_discovery", "source_registry", "demo",
    )
    for rel in ("__init__.py", "manifest.py", "features.py", "predictor.py", "runtime.py"):
        mods = _module_imports(rel)
        for module in mods:
            for token in forbidden:
                assert token not in module, f"package/{rel} imports forbidden {token}"


def test_importing_package_entry_does_not_load_workflow():
    # Isolated subprocess: importing ONLY the package entry point must not
    # pull in platform workflow/report/job/FastAPI modules.
    import subprocess
    import sys

    code = (
        "import sys; import bremen.model_packages.bremen_v01; "
        "bad=[m for m in sys.modules if any(t in m for t in "
        "('workflow_bremen','workflow_aramina','fastapi_app','job_api_handler',"
        "'report_bremen','report_provider','source_registry'))]; "
        "print(','.join(bad)); sys.exit(1 if bad else 0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, f"package import pulled in platform modules: {result.stdout}"


def test_shims_reexport_authoritative_objects():
    # Exactly one active implementation; shims must be identity re-exports.
    import bremen.model_packages.bremen_v01.features as legacy_features
    import bremen.model_packages.bremen_v01.runtime as legacy_runtime
    import bremen.model_packages.bremen_v01.predictor as legacy_inference
    import bremen.model_packages.bremen_v01.features as pkg_features
    import bremen.model_packages.bremen_v01.predictor as pkg_predictor
    import bremen.model_packages.bremen_v01.runtime as pkg_runtime

    assert legacy_features.build_bremen_features is pkg_features.build_bremen_features
    assert legacy_features.FEATURE_COLS is pkg_features.FEATURE_COLS
    assert legacy_inference.predict_proba_portable is pkg_predictor.predict_proba_portable
    assert legacy_inference.adapt_model_package is pkg_predictor.adapt_model_package
    assert legacy_runtime.BremenRuntime is pkg_runtime.BremenRuntime
    assert legacy_runtime.BremenRuntimeError is pkg_runtime.BremenRuntimeError
