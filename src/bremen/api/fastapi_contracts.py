"""Pydantic request contracts for FastAPI Phase 3 write routes.

Framework-independent models that can be used outside FastAPI for
validation in tests or other transports.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    """Request body for POST /demo/api/jobs.

    Accepts the Control Room contract with model_id, source_id/upload_id,
    and preserves legacy h5_path and container_id for backward compatibility.

    Exactly one of ``source_id``, ``upload_id``, ``h5_path``, or
    ``container_id`` must be provided (validated at the route level
    against existing business-logic semantics).
    """

    workflow_id: str = Field(default="bremen", description="Workflow to execute")
    model_id: Optional[str] = Field(default=None, description="Model selection ID")
    source_id: Optional[str] = Field(default=None, description="Opaque catalog source ID")
    upload_id: Optional[str] = Field(default=None, description="Opaque staged upload ID")
    h5_path: str = Field(default="", description="Legacy explicit filesystem path")
    container_id: str = Field(default="", description="Legacy container ID")
    action: str = Field(default="", description="Action routing (e.g. delete_report)")
    # Aramina-specific request fields
    patient_id: Optional[str] = Field(default=None, description="Patient identifier for Aramina")
    target_side: Optional[str] = Field(default=None, description="Target side: left or right")
    analysis_author: Optional[str] = Field(default=None, description="Analysis author for Aramina")
    prediction_comment: Optional[str] = Field(default=None, description="Prediction comment for Aramina")



class ModelRequirementsValidateRequest(BaseModel):
    """Request body for POST /demo/api/models/{model_id}/requirements/validate.

    This is intentionally permissive in PR0122 because validation is a
    no-op/not-available contract. The endpoint echoes safe identifiers but
    must not open H5, create inference jobs, or create reports.

    PR0158a: carries the model-specific request fields the validation layer is
    authoritative about. ``patient_id`` and ``target_side`` (plus
    ``analysis_author``/``prediction_comment`` for parity with
    ``JobCreateRequest``) must survive ``model_dump(exclude_none=True)`` so an
    Aramina preflight does not spuriously report them missing.  These are plain
    request-contract fields only; no Aramina scientific validation is performed
    here and the model-requirements layer remains authoritative.
    """

    container_id: Optional[str] = Field(default=None, description="Catalog/display container ID")
    source_id: Optional[str] = Field(default=None, description="Fresh catalog source ID")
    upload_id: Optional[str] = Field(default=None, description="Staged upload ID")
    h5_path: Optional[str] = Field(default=None, description="Legacy explicit H5 path")
    workflow_id: Optional[str] = Field(default=None, description="Workflow routing key")
    storage: Optional[dict[str, Any]] = Field(default=None, description="Future direct storage reference")
    # Model-specific request fields preserved through model_dump(exclude_none=True).
    # All default None so a request omitting them is unchanged (Bremen no-op path).
    patient_id: Optional[str] = Field(default=None, description="Patient identifier (Aramina)")
    target_side: Optional[str] = Field(default=None, description="Target side: left or right (Aramina)")
    analysis_author: Optional[str] = Field(default=None, description="Analysis author (Aramina)")
    prediction_comment: Optional[str] = Field(default=None, description="Prediction comment (Aramina)")
