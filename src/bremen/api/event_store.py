"""Bounded in-memory event store with retention and eviction.

Thread-safe, deterministic eviction (LRU per job + max-age sweep).
Designed as the first implementation behind an interface that can be
replaced by a persistent store later.

Uses ``threading.Condition`` so SSE streams can block efficiently
until new events arrive rather than polling.

PR0077 — multi-workflow analysis workspace, event stream, and reports.
"""

from __future__ import annotations

import logging
import threading
import time as _time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

from .event_schema import (
    JobEvent,
    validate_event_details,
)

_log = logging.getLogger("bremen.event.store")

# ---------------------------------------------------------------------------
# Default limits (configurable at construction)
# ---------------------------------------------------------------------------

DEFAULT_MAX_JOBS = 100
DEFAULT_MAX_EVENTS_PER_JOB = 1000
DEFAULT_MAX_AGE_SECONDS = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Internal per-job bucket
# ---------------------------------------------------------------------------


@dataclass
class _JobBucket:
    """Per-job event storage with sequence tracking."""

    job_id: str
    events: list[JobEvent] = field(default_factory=list)
    sequence: int = 0
    last_access: float = field(default_factory=_time.monotonic)

    def append(self, event: JobEvent) -> JobEvent:
        """Append an event, assigning the next monotonic sequence number."""
        self.sequence += 1
        stamped = JobEvent(
            schema_version=event.schema_version,
            event_id=event.event_id,
            sequence=self.sequence,
            timestamp=event.timestamp,
            job_id=event.job_id,
            request_id=event.request_id,
            workflow_id=event.workflow_id,
            stage=event.stage,
            event_type=event.event_type,
            status=event.status,
            duration_ms=event.duration_ms,
            details=dict(event.details),
        )
        self.events.append(stamped)
        self.last_access = _time.monotonic()
        return stamped


# ---------------------------------------------------------------------------
# Public store
# ---------------------------------------------------------------------------


class BoundedEventStore:
    """Thread-safe bounded in-memory event store.

    Enforces:
    - ``max_jobs`` — oldest (LRU) jobs evicted when exceeded.
    - ``max_events_per_job`` — oldest events dropped per job.
    - ``max_age_seconds`` — events older than this age are evicted
      on ``evict_old()``.

    Storage metadata is exposed for API responses:
    - ``storage_mode = "ephemeral"``
    - ``retention_seconds``
    - ``max_jobs``

    SSE streams can use ``wait_for_events()`` to block efficiently
    until new events are available for a job.
    """

    def __init__(
        self,
        max_jobs: int = DEFAULT_MAX_JOBS,
        max_events_per_job: int = DEFAULT_MAX_EVENTS_PER_JOB,
        max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    ) -> None:
        self._max_jobs = max_jobs
        self._max_events_per_job = max_events_per_job
        self._max_age_seconds = max_age_seconds
        self._buckets: OrderedDict[str, _JobBucket] = OrderedDict()
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)

    # ---- Storage metadata ----

    @property
    def storage_mode(self) -> str:
        return "ephemeral"

    @property
    def retention_seconds(self) -> int:
        return self._max_age_seconds

    @property
    def max_jobs(self) -> int:
        return self._max_jobs

    # ---- Core operations ----

    def append(self, job_id: str, event: JobEvent) -> JobEvent:
        """Append a validated event to *job_id*, returning the stamped event.

        Automatically enforces per-job cap and job-count LRU eviction.
        Notifies all waiters blocked on ``wait_for_events()``.
        """
        validate_event_details(event.details)

        with self._condition:
            bucket = self._buckets.get(job_id)
            if bucket is None:
                # Create new bucket; evict LRU if at max capacity
                if len(self._buckets) >= self._max_jobs:
                    self._buckets.popitem(last=False)  # evict oldest
                bucket = _JobBucket(job_id=job_id)
                self._buckets[job_id] = bucket
            else:
                # Touch for LRU ordering
                self._buckets.move_to_end(job_id)

            # Enforce per-job event cap
            if len(bucket.events) >= self._max_events_per_job:
                bucket.events.pop(0)

            stamped = bucket.append(event)
            _log.debug(
                "bremen.event.store.append\t"
                "job_id=%s\tsequence=%s\tevent_type=%s",
                job_id, stamped.sequence, stamped.event_type,
            )
            self._condition.notify_all()
            return stamped

    def get_events(
        self, job_id: str, since_sequence: int = 0
    ) -> list[JobEvent]:
        """Return events for *job_id* with ``sequence > since_sequence``."""
        with self._condition:
            bucket = self._buckets.get(job_id)
            if bucket is None:
                return []
            return [e for e in bucket.events if e.sequence > since_sequence]

    def get_job_event_count(self, job_id: str) -> int:
        """Return the number of stored events for *job_id*."""
        with self._condition:
            bucket = self._buckets.get(job_id)
            return len(bucket.events) if bucket else 0

    def get_job_cursor(self, job_id: str) -> int:
        """Return the last sequence number for *job_id*, or 0 if unknown."""
        with self._condition:
            bucket = self._buckets.get(job_id)
            return bucket.sequence if bucket else 0

    def has_job(self, job_id: str) -> bool:
        """Return ``True`` if *job_id* is known to the store."""
        with self._condition:
            return job_id in self._buckets

    # ---- Stream support ----

    def wait_for_events(
        self, job_id: str, since_sequence: int, timeout: float,
    ) -> list[JobEvent]:
        """Block until new events for *job_id* are available or *timeout*.

        Returns new events with ``sequence > since_sequence``, or an
        empty list if the timeout expires before new events arrive.

        Parameters
        ----------
        job_id : The job ID to wait for.
        since_sequence : Return events with sequence greater than this.
        timeout : Maximum seconds to wait.

        Returns
        -------
        List of events that arrived since the cursor.
        """
        with self._condition:
            # Check immediately
            events = self._get_new_events_locked(job_id, since_sequence)
            if events:
                return events

            # Wait for notification or timeout
            self._condition.wait(timeout=timeout)

            # Re-scan for new events
            return self._get_new_events_locked(job_id, since_sequence)

    def _get_new_events_locked(
        self, job_id: str, since_sequence: int,
    ) -> list[JobEvent]:
        """Must be called while holding ``_condition``."""
        bucket = self._buckets.get(job_id)
        if bucket is None:
            return []
        return [e for e in bucket.events if e.sequence > since_sequence]

    # ---- Eviction ----

    def evict_old(self) -> int:
        """Evict jobs whose last access is older than ``max_age_seconds``.

        Returns the count of evicted jobs.
        """
        now = _time.monotonic()
        max_age = self._max_age_seconds
        evicted = 0
        with self._condition:
            stale = [
                jid
                for jid, b in self._buckets.items()
                if (now - b.last_access) > max_age
            ]
            for jid in stale:
                del self._buckets[jid]
                evicted += 1
        return evicted

    def reset_for_tests(self) -> None:
        """Clear all stored jobs and events (test-only)."""
        with self._condition:
            self._buckets.clear()
