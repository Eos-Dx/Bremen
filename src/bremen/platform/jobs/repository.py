"""Process-local repository state and locks; survives application module reload."""

from bremen.platform.jobs.models import AnalysisJob
import threading
import bremen
from bremen.platform.events.store import BoundedEventStore

_STORE_KEY = "_bremen_workspace_event_store"
_JOBS_KEY = "_bremen_workspace_jobs"
_PROVIDERS_KEY = "_bremen_workspace_report_providers"
_INIT_LOCK_KEY = "_bremen_workspace_init_lock"
_JOBS_LOCK_KEY = "_bremen_workspace_jobs_lock"
_PROVIDERS_LOCK_KEY = "_bremen_workspace_providers_lock"
_UPLOADS_KEY = "_bremen_workspace_staged_uploads"
_UPLOADS_LOCK_KEY = "_bremen_workspace_uploads_lock"


def _get_package_lock(key: str) -> threading.Lock:
    """Return (or create and store) a lock on the bremen package.

    The lock is stored on the package so it survives module reload.
    Uses a simple pattern since the inner setattr is unlikely to race
    fatally for locks (two locks are both valid), but adjacent to the
    double-checked singleton pattern for data objects.
    """
    lock = getattr(bremen, key, None)
    if lock is None:
        lock = threading.Lock()
        setattr(bremen, key, lock)
    return lock


def _get_or_create_store():
    s = getattr(bremen, _STORE_KEY, None)
    if s is not None:
        return s
    init_lock = _get_package_lock(_INIT_LOCK_KEY)
    with init_lock:
        s = getattr(bremen, _STORE_KEY, None)
        if s is not None:
            return s
        s = BoundedEventStore()
        setattr(bremen, _STORE_KEY, s)
        return s


def _get_or_create_jobs():
    j = getattr(bremen, _JOBS_KEY, None)
    if j is not None:
        return j
    init_lock = _get_package_lock(_INIT_LOCK_KEY)
    with init_lock:
        j = getattr(bremen, _JOBS_KEY, None)
        if j is not None:
            return j
        j = {}
        setattr(bremen, _JOBS_KEY, j)
        return j


def _get_or_create_providers():
    p = getattr(bremen, _PROVIDERS_KEY, None)
    if p is not None:
        return p
    init_lock = _get_package_lock(_INIT_LOCK_KEY)
    with init_lock:
        p = getattr(bremen, _PROVIDERS_KEY, None)
        if p is not None:
            return p
        p = {}
        setattr(bremen, _PROVIDERS_KEY, p)
        return p


def _get_or_create_uploads():
    u = getattr(bremen, _UPLOADS_KEY, None)
    if u is not None:
        return u
    init_lock = _get_package_lock(_INIT_LOCK_KEY)
    with init_lock:
        u = getattr(bremen, _UPLOADS_KEY, None)
        if u is not None:
            return u
        u = {}
        setattr(bremen, _UPLOADS_KEY, u)
        return u


# Module-level references that point to persistent bremen-package objects
_event_store = _get_or_create_store()
_jobs = _get_or_create_jobs()
_report_providers = _get_or_create_providers()
_staged_uploads = _get_or_create_uploads()

# Thread-safety locks for shared mutable state
_jobs_lock = _get_package_lock(_JOBS_LOCK_KEY)
_providers_lock = _get_package_lock(_PROVIDERS_LOCK_KEY)
_uploads_lock = _get_package_lock(_UPLOADS_LOCK_KEY)


# ---------------------------------------------------------------------------


def get_analysis_job(job_id: str) -> AnalysisJob | None:
    """Return an analysis job by ID, or ``None``."""
    with _jobs_lock:
        return _jobs.get(job_id)
