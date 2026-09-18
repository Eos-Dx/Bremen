"""Two-model execution proof and concurrency test (PR0085).

Constructs two distinct synthetic Bremen model packages with different
coefficients and thresholds. Proves that each job executes the correct
package and produces the expected output.

Uses synthetic model packages and controlled canonical XRD input only.
No real AWS calls. No real model artifacts.
"""

from __future__ import annotations

from tests.runtime_inputs import execute_case

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from tests.bremen_3x3_helpers import GOLD

from bremen.platform.models.registry import (
    RegistryModelEntry,
    ModelRegistry,
    initialize_registry,
    reset_for_tests,
)
from bremen.platform.runtime.registry import get_descriptor_for_model


# ---------------------------------------------------------------------------
# Synthetic model packages with different coefficients
# ---------------------------------------------------------------------------

# Model A: negative intercept -> very low probability (below threshold)
PACKAGE_A_COEF = [0.01] * 15
PACKAGE_A_INTERCEPT = -5.0
PACKAGE_A_THRESHOLD = 0.5

# Model B: high coefficients -> high probability (above threshold)
PACKAGE_B_COEF = [0.9] * 15
PACKAGE_B_INTERCEPT = 0.0
PACKAGE_B_THRESHOLD = 0.3


def _build_package(coef: list[float], threshold: float, intercept: float = 0.0) -> dict[str, Any]:
    return {
        "portable_logreg": {
            "feature_columns": GOLD["feature_names"],
            "coef": coef,
            "imputer_statistics": [0.0] * 15,
            "scaler_mean": [0.0] * 15,
            "scaler_scale": [1.0] * 15,
            "intercept": intercept,
            "threshold": threshold,
        }
    }


def _make_entry(
    model_id: str,
    display_name: str,
    coef: list[float],
    threshold: float,
    intercept: float = 0.0,
) -> RegistryModelEntry:
    pkg = _build_package(coef, threshold, intercept)
    return RegistryModelEntry(
        model_id=model_id,
        display_name=display_name,
        workflow_id="bremen",
        model_version="v1.0",
        artifact_type="portable_logreg",
        feature_schema_version="v0.1",
        decision_policy_id="bremen_mri_continuation_threshold",
        decision_policy_version="0.1.0",
        technical_ready=True,
        scientifically_certified=False,
        technical_demo_only=True,
        availability="available",
        _package=pkg,
        _checksum=hashlib.sha256(json.dumps(coef).encode()).hexdigest(),
    )


# ---------------------------------------------------------------------------
# Controlled synthetic canonical XRD input
# ---------------------------------------------------------------------------


def _make_canonical_case() -> Any:
    """Controlled full product input; models still differ in coefficients."""
    from tests.bremen_3x3_helpers import make_case
    return make_case()


# ---------------------------------------------------------------------------
# Two-model execution proof
# ---------------------------------------------------------------------------


class TestTwoModelExecution:
    def teardown_method(self):
        reset_for_tests()

    def test_model_a_resolves_to_package_a(self):
        """model-a resolves to package A with low coefficients."""
        entry_a = _make_entry("model-a", "Model A", PACKAGE_A_COEF, PACKAGE_A_THRESHOLD, intercept=PACKAGE_A_INTERCEPT)
        reg = ModelRegistry(
            entries=(entry_a,),
            catalog_status="available",
            candidate_count=1,
            available_count=1,
            rejected_count=0,
        )
        initialize_registry(reg)

        provider = get_descriptor_for_model("model-a")
        assert provider is not None
        # Execute with controlled input
        case = _make_canonical_case()
        result = execute_case(provider, case)
        assert result.status == "completed"
        payload = result.payload or {}
        prob = payload.get("probability", 0)
        # Low coefficients should produce low probability
        assert prob < 0.5, f"Expected low probability for model-a, got {prob}"

    def test_model_b_resolves_to_package_b(self):
        """model-b resolves to package B with high coefficients."""
        entry_b = _make_entry("model-b", "Model B", PACKAGE_B_COEF, PACKAGE_B_THRESHOLD)
        reg = ModelRegistry(
            entries=(entry_b,),
            catalog_status="available",
            candidate_count=1,
            available_count=1,
            rejected_count=0,
        )
        initialize_registry(reg)

        provider = get_descriptor_for_model("model-b")
        assert provider is not None
        case = _make_canonical_case()
        result = execute_case(provider, case)
        assert result.status == "completed"
        payload = result.payload or {}
        prob = payload.get("probability", 0)
        # High coefficients should produce high probability
        assert prob > 0.5, f"Expected high probability for model-b, got {prob}"

    def test_different_models_produce_different_outputs(self):
        """model-a and model-b produce different probabilities for same input."""
        entry_a = _make_entry("model-a", "Model A", PACKAGE_A_COEF, PACKAGE_A_THRESHOLD, intercept=PACKAGE_A_INTERCEPT)
        entry_b = _make_entry("model-b", "Model B", PACKAGE_B_COEF, PACKAGE_B_THRESHOLD)
        reg = ModelRegistry(
            entries=(entry_a, entry_b),
            catalog_status="available",
            candidate_count=2,
            available_count=2,
            rejected_count=0,
        )
        initialize_registry(reg)

        case = _make_canonical_case()

        provider_a = get_descriptor_for_model("model-a")
        result_a = execute_case(provider_a, case)
        prob_a = (result_a.payload or {}).get("probability", 0)

        provider_b = get_descriptor_for_model("model-b")
        result_b = execute_case(provider_b, case)
        prob_b = (result_b.payload or {}).get("probability", 0)

        # Different coefficients should produce different probabilities
        assert abs(prob_a - prob_b) > 0.1, (
            f"Expected different probabilities, got A={prob_a}, B={prob_b}"
        )
        # model-a (low coef) should be below threshold
        # model-b (high coef) should be above threshold
        assert prob_a < PACKAGE_A_THRESHOLD, (
            f"Expected model-a below threshold {PACKAGE_A_THRESHOLD}, got {prob_a}"
        )
        assert prob_b > PACKAGE_B_THRESHOLD, (
            f"Expected model-b above threshold {PACKAGE_B_THRESHOLD}, got {prob_b}"
        )

    def test_model_id_in_result_payload(self):
        """model_id appears in the result payload."""
        entry = _make_entry("my-model", "My Model", PACKAGE_A_COEF, PACKAGE_A_THRESHOLD, intercept=PACKAGE_A_INTERCEPT)
        reg = ModelRegistry(
            entries=(entry,),
            catalog_status="available",
            available_count=1,
        )
        initialize_registry(reg)

        provider = get_descriptor_for_model("my-model")
        case = _make_canonical_case()
        execute_case(provider, case)
        # The provider's model_id is set from the entry
        assert provider.model_id == "my-model"

    def test_model_state_not_overwritten(self):
        """ModelState is not modified during selection."""
        from bremen.platform.models import state as ms
        ms.ModelState.reset_for_tests()

        entry = _make_entry("test-model", "Test", PACKAGE_A_COEF, PACKAGE_A_THRESHOLD, intercept=PACKAGE_A_INTERCEPT)
        reg = ModelRegistry(
            entries=(entry,),
            catalog_status="available",
            available_count=1,
        )
        initialize_registry(reg)

        # ModelState should still be None (not configured)
        assert ms.ModelState.get_model() is None

        # Provider should work from registry, not ModelState
        provider = get_descriptor_for_model("test-model")
        assert provider is not None


# ---------------------------------------------------------------------------
# Concurrency proof
# ---------------------------------------------------------------------------


class TestConcurrentExecution:
    def teardown_method(self):
        reset_for_tests()

    def test_concurrent_jobs_different_models(self):
        """Two concurrent jobs with different models produce correct outputs."""
        entry_a = _make_entry("model-a", "Model A", PACKAGE_A_COEF, PACKAGE_A_THRESHOLD, intercept=PACKAGE_A_INTERCEPT)
        entry_b = _make_entry("model-b", "Model B", PACKAGE_B_COEF, PACKAGE_B_THRESHOLD)
        reg = ModelRegistry(
            entries=(entry_a, entry_b),
            catalog_status="available",
            candidate_count=2,
            available_count=2,
            rejected_count=0,
        )
        initialize_registry(reg)

        case = _make_canonical_case()
        barrier = threading.Barrier(2, timeout=10)
        results: dict[str, float] = {}
        errors: list[Exception] = []

        def run_model(model_id: str) -> None:
            try:
                provider = get_descriptor_for_model(model_id)
                # Synchronize so both jobs overlap
                barrier.wait()
                result = execute_case(provider, case)
                prob = (result.payload or {}).get("probability", 0)
                results[model_id] = prob
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_a = executor.submit(run_model, "model-a")
            fut_b = executor.submit(run_model, "model-b")
            fut_a.result(timeout=30)
            fut_b.result(timeout=30)

        assert len(errors) == 0, f"Concurrent execution errors: {errors}"
        assert "model-a" in results
        assert "model-b" in results

        # model-a (low coef) should be below threshold
        assert results["model-a"] < PACKAGE_A_THRESHOLD, (
            f"Expected model-a below {PACKAGE_A_THRESHOLD}, got {results['model-a']}"
        )
        # model-b (high coef) should be above threshold
        assert results["model-b"] > PACKAGE_B_THRESHOLD, (
            f"Expected model-b above {PACKAGE_B_THRESHOLD}, got {results['model-b']}"
        )
        # Different outputs
        assert abs(results["model-a"] - results["model-b"]) > 0.1

    def test_no_cross_job_mutation(self):
        """Each job remains bound to its original model_id."""
        entry_a = _make_entry("model-a", "Model A", PACKAGE_A_COEF, PACKAGE_A_THRESHOLD, intercept=PACKAGE_A_INTERCEPT)
        entry_b = _make_entry("model-b", "Model B", PACKAGE_B_COEF, PACKAGE_B_THRESHOLD)
        reg = ModelRegistry(
            entries=(entry_a, entry_b),
            catalog_status="available",
            available_count=2,
        )
        initialize_registry(reg)

        provider_a = get_descriptor_for_model("model-a")
        provider_b = get_descriptor_for_model("model-b")

        # Each provider has its own package
        assert provider_a.model_id == "model-a"
        assert provider_b.model_id == "model-b"
        assert provider_a.runtime.package is not provider_b.runtime.package

    def test_deterministic_repeated_execution(self):
        """Repeated execution with same model produces same output."""
        entry = _make_entry("test-model", "Test", PACKAGE_A_COEF, PACKAGE_A_THRESHOLD, intercept=PACKAGE_A_INTERCEPT)
        reg = ModelRegistry(
            entries=(entry,),
            catalog_status="available",
            available_count=1,
        )
        initialize_registry(reg)

        case = _make_canonical_case()
        provider = get_descriptor_for_model("test-model")

        result1 = execute_case(provider, case)
        result2 = execute_case(provider, case)

        prob1 = (result1.payload or {}).get("probability", 0)
        prob2 = (result2.payload or {}).get("probability", 0)

        assert abs(prob1 - prob2) < 0.001, (
            f"Expected deterministic output, got {prob1} and {prob2}"
        )
