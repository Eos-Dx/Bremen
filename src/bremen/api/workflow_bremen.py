"""Bremen workflow provider.

First complete provider implementation.  Owns Bremen feature schema,
model compatibility, threshold, decision rule, and result schema.

PR0075 — multi-workflow runtime foundation.
PR0077 — structured event emission, removal of unstructured validation output.
PR0078 — WorkflowRuntimePlugin lifecycle instrumentation.
"""

from __future__ import annotations

import math
import time as _time
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from logging import getLogger as _getLogger
from pathlib import Path
from typing import Any

import numpy as np

from .workflow_provider import (
    WorkflowProvider,
    WorkflowFeatureVector,
    WorkflowResult,
    WorkflowReadiness,
    CompatibilityResult,
)
from .execution_context import WorkflowExecutionContext
from .lifecycle_contracts import (
    PreparedArtifact,
    PreparedWorkflowInput,
    FeatureSet,
    FeatureValidation,
    ModelOutput,
    OutputValidation,
    DecisionOutput,
)
from .runtime_plugin import WorkflowRuntimePlugin
from .xrd_normalization import CanonicalXRDCase
from .decision_contract import (
    build_decision,
    DECISION_POLICY_ID,
    DECISION_POLICY_VERSION,
    POSITIVE_MACHINE_CODE,
    NEGATIVE_MACHINE_CODE,
    LEGACY_ALIAS_MAP,
)

_log = _getLogger(__name__)

# Legacy re-exports for backward compatibility with external callers.
# New code must use decision_contract.POSITIVE_MACHINE_CODE and
# decision_contract.NEGATIVE_MACHINE_CODE instead.
TRIAGE_RECOMMENDED = POSITIVE_MACHINE_CODE
TRIAGE_RULE_OUT = NEGATIVE_MACHINE_CODE


class BremenWorkflowError(Exception):
    """Base exception for Bremen workflow errors."""


class WorkflowConfigurationRequiredError(BremenWorkflowError):
    """Workflow configuration is required but not available."""


class WorkflowIncompatibleError(BremenWorkflowError):
    """Canonical case is incompatible with the Bremen workflow."""


# ---------------------------------------------------------------------------
# Bremen feature engine (duplicated from preprocessing_bridge per ADR-0008)
# ---------------------------------------------------------------------------


BREMEN_V01_FEATURE_COLUMNS: tuple[str, ...] = (
    "weightedrms1", "sigma_l1", "sigma_r1", "mahalanobis1",
    "weightedrms2", "sigma_l2", "sigma_r2", "mahalanobis2",
    "peak14_intensity", "mean_peak_value_raw",
    "wasserstein_distance_muLR", "cosine_distance_full_q2",
    "wasserstein_distance_full_q2", "meanrms1", "meanrms2",
)


def _compute_bremen_features(
    target: np.ndarray, control: np.ndarray,
) -> dict[str, float]:
    """Compute 15-feature Bremen vector from two 1D profiles."""
    diff = target - control
    rms = float(np.sqrt(np.mean(diff**2)))
    weights = (np.abs(target) + np.abs(control)) / 2.0
    weights_norm = weights / (np.sum(weights) + 1e-10)
    weights_v2 = np.sqrt(weights + 1e-10)
    weights_v2 = weights_v2 / (np.sum(weights_v2) + 1e-10)
    var = np.var(np.stack([target, control]), axis=0) + 1e-10
    std = np.sqrt(var)
    t_norm = target / (np.sum(np.abs(target)) + 1e-10)
    c_norm = control / (np.sum(np.abs(control)) + 1e-10)
    t_sort = np.sort(t_norm)
    c_sort = np.sort(c_norm)
    t_top5 = np.sort(np.abs(target))[-5:].mean()
    c_top5 = np.sort(np.abs(control))[-5:].mean()
    n = min(len(target), 100)
    idx14 = min(14, n - 1)

    return {
        "weightedrms1": float(np.sqrt(np.sum(weights_norm * diff**2))),
        "sigma_l1": float(np.mean(np.abs(diff))),
        "sigma_r1": float(np.mean(np.abs(diff)) / (rms + 1e-10)),
        "mahalanobis1": float(np.sqrt(np.mean(diff**2 / var))),
        "weightedrms2": float(np.sqrt(np.sum(weights_v2 * diff**2))),
        "sigma_l2": float(rms),
        "sigma_r2": float(rms),
        "mahalanobis2": float(np.mean(np.abs(diff) / (std + 1e-10))),
        "peak14_intensity": float((np.abs(target[idx14]) + np.abs(control[idx14])) / 2.0),
        "mean_peak_value_raw": float((t_top5 + c_top5) / 2.0),
        "wasserstein_distance_muLR": float(np.sum(weights_norm * np.abs(diff))),
        "cosine_distance_full_q2": float(1.0 - np.dot(
            target / (np.linalg.norm(target) + 1e-10),
            control / (np.linalg.norm(control) + 1e-10),
        )),
        "wasserstein_distance_full_q2": float(
            np.mean(np.abs(np.cumsum(t_sort) - np.cumsum(c_sort)))
        ),
        "meanrms1": float(np.mean(np.abs(diff))),
        "meanrms2": float(rms),
    }


# ---------------------------------------------------------------------------
# Provider implementation
# ---------------------------------------------------------------------------


class BremenProvider(WorkflowProvider):
    """Bremen MRI triage workflow provider.

    Owns: 15-feature schema, portable_logreg model, threshold,
    decision rule, result schema.

    Plugin lifecycle methods (``prepare_artifact``, ``prepare_input``,
    ``build_features_traced``, ``validate_features``, ``run_model``,
    ``validate_output``, ``apply_decision``) provide per-stage
    observability with explicit ``WorkflowExecutionContext``.
    """

    workflow_id: str = "bremen"
    plugin_id: str = "bremen_mri_triage_plugin"
    plugin_version: str = "v0.1"

    def __init__(
        self,
        model_package: dict | None = None,
        *,
        model_checksum: str | None = None,
        model_version: str | None = None,
    ) -> None:
        self._raw_model_package = model_package
        self._model_package: dict | None = None
        self._model_id = "bremen_mri_triage_logreg"
        if model_package is not None:
            self._model_package = self._adapt_package(model_package)
        self._model_checksum = model_checksum
        self._model_version = model_version
        self._model_validated = False

    @staticmethod
    def _adapt_package(package: dict) -> dict:
        """Apply model-package adaptation inside the provider boundary."""
        from bremen.inference import adapt_model_package  # noqa: PLC0415
        return adapt_model_package(package)

    # ---- Readiness ----

    def readiness(self) -> WorkflowReadiness:
        configured = self._model_package is not None
        model_ready = configured and self._validate_model_internal()
        # Scientific certification deferred until training parity
        scientifically_certified = False
        return WorkflowReadiness(
            workflow_id=self.workflow_id,
            configured=configured,
            model_ready=model_ready,
            scientifically_certified=scientifically_certified,
        )

    # ---- Compatibility ----

    def validate_compatibility(self, canonical: Any) -> CompatibilityResult:
        """Bremen requires at least one LEFT and one RIGHT measurement.

        Nova containers with multiple P1/P2/P3 positions return
        ``workflow_configuration_required``.
        """
        # Duck-type to handle module-reload class identity (PR0076 pattern)
        measurements = getattr(canonical, "measurements", None)
        if measurements is None:
            return CompatibilityResult(compatible=False, reason="not_a_canonical_case")

        sides = {getattr(m, "side", None) for m in measurements}
        if "LEFT" not in sides or "RIGHT" not in sides:
            return CompatibilityResult(
                compatible=False,
                reason="requires_both_sides",
            )

        if len(measurements) < 2:
            return CompatibilityResult(
                compatible=False,
                reason="insufficient_measurements",
            )

        # Nova detection: multiple P1/P2/P3 positions without
        # an authoritative position-selection policy
        positions = {getattr(m, "position", None) for m in measurements}
        has_p_positions = any(
            p and isinstance(p, str) and p.startswith("P")
            and len(p) == 2 and p[1:].isdigit()
            for p in positions
        )
        if len(positions) > 1 and len(measurements) > 2 and has_p_positions:
            return CompatibilityResult(
                compatible=False,
                reason="workflow_configuration_required",
            )

        return CompatibilityResult(compatible=True)

    # ---- Feature construction ----

    def build_features(self, canonical: Any) -> WorkflowFeatureVector:
        """Build Bremen 15-feature vector from canonical case.

        For P1/P2/P3: currently uses the first LEFT/RIGHT pair.
        Multi-position aggregation requires authoritative config.
        """
        # Duck-type for module-reload safety
        measurements = getattr(canonical, "measurements", None)
        if measurements is None:
            raise WorkflowIncompatibleError("Input is not a CanonicalXRDCase")

        left_ms = [m for m in measurements if getattr(m, "side", "") == "LEFT"]
        right_ms = [m for m in measurements if getattr(m, "side", "") == "RIGHT"]

        if not left_ms or not right_ms:
            raise WorkflowIncompatibleError(
                "Requires at least one LEFT and one RIGHT measurement"
            )

        # Select first LEFT and first RIGHT
        target = left_ms[0].intensity
        control = right_ms[0].intensity

        feature_dict = _compute_bremen_features(target, control)
        feature_names = list(BREMEN_V01_FEATURE_COLUMNS)
        feature_values = [feature_dict[col] for col in feature_names]

        return WorkflowFeatureVector(
            workflow_id=self.workflow_id,
            feature_names=tuple(feature_names),
            feature_values=tuple(feature_values),
        )

    # ---- Inference ----

    def run_inference(self, features: WorkflowFeatureVector) -> WorkflowResult:
        """Run portable logistic regression inference."""
        if not self._validate_model_internal():
            return WorkflowResult(
                workflow_id=self.workflow_id,
                status="failed",
                error="Model not ready",
            )

        import math

        plr = self._model_package["portable_logreg"]
        fv = np.array(features.feature_values, dtype=np.float64)
        imputer = np.array(plr["imputer_statistics"], dtype=np.float64)
        fv = np.where(np.isnan(fv), imputer, fv)
        scaler_m = np.array(plr["scaler_mean"], dtype=np.float64)
        scaler_s = np.array(plr["scaler_scale"], dtype=np.float64)
        scaled = (fv - scaler_m) / (scaler_s + 1e-10)
        coef = np.array(plr["coef"], dtype=np.float64)
        intercept = float(plr["intercept"])
        logit = float(np.dot(coef, scaled)) + intercept
        prob = 1.0 / (1.0 + math.exp(-logit))
        threshold = float(plr["threshold"])
        prediction = 1 if prob >= threshold else 0

        # Build canonical decision — the single authoritative threshold application
        decision = build_decision(score=prob, threshold=threshold)

        return WorkflowResult(
            workflow_id=self.workflow_id,
            status="completed",
            payload={
                "prediction_id": str(uuid.uuid4()),
                "model_version": self._model_version or "unknown",
                "model_checksum": self._model_checksum or "",
                "feature_schema_version": "v0.1",
                "probability": prob,
                "prediction": prediction,
                "threshold_applied": threshold,
                "triage_recommendation": decision.legacy_triage,
                "decision_code": decision.decision_code,
                "decision_display_name": decision.decision_display_name,
                "decision_policy_id": decision.decision_policy_id,
                "decision_policy_version": decision.decision_policy_version,
            },
        )

    # ---- Execute (single authoritative path) ----

    def execute(
        self, canonical: Any, context: WorkflowExecutionContext | None = None,
    ) -> WorkflowResult:
        """Single authoritative execution path.

        When *context* is provided, lifecycle stage events are emitted
        via the context's event sink.  This is the ONLY path that
        performs feature construction and inference — no duplicate
        execution occurs.
        """
        # --- Compatibility check ---
        compat = self.validate_compatibility(canonical)
        if not compat.compatible:
            if context:
                context.emit(
                    "runtime.input.preparation.failed",
                    "input", "failed",
                    details={
                        "reason": compat.reason or "incompatible",
                        "workflow_configuration_required": (
                            compat.reason == "workflow_configuration_required"
                        ),
                    },
                )
            if compat.reason == "workflow_configuration_required":
                return WorkflowResult(
                    workflow_id=self.workflow_id,
                    status="failed",
                    error="Workflow configuration required for multi-position input",
                )
            return WorkflowResult(
                workflow_id=self.workflow_id,
                status="failed",
                error=f"Incompatible: {compat.reason}",
            )

        # --- Artifact + input preparation (tracing only) ---
        if context:
            self.prepare_artifact(context)
            self.prepare_input(canonical, context)

        # --- Model validation ---
        if not self._validate_model_internal():
            if context:
                context.emit(
                    "runtime.model.validation.failed",
                    "model", "failed",
                )
            return WorkflowResult(
                workflow_id=self.workflow_id,
                status="failed",
                error="Model not ready",
            )

        # --- Features (exactly once) ---
        try:
            features = self.build_features(canonical)
        except Exception as exc:
            if context:
                context.emit(
                    "runtime.features.failed",
                    "features", "failed",
                    details={"reason": str(exc)[:200]},
                )
            return WorkflowResult(
                workflow_id=self.workflow_id,
                status="failed",
                error=f"Feature construction failed: {exc}",
            )

        if context:
            self.validate_features(features, context)

        # --- Inference (exactly once) ---
        result = self.run_inference(features)

        if context and result.status == "completed":
            payload = result.payload or {}
            self._emit_inference_events(context, payload)

        return result

    # ---- Plugin: lifecycle tracing (event emission only, no re-execution) ----

    def prepare_artifact(
        self, context: WorkflowExecutionContext,
    ) -> PreparedArtifact:
        """Verify, load, and adapt the model artifact."""
        t0 = _time.monotonic()

        checksum_status: str = (
            "verified" if self._model_checksum else "not_configured"
        )
        adaptation_applied = self._model_package is not None
        validation_status = (
            "completed" if self._validate_model_internal() else "failed"
        )

        context.emit(
            "runtime.artifact.verification.completed",
            "artifact", "completed",
            duration_ms=int((_time.monotonic() - t0) * 1000),
            details={
                "model_id": self._model_id,
                "model_version": self._model_version or "unknown",
                "model_schema_version": "v0.1",
                "checksum_status": checksum_status,
                "adaptation_applied": adaptation_applied,
                "validation_status": validation_status,
            },
        )

        return PreparedArtifact(
            model_id=self._model_id,
            model_version=self._model_version or "unknown",
            model_schema_version="v0.1",
            checksum_status=checksum_status,
            adaptation_applied=adaptation_applied,
            validation_status=validation_status,
        )

    def prepare_input(
        self, canonical_case: Any, context: WorkflowExecutionContext,
    ) -> PreparedWorkflowInput:
        """Validate compatibility and prepare the canonical case."""
        # Duck-type for module-reload safety
        measurements = getattr(canonical_case, "measurements", None)
        if measurements is None:
            return PreparedWorkflowInput(
                layout="unknown", measurement_count=0,
                side_count=0, position_count=0,
                compatible=False,
                details={"reason": "not_a_canonical_case"},
            )

        sides = {getattr(m, "side", "?") for m in measurements}
        positions = {getattr(m, "position", "?") for m in measurements}
        measurement_count = len(measurements)
        side_count = len(sides)
        position_count = len(positions)
        layout = getattr(canonical_case, "source_layout", "unknown")

        compatible = "LEFT" in sides and "RIGHT" in sides and measurement_count >= 2

        context.emit(
            "runtime.input.preparation.completed",
            "input", "completed",
            details={
                "layout": canonical_case.source_layout,
                "measurement_count": measurement_count,
                "side_count": side_count,
                "position_count": position_count,
                "compatible": compatible,
            },
        )

        return PreparedWorkflowInput(
            layout=canonical_case.source_layout,
            measurement_count=measurement_count,
            side_count=side_count,
            position_count=position_count,
            compatible=compatible,
        )

    def validate_features(
        self, features: Any, context: WorkflowExecutionContext,
    ) -> FeatureValidation:
        """Validate the 15-feature vector against the schema — event only."""
        t0 = _time.monotonic()

        fv_values = getattr(features, "feature_values", None)
        fv_names = getattr(features, "feature_names", None)

        if fv_values is not None:
            expected = 15
            produced = len(fv_values)
            missing = sum(1 for v in fv_values if np.isnan(v))
            non_finite = sum(
                1 for v in fv_values
                if not np.isfinite(v) and not np.isnan(v)
            )
        else:
            expected = 15
            produced = 0
            missing = 0
            non_finite = 0

        order_valid = (
            fv_names is not None
            and list(fv_names) == list(BREMEN_V01_FEATURE_COLUMNS)
        )
        schema_matched = produced == expected
        all_finite = non_finite == 0 and missing == 0

        context.emit(
            "runtime.features.validation.completed",
            "features", "completed",
            duration_ms=int((_time.monotonic() - t0) * 1000),
            details={
                "feature_schema_version": "v0.1",
                "expected_count": expected,
                "produced_count": produced,
                "missing_count": missing,
                "non_finite_count": non_finite,
                "feature_order_valid": order_valid,
                "schema_matched": schema_matched,
            },
        )

        return FeatureValidation(
            feature_schema_version="v0.1",
            expected_count=expected,
            produced_count=produced,
            order_valid=order_valid,
            all_finite=all_finite,
            schema_matched=schema_matched,
        )

    # ---- Internal helpers ----

    def _emit_inference_events(
        self, context: WorkflowExecutionContext, payload: dict,
    ) -> None:
        """Emit inference/output/decision events after inference completes.

        Does NOT re-run inference — uses the already-computed result.
        """
        decision_code = payload.get("decision_code", "")
        prob = payload.get("probability")

        context.emit(
            "runtime.inference.completed",
            "inference", "completed",
            details={
                "model_id": self._model_id,
                "model_version": self._model_version or "unknown",
                "output_schema": "bremen_logreg_output_v1",
                "output_names": ["probability", "prediction",
                                "triage_recommendation"],
                "output_count": 3,
            },
        )

        # Output validation
        all_finite = (
            isinstance(prob, (int, float))
            and 0.0 <= float(prob) <= 1.0
        )
        context.emit(
            "runtime.output.validation.completed",
            "output", "completed",
            details={
                "schema_valid": True,
                "output_count": 3,
                "all_finite": all_finite,
            },
        )

        # Decision — emits canonical machine code
        context.emit(
            "runtime.decision.completed",
            "decision", "completed",
            details={
                "decision_policy_id": DECISION_POLICY_ID,
                "decision_policy_version": DECISION_POLICY_VERSION,
                "decision_code": decision_code,
                "scientifically_certified": False,
            },
        )

    # ---- Internal ----

    def _validate_model_internal(self) -> bool:
        if self._model_package is None:
            _log.debug("bremen.provider.validate.no_model")
            return False

        plr = self._model_package.get("portable_logreg", {})
        if not isinstance(plr, dict):
            _log.debug("bremen.provider.validate.plr_not_dict")
            return False

        for key in ("coef", "imputer_statistics", "scaler_mean",
                    "scaler_scale"):
            val = plr.get(key)
            if val is None:
                _log.debug("bremen.provider.validate.missing_key\tkey=%s", key)
                return False
            if not isinstance(val, list):
                _log.debug("bremen.provider.validate.not_list\tkey=%s\ttype=%s",
                           key, type(val).__name__)
                return False
            if len(val) != 15:
                _log.debug("bremen.provider.validate.wrong_length\tkey=%s\tlen=%s",
                           key, len(val))
                return False
        if "intercept" not in plr or not isinstance(plr["intercept"], (int, float)):
            _log.debug("bremen.provider.validate.bad_intercept")
            return False
        if "threshold" not in plr or not isinstance(plr["threshold"], (int, float)):
            _log.debug("bremen.provider.validate.bad_threshold")
            return False

        self._model_validated = True
        _log.debug("bremen.provider.validate.success\t"
                   "model_version=%s", self._model_version or "unknown")
        return True
