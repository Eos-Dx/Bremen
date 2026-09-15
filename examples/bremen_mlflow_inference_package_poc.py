"""Framework-neutral adapter PoC used by the PR0155 MLflow packaging spike.

This file intentionally does not import MLflow.  It proves that the real
BremenRuntime can accept a JSON/Pydantic-friendly batch boundary suitable for
an MLflow pyfunc signature without moving feature engineering into the adapter.
"""
from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

from bremen.api.xrd_normalization import CanonicalXRDMeasurement
from bremen.model_packages.bremen_v01.runtime import BremenRuntime
from bremen.model_runtime import ModelInput


class MeasurementInput(BaseModel):
    side: Literal["LEFT", "RIGHT"]
    position: str
    q: list[float]
    intensity: list[float]


class BremenCaseInput(BaseModel):
    measurements: list[MeasurementInput] = Field(min_length=6, max_length=6)


class BremenPredictionOutput(BaseModel):
    model_id: str
    model_version: str
    probability: float
    prediction: int
    threshold_applied: float
    decision_code: str
    feature_names: list[str]
    feature_values: list[float]


class BremenBatchAdapter:
    def __init__(self, model_package: dict):
        self.runtime = BremenRuntime(model_package)

    def predict(self, model_input: list[BremenCaseInput]) -> list[BremenPredictionOutput]:
        outputs: list[BremenPredictionOutput] = []
        for case in model_input:
            measurements = tuple(
                CanonicalXRDMeasurement(
                    side=m.side,
                    position=m.position,
                    q=np.asarray(m.q, dtype=np.float64),
                    intensity=np.asarray(m.intensity, dtype=np.float64),
                )
                for m in case.measurements
            )
            prediction = self.runtime.predict_model(
                ModelInput(workflow_id="bremen", measurements=measurements)
            )
            result = prediction.result
            outputs.append(
                BremenPredictionOutput(
                    model_id=prediction.model_id,
                    model_version=prediction.model_version,
                    probability=float(result["probability"]),
                    prediction=int(result["prediction"]),
                    threshold_applied=float(result["threshold_applied"]),
                    decision_code=str(result["decision_code"]),
                    feature_names=list(result["feature_names"]),
                    feature_values=list(result["feature_values"]),
                )
            )
        return outputs
