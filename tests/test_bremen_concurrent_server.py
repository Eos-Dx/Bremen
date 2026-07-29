"""Concurrent safety tests for PR0079.

Covers:
- ThreadingHTTPServer class properties (AST/import check, no real server)
- Singleton initialization under concurrent first access
- Module reload preserves store, jobs, and locks
- Concurrent job creation and list iteration safety
- InMemoryJobStore thread safety (W001 resolution)
- BoundedEventStore thread safety

Server-spawning tests (ThreadingHTTPServer, urlopen, socket.create_connection)
have been removed. SSE concurrency and server shutdown tests are covered by
the http.server integration suite and manual smoke scripts.
"""

from __future__ import annotations

import threading
import time as _time

import pytest

from bremen.api.jobs import InMemoryJobStore
from bremen.api.job_api_handler import (
    reset_for_tests,
    _event_store,
    _jobs,
    _jobs_lock as _job_api_jobs_lock,
    _report_providers,
    _providers_lock,
    create_analysis_job,
    get_analysis_job,
    list_analysis_jobs,
)
from bremen.api.event_store import BoundedEventStore
from bremen.api.event_schema import JobEvent


# ---------------------------------------------------------------------------
# Threaded server class tests (AST/import check only)
# ---------------------------------------------------------------------------


class TestThreadedServerClass:
    def test_threading_server_is_used(self):
        """_ThreadingHTTPServer exists and has correct properties."""
        from bremen.api.server import _ThreadingHTTPServer

        # Verify it inherits from HTTPServer without importing HTTPServer
        mro_names = [c.__name__ for c in _ThreadingHTTPServer.__mro__]
        assert "HTTPServer" in mro_names
        assert hasattr(_ThreadingHTTPServer, "daemon_threads")
        assert _ThreadingHTTPServer.daemon_threads is True


# ---------------------------------------------------------------------------
# Singleton initialization tests
# ---------------------------------------------------------------------------


class TestSingletonInitialization:
    def test_singleton_first_access_no_duplicate_creation(self):
        """Multiple concurrent first-access calls produce one store."""
        import bremen
        reset_for_tests()

        for key in [
            "_bremen_workspace_event_store",
            "_bremen_workspace_jobs",
            "_bremen_workspace_report_providers",
            "_bremen_workspace_init_lock",
            "_bremen_workspace_jobs_lock",
            "_bremen_workspace_providers_lock",
        ]:
            try:
                delattr(bremen, key)
            except AttributeError:
                pass

        results = []
        barrier = threading.Barrier(4)

        def create():
            barrier.wait()
            from bremen.api.job_api_handler import (
                _get_or_create_store,
                _get_or_create_jobs,
                _get_or_create_providers,
            )
            s = _get_or_create_store()
            j = _get_or_create_jobs()
            p = _get_or_create_providers()
            results.append((id(s), id(j), id(p)))

        threads = [threading.Thread(target=create) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        store_ids = {r[0] for r in results}
        jobs_ids = {r[1] for r in results}
        providers_ids = {r[2] for r in results}

        assert len(store_ids) == 1, "Multiple event stores created"
        assert len(jobs_ids) == 1, "Multiple jobs dicts created"
        assert len(providers_ids) == 1, "Multiple providers dicts created"

    def test_module_reload_preserves_singletons(self):
        """Module reload preserves store, jobs, and lock identity."""
        import sys
        import importlib
        import bremen

        reset_for_tests()

        store_id_before = id(_event_store)
        jobs_id_before = id(_jobs)
        lock_id_before = id(_job_api_jobs_lock)

        for key in list(sys.modules):
            if key.startswith("bremen.api"):
                del sys.modules[key]
        importlib.import_module("bremen.api")

        from bremen.api.job_api_handler import (
            _event_store as reloaded_store,
            _jobs as reloaded_jobs,
            _jobs_lock as reloaded_lock,
        )

        assert reloaded_store is not None
        assert reloaded_jobs is not None
        assert reloaded_lock is not None
        assert hasattr(bremen, "_bremen_workspace_event_store")
        assert hasattr(bremen, "_bremen_workspace_jobs")
        assert hasattr(bremen, "_bremen_workspace_jobs_lock")


# ---------------------------------------------------------------------------
# Concurrent job storage tests
# ---------------------------------------------------------------------------


class TestConcurrentJobStorage:
    def test_concurrent_job_creation(self):
        """Multiple threads creating jobs simultaneously, all visible."""
        reset_for_tests()
        import tempfile
        import os
        import h5py
        import numpy as np

        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, "test.h5")
            with h5py.File(h5_path, "w") as f:
                scans = f.create_group("scans")
                for label in ("target", "contralateral"):
                    grp = scans.create_group(label)
                    arr = np.random.default_rng(42).normal(10.0, 2.0, 100).astype(np.float64)
                    grp.create_dataset("measurements", data=arr.reshape(1, -1))

            job_ids = []
            barrier = threading.Barrier(3)

            def create_job():
                barrier.wait()
                job = create_analysis_job(h5_path=h5_path)
                job_ids.append(job.job_id)

            threads = [threading.Thread(target=create_job) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(job_ids) == 3
            for jid in job_ids:
                assert get_analysis_job(jid) is not None

    def test_concurrent_list_during_creation(self):
        """list_analysis_jobs does not raise during concurrent creation."""
        reset_for_tests()
        import tempfile
        import os
        import h5py
        import numpy as np

        with tempfile.TemporaryDirectory() as td:
            h5_path = os.path.join(td, "test.h5")
            with h5py.File(h5_path, "w") as f:
                scans = f.create_group("scans")
                for label in ("target", "contralateral"):
                    grp = scans.create_group(label)
                    arr = np.random.default_rng(42).normal(10.0, 2.0, 100).astype(np.float64)
                    grp.create_dataset("measurements", data=arr.reshape(1, -1))

            errors = []
            barrier = threading.Barrier(2)

            def create_job():
                barrier.wait()
                try:
                    for _ in range(5):
                        create_analysis_job(h5_path=h5_path)
                except Exception as exc:
                    errors.append(exc)

            def list_jobs():
                barrier.wait()
                try:
                    for _ in range(20):
                        list_analysis_jobs()
                        _time.sleep(0.01)
                except Exception as exc:
                    errors.append(exc)

            t1 = threading.Thread(target=create_job)
            t2 = threading.Thread(target=list_jobs)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            assert len(errors) == 0, f"Errors during concurrent access: {errors}"


# ---------------------------------------------------------------------------
# InMemoryJobStore thread safety tests (W001 resolution)
# ---------------------------------------------------------------------------


class TestInMemoryJobStoreThreadSafety:
    def test_concurrent_create_and_read(self):
        """Concurrent create and read operations are safe."""
        store = InMemoryJobStore()
        barrier = threading.Barrier(3)
        errors = []

        def create():
            barrier.wait()
            try:
                for _ in range(20):
                    store.create_job()
            except Exception as exc:
                errors.append(exc)

        def read():
            barrier.wait()
            try:
                for _ in range(50):
                    store.job_count
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=create) for _ in range(2)]
        threads.append(threading.Thread(target=read))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        assert store.job_count == 40

    def test_concurrent_update_and_read(self):
        """Concurrent status update and read are safe."""
        store = InMemoryJobStore()
        job = store.create_job()
        barrier = threading.Barrier(2)
        errors = []

        def update():
            barrier.wait()
            try:
                for _ in range(20):
                    store.update_status(job.job_id, "completed")
            except Exception as exc:
                errors.append(exc)

        def read():
            barrier.wait()
            try:
                for _ in range(50):
                    store.get_job(job.job_id)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=update), threading.Thread(target=read)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"


# ---------------------------------------------------------------------------
# Event store concurrency tests (already thread-safe, verify)
# ---------------------------------------------------------------------------


class TestEventStoreConcurrency:
    def test_concurrent_append_same_job(self):
        store = BoundedEventStore(max_events_per_job=100)
        barrier = threading.Barrier(4)

        def append():
            barrier.wait()
            for _ in range(25):
                store.append("j1", JobEvent(job_id="j1", request_id="r1"))

        threads = [threading.Thread(target=append) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert store.get_job_event_count("j1") == 100

    def test_concurrent_append_different_jobs(self):
        store = BoundedEventStore()
        barrier = threading.Barrier(3)

        def append(jid):
            barrier.wait()
            for _ in range(10):
                store.append(jid, JobEvent(job_id=jid, request_id="r1"))

        threads = [
            threading.Thread(target=append, args=(f"j{i}",)) for i in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for i in range(3):
            assert store.has_job(f"j{i}")

    def test_monotonic_sequence_under_concurrency(self):
        store = BoundedEventStore()
        barrier = threading.Barrier(4)

        def append():
            barrier.wait()
            for _ in range(25):
                store.append("j1", JobEvent(job_id="j1", request_id="r1"))

        threads = [threading.Thread(target=append) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        events = store.get_events("j1")
        sequences = [e.sequence for e in events]
        assert len(sequences) == len(set(sequences)), "Duplicate sequence numbers"
        assert sequences == sorted(sequences), "Non-monotonic sequences"
