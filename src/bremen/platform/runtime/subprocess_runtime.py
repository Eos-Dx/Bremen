"""IR-05 supervised subprocess Worker runtime proxy.

Implements ``bremen.contracts.model_runtime.ModelRuntime`` (the SAME
structural protocol ``BremenRuntime``/``AraminaRuntime`` already satisfy) by
driving an IR-04 READY release through one fresh ``bremen.worker.v1`` Worker
subprocess per invocation, instead of running the model package in-process.

Because this class satisfies the existing ``ModelRuntime`` protocol, swapping
it in for the legacy runtime (see ``bremen.platform.runtime.registry``)
requires no change to ``execute_model``/``execute`` in ``executor.py``: the
existing report projection (``descriptor.project``/``descriptor.failure``),
job lifecycle and event emission are reused unchanged.

Harness/plugin boundary (HARD RULE 10 / architecture gate): this module
never imports ``bremen.ml_plugin`` or any model-specific release plugin
module. It only knows:

- contracts (``bremen.contracts.worker_protocol``, ``bremen.contracts.model_runtime``)
- registry metadata (the opaque catalog ``entry`` object)
- the verified manifest and ``InstalledRelease`` paths from
  ``bremen.platform.models.release_cache``
- plain subprocess/process-group mechanics

The plugin itself is only ever reached as a string in an ``argv`` list
(``python -m bremen.ml_plugin.entrypoint ...``), spawned as a child process —
never imported into this process.

Candidate route (disabled by default): see ``is_candidate_enabled_for``.
Nothing here changes behavior for a model unless that model's id is listed in
``BREMEN_CANDIDATE_SUBPROCESS_MODELS`` (platform configuration, not user
request data) *and* its catalog entry carries a valid ``runtime_release``.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Mapping

from bremen.contracts.model_runtime import (
    ModelConfigurationRequiredError,
    ModelInferenceFailedError,
    ModelInput,
    ModelInputInvalidError,
    ModelPreprocessingFailedError,
    ModelRequirements,
    ModelRuntimeError,
    ModelValidation,
    RuntimePrediction,
)
from bremen.contracts.worker_protocol import (
    MAX_DIAGNOSTIC_BYTES,
    MAX_RESULT_JSON_BYTES,
    PROTOCOL_ID,
    STAGED_INPUT_FILENAME,
    STAGED_REQUEST_FILENAME,
    STAGED_RESULT_FILENAME,
    WorkerError,
    WorkerProtocolError,
    WorkerRequest,
    WorkerResult,
    decode_model_requirements,
    decode_model_validation,
    decode_runtime_prediction,
    encode_worker_request,
    validate_result_matches_request,
    validate_worker_request,
    validate_worker_result,
)
from bremen.platform.models.release_cache import (
    InstalledRelease,
    ReleaseCache,
    ReleaseCacheError,
    _restricted_environment,  # reuse the IR-04 security principle, not a copy
)

__all__ = [
    "DEFAULT_INVOCATION_TIMEOUT_SECONDS",
    "DEFAULT_TERMINATION_GRACE_SECONDS",
    "ENV_CANDIDATE_MODELS",
    "ENV_INVOCATION_TIMEOUT",
    "SubprocessRuntime",
    "candidate_model_ids",
    "is_candidate_enabled_for",
]

# ---------------------------------------------------------------------------
# Candidate opt-in (disabled by default) — platform configuration only.
# ---------------------------------------------------------------------------

#: Comma-separated allowlist of model_ids authorized to run through the
#: candidate subprocess route. Empty/unset -> no model uses it (legacy
#: in-process execution remains the default for everything). This is read
#: from process environment only — never from request/API payload data.
ENV_CANDIDATE_MODELS = "BREMEN_CANDIDATE_SUBPROCESS_MODELS"

#: Per-invocation deadline. Installation has its own IR-04 deadlines; this
#: is strictly the Worker-invocation deadline IR-05 owns.
ENV_INVOCATION_TIMEOUT = "BREMEN_CANDIDATE_INVOCATION_TIMEOUT_SECONDS"

DEFAULT_INVOCATION_TIMEOUT_SECONDS = 120
DEFAULT_TERMINATION_GRACE_SECONDS = 5

#: The verified release entrypoint invocation convention IR-04 already
#: established and smoke-tested (``ReleaseCache._run_entrypoint``). IR-05
#: reuses it exactly rather than inventing a second launch convention.
_ENTRYPOINT_MODULE = "bremen.ml_plugin.entrypoint"

#: "At most one scientific invocation per application instance" (IR-05
#: normative target). One process-wide, non-blocking semaphore shared by
#: every SubprocessRuntime instance in this process — not per-model, not
#: per-instance. ``ThreadPoolExecutor(max_workers=2)`` elsewhere in the
#: platform is not permission for two concurrent scientific Workers.
_CANDIDATE_SEMAPHORE = threading.Semaphore(1)


def candidate_model_ids() -> frozenset[str]:
    """The platform-configured allowlist of model_ids for candidate execution."""
    raw = os.environ.get(ENV_CANDIDATE_MODELS, "")
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def is_candidate_enabled_for(entry: Any) -> bool:
    """True only when ALL of: the model is in the platform allowlist, and
    its catalog entry carries a valid (non-empty) ``runtime_release``.

    No per-request signal can influence this — it consults only the
    process environment and the already-validated catalog entry.
    """
    model_id = getattr(entry, "model_id", None)
    if not isinstance(model_id, str) or not model_id or model_id not in candidate_model_ids():
        return False
    getter = getattr(entry, "get_runtime_release", None)
    if not callable(getter):
        return False
    reference = getter()
    return isinstance(reference, dict) and bool(reference)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


_DEFAULT_CACHE: ReleaseCache | None = None


def _default_release_cache() -> ReleaseCache:
    global _DEFAULT_CACHE
    if _DEFAULT_CACHE is None:
        _DEFAULT_CACHE = ReleaseCache()
    return _DEFAULT_CACHE


# ---------------------------------------------------------------------------
# Typed-error -> existing ModelRuntimeError mapping
# ---------------------------------------------------------------------------

#: Maps each of the seven ``bremen.worker.v1`` typed error codes onto one of
#: the FIVE existing ``ModelRuntimeError`` categories already consumed by
#: ``bremen_failure``/``aramina_failure`` (``bremen.contracts.model_runtime``
#: is not modified by IR-05 — there is no sixth/seventh category to add).
#: This preserves the existing external failure SHAPE; it does not claim to
#: reproduce every historical in-process error MESSAGE byte-for-byte for
#: every typed code (see IMPLEMENTATION_REPORT.md "Error mapping" for the
#: documented, deliberate simplifications).
_ERROR_CODE_TO_EXCEPTION = {
    "INPUT_INVALID": ModelInputInvalidError,
    "QC_FAILED": ModelPreprocessingFailedError,
    "MODEL_NOT_READY": ModelConfigurationRequiredError,
    "INFERENCE_FAILED": ModelInferenceFailedError,
    "TIMEOUT": ModelInferenceFailedError,
    "RESOURCE_EXHAUSTED": ModelInferenceFailedError,
    "PROTOCOL_ERROR": ModelPreprocessingFailedError,
}


def _map_worker_error(error: WorkerError) -> ModelRuntimeError:
    """Map a Worker error to the appropriate runtime exception.

    For Aramina failures with transported details, attach them to the
    exception so the aramina_failure projection can reconstruct the full
    error diagnosis (code, failure_stage, preprocessing_diagnostic).
    """
    exception_cls = _ERROR_CODE_TO_EXCEPTION.get(error.code, ModelPreprocessingFailedError)
    exc = exception_cls(error.safe_reason)

    # Attach details if present (IR-05 candidate path Aramina failures).
    # The aramina_failure projection will check for this attribute and
    # reconstruct the full AraminaWorkflowError if needed.
    if error.details:
        exc.details = error.details  # type: ignore[attr-defined]

    return exc


# ---------------------------------------------------------------------------
# The runtime
# ---------------------------------------------------------------------------


class SubprocessRuntime:
    """Drives one IR-04 READY release through the ``bremen.worker.v1``
    file protocol for ``requirements``/``validate``/``predict``.

    Satisfies ``bremen.contracts.model_runtime.ModelRuntime`` structurally.
    ``requires_raw_container = True`` so ``bremen_descriptor`` routes the
    raw staged H5 path directly (no legacy canonical normalization) when
    this runtime is used for Bremen; Aramina's descriptor always normalizes
    canonical input regardless of runtime (unchanged), and this runtime
    forwards only the small JSON-safe ``CanonicalMetadata`` provenance
    fields from it — never the measurement arrays.
    """

    requires_raw_container = True

    def __init__(
        self,
        *,
        entry: Any,
        release_cache: ReleaseCache | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self._entry = entry
        self._cache = release_cache or _default_release_cache()
        self._timeout_seconds = timeout_seconds or _env_int(
            ENV_INVOCATION_TIMEOUT, DEFAULT_INVOCATION_TIMEOUT_SECONDS
        )

    # -- ModelRuntime protocol -------------------------------------------

    def model_ready(self) -> bool:
        """For candidate runtime: return True if candidate is enabled (may
        attempt installation), False otherwise.

        This is NOT "release is already on disk" but "runtime is configured
        and may attempt installation". The actual cache-warm check happens
        during _invoke() -> ReleaseCache.install(), which can install a cold
        release if it exists in the configured location.

        This allows the executor to schedule the invocation; the _invoke()
        call will then attempt ReleaseCache.install() and fail with a clear
        error if the release is truly unavailable (not just uncached).
        """
        return is_candidate_enabled_for(self._entry)

    def model_requirements(self) -> ModelRequirements:
        result = self._invoke(operation="requirements", model_input=None)
        try:
            return decode_model_requirements(result.payload)
        except WorkerProtocolError:
            raise ModelPreprocessingFailedError("worker_result_invalid") from None

    def validate_model_input(self, model_input: ModelInput) -> ModelValidation:
        result = self._invoke(operation="validate", model_input=model_input)
        try:
            return decode_model_validation(result.payload)
        except WorkerProtocolError:
            raise ModelPreprocessingFailedError("worker_result_invalid") from None

    def predict_model(
        self, model_input: ModelInput, *, on_features=None,
    ) -> RuntimePrediction:
        # on_features: the bremen.worker.v1 result.json carries only a
        # single terminal payload today — no structured feature-stage
        # event exists in the protocol to translate (see
        # IMPLEMENTATION_REPORT.md "Existing projection / events"). Per the
        # task's own instruction, no new event subsystem is invented here;
        # on_features is accepted for protocol compatibility and is a no-op.
        result = self._invoke(operation="predict", model_input=model_input)
        try:
            return decode_runtime_prediction(result.payload)
        except WorkerProtocolError:
            raise ModelPreprocessingFailedError("worker_result_invalid") from None

    # -- internals ---------------------------------------------------------

    def _invoke(self, *, operation: str, model_input: ModelInput | None) -> WorkerResult:
        try:
            installed = self._cache.install(self._entry)
        except ReleaseCacheError:
            raise ModelConfigurationRequiredError("candidate_release_not_ready") from None

        acquired = _CANDIDATE_SEMAPHORE.acquire(blocking=False)
        if not acquired:
            raise ModelInferenceFailedError("candidate_capacity_exhausted")
        try:
            result = _run_worker(
                installed,
                operation=operation,
                model_input=model_input,
                timeout_seconds=self._timeout_seconds,
            )
        finally:
            _CANDIDATE_SEMAPHORE.release()

        if result.status == "ok":
            return result
        raise _map_worker_error(result.error)


# ---------------------------------------------------------------------------
# Job directory / request-response plumbing
# ---------------------------------------------------------------------------


def _build_worker_request(installed: InstalledRelease, *, operation: str, model_input) -> WorkerRequest:
    payload: dict[str, Any] = {}
    if operation in ("validate", "predict"):
        if model_input is None:
            raise ModelInputInvalidError("model_input_required")
        payload = {
            "workflow_id": model_input.workflow_id,
            "patient_id": model_input.patient_id or "",
            "target_side": model_input.target_side or "",
            "container_path": STAGED_INPUT_FILENAME,
            "parameters": dict(model_input.parameters or {}),
        }
        canonical = getattr(model_input, "canonical", None)
        if canonical is not None:
            payload["canonical_metadata"] = {
                "source_layout": canonical.source_layout,
                "source_layout_version": canonical.source_layout_version,
                "source_checksum": canonical.source_checksum,
                "calibration_provenance": canonical.calibration_provenance,
                "calibration_metadata": dict(
                    getattr(canonical, "calibration_metadata", None) or {}
                ),
            }
    raw = {
        "protocol": PROTOCOL_ID,
        "request_id": f"req-{uuid.uuid4().hex}",
        "operation": operation,
        "model_id": installed.model_id,
        "release_digest": installed.digest,
        "payload": payload,
    }
    return validate_worker_request(raw)


def _stage_input(model_input, job_dir: str) -> None:
    source = model_input.container_path
    if not source or not os.path.isfile(source):
        raise ModelInputInvalidError("container_path_unavailable")
    destination = os.path.join(job_dir, STAGED_INPUT_FILENAME)
    shutil.copyfile(source, destination)
    with contextlib.suppress(OSError):
        os.chmod(destination, 0o600)


def _error_result(request: WorkerRequest, code: str, reason: str) -> WorkerResult:
    return WorkerResult(
        protocol=request.protocol,
        request_id=request.request_id,
        operation=request.operation,
        model_id=request.model_id,
        release_digest=request.release_digest,
        status="error",
        error=WorkerError(code=code, safe_reason=reason),
    )


def _truncate_diagnostic(text: str | None) -> str:
    if not text:
        return ""
    encoded = text.encode("utf-8", "replace")
    if len(encoded) <= MAX_DIAGNOSTIC_BYTES:
        return text
    return encoded[:MAX_DIAGNOSTIC_BYTES].decode("utf-8", "ignore")


@dataclass(frozen=True)
class _Completed:
    returncode: int
    stdout: str
    stderr: str


def _terminate_process_group(pid: int, grace_seconds: float) -> None:
    """Graceful SIGTERM to the whole process group, then SIGKILL after a
    bounded grace period. Covers Worker-spawned descendants, not only the
    direct child, because the Worker was started as its own session/group
    leader (``start_new_session=True``).
    """
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, signal.SIGTERM)
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        try:
            os.killpg(pid, 0)  # alive check only; no signal delivered
        except (ProcessLookupError, PermissionError):
            # PermissionError can occur once the group leader has already
            # exited and its pid/pgid was reclaimed; treat both the same as
            # "no longer observable" rather than retrying forever.
            return
        time.sleep(0.05)
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, signal.SIGKILL)


def _spawn_and_supervise(
    argv: list[str], *, cwd: str, timeout_seconds: float, grace_seconds: float,
) -> tuple[_Completed | None, bool]:
    """Spawn the Worker as its own process-group leader and enforce the
    invocation deadline. Returns ``(completed, timed_out)``; exactly one of
    the two carries the outcome.

    Fails closed on non-POSIX hosts rather than silently losing process-group
    supervision (HARD RULE: "unsupported process-group semantics should fail
    closed").
    """
    if os.name != "posix":
        raise ModelConfigurationRequiredError("unsupported_platform")

    process = subprocess.Popen(  # noqa: S603 - argv is built entirely from
        # verified release/registry data; never a shell, never a
        # user-supplied executable or module (see _build_worker_request /
        # InstalledRelease — no API/request payload can reach this argv).
        argv,
        cwd=cwd,
        env=_restricted_environment(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout_data, stderr_data = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        _terminate_process_group(process.pid, grace_seconds)
        with contextlib.suppress(Exception):
            process.communicate(timeout=grace_seconds + 2)
        with contextlib.suppress(Exception):
            process.wait(timeout=1)
        return None, True
    return (
        _Completed(
            returncode=process.returncode,
            stdout=_truncate_diagnostic(stdout_data),
            stderr=_truncate_diagnostic(stderr_data),
        ),
        False,
    )


def _read_and_validate_result(
    job_dir: str, request: WorkerRequest, returncode: int,
) -> WorkerResult:
    result_path = os.path.join(job_dir, STAGED_RESULT_FILENAME)
    if not os.path.isfile(result_path) or os.path.islink(result_path):
        return _error_result(request, "PROTOCOL_ERROR", "worker_result_missing")
    try:
        size = os.path.getsize(result_path)
    except OSError:
        return _error_result(request, "PROTOCOL_ERROR", "worker_result_missing")
    if size > MAX_RESULT_JSON_BYTES:
        return _error_result(request, "PROTOCOL_ERROR", "worker_result_oversized")
    try:
        with open(result_path, "r", encoding="utf-8") as stream:
            raw = json.load(stream)
    except Exception:
        return _error_result(request, "PROTOCOL_ERROR", "worker_result_malformed")
    try:
        result = validate_worker_result(raw)
        validate_result_matches_request(request, result)
    except WorkerProtocolError:
        return _error_result(request, "PROTOCOL_ERROR", "worker_result_invalid")
    if returncode != 0:
        # A claimed success is never trusted unless the process also exited
        # cleanly (HARD RULE: success requires BOTH a valid result and a
        # clean exit).
        return _error_result(request, "PROTOCOL_ERROR", "worker_exit_nonzero")
    return result


def _entrypoint_argv(installed: InstalledRelease, job_dir: str) -> list[str]:
    """The verified release entrypoint invocation (IR-04's own
    ``ReleaseCache._run_entrypoint`` convention, reused exactly). A separate
    function only so tests can substitute a standalone fixture script
    without needing the spawned process to resolve ``-m`` module imports
    through the deliberately-stripped child ``PYTHONPATH`` — production
    behavior/argv is identical either way.
    """
    return [
        installed.main_python, "-m", _ENTRYPOINT_MODULE,
        "--release-dir", installed.release_dir, "--job-dir", job_dir,
    ]


def _run_worker(
    installed: InstalledRelease,
    *,
    operation: str,
    model_input,
    timeout_seconds: float,
    grace_seconds: float = DEFAULT_TERMINATION_GRACE_SECONDS,
) -> WorkerResult:
    job_dir = tempfile.mkdtemp(prefix="bremen-worker-")
    with contextlib.suppress(OSError):
        os.chmod(job_dir, 0o700)
    try:
        request = _build_worker_request(installed, operation=operation, model_input=model_input)
        encoded = encode_worker_request(request)
        with open(os.path.join(job_dir, STAGED_REQUEST_FILENAME), "w", encoding="utf-8") as stream:
            stream.write(encoded)
        if operation in ("validate", "predict"):
            _stage_input(model_input, job_dir)

        argv = _entrypoint_argv(installed, job_dir)
        completed, timed_out = _spawn_and_supervise(
            argv, cwd=job_dir, timeout_seconds=timeout_seconds, grace_seconds=grace_seconds,
        )
        if timed_out:
            return _error_result(request, "TIMEOUT", "worker_invocation_timeout")
        return _read_and_validate_result(job_dir, request, completed.returncode)
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)
