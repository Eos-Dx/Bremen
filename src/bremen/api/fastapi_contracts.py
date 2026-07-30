"""Pydantic request contracts for FastAPI Phase 3 write routes.

Framework-independent models that can be used outside FastAPI for
validation in tests or other transports.
"""

from __future__ import annotations

from typing import Optional

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
