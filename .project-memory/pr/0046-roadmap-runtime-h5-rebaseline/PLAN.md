# PR 0046 — Plan: Roadmap Runtime/H5 Rebaseline

## 1. Title / Branch / Objective

- **Title**: Roadmap Runtime/H5 Rebaseline
- **Branch**: `0046-roadmap-runtime-h5-rebaseline`
- **Objective**: Update ROADMAP.md to reflect actual project state through PR0045, replace stale Next Execution Sequence, add H5 layout strategy section, and create AGENT_TEST_DEBUGGING_RULES.md to codify debugging protocols discovered during PR0043–PR0045 implementation. Documentation/process only — no runtime code, no tests.

---

## 2. Precondition Verification

```
$ git rev-parse --verify HEAD
8b699d53e5965d153263bdc95ee6d2da93ff982d

$ git branch --show-current
0046-roadmap-runtime-h5-rebaseline

$ git status --short
(clean — no uncommitted changes)
```

Required files all present and read:

- ROADMAP.md ✓ (full read — see drift evidence below)
- .project-memory/pr/0043-s3-h5-input-staging/PLAN.md ✓
- .project-memory/pr/0044-h5-sample-metadata-fallback/PLAN.md ✓
- .project-memory/pr/0045-h5-layout-adapter-boundary/PLAN.md ✓
- .project-memory/pr/0045-h5-layout-adapter-boundary/reviews/precommit-review.yml ✓

PR0045 confirmed merged (precommit-review.yml shows 532 tests pass, adapter boundary merged with warning-only scope deviation).

---

## 3. Current Roadmap Drift Evidence

### Problem 1: Completed foundation PRs stop at PR0022C

ROADMAP.md "Completed foundation PRs" section lists:
- PR-0001 through PR-0022C

Gap: PR0026 through PR0045 are completed but not listed. This is the most visible drift — a developer reading the roadmap sees no evidence of runtime, staging, preflight, adapter, or layout work.

### Problem 2: Stale Next Execution Sequence

The "Next Execution Sequence (post-platform-foundation)" section lists:

```
PR 0026 — Runtime HTTP service runner
PR 0027 — Model package source integration
PR 0028 — Runtime model loading boundary
PR 0030 — Roadmap/ADR amendment (App Runner pivot)
PR 0031 — ECR workflow: add stable App Runner image tag
PR 0032 — Model package fetch/staging from S3
PR 0033 — Startup model loading and readiness probe
PR 0034 — App Runner Terraform skeleton
PR 0035 — DS feature inventory and model package composition decision
PR 0036 — H5/preflight metadata gate
PR 0037 — Preprocessing bridge
PR 0038 — Inference pipeline integration
PR 0039 — Config governance ADR and gate decisions
PR-0039 — v0.1 feature schema rebaseline + inference integration
```

Every single one of these is already completed (PR0026–PR0039 mapping to actual PR0026–PR0045). The sequence presents them as future work. The duplicate/conflicting PR0039 entries (config governance AND v0.1 schema rebaseline) remain unresolved.

### Problem 3: Training Pipeline Track uses overlapping numbering

The Training Pipeline Track section uses PR0033–PR0035 numbering that overlaps with the main sequence. These are actual completed PRs (PR0034 = training pipeline, PR0035 = model publication, PR0036 = preflight gate, etc.), but the roadmap presents them as future/separate work.

### Problem 4: No H5 layout strategy

The roadmap has no section documenting:
- H5 layout adapter/plugin architecture (PR0045)
- Canonical vs calibration sample layout support
- Multi-patient H5 explicit ref requirement
- No auto-selection rule

### Problem 5: DS inventory / composite package notes are stale

The roadmap mentions an open question about Mahalanobis/Wasserstein reference statistics and a "DS/inventory PR (planned PR 0035)". This was addressed by the actual v0.1 model publication which uses the 15-feature schema with no composite package requirement.

### Problem 6: No agent debugging protocol

Despite PR0043–PR0045 discovering frequent agent-loop issues around pytest output, tail-hidden tracebacks, exception identity problems, and global test state leakage, there is no documented debugging protocol.

---

## 4. Completed PR Rebaseline Scope

The following PRs are completed and must be reflected in ROADMAP.md:

| PR | Title | Key artifact |
|----|-------|-------------|
| PR0026 | Runtime HTTP service runner | `src/bremen/api/server.py` — exposes API skeleton as service process |
| PR0027 | Model package source integration | `read_cloud_config()` + `model_package.validate_model_package()` |
| PR0028 | Runtime model loading boundary | Controlled `joblib.load()` deserialization with checksum/trust rules |
| PR0029 | Runtime model config roadmap rebaseline | ROADMAP.md amendment |
| PR0030 | App Runner pivot docs | ADR-0008 + APRANA retirement + model lifecycle |
| PR0031 | App Runner image tag | `app-runner` stable tag in ECR workflow |
| PR0032 | Model package fetch/staging from S3 | S3 model download to staging directory |
| PR0033 | Startup model loading + readiness probe | Server startup wiring, readiness endpoint |
| PR0034 | Bremen training pipeline | `Dockerfile.training`, `src/bremen/training/`, feature computation |
| PR0035 | Model package publication path | v0.1 model published to S3, manifest validation |
| PR0036 | H5 preflight gate | `run_h5_preflight()` with target/control validation |
| PR0037 | Preprocessing bridge | `run_preprocessing_bridge()` with 15-feature extraction |
| PR0038 | Inference pipeline integration | `run_inference()` end-to-end, first working prediction |
| PR0039 | v0.1 schema rebaseline + inference integration | ADR-0010, 15-column schema, portable logistic regression |
| PR0040 | S3 model startup staging | Model fetch from S3 at container startup |
| PR0041 | Runtime observability logging | `bremen.*` structured log events |
| PR0042 | Prediction job execution wiring | `handle_submit_prediction()` → job → run_inference |
| PR0043 | S3 H5 input staging | `src/bremen/h5_inputs.py`, `stage_h5_input()` |
| PR0044 | H5 sample metadata fallback | `resolve_patient_metadata()`, `patient_name_fallback` |
| PR0045 | H5 layout adapter boundary | `src/bremen/api/h5_layouts.py`, adapter protocol + calibration support |

### Current state summary for ROADMAP.md

**Current state (to be written into ROADMAP.md):**
- Runtime service exists and is operational on App Runner.
- Runtime model is loaded at startup from a checksum-verified model package (S3 staging + joblib).
- App Runner proving path is operational (S3 staging, inference, prediction jobs).
- S3 model startup staging works (container start → S3 fetch → checksum → joblib.load).
- S3 H5 input staging works (`h5_uri` accepted, downloaded, checksum verified, staged locally).
- Prediction job execution is wired (submit → validate → stage → preflight → bridge → inference → completed/failed).
- H5 metadata fallback is implemented (primary `/patient/id`, fallback sample-level `patient_name` with source tracking).
- H5 layout adapter boundary exists (abstract adapter protocol, detect/resolve, Canonical + CalibrationSample adapters, layout registry).
- Calibration sample layout is supported at metadata/context level only (preflight passes, preprocessing not yet implemented).
- Calibration sample preprocessing is not yet implemented (scheduled PR0047).

---

## 5. New Next Execution Sequence

Replace the stale sequence with:

| PR | Title | Description |
|----|-------|-------------|
| **PR0047** | **Calibration sample preprocessing bridge** | Map calibration sample layout into runtime preprocessing without changing inference math. Use explicit target/control sample refs. Read integration i/q arrays safely. Produce the existing 15-feature v0.1 schema. No clinical claims. |
| **PR0048** | **HTTP prediction explicit-ref wiring** | Ensure `target_scan_ref` / `control_scan_ref` are carried through HTTP → staging → preflight/layout context → preprocessing/inference. Production smoke with explicit refs. |
| **PR0049** | **Production end-to-end smoke hardening** | S3 H5 → explicit sample refs → checksum → layout adapter → preprocessing → inference → completed job/result. Document expected failures and safe errors. |
| **PR0050** | **Model/version readiness endpoint cleanup** | Align `/model/version` `model_status` with actual `model_ready` state. Preserve safe metadata only. |
| **PR0051** | **Config governance ADR/gates** | Close G-CFG-1/G-CFG-2/G-CFG-3 or explicitly defer with rationale. Config audit/history architecture only, no UI unless separately planned. |
| **PR0052** | **Matador boundary / system-of-record adapter skeleton** | Contract only, no local path dependency, no raw patient data logging. |
| **PR0053** | **Decision-support report/output wrapper** | Controlled output around prediction result. No diagnosis, no clinical validation claim. |
| **PR0054** | **Release readiness / operator notes** | Production checklist, rollback, smoke commands, model artifact notes. |

### Rationale for new sequencing

- PR0047 is next because the adapter boundary (PR0045) cannot produce predictions until preprocessing is wired for calibration layout.
- PR0048 pipes refs through the HTTP layer — needed before production smoke with multi-patient H5s works.
- PR0049 validates the complete S3 → prediction production path.
- PR0050–PR0054 are platform readiness items that build on having a working prediction path.
- No hard dates — execution order is sequential for the first three, with later items subject to prioritization.

---

## 6. H5 Layout Strategy Section

Add to ROADMAP.md a new section "H5 Layout Strategy" with:

### Core principles

- H5 layouts are adapter/plugin based (`H5LayoutAdapter` protocol). New H5 layouts add an adapter + tests, not hardcoded conditionals in preflight.
- The canonical layout (single patient, `/patient/id`, `/scans/target/`, `/scans/contralateral/`) remains fully supported with zero regression.
- The calibration sample layout (multiple patients under `/calib_*/sample_*/`, `sample/patient_name`, `sample/sample_type`, `sets/set_*/integration/i/q`) is supported through the `CalibrationSampleH5LayoutAdapter` at the metadata/context/preflight level.
- Multi-patient H5 containers require explicit `target_scan_ref` / `control_scan_ref` to select which samples to process.
- No automatic first-patient or first-sample selection is permitted under any adapter.
- Raw patient identifiers (`patient_name`, `patient_id`) must not be logged. Raw scan arrays must not be logged.
- Future H5 layouts must add adapters and passing tests. Adapters must include `detect()` and `resolve_prediction_context()` methods.

### Current adapter inventory

| Adapter | Detection trigger | Status |
|---------|------------------|--------|
| CanonicalH5LayoutAdapter | `/scans/target/measurements` exists | Production — supported |
| CalibrationSampleH5LayoutAdapter | `/calib_*` groups with `sample/patient_name` + `sample/sample_type`, no `/scans/target/measurements` | Preflight metadata/context only — preprocessing in PR0047 |

---

## 7. Agent Debugging Rules Plan

Create new file `.project-memory/AGENT_TEST_DEBUGGING_RULES.md` with:

### Title

Agent Test Debugging Protocol

### Scope

This protocol applies to all agent-driven test debugging during Bremen development. It is required reading for any agent discovering or debugging test failures during implementation or review.

### Rules

**Rule 1: Do not use tail/head on failing pytest output.**
- `tail` and `head` truncate exception context, making root cause undiagnosable.
- The first failing run must capture the complete output.

**Rule 2: First failing run command.**
```bash
python -m pytest -q -x --tb=long -vv
```
- `-x` stops at first failure.
- `--tb=long` prints full traceback with variable values.
- `-vv` shows verbose diff for assertion errors.
- If the output is too long to inspect, proceed to Rule 3.

**Rule 3: Isolate the single failing test.**
```bash
python -m pytest -q <test-path>::<test-name> -vv --tb=long
```
- Run just the failing test.
- No noise from passing tests.
- Full traceback visible.

**Rule 4: Anti-loop rule.**
- After 3 unsuccessful attempts or 20 minutes on the same failure family, **stop and classify**.
- Do not make blind production-code changes after the third attempt.
- Classification categories:
  - **product regression**: A change broke existing behavior. Revert or fix.
  - **brittle test assertion**: Assertion depends on implementation detail or ordering. Fix the test.
  - **exception identity / import-order**: Exception is the right type and message but pytest.raises does not catch it. Check import paths — exception classes imported through different module paths are different Python types.
  - **global state leakage**: Test passes alone but fails when run after other test files. Look for shared mutable state (`ModelState`, loggers, module-level caches). Add `reset_for_tests()` or fixture isolation.
  - **test order dependency**: Tests assume prior test state. Pytest should be stateless — fix the fixture or add cleanup.
  - **environment issue**: Missing env vars, wrong working directory, incompatible Python version, missing system packages.

**Rule 5: Expected exception text visible but pytest.raises does not catch it.**
- Suspect exception class identity / import-order issue.
- Verify the exception being raised is literally the same class as the one in the `except` clause / `pytest.raises`.
- Check that the exception module is imported at the top of the test file, not conditionally.

**Rule 6: Test passes alone but fails after other files.**
- Suspect global state leakage.
- Likely candidates: `ModelState` singleton, module-level caches, global loggers with handlers attached, `sys.path` modifications.
- Add `ModelState.reset_for_tests()` in fixtures or cleanup.

**Rule 7: Test isolation preferences.**
- Prefer fixing test isolation (fixtures, cleanup, reset) over changing production code.
- Prefer centralised exception imports (one canonical module) over duplicating exception class references.
- Do not add sleep/timing-based workarounds. If timing matters, use pytest-timeout or explicit wait loops with backoff.

**Rule 8: No external dependencies in unit tests.**
- No real AWS, Docker, Terraform, or network calls by default.
- No real H5 files or model artifacts in unit tests — use synthetic data.
- All real-resource tests must be skipped by default (pytest.mark.skipif with env var guard).

**Rule 9: No sensitive data in logs or exceptions.**
- No raw patient identifiers.
- No full S3 URIs.
- No raw feature values.
- No raw scan arrays.
- No secrets, account IDs, or registry URLs.

---

## 8. Preserved Decisions/Gates

ROADMAP.md must preserve all current architectural decisions:

### Runtime target decision
- App Runner near-term proving/testing target
- ECS Fargate long-term primary production target
- APRANA retired

### Model binding lifecycle
- No model in Docker image
- Startup load only — no per-request loading
- Checksum verification before `joblib.load()`
- No hot-swap
- New model version = new deployment / rolling replacement

### Decision gates
- G-API-1: DECIDED — async submit → poll
- G-API-2: DECIDED — ECS Fargate (primary), App Runner (near-term)
- G-INFRA-1: DECIDED — Terraform
- G-CFG-1: OPEN — build vs. adopt config management
- G-CFG-2: OPEN — DynamoDB vs. other state store
- G-CFG-3: OPEN — JSON Schema vs. Pydantic vs. custom validation
- G-DEP-1: OPEN — container repo merge of feat/v0_3

### Config governance
- Config separate from model
- Versioned, timestamped, auditable, reproducible
- Change classes: A (safe ops), B (decision-adjacent), C (model-binding), D (structural-forbidden)
- No config UI/API/database implementation in current scope

---

## 9. Non-Goals

This PR explicitly does NOT:
- Change any runtime code
- Change any tests
- Edit any ADR files
- Edit docs/architecture.md
- Edit Dockerfile or Dockerfile.training
- Edit Terraform or GitHub Actions
- Edit requirements.txt or pyproject.toml
- Deploy to App Runner
- Run production smoke
- Commit H5 or model artifacts
- Add clinical claims
- Add secrets, account IDs, or registry URLs

---

## 10. Allowed Files

- ROADMAP.md — update current state, replace next execution sequence, add H5 layout strategy section, preserve decisions/gates
- .project-memory/AGENT_TEST_DEBUGGING_RULES.md — new file with test debugging protocol
- .project-memory/pr/0046-roadmap-runtime-h5-rebaseline/PLAN.md — this plan
- .project-memory/pr/0046-roadmap-runtime-h5-rebaseline/reviews/plan-review.yml — future review artifact
- .project-memory/pr/0046-roadmap-runtime-h5-rebaseline/reviews/precommit-review.yml — future review artifact

---

## 11. Forbidden Files

- src/**
- tests/**
- docs/adr/**
- docs/architecture.md
- Dockerfile
- Dockerfile.training
- infra/**
- .github/**
- requirements.txt
- pyproject.toml
- Real *.h5, *.hdf5, *.joblib, *.pkl, *.npy, *.npz artifacts
- Secrets, account IDs, access keys, registry URLs

---

## 12. Validation Checklist

```bash
# Python doc sanity check
python - <<'PY'
from pathlib import Path
for p in [
    Path("ROADMAP.md"),
    Path(".project-memory/AGENT_TEST_DEBUGGING_RULES.md"),
]:
    text = p.read_text()
    assert "APRANA" in text or p.name != "ROADMAP.md"
    assert "0047" in text or p.name != "ROADMAP.md"
    assert "tail" in text or p.name != "AGENT_TEST_DEBUGGING_RULES.md"
print("docs sanity ok")
PY

# Verify new sections present
grep -n "PR0047\|Calibration sample preprocessing bridge\|H5 layout strategy\|Agent test debugging" ROADMAP.md

# Verify debugging rules present
grep -n "tail\|Anti-loop\|exception identity\|global state leakage" \
  .project-memory/AGENT_TEST_DEBUGGING_RULES.md

# Verify only allowed files changed
git diff --name-only

# Verify no source/test/infra/dependency changes
git diff --name-only -- src tests docs/adr docs/architecture.md \
  Dockerfile Dockerfile.training infra .github requirements.txt pyproject.toml
# Must output nothing

# No artifact leaks
git ls-files "*.h5" "*.hdf5" "*.joblib" "*.pkl" "*.npy" "*.npz"

# Verify stale sequence is gone
grep -c "PR 0026\|PR 0027\|PR 0028\|PR 0030\|PR 0031" ROADMAP.md || true
# Should output "0" or "0 matches"
```

---

## 13. Rollback Plan

1. **Immediate rollback**: `git revert HEAD` on `0046-roadmap-runtime-h5-rebaseline` branch
2. Verify revert:
   - `git diff --name-only` — no changes
   - `python -m pytest -q` — 532+ tests pass (no code changed, but verify no regression)
3. Open revert PR with label `revert/0046`

### Partial rollback (rules only)

If only the agent debugging rules file causes issues, revert that file and keep the ROADMAP.md updates. The debugging rules are advisory and can be reintroduced in a follow-up PR.

---

## 14. Implementation Agent Assignment

**Implementation agent**: coder

---

PLAN COMPLETE: yes

BLOCKERS: none

WARNINGS:
1. ROADMAP.md is a large file — the implementation agent must be careful to read all existing content once before editing to avoid accidental deletion of preserved decisions.
2. The Training Pipeline Track section uses overlapping PR0033–PR0035 numbering. The implementation agent should either renumber it (e.g., PR0034-T, PR0035-T) or reframe it as "Training Pipeline (completed)" with a reference to the main sequence.
3. The Product Track sequence (items 1–12 in the original roadmap) is very stale — most items are superseded by actual execution. The agent should decide whether to remove it or reframe it as historical context.
4. G-DEP-1 remains OPEN — container dependency version pinning is not yet resolved.

FILES CHANGED:
- `.project-memory/pr/0046-roadmap-runtime-h5-rebaseline/PLAN.md` — written

ROADMAP DRIFT SUMMARY:
- Completed foundation PRs list stops at PR0022C (missing PR0026–PR0045)
- Next Execution Sequence lists 12 already-completed PRs as future work
- PR0039 appears twice with conflicting descriptions (config governance vs v0.1 schema rebaseline)
- Training Pipeline Track uses overlapping numbering with main sequence
- No H5 layout strategy section exists
- DS inventory/composite package notes are stale (v0.1 model published, no composite needed)
- No agent test debugging protocol exists

COMPLETED STATE REBASELINE SUMMARY:
20 PRs (PR0026–PR0045) completed. Runtime service operational on App Runner. Full pipeline: S3 stage → preflight → layout adapter → preprocessing bridge → inference → prediction result. H5 metadata fallback implemented. H5 layout adapter boundary exists with canonical + calibration adapters.

NEXT SEQUENCE SUMMARY:
PR0047 Calibration sample preprocessing bridge → PR0048 HTTP explicit-ref wiring → PR0049 Production end-to-end smoke → PR0050 Model/version endpoint cleanup → PR0051 Config governance → PR0052 Matador boundary → PR0053 Decision-support wrapper → PR0054 Release readiness.

H5 STRATEGY SUMMARY:
Adapter/plugin based (H5LayoutAdapter protocol). Canonical layout supported. Calibration layout supported at metadata/context level. Multi-patient H5 requires explicit refs. No auto-selection. No raw identifiers in logs. Future layouts add adapters + tests.

AGENT DEBUGGING RULES SUMMARY:
9 rules. No tail/head on pytest output. Use `-x --tb=long -vv` first, then isolate single test. Anti-loop: stop after 3 attempts / 20 min and classify. Fix test isolation, not production code. No external deps in unit tests. No sensitive data in logs.

PRESERVED DECISIONS/GATES:
App Runner (near-term) + ECS Fargate (long-term). APRANA retired. Model lifecycle: no in-image, startup load, checksum enforced, no hot-swap. Gates: G-API-1/2/INFRA-1 DECIDED, G-CFG-1/2/3/DEP-1 OPEN.

NON-GOALS:
No runtime code, no tests, no ADR edits, no infra/CI/CD/Docker/dependency changes, no deployment, no smoke, no artifacts, no clinical claims, no secrets.

VALIDATION PLAN:
Python doc sanity check (APRANA in ROADMAP, 0047 in ROADMAP, tail in AGENT rules). `git diff --name-only` for allowed files only. grep for new sections. Zero changes to src/tests/infra/Dockerfile/dependency files.

IMPLEMENTATION AGENT ASSIGNMENT: coder
