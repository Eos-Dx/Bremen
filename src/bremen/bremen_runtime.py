"""Model-owned Bremen 3×3 scientific inference boundary (PR0152, PR0153B).

This is a concrete runtime for the PR0151 contract.  PR0153B connects it to the
Model Runtime Contract v1 semantic boundary without changing any scientific
behaviour: it still owns exact 3 LEFT + 3 RIGHT validation, preprocessing,
the frozen 15-feature contract, imputation/scaler arithmetic, portable logistic
regression inference and the model-owned threshold.  Workflow/API concerns stay
outside; the fitted artifact is never modified or fit.

Research decision support requiring radiologist review.
"""
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from bremen.api.decision_contract import BremenDecision, build_decision
from bremen.bremen_features import (
    FEATURE_COLS, BremenFeatureError, build_bremen_features, validate_bremen_shape,
)
from bremen.inference import (
    adapt_model_package, predict_proba_portable, validate_portable_logreg_model,
)
from bremen.model_runtime import (
    CONTRACT_VERSION,
    ModelConfigurationRequiredError,
    ModelInferenceFailedError,
    ModelInput,
    ModelInputInvalidError,
    ModelPreprocessingFailedError,
    ModelRequirements,
    ModelRuntimeError,
    ModelValidation,
    RuntimePrediction,
)

# Model release identity recorded in PR0151/PR0152 evidence.
# (``model_id`` lives in the training run manifest; the artifact's
# ``model_identity`` block carries name+version only — see PR0152 review.)
BREMEN_WORKFLOW_ID = "bremen"
BREMEN_FEATURE_SCHEMA_VERSION = "v0.1"
BREMEN_MODEL_ID = "bremen-paper-reference-v0-2-0"
BREMEN_MODEL_VERSION = "0.2.0-paper-reference"


def _runtime_error_for(exc: BaseException) -> ModelRuntimeError:
    """Map a safe Bremen failure reason onto a Model Runtime Contract category.

    ``safe_reason`` values stay byte-identical to PR0152 so platform adapters
    preserve their established external error envelopes unchanged.  An already
    category-classified ``ModelRuntimeError`` (a specific ownership category)
    propagates unchanged; the generic ``BremenRuntimeError`` base is mapped by
    its fixed reason string.
    """
    if (
        isinstance(exc, ModelRuntimeError)
        and type(exc) is not BremenRuntimeError
        and exc.category != ModelRuntimeError.category
    ):
        return exc
    reason = str(exc)
    if reason == "requires_exactly_3_left_3_right":
        return ModelInputInvalidError(reason)
    if reason == "invalid_feature_schema":
        return ModelInputInvalidError(reason)
    if reason in ("model_not_ready", "workflow_configuration_required"):
        return ModelConfigurationRequiredError(reason)
    if reason in ("raw_peak_gate_failed", "invalid_scientific_profiles"):
        return ModelPreprocessingFailedError(reason)
    if reason in ("model_execution_failed", "inference_failed"):
        return ModelInferenceFailedError(reason)
    return ModelPreprocessingFailedError("invalid_scientific_profiles")


@dataclass(frozen=True)
class BremenFeatures:
    feature_names: tuple[str, ...]
    feature_values: tuple[float, ...]


@dataclass(frozen=True)
class BremenModelResult:
    features: BremenFeatures
    probability: float
    prediction: int
    threshold: float
    decision: BremenDecision


class BremenRuntimeError(ModelRuntimeError):
    """A fixed, safe runtime failure; no source exception text is exposed.

    PR0153B: the class now also derives from the common
    ``ModelRuntimeError`` ownership base so existing ``except
    BremenRuntimeError`` boundaries keep working unchanged while the runtime
    participates in Model Runtime Contract v1.
    """


class BremenRuntime:
    """Own validation, preprocessing, feature construction, scoring and decision.

    Reference implementation of Model Runtime Contract v1
    (``bremen.model_runtime.ModelRuntime``): ``model_requirements``,
    ``validate_model_input`` and ``predict_model`` expose the three semantic
    responsibilities without adding a wrapper layer over the frozen PR0152
    scientific sequence.
    """

    feature_names = tuple(FEATURE_COLS)

    def __init__(self, package: dict | None = None):
        self.package = adapt_model_package(package) if package is not None else None

    @staticmethod
    def validate_input(measurements) -> None:
        validate_bremen_shape(measurements)

    def model_ready(self) -> bool:
        try:
            validate_portable_logreg_model(self.package)
        except Exception:
            # Package validators may reject a malformed artifact with their
            # dedicated exception; readiness never exposes that exception.
            return False
        return True

    def build_features(self, measurements) -> BremenFeatures:
        self.validate_input(measurements)
        values = build_bremen_features(measurements)
        return BremenFeatures(self.feature_names, tuple(values.values()))

    def score(self, names: Sequence[str], values: Sequence[float]) -> BremenModelResult:
        """Score an ordered vector, including authoritative imputation and scaling."""
        if tuple(names) != self.feature_names or len(values) != len(self.feature_names):
            raise BremenRuntimeError("invalid_feature_schema")
        if not self.model_ready():
            raise BremenRuntimeError("model_not_ready")
        try:
            scored = predict_proba_portable(self.package, list(values))
            decision = build_decision(scored['probability'], scored['threshold_applied'])
        except Exception:
            raise BremenRuntimeError("model_execution_failed") from None
        return BremenModelResult(
            features=BremenFeatures(tuple(names), tuple(values)),
            probability=scored['probability'], prediction=int(decision.is_positive),
            threshold=scored['threshold_applied'], decision=decision,
        )

    def run(
        self, measurements, *, on_features: Callable[[BremenFeatures], None] | None = None,
    ) -> BremenModelResult:
        """Execute the entire model contract once; optionally notify job tracing."""
        self.validate_input(measurements)
        if not self.model_ready():
            raise BremenRuntimeError("model_not_ready")
        features = self.build_features(measurements)
        if on_features is not None:
            on_features(features)
        return self.score(features.feature_names, features.feature_values)

    # ---- Model Runtime Contract v1 (PR0153B) -------------------------------
    # These members expose the frozen PR0152 scientific sequence through the
    # common semantic boundary.  No scientific behaviour is changed here.

    def model_requirements(self) -> ModelRequirements:
        """Describe the Bremen model-specific input contract."""
        return ModelRequirements(
            contract_version=CONTRACT_VERSION,
            workflow_id=BREMEN_WORKFLOW_ID,
            model_id=BREMEN_MODEL_ID,
            model_version=BREMEN_MODEL_VERSION,
            feature_schema_version=BREMEN_FEATURE_SCHEMA_VERSION,
            measurement_sides=(("LEFT", 3), ("RIGHT", 3)),
            total_measurements=6,
            requires_target_side=False,
            request_fields=("container_id", "source_id"),
            optional_request_fields=(),
            notes=(
                "Bremen requires exactly 3 LEFT and 3 RIGHT canonical "
                "measurements (six total) before any scientific work.",
            ),
        )

    def validate_model_input(self, input: ModelInput) -> ModelValidation:
        """Validate the exact 3+3 scientific input contract.

        Raises ``ModelInputInvalidError`` only when the carrier supplies no
        measurement collection at all; otherwise reports the shape verdict
        structurally via the frozen ``validate_bremen_shape`` (an empty or
        wrong-count set yields the established ``requires_exactly_3_left_3_right``
        reason).  This is the contract-facing form of ``validate_input``; the
        frozen validation implementation is unchanged.
        """
        measurements = input.measurements
        if measurements is None:
            raise ModelInputInvalidError("not_a_canonical_case")
        try:
            validate_bremen_shape(measurements)
        except BremenFeatureError as exc:
            return ModelValidation(compatible=False, safe_reason=str(exc))
        return ModelValidation(compatible=True)

    def predict_model(
        self,
        input: ModelInput,
        *,
        on_features: Callable[[BremenFeatures], None] | None = None,
    ) -> RuntimePrediction:
        """Run the complete frozen model contract and return a runtime result.

        The scientific sequence is exactly ``run()`` (validate → build features
        → score → decide).  Safe failures are translated into Model Runtime
        Contract error categories without changing their established
        ``safe_reason`` constants.
        """
        try:
            model_result = self.run(input.measurements, on_features=on_features)
        except (BremenFeatureError, ModelRuntimeError) as exc:
            raise _runtime_error_for(exc) from None
        except Exception:
            raise ModelPreprocessingFailedError("invalid_scientific_profiles") from None
        return RuntimePrediction(
            workflow_id=BREMEN_WORKFLOW_ID,
            model_id=str(self.model_metadata.get("model_id") or BREMEN_MODEL_ID),
            model_version=str(self.model_metadata.get("model_version") or ""),
            result=_bremen_result_mapping(model_result),
        )

    @property
    def model_metadata(self) -> Mapping[str, object]:
        """Safe, resolved model identity for runtime results (no artifact data)."""
        package = self.package if isinstance(self.package, dict) else {}
        plr = package.get("portable_logreg") if isinstance(package, dict) else None
        plr = plr if isinstance(plr, dict) else {}
        identity = package.get("model_identity") if isinstance(package, dict) else None
        identity = identity if isinstance(identity, dict) else {}
        version = (
            plr.get("model_version") or identity.get("version")
            or BREMEN_MODEL_VERSION
        )
        return {"model_id": BREMEN_MODEL_ID, "model_version": str(version)}


def _bremen_result_mapping(result: BremenModelResult) -> dict[str, object]:
    """Project the model-owned result into the contract result mapping.

    Carries only established, already-public inference fields; no new public
    semantics are introduced and no scientific internals are exposed.
    """
    decision = result.decision
    return {
        "probability": result.probability,
        "prediction": result.prediction,
        "threshold_applied": result.threshold,
        "decision_code": decision.decision_code,
        "decision_display_name": decision.decision_display_name,
        "decision_explanation": decision.decision_explanation,
        "decision_policy_id": decision.decision_policy_id,
        "decision_policy_version": decision.decision_policy_version,
        "triage_recommendation": decision.legacy_triage,
        "scientifically_certified": decision.scientifically_certified,
        "technical_demo_only": decision.technical_demo_only,
        "feature_names": result.features.feature_names,
        "feature_values": result.features.feature_values,
    }


# Explicit re-export for callers translating safe feature/input failures.
__all__ = ['BremenRuntime', 'BremenRuntimeError', 'BremenFeatureError',
           'BremenFeatures', 'BremenModelResult']
