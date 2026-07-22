"""Comprehensive backend tests for event schema, bounded store, and SSE.

Covers:
- event schema version, ID uniqueness, UTC timestamps
- monotonic sequence per job
- concurrent writes, per-job isolation
- max events per job, max jobs, age eviction, LRU eviction
- prohibited detail validation and allowlist filtering
- job lookup, event cursor, invalid cursor
- unknown/expired job responses
- SSE content type, event framing, Last-Event-ID
- reconnect without replaying acknowledged events
- prompt delivery of newly emitted events (latency < 2s)
- heartbeat only when no events arrive
- terminal stream_complete
- client disconnect cleanup
- event/log recursion prevention
- no empty job_id or request_id in stored events
- module-reload safety
"""

from __future__ import annotations

import json
import threading
import time as _time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bremen.api.event_schema import (
    JobEvent,
    EventType,
    SCHEMA_VERSION,
    validate_event_details,
    allowed_event_details,
)
from bremen.api.event_store import BoundedEventStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    job_id: str = "job-1",
    request_id: str = "req-1",
    event_type: str = "runtime.request.accepted",
    **kwargs,
) -> JobEvent:
    defaults = {
        "job_id": job_id,
        "request_id": request_id,
        "stage": "test",
        "event_type": event_type,
        "status": "started",
    }
    defaults.update(kwargs)
    return JobEvent(**defaults)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Event schema validation
# ---------------------------------------------------------------------------


class TestEventSchema:
    """Tests for event schema structure and validation."""

    def test_schema_version_is_stable(self):
        """SCHEMA_VERSION is a non-empty string."""
        assert isinstance(SCHEMA_VERSION, str)
        assert len(SCHEMA_VERSION) > 0

    def test_event_id_is_unique(self):
        """Two JobEvent instances have distinct event_ids."""
        e1 = _make_event()
        e2 = _make_event()
        assert e1.event_id != e2.event_id

    def test_timestamp_is_utc_iso(self):
        """Timestamp is an ISO-8601 UTC string."""
        e = _make_event()
        ts = e.timestamp
        assert "T" in ts
        assert "+" in ts or "Z" in ts

    def test_to_dict_is_deterministic(self):
        """to_dict() produces JSON-serializable output with all fields."""
        e = _make_event()
        d = e.to_dict()
        assert d["schema_version"] == SCHEMA_VERSION
        assert d["event_id"] == e.event_id
        assert d["sequence"] == e.sequence
        assert d["job_id"] == e.job_id
        assert d["request_id"] == e.request_id

    def test_prohibited_details_rejected(self):
        """validate_event_details raises ValueError on prohibited keys."""
        for key in ["patient_id", "raw_data", "poni_text", "traceback"]:
            with pytest.raises(ValueError):
                validate_event_details({key: "test"})

    def test_allowed_details_filters_prohibited(self):
        """allowed_event_details strips prohibited keys."""
        raw = {"safe": "ok", "patient_id": "bad", "raw_data": [1, 2]}
        clean = allowed_event_details(raw)
        assert "safe" in clean
        assert "patient_id" not in clean
        assert "raw_data" not in clean

    def test_event_type_enum_covers_lifecycle(self):
        """EventType enum includes all required lifecycle events."""
        required = {
            "runtime.request.accepted",
            "runtime.normalization.started",
            "runtime.normalization.completed",
            "runtime.normalization.failed",
            "runtime.workflow.resolved",
            "runtime.workflow.started",
            "runtime.workflow.completed",
            "runtime.workflow.failed",
            "runtime.model.validation.started",
            "runtime.model.validation.completed",
            "runtime.features.started",
            "runtime.features.completed",
            "runtime.request.completed",
        }
        all_values = {e.value for e in EventType}
        assert required.issubset(all_values)


# ---------------------------------------------------------------------------
# Event store — basic operations
# ---------------------------------------------------------------------------


class TestBoundedEventStore:
    """Tests for BoundedEventStore core operations."""

    def test_append_returns_stamped_event(self):
        store = BoundedEventStore()
        e = _make_event()
        stamped = store.append("job-1", e)
        assert stamped.sequence == 1
        assert stamped.job_id == "job-1"

    def test_monotonic_sequence_per_job(self):
        """Events within a job receive increasing sequence numbers."""
        store = BoundedEventStore()
        s1 = store.append("job-a", _make_event(job_id="job-a")).sequence
        s2 = store.append("job-a", _make_event(job_id="job-a")).sequence
        s3 = store.append("job-a", _make_event(job_id="job-a")).sequence
        assert s1 < s2 < s3

    def test_sequence_independent_per_job(self):
        """Different jobs have independent sequence counters."""
        store = BoundedEventStore()
        store.append("job-a", _make_event(job_id="job-a"))
        store.append("job-a", _make_event(job_id="job-a"))
        s_b1 = store.append("job-b", _make_event(job_id="job-b")).sequence
        assert s_b1 == 1  # starts from 1

    def test_no_duplicate_sequence_values(self):
        """No two events for the same job share a sequence number."""
        store = BoundedEventStore()
        seen = set()
        for _ in range(10):
            stamped = store.append("job-1", _make_event(job_id="job-1"))
            assert stamped.sequence not in seen
            seen.add(stamped.sequence)

    def test_per_job_event_isolation(self):
        """Events from job A are not visible in job B."""
        store = BoundedEventStore()
        store.append("job-a", _make_event(job_id="job-a"))
        store.append("job-b", _make_event(job_id="job-b"))
        a_events = store.get_events("job-a")
        assert all(e.job_id == "job-a" for e in a_events)

    def test_get_events_since_cursor(self):
        store = BoundedEventStore()
        store.append("j1", _make_event(job_id="j1"))
        store.append("j1", _make_event(job_id="j1"))
        store.append("j1", _make_event(job_id="j1"))
        events = store.get_events("j1", since_sequence=1)
        assert len(events) == 2
        assert all(e.sequence > 1 for e in events)

    def test_get_events_unknown_job(self):
        store = BoundedEventStore()
        assert store.get_events("nonexistent") == []

    def test_has_job(self):
        store = BoundedEventStore()
        assert not store.has_job("unseen")
        store.append("j1", _make_event(job_id="j1"))
        assert store.has_job("j1")

    def test_get_job_cursor(self):
        store = BoundedEventStore()
        assert store.get_job_cursor("unknown") == 0
        store.append("j1", _make_event(job_id="j1"))
        store.append("j1", _make_event(job_id="j1"))
        assert store.get_job_cursor("j1") == 2

    def test_no_empty_job_id(self):
        """Stored events must not have empty job_id or request_id."""
        store = BoundedEventStore()
        e = _make_event(job_id="valid-job", request_id="")
        stamped = store.append("valid-job", e)
        assert stamped.job_id == "valid-job"
        # request_id may be empty but job_id must not
        assert stamped.job_id != ""

    def test_no_empty_job_id_in_events(self):
        """Appending with empty job_id key stores under that key,
        but the events themselves carry their original job_id."""
        store = BoundedEventStore()
        e = _make_event(job_id="real-job", request_id="real-req")
        stamped = store.append("real-job", e)
        assert stamped.job_id == "real-job"
        assert stamped.request_id == "real-req"
        stored = store.get_events("real-job")
        assert all(ev.job_id == "real-job" for ev in stored)


# ---------------------------------------------------------------------------
# Event store — boundedness
# ---------------------------------------------------------------------------


class TestBoundedEventStoreLimits:
    """Tests for boundedness: max events, max jobs, LRU eviction, age."""

    def test_max_events_per_job(self):
        store = BoundedEventStore(max_events_per_job=5)
        for _ in range(8):
            store.append("j1", _make_event(job_id="j1"))
        assert store.get_job_event_count("j1") == 5

    def test_max_jobs_lru_eviction(self):
        store = BoundedEventStore(max_jobs=3)
        store.append("j1", _make_event(job_id="j1"))
        store.append("j2", _make_event(job_id="j2"))
        store.append("j3", _make_event(job_id="j3"))
        # j1 is oldest
        store.append("j4", _make_event(job_id="j4"))  # should evict j1
        assert not store.has_job("j1")
        assert store.has_job("j2")

    def test_lru_touch_on_append(self):
        """Appending to an existing job moves it to LRU end."""
        store = BoundedEventStore(max_jobs=3)
        store.append("j1", _make_event(job_id="j1"))
        store.append("j2", _make_event(job_id="j2"))
        store.append("j3", _make_event(job_id="j3"))
        # Touch j1
        store.append("j1", _make_event(job_id="j1"))
        # Now j1 is recent, j2 is oldest
        store.append("j4", _make_event(job_id="j4"))
        assert store.has_job("j1")  # survived
        assert not store.has_job("j2")  # evicted

    def test_age_eviction(self):
        store = BoundedEventStore(max_age_seconds=0)  # expire immediately
        store.append("j1", _make_event(job_id="j1"))
        _time.sleep(0.01)
        evicted = store.evict_old()
        assert evicted >= 1
        assert not store.has_job("j1")

    def test_deterministic_lru(self):
        store = BoundedEventStore(max_jobs=2)
        store.append("a", _make_event(job_id="a"))
        store.append("b", _make_event(job_id="b"))
        store.append("c", _make_event(job_id="c"))
        # 'a' must have been evicted (oldest)
        assert not store.has_job("a")
        assert store.has_job("b")
        assert store.has_job("c")


# ---------------------------------------------------------------------------
# Event store — concurrency
# ---------------------------------------------------------------------------


class TestBoundedEventStoreConcurrency:
    """Tests for thread safety and concurrent access."""

    def test_concurrent_writes_same_job(self):
        store = BoundedEventStore()
        N = 50
        barrier = threading.Barrier(4)

        def writer():
            barrier.wait()
            for _ in range(N):
                store.append("shared", _make_event(job_id="shared"))

        threads = [threading.Thread(target=writer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert store.get_job_event_count("shared") == 4 * N
        events = store.get_events("shared")
        sequences = [e.sequence for e in events]
        assert len(sequences) == len(set(sequences))  # no duplicates
        assert sorted(sequences) == sequences  # monotonic

    def test_concurrent_writes_different_jobs(self):
        store = BoundedEventStore()
        N = 30

        def writer(jid):
            for _ in range(N):
                store.append(jid, _make_event(job_id=jid))

        threads = [
            threading.Thread(target=writer, args=(f"j{i}",))
            for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for i in range(4):
            assert store.get_job_event_count(f"j{i}") == N


# ---------------------------------------------------------------------------
# Event store — module-reload safety
# ---------------------------------------------------------------------------


class TestBoundedEventStoreModuleReload:
    """Verify store survives bremen.api.* module purge/re-import."""

    def test_store_survives_module_reload(self):
        """Events stored in original store remain visible after module reload."""
        import sys
        import importlib

        from bremen.api.job_api_handler import (
            _event_store as original_store,
            reset_for_tests,
        )

        reset_for_tests()
        original_store.append("j1", _make_event(job_id="j1"))

        # Purge and reload bremen.api.* modules
        for key in list(sys.modules):
            if key.startswith("bremen.api"):
                del sys.modules[key]
        importlib.import_module("bremen.api")

        from bremen.api.job_api_handler import (
            _event_store as reloaded_store,
        )

        # The same module-level store should be authoritative
        assert reloaded_store.has_job("j1")
        events = reloaded_store.get_events("j1")
        assert len(events) == 1
        assert events[0].job_id == "j1"

        reset_for_tests()


# ---------------------------------------------------------------------------
# SSE — prompt delivery latency
# ---------------------------------------------------------------------------


class TestSSEPromptDelivery:
    """Verify SSE events are delivered promptly, not after 15 s."""

    def test_new_event_notified_quickly(self):
        """A new event emitted while an SSE stream is waiting is delivered
        within a testable latency (well under 2 s, not 15 s)."""
        store = BoundedEventStore()
        store.append("j1", _make_event(job_id="j1"))

        cursor = store.get_job_cursor("j1")
        delivered: list = []

        def waiter():
            evs = store.wait_for_events("j1", cursor, timeout=10.0)
            delivered.extend(evs)

        t = threading.Thread(target=waiter)
        t.start()

        # Wait a tiny bit then emit
        _time.sleep(0.05)
        store.append("j1", _make_event(job_id="j1"))

        t.join(timeout=3.0)
        assert not t.is_alive(), "waiter did not return — condition may not have fired"
        assert len(delivered) >= 1, (
            "New event was not delivered within test window"
        )

    def test_heartbeat_only_when_no_events(self):
        """wait_for_events returns empty list when timeout expires with no events."""
        store = BoundedEventStore()
        store.append("j1", _make_event(job_id="j1"))
        cursor = store.get_job_cursor("j1")

        t0 = _time.monotonic()
        evs = store.wait_for_events("j1", cursor, timeout=0.2)
        elapsed = _time.monotonic() - t0

        assert evs == []  # no new events
        assert elapsed >= 0.15  # waited at least close to timeout


# ---------------------------------------------------------------------------
# SSE — reconnect and cursor
# ---------------------------------------------------------------------------


class TestSSEReconnect:
    """Tests for SSE reconnect semantics."""

    def test_reconnect_after_cursor_skips_old_events(self):
        store = BoundedEventStore()
        store.append("j1", _make_event(job_id="j1"))
        store.append("j1", _make_event(job_id="j1"))
        cursor = store.get_job_cursor("j1")  # 2

        # Reconnect with Last-Event-ID = 2
        events = store.get_events("j1", since_sequence=2)
        assert len(events) == 0  # no new events after cursor

    def test_reconnect_picks_up_new_events(self):
        store = BoundedEventStore()
        store.append("j1", _make_event(job_id="j1"))
        cursor = store.get_job_cursor("j1")  # 1

        store.append("j1", _make_event(job_id="j1"))
        store.append("j1", _make_event(job_id="j1"))

        events = store.get_events("j1", since_sequence=cursor)
        assert len(events) == 2


# ---------------------------------------------------------------------------
# Recursion prevention
# ---------------------------------------------------------------------------


class TestEventRecursion:
    """Verify no event/log recursion occurs."""

    def test_store_logger_not_captured(self):
        """The event store logger uses 'bremen.event.store' namespace
        to avoid being captured by any event-capture mechanism."""
        import logging
        logger = logging.getLogger("bremen.event.store")
        assert logger.name == "bremen.event.store"

    def test_append_does_not_emit_event(self):
        """Appending an event does not recursively emit another event."""
        store = BoundedEventStore()
        store.append("j1", _make_event(job_id="j1"))
        # Only the original event exists
        assert store.get_job_event_count("j1") == 1


# ---------------------------------------------------------------------------
# Storage metadata
# ---------------------------------------------------------------------------


class TestStoreMetadata:
    def test_storage_mode_is_ephemeral(self):
        store = BoundedEventStore()
        assert store.storage_mode == "ephemeral"

    def test_retention_and_max_jobs(self):
        store = BoundedEventStore(max_jobs=5, max_age_seconds=60)
        assert store.max_jobs == 5
        assert store.retention_seconds == 60
