# PR 0064 — Plan Demo Readiness Capture Package

Author: plan
Mode: planning only
Branch: 0064-demo-readiness-capture-package

## Objective

Add a capture/package option to the existing `demo-run` flow so a product owner or operator can create a reusable demo readiness packet from the same live demo execution. When `--capture-dir <directory>` is passed to `python -m bremen demo-run --pretty --capture-dir <dir>`, three files are written:

| File | Content |
|------|---------|
| `bremen-demo-summary.txt` | Pretty presentation text from `format_pretty()` |
| `bremen-demo-evidence.json` | Validated evidence/result JSON (the full result dict) |
| `bremen-demo-manifest.json` | Capture metadata: generated_at_utc, capture version, technical_demo_only, file list, status |

All three files are guaranteed to contain `technical_demo_only`, Bremen identity, and safety disclaimers.

This completes the demo readiness pipeline:
- **PR0060** demo-smoke — Check a running service
- **PR0061** demo_evidence — Evidence bundle contract
- **PR0062** demo-run — One-command local demo
- **PR0063** demo_presentation — Pretty text output
- **PR0064** demo_capture — Reusable capture packet

## Required reads — observed facts

### `src/bremen/demo_run.py` (PR0062 + PR0063)
- `main()` accepts `--base-url`, `--timeout`, `--skip-prediction`, `--pretty`.
- `--pretty` calls `format_pretty(result)` and prints the result.
- `run_demo()` returns a dict with `technical_demo_only`, `status`, `checks`, `health`, `model_version`, `prediction`, `warnings`, `evidence`, `request_id`, `timestamp`.

### `src/bremen/demo_presentation.py` (PR0063)
- `format_pretty(result) -> str` — produces stable plain-text output.
- `format_pretty_header(result) -> str` — header-only.
- `format_pretty_footer(result) -> str` — footer-only.

### `src/bremen/demo_evidence.py` (PR0061)
- `validate_demo_evidence_bundle(bundle)` — validates evidence bundle shape.
- `json_dumps_evidence_bundle(bundle)` — validated JSON serialization.

### `src/bremen/__main__.py`
- `demo_run` subcommand is registered with `--base-url`, `--timeout`, `--skip-prediction`, `--pretty`.
- Adding `--capture-dir` follows the established pattern.

### Tests
- 1155 tests pass. All PR0060–PR0063 are merged.
- `tests/test_bremen_demo_run.py` — 13+ test scenarios.
- `tests/test_bremen_demo_presentation.py` — 14+ test scenarios.

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Allowed implementation files

1. **`src/bremen/demo_capture.py`** — NEW. Capture module: manifest builder, file writer, safe directory handling. Stdlib only.
2. **`src/bremen/demo_run.py`** — MODIFY. Add `--capture-dir` flag; when set, call `write_demo_capture()` before returning.
3. **`src/bremen/__main__.py`** — MODIFY. Add `--capture-dir` argument to `demo-run` subparser; pass through to handler.
4. **`tests/test_bremen_demo_capture.py`** — NEW. Tests for capture module and `--capture-dir` integration.
5. **`tests/test_bremen_demo_run.py`** — MODIFY. Add test for `demo-run --capture-dir` behavior.
6. **`tests/test_bremen_cli_entrypoint.py`** — MODIFY. Add CLI help test for `--capture-dir`.

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

### 1. `src/bremen/demo_capture.py` — Demo capture module

A small stdlib-only module. No network calls, no file reads, no model loading, no H5 access.

```python
"""Bremen demo readiness capture module.

Writes a reusable demo readiness packet from a demo-run result dict
to a specified directory.  Produces three files:

- ``bremen-demo-summary.txt`` — Pretty presentation text.
- ``bremen-demo-evidence.json`` — Validated evidence/result JSON.
- ``bremen-demo-manifest.json`` — Capture metadata.

All files include ``technical_demo_only``, Bremen identity, safety notes.

Standard library only — no third-party dependencies.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
```

**Constants**:

```python
DEMO_CAPTURE_VERSION = "v0.1"
FILE_SUMMARY = "bremen-demo-summary.txt"
FILE_EVIDENCE = "bremen-demo-evidence.json"
FILE_MANIFEST = "bremen-demo-manifest.json"
```

**`build_capture_manifest(result: dict, files: list[dict], *, generated_at_utc: str | None = None) -> dict`**:

Builds the capture manifest dict:

```python
{
    "demo_capture_version": DEMO_CAPTURE_VERSION,
    "generated_at_utc": "<ISO-8601 UTC>",
    "technical_demo_only": True,
    "product": "Bremen",
    "status": "pass" / "partial" / "fail",
    "request_id": "<uuid or null>",
    "files": [
        {"filename": "bremen-demo-summary.txt", "description": "Pretty text summary"},
        {"filename": "bremen-demo-evidence.json", "description": "Evidence/result JSON"},
        {"filename": "bremen-demo-manifest.json", "description": "Capture metadata"},
    ],
    "safety_notes": [
        "Technical product demo only — not a clinical result.",
        "Not clinically validated.",
        "Does not replace MRI, biopsy, radiologist, clinician, or clinical judgment.",
        "All clinical decisions must be made by qualified clinicians.",
    ],
}
```

The `generated_at_utc` parameter allows injection for test determinism. If `None`, uses `datetime.now(timezone.utc).isoformat()`.

**`write_demo_capture(result: dict, capture_dir: str, *, pretty_text: str | None = None) -> dict`**:

Writes the three capture files to `capture_dir`. Returns the manifest dict.

Behavior:
1. Resolve `capture_dir` — create directory (including parents) if missing.
2. If `capture_dir` exists as a file, raise `FileExistsError`.
3. If any of the three output files already exist, raise `FileExistsError` with a message listing the conflicting files. (No `--overwrite` flag planned — this is a safe default. If overwrite is needed, the user removes the directory first.)
4. Write `bremen-demo-summary.txt` — the pretty text, or a fallback header if `pretty_text` is `None`.
5. Write `bremen-demo-evidence.json` — validated JSON of the result dict. Use `json.dumps(indent=2)` for readability.
6. Build and write `bremen-demo-manifest.json` — capture metadata.
7. Return the manifest dict.

**Safety rules in capture module**:
- No diagnosis, no clinical recommendation as validated truth.
- No MRI/biopsy/radiologist replacement language.
- No patient-specific claims.
- No clinical performance claims.
- No Aramis references.
- `technical_demo_only: true` in every file.
- Bremen product identity in every file.

### 2. `src/bremen/demo_run.py` — Add `--capture-dir` flag

Add to argparse in `main()`:

```python
parser.add_argument(
    "--capture-dir",
    type=str,
    default=None,
    help=(
        "Directory to write demo capture files "
        "(summary.txt, evidence.json, manifest.json). "
        "Directory is created if it does not exist."
    ),
)
```

After getting the result (and printing JSON + pretty output), add capture logic:

```python
if args.capture_dir:
    from .demo_capture import write_demo_capture  # noqa: PLC0415

    # Get pretty text from earlier format_pretty call if --pretty was used
    pretty_text = pretty_text_result if args.pretty else None

    manifest = write_demo_capture(
        result=result,
        capture_dir=args.capture_dir,
        pretty_text=pretty_text,
    )
    print(f"\nDemo capture written to: {args.capture_dir}")
    print(f"  summary: {manifest['files'][0]['filename']}")
    print(f"  evidence: {manifest['files'][1]['filename']}")
    print(f"  manifest: {manifest['files'][2]['filename']}")
```

The implementation must restructure the output slightly: collect the pretty text as a variable rather than printing it directly, so it can be passed to `write_demo_capture()`.

**Refactored output flow**:

```python
# Print JSON
print(json.dumps(result, indent=2, ensure_ascii=False))

# Build pretty text (if --pretty)
pretty_text = format_pretty(result) if args.pretty else None
if pretty_text:
    print()
    print(pretty_text)

# Write capture (if --capture-dir)
if args.capture_dir:
    from .demo_capture import write_demo_capture
    manifest = write_demo_capture(
        result=result,
        capture_dir=args.capture_dir,
        pretty_text=pretty_text,
    )
    print(f"\nDemo capture written to: {args.capture_dir}")
    ...
```

### 3. `src/bremen/__main__.py` — Add `--capture-dir` to demo-run

Add to the demo-run subparser:

```python
demo_run.add_argument(
    "--capture-dir",
    type=str,
    default=None,
    help=(
        "Directory to write demo capture files "
        "(summary.txt, evidence.json, manifest.json)."
    ),
)
```

Pass through in `_handle_demo_run()`:

```python
if args.capture_dir:
    cli_args.append(f"--capture-dir={args.capture_dir}")
```

### 4. `tests/test_bremen_demo_capture.py` — New tests (15+ scenarios)

1. **`DEMO_CAPTURE_VERSION` is non-empty string** — Module constant exists.
2. **`build_capture_manifest()` includes all required fields** — `demo_capture_version`, `generated_at_utc`, `technical_demo_only`, `product`, `status`, `files`, `safety_notes`.
3. **`technical_demo_only` is `True`** — Critical invariant.
4. **`product` is `"Bremen"`** — Product identity.
5. **`safety_notes` is non-empty list** — Safety invariant.
6. **`files` lists all 3 expected filenames** — summary, evidence, manifest.
7. **`build_capture_manifest()` accepts explicit `generated_at_utc`** — Deterministic for tests.
8. **`write_demo_capture()` writes all 3 files** — In a temp dir, verify files exist.
9. **`bremen-demo-summary.txt` contains pretty text** — Verify content.
10. **`bremen-demo-evidence.json` is valid JSON** — `json.loads()` succeeds.
11. **`bremen-demo-evidence.json` contains `technical_demo_only`** — Safety invariant in every file.
12. **`bremen-demo-manifest.json` is valid manifest** — Validated against expected shape.
13. **`write_demo_capture()` creates missing directory** — Path doesn't exist yet.
14. **`write_demo_capture()` raises `FileExistsError` when capture_dir is a file** — Path exists as a regular file.
15. **`write_demo_capture()` raises `FileExistsError` when output files exist** — Controlled failure.
16. **No Aramis references** — String scan on all capture files.
17. **No clinical/replacement language** — String scan (except safe negation in disclaimers/safety_notes).
18. **JSON serializable** — All capture files pass `json.loads()`.

### 5. `tests/test_bremen_demo_run.py` — Add `--capture-dir` test

Add 2 test cases:
- `test_demo_run_capture_dir_writes_files` — `demo-run --capture-dir <tmpdir>` writes 3 files.
- `test_demo_run_capture_dir_with_pretty` — `demo-run --pretty --capture-dir <tmpdir>` includes pretty text in summary file.

### 6. `tests/test_bremen_cli_entrypoint.py` — Add `--capture-dir` CLI help test

Add:
- `test_demo_run_capture_dir_in_help` — `python -m bremen demo-run --help` shows `--capture-dir`.

## Non-goals

- No multi-tenancy, model profiles, or plugin architecture.
- No deployment mutation (Terraform, Docker, CI/CD).
- No React/frontend.
- No new dependencies.
- No docs/ROADMAP updates.
- No real patient data.
- No `--overwrite` flag (deferred; user removes dir first).
- No cloud upload (S3, AWS storage).
- No network calls.

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
- `technical_demo_only: true` in every capture file.
- No real patient data.
- No Aramis references.
- No diagnosis/replacement language (except safe negation in disclaimers/safety_notes).

## Validation checklist

```bash
# Git checks
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only

# Compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_demo_capture.py
python -m pytest -q tests/test_bremen_demo_run.py
python -m pytest -q tests/test_bremen_demo_presentation.py
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

# End-to-end capture smoke test
tmpdir="$(mktemp -d)" && \
  python -m bremen demo-run --pretty --capture-dir "$tmpdir" && \
  find "$tmpdir" -maxdepth 1 -type f -print | sort
# Expected: 3 files (summary.txt, evidence.json, manifest.json)
```

### Forbidden-pattern grep checks

```bash
# No Aramis dependency or product labels
grep -R -I -n "Aramis\|aramis\|M2Q\|BENIGN vs CANCER" \
  src/bremen/demo_capture.py src/bremen/demo_run.py src/bremen/demo_presentation.py \
  tests/test_bremen_demo_capture.py tests/test_bremen_demo_run.py tests/test_bremen_demo_presentation.py || true
# Expected: no output

# No clinical/replacement claims
grep -R -I -n "diagnosis\|diagnose\|replaces MRI\|replace MRI\|replaces biopsy\|replace biopsy\|replaces radiologist\|replace radiologist\|replaces clinician\|replace clinician" \
  src/bremen/demo_capture.py src/bremen/demo_run.py src/bremen/demo_presentation.py \
  tests/test_bremen_demo_capture.py tests/test_bremen_demo_run.py tests/test_bremen_demo_presentation.py || true
# Expected: no output (negative-test/hygiene-test assertion strings allowed with justification)

# No unsafe deserialization
grep -R -I -n "joblib\.load\|pickle\.load\|import pickle" \
  src/bremen/demo_capture.py src/bremen/demo_run.py src/bremen/demo_presentation.py \
  tests/test_bremen_demo_capture.py tests/test_bremen_demo_run.py tests/test_bremen_demo_presentation.py || true
# Expected: no output

# No H5 dependency
grep -R -I -n "\.h5\|\.hdf5\|h5py" \
  src/bremen/demo_capture.py src/bremen/demo_run.py \
  tests/test_bremen_demo_capture.py tests/test_bremen_demo_run.py || true
# Expected: no output

# No AWS/network client deps (stdlib urllib localhost is allowed)
grep -R -I -n "boto3\|botocore\|requests\|httpx" \
  src/bremen/demo_capture.py src/bremen/demo_run.py src/bremen/demo_presentation.py \
  tests/test_bremen_demo_capture.py tests/test_bremen_demo_run.py tests/test_bremen_demo_presentation.py || true
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
| Capture module | `src/bremen/demo_capture.py` — stdlib only, no network, no model loading. |
| CLI flag | `--capture-dir <directory>` on `demo-run`. |
| Capture files | 3 files: `bremen-demo-summary.txt`, `bremen-demo-evidence.json`, `bremen-demo-manifest.json`. |
| Directory creation | Yes — created (including parents) if missing. |
| File collision | `FileExistsError` — safe default. No `--overwrite` in this PR. |
| Pretty text in capture | Included when `--pretty --capture-dir` used together. |
| Fallback without `--pretty` | Summary file gets a minimal header-only text (still safe). |
| `technical_demo_only` | Required in every capture file. |
| Overwrite | Deferred (user removes dir first). |
| Cloud upload | Deferred. |

## Rollback plan

1. **Revert `src/bremen/demo_capture.py`** — delete.
2. **Revert `src/bremen/demo_run.py`** — remove `--capture-dir` additions.
3. **Revert `src/bremen/__main__.py`** — remove `--capture-dir` from demo-run subcommand.
4. **Revert `tests/test_bremen_demo_capture.py`** — delete.
5. **Revert test modifications** — revert `test_bremen_demo_run.py` and `test_bremen_cli_entrypoint.py`.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only 6 allowed files changed. No forbidden files. |
| **Capture drift** | Stdlib-only. Writes 3 files. No network, no model loading. |
| **Demo-run drift** | `--capture-dir` is additive — JSON/pretty output unchanged. Backward-compatible. |
| **Safety drift** | No unsafe deserialization, no H5, no AWS, no clinical claims. `technical_demo_only` in every file. |
| **Test drift** | 18+ new capture tests + 2 demo-run tests + 1 CLI test. Existing tests pass. |
| **Validation drift** | All validation checks pass. Forbidden-pattern greps return nothing. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Plan starts multi-tenancy, model-profile, or plugin work.
- Plan becomes docs-only.
- Plan requires AWS credentials, Terraform, Docker, or GitHub Actions changes.
- Plan requires React/frontend/package-manager files.
- Plan requires new dependencies.
- Plan requires real patient data.
- Plan requires unsafe model loading or H5 mutation.
- Plan weakens Bremen safety language.
- Implementation phase is not Agent: coder / Mode: implementation.

## Decisions summary

| Decision | Value |
|----------|-------|
| Capture module | `src/bremen/demo_capture.py` — stdlib only. |
| CLI flag | `--capture-dir <dir>` on `demo-run`. |
| Capture files | `bremen-demo-summary.txt`, `bremen-demo-evidence.json`, `bremen-demo-manifest.json`. |
| Directory | Created if missing (including parents). |
| Collision | `FileExistsError` — safe default, no overwrite. |
| Pretty text | Included when `--pretty --capture-dir` both used. |
| Fallback text | Minimal safe header if `--pretty` not used. |
| `technical_demo_only` | Required in every file. |
| Multi-tenancy | Deferred. |
| Cloud upload | Deferred. |
| Overwrite | Deferred. |
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
- `src/bremen/demo_presentation.py`
- `src/bremen/demo_smoke.py`
- `src/bremen/demo_evidence.py`
- `src/bremen/api/server.py`
- `src/bremen/api/app.py`
- `tests/test_bremen_demo_run.py`
- `tests/test_bremen_demo_presentation.py`
- `tests/test_bremen_demo_smoke.py`
- `tests/test_bremen_demo_evidence.py`
- `tests/test_bremen_cli_entrypoint.py`
- `tests/test_bremen_api_server.py`
- `tests/test_bremen_api_skeleton.py`
- `tests/test_bremen_dependency_hygiene.py`
- `.project-memory/project_contract.yml`
- `AGENTS.md`

## Files written

- `.project-memory/pr/0064-demo-readiness-capture-package/PLAN.md` (this file)

## Boundary confirmations

- confirm: PR0064 planned as demo readiness capture package: yes
- confirm: demo remains Bremen-native: yes
- confirm: capture package is not disposable: yes (versioned, reusable, testable)
- confirm: `--capture-dir` planned for demo-run: yes
- confirm: product-owner demo value planned: yes
- confirm: `technical_demo_only` preserved: yes
- confirm: JSON behavior preserved: yes
- confirm: pretty behavior preserved: yes
- confirm: request_id behavior preserved: yes
- confirm: no deployment mutation planned: yes
- confirm: no Terraform/GitHub Actions/Docker changes planned: yes
- confirm: no React/frontend planned: yes
- confirm: multi-tenancy/model-profile/plugin work deferred: yes
- confirm: no new dependencies planned: yes
- confirm: no unsafe model loading planned: yes
- confirm: no H5 mutation planned: yes
- confirm: no real patient data planned: yes
- confirm: no Aramis dependency planned: yes
- confirm: no clinical diagnosis/replacement claims planned: yes
- confirm: implementation assigned to Agent: coder / Mode: implementation: yes
- confirm: no git mutation commands run: yes
