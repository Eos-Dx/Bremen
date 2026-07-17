# PR 0066 — Plan Demo Route Readiness Smoke

Author: plan
Mode: planning only
Branch: 0066-demo-route-readiness-smoke

## Objective

Extend the existing `run_demo_smoke()` checks to include the PR0065 `/demo/*` route namespace. When a Bremen service is running with the demo routes enabled, `demo-smoke` and `demo-run` will verify that `/demo` returns HTML with Bremen identity and `technical_demo_only`, and `/demo/api/evidence` returns JSON with `technical_demo_only: true`.

No new CLI command. No `--ui` flag. No service startup change. Backward-compatible JSON result shape.

## Required reads — observed facts

### `src/bremen/demo_smoke.py`
- `run_demo_smoke(base_url, timeout, skip_prediction)` performs 3 checks: health, model_version, prediction.
- Returns dict with keys: `technical_demo_only`, `base_url`, `request_id`, `checks`, `health`, `model_version`, `prediction`, `warnings`, `status`, `timestamp`, `evidence`.
- The `checks` dict currently has keys: `health`, `model_version`, `prediction`.
- `_request()` helper makes HTTP calls via stdlib `urllib.request`.

### `src/bremen/demo_ui.py` (PR0065)
- `build_demo_html_page()` — generates self-contained HTML.
- `build_demo_evidence_json_response()` — generates evidence JSON string.
- Module is safe to import — no model loading, no H5, no network.

### `src/bremen/demo_run.py`
- `run_demo()` calls `run_demo_smoke()` and returns the same dict shape.
- `--pretty` and `--capture-dir` work on the result dict.
- No changes needed for route readiness — the new checks flow through automatically.

### `src/bremen/demo_capture.py`
- `write_demo_capture()` writes summary, evidence, manifest from the result dict.
- No changes needed — route readiness checks in the result dict flow into capture automatically.

### `src/bremen/api/server.py` (PR0065)
- `do_GET()` now matches `/demo` and `/demo/api/evidence` in addition to existing routes.

### Tests
- 1238 tests pass. All PR0060–0065 merged.

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Allowed implementation files

1. **`src/bremen/demo_smoke.py`** — MODIFY. Add `/demo` and `/demo/api/evidence` checks in `run_demo_smoke()`.
2. **`tests/test_bremen_demo_smoke.py`** — MODIFY. Add tests for demo route readiness checks.
3. **`tests/test_bremen_demo_run.py`** — No change needed (result flows through automatically), but verify existing tests still pass.

**No CLI changes.** No changes to `__main__.py`, `demo_run.py`, `demo_capture.py`, `demo_ui.py`, or `server.py`.

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

### 1. `src/bremen/demo_smoke.py` — Add demo route readiness checks

**Add two new optional checks** after the existing health/model_version/prediction checks and before the overall status computation.

**Check 4: `/demo` HTML check**:

```python
# ---- Check 4: Demo route (/demo) ----
try:
    status, body, resp_headers = _request("GET", "/demo")
    body_text = body.decode("utf-8")
    html_ok = (
        status == 200
        and "Bremen" in body_text
        and "technical demo" in body_text.lower()
    )
    demo_route_result = {
        "status": "pass" if html_ok else "fail",
        "http_status": status,
        "contains_bremen": "Bremen" in body_text,
        "contains_technical_demo": "technical demo" in body_text.lower(),
    }
    if html_ok:
        checks["demo_routes"] = "pass"
    else:
        checks["demo_routes"] = "fail"
        warnings.append(
            f"/demo check: HTTP {status}, "
            f"Bremen={'Bremen' in body_text}, "
            f"tech_demo={'technical demo' in body_text.lower()}"
        )
except HTTPError as exc:
    demo_route_result = {"status": "fail", "http_status": exc.code, "error": str(exc)}
    checks["demo_routes"] = "fail"
    warnings.append(f"/demo HTTP error: {exc.code}")
except Exception as exc:
    demo_route_result = {"status": "error", "error": str(exc)}
    checks["demo_routes"] = "fail"
    warnings.append(f"/demo check error: {exc}")
```

**Check 5: `/demo/api/evidence` JSON check**:

```python
# ---- Check 5: Demo evidence route (/demo/api/evidence) ----
try:
    status, body, resp_headers = _request("GET", "/demo/api/evidence")
    data = json.loads(body)
    json_ok = (
        status == 200
        and data.get("technical_demo_only") is True
        and data.get("product") == "Bremen"
    )
    evidence_route_result = {
        "status": "pass" if json_ok else "fail",
        "http_status": status,
        "technical_demo_only": data.get("technical_demo_only"),
        "product": data.get("product"),
    }
    if json_ok:
        checks["demo_evidence"] = "pass"
    else:
        checks["demo_evidence"] = "fail"
        warnings.append(
            f"/demo/api/evidence check: HTTP {status}, "
            f"technical_demo_only={data.get('technical_demo_only')}, "
            f"product={data.get('product')}"
        )
except HTTPError as exc:
    evidence_route_result = {"status": "fail", "http_status": exc.code, "error": str(exc)}
    checks["demo_evidence"] = "fail"
    warnings.append(f"/demo/api/evidence HTTP error: {exc.code}")
except (json.JSONDecodeError, Exception) as exc:
    evidence_route_result = {"status": "error", "error": str(exc)}
    checks["demo_evidence"] = "fail"
    warnings.append(f"/demo/api/evidence check error: {exc}")
```

**Backward compatibility**: The `checks` dict gains two new keys: `demo_routes` and `demo_evidence`. The overall status computation uses `checks.values()` so these new keys contribute to the overall pass/partial/fail determination automatically. Existing JSON consumers that iterate `checks` will see the new keys. The result dict gains two new top-level keys: `demo_routes` and `demo_evidence`.

**Evidence bundle update**: The evidence bundle (built at the end of `run_demo_smoke()`) already includes `checks` and `warnings`. Since we update `checks` before building evidence, the new check statuses will appear in the evidence bundle automatically.

### 2. `tests/test_bremen_demo_smoke.py` — Add route readiness tests

Add test cases to the existing test file:

1. **`test_demo_routes_checks_against_test_server`** — Start a test server with `_make_handler(load_model=True)`, call `run_demo_smoke()`, verify `demo_routes` and `demo_evidence` checks are present in the result dict and are `"pass"`.
2. **`test_demo_routes_check_contains_html`** — Verify `demo_routes` result keys include `status`, `http_status`, `contains_bremen`, `contains_technical_demo`.
3. **`test_demo_evidence_check_contains_json`** — Verify `demo_evidence` result keys include `status`, `http_status`, `technical_demo_only`, `product`.
4. **`test_demo_routes_fail_when_service_unavailable`** — When service is unreachable, demo route checks show appropriate error status.
5. **`test_demo_checks_contribute_to_overall_status`** — When demo routes fail, overall status reflects the failure (partial or fail).
6. **`test_existing_checks_preserved`** — Health, model_version, and prediction checks still work and contribute to overall status.

Use the same test infrastructure: `_find_free_port()`, `_make_handler()` with `load_model=True`, daemon thread, `urllib.request`.

### 3. No changes needed to `demo_run.py`, `demo_capture.py`, `__main__.py`, or `server.py`

The route readiness checks flow through `run_demo_smoke()` → `run_demo()` → `main()` → JSON/pretty/capture output automatically. No wiring changes needed.

## Non-goals

- No new CLI command, no `--ui` flag.
- No service startup changes.
- No changes to `demo_ui.py` or `demo_run.py`.
- No changes to capture manifest format (existing flow handles new keys).
- No changes to pretty presentation (format_pretty already displays checks dynamically).
- No React/frontend, no package manager.
- No external assets.
- No multi-tenancy, model profiles, plugins.
- No deployment mutation (Terraform, Docker, CI/CD).
- No new dependencies.
- No docs/ROADMAP changes.

## Safety boundaries

- No runtime training.
- No unsafe model deserialization.
- No new `joblib.load()` or `pickle.load()`.
- No H5 reads or writes.
- No AWS/S3 network calls — stdlib `urllib.request` to supplied `--base-url` only.
- No Matador resolver implementation.
- No clinical report template.
- No clinical diagnosis claims.
- `technical_demo_only` enforced in checks.
- No real patient data.
- No Aramis references.
- No diagnosis/replacement language.

## Validation checklist

```bash
# Git checks
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only

# Compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_demo_smoke.py
python -m pytest -q tests/test_bremen_demo_ui.py
python -m pytest -q tests/test_bremen_demo_run.py
python -m pytest -q tests/test_bremen_demo_capture.py
python -m pytest -q tests/test_bremen_api_server.py
python -m pytest -q tests/test_bremen_api_skeleton.py
if test -f tests/test_bremen_dependency_hygiene.py; then \
  python -m pytest -q tests/test_bremen_dependency_hygiene.py; \
else echo "SKIP missing tests/test_bremen_dependency_hygiene.py"; fi
python -m pytest -q
python -m bremen --help
python -m bremen serve --help
python -m bremen demo-smoke --help
python -m bremen demo-run --help
python -m bremen demo-run --pretty
tmpdir="$(mktemp -d)" && \
  python -m bremen demo-run --pretty --capture-dir "$tmpdir" && \
  find "$tmpdir" -maxdepth 1 -type f -print | sort
```

### Forbidden-pattern grep checks

```bash
# No --ui flag or extra launch command
grep -R -I -n -- "--ui\|demo-run --ui" src/bremen tests || true
# Expected: no output

# No external assets/CDN links in demo UI
grep -R -I -n "https://\|http://.*cdn\|unpkg\|jsdelivr\|googleapis\|fontawesome" \
  src/bremen/demo_ui.py tests/test_bremen_demo_ui.py || true
# Expected: no output

# No Aramis dependency or product labels
grep -R -I -n "Aramis\|aramis\|M2Q\|BENIGN vs CANCER" \
  src/bremen tests/test_bremen_demo_smoke.py tests/test_bremen_demo_ui.py || true
# Expected: no output (test assertions verifying absence are allowed)

# No clinical/replacement claims (except safe negation in disclaimers)
grep -R -I -n "diagnosis\|diagnose\|replaces MRI\|replace MRI\|replaces biopsy\|replace biopsy\|replaces radiologist\|replace radiologist\|replaces clinician\|replace clinician" \
  src/bremen tests/test_bremen_demo_smoke.py tests/test_bremen_demo_ui.py || true
# Expected: no output

# No unsafe deserialization
grep -R -I -n "joblib\.load\|pickle\.load\|import pickle" \
  src/bremen tests/test_bremen_demo_smoke.py tests/test_bremen_demo_ui.py || true
# Expected: no output (pre-existing in modeling.py/mlflow_tracking.py is not in PR scope)

# No H5 dependency
grep -R -I -n "\.h5\|\.hdf5\|h5py" \
  src/bremen/demo_smoke.py src/bremen/demo_ui.py \
  tests/test_bremen_demo_smoke.py tests/test_bremen_demo_ui.py || true
# Expected: no output

# No AWS/network client deps (stdlib urllib is allowed)
grep -R -I -n "boto3\|botocore\|requests\|httpx" \
  src/bremen/demo_smoke.py src/bremen/demo_ui.py \
  tests/test_bremen_demo_smoke.py tests/test_bremen_demo_ui.py || true
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
| Check 4 route | `GET /demo` — HTML page |
| Check 5 route | `GET /demo/api/evidence` — JSON evidence |
| Result dict keys | `demo_routes` (new), `demo_evidence` (new) |
| Checks dict keys | `demo_routes` (new), `demo_evidence` (new) |
| Backward compatibility | New keys are additive — existing consumers ignore unknown keys |
| Overall status | New checks contribute to pass/partial/fail computation |
| Capture/pretty output | New keys flow through automatically |
| CLI changes | None |

## Rollback plan

1. **Revert `src/bremen/demo_smoke.py`** — remove the demo route readiness check blocks.
2. **Revert `tests/test_bremen_demo_smoke.py`** — remove route readiness test cases.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only 2 files changed (allowed list). No forbidden files. |
| **Route drift** | Checks `/demo` and `/demo/api/evidence` only. No root `/`. |
| **No new CLI** | No changes to `__main__.py`, `demo_run.py`, `demo_capture.py`. |
| **Safety drift** | No unsafe deserialization, no H5, no AWS, no clinical claims. |
| **Test drift** | 6 new test scenarios. Existing 1238 tests pass unchanged. |
| **Validation drift** | All validation checks pass. Forbidden-pattern greps return nothing. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Plan adds `--ui` or another launch command.
- Plan requires changes to `server.py`, `demo_ui.py`, `demo_run.py`, `demo_capture.py`, or `__main__.py`.
- Plan requires new dependencies.
- Plan requires real patient data.
- Plan requires unsafe model loading or H5 mutation.
- Plan weakens Bremen safety language.
- Implementation phase is not Agent: coder / Mode: implementation.

## Decisions summary

| Decision | Value |
|----------|-------|
| Module to modify | `demo_smoke.py` only — add Check 4 and Check 5 |
| Route checks | `/demo` (HTML), `/demo/api/evidence` (JSON) |
| New result keys | `demo_routes` (dict), `demo_evidence` (dict) |
| New checks keys | `demo_routes`, `demo_evidence` — additive |
| Overall status | New checks contribute automatically via `checks.values()` |
| Evidence bundle | Updated automatically because `checks` is passed to `build_demo_evidence_bundle()` |
| Capture/pretty | Flow through automatically |

## Files read

- `ROADMAP.md`
- `docs/api_contract.md`
- `docs/architecture.md`
- `docs/adr/0003-bremen-microservice-api-architecture.md`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `docs/adr/0008-runtime-target-apprunner-proving.md`
- `docs/adr/0012-system-of-record-boundary.md`
- `src/bremen/__main__.py`
- `src/bremen/demo_smoke.py`
- `src/bremen/demo_run.py`
- `src/bremen/demo_capture.py`
- `src/bremen/demo_ui.py`
- `src/bremen/demo_evidence.py`
- `src/bremen/api/server.py`
- `src/bremen/api/app.py`
- `tests/test_bremen_demo_smoke.py`
- `tests/test_bremen_demo_run.py`
- `tests/test_bremen_demo_capture.py`
- `tests/test_bremen_demo_ui.py`
- `tests/test_bremen_api_server.py`
- `tests/test_bremen_api_skeleton.py`
- `tests/test_bremen_cli_entrypoint.py`
- `tests/test_bremen_dependency_hygiene.py`
- `.project-memory/project_contract.yml`
- `AGENTS.md`

## Files written

- `.project-memory/pr/0066-demo-route-readiness-smoke/PLAN.md` (this file)

## Boundary confirmations

- confirm: PR0066 planned as demo route readiness smoke: yes
- confirm: `/demo` and `/demo/api/evidence` checks planned: yes
- confirm: no new startup command planned: yes
- confirm: no `--ui` flag planned: yes
- confirm: no root `/` demo page planned: yes
- confirm: existing demo-run behavior preserved: yes
- confirm: existing capture-dir behavior preserved: yes
- confirm: demo-smoke deployed base-url value preserved or improved: yes (now checks demo routes too)
- confirm: no React/frontend stack planned: yes
- confirm: no package-manager files planned: yes
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
