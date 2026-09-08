"""In-process execution of a selected, checksum-verified Aramina artifact.

The supported local package contract is explicit: ``model_id``,
``model_version``, ``feature_schema_version``, ``artifact_type``, ``model`` (predict_proba/classes_),
``positive_class``, and ``feature_contract``. The latter declares
``schema_version=aramina.canonical_intensity.v1``, ``position``, ``q_grid``,
and ``normalization=none``. This contract consumes one canonical spectrum
on the requested side, at exactly the declared q coordinates. No implicit
resampling, aggregation, label mapping, or clinical threshold is applied.
Other feature contracts fail with ARAMINA_UNSUPPORTED_ARTIFACT. This is a
supported runtime contract, not a claim that an uninspected real artifact
conforms to it. Preprocessing remains artifact-specific.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .aramina_provider import AraminaProviderRequest
from .model_registry import RegistryModelEntry
from .workflow_provider import (
    CompatibilityResult,
    WorkflowFeatureVector,
    WorkflowProvider,
    WorkflowReadiness,
    WorkflowResult,
)
from .xrd_normalization import CanonicalXRDCase, validate_canonical_case

ARTIFACT_TYPE = "aramina.joblib.model_package"
_FEATURE_CONTRACT = "aramina.canonical_intensity.v1"
_DEFAULT_AUTHOR = "Bremen Platform"
_SAFE_FAILURES = frozenset({
    "ARAMINA_INVALID_REQUEST", "ARAMINA_UNSUPPORTED_ARTIFACT",
    "ARAMINA_ARTIFACT_INTEGRITY_FAILED", "ARAMINA_UNSUPPORTED_INPUT",
    "ARAMINA_EXECUTION_FAILED", "ARAMINA_INVALID_RESULT",
})


class AraminaWorkflowError(Exception):
    """An allow-listed stable failure code; never arbitrary exception text."""

    def __init__(self, code: str) -> None:
        self.code = code if code in _SAFE_FAILURES else "ARAMINA_EXECUTION_FAILED"
        super().__init__(self.code)


def _build_aramina_request_json(
    *, patient_id: str, target_side: str,
    analysis_author: str = "", prediction_comment: str = "",
) -> dict[str, str]:
    """Validate local model input; omit all platform/private identifiers."""
    if not isinstance(patient_id, str) or not patient_id.strip():
        raise AraminaWorkflowError("ARAMINA_INVALID_REQUEST")
    if not isinstance(target_side, str) or target_side.strip().lower() not in {
        "left", "right",
    }:
        raise AraminaWorkflowError("ARAMINA_INVALID_REQUEST")
    if not isinstance(analysis_author, str) or not isinstance(prediction_comment, str):
        raise AraminaWorkflowError("ARAMINA_INVALID_REQUEST")
    return {
        "patient_id": patient_id.strip(),
        "target_side": target_side.strip().lower(),
        "analysis_author": analysis_author.strip() or _DEFAULT_AUTHOR,
        "prediction_comment": prediction_comment.strip(),
    }


def _load_selected_artifact(entry: RegistryModelEntry) -> dict[str, Any]:
    """Verify the same bytes we deserialize, only on the execution path."""
    if entry.artifact_type != ARTIFACT_TYPE or not entry._artifact_path:
        raise AraminaWorkflowError("ARAMINA_UNSUPPORTED_ARTIFACT")
    from .s3_model_discovery import _load_staged_artifact
    try:
        package = _load_staged_artifact(entry._artifact_path, entry._checksum)
    except ValueError:
        raise AraminaWorkflowError("ARAMINA_ARTIFACT_INTEGRITY_FAILED") from None
    except Exception:
        raise AraminaWorkflowError("ARAMINA_UNSUPPORTED_ARTIFACT") from None
    return _validate_artifact(package, entry)


def _validate_artifact(package: Any, entry: RegistryModelEntry) -> dict[str, Any]:
    """Validate identity, feature contract and estimator without defaults."""
    failure = "ARAMINA_UNSUPPORTED_ARTIFACT"
    if not isinstance(package, dict):
        raise AraminaWorkflowError(failure)
    required = {
        "model_id", "model_version", "artifact_type", "model",
        "feature_contract", "positive_class", "feature_schema_version",
    }
    if not required.issubset(package):
        raise AraminaWorkflowError(failure)
    if (package["model_id"] != entry.model_id
            or package["model_version"] != entry.model_version
            or package["artifact_type"] != ARTIFACT_TYPE
            or package["feature_schema_version"] != entry.feature_schema_version):
        raise AraminaWorkflowError(failure)
    contract = package["feature_contract"]
    if not isinstance(contract, dict) or set(contract) != {
        "schema_version", "position", "q_grid", "normalization",
    }:
        raise AraminaWorkflowError(failure)
    if (contract["schema_version"] != _FEATURE_CONTRACT
            or contract["normalization"] != "none"
            or not isinstance(contract["position"], str)
            or not contract["position"]):
        raise AraminaWorkflowError(failure)
    try:
        q = np.asarray(contract["q_grid"], dtype=float)
        if q.ndim != 1 or not q.size or not np.isfinite(q).all():
            raise ValueError
        if not (np.diff(q) > 0).all():
            raise ValueError
        model = package["model"]
        if not callable(getattr(model, "predict_proba", None)):
            raise ValueError
        classes = np.asarray(model.classes_)
        if (classes.ndim != 1 or classes.size != 2
                or len(set(classes.tolist())) != 2
                or np.count_nonzero(classes == package["positive_class"]) != 1):
            raise ValueError
        if getattr(model, "n_features_in_", q.size) != q.size:
            raise ValueError
    except Exception:
        raise AraminaWorkflowError(failure) from None
    return package


def _prepare_features(
    package: dict[str, Any], canonical: CanonicalXRDCase,
    request_json: dict[str, str], h5_path: str,
) -> np.ndarray:
    """Use existing normalization and patient resolution; reject ambiguity."""
    try:
        validate_canonical_case(canonical)
        from .workflow_orchestrator import _validate_aramina_source
        _validate_aramina_source(h5_path, canonical, request_json["patient_id"])
        contract = package["feature_contract"]
        candidates = [m for m in canonical.measurements
                      if m.side.lower() == request_json["target_side"]
                      and m.position == contract["position"]]
        if len(candidates) != 1:
            raise ValueError
        measurement = candidates[0]
        if measurement.qc_flags:
            raise ValueError
        q = np.asarray(contract["q_grid"], dtype=float)
        if not np.array_equal(measurement.q, q):
            raise ValueError
        features = np.asarray(measurement.intensity, dtype=float).reshape(1, -1)
        if not np.isfinite(features).all():
            raise ValueError
        return features.copy()
    except Exception:
        raise AraminaWorkflowError("ARAMINA_UNSUPPORTED_INPUT") from None


def _run_local_artifact(
    entry: RegistryModelEntry, canonical: CanonicalXRDCase,
    request_json: dict[str, str], h5_path: str,
) -> dict[str, float]:
    """Execute the selected estimator and return only a validated numeric score."""
    package = _load_selected_artifact(entry)
    features = _prepare_features(package, canonical, request_json, h5_path)
    model = package["model"]
    try:
        probabilities = np.asarray(model.predict_proba(features), dtype=float)
    except Exception:
        raise AraminaWorkflowError("ARAMINA_EXECUTION_FAILED") from None
    if (probabilities.shape != (1, 2) or not np.isfinite(probabilities).all()
            or (probabilities < 0).any() or (probabilities > 1).any()
            or not np.isclose(probabilities.sum(), 1.0)):
        raise AraminaWorkflowError("ARAMINA_INVALID_RESULT")
    index = np.flatnonzero(np.asarray(model.classes_) == package["positive_class"])[0]
    return {"risk_score": float(probabilities[0, index])}


class AraminaWorkflowProvider(WorkflowProvider):
    """Run one catalog-selected model locally, without environment/network config."""

    workflow_id = "aramina"

    def __init__(self, *, entry: RegistryModelEntry) -> None:
        self._entry = entry

    def readiness(self) -> WorkflowReadiness:
        # Discovery has staged the artifact. Structural/input failures are
        # reported by execute with stable codes, not a generic readiness gate.
        return WorkflowReadiness(
            workflow_id=self.workflow_id, configured=True, model_ready=True,
            scientifically_certified=False,
        )

    def validate_compatibility(self, canonical: Any) -> CompatibilityResult:
        return CompatibilityResult(compatible=True, reason="artifact_contract_required")

    def build_features(self, canonical: Any) -> WorkflowFeatureVector:
        raise AraminaWorkflowError("ARAMINA_INVALID_REQUEST")

    def run_inference(self, features: WorkflowFeatureVector) -> WorkflowResult:
        return WorkflowResult(
            workflow_id=self.workflow_id, status="failed",
            error="ARAMINA_INVALID_REQUEST",
        )

    def execute(
        self, canonical: Any, context: Any = None, *,
        aramina_request: AraminaProviderRequest | None = None, h5_path: str = "",
    ) -> WorkflowResult:
        try:
            if aramina_request is None:
                raise AraminaWorkflowError("ARAMINA_INVALID_REQUEST")
            request_json = _build_aramina_request_json(
                patient_id=aramina_request.patient_id,
                target_side=aramina_request.target_side,
                analysis_author=aramina_request.analysis_author,
                prediction_comment=aramina_request.prediction_comment,
            )
            report = _run_local_artifact(self._entry, canonical, request_json, h5_path)
            payload = {
                "workflow_id": self.workflow_id,
                "model_id": self._entry.model_id,
                "model_version": self._entry.model_version,
                "technical_demo_only": True,
                "scientifically_certified": False,
                "external_report": report,
            }
            if self._entry._clinical_stage == "research draft":
                payload["clinical_stage"] = "research draft"
            if context is not None:
                context.emit("runtime.output.completed", "output", "completed")
            return WorkflowResult(
                workflow_id=self.workflow_id, status="completed", payload=payload,
            )
        except AraminaWorkflowError as exc:
            code = exc.code
        except Exception:
            code = "ARAMINA_EXECUTION_FAILED"
        return WorkflowResult(workflow_id=self.workflow_id, status="failed", error=code)
