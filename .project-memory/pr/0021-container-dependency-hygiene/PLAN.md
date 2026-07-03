# PR 0021 — Plan Container Dependency Hygiene

Author: plan
Mode: planning only
Branch: 0021-container-dependency-hygiene

## Objective

Remove local-machine dependency drift from `requirements.txt` and make container dependency installation reproducible for CI/deployment.

This PR fixes the `-e /Users/sad/dev/container` local-path defect without re-pinning the private container dependency from `feat/v0_3` to `main`. G-DEP-1 remains OPEN. The event-triggered re-pin to `main` is future work, deferred until the external container repo merges `feat/v0_3` to `main`.

## Context

PR 0019 added the API contract and async microservice skeleton. The next deployment-critical blocker is dependency hygiene before PR 0022 (Terraform/ECR/ECS/S3 IaC).

### Current dependency audit (requirements.txt)

```
numpy>=1.26,<3
...  (public PyPI packages)
-e /Users/sad/dev/container
-e /Users/sad/dev/XRD-preprocessing[dev]
-e /Users/sad/dev/Aramis[dev]
```

Three local-machine editable install paths, none of which are reproducible for CI or deployment.

### How each package is actually installed in CI (quality.yml)

| Package | CI source | How it's provided |
|---------|-----------|-------------------|
| xrd-preprocessing | `git+https://github.com/Eos-Dx/XRD-preprocessing.git` | CI workflow runs `pip install "git+https://..."` AND it's in `pyproject.toml` as a git dependency |
| container | `git+https://github.com/Eos-Dx/container.git@feat/v0_3-eoscan-session-container` | CI workflow runs `pip install "git+https://...@feat/v0_3-..."` |
| Aramis | Not installed by CI | No longer an active dependency for Bremen |

### ADR-0005 commitment

ADR-0005 states the `requirements.txt` local-path defect is fixed in this delegated PR (0021). Re-pinning from `feat/v0_3` to `main` is separately event-triggered via G-DEP-1 and is NOT done here.

## Exact allowed implementation files

The coder may create or modify exactly these files:

1. **`requirements.txt`** — MODIFY. Remove local-machine editable paths. Add the container dependency using the same git URL that CI uses.
2. **`tests/test_bremen_dependency_hygiene.py`** — NEW. Verification that requirements.txt no longer contains local machine paths.

Optional only if strongly justified:

3. **`docs/adr/0005-container-dependency-stabilization.md`** — MODIFY (only if current text contradicts actual PR 0021 scope).
4. **`ROADMAP.md`** — MODIFY (only if current PR 0021 description is inconsistent with actual scope).

PLAN.md recommends NO modifications to ADR-0005 or ROADMAP.md. The current ADR-0005 says "The requirements.txt local-path defect is fixed in the same delegated PR as the re-pin work, since both are 'container dependency hygiene.'" The task says this PR cannot re-pin. There is a minor tension, but ADR-0005 states this as a recommendation ("is fixed in the same delegated PR"), not an inviolable rule. The PR can fix the local-path defect now and defer the re-pin to a future event-triggered PR. If the coder or reviewer finds this tension too ambiguous, they may update ADR-0005 to clarify the split scope, but the default is to leave ADR-0005 and ROADMAP.md unchanged.

## Exact forbidden files

- `src/**` — no source code changes
- `docs/api_contract.md`, `docs/architecture.md` — no API/architecture changes
- `docs/adr/0001-*.md` through `docs/adr/0004-*.md`, `docs/adr/0006-*.md` — read-only
- `README.md`, `docs/roadmap.md`, `docs/machine_learning_concept.md`, `docs/repository_cleanup.md`
- `.github/**`, `Dockerfile`, `.dockerignore` — no CI/Docker changes
- `pyproject.toml` — no metadata changes
- `sonar-project.properties`, `environment.yml`, `Makefile`
- `config/**`, `examples/**`, `tests/data/**`
- `agents/**`
- Any H5/HDF5 files
- Any model/joblib/pkl/npy/npz artifacts
- Terraform/CDK/CloudFormation/IaC files

## Required reads (completed for this PLAN.md)

- `requirements.txt` — confirmed 3 local-machine editable paths
- `.github/workflows/quality.yml` — confirmed CI install commands for private deps
- `docs/adr/0005-container-dependency-stabilization.md` — ADR scope and G-DEP-1 definition
- `ROADMAP.md` — confirms G-DEP-1 is OPEN, PR 0021 description
- `.project-memory/project_contract.yml` — safety invariants
- `pyproject.toml` — confirms xrd-preprocessing is already a git dependency
- `AGENTS.md` — agent role definitions

## Implementation phase assignment

- **Agent**: coder
- **Mode**: implementation

## Dependency hygiene summary

### Changes to requirements.txt

Remove these three lines entirely:
```
-e /Users/sad/dev/container
-e /Users/sad/dev/XRD-preprocessing[dev]
-e /Users/sad/dev/Aramis[dev]
```

Add this line to replace the container dependency:
```
container @ git+https://github.com/Eos-Dx/container.git@feat/v0_3-eoscan-session-container
```

**Rationale for each removal:**

1. **`-e /Users/sad/dev/container`** — Replaced with the non-editable git URL pin that matches CI's install command. The pin stays at `feat/v0_3`; G-DEP-1 is not closed.

2. **`-e /Users/sad/dev/XRD-preprocessing[dev]`** — Removed entirely. `pyproject.toml` already lists `xrd-preprocessing @ git+https://github.com/Eos-Dx/XRD-preprocessing.git@v0.1.5-beta` as a core dependency. The CI workflow also installs it explicitly. The editable local path in `requirements.txt` is redundant and introduces local-machine drift.

3. **`-e /Users/sad/dev/Aramis[dev]`** — Removed entirely. Aramis is not an active dependency for Bremen (per ADR-0002). This line was a stale artifact from the fork. No replacement needed.

### What does NOT change

- `pyproject.toml` — unchanged. The xrd-preprocessing git dependency stays.
- `.github/workflows/quality.yml` — unchanged. CI install commands remain the same.
- The `feat/v0_3` pin for `container` in `requirements.txt` — unchanged (copied from CI's existing URL).
- G-DEP-1 — remains OPEN. This PR does not close it.
- No re-pin to `container` `main`. This PR uses the same feature-branch pin that CI already uses.

## G-DEP-1 boundary

- **G-DEP-1 remains OPEN.**
- This PR does NOT re-pin `feat/v0_3` to `main`.
- This PR does NOT claim `container` `main` is ready.
- This PR does NOT change `VERSION_REGISTRY` expectations.
- The event-triggered re-pin (when the container repo merges `feat/v0_3` to `main`) remains future work.
- This PR's change is purely mechanical: replace non-reproducible local paths with the same reproducible git URL that CI already uses.

## Testing strategy

### New test file: `tests/test_bremen_dependency_hygiene.py`

Tests must verify:

1. `requirements.txt` does not contain `/Users/` (no local macOS home paths).
2. `requirements.txt` does not contain `/home/` (no local Linux home paths).
3. `requirements.txt` does not contain `-e ` (no editable local absolute paths or local editable references).
4. `requirements.txt` does not contain local machine paths to `container`.
5. If a `container` Git dependency exists in `requirements.txt`, it references `github.com/Eos-Dx/container.git` (not a local path or unknown host).
6. G-DEP-1 is not marked DECIDED in `ROADMAP.md` (verify the gate remains OPEN).
7. Import safety check: reading and parsing `requirements.txt` does not import `joblib`, `pickle`, `h5py`, or any AWS SDK (the test file itself is lightweight).

### What tests must NOT do

- Install dependencies (`pip install`).
- Modify `requirements.txt` or any other file during test execution.
- Call any Bremen runtime code that requires private dependencies.
- Read H5/HDF5 files.
- Load model artifacts.

## Non-goals

- No source code changes (`src/**`).
- No API changes.
- No model package logic changes.
- No CI workflow changes (default is no `.github` changes — only modify if requirements.txt cannot be made consistent without them, which is not the case here).
- No Dockerfile changes.
- No `pyproject.toml` changes.
- No dependency installation or `pip install` in this PR.
- No Terraform/IaC.
- No AWS/ECR/ECS/S3 work.
- No H5/HDF5 reads.
- No model/joblib artifacts.
- No G-DEP-1 closure.
- No re-pin to `container` `main`.
- No APRANA work.
- No clinical/product docs changes.
- No changes to `docs/adr/` or `ROADMAP.md` unless found factually inconsistent (currently not inconsistent, though ADR-0005 has a minor scope tension noted above).

## Validation checklist

The implementation phase (coder) must execute these checks:

```bash
# 1-2) Baseline state
git rev-parse --verify HEAD
git branch --show-current

# 3-4) Working tree
git status --short
git diff --name-only

# 5) Verify local paths are removed from requirements.txt
grep -n "/Users\|/home\|-e /" requirements.txt || echo "No local paths found (expected)"

# 6) Verify container references are to the git URL, not local
grep -n "container.git" requirements.txt .github/workflows/quality.yml

# 7) G-DEP-1 remains OPEN in ROADMAP.md
grep -n "G-DEP-1" ROADMAP.md
grep -n "OPEN" ROADMAP.md

# 8-13) Compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_dependency_hygiene.py
python -m pytest -q tests/test_bremen_api_contract.py
python -m pytest -q tests/test_bremen_api_skeleton.py
python -m pytest -q tests/test_bremen_model_package.py
python -m pytest -q tests/test_bremen_config_loading.py
python -m pytest -q tests/test_bremen_import_identity.py
python -m pytest -q

# 14) CLI help still works
python -m bremen --help

# 15) No forbidden file changes
git diff --name-only -- src docs/api_contract.md docs/architecture.md docs/adr/0001-bremen-product-identity.md docs/adr/0002-twin-product-document-separation.md docs/adr/0003-bremen-microservice-api-architecture.md docs/adr/0004-bremen-configuration-management-strategy.md docs/adr/0006-multi-target-deployment-and-iac.md README.md docs/roadmap.md docs/machine_learning_concept.md docs/repository_cleanup.md .github Dockerfile .dockerignore pyproject.toml sonar-project.properties environment.yml Makefile config examples tests/data agents

# 16) No model artifacts created
git diff --name-only | grep -E "\.(h5|hdf5|joblib|pkl|npy|npz)$" || true

# 17) Safety checks
find . -path "./.git" -prune -o -path "./venv" -prune -o -path "./.venv" -prune -o -type f \( -name "*.h5" -o -name "*.hdf5" -o -name "*.joblib" -o -name "*.pkl" -o -name "*.npy" -o -name "*.npz" \) -print
find . -name ".DS_Store" -print
```

## Rollback plan

If the requirements.txt changes cause issues:

1. **Revert `requirements.txt`** — restore the three local-path lines. The previous state was functionally usable on the developer's local machine.
2. **Revert `tests/test_bremen_dependency_hygiene.py`** — delete the file.
3. **Revert `docs/adr/0005-container-dependency-stabilization.md`** — if modified, restore to pre-PR-0021 version.
4. **Revert `ROADMAP.md`** — if modified, restore to pre-PR-0021 version.

The rollback preserves all API, model, and application code. Only dependency declarations and their tests are affected.

## Follow-up PRs

- **PR 0022** — Terraform/ECR/ECS/S3 IaC skeleton (delegated from ADR-0006, uses G-API-2/G-INFRA-1 decisions)
- **PR 0020** — Cloud-aware config sourcing (delegated from ADR-0004, depends on PR 0019)
- **Future event-triggered PR (G-DEP-1)** — Re-pin `container` dependency to `main` after the external container repo merges `feat/v0_3` to `main`. Re-verify `VERSION_REGISTRY` against new `main`.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only `requirements.txt` and `tests/test_bremen_dependency_hygiene.py` changed. ADR-0005 and ROADMAP.md optionally only if factually inconsistent. |
| **Dependency drift** | Three local-path lines removed (`/Users/sad/dev/container`, `/Users/sad/dev/XRD-preprocessing[dev]`, `/Users/sad/dev/Aramis[dev]`). Container dependency replaced with same CI git URL pin at `feat/v0_3`. |
| **G-DEP-1 boundary drift** | G-DEP-1 remains OPEN. No re-pin to `container` main. No change to VERSION_REGISTRY expectations. Event-triggered re-pin deferred. |
| **Source/API drift** | No source code or API changes. No source files in `src/` modified. |
| **CI/Docker drift** | No CI workflow or Dockerfile changes. The changed `requirements.txt` is compatible with both CI install commands and local `pip install -r requirements.txt`. |
| **Test drift** | Hygiene test verifies no local paths, git-hosted container URL, and G-DEP-1 remains OPEN. Existing API/model/config tests pass unchanged. |
| **Validation drift** | All validation checks pass. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Plan closes G-DEP-1 (marks it DECIDED in ROADMAP.md).
- Plan re-pins `container` dependency to `main` without external event evidence.
- Plan modifies source/API/model code (`src/**`).
- Plan modifies CI/Docker/IaC by default (`.github/**, Dockerfile, .dockerignore`).
- Plan adds dependency installation as part of this PR.
- Plan creates model artifacts.
- Plan reads H5/HDF5 files.
- Plan changes unrelated docs by default.
- Plan makes APRANA technical claims.
- Any file outside the four allowed files is changed (requirements.txt, test file, ADR-0005, ROADMAP.md).

## Decisions summary

### Allowed files
1. `requirements.txt` — MODIFY
2. `tests/test_bremen_dependency_hygiene.py` — NEW
3. `docs/adr/0005-container-dependency-stabilization.md` — MODIFY (optional, only if factually inconsistent)
4. `ROADMAP.md` — MODIFY (optional, only if factually inconsistent)

### Forbidden files
- `src/**`, `docs/api_contract.md`, `docs/architecture.md`, all ADRs except 0005, README.md, all other docs
- `.github/**`, `Dockerfile`, `.dockerignore`, `pyproject.toml`, all other infrastructure files
- `config/**`, `examples/**`, `tests/data/**`, `agents/**`
- H5/HDF5, model artifacts, IaC files

### Dependency hygiene summary
- Remove 3 local-path lines: `container`, `XRD-preprocessing[dev]`, `Aramis[dev]`.
- Add `container @ git+https://github.com/Eos-Dx/container.git@feat/v0_3-eoscan-session-container` to keep the container dependency reproducible.
- xrd-preprocessing is already in pyproject.toml as a git dependency — no replacement needed.
- Aramis is not an active Bremen dependency — no replacement needed.

### G-DEP-1 boundary summary
- G-DEP-1 remains OPEN.
- No re-pin to `container` `main`.
- Event-triggered re-pin remains future work.
- The pin stays at `feat/v0_3` (same URL CI already uses).

### Testing summary
1 test file, 7 scenarios: no /Users/ paths, no /home/ paths, no `-e` paths, no local container path, container URL references github.com, G-DEP-1 not DECIDED, import safety.

### Validation summary
17 checks: git state, grep for local paths, container git URL, G-DEP-1 OPEN, compileall, all existing tests, CLI help, forbidden path check, model artifact scan, .DS_Store.

### Follow-up sequencing
PR 0022 (Terraform IaC) → PR 0020 (cloud config) → future G-DEP-1 event PR (container re-pin).

## Exact human commit instructions for planning artifacts

This PLAN.md is a planning artifact only. No implementation files have been created or modified.

1. Planner writes this file: `.project-memory/pr/0021-container-dependency-hygiene/PLAN.md`
2. Human runs: `git add .project-memory/pr/0021-container-dependency-hygiene/PLAN.md`
3. Human runs: `git commit -m "PR 0021 — Plan container dependency hygiene"`
4. Human pushes the branch for plan-review.
5. After plan-review approves, the coder implements the allowed files.

## Files read

- `requirements.txt`
- `.github/workflows/quality.yml`
- `docs/adr/0005-container-dependency-stabilization.md`
- `ROADMAP.md`
- `.project-memory/project_contract.yml`
- `pyproject.toml`
- `AGENTS.md`

## Files written

- `.project-memory/pr/0021-container-dependency-hygiene/PLAN.md` (this file)

## Files intentionally ignored

- All source files (`src/**`)
- All API files (already implemented in PR 0019)
- All model package files (already implemented in PR 0013)
- All CI, Docker, IaC files (unchanged by default)
- All docs not in the allowed set
- Any H5/HDF5 or model artifact files

## Boundary confirmations

- confirm: PR 0021 planned: yes
- confirm: local requirements path cleanup planned: yes
- confirm: G-DEP-1 remains OPEN: yes
- confirm: no container main re-pin planned without external event: yes
- confirm: no source/API/model code changes planned: yes
- confirm: no CI/Docker/IaC changes planned by default: yes
- confirm: no dependency installation planned: yes
- confirm: no H5/HDF5 reads planned: yes
- confirm: no model artifacts planned: yes
- confirm: no implementation files modified: yes
- confirm: no git mutation commands run: yes
