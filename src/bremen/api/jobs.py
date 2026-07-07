"""In-memory async job store for the Bremen API.

Not persistent — for test/stub/dev use only.  No background worker,
no concurrency handling beyond basic safety.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .schemas import (
    CompletedResult,
    PredictionRequest,
    STATUS_ACCEPTED,
)

_log = logging.getLogger(__name__)


@dataclass
class JobRecord:
    """Internal record for a single prediction job."""

    job_id: str
    status: str
    submitted_at: str
    updated_at: str | None
    request: PredictionRequest | None
    result: CompletedResult | None
    error: str | None


class InMemoryJobStore:
    """In-memory job store.

    Stores ``JobRecord`` objects keyed by UUID string.  No persistence,
    no background worker, no concurrency control.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}

    def create_job(
        self, request: PredictionRequest | None = None
    ) -> JobRecord:
        """Create and store a new job with status ``accepted``.

        Parameters
        ----------
        request : Optional ``PredictionRequest`` to associate with the job.

        Returns
        -------
        The newly created ``JobRecord``.
        """
        job_id = str(uuid.uuid4())
        now = _utc_now()
        record = JobRecord(
            job_id=job_id,
            status=STATUS_ACCEPTED,
            submitted_at=now,
            updated_at=None,
            request=request,
            result=None,
            error=None,
        )
        self._jobs[job_id] = record
        _log.info(
            "bremen.job.created\t"
            "stage=job\tstatus=created\t"
            "job_id=%s",
            job_id,
        )
        return record

    def get_job(self, job_id: str) -> JobRecord | None:
        """Retrieve a job by its ID.

        Parameters
        ----------
        job_id : The job's UUID string.

        Returns
        -------
        The ``JobRecord`` if found, or ``None``.
        """
        return self._jobs.get(job_id)

    def update_status(
        self,
        job_id: str,
        status: str,
        result: CompletedResult | None = None,
        error: str | None = None,
    ) -> None:
        """Update the status (and optionally result/error) of a job.

        Parameters
        ----------
        job_id : The job's UUID string.
        status : New status value.
        result : Optional ``CompletedResult``.
        error : Optional error message string.

        Raises
        ------
        KeyError
            If *job_id* is not found.
        """
        record = self._jobs[job_id]
        record.status = status
        record.updated_at = _utc_now()
        if result is not None:
            record.result = result
        if error is not None:
            record.error = error
        if status == "completed":
            _log.info(
                "bremen.job.completed\t"
                "stage=job\tstatus=completed\t"
                "job_id=%s",
                job_id,
            )
        elif status == "failed":
            _log.error(
                "bremen.job.failed\t"
                "stage=job\tstatus=failed\t"
                "job_id=%s\t"
                "safe_reason=%s",
                job_id,
                (error or "")[:200],
            )

    @property
    def job_count(self) -> int:
        """Number of jobs currently stored."""
        return len(self._jobs)


def _utc_now() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()
