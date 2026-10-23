# SUPERVISOR_EVIDENCE.md — PR0169 IR-05

All evidence is local (`/tmp/ir05`, `/tmp/ir03`, `/tmp/bremen-ir01-fixtures`).
No AWS or App Runner call was made.

## Candidate route and supervision

- Opt-in: `BREMEN_CANDIDATE_SUBPROCESS_MODELS` (exact model ids) **and** a
  catalog entry carrying `runtime_release`. Unset/empty → legacy behavior.
- One fresh Worker process per invocation:
  `[<installed main python>, -m, bremen.ml_plugin.entrypoint, --release-dir,
  <release>, --job-dir, <job>]`, argv only, `shell=False`.
- Job directory 0700 per invocation; `request.json` staged, `input.h5` copied,
  `result.json` read and validated; directory removed in `finally`.
- Process group: `start_new_session=True`; timeout → SIGTERM to the group,
  bounded grace, then SIGKILL; wait/reap always.
- Capacity: one process-wide non-blocking semaphore; a second concurrent
  invocation fails with `candidate_capacity_exhausted`; released in `finally`.
- Result trust: regular file, size bound, JSON, protocol/identity/digest match,
  status shape; a nonzero exit after a claimed success is `PROTOCOL_ERROR`;
  stdout/stderr are diagnostics only (bounded and not a result channel).
- Environment: IR-04 `_restricted_environment` — no AWS_*, BOTO*, PYTHONPATH.
- Import boundary: `subprocess_runtime` never imports the ML plugin or model
  packages; the plugin is only an argv module string.

## Cold-cache registry/executor integration

Test class: `TestRegistryExecutorColdCacheIntegration`
(`tests/test_ir05_subprocess_runtime.py`).

Production wiring exercised: `get_descriptor_for_model` → real registry
factory → `executor.execute` → `SubprocessRuntime._invoke` →
`ReleaseCache.install(entry)`.

Observed in `test_cold_cache_candidate_execution_reaches_install`:

- cache starts cold (`read_ready(digest) is None`);
- `ReleaseCache.install` called twice (validate, predict) with the real catalog
  entry;
- the `InstalledRelease` returned by install is the object passed to the
  worker call;
- `descriptor.runtime` is `SubprocessRuntime` and `descriptor.model_ready` is
  `True`, so the executor does not short-circuit;
- worker operations `["validate", "predict"]`;
- projected result: `probability=0.7726940329943811`,
  `threshold_applied=0.3585907282566089`, `prediction=1`,
  overall status `completed`;
- `BremenRuntime` was patched to raise and was never invoked (no fallback).

Observed in `test_cold_install_failure_fails_safely_without_legacy`:

- `ReleaseCache.install` raises `ReleaseCacheError`;
- install attempted once, no worker spawn, no legacy call;
- request fails as `workflow_configuration_required` with the established safe
  message, not "Workflow unavailable — model not ready".

Readiness semantics: `model_ready()` means "configured and eligible to attempt
installation", not "READY cache entry exists".

## Typed error mapping

Each of the seven `bremen.worker.v1` codes maps deterministically onto the
existing `ModelRuntimeError` classes; details are attached when present and the
existing `descriptor.failure` projection is reused unchanged.

## Aramina failure parity

Unit tests: `TestAraminaFailureParity` (legacy exception vs candidate Worker
transport). Real end-to-end run: `/tmp/ir05/aramina_failure_parity.py`
(A1 release, `Nova_376.h5`, target `left`; legacy descriptor vs candidate
descriptor through `executor.execute`):

```
LEGACY    {"error": "ARAMINA_UNSUPPORTED_INPUT",
           "failure_stage": "preprocessing_contract",
           "preprocessing_diagnostic": {5-key dict}}
CANDIDATE {"error": "ARAMINA_UNSUPPORTED_INPUT",
           "failure_stage": "preprocessing_contract",
           "preprocessing_diagnostic": {5-key dict}}
PARITY True
```

The diagnostic remains a dict end-to-end:
`preprocessing_stage=worker_pipeline_execution`,
`preprocessing_exception_class=ValueError`,
`preprocessing_transformer=H5PoniGeometryCalculatorTransformer`,
`preprocessing_release=v0.1.7-beta`,
`preprocessing_reason_code=ARAMINA_PREPROCESSING_PIPELINE_EXECUTION_FAILED`.

Malformed/arbitrary details (unknown key, unknown code, unknown stage,
non-allowlisted diagnostic values, string diagnostic) project as
`ARAMINA_EXECUTION_FAILED` with no stage/diagnostic.

## WorkerError.details

Optional; JSON object with string keys; recursive JSON safety on encode and
decode (NaN/Infinity/arbitrary objects/non-string nested keys rejected);
unknown error fields still rejected; absent details is byte-compatible with the
previous shape. Result-size behavior unchanged.

Protocol suite: **261 passed** (was 250).

## Five-release supervisor parity

See `FIVE_RELEASE_PARITY.md` — real rebuilt releases, installed through the
real `ReleaseCache`, driven by the real `SubprocessRuntime` and a real Worker
process.

## Validation

| Command | Result |
|---|---|
| `python3 -m compileall -q src tests` | exit 0 |
| `pytest -q tests/test_ir05_subprocess_runtime.py` | 52 passed |
| `pytest -q tests/test_worker_protocol_contract.py` | 261 passed |
| targeted discovery/registry/contracts/worker/IR-04 | 539 passed |
| targeted runtime/Aramina/registry/jobs/report | 507 passed |
| IR-03 plugin tests | 59 passed |
| `BREMEN_IR03_RELEASES=/tmp/ir05/releases pytest -q tests/test_ir03_parity.py` | 21 passed |
| `pytest -q` | 4500 passed, 8 skipped, 40 warnings |
| `git diff --check` | exit 0 |
