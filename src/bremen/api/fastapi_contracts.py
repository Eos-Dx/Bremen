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



class ModelRequirementsValidateRequest(BaseModel):
    """Request body for POST /demo/api/models/{model_id}/requirements/validate.

    This is intentionally permissive in PR0122 because validation is a
    no-op/not-available contract. The endpoint echoes safe identifiers but
    must not open H5, create inference jobs, or create reports.
    """

    container_id: Optional[str] = Field(default=None, description="Catalog/display container ID")
    source_id: Optional[str] = Field(default=None, description="Fresh catalog source ID")
    upload_id: Optional[str] = Field(default=None, description="Staged upload ID")
    h5_path: Optional[str] = Field(default=None, description="Legacy explicit H5 path")
    workflow_id: Optional[str] = Field(default=None, description="Workflow routing key")
    storage: Optional[dict[str, Any]] = Field(default=None, description="Future direct storage reference")
