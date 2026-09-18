"""Bremen v0.1 runtime entry point — Model Runtime Contract v1 (PR0154).

This is the authoritative, inference-complete Bremen scientific runtime,
moved here by PR0154 behind the model-package boundary.  PR0153B connected
the PR0152 runtime to Model Runtime Contract v1 without scientific change;
PR0154 relocates the same implementation so the platform depends on the
package instead of owning Bremen scientific files.

The runtime owns, unchanged from PR0151/PR0152:

- exact 3 LEFT + 3 RIGHT validation,
- per-profile ROI / Savitzky-Golay smoothing / p05 normalization,
- common-grid interpolation, per-side means and sample std (ddof=1),
- the frozen 15-feature contract and raw-peak gate,
- imputation and scaler arithmetic,
- portable logistic-regression inference and the model-owned threshold,
- safe model diagnostics and release provenance.

Boundary notes:

- ``features`` and ``predictor`` (package science) import only
  numpy/pandas/scipy/stdlib; this runtime is the single model-owned bridge to
  platform modules and nothing else: ``api.decision_contract`` (the
  platform decision-vocabulary authority shared with events/reports) and
  ``canonical_input.validate_canonical_measurement`` (the PR0152 lazy import
  lifted out of the science module in PR0154 and neutralized to
  ``bremen.contracts.canonical_input`` in PR0156 so canonical input validation is a
  generic cross-model contract, not an ``api`` import).  The numerical
  threshold comparison stays inside the package predictor.
- The fitted artifact is never modified or fit.  Research decision support
  requiring radiologist review.
"""
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from bremen.model_packages.bremen_v01.decision import BremenDecision, build_decision
from bremen.contracts.canonical_input import validate_canonical_measurement
from . import manifest
from .features import (
    FEATURE_COLS, BremenFeatureError, build_bremen_features, validate_bremen_shape,
)
from bremen.model_packages.bremen_v01.predictor import (
    adapt_model_package, predict_proba_portable, validate_portable_logreg_model,
)
from bremen.contracts.model_runtime import (
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


def _runtime_error_for(exc: BaseException) -> ModelRuntimeError:
    """Map a safe Bremen failure reason onto a Model Runtime Contract category.

    ``safe_reason`` values stay byte-identical to PR0152/PR0153B so platform
    adapters preserve their established external error envelopes unchanged.  An
    already category-classified ``ModelRuntimeError`` (a specific ownership
    category) propagates unchanged; the generic ``BremenRuntimeError`` base is
    mapped by its fixed reason string.
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

    Derives from the common ``ModelRuntimeError`` ownership base (PR0153B) so
    existing ``except BremenRuntimeError`` boundaries keep working unchanged.
    """


class BremenRuntime:
    """Authoritative Bremen v0.1 runtime implementing Model Runtime Contract v1.

    Reference implementation of ``bremen.contracts.model_runtime.ModelRuntime``:
    ``model_requirements``, ``validate_model_input`` and ``predict_model``
    expose the three semantic responsibilities without a wrapper layer over
    the frozen PR0152 scientific sequence.  The package release manifest is
    the single identity/requirements source.
    """

    feature_names = tuple(FEATURE_COLS)

    def __init__(self, package: dict | None = None):
        self.package = adapt_model_package(package) if package is not None else None

    # ---- Structural input checks (model-owned contract) ----

    @staticmethod
    def validate_input(measurements) -> None:
        """Enforce the exact 3+3 product shape contract (frozen)."""
        validate_bremen_shape(measurements)

    @staticmethod
    def validate_measurements(measurements) -> None:
        """Validate measurement structure through the canonical validator.

        PR0154 lifted this check out of the pure science module
        (``features.build_bremen_features``) to the runtime boundary.  The
        established safe reason mapping is preserved: a structural violation
        becomes the fixed constant ``invalid_scientific_profiles``.
        """
        try:
            for measurement in measurements:
                validate_canonical_measurement(measurement)
        except Exception:
            raise BremenFeatureError("invalid_scientific_profiles") from None

    def model_ready(self) -> bool:
        try:
            validate_portable_logreg_model(self.package)
        except Exception:
            # Package validators may reject a malformed artifact with their
            # dedicated exception; readiness never exposes that exception.
            return False
        return True

    # ---- Feature construction (frozen PR0152 sequence) ----

    def build_features(self, measurements) -> BremenFeatures:
        self.validate_input(measurements)
        self.validate_measurements(measurements)
        values = build_bremen_features(measurements)
        return BremenFeatures(self.feature_names, tuple(values.values()))

    # ---- Scoring (frozen PR0152 portable inference) ----

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

    # ---- Model Runtime Contract v1 members -------------------------------
    # These members expose the frozen PR0152 scientific sequence through the
    # common semantic boundary.  No scientific behaviour is changed here.

    def model_requirements(self) -> ModelRequirements:
        """Describe the Bremen model-specific input contract (manifest-owned)."""
        return ModelRequirements(
            contract_version=CONTRACT_VERSION,
            workflow_id=manifest.WORKFLOW_ID,
            model_id=manifest.MODEL_ID,
            model_version=manifest.MODEL_VERSION,
            feature_schema_version=manifest.FEATURE_SCHEMA_VERSION,
            measurement_sides=manifest.MEASUREMENT_SIDES,
            total_measurements=manifest.TOTAL_MEASUREMENTS,
            requires_target_side=manifest.REQUIRES_TARGET_SIDE,
            request_fields=manifest.REQUEST_FIELDS,
            optional_request_fields=manifest.OPTIONAL_REQUEST_FIELDS,
            notes=manifest.INPUT_NOTES,
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
        if self.requires_raw_container:
            return ModelValidation(
                compatible=bool(input.container_path),
                safe_reason="" if input.container_path else "raw_container_required",
            )
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

        PR0160: when the carrier provides the raw staged container
        (``container_path``), the scientific sequence is package-owned:
        validate -> artifact-owned preprocessing (from the active artifact's
        ``prediction_preprocessing_yaml``) -> frozen feature construction ->
        gate -> score -> decide. Artifacts requiring raw input cannot fall
        back to integrated profiles. Legacy artifacts without raw preprocessing
        retain the frozen ``run()`` integrated-profile sequence.  Safe failures are translated into Model Runtime Contract
        error categories without changing their established ``safe_reason``
        constants.
        """
        try:
            if self.requires_raw_container:
                if not input.container_path:
                    raise ModelInputInvalidError("raw_container_required")
                model_result = self._predict_from_raw_container(
                    input, on_features=on_features,
                )
            else:
                # No raw-container science configured: use the legacy frozen
                # integrated-profile sequence (synthetic fixture boundary and
                # package-level direct tests).  The synthetic MODEL fixture has
                # no prediction_preprocessing_yaml.
                model_result = self.run(input.measurements, on_features=on_features)
        except (BremenFeatureError, ModelRuntimeError) as exc:
            raise _runtime_error_for(exc) from None
        except Exception:
            raise ModelPreprocessingFailedError("invalid_scientific_profiles") from None
        metadata = self.model_metadata
        # PR0159: the model package owns the interpretation of its own
        # container/artifact metadata.  The normalized contract (source
        # metadata, model metadata, model metrics) is transported verbatim in
        # the runtime result so the platform mapper never parses model-specific
        # internals.  Absent fields keep the contract's explicit absence.
        from . import source_metadata as _source_metadata  # noqa: PLC0415

        result = _bremen_result_mapping(model_result)
        if self.requires_raw_container:
            # Prediction can succeed only after the package's exact shape gate.
            counts = dict(manifest.MEASUREMENT_SIDES)
            result.update(left_measurement_count=counts["LEFT"],
                          right_measurement_count=counts["RIGHT"])
        return RuntimePrediction(
            workflow_id=manifest.WORKFLOW_ID,
            model_id=str(metadata.get("model_id") or manifest.MODEL_ID),
            model_version=str(metadata.get("model_version") or ""),
            result=result,
            source_metadata=_source_metadata.extract_source_metadata(input.container_path),
            model_metadata=_source_metadata.extract_model_metadata(self.package),
            model_metrics=_source_metadata.extract_model_metrics(self.package),
        )

    @property
    def requires_raw_container(self) -> bool:
        """Artifacts declaring raw preprocessing must never fall back to profiles."""
        return (self._has_artifact_preprocessing() or
                isinstance(self.package, dict) and
                self.package.get("kind") == "bremen_paper_reference_model")

    def _has_artifact_preprocessing(self) -> bool:
        """True when the active artifact declares package-owned preprocessing.

        The synthetic/frozen integrated-profile fixture (MODEL) has no
        ``prediction_preprocessing_yaml``; the real paper-reference artifact
        does.  The raw-container path is only used when the artifact itself
        owns the preprocessing configuration.
        """
        package = self.package if isinstance(self.package, dict) else {}
        config_yaml = package.get("prediction_preprocessing_yaml")
        return isinstance(config_yaml, str) and bool(config_yaml.strip())

    def _predict_from_raw_container(
        self,
        input: ModelInput,
        *,
        on_features: Callable[[BremenFeatures], None] | None = None,
    ) -> BremenModelResult:
        """Execute the package-owned raw-container scientific sequence.

        The artifact's ``prediction_preprocessing_yaml`` is the authoritative
        preprocessing configuration; the pinned xrd-preprocessing worker
        (``preprocess_bremen``) produces the measurement frame; the frozen
        feature/gate/estimator sequence is then identical to ``run()``.  The
        platform never reconstructs Bremen scientific preprocessing.
        """
        if not self.model_ready():
            raise BremenRuntimeError("model_not_ready")
        package = self.package if isinstance(self.package, dict) else {}
        config_yaml = package.get("prediction_preprocessing_yaml")
        if not isinstance(config_yaml, str) or not config_yaml.strip():
            raise BremenRuntimeError("model_not_ready")
        from .preprocessing import preprocess_bremen  # noqa: PLC0415
        from .features import build_bremen_features_from_frame  # noqa: PLC0415

        frame = preprocess_bremen(input.container_path, config_yaml)
        values = build_bremen_features_from_frame(frame)
        features = BremenFeatures(
            self.feature_names,
            tuple(values[name] for name in self.feature_names),
        )
        if on_features is not None:
            on_features(features)
        return self.score(features.feature_names, features.feature_values)

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
            or manifest.MODEL_VERSION
        )
        return {"model_id": manifest.MODEL_ID, "model_version": str(version)}


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


__all__ = [
    "BremenRuntime",
    "BremenRuntimeError",
    "BremenFeatureError",
    "BremenFeatures",
    "BremenModelResult",
]
