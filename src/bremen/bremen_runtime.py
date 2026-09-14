"""Model-owned Bremen 3×3 scientific inference boundary (PR0152).

This is a concrete runtime for the PR0151 contract, not a generic runtime framework.
Workflow/API concerns stay outside; the fitted artifact is never modified or fit.
"""
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from bremen.api.decision_contract import BremenDecision, build_decision
from bremen.bremen_features import (
    FEATURE_COLS, BremenFeatureError, build_bremen_features, validate_bremen_shape,
)
from bremen.inference import (
    adapt_model_package, predict_proba_portable, validate_portable_logreg_model,
)


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


class BremenRuntimeError(ValueError):
    """A fixed, safe runtime failure; no source exception text is exposed."""


class BremenRuntime:
    """Own validation, preprocessing, feature construction, scoring and decision."""

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


# Explicit re-export for callers translating safe feature/input failures.
__all__ = ['BremenRuntime', 'BremenRuntimeError', 'BremenFeatureError',
           'BremenFeatures', 'BremenModelResult']
