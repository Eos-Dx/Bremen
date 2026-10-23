# IMPLEMENTATION_REPORT.md — PR0169 IR-05 supervised subprocess runtime

Status: implementation complete for the local IR-05 gate. Candidate route is
disabled by default; no model is ACTIVE; live AWS/App Runner work remains
out of scope.

## TASK COMPLETE

IR-05 adds one supervised candidate execution path behind the existing
`ModelRuntime` protocol:

```
platform configuration (BREMEN_CANDIDATE_SUBPROCESS_MODELS)
  + catalog entry with runtime_release
    -> registry factory builds SubprocessRuntime instead of the legacy runtime
      -> existing executor.execute / execute_model (unchanged)
        -> SubprocessRuntime._invoke
          -> ReleaseCache.install(entry)         (cold or warm)
            -> one fresh Worker process per invocation
              -> bremen.ml_plugin.entrypoint (argv, file protocol)
                -> result.json
          -> existing report projection (descriptor.project / descriptor.failure)
```

Nothing changes for a model that is not opted in. There is no legacy fallback
on the candidate path.

## FILES CHANGED

- `src/bremen/platform/runtime/subprocess_runtime.py` (new)
- `src/bremen/platform/runtime/registry.py` — candidate runtime selection only
- `src/bremen/platform/reports/runtime_projection.py` — allowlisted Aramina
  failure reconstruction from Worker details
- `src/bremen/contracts/worker_protocol.py` — additive `WorkerError.details`,
  `decode_model_requirements`
- `src/bremen/ml_plugin/inference.py` — transports structured Aramina failure
  details (dict diagnostic, never stringified)
- `tests/test_ir05_subprocess_runtime.py` — 52 tests
- `tests/test_worker_protocol_contract.py` — 261 tests
- `tests/test_ir03_standalone_runtime.py` — details field is optional/None
- `.project-memory/pr/0169-ir-05-supervised-subprocess-runtime/IMPLEMENTATION_REPORT.md`
- `.project-memory/pr/0169-ir-05-supervised-subprocess-runtime/SUPERVISOR_EVIDENCE.md`
- `.project-memory/pr/0169-ir-05-supervised-subprocess-runtime/FIVE_RELEASE_PARITY.md`

No executor, jobs service, scientific code, threshold, preprocessing, feature,
Docker, CI or IaC file was modified.

## COLD CACHE INTEGRATION

Test: `TestRegistryExecutorColdCacheIntegration` in
`tests/test_ir05_subprocess_runtime.py`
(`test_cold_cache_candidate_execution_reaches_install`,
`test_cold_install_failure_fails_safely_without_legacy`).

What is real in the test: `get_descriptor_for_model` → the actual registry
factory → `bremen.platform.runtime.executor.execute` → `SubprocessRuntime` →
`SubprocessRuntime._invoke`. Only two narrow boundaries are substituted:
`ReleaseCache.install` (the cache starts with no READY entry, and the test
records calls) and `_run_worker` (no subprocess spawn).

- ReleaseCache.install observed: yes — the test asserts
  `install_calls == [entry, entry]` (validate, then predict) and that the
  returned `InstalledRelease` is the one passed to the worker call.
- Executor short-circuit: none — `descriptor.model_ready is True` and both
  `validate` and `predict` reached the candidate runtime.
- Legacy fallback: none — `BremenRuntime.validate_model_input` /
  `predict_model` were patched to raise and were never called.
- Result reached the existing projection with exact B2 values
  (`0.7726940329943811`, `0.3585907282566089`, `1`).

Cold-install failure: `ReleaseCache.install` raises `ReleaseCacheError`; the
request fails as `workflow_configuration_required` with the existing safe
message "Workflow configuration required for multi-position input" — not the
executor's "Workflow unavailable — model not ready" short-circuit — no worker
spawn, no legacy call.

### Readiness semantics

`SubprocessRuntime.model_ready()` returns `is_candidate_enabled_for(entry)`
(platform allowlist + valid `runtime_release`). It means "configured and
eligible to attempt installation", not "already READY". The actual cache
resolution happens inside `_invoke` → `ReleaseCache.install`, so an empty cache
never blocks the candidate route.

## ARAMINA FAILURE CONTRACT

Worker transport (`_error_details` in `src/bremen/ml_plugin/inference.py`) now
preserves the structured diagnostic:

```json
{
  "aramina_error_code": "ARAMINA_UNSUPPORTED_INPUT",
  "failure_stage": "preprocessing_contract",
  "preprocessing_diagnostic": {
    "preprocessing_stage": "worker_pipeline_execution",
    "preprocessing_exception_class": "ValueError",
    "preprocessing_transformer": "H5PoniGeometryCalculatorTransformer",
    "preprocessing_release": "v0.1.7-beta",
    "preprocessing_reason_code":
      "ARAMINA_PREPROCESSING_PIPELINE_EXECUTION_FAILED"
  }
}
```

- `preprocessing_diagnostic` stays a dict (never coerced to `str`).
- Non-`UNSUPPORTED_INPUT` Aramina codes transport only
  `aramina_error_code`.
- `SubprocessRuntime` does not import Aramina code; it only attaches
  `WorkerError.details` to the mapped `ModelRuntimeError`.
- `aramina_failure` revalidates details against the existing public vocabulary
  (`_SAFE_FAILURES`, `FAILURE_STAGES`, `safe_preprocessing_diagnostic`) and
  only then rebuilds `AraminaWorkflowError`. Malformed, extra-key, wrong-type
  or non-allowlisted details produce the existing generic
  `ARAMINA_EXECUTION_FAILED` with no stage/diagnostic.

Legacy vs candidate parity (unit tests `TestAraminaFailureParity`, plus a real
end-to-end run):

| Case | error | failure_stage | preprocessing_diagnostic |
|---|---|---|---|
| invalid request | `ARAMINA_INVALID_REQUEST` | `None` | `None` — identical |
| unsupported input (`target_side_contract`) | `ARAMINA_UNSUPPORTED_INPUT` | `target_side_contract` | `None` — identical |
| preprocessing failure | `ARAMINA_UNSUPPORTED_INPUT` | `preprocessing_contract` | full dict — identical (legacy and candidate both produced the same 5-key dict in the real run) |
| `ARAMINA_MODEL_IDENTITY_MISMATCH` | identical | `None` | `None` |
| `ARAMINA_UNSUPPORTED_ARTIFACT` | identical | `None` | `None` |
| malformed/arbitrary details | `ARAMINA_EXECUTION_FAILED` | `None` | `None` |

## WORKER PROTOCOL DETAILS

`WorkerError.details: Mapping[str, Any] | None`, optional, transported through
`encode_worker_result` and validated by `validate_worker_result`:

- must be a JSON object, string keys only;
- recursive `reject_non_json_safe` (NaN/Infinity, bytes, arbitrary objects,
  non-string nested keys all rejected);
- unknown error-object fields (e.g. `traceback`, `path`, `stdout`) still
  rejected;
- absent `details` encodes/round-trips exactly as before;
- result-size behavior is unchanged (`MAX_RESULT_JSON_BYTES` = 1 MiB).

Tests: `TestWorkerErrorDetails` (11 cases) in
`tests/test_worker_protocol_contract.py` — current count **261** (was 250).

## SUPERVISION / SECURITY

- argv-only `Popen`, `start_new_session=True`, bounded timeout, process-group
  SIGTERM then SIGKILL, wait/reap.
- One process-wide non-blocking semaphore (one scientific invocation).
- Per-invocation 0700 job directory with fixed
  `request.json`/`input.h5`/`result.json`; input copied; symlinked result
  rejected; cleanup in `finally`.
- Child environment reuses IR-04's `_restricted_environment` (no AWS/BOTO/
  PYTHONPATH).
- Result regular-file/size/JSON/protocol/identity checks; nonzero exit after a
  claimed success is `PROTOCOL_ERROR`.
- Candidate route disabled unless an exact model_id is allowlisted and the
  entry carries `runtime_release`; no request data can influence it.

## PLUGIN / RELEASE REBUILD

`src/bremen/ml_plugin/inference.py` changed, so the plugin wheel and all five
releases were rebuilt with the existing IR-03 build path.

- OLD plugin wheel SHA-256:
  `029af6c73238cd83d31f1dea31fa52cbbd69f4236e14ba317f076e04affa7e82`
- NEW plugin wheel SHA-256:
  `f4c4bf1ee52b7002b49598a1d40200517469b97e9f8f6809761949595d23d626`
  (independently computed from the built wheel; size 113597 bytes)

| Slot | release_id | manifest SHA-256 | main wheels | aux wheels | golden files |
|---|---|---|---|---|---|
| A1 | `aramina-target-breast-risk-0-2-12-beta-9bb9111` | `02be0ce3117080bbbf998a81ffaeff993938aaeb6fd2cc98c93ee730f7532b4c` | 13 | 54 | 2 |
| A2 | `aramina-target-breast-risk-0-2-13-beta-f5e4a04` | `7ebd66806b7924202d68d7d74265784300b8dacc64b6df98bb8d4e2984fd4e49` | 13 | 54 | 2 |
| B1 | `bremen-mri-triage-logreg-v0-1` | `678edd64ddb35a2ba26e92f9bd804ab350303e458b4d152a5a4498ab812bc8ad` | 13 | 0 | 3 |
| B2 | `bremen-paper-reference-v0-2-0` | `d6df5c67bee4c9beadecd75fa316883fdcbfed81532ccea298d14f0bdc312321` | 13 | 54 | 2 |
| B3 | `bremen-v0-2-0-symmetry-candidate` | `596f8e10c065ae8d7c99201274c8559e8d158bff2393f637d47e8755611887eb` | 13 | 54 | 2 |

Model artifacts, checksums, thresholds, locks and preprocessing versions are
unchanged; only derived plugin/file hashes changed.

## VALIDATION RESULTS

Environment: `/tmp/bremen-ir01-exec-venv` (Python 3.13.12). New release root:
`/tmp/ir05/releases`.

| Command | Result |
|---|---|
| `python3 -m compileall -q src tests` | exit 0 |
| `pytest -q tests/test_ir05_subprocess_runtime.py` | **52 passed** |
| `pytest -q tests/test_worker_protocol_contract.py` | **261 passed** |
| `pytest -q tests/test_s3_model_discovery.py tests/test_model_registry.py tests/test_inference_release_contract.py tests/test_worker_protocol_contract.py tests/test_ir04_release_cache.py` | **539 passed** |
| `pytest -q` targeted runtime/Aramina/registry/jobs/report set | **507 passed** |
| `pytest -q tests/test_ir03_plugin_wheel.py tests/test_ir03_standalone_runtime.py tests/test_ir03_plugin_import_boundary.py` | **59 passed** |
| `pytest -q tests/test_ir04_release_cache.py` | 65 passed (included above) |
| `BREMEN_IR03_RELEASES=/tmp/ir05/releases pytest -q tests/test_ir03_parity.py` | **21 passed** |
| `pytest -q` | **4500 passed, 8 skipped, 40 warnings** |
| `git diff --check` | exit 0 |
| `git status --short` | IR-05 source/test/project-memory changes only |
| `git diff --stat` | see final report |

## LIVE S3 / APP RUNNER

Not run. Local evidence only; no AWS or App Runner calls were made.

## WARNINGS

- Candidate route remains disabled by default and is not activated in this PR.
- `on_features` is a no-op on the candidate path (the protocol carries no
  feature-stage event).
- Release installation happens inside the first invocation for a cold cache;
  the per-invocation timeout does not cover installation.
- Exact float equality follows IR-03 frozen parity evidence.
- `matador_raw` remains an unsupported plugin layout.
- No App Runner verification (IR-06) and no lifecycle/activation work.

## REMAINING BLOCKERS

None for the three received blockers.

## NEXT REQUIRED ACTION

Repeat precommit review.
