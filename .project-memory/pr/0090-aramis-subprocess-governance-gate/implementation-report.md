# PR0090 Implementation Report

## Files Changed

| File | Action | Lines |
|------|--------|-------|
| `docs/adr/0013-aramis-process-isolated-runtime-exception.md` | CREATED | 165 lines, 7790 chars |
| No other files changed | — | — |

## ADR Strategy

Option A: New ADR-0013 created as a standalone document that supersedes
ADR-0002 only for the narrow case of process-isolated, Docker-level
Aramis runtime bundling. ADR-0002 is not modified. This preserves the
original prohibition text for audit trail and allows one-file rollback.

## ADR-0002 Prohibition Acknowledged

ADR-0013 explicitly cites ADR-0002's prohibition and acknowledges that
the prohibition would flatly block Phase 1 Docker-level Aramis bundling
without this exception. ADR-0002 remains in full force for all
product-facing surfaces (public API, UI, reports, model catalog, demo
routes, decision vocabulary).

## ADR-0013 Exception Boundary

**Permitted** (only in later implementation PRs, not PR0090):
- Process-isolated subprocess
- Separate Aramis virtualenv (`/opt/aramis-venv`)
- One-shot subprocess lifecycle
- Docker-level smoke proof
- Later gated workflow integration (Phases 2-5)

**Explicitly forbidden** (both now and in all future phases):
- In-process Aramis import
- Shared Bremen/Aramis Python site-packages
- Shared feature set
- Shared decision vocabulary
- Mapping `p_cancer` to `p_mri_needed`
- Mapping `CANCER/NON-CANCER` to `CONTINUE_MRI` or `MRI_REVIEW_DEFER`
- Mapping Aramis reliability semantics into Bremen decision_policy
- Public `/demo` exposure before a later approved PR
- Adding `aramis` to model/workflow allowlists in PR0090
- Persistent process, process pool, IPC server, or network service
- Real patient H5 data
- Copying directive Aramis report wording into Bremen surfaces
- Guessing Aramis dependencies, CLI, or output schema

## Source Access Gate

Preserved. Five explicit artifact options must be satisfied before
Docker work (Phase 1) can begin:
1. Official Aramis runtime source tree
2. Official Docker/runtime bundle
3. Dependency manifest
4. CLI entrypoint
5. Written subprocess/CLI contract

Every future implementation plan must cite the exact source/bundle used.

## Phased Sequence

| Phase | Title | PR |
|-------|-------|-----|
| 1 | Docker-level smoke proof | PR0091+ (future) |
| 2 | Provider subprocess invocation | Future |
| 3 | Checksummed artifact/manifest | Future |
| 4 | Workflow allowlist | Future |
| 5 | Safe native-result presentation | Future |

PR0090 only covers the governance prerequisite to Phase 1.

## No-Aramis Test Policy

All 19 existing `test_no_aramis_*` tests across 11 test files remain
valid for product-facing surfaces. No existing test was modified or
weakened. Future implementation PRs must scope new Docker smoke tests
to avoid the same check paths as product-facing tests.

## Validation Results

| Check | Result |
|-------|--------|
| `git rev-parse HEAD` | `0c7d2dc944b15ffd95e842afabbf724434749a80` |
| `git branch --show-current` | `0090-aramis-subprocess-governance-gate` |
| `git status --short` | Only untracked: ADR-0013 + .project-memory dirs |
| `git diff --name-only` | No modified tracked files |
| ADR exists | Yes |
| All required sections | Present |
| Process-isolation language | Present |
| Clinical-equivalence grep | Only in explicit prohibition context |
| No src/tests/Docker/requirements changes | Confirmed |
| `git diff --check` | Clean |
| Docs lint | Tables present, 165 lines |

## Scope Confirmations

- No source code modified
- No test code modified
- No Dockerfile modified
- No requirements.txt modified
- No dependencies added
- No CI/infra changes
- No runtime behavior changed
- Governance-only PR — creates ADR-0013 exception only

## Rollback

Remove `docs/adr/0013-aramis-process-isolated-runtime-exception.md` to
restore ADR-0002 prohibition to full force. No code changes needed.

## Warnings

- ROADMAP.md was not updated (optional per PLAN, skipped to keep scope
  minimal).
- `requirements.txt` comment referencing ADR-0002 was NOT updated in
  this PR. Future Phase 1 implementation PR should update it to
  reference ADR-0013 instead.
- PR0090 is governance-only. Docker Phase 1 work is deferred to
  PR0091+ after official Aramis runtime source/bundle/CLI contract is
  available.
