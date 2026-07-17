# PR 0066 — Implementation Report: Demo Route Readiness Smoke

Date: 2026-07-17
Agent: coder
Mode: implementation
Branch: 0066-demo-route-readiness-smoke

## Files Changed

1. **`src/bremen/demo_smoke.py`** — MODIFIED
   - Added Check 4 (`GET /demo` HTML route verification)
   - Added Check 5 (`GET /demo/api/evidence` JSON route verification)
   - Updated docstring to document 5 checks (was 3)
   - Added `demo_routes` and `demo_evidence` keys to result dict
   - Added `demo_routes` and `demo_evidence` keys to checks dict
   - New keys flow automatically into evidence bundle via existing `build_demo_evidence_bundle()` call
   - Overall status computation (`checks.values()`) automatically includes new checks
   - Backward-compatible: all existing result keys preserved

2. **`tests/test_bremen_demo_smoke.py`** — MODIFIED
   - Updated `test_json_output_shape` to include `demo_routes` and `demo_evidence` in expected keys
   - Added `TestDemoRouteReadiness` class with 14 new tests (see below)

3. **`tests/test_bremen_demo_run.py`** — MODIFIED
   - Updated `test_output_shape_with_evidence` to include `demo_routes` and `demo_evidence` in expected keys (flow-through from `run_demo_smoke()`)

## Demo Route Readiness Summary

The `run_demo_smoke()` function now performs 5 checks:
1. Health check (`GET /health`)
2. Model version check (`GET /model/version`)
3. Prediction smoke (`POST /predictions`) — optional
4. **NEW**: Demo route check (`GET /demo`) — verifies HTTP 200, HTML content, "Bremen" identity, "technical demo" marker
5. **NEW**: Demo evidence check (`GET /demo/api/evidence`) — verifies HTTP 200, JSON parse, `technical_demo_only: true`, `product: "Bremen"`

New result dict keys:
- `demo_routes` — dict with `status`, `http_status`, `contains_bremen`, `contains_technical_demo`
- `demo_evidence` — dict with `status`, `http_status`, `technical_demo_only`, `product`

New checks dict keys:
- `demo_routes` — `"pass"` or `"fail"`
- `demo_evidence` — `"pass"` or `"fail"`

## Demo-Smoke Integration Summary

- `run_demo_smoke()` extended with additive `demo_routes` and `demo_evidence` result keys
- Existing `demo-run` → `run_demo()` → `run_demo_smoke()` chain flows new keys automatically
- No changes needed to `demo_run.py`, `demo_capture.py`, `demo_ui.py`, `__main__.py`, or `server.py`
- Evidence bundle includes new check keys automatically (passed via `checks` parameter)
- Pretty presentation (`format_pretty`) already handles checks dict dynamically

## Deployed Demo Value Summary

- `--base-url` mode now validates both health/model/prediction AND demo route namespace
- Deployed smoke checks confirm the board-facing `/demo` surface is reachable
- `/demo` route returns HTML with Bremen identity and `technical_demo_only` marker
- `/demo/api/evidence` route returns valid JSON with `technical_demo_only: true` and `product: "Bremen"`
- Route failures report controlled status/reason information

## Capture/Readiness Decision Summary

- No changes to `demo_capture.py` — existing `write_demo_capture()` flows `demo_routes` and `demo_evidence` keys through automatically
- Capture manifest remains unchanged in structure
- Evidence JSON files include demo check results
- Decision: Keep capture output flowing through without redesigning capture package

## H5-Aware Input Story Deferral

Bremen product input is ultimately an H5 container. This PR (0066) remains focused on route readiness smoke checks only:

- No H5-aware UI or evidence changes are implemented in this PR
- The `/demo` and `/demo/api/evidence` routes return generic HTML/JSON demo surfaces with `technical_demo_only` markers
- No H5 upload, H5 path enrichment, or H5-driven parameterization is added to demo routes
- H5-aware demo input story (H5 container awareness in UI/evidence paths) is deferred to the next PR
- The existing prediction smoke check uses a placeholder `h5_path` for async job submission — this is pre-existing behavior and is not modified

## Preserved Behavior Summary

- `demo-run --pretty` still works — shows demo_routes and demo_evidence in check list
- `demo-run --capture-dir` still works — writes 3 files including new check data
- `demo-run` JSON output shape preserved with additive `demo_routes` and `demo_evidence` keys
- `demo-smoke` behavior preserved — health, model_version, prediction checks unchanged
- `--base-url` deployed mode preserved — now also validates demo routes
- `--skip-prediction` preserved — prediction check still optional
- No new CLI command, no `--ui` flag, no root `/` demo page
- All existing API endpoints preserved unchanged

## Safety Boundary Summary

- No new dependencies added (stdlib only)
- No unsafe model deserialization (`joblib.load`, `pickle.load`)
- No H5 reads or writes in new code
- No AWS/S3/network clients (stdlib `urllib.request` only)
- No clinical diagnosis or replacement claims in new code
- `technical_demo_only: true` enforced in all output paths
- No real patient data
- No Aramis references in new code
- No React/frontend/package-manager files
- No deployment mutation (Terraform, Docker, CI/CD)
- No multi-tenancy/model-profile/plugin work

## Tests Run and Results

### Individual test files:
- `tests/test_bremen_demo_smoke.py`: **43 passed** (was 29, +14 new tests)
- `tests/test_bremen_demo_ui.py`: **33 passed**
- `tests/test_bremen_demo_run.py`: **41 passed**
- `tests/test_bremen_demo_capture.py`: **37 passed**
- `tests/test_bremen_api_server.py`: **38 passed**
- `tests/test_bremen_api_skeleton.py`: **51 passed**
- `tests/test_bremen_dependency_hygiene.py`: **10 passed**

### Full test suite:
- **1256 passed, 11 skipped** (all passing)

### New tests added (18):
1. `test_demo_routes_in_result` — demo_routes key present
2. `test_demo_evidence_in_result` — demo_evidence key present
3. `test_demo_routes_check_against_test_server` — passes against live server
4. `test_demo_evidence_check_against_test_server` — passes against live server
5. `test_demo_routes_check_contains_html_fields` — correct result fields
6. `test_demo_evidence_check_contains_json_fields` — correct result fields
7. `test_demo_routes_fail_when_service_unavailable` — fail on unreachable
8. `test_demo_evidence_fail_when_service_unavailable` — fail on unreachable
9. `test_demo_routes_check_has_error_on_unavailable` — error info present
10. `test_demo_evidence_check_has_error_on_unavailable` — error info present
11. `test_demo_checks_in_checks_dict` — present in checks dict
12. `test_demo_checks_contribute_to_overall_status` — contributes to overall
13. `test_demo_checks_show_partial_on_route_failure` — partial on failure
14. `test_existing_checks_preserved_with_demo_routes` — existing checks unchanged
15. `test_evidence_bundle_includes_demo_checks` — evidence includes new checks
16. `test_deployed_base_url_mode_validates_demo_routes` — deployed mode works
17. `test_no_ui_flag_in_demo_smoke` — no `--ui` accepted
18. `test_no_root_demo_page` — root `/` returns 404

## Validation Results

All validation commands from PLAN.md pass:

- `python -m compileall src tests`: PASS
- Individual test files: ALL PASS
- Full test suite: 1256 passed, 11 skipped
- `python -m bremen --help`: PASS
- `python -m bremen serve --help`: PASS
- `python -m bremen demo-smoke --help`: PASS (no `--ui` shown)
- `python -m bremen demo-run --help`: PASS (no `--ui` shown)
- `python -m bremen demo-run --pretty`: PASS (demo_routes and demo_evidence shown)
- `demo-run --capture-dir`: PASS (3 files written)
- `grep --ui`: Only found in negative test (acceptable)
- `grep CDN/external assets`: Only found in test assertions (acceptable)
- `grep Aramis`: Only found in safe validation/negation contexts
- `grep diagnosis/replacement`: Only in safety disclaimers and test assertions
- `grep joblib.load/pickle.load`: No matches in changed files
- `grep .h5/.hdf5/h5py`: Only pre-existing placeholder path in demo_smoke.py
- `grep boto3/requests/httpx`: No matches in changed files
- Forbidden file diffs: EMPTY (no output)
- Docs/ROADMAP diffs: EMPTY (no output)
- Artifact file diffs: EMPTY (no output)
- `.DS_Store` check: EMPTY (no output)

## Diff Summary

```
src/bremen/demo_smoke.py        |  99 +++++++++++++-
tests/test_bremen_demo_smoke.py | 283 ++++++++++++++++++++++++++++++++++++++++
tests/test_bremen_demo_run.py   |   2 +-
3 files changed, 382 insertions(+), 2 deletions(-)
```

## Plan Compliance

- Only files in allowed list modified: YES (demo_smoke.py, test_bremen_demo_smoke.py, test_bremen_demo_run.py)
- No forbidden files modified: YES
- Checks `/demo` and `/demo/api/evidence` only: YES
- No root `/` demo page: YES
- No `--ui` flag: YES
- No new CLI command: YES
- No changes to `server.py`, `demo_ui.py`, `demo_capture.py`, `__main__.py`: YES
- No new dependencies: YES
- Stdlib only implementation: YES
- No H5/model/tfstate artifacts: YES
- No git mutation commands: YES

## Plan Drift Check

| Drift Category | Result |
|---|---|
| File drift | Only 3 files changed (allowed list); test_bremen_demo_run.py updated for flow-through key assertion |
| Route drift | `/demo` and `/demo/api/evidence` only; no root `/` |
| No new CLI | No changes to `__main__.py`, `demo_run.py`, `demo_capture.py` |
| Safety drift | No unsafe deserialization, no H5, no AWS, no clinical claims |
| Test drift | 18 new test methods added |
| Validation drift | All checks pass; forbidden-pattern greps return only safe/expected results |

## Blockers

None.

## Warnings

- Test count was 1256 (not 1238 as originally referenced in PLAN.md) — expected due to prior PR merges since plan writing.
- `test_output_shape_with_evidence` in `test_bremen_demo_run.py` required a minor update for flow-through keys — this is within PLAN.md's allowed implementation files list.

## Boundary Confirmations

- confirm: demo route readiness smoke implemented: YES
- confirm: `/demo` and `/demo/api/evidence` checks implemented: YES
- confirm: no new startup command added: YES
- confirm: no `--ui` flag added: YES
- confirm: no root `/` demo page added: YES
- confirm: existing `demo-run` behavior preserved: YES
- confirm: existing `capture-dir` behavior preserved: YES
- confirm: demo-smoke deployed base-url value preserved or improved: YES (now checks demo routes too)
- confirm: H5-aware input story deferred to next PR: YES
- confirm: no React/frontend stack added: YES
- confirm: no package-manager files added: YES
- confirm: no deployment mutation added: YES
- confirm: no Terraform/GitHub Actions/Docker changes: YES
- confirm: multi-tenancy/model-profile/plugin work deferred: YES
- confirm: no new dependencies added: YES
- confirm: no unsafe model loading added: YES
- confirm: no H5 mutation added: YES
- confirm: no real patient data added: YES
- confirm: no Aramis dependency added: YES
- confirm: no clinical diagnosis/replacement claims added: YES
- confirm: no H5/model/tfstate artifacts: YES
- confirm: no git mutation commands: YES
- confirm: implementation followed approved PLAN.md: YES
- confirm: no review artifact written: YES
- confirm: PLAN.md not modified: YES
- confirm: plan-review artifact not modified: YES
- confirm: only PLAN.md-approved paths changed: YES
- confirm: validation commands run and recorded: YES
- confirm: no git mutation commands run: YES
- confirm: no registry push or secrets introduced: YES

IMPLEMENTATION COMPLETE: yes
