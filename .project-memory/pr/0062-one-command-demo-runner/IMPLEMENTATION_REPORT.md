# IMPLEMENTATION REPORT — PR 0062 One-command Bremen Demo Runner

**Branch**: `0062-one-command-demo-runner`
**Plan**: `.project-memory/pr/0062-one-command-demo-runner/PLAN.md`
**Plan Review**: `reviews/plan-review.yml` — verdict `approve`
**HEAD**: `c4ea09072869035dddefb9ede4db894384d621fa`

## FILES CHANGED

| File | Status | Lines |
|------|--------|-------|
| `src/bremen/demo_run.py` | NEW | 250 |
| `tests/test_bremen_demo_run.py` | NEW | 558 |
| `src/bremen/__main__.py` | MODIFIED | +52/-1 |
| `tests/test_bremen_cli_entrypoint.py` | MODIFIED | +40/-0 |

**Total**: 2 new files, 2 modified files.

All files listed in PLAN.md "Allowed implementation files" section.

## ONE-COMMAND DEMO SUMMARY

`python -m bremen demo-run` is implemented as a single command that:

1. Starts a local Bremen HTTP service on `127.0.0.1` with an ephemeral (OS-assigned) port
2. Waits for the `/health` endpoint to respond with HTTP 200 (bounded polling, configurable timeout)
3. Runs the existing PR0060 `demo-smoke` path (`run_demo_smoke()`) against the local service
4. Produces the PR0061 evidence bundle in the output
5. Shuts down the service cleanly in a `finally` block
6. Prints JSON output + human-readable summary

Supported CLI flags:
- `--base-url URL` — use an already-running service (skip local server start)
- `--timeout N` — timeout in seconds (default 30)
- `--skip-prediction` — skip the prediction check

The module `src/bremen/demo_run.py` is stdlib-only (250 lines) with no new dependencies.

## SERVER LIFECYCLE SUMMARY

- **Host**: Hardcoded to `127.0.0.1` (localhost only)
- **Port**: Ephemeral via `socket.bind(("127.0.0.1", 0))` — no fixed-port conflicts
- **Server startup**: Reuses `_make_handler(load_model=True)` from `server.py` — same pattern as existing tests
- **Synthetic model**: Loaded via existing `_load_synthetic_model()` — creates temp file, `joblib.dump()`, `ModelState.load_at_startup()`
- **Health wait**: `_wait_for_health()` — bounded polling with configurable timeout and 0.5s interval
- **Cleanup**: `server.shutdown()` + `thread.join(timeout=5)` in `finally` block — guaranteed cleanup
- **Failure output**: Controlled error dict with `technical_demo_only: True`, `status: "fail"`, error message, and warnings

## DEMO-SMOKE / EVIDENCE REUSE SUMMARY

- `run_demo()` calls `run_demo_smoke()` from `demo_smoke.py` — no duplicated smoke logic
- Evidence bundle is included automatically via the existing `demo_smoke.py` → `build_demo_evidence_bundle()` call
- `--skip-prediction` passes through to `run_demo_smoke()`
- `--base-url` override directs to `run_demo_smoke()` with the provided URL, skipping local server start
- All existing demo-smoke and demo-evidence tests continue to pass unchanged

## PRODUCT-OWNER DEMO VALUE SUMMARY

The single command `python -m bremen demo-run` enables this demo story:

1. **One command starts local Bremen service** — no manual server startup
2. **One command runs smoke/evidence** — health, model/version, prediction checks all run automatically
3. **No manual steps** — ephemeral port, automatic health wait, automatic shutdown
4. **Output is stable, JSON-serializable, and understandable** — JSON + human-readable summary
5. **Evidence bundle is included** — all PR0061 evidence fields present
6. **`technical_demo_only` is clear** — present at top level and in evidence
7. **`request_id`/status/warnings are visible** — propagated throughout

This completes the demo trilogy:
- **PR0060**: `demo-smoke` — check a running service
- **PR0061**: `demo_evidence.py` — evidence bundle contract
- **PR0062**: `demo-run` — one-command local demo

## OUTPUT CONTRACT SUMMARY

Output from `run_demo()` includes all existing `run_demo_smoke()` fields plus:
- `technical_demo_only: True`
- `base_url` — the local service URL
- `request_id` — UUID generated per run
- `checks` — health/model_version/prediction pass/fail
- `health`, `model_version`, `prediction` — individual check results
- `warnings` — list of warning strings
- `status` — overall `"pass"`, `"partial"`, or `"fail"`
- `timestamp` — ISO-8601 UTC
- `evidence` — PR0061 evidence bundle with `technical_demo_only`, `product`, `product_question`, `disclaimer`, `evidence_version`, `scenario_id`, `safety_notes`, and optional fields

On startup failure: returns `{"technical_demo_only": True, "status": "fail", "base_url": ..., "error": ..., "checks": {"server_startup": "fail"}, "warnings": [...], "timestamp": ...}`

## SAFETY BOUNDARY SUMMARY

| Boundary | Status | Evidence |
|----------|--------|---------|
| No Aramis dependency or benchmark | ✓ | Zero Aramis strings in `demo_run.py`. Validation grep confirms `demo_run.py` has no matches. |
| No clinical diagnosis/replacement claims | ✓ | `demo_run.py` only has the safety header comment (no clinical claims). |
| No unsafe model deserialization | ✓ | Uses existing `_load_synthetic_model()` — no new `joblib.load()` or `pickle.load()`. |
| No H5 reads/writes | ✓ | No `.h5`, `.hdf5`, or `h5py` in `demo_run.py` or `demo_evidence.py`. |
| No AWS/S3/network calls | ✓ | Only stdlib `urllib.request` to localhost. No `boto3`, `requests`, `httpx` in scope. |
| No new dependencies | ✓ | Stdlib-only module. No changes to `requirements.txt` or `pyproject.toml`. |
| No deployment mutation | ✓ | No Terraform, Docker, GitHub Actions, or infra changes. |
| No React/frontend | ✓ | No `frontend/**`, `web/**`, `ui/**`, or package-manager files changed. |
| No docs/ROADMAP changes | ✓ | Docs and ROADMAP unchanged. |
| No real patient data | ✓ | All feature values are synthetic. No patient identifiers. |
| No H5/model/tfstate artifacts | ✓ | No artifact files in diff. |
| No git mutation commands | ✓ | No `git add`, `git commit`, `git push`, or any mutating commands executed. |

## TESTS RUN

| Test File | Tests | Result |
|-----------|-------|--------|
| `test_bremen_demo_run.py` | 37 | ✓ All passed |
| `test_bremen_demo_smoke.py` | 25 | ✓ All passed |
| `test_bremen_demo_evidence.py` | 63 | ✓ All passed |
| `test_bremen_api_server.py` | 28 | ✓ All passed |
| `test_bremen_api_skeleton.py` | 51 | ✓ All passed |
| `test_bremen_cli_entrypoint.py` | 23 | ✓ All passed |
| `test_bremen_dependency_hygiene.py` | 10 | ✓ All passed |
| **Full suite** | **1109 passed, 11 skipped** | ✓ **0 failures** |

Coverage summary for demo-run tests:
- Constants (`DEMO_RUN_VERSION`)
- Helper functions (`_find_free_port`, `_start_local_server` — ephemeral port, without model, distinct ports)
- `run_demo()` with explicit base URL — health check, model version, overall pass, output shape, `technical_demo_only`, `request_id`, skip-prediction, unavailable service
- `run_demo()` without base URL (auto-start) — returns result dict, health check pass, model version pass, overall pass
- Evidence bundle — present with explicit URL, `technical_demo_only`, `product: "Bremen"`, required keys, request_id match, present with auto-start
- Server startup failure — controlled error output shape
- JSON serializability — both explicit URL and auto-start
- No fixed port conflict — two sequential calls use different ports
- `--skip-prediction` pass-through — skipped when True, attempted when False
- CLI help — `demo-run --help` exits 0, in main help, shows options
- Import/dependency safety — no H5, no joblib/pickle, no boto3/requests
- End-to-end CLI subprocess test — `python -m bremen demo-run --skip-prediction`

## VALIDATION RESULTS

| Command | Status |
|---------|--------|
| `git rev-parse --verify HEAD` | ✓ `c4ea090` |
| `git branch --show-current` | ✓ `0062-one-command-demo-runner` |
| `git status --short` | ✓ 2 modified, 2 untracked (expected) |
| `git diff --name-only` | ✓ Only allowed files |
| `python -m compileall src tests` | ✓ All compiled |
| `python -m pytest -q tests/test_bremen_demo_run.py` | ✓ 37 passed |
| `python -m pytest -q tests/test_bremen_demo_smoke.py` | ✓ 25 passed |
| `python -m pytest -q tests/test_bremen_demo_evidence.py` | ✓ 63 passed |
| `python -m pytest -q tests/test_bremen_api_server.py` | ✓ 28 passed |
| `python -m pytest -q tests/test_bremen_api_skeleton.py` | ✓ 51 passed |
| `python -m pytest -q tests/test_bremen_dependency_hygiene.py` | ✓ 10 passed |
| `python -m pytest -q` | ✓ 1109 passed, 11 skipped |
| `python -m bremen --help` | ✓ Lists `demo-run` alongside other commands |
| `python -m bremen serve --help` | ✓ Shows --host, --port |
| `python -m bremen demo-smoke --help` | ✓ Shows --base-url, --timeout, --skip-prediction |
| `python -m bremen demo-run --help` | ✓ Shows --base-url, --timeout, --skip-prediction |
| Aramis grep (`demo_run.py`) | ✓ Zero matches (required) |
| Aramis grep (all evidence files) | ✓ Safe-only (prohibition context in `demo_evidence.py`, test assertions) |
| Clinical/replacement grep (`demo_run.py`) | ✓ Only safety header comment |
| Clinical/replacement grep (all evidence files) | ✓ Safe-only (disclaimer negation, prohibition pattern lists, test assertions) |
| joblib/pickle grep (all evidence files) | ✓ Only test assertions checking they DON'T appear |
| H5 grep (`demo_run.py` + evidence) | ✓ No matches in source |
| AWS/network grep (all evidence files) | ✓ No matches in source (stdlib urllib localhost only) |
| Web framework grep | ✓ Only pre-existing deferred references, no new deps |
| Forbidden files diff | ✓ No output |
| Docs/ROADMAP diff | ✓ No output |
| Artifact scan | ✓ No output |
| .DS_Store | ✓ No output |

## DIFF SUMMARY

```
src/bremen/__main__.py              |  52 ++++++++-
tests/test_bremen_cli_entrypoint.py |  40 +++++++
2 files changed, 91 insertions(+), 1 deletion(-)
```

Plus 2 new files: `src/bremen/demo_run.py` (250 lines), `tests/test_bremen_demo_run.py` (558 lines).

## PLAN COMPLIANCE

| Plan Requirement | Status |
|-----------------|--------|
| `python -m bremen demo-run` CLI command | ✓ Implemented |
| `--base-url`, `--timeout`, `--skip-prediction` options | ✓ Implemented |
| `src/bremen/demo_run.py` — stdlib-only | ✓ 250 lines, no new deps |
| `src/bremen/__main__.py` — demo-run subcommand | ✓ Subparser + handler added |
| `tests/test_bremen_demo_run.py` — new tests | ✓ 37 tests |
| `tests/test_bremen_cli_entrypoint.py` — CLI help tests | ✓ 3 new tests |
| Start local server on ephemeral port | ✓ `_start_local_server()` with `port=0` |
| Reuse `_make_handler(load_model=True)` | ✓ Same pattern as existing tests |
| Bounded health wait polling | ✓ `_wait_for_health()` with timeout + 0.5s interval |
| Call `run_demo_smoke()` — no duplicated logic | ✓ `run_demo()` calls `run_demo_smoke()` |
| Evidence bundle included automatically | ✓ Via existing `demo_smoke.py` → `build_demo_evidence_bundle()` |
| Server shutdown in `finally` | ✓ `server.shutdown()` + `thread.join(timeout=5)` |
| Controlled failure on startup error | ✓ Error dict with `technical_demo_only`, `status: "fail"`, warning |
| `--base-url` override for deployed services | ✓ Passes through to `run_demo_smoke()`, skips local server |
| No new dependencies | ✓ Stdlib-only |
| No model loading changes | ✓ Uses existing `_load_synthetic_model()` |
| No H5, AWS, clinical claims | ✓ All safety boundaries confirmed |

## PLAN DRIFT CHECK

| Drift Category | Check | Status |
|---------------|-------|--------|
| File drift | 4 files changed, all in allowed list | ✓ |
| Demo-run drift | Stdlib-only, reuses existing `_make_handler()` / `_load_synthetic_model()` | ✓ |
| Server lifecycle drift | Uses HTTPServer + daemon thread pattern from existing tests | ✓ |
| Safety drift | No unsafe deserialization, no H5, no AWS, no clinical claims | ✓ |
| Test drift | 37 new demo-run tests + 3 CLI tests. All 1109 pass. | ✓ |

**Key design decisions confirmed**:
- `_make_handler()` is private but used (same pattern as existing tests — acceptable per plan-review warning)
- `demo_run.py` contains zero Aramis strings (required by plan-review warning)
- Uses `ModelState.reset_for_tests()` before auto-start server (to ensure clean singleton state)

## BLOCKERS

None. All validation passed.

## WARNINGS

None. Implementation fully complies with PLAN.md and plan-review verdict.

## DEFERRED WORK

The following is explicitly out of scope for PR0062 and deferred:
- Frontend/dashboard for evidence visualization
- Model Ops / React console integration
- Deployment mutation (Terraform, Docker, App Runner)
- Real patient data integration
- Clinical report template additions
- Training pipeline changes
- Aramis cross-product alignment (permanent non-goal)
- Non-localhost server binding for demo-run (localhost-only by design)

## BOUNDARY CONFIRMATIONS

- confirm: one-command Bremen demo runner implemented: yes
- confirm: demo-run starts local service: yes
- confirm: demo-run uses existing demo-smoke/evidence path: yes
- confirm: demo evidence is not disposable: yes (builds on versioned evidence bundle)
- confirm: product-owner demo value implemented: yes
- confirm: technical_demo_only preserved: yes
- confirm: request_id/logging behavior preserved: yes
- confirm: localhost/ephemeral-port lifecycle implemented: yes
- confirm: deployed URL compatibility remains in demo-smoke: yes
- confirm: no deployment mutation added: yes
- confirm: no Terraform/GitHub Actions/Docker changes: yes
- confirm: no React/frontend added: yes
- confirm: no new dependencies added: yes
- confirm: no unsafe model loading added: yes
- confirm: no H5 mutation added: yes
- confirm: no real patient data added: yes
- confirm: no Aramis dependency added: yes
- confirm: no clinical diagnosis/replacement claims added: yes
- confirm: Bremen safety identity preserved: yes
- confirm: no H5/model/tfstate artifacts: yes
- confirm: no git mutation commands: yes
- confirm: implementation followed approved PLAN.md: yes
- confirm: no review artifact written: yes
- confirm: PLAN.md not modified: yes
- confirm: plan-review artifact not modified: yes
- confirm: only PLAN.md-approved paths changed: yes
- confirm: validation commands run and recorded: yes
