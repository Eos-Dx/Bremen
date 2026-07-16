# PR 0065 — Plan Demo Route Namespace

Author: plan
Mode: planning only
Branch: 0065-demo-route-namespace

## Objective

Add a `/demo/*` route namespace to the existing Bremen HTTP service, served alongside the normal API on the same startup path. The `/demo` page provides a board-friendly browser view of the existing demo evidence/smoke infrastructure. The `/demo/api/evidence` endpoint serves the same evidence bundle JSON that the CLI tools produce.

No new CLI command. No `--ui` flag. No separate service mode. No React. No package manager. No external assets.

Demo is separated by path, not by startup command. Future removal is possible by gating `/demo/*`.

## Required reads — observed facts

### `src/bremen/api/server.py`
- `_make_handler()` returns a `_BremenHandler` class with `do_GET()` and `do_POST()` dispatching by `self.path`.
- `do_GET()` matches `/health`, `/model/version`, `/predictions/{job_id}`.
- `do_POST()` matches `/predictions`.
- The handler has access to `job_store`, `version`, and can import demo modules.
- `_load_synthetic_model()` and `load_model` parameter exist for synthetic model loading.
- `run_server()` is blocking and calls `ModelState.load_at_startup()`.

### `src/bremen/demo_evidence.py`
- `build_demo_evidence_bundle()` — builds the evidence bundle dict.
- `validate_demo_evidence_bundle()` — validates bundle shape.
- `json_dumps_evidence_bundle()` — produces validated JSON string.
- `build_demo_feature_artifact_payload()` — synthetic 15-feature artifact.
- Constants: `BREMEN_PRODUCT_NAME`, `BREMEN_PRODUCT_QUESTION`, `BREMEN_DEMO_DISCLAIMER`, `DEMO_EVIDENCE_VERSION`, `DEMO_SCENARIO_ID`, `_DEFAULT_SAFETY_NOTES`.

### `src/bremen/demo_presentation.py`
- `format_pretty(result)` — plain-text formatting.
- All output is text, not HTML. No HTML exists in the demo modules.

### `src/bremen/demo_smoke.py`
- `run_demo_smoke(base_url, timeout, skip_prediction)` — calls `/health`, `/model/version`, `/predictions` internally and returns structured result dict.
- This requires a running HTTP service at `base_url`.

### `src/bremen/__main__.py`
- No changes needed for this PR. No new CLI commands, no `--ui` flag.
- The service starts via `python -m bremen serve`, same as before.

### Tests
- 1195 tests pass. All PR0060–0064 are merged.

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Allowed implementation files

1. **`src/bremen/demo_ui.py`** — NEW. Demo UI page generator and `/demo/api/evidence` handler. Stdlib only.

2. **`src/bremen/api/server.py`** — MODIFY. Add `/demo` routing in `do_GET()` and `/demo/api/evidence` as a handler call.

3. **`tests/test_bremen_demo_ui.py`** — NEW. Tests for the demo UI module and `/demo/*` routes.

4. **`tests/test_bremen_api_server.py`** — MODIFY. Add HTTP-level tests for `/demo` and `/demo/api/evidence`.

**Default: no CLI changes.** No changes to `__main__.py`, `demo_run.py`, `demo_smoke.py`, or any existing CLI modules.

## Forbidden files

- `.github/**`, `infra/terraform/**`
- `Dockerfile`, `Dockerfile.training`
- `requirements.txt`, `pyproject.toml`
- `frontend/**`, `web/**`, `ui/**`
- `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `node_modules/**`
- `tests/data/**`
- Any `.h5`, `.hdf5`, `.joblib`, `.pkl`, `.npy`, `.npz`
- `tfstate`, `.terraform`
- `config/training/**`, `src/bremen/training/**`
- `docs/**`, `ROADMAP.md`
- Aramis artifacts, model descriptions, feature schemas as dependency

## Exact implementation scope

### 1. `src/bremen/demo_ui.py` — Demo UI page generator

A small stdlib-only module. No web framework, no HTTP server, no network calls. Pure HTML generation from evidence/result dicts.

```python
"""Bremen /demo route UI page generator.

Produces a self-contained, board-friendly HTML page from an existing
Bremen demo evidence/result bundle.  Inline CSS only — no external
assets, no CDN, no network requests.

No web framework dependency.  Standard library only.
"""

from __future__ import annotations

from typing import Any
```

**Two public functions**:

```python
def build_demo_html_page(
    evidence: dict[str, Any] | None = None,
    base_url: str | None = None,
    request_id: str | None = None,
) -> str:
    """Build a self-contained HTML page for the /demo route.

    Parameters
    ----------
    evidence : Optional evidence bundle dict (from
        ``build_demo_evidence_bundle()``).  If ``None``, uses
        a default "generating..." status.
    base_url : Base URL of the service.
    request_id : Optional request ID for traceability.

    Returns
    -------
    A complete HTML5 document as a string.
    """
```

```python
def build_demo_evidence_json_response(
    evidence: dict[str, Any] | None = None,
) -> str:
    """Build the JSON response for the /demo/api/evidence endpoint.

    Parameters
    ----------
    evidence : Optional evidence bundle dict.  If ``None``, builds
        a fresh bundle from ``build_demo_evidence_bundle()``.

    Returns
    -------
    A JSON string suitable for the HTTP response body.
    """
```

**HTML page content**:

The HTML page should be board-friendly and screenshot-ready. Content:

- Header: Bremen product identity + `Technical demo only` banner
- Card 1: Service Health — status, model_ready, version
- Card 2: Model / Source — status, version, feature schema
- Card 3: Evidence Bundle — version, scenario, safety notes
- Card 4: Prediction / Demo Flow — synthetic feature artifact → Bremen → evidence → output
- Footer: Full safety disclaimer

**Design rules**:

- Self-contained HTML with inline CSS only
- No external assets (no CDN, no fonts, no images)
- No JavaScript unless truly required; if any JS, must be inline and minimal
- No network requests from the page
- Responsive enough for browser viewing
- Clean, readable typography — sans-serif, adequate contrast, generous spacing
- `technical_demo_only` banner visible without scrolling

**Evidence JSON endpoint**:

`/demo/api/evidence` returns the same evidence bundle JSON that `validate_demo_evidence_bundle()` and `json_dumps_evidence_bundle()` produce. This is the same evidence shape that the CLI tools generate, now available over REST.

### 2. `src/bremen/api/server.py` — Add `/demo/*` routing

**Minimal changes to `_make_handler()`**:

In `do_GET()`, add routes BEFORE the final `else: 404`:

```python
elif self.path == "/demo":
    from ..demo_ui import build_demo_html_page, build_existence_proof  # noqa: PLC0415

    # Build evidence from live service state
    import json
    from ..demo_evidence import build_demo_evidence_bundle  # noqa: PLC0415

    evidence = build_demo_evidence_bundle(
        base_url=f"http://{self.headers.get('Host', 'localhost')}",
        request_id=self._get_request_id(),
        model_status=ModelState.get_instance().info() if ... else None,
        # Deterministic: build a minimal safe evidence bundle
        # without requiring full prediction smoke
    )
    html = build_demo_html_page(
        evidence=evidence,
        base_url=f"http://{self.headers.get('Host', 'localhost')}",
        request_id=self._get_request_id(),
    )
    body = html.encode("utf-8")
    self.send_response(200)
    self.send_header("Content-Type", "text/html; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.send_header("X-Request-ID", self._get_request_id())
    self.end_headers()
    self.wfile.write(body)

elif self.path == "/demo/api/evidence":
    from ..demo_ui import build_demo_evidence_json_response  # noqa: PLC0415
    from ..demo_evidence import build_demo_evidence_bundle  # noqa: PLC0415

    evidence = build_demo_evidence_bundle(
        base_url=f"http://{self.headers.get('Host', 'localhost')}",
        request_id=self._get_request_id(),
        model_status="ready",  # safe default for demo
    )
    json_str = build_demo_evidence_json_response(evidence=evidence)
    body = json_str.encode("utf-8")
    self.send_response(200)
    self.send_header("Content-Type", "application/json")
    self.send_header("Content-Length", str(len(body)))
    self.send_header("X-Request-ID", self._get_request_id())
    self.end_headers()
    self.wfile.write(body)
```

The evidence bundle in `/demo/api/evidence` must include `technical_demo_only: true`, Bremen identity, and safety notes just like any other evidence output.

**Import handling**: Use lazy imports inside the route handler methods (same pattern as existing `do_POST` which imports `logging` and `ModelState` inline). This keeps module-level imports minimal and avoids circular dependencies.

### 3. `tests/test_bremen_demo_ui.py` — New tests

Test scenarios (12+):

1. **`build_demo_html_page()` returns a string** — Basic smoke test.
2. **`build_demo_html_page()` contains "Bremen"** — Product identity.
3. **`build_demo_html_page()` contains "technical demo"** — Safety disclaimer.
4. **`build_demo_html_page()` contains "not a clinical"** — Disclaimer text.
5. **`build_demo_html_page()` contains inline CSS `<style>`** — Self-contained.
6. **`build_demo_html_page()` has no external URLs** — No `https://`, `http://` (except in safe sample content), no `cdn`, `unpkg`, `jsdelivr`, `googleapis`, `fontawesome`.
7. **`build_demo_evidence_json_response()` returns valid JSON** — `json.loads()` succeeds.
8. **`build_demo_evidence_json_response()` contains `technical_demo_only: true`** — Safety invariant.
9. **`build_demo_evidence_json_response()` contains `product: "Bremen"`** — Identity.
10. **`build_demo_evidence_json_response()` is deterministic** — Same input produces same output.
11. **No Aramis references** — String scan on both HTML and JSON output.
12. **No clinical/replacement claims** — String scan (except safe negation in disclaimers).

### 4. `tests/test_bremen_api_server.py` — Add `/demo/*` HTTP tests

Add 4–5 HTTP-level tests:

1. **`test_get_demo_returns_html`** — `GET /demo` returns 200 with `Content-Type: text/html`.
2. **`test_get_demo_contains_bremen`** — Response body contains "Bremen".
3. **`test_get_demo_contains_technical_demo`** — Response body contains "technical demo".
4. **`test_get_demo_api_evidence_returns_json`** — `GET /demo/api/evidence` returns 200 with `Content-Type: application/json`.
5. **`test_get_demo_api_evidence_contains_technical_demo_only`** — JSON body contains `technical_demo_only: true`.
6. **`test_get_demo_api_evidence_contains_bremen`** — JSON body contains `Bremen`.

Use the same test infrastructure as existing server tests: `_find_free_port()`, `_make_handler()` with `load_model=True`, daemon thread, `urllib.request` to localhost.

## Non-goals

- No new CLI command, no `--ui` flag, no separate service mode.
- No demo content at root `/` (only `/demo` and `/demo/*`).
- No React, frontend build step, or package manager.
- No external assets, CDN, fonts, images.
- No JavaScript beyond absolute minimum inline usage.
- No multi-tenancy, model profiles, or plugin architecture.
- No deployment mutation (Terraform, Docker, CI/CD).
- No changes to `__main__.py`, `demo_run.py`, `demo_smoke.py`, or any CLI command.
- No changes to existing API endpoints (`/health`, `/model/version`, `/predictions`).
- No production UI, patient-facing UI, or clinical UI.
- No `--overwrite` or `--upload` for capture.
- No new dependencies.
- No docs/ROADMAP changes.

## Safety boundaries

- No runtime training.
- No unsafe model deserialization.
- No new `joblib.load()` or `pickle.load()`.
- No H5 reads or writes.
- No preprocessing expansion.
- No AWS/S3 network calls — the `/demo` page is self-contained HTML with no external network requests.
- No Matador resolver implementation.
- No clinical report template.
- No clinical diagnosis claims.
- `technical_demo_only` prominent in HTML and JSON output.
- No real patient data.
- No Aramis references.
- No diagnosis/replacement language (except safe negation in disclaimers).
- No interactive/stateful UI that could leak data.

## Validation checklist

```bash
# Git checks
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only

# Compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_demo_ui.py
python -m pytest -q tests/test_bremen_api_server.py
python -m pytest -q tests/test_bremen_api_skeleton.py
python -m pytest -q tests/test_bremen_demo_run.py
python -m pytest -q tests/test_bremen_demo_capture.py
python -m pytest -q tests/test_bremen_demo_presentation.py
python -m pytest -q tests/test_bremen_demo_smoke.py
python -m pytest -q tests/test_bremen_demo_evidence.py
if test -f tests/test_bremen_dependency_hygiene.py; then \
  python -m pytest -q tests/test_bremen_dependency_hygiene.py; \
else echo "SKIP missing tests/test_bremen_dependency_hygiene.py"; fi
python -m pytest -q
python -m bremen --help
python -m bremen serve --help
python -m bremen demo-smoke --help
python -m bremen demo-run --help
python -m bremen demo-run --pretty

# End-to-end — capture still works
tmpdir="$(mktemp -d)" && \
  python -m bremen demo-run --pretty --capture-dir "$tmpdir" && \
  find "$tmpdir" -maxdepth 1 -type f -print | sort

# End-to-end — demo route works
python -m bremen serve --port 8888 &
sleep 2
curl -s http://127.0.0.1:8888/demo | head -10
curl -s http://127.0.0.1:8888/demo/api/evidence | python -m json.tool
kill %1 2>/dev/null || true
```

### Forbidden-pattern grep checks

```bash
# No Aramis dependency or product labels
grep -R -I -n "Aramis\|aramis\|M2Q\|BENIGN vs CANCER" \
  src/bremen/demo_ui.py src/bremen/api/server.py \
  tests/test_bremen_demo_ui.py tests/test_bremen_api_server.py || true
# Expected: no output (test assertions verifying absence are allowed)

# No clinical/replacement claims (except safe negation in disclaimers)
grep -R -I -n "diagnosis\|diagnose\|replaces MRI\|replace MRI\|replaces biopsy\|replace biopsy\|replaces radiologist\|replace radiologist\|replaces clinician\|replace clinician" \
  src/bremen/demo_ui.py src/bremen/api/server.py \
  tests/test_bremen_demo_ui.py tests/test_bremen_api_server.py || true
# Expected: no output except safe negation in safety notes

# No unsafe deserialization
grep -R -I -n "joblib\.load\|pickle\.load\|import pickle" \
  src/bremen/demo_ui.py src/bremen/api/server.py \
  tests/test_bremen_demo_ui.py tests/test_bremen_api_server.py || true
# Expected: no output

# No H5 dependency
grep -R -I -n "\.h5\|\.hdf5\|h5py" \
  src/bremen/demo_ui.py src/bremen/api/server.py \
  tests/test_bremen_demo_ui.py tests/test_bremen_api_server.py || true
# Expected: no output

# No AWS/network client deps
grep -R -I -n "boto3\|botocore\|requests\|httpx" \
  src/bremen/demo_ui.py src/bremen/api/server.py \
  tests/test_bremen_demo_ui.py tests/test_bremen_api_server.py || true
# Expected: no output

# No new web framework
grep -R -I -n "FastAPI\|Flask\|uvicorn\|gunicorn\|starlette\|aiohttp\|django" \
  src tests requirements.txt pyproject.toml || true
# Expected: no output (pre-existing deferred references only)

# No external assets/CDN links in demo UI
grep -R -I -n "https://\|http://.*cdn\|unpkg\|jsdelivr\|googleapis\|fontawesome" \
  src/bremen/demo_ui.py tests/test_bremen_demo_ui.py || true
# Expected: no output

# No --ui flag or extra launch command
grep -R -I -n -- "--ui\|demo-run --ui\|demo-run --browser" \
  src/bremen tests || true
# Expected: no output

# Forbidden files unchanged
git diff --name-only -- .github infra/terraform Dockerfile Dockerfile.training \
  requirements.txt pyproject.toml config/training frontend web ui \
  package.json package-lock.json yarn.lock pnpm-lock.yaml tests/data

# Docs/ROADMAP unchanged
git diff --name-only -- docs ROADMAP.md
# Expected: no output

# No model/data artifacts
git diff --name-only | grep -E "\.(h5|hdf5|joblib|pkl|npy|npz|tfstate|tfstate\.backup)$" || true
# Expected: no output

# No .DS_Store
find . -name ".DS_Store" -print
```

## Platform safety decisions

| Decision | Value |
|----------|-------|
| Demo route base | `/demo` (not root `/`) |
| Evidence API | `/demo/api/evidence` — returns validated evidence JSON |
| UI page generation | `src/bremen/demo_ui.py` — pure HTML generation, stdlib only |
| External assets | **None** — inline CSS only, no CDN, no fonts, no images |
| JavaScript | **Minimal or none** — inline only if needed for formatting |
| CLI changes | **None** — no new commands, no `--ui` flag |
| Evidence source | Uses same `build_demo_evidence_bundle()` as CLI tools |
| `technical_demo_only` | Visible in HTML and JSON |
| Future removal | Gate/remove `/demo/*` routes in server.py |
| Production API | Unchanged — remains at root level |

## Rollback plan

1. **Revert `src/bremen/demo_ui.py`** — delete.
2. **Revert `src/bremen/api/server.py`** — remove `/demo` and `/demo/api/evidence` routing from `do_GET()`.
3. **Revert `tests/test_bremen_demo_ui.py`** — delete.
4. **Revert `tests/test_bremen_api_server.py`** — remove `/demo/*` test cases.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only 4 allowed files changed. No forbidden files. |
| **Route drift** | Routes are under `/demo/*` only. No root `/` demo page. |
| **No new CLI** | No changes to `__main__.py`, `demo_run.py`, `demo_smoke.py`. |
| **UI drift** | Self-contained HTML, inline CSS, no external assets, no CDN, no React. |
| **Safety drift** | No unsafe deserialization, no H5, no AWS, no clinical claims. |
| **Test drift** | 12+ UI tests + 5+ server tests. Existing 1195 tests pass unchanged. |
| **Validation drift** | All validation checks pass. Forbidden-pattern greps return nothing. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Plan adds `--ui` or another launch command.
- Plan places demo at root `/`.
- Plan starts production frontend/React work.
- Plan starts multi-tenancy/model-profile/plugin work.
- Plan requires external assets, CDN, or package manager files.
- Plan requires new dependencies.
- Plan requires real patient data.
- Plan requires unsafe model loading or H5 mutation.
- Plan weakens Bremen safety language.
- Implementation phase is not Agent: coder / Mode: implementation.

## Decisions summary

| Decision | Value |
|----------|-------|
| Demo UI module | `src/bremen/demo_ui.py` — pure HTML generation, stdlib only. |
| HTML page function | `build_demo_html_page(evidence, base_url, request_id) -> str` |
| Evidence JSON function | `build_demo_evidence_json_response(evidence) -> str` |
| Server routing | `/demo` and `/demo/api/evidence` added to `do_GET()` in server.py. |
| Content types | `/demo` → `text/html`, `/demo/api/evidence` → `application/json`. |
| CLI change | **None**. |
| External assets | **None**. Inline CSS only. |
| Future removal | Gate/remove `/demo/*` in server.py. |
| Existing endpoints | Unchanged. |
| Multi-tenancy | Deferred. |

## Files read

- `ROADMAP.md`
- `docs/api_contract.md`
- `docs/architecture.md`
- `docs/adr/0003-bremen-microservice-api-architecture.md`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `docs/adr/0008-runtime-target-apprunner-proving.md`
- `docs/adr/0012-system-of-record-boundary.md`
- `src/bremen/__main__.py`
- `src/bremen/api/server.py`
- `src/bremen/api/app.py`
- `src/bremen/api/jobs.py`
- `src/bremen/api/schemas.py`
- `src/bremen/demo_run.py`
- `src/bremen/demo_capture.py`
- `src/bremen/demo_presentation.py`
- `src/bremen/demo_smoke.py`
- `src/bremen/demo_evidence.py`
- `tests/test_bremen_api_server.py`
- `tests/test_bremen_api_skeleton.py`
- `tests/test_bremen_demo_run.py`
- `tests/test_bremen_demo_capture.py`
- `tests/test_bremen_demo_presentation.py`
- `tests/test_bremen_demo_smoke.py`
- `tests/test_bremen_demo_evidence.py`
- `tests/test_bremen_cli_entrypoint.py`
- `tests/test_bremen_dependency_hygiene.py`
- `.project-memory/project_contract.yml`
- `AGENTS.md`

## Files written

- `.project-memory/pr/0065-demo-route-namespace/PLAN.md` (this file)

## Boundary confirmations

- confirm: PR0065 planned as demo route namespace: yes
- confirm: demo remains Bremen-native: yes
- confirm: demo is separated by `/demo` path, not startup command: yes
- confirm: no `--ui` flag planned: yes
- confirm: no extra launch command planned: yes
- confirm: no root `/` demo page planned: yes
- confirm: browser UI is board-demo oriented: yes
- confirm: UI is REST/evidence backed: yes
- confirm: UI is not production UI: yes
- confirm: no React/frontend stack planned: yes
- confirm: no package-manager files planned: yes
- confirm: product-owner/board demo value planned: yes
- confirm: `technical_demo_only` preserved: yes
- confirm: JSON behavior preserved: yes
- confirm: pretty behavior preserved: yes
- confirm: capture-dir behavior preserved: yes
- confirm: request_id behavior preserved: yes
- confirm: `/demo` deprecation/removal boundary planned: yes
- confirm: no deployment mutation planned: yes
- confirm: no Terraform/GitHub Actions/Docker changes planned: yes
- confirm: multi-tenancy/model-profile/plugin work deferred: yes
- confirm: no new dependencies planned: yes
- confirm: no unsafe model loading planned: yes
- confirm: no H5 mutation planned: yes
- confirm: no real patient data planned: yes
- confirm: no Aramis dependency planned: yes
- confirm: no clinical diagnosis/replacement claims planned: yes
- confirm: implementation assigned to Agent: coder / Mode: implementation: yes
- confirm: no git mutation commands run: yes
