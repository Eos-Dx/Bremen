"""Workflow registry with typed isolation.

Each workflow provider is registered independently.  Duplicate IDs
are rejected.  Unknown workflow lookups return typed errors.

PR0075 — multi-workflow runtime foundation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .workflow_provider import WorkflowProvider, WorkflowReadiness


class WorkflowRegistryError(Exception):
    """Base exception for workflow registry operations."""


class WorkflowNotFoundError(WorkflowRegistryError):
    """Requested workflow ID is not registered."""


class DuplicateWorkflowError(WorkflowRegistryError):
    """Workflow ID already registered."""


class WorkflowRegistry:
    """Registry of workflow providers.

    Providers are keyed by ``workflow_id``.  Registration order
    does not affect execution order — workflow selection is
    always explicit.
    """

    def __init__(self) -> None:
        self._providers: dict[str, WorkflowProvider] = {}

    def register(self, provider: WorkflowProvider) -> None:
        """Register a workflow provider.

        Raises DuplicateWorkflowError if the workflow ID is already registered.
        """
        wid = provider.workflow_id
        if wid in self._providers:
            raise DuplicateWorkflowError(
                f"Workflow '{wid}' is already registered"
            )
        self._providers[wid] = provider

    def resolve(self, workflow_id: str) -> WorkflowProvider:
        """Resolve a workflow provider by ID.

        Raises WorkflowNotFoundError if not registered.
        """
        if workflow_id not in self._providers:
            raise WorkflowNotFoundError(
                f"Workflow '{workflow_id}' not found"
            )
        return self._providers[workflow_id]

    def list_capabilities(self) -> dict[str, WorkflowReadiness]:
        """Return readiness for all registered workflows."""
        return {wid: p.readiness() for wid, p in self._providers.items()}

    def list_workflow_ids(self) -> list[str]:
        """Return all registered workflow IDs."""
        return list(self._providers.keys())
