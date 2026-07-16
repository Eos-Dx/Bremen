# IMPLEMENTATION REPORT — PR 0065 Demo Route Namespace

**Branch**: `0065-demo-route-namespace`
**Plan**: `.project-memory/pr/0065-demo-route-namespace/PLAN.md`
**Plan Review**: `reviews/plan-review.yml` — verdict `approve`
**HEAD**: `a14dc2698bc0baae18b2f64ef04a9a6f3177a2ce`

## FILES CHANGED

| File | Status | Lines |
|------|--------|-------|
| `src/bremen/demo_ui.py` | NEW | 262 |
| `tests/test_bremen_demo_ui.py` | NEW | 330 |
| `src/bremen/api/server.py` | MODIFIED | +68/-0 |
| `tests/test_bremen_api_server.py` | MODIFIED | +79/-0 |

**Total**: 2 new files, 2 modified files.

All files listed in PLAN.md "Allowed implementation files" section. No CLI files modified.

## DEMO ROUTE NAMESPACE SUMMARY

Added two new routes to the existing Bremen HTTP service, served alongside the normal API on the same startup path (`python -m bremen serve`):

- **`GET /demo`** — Returns a self-contained, board-friendly HTML page with the demo evidence bundle, health/model/evidence/prediction status cards, and safety disclaimer
- **`GET /demo/api/evidence`** — Returns the same evidence bundle JSON that CLI tools generate, now available over REST

No new CLI command. No `--ui` flag. No separate service mode. Demo is separated by path only — future removal is possible by gating `/demo/*` routes in `server.py`.

## BROWSER DEMO UI SUMMARY

**Module**: `src/bremen/demo_ui.py` (262 lines, stdlib-only)

**Functions**:
- `build_demo_html_page(evidence, base_url, request_id) -> str` — Returns a complete HTML5 document with inline CSS, no external assets or CDN
- `build_demo_evidence_json_response(evidence) -> str` — Returns JSON string of the evidence bundle

**HTML page structure**:
- Yellow banner: "Technical demo only — not a clinical result."
- Overview card: Product, Question, Base URL, Request ID, Evidence Version, Scenario
- Service Health card: Status, Model Ready, check pass/fail indicators
- Model / Source card: Status, Model Version, Feature Schema
- Evidence Bundle card: Version, Scenario, Prediction Status
- Demo Flow card: Synthetic Feature Artifact, Bremen Service, Evidence Bundle, Technical Demo Output
- Warnings section (if warnings present)
- Footer: Full safety disclaimer

**Design**: Self-contained HTML with inline CSS, no `<script>` tags, no external URLs, no CDN, no fonts, no images. Screenshot-friendly and board-demo oriented.

## REST ENDPOINT SUMMARY

`GET /demo/api/evidence` returns the same evidence bundle JSON that `validate_demo_evidence_bundle()` and `json_dumps_evidence_bundle()` produce. The bundle includes `technical_demo_only: true`, `product: "Bremen"`, safety notes, model status, prediction status, and request_id.

## PRODUCT-OWNER / BOARD DEMO VALUE SUMMARY

A product owner or board member can now:
- Start the service normally: `python -m bremen serve`
- Open `http://localhost:8000/demo` in a browser — see a clean, card-based demo view with all key status indicators
- Hit `http://localhost:8000/demo/api/evidence` to get the evidence JSON over HTTP
- Use the same evidence shape that CLI tools produce, now REST-accessible
- See `technical_demo_only`, Bremen identity, and safety disclaimers prominently displayed

## ENABLEMENT / DEPRECATION BOUNDARY SUMMARY

- Demo is enabled solely by the `/demo/*` route namespace
- No changes to root-level endpoints (`/health`, `/model/version`, `/predictions`)
- Root `/` remains 404 (unchanged)
- Future deprecation or removal can be done by removing the two `elif` branches in `do_GET()` and deleting `demo_ui.py`
- No feature flags, config store, or auth implemented

## PRESERVED BEHAVIOR SUMMARY

- `/health`, `/model/version`, `/predictions`, `/predictions/{job_id}` unchanged
- Root `/` still returns 404
- Existing API error behavior unchanged
- request_id propagation unchanged
- Existing `demo-run` JSON/pretty/capture-dir behavior unchanged
- Existing `demo-smoke` behavior unchanged
- Evidence bundle shape unchanged
- No changes to `__main__.py`, `demo_run.py`, `demo_smoke.py`, or any CLI command
- No `--ui` flag added

## MULTI-TENANCY DEFERRAL SUMMARY

Multi-tenancy, model profiles, plugin configuration, and feature flags are deferred. No code was written in any of these areas.

## SAFETY BOUNDARY SUMMARY

| Boundary | Status | Evidence |
|----------|--------|---------|
| No `--ui` flag or new launch command | ✓ | No changes to `__main__.py` or CLI files |
| No root `/` demo page | ✓ | Root `/` still returns 404 (verified by test) |
| No React/frontend stack | ✓ | Stdlib-only HTML generation, no package-manager files |
| No external assets/CDN | ✓ | Inline CSS only, no external URLs (verified by grep and test) |
| No JavaScript | ✓ | No `<script>` tags in generated HTML (verified by test) |
| No unsafe model deserialization | ✓ | No `joblib.load()` or `pickle.load()` in new code |
| No H5 reads/writes | ✓ | No `.h5`, `.hdf5`, or `h5py` in new code |
| No AWS/network clients | ✓ | No `boto3`, `requests`, `httpx` in new code |
| No Aramis dependency | ✓ | Zero Aramis strings in `demo_ui.py` and `server.py` (verified by grep) |
| No clinical/replacement claims | ✓ | Only safe negation in disclaimer strings |
| `build_existence_proof` not created | ✓ | Zero matches for `build_existence_proof` in repo (verified by grep) |
| No new dependencies | ✓ | Stdlib-only module |
| No deployment mutation | ✓ | No Terraform, Docker, GitHub Actions changes |
| No docs/ROADMAP changes | ✓ | Unchanged |
| No real patient data | ✓ | Synthetic evidence only |

## TESTS RUN

| Test File | Tests | Result |
|-----------|-------|--------|
| `test_bremen_demo_ui.py` | 33 | ✓ All passed |
| `test_bremen_api_server.py` | 38 | ✓ All passed |
| `test_bremen_api_skeleton.py` | 51 | ✓ All passed |
| `test_bremen_demo_run.py` | 41 | ✓ All passed |
| `test_bremen_demo_capture.py` | 37 | ✓ All passed |
| `test_bremen_demo_presentation.py` | 43 | ✓ All passed |
| `test_bremen_demo_smoke.py` | 25 | ✓ All passed |
| `test_bremen_demo_evidence.py` | 63 | ✓ All passed |
| `test_bremen_dependency_hygiene.py` | 10 | ✓ All passed |
| **Full suite** | **1238 passed, 11 skipped** | ✓ **0 failures** |

Coverage summary for UI tests (33 tests):
- HTML page: returns string, contains Bremen, technical demo, disclaimer, inline CSS, product question, uses evidence data, request_id, no external URLs, has doctype, no JS, proper structure, warnings section, all 4 cards present, footer disclaimer
- Evidence JSON: valid JSON, `technical_demo_only`, `product: "Bremen"`, evidence_version, safety_notes, explicit evidence, deterministic, parsable, no diagnosis claim
- No Aramis references: HTML, JSON, module source
- Import/dependency safety: no H5, no joblib/pickle, no boto3/requests

Coverage for server HTTP tests:
- `GET /demo` returns HTML 200, contains Bremen, technical demo, request_id header
- `GET /demo/api/evidence` returns JSON 200, `technical_demo_only`, `product: "Bremen"`, request_id header
- Root `/` still 404
- Unknown `/demo/*` subroute returns 404

## VALIDATION RESULTS

| Command | Status |
|---------|--------|
| `git rev-parse --verify HEAD` | ✓ `a14dc26` |
| `git branch --show-current` | ✓ `0065-demo-route-namespace` |
| `git status --short` | ✓ 2 modified, 2 untracked (expected) |
| `git diff --name-only` | ✓ Only allowed files |
| `python -m compileall src tests` | ✓ All compiled |
| `python -m pytest -q tests/test_bremen_demo_ui.py` | ✓ 33 passed |
| `python -m pytest -q tests/test_bremen_api_server.py` | ✓ 38 passed |
| `python -m pytest -q tests/test_bremen_api_skeleton.py` | ✓ 51 passed |
| `python -m pytest -q tests/test_bremen_demo_run.py` | ✓ 41 passed |
| `python -m pytest -q tests/test_bremen_demo_capture.py` | ✓ 37 passed |
| `python -m pytest -q tests/test_bremen_demo_presentation.py` | ✓ 43 passed |
| `python -m pytest -q tests/test_bremen_demo_smoke.py` | ✓ 25 passed |
| `python -m pytest -q tests/test_bremen_demo_evidence.py` | ✓ 63 passed |
| `python -m pytest -q tests/test_bremen_dependency_hygiene.py` | ✓ 10 passed |
| `python -m pytest -q` | ✓ 1238 passed, 11 skipped |
| `python -m bremen --help` | ✓ Lists all commands |
| `python -m bremen serve --help` | ✓ Shows --host, --port |
| `python -m bremen demo-smoke --help` | ✓ Shows --base-url, --timeout, --skip-prediction |
| `python -m bremen demo-run --help` | ✓ Shows --pretty, --capture-dir |
| End-to-end capture smoke test | ✓ 3 files created |
| Aramis grep (all files) | ✓ Test assertions only — no source references |
| Clinical/replacement grep | ✓ Safety negation only |
| joblib/pickle grep | ✓ Pre-existing test assertions only |
| H5 grep (`demo_ui.py` + `server.py`) | ✓ No matches in source |
| AWS/network grep | ✓ No source imports (test assertions only) |
| Web framework grep | ✓ Pre-existing deferred references only |
| External assets/CDN grep | ✓ Test assertions only — no source references |
| `--ui` / `demo-run --ui` grep | ✓ No matches |
| `build_existence_proof` grep | ✓ No matches |
| Forbidden files diff | ✓ No output |
| Docs/ROADMAP diff | ✓ No output |
| Artifact scan | ✓ No output |
| .DS_Store | ✓ No output |

## DIFF SUMMARY

```
src/bremen/api/server.py        | 68 +++++++++++++++++++++++++
tests/test_bremen_api_server.py | 79 ++++++++++++++++++++++++++
2 files changed, 147 insertions(+)
```

Plus 2 new files: `src/bremen/demo_ui.py` (262 lines), `tests/test_bremen_demo_ui.py` (330 lines).

## PLAN COMPLIANCE

| Plan Requirement | Status |
|-----------------|--------|
| `src/bremen/demo_ui.py` — demo UI module | ✓ 262 lines, stdlib only, inline CSS |
| `build_demo_html_page()` — HTML generator | ✓ Self-contained HTML5 with cards, banner, footer |
| `build_demo_evidence_json_response()` — JSON generator | ✓ Validated evidence bundle JSON |
| `GET /demo` route in server.py | ✓ Returns HTML with `text/html; charset=utf-8` |
| `GET /demo/api/evidence` route in server.py | ✓ Returns JSON with `application/json` |
| No root `/` demo page | ✓ Root `/` still returns 404 (tested) |
| No `--ui` flag or new launch command | ✓ No CLI changes |
| No external assets/CDN | ✓ Inline CSS only, verified by grep/test |
| No JavaScript | ✓ No `<script>` tags (verified by test) |
| `technical_demo_only` in HTML and JSON | ✓ Banner in HTML, field in JSON |
| Bremen product identity | ✓ In HTML header and JSON |
| request_id preserved | ✓ In HTML, JSON, and response headers |
| Existing endpoints unchanged | ✓ `/health`, `/model/version`, `/predictions` all unchanged |
| Existing CLI behavior preserved | ✓ All demo-run/demo-smoke tests pass |
| No `build_existence_proof` created | ✓ Zero matches in repo (verified by grep) |
| No multi-tenancy/model-profiles/plugins | ✓ Deferred |

## PLAN DRIFT CHECK

| Drift Category | Check | Status |
|---------------|-------|--------|
| File drift | 4 files changed, all in allowed list | ✓ |
| Route drift | Routes under `/demo/*` only, root `/` still 404 | ✓ |
| No new CLI | No changes to `__main__.py`, `demo_run.py`, `demo_smoke.py` | ✓ |
| UI drift | Self-contained HTML, inline CSS, no external assets, no CDN, no React | ✓ |
| Safety drift | No unsafe deserialization, no H5, no AWS, no clinical claims | ✓ |
| Multi-tenancy drift | No multi-tenancy, model profiles, or plugins started | ✓ |
| Test drift | 33 new UI tests + 10 server HTTP tests. All 1238 pass. | ✓ |

## BLOCKERS

None.

## WARNINGS

None. Implementation fully complies with PLAN.md and plan-review verdict.

**Plan-review warning resolution**: The PLAN.md's `server.py` code sample incorrectly imported `build_existence_proof` from `demo_ui`. This was never created — the implementation uses only `build_demo_html_page` and `build_demo_evidence_json_response`. Verified by grep: zero matches for `build_existence_proof` in the repository.

## BOUNDARY CONFIRMATIONS

- confirm: demo route namespace implemented: yes
- confirm: demo remains Bremen-native: yes
- confirm: demo is separated by /demo path, not startup command: yes
- confirm: no --ui flag added: yes
- confirm: no extra launch command added: yes
- confirm: no root / demo page added: yes
- confirm: browser UI is board-demo oriented: yes
- confirm: UI is REST/evidence backed: yes
- confirm: UI is not production UI: yes
- confirm: no React/frontend stack added: yes
- confirm: no package-manager files added: yes
- confirm: product-owner/board demo value implemented: yes
- confirm: technical_demo_only preserved: yes
- confirm: JSON behavior preserved: yes
- confirm: pretty behavior preserved: yes
- confirm: capture-dir behavior preserved: yes
- confirm: request_id behavior preserved: yes
- confirm: /demo deprecation/removal boundary preserved: yes
- confirm: no deployment mutation added: yes
- confirm: no Terraform/GitHub Actions/Docker changes: yes
- confirm: multi-tenancy/model-profile/plugin work deferred: yes
- confirm: no new dependencies added: yes
- confirm: no unsafe model loading added: yes
- confirm: no H5 mutation added: yes
- confirm: no real patient data added: yes
- confirm: no Aramis dependency added: yes
- confirm: no clinical diagnosis/replacement claims added: yes
- confirm: build_existence_proof not created/imported: yes
- confirm: no H5/model/tfstate artifacts: yes
- confirm: no git mutation commands: yes
