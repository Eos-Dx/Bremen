# PR 0063 — Plan Product Demo Presentation Polish

Author: plan
Mode: planning only
Branch: 0063-product-demo-presentation-polish

## Objective

Add a reusable, testable presentation layer to the existing Bremen demo path (PR0060 demo-smoke, PR0061 evidence pack, PR0062 demo-run), making the output presentation-ready for product-owner and stakeholder demos.

This PR adds a `--pretty` flag to `python -m bremen demo-run` (and optionally `demo-smoke`) that emits a stable, structured plain-text summary alongside the existing JSON. The JSON output remains unchanged and backward-compatible.

No new product architecture. No multi-tenancy. No model profiles. No plugins. No deployment changes.

## Required reads — observed facts

### `src/bremen/demo_run.py`
- `main()` prints JSON (`json.dumps(result, indent=2)`) followed by a short human-readable summary (status, checks, warnings, request_id, evidence version/product).
- CLI flags: `--base-url`, `--timeout`, `--skip-prediction`.
- No `--pretty` flag exists yet.

### `src/bremen/demo_smoke.py`
- Same pattern: JSON output + basic human-readable summary.
- `main()` in demo_smoke is called from `demo_run.py` — any `--pretty` integration in demo-run will be handled at the demo-run level.

### `src/bremen/demo_evidence.py`
- `build_demo_evidence_bundle()` returns structured dict.
- `validate_demo_evidence_bundle()` validates shape.
- `json_dumps_evidence_bundle()` produces JSON string.
- No text/pretty formatter exists yet.

### `src/bremen/__main__.py`
- `demo_run` and `demo_smoke` subcommands exist with CLI args.
- Adding `--pretty` to `demo-run` follows the established pattern.

### Tests
- 1109 tests pass (PR0060 + PR0061 + PR0062 are all merged).
- `tests/test_bremen_demo_run.py` — 13 test scenarios for demo-run.
- `tests/test_bremen_demo_smoke.py` — tests for demo-smoke.

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Allowed implementation files

1. **`src/bremen/demo_presentation.py`** — NEW. Reusable presentation formatter module. Stdlib only.
2. **`src/bremen/demo_run.py`** — MODIFY. Add `--pretty` flag; when set, call `format_pretty()` instead of raw human-readable summary.
3. **`src/bremen/__main__.py`** — MODIFY. Add `--pretty` argument to `demo-run` subcommand.
4. **`tests/test_bremen_demo_presentation.py`** — NEW. Tests for the presentation formatter.
5. **`tests/test_bremen_demo_run.py`** — MODIFY. Add test for `demo-run --pretty` behavior.
6. **`tests/test_bremen_cli_entrypoint.py`** — MODIFY. Add CLI help test for `--pretty`.

Optional (justify in notes if included):
- `src/bremen/demo_smoke.py` — MODIFY to add `--pretty` to demo-smoke as well. Default preference: keep `--pretty` on `demo-run` only; ``demo-smoke`` maintains its existing output format unchanged.

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

## Exact implementation scope

### 1. `src/bremen/demo_presentation.py` — Presentation formatter

A pure, testable, stdlib-only formatter. Takes a demo-run result dict (the dict returned by `run_demo()` or `run_demo_smoke()`) and returns a stable plain-text string.

```python
"""Bremen demo presentation formatter.

Produces stable, deterministic plain-text presentation output from
a Bremen demo-run or demo-smoke result dict.  Suitable for
product-owner demos, operator checks, release-walkthrough output,
and future Model Ops console content.

No colors, no terminal codes, no HTML, no deployment assumptions.
Standard library only — no third-party dependencies.
"""

from __future__ import annotations

from typing import Any
```

**`format_pretty(result: dict[str, Any]) -> str`**:

Returns a multi-line string. Each section is a clearly labelled group of lines. Example output:

```
===============================================================================
  BREMEN PRODUCT DEMO
  Technical demo only — not a clinical result.
===============================================================================

  Product       : Bremen
  Question      : Should patient continue to MRI?
  Base URL      : http://127.0.0.1:52731
  Request ID    : a1b2c3d4-e5f6-7890-abcd-ef1234567890
  Total Status  : PASS  [health: ✓  model_version: ✓  prediction: ✓]

  ── Health ──────────────────────────────────────────────────────────────
  Status       : ok
  Model Ready  : yes
  Version      : v0.1
  Service      : bremen

  ── Model / Version ─────────────────────────────────────────────────────
  Status          : ready
  Version         : smoke-v0.1
  Checksum        : a1b2...c3d4
  Feature Schema  : bremen.feature_artifact.v0.1

  ── Prediction ──────────────────────────────────────────────────────────
  Status        : completed
  Job ID        : f6e5d4c3-b2a1-0987-6543-210fedcba987
  QC Status     : passed
  p_mri_needed  : 0.620
  Recommendation: MRI_RECOMMENDED

  ── Evidence Bundle ─────────────────────────────────────────────────────
  Version       : v0.1
  Scenario      : bremen_demo_v1
  Safety Notes  :
    1. Technical product demo only — not a clinical result.
    2. Not clinically validated.
    3. Does not replace MRI, biopsy, radiologist, clinician,
       or clinical judgment.
    4. All clinical decisions must be made by qualified clinicians.

  ── Warnings ────────────────────────────────────────────────────────────
  (none)

===============================================================================
  This is a technical product demo. Not a clinical result.
  Not clinically validated. Does not replace MRI, biopsy,
  radiologist, clinician, or clinical judgment.
===============================================================================
```

**Non-negotiable output rules**:
- `Technical demo only` or `technical_demo_only` must appear in the header and footer.
- `Bremen` product identity must appear in the header.
- No diagnosis, no "replaces MRI", no "replaces biopsy", no "replaces radiologist", no "replaces clinician" language (except in disclaimer/safety notes which use safe negation).
- No Aramis references.
- No terminal control codes or colors.
- Stable, deterministic — same input always produces same output.
- Handles `not_available` prediction state gracefully:

```
  ── Prediction ──────────────────────────────────────────────────────────
  Status        : not_available
  Reason        : Prediction check was skipped via --skip-prediction flag.
```

- Handles `fail` status gracefully (shows warnings, doesn't mask errors).

**`format_pretty_header(result: dict[str, Any]) -> str`** — Returns just the header section (for potential use by interactive scripts).

**`format_pretty_footer(result: dict[str, Any]) -> str`** — Returns just the footer section.

### 2. `src/bremen/demo_run.py` — Add `--pretty` flag

Add `--pretty` flag to the argparse in `main()`:

```python
parser.add_argument(
    "--pretty",
    action="store_true",
    help="Print a formatted plain-text presentation summary.",
)
```

When `--pretty` is set, print the same JSON output (preserving backward compatibility), THEN print the pretty-formatted output:

```python
if args.pretty:
    from .demo_presentation import format_pretty
    print()
    print(format_pretty(result))
```

The JSON output remains the primary machine-readable output. The pretty output is additive — printed after the JSON with a blank line separator. This preserves backward compatibility for any JSON consumers while adding the presentation layer.

### 3. `src/bremen/__main__.py` — Add `--pretty` to demo-run subcommand

Add the `--pretty` flag to the demo-run subparser:

```python
demo_run.add_argument(
    "--pretty",
    action="store_true",
    help="Print a formatted plain-text presentation summary.",
)
```

Pass `--pretty` through to `_handle_demo_run()`:

```python
def _handle_demo_run(args):
    from .demo_run import main as demo_run_main
    cli_args = [f"--timeout={args.timeout}"]
    if args.base_url:
        cli_args.append(f"--base-url={args.base_url}")
    if args.skip_prediction:
        cli_args.append("--skip-prediction")
    if args.pretty:
        cli_args.append("--pretty")
    return demo_run_main(cli_args)
```

### 4. `tests/test_bremen_demo_presentation.py` — New tests

Test scenarios (12+):

1. **`format_pretty()` returns a string** — Basic smoke test.
2. **`format_pretty()` includes "Bremen"** — Product identity present.
3. **`format_pretty()` includes "technical demo"** — Safety disclaimer present.
4. **`format_pretty()` includes health status** — `ok` or `fail` visible.
5. **`format_pretty()` includes model status** — `ready` or `not_configured` visible.
6. **`format_pretty()` includes prediction status** — `completed`, `not_available`, or `failed`.
7. **`format_pretty()` includes request_id** — UUID visible in output.
8. **`format_pretty()` includes evidence bundle** — `evidence_version`, `safety_notes`.
9. **`format_pretty()` handles `not_available` prediction** — Shows `not_available` and reason.
10. **`format_pretty()` handles fail status with warnings** — Warnings visible.
11. **`format_pretty()` has no terminal control codes** — No ANSI escape sequences.
12. **`format_pretty()` is deterministic** — Same input produces identical output.
13. **No Aramis references** — String scan for prohibited patterns returns no matches.
14. **No clinical/replacement language** — String scan for prohibited patterns returns no matches (except safe negation in disclaimer/safety_notes).

### 5. `tests/test_bremen_demo_run.py` — Add `--pretty` test

Add 2 test cases:
- `test_demo_run_pretty_flag_accepted` — `--pretty` is a valid flag (doesn't crash); verify output contains expected text.
- `test_demo_run_pretty_json_still_present` — JSON output still present in stdout when `--pretty` is used.

### 6. `tests/test_bremen_cli_entrypoint.py` — Add `--pretty` CLI help test

Add:
- `test_demo_run_pretty_in_help` — `python -m bremen demo-run --help` shows `--pretty`.

## Non-goals

- No new HTTP routes or API contract changes.
- No model loading changes.
- No H5 reads or writes.
- No AWS/S3 calls.
- No Matador resolver implementation.
- No clinical report template addition.
- No multi-tenancy, model profiles, or plugin architecture.
- No deployment mutation (Terraform, Docker, CI/CD).
- No React/frontend.
- No new dependencies.
- No docs/ROADMAP updates.
- No real patient data.
- No terminal colors or control codes.
- No HTML output.

## Safety boundaries

- No runtime training.
- No unsafe model deserialization.
- No new `joblib.load()` or `pickle.load()`.
- No H5 reads or writes.
- No preprocessing expansion.
- No AWS/S3 network calls.
- No Matador resolver implementation.
- No clinical report template.
- No clinical diagnosis claims.
- `technical_demo_only` prominent in pretty output.
- No real patient data.
- No Aramis references.
- No diagnosis/replacement language (except safe negation in disclaimers).

## Validation checklist

```bash
# Git checks
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only

# Compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_demo_presentation.py
python -m pytest -q tests/test_bremen_demo_run.py
python -m pytest -q tests/test_bremen_demo_smoke.py
python -m pytest -q tests/test_bremen_demo_evidence.py
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
```

### Forbidden-pattern grep checks

```bash
# No Aramis dependency or product labels
grep -R -I -n "Aramis\|aramis\|M2Q\|BENIGN vs CANCER" \
  src/bremen/demo_presentation.py src/bremen/demo_run.py \
  src/bremen/demo_smoke.py src/bremen/demo_evidence.py \
  tests/test_bremen_demo_presentation.py tests/test_bremen_demo_run.py \
  tests/test_bremen_demo_smoke.py tests/test_bremen_demo_evidence.py || true
# Expected: no output

# No clinical/replacement claims
grep -R -I -n "diagnosis\|diagnose\|replaces MRI\|replace MRI\|replaces biopsy\|replace biopsy\|replaces radiologist\|replace radiologist\|replaces clinician\|replace clinician" \
  src/bremen/demo_presentation.py src/bremen/demo_run.py \
  src/bremen/demo_smoke.py src/bremen/demo_evidence.py \
  tests/test_bremen_demo_presentation.py tests/test_bremen_demo_run.py \
  tests/test_bremen_demo_smoke.py tests/test_bremen_demo_evidence.py || true
# Expected: no output (negative-test assertion strings in tests allowed with justification)

# No unsafe deserialization
grep -R -I -n "joblib\.load\|pickle\.load\|import pickle" \
  src/bremen/demo_presentation.py src/bremen/demo_run.py \
  src/bremen/demo_smoke.py src/bremen/demo_evidence.py \
  tests/test_bremen_demo_presentation.py tests/test_bremen_demo_run.py \
  tests/test_bremen_demo_smoke.py tests/test_bremen_demo_evidence.py || true
# Expected: no output

# No H5 dependency in presentation/demo
grep -R -I -n "\.h5\|\.hdf5\|h5py" \
  src/bremen/demo_presentation.py src/bremen/demo_run.py \
  src/bremen/demo_evidence.py \
  tests/test_bremen_demo_presentation.py tests/test_bremen_demo_run.py \
  tests/test_bremen_demo_evidence.py || true
# Expected: no output

# No AWS/network client deps (stdlib urllib localhost is allowed)
grep -R -I -n "boto3\|botocore\|requests\|httpx" \
  src/bremen/demo_presentation.py src/bremen/demo_run.py \
  src/bremen/demo_smoke.py src/bremen/demo_evidence.py \
  tests/test_bremen_demo_presentation.py tests/test_bremen_demo_run.py \
  tests/test_bremen_demo_smoke.py tests/test_bremen_demo_evidence.py || true
# Expected: no output

# No new web framework
grep -R -I -n "FastAPI\|Flask\|uvicorn\|gunicorn\|starlette\|aiohttp\|django" \
  src tests requirements.txt pyproject.toml || true
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
| Presentation module | `src/bremen/demo_presentation.py` — pure function, no state, no side effects. |
| Pretty output scope | `demo-run --pretty` only (not `demo-smoke`). |
| JSON preserved | JSON output remains unchanged; pretty output is additive. |
| Terminal codes | **None** — plain text only. |
| Output format | Key-value pairs in sections with ASCII-rule separators. |
| Safety disclaimer | Prominent in header and footer. |
| `technical_demo_only` | Visible in output header. |
| Real patient data | **None**. |
| Multi-tenancy | **None**. |

## Rollback plan

1. **Revert `src/bremen/demo_presentation.py`** — delete.
2. **Revert `src/bremen/demo_run.py`** — remove `--pretty` additions.
3. **Revert `src/bremen/__main__.py`** — remove `--pretty` from demo-run subcommand.
4. **Revert `tests/test_bremen_demo_presentation.py`** — delete.
5. **Revert test modifications** — revert `test_bremen_demo_run.py` and `test_bremen_cli_entrypoint.py`.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only 6 allowed files changed. No forbidden files. |
| **Presentation drift** | Pure function, stdlib only, no side effects, no terminal codes. |
| **Demo-run drift** | `--pretty` is additive — JSON output unchanged. Backward-compatible. |
| **Safety drift** | No unsafe deserialization, no H5, no AWS, no clinical claims. |
| **Test drift** | 14+ new presentation tests + 2 demo-run tests + 1 CLI test. Existing tests pass unchanged. |
| **Validation drift** | All validation checks pass. Forbidden-pattern greps return nothing. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Implementation requires new dependencies.
- Implementation requires Terraform, Docker, GitHub Actions, or deployment changes.
- Implementation adds HTML, colors, terminal codes, or frontend.
- Implementation introduces unsafe model deserialization.
- Implementation reads H5 files.
- Implementation starts multi-tenancy/model-profile/plugin work.
- Implementation hardcodes secrets, account IDs, or production URLs.
- Implementation cannot be completed within the allowed files.
- Implementation becomes docs-only.
- Implementation phase is not Agent: coder / Mode: implementation.

## Decisions summary

| Decision | Value |
|----------|-------|
| Presentation module | `src/bremen/demo_presentation.py` — pure function, stdlib only. |
| Core function | `format_pretty(result) -> str` — deterministic, plain text. |
| CLI flag | `python -m bremen demo-run --pretty` (additive to JSON). |
| JSON behavior | Unchanged — JSON output always present. |
| Terminal codes | None — plain ASCII text only. |
| Output sections | Header + Health + Model/Version + Prediction + Evidence + Warnings + Footer. |
| Safety disclaimer | Prominent in header and footer. |
| `technical_demo_only` | Visible in header text. |
| Scope | `demo-run --pretty` only. `demo-smoke` unchanged. |
| Dependencies | None new. |

## Files read

- `ROADMAP.md`
- `docs/api_contract.md`
- `docs/architecture.md`
- `docs/adr/0003-bremen-microservice-api-architecture.md`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `docs/adr/0008-runtime-target-apprunner-proving.md`
- `docs/adr/0012-system-of-record-boundary.md`
- `src/bremen/__main__.py`
- `src/bremen/demo_run.py`
- `src/bremen/demo_smoke.py`
- `src/bremen/demo_evidence.py`
- `src/bremen/api/server.py`
- `src/bremen/api/app.py`
- `tests/test_bremen_demo_run.py`
- `tests/test_bremen_demo_smoke.py`
- `tests/test_bremen_demo_evidence.py`
- `tests/test_bremen_cli_entrypoint.py`
- `tests/test_bremen_api_server.py`
- `tests/test_bremen_api_skeleton.py`
- `tests/test_bremen_dependency_hygiene.py`
- `.project-memory/project_contract.yml`
- `AGENTS.md`

## Files written

- `.project-memory/pr/0063-product-demo-presentation-polish/PLAN.md` (this file)

## Boundary confirmations

- confirm: PR0063 planned as product demo presentation polish: yes
- confirm: demo remains Bremen-native: yes
- confirm: demo presentation is not disposable: yes (reusable module, testable functions)
- confirm: pretty output planned: yes
- confirm: product-owner demo value planned: yes
- confirm: technical_demo_only preserved: yes
- confirm: JSON behavior preserved: yes (additive pretty output)
- confirm: request_id/logging behavior preserved: yes
- confirm: no deployment mutation planned: yes
- confirm: no Terraform/GitHub Actions/Docker changes planned: yes
- confirm: no React/frontend planned: yes
- confirm: no multi-tenancy implementation planned: yes
- confirm: no new dependencies planned: yes
- confirm: no unsafe model loading planned: yes
- confirm: no H5 mutation planned: yes
- confirm: no real patient data planned: yes
- confirm: no Aramis dependency planned: yes
- confirm: no clinical diagnosis/replacement claims planned: yes
- confirm: implementation assigned to Agent: coder / Mode: implementation: yes
- confirm: no git mutation commands run: yes
