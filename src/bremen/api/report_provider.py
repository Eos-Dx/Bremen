"""Report provider contract and common envelope.

Defines the abstract report provider protocol, the ``ReportEnvelope``
common wrapper, and report lifecycle statuses.

PR0077 — multi-workflow analysis workspace, event stream, and reports.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Report lifecycle statuses
# ---------------------------------------------------------------------------

REPORT_STATUS_NOT_REQUESTED = "not_requested"
REPORT_STATUS_PENDING = "pending"
REPORT_STATUS_GENERATING = "generating"
REPORT_STATUS_AVAILABLE = "available"
REPORT_STATUS_FAILED = "failed"
REPORT_STATUS_UNAVAILABLE = "unavailable"


# ---------------------------------------------------------------------------
# ReportEnvelope
# ---------------------------------------------------------------------------


@dataclass
class ReportEnvelope:
    """Common report envelope wrapping a workflow-specific payload.

    Every report carries safe technical metadata — workflow identity,
    model identity, schema version, scientific certification status,
    and a disclaimer.  The ``payload`` is workflow-specific.
    """

    report_id: str
    workflow_id: str
    job_id: str
    report_schema_version: str
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    workflow_status: str = REPORT_STATUS_NOT_REQUESTED
    model_id: str | None = None
    model_version: str | None = None
    scientifically_certified: bool = False
    disclaimer: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "workflow_id": self.workflow_id,
            "job_id": self.job_id,
            "report_schema_version": self.report_schema_version,
            "generated_at": self.generated_at,
            "workflow_status": self.workflow_status,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "scientifically_certified": self.scientifically_certified,
            "disclaimer": self.disclaimer,
            "payload": dict(self.payload),
        }


# ---------------------------------------------------------------------------
# ReportProvider protocol
# ---------------------------------------------------------------------------


class ReportProvider(ABC):
    """Abstract report provider for a workflow.

    Each workflow registers its own report provider.  The provider
    receives the workflow's ``WorkflowResult`` (from the multi-workflow
    runtime) and produces a typed ``ReportEnvelope``.
    """

    workflow_id: str = ""

    @abstractmethod
    def generate_report(
        self,
        job_id: str,
        workflow_result: dict[str, Any],
        *,
        model_identity: dict[str, str] | None = None,
        readiness_snapshot: dict[str, bool] | None = None,
    ) -> ReportEnvelope:
        """Generate a workflow-specific report from the output of a workflow run.

        Parameters
        ----------
        job_id : The analysis job ID.
        workflow_result : The ``WorkflowResult.payload`` dict from the
            workflow provider execution.
        model_identity : Optional model identity (model_id, model_version,
            model_checksum).
        readiness_snapshot : Optional readiness state at execution time.

        Returns
        -------
        A ``ReportEnvelope`` with workflow-specific payload.
        """
        ...
