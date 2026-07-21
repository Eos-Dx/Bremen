"""Bremen workflow provider.

First complete provider implementation.  Owns Bremen feature schema,
model compatibility, threshold, decision rule, and result schema.

PR0075 — multi-workflow runtime foundation.
"""

from __future__ import annotations

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
from .xrd_normalization import CanonicalXRDCase

_log = _getLogger(__name__)

# Re-export for external callers
TRIAGE_RECOMMENDED = "MRI_RECOMMENDED"
TRIAGE_RULE_OUT = "MRI_RULE_OUT"


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
    """

    workflow_id: str = "bremen"

    def __init__(
        self,
        model_package: dict | None = None,
        *,
        model_checksum: str | None = None,
        model_version: str | None = None,
    ) -> None:
        self._model_package = model_package
        self._model_checksum = model_checksum
        self._model_version = model_version
        self._model_validated = False

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
        """Bremen requires at least one LEFT and one RIGHT measurement."""
        if not isinstance(canonical, CanonicalXRDCase):
            return CompatibilityResult(compatible=False, reason="not_a_canonical_case")

        sides = {m.side for m in canonical.measurements}
        if "LEFT" not in sides or "RIGHT" not in sides:
            return CompatibilityResult(
                compatible=False,
                reason="requires_both_sides",
            )

        if len(canonical.measurements) < 2:
            return CompatibilityResult(
                compatible=False,
                reason="insufficient_measurements",
            )

        return CompatibilityResult(compatible=True)

    # ---- Feature construction ----

    def build_features(self, canonical: Any) -> WorkflowFeatureVector:
        """Build Bremen 15-feature vector from canonical case.

        For P1/P2/P3: currently uses the first LEFT/RIGHT pair.
        Multi-position aggregation requires authoritative config.
        """
        if not isinstance(canonical, CanonicalXRDCase):
            raise WorkflowIncompatibleError("Input is not a CanonicalXRDCase")

        left_ms = [m for m in canonical.measurements if m.side == "LEFT"]
        right_ms = [m for m in canonical.measurements if m.side == "RIGHT"]

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
        triage = TRIAGE_RECOMMENDED if prob >= threshold else TRIAGE_RULE_OUT

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
                "triage_recommendation": triage,
            },
        )

    # ---- Execute ----

    def execute(self, canonical: Any) -> WorkflowResult:
        """Full execution: compatibility → features → inference."""
        compat = self.validate_compatibility(canonical)
        if not compat.compatible:
            return WorkflowResult(
                workflow_id=self.workflow_id,
                status="failed",
                error=f"Incompatible: {compat.reason}",
            )
        try:
            features = self.build_features(canonical)
        except Exception as exc:
            return WorkflowResult(
                workflow_id=self.workflow_id,
                status="failed",
                error=f"Feature construction failed: {exc}",
            )
        return self.run_inference(features)

    # ---- Internal ----

    def _validate_model_internal(self) -> bool:
        if self._model_package is None:
            return False

        plr = self._model_package.get("portable_logreg", {})
        for key in ("coef", "imputer_statistics", "scaler_mean",
                    "scaler_scale"):
            if key not in plr or not isinstance(plr[key], list) or len(plr[key]) != 15:
                return False
        if "intercept" not in plr or not isinstance(plr["intercept"], (int, float)):
            return False
        if "threshold" not in plr or not isinstance(plr["threshold"], (int, float)):
            return False

        self._model_validated = True
        return True
