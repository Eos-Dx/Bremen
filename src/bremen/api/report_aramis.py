"""Aramis report provider boundary.

Scaffold that returns an authoritative ``unavailable`` typed response.
Does not fabricate TRA probabilities, reliability, symmetry features,
sensitivity/specificity, recommendations, or clinical content.

When an authoritative Aramis report runtime is configured in the
future, this provider will delegate to it.

PR0077 — multi-workflow analysis workspace, event stream, and reports.
"""

from __future__ import annotations

import uuid
from typing import Any

from .report_provider import (
    ReportEnvelope,
    ReportProvider,
    REPORT_STATUS_UNAVAILABLE,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARAMIS_UNAVAILABLE_REASON = "WORKFLOW_OR_REPORT_PROVIDER_NOT_CONFIGURED"

ARAMIS_UNAVAILABLE_MESSAGE = (
    "The Aramis workflow report provider is not configured. "
    "No authoritative Aramis report content is available."
)


# ---------------------------------------------------------------------------
# Aramis report provider
# ---------------------------------------------------------------------------


class AramisReportProvider(ReportProvider):
    """Aramis report provider boundary.

    Returns ``unavailable`` with a typed reason code until an
    authoritative Aramis report runtime is configured.

    Does not fabricate:
    - TRA probabilities
    - reliability
    - symmetry features
    - sensitivity/specificity
    - recommendations
    - clinical content
    """

    workflow_id = "aramis"

    def generate_report(
        self,
        job_id: str,
        workflow_result: dict[str, Any],
        *,
        model_identity: dict[str, str] | None = None,
        readiness_snapshot: dict[str, bool] | None = None,
    ) -> ReportEnvelope:
        """Return an unavailable report with a typed reason code."""
        return ReportEnvelope(
            report_id=str(uuid.uuid4()),
            workflow_id=self.workflow_id,
            job_id=job_id,
            report_schema_version="v0.1",
            workflow_status=REPORT_STATUS_UNAVAILABLE,
            model_id=None,
            model_version=None,
            scientifically_certified=False,
            disclaimer=(
                "No authoritative Aramis report is available. "
                "This is a placeholder boundary only."
            ),
            payload={
                "reason_code": ARAMIS_UNAVAILABLE_REASON,
                "message": ARAMIS_UNAVAILABLE_MESSAGE,
            },
        )
