# PR 0006 — Plan Fast CI Coverage and Dependency Cache

Author: plan
Mode: planning only
Branch: 0006-ci-coverage-cache

## Objective

Add reliable coverage reporting with threshold enforcement and safe dependency caching for faster CI. This is a small, focused infrastructure update — no Docker publish, no GHCR, no deployment, no runtime changes.

## Context

PR 0005 added the initial CI/SonarCloud/Docker skeleton and is green. The current `.github/workflows/quality.yml` already runs:

- `pytest-cov` with `--cov=src/bremen`, `--cov-fail-under=80`, and `coverage.xml` output
- SonarCloud scan that ingests `coverage.xml`
- Full pytest suite

What is missing:
- **Dependency caching**: Every CI run re-downloads all pip dependencies from scratch, including the private `xrd-preprocessing` and `container` packages. This adds 30-60 seconds per run.
- **Coverage path alignment in SonarCloud**: The coverage report path is passed via workflow args (`-Dsonar.python.coverage.reportPaths=coverage.xml`) but is not declared in `sonar-project.properties`. Adding it there makes it explicit.
- **Coverage target name**: The current `--cov=src/bremen` uses the source path. The task prefers `--cov=bremen` (the installed package name). Both work, but `--cov=bremen` is the standard convention for installed packages.

PR 0006 adds these three small changes. Nothing more.

## Infrastructure-track classification

This PR belongs to the **infrastructure/delivery track**. It is not a product quest or runtime feature quest.

It is sequenced before product/runtime features because reliable CI and fast feedback are prerequisites for subsequent development work.

**Known roadmap discrepancy**: `docs/roadmap.md` and `docs/repository_cleanup.md` currently describe PR 0006 as the "Unified Bremen Entrypoint and Config Discovery/Loading" PR. This PR (0006) covers only coverage and caching. The entrypoint work is deferred to a later PR. The roadmap cannot be updated in this PR because `docs/**` is forbidden by the task. The roadmap will be updated in the entrypoint PR or a separate documentation PR.

## Non-goals

This PR does not:
- Change Dockerfile, .dockerignore, or activate the commented-out Docker smoke job
- Add GHCR publish, Docker push, or image publishing of any kind
- Deploy infrastructure (no AWS, ECR, Kubernetes, Helm)
- Change runtime behavior, preprocessing, inference, or training
- Change H5 handling, model/joblib handling, or config handling
- Implement config discovery or config validation
- Change docs, README, or AGENTS.md
- Change pyproject.toml, environment.yml, Makefile, or requirements.txt
- Add SSH key or SSH-based dependency access flows

## Allowed implementation files

The coder may create or modify exactly these files:

1. **`.github/workflows/quality.yml`** — MODIFY. Add pip dependency caching using `actions/setup-python@v5` built-in cache. Update `--cov=src/bremen` to `--cov=bremen` if desired.
2. **`sonar-project.properties`** — MODIFY only if coverage path alignment is needed. Add `sonar.python.coverage.reportPaths=coverage.xml` if not already declared.
3. **`.project-memory/pr/0006-ci-coverage-cache/PLAN.md`** — this file, written by planner.
4. **`.project-memory/pr/0006-ci-coverage-cache/reviews/plan-review.yml`** — written later by plan-review role.

No other files may be created or modified.

## Forbidden files

- `Dockerfile` — not modified
- `.dockerignore` — not modified
- `README.md` — not modified
- `AGENTS.md` — not modified
- `docs/**` — not modified (roadmap discrepancy noted above)
- `.project-memory/memory_index.yml` — not modified
- `src/**` — not modified
- `tests/**` — not modified
- `config/**` — not modified
- `examples/**` — not modified
- `pyproject.toml` — not modified
- `environment.yml` — not modified
- `Makefile` — not modified
- `requirements.txt` — not modified
- `.gitignore` — not modified
- `packaging/**` — not modified
- `agents/**` — not modified
- Any H5/HDF5 files — not modified
- Any binary/model artifacts — not modified

## Current CI baseline

The current `.github/workflows/quality.yml` implements:

- Trigger on push (any branch), pull_request, and workflow_dispatch
- Single `test` job on `ubuntu-latest`
- Python 3.13 via `actions/setup-python@v5`
- Private dependency access via `BREMEN_CI_GITHUB_TOKEN` (token-based git config override)
- `pip install` of `xrd-preprocessing`, `container` (feat/v0_3 branch), `bremen` package, and `pytest-cov`
- Dependency import proof (`xrd_preprocessing`, `container`, `container.registry.VERSION_REGISTRY` asserts `0_3`)
- `python -m compileall src tests`
- `python -m pytest` with `--cov=src/bremen --cov-report=term-missing --cov-report=xml:coverage.xml --cov-fail-under=80 -q`
- SonarCloud scan via `SonarSource/sonarqube-scan-action@v6` with `coverage.xml`
- GitHub token cleanup step (runs always)
- Commented-out Docker smoke job (`# TODO(PR-0006)`)

## Coverage design

### Changes

1. **Update coverage target from `--cov=src/bremen` to `--cov=bremen`** — This uses the installed package name rather than the source path. Both resolve to the same code. `--cov=bremen` is the standard convention for installed packages.

2. **Keep `--cov-fail-under=80`** — The threshold is already at 80% and passing.

3. **Keep `--cov-report=xml:coverage.xml`** — Already generated and fed to SonarCloud.

4. **Keep `--cov-report=term-missing`** — Shows which lines are uncovered in CI output.

### What does not change

- The threshold stays at 80%. It is not lowered.
- No fake coverage is added (no broad `exclude_lines`, no blanket `# pragma: no cover`).
- No meaningful runtime code is excluded from coverage.
- No `--cov-append`, no `--cov-branch` changes (keep defaults).

### If coverage is below 80

The current coverage already passes at 80%. If the change from `--cov=src/bremen` to `--cov=bremen` causes a different measurement (it should not, but if it does), the coder must:
- Report the exact coverage gap in precommit-review.
- Do not fake coverage or add broad exclusions.
- Propose a separate test-improvement PR.
- This PR can proceed even if coverage temporarily dips, AS LONG AS the gap is reported and a follow-up PR is agreed upon.

## Cache design

### Approach

Use `actions/setup-python@v5` built-in pip cache. The `setup-python` action has a `cache: pip` option that automatically caches and restores `~/.cache/pip` based on a key derived from the dependency files.

### Implementation

```yaml
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: "3.13"
    cache: pip
```

No additional `actions/cache@v4` step. No custom cache key computation. No `restore-keys` fallback.

`actions/setup-python@v5` with `cache: pip` automatically:
- Detects `requirements.txt`, `pyproject.toml`, or `setup.py` in the repository root.
- Computes a hash of the detected file(s).
- Caches `~/.cache/pip` keyed by that hash.
- Restores the cache on subsequent runs when the hash matches.

### Why `setup-python` built-in cache

- Fewer workflow steps to maintain.
- Uses the same cache key derivation that the GitHub Actions team maintains and tests.
- No need to manually specify `pyproject.toml`, `environment.yml`, and workflow file in a custom cache key.
- The action is already used in the workflow (no new action to add).

### Safety

- The pip cache stores downloaded wheel files and source archives — no secrets, no tokens.
- `BREMEN_CI_GITHUB_TOKEN` is not stored in the cache.
- Private dependency install commands still run every time; their sources are re-fetched.
- The cache only accelerates the download of public PyPI packages.

### Cache key details

The automatic key from `setup-python@v5` uses `hashFiles(pyproject.toml)` for pip-based projects. If `environment.yml` is needed in the key, the built-in cache does not support it directly. In that case, a manual `actions/cache@v4` step could be added, but this PLAN.md prefers the simpler `setup-python` built-in.

If the Python version changes (e.g., `3.13` → `3.14`), the cache is automatically invalidated because `setup-python` uses a composite key that includes the Python version.

## Secret handling

No changes to the existing secret model:

| Secret | Purpose | How it is used |
|--------|---------|----------------|
| `BREMEN_CI_GITHUB_TOKEN` | Access private XRD-preprocessing and container repos | Git config with `insteadOf` override. Not passed into Docker. Not cached. |
| `SONAR_TOKEN` | SonarCloud API authentication | Set as environment variable for `SonarSource/sonarqube-scan-action@v6`. Not committed. |

No new secrets are added. No SSH key flow is added. No secret is passed to Docker (not applicable — Docker is not modified).

## Sonar coverage integration

### Current state

The workflow passes `-Dsonar.python.coverage.reportPaths=coverage.xml` as an argument to `SonarSource/sonarqube-scan-action@v6`. This works correctly — SonarCloud receives the coverage report path.

### Change for sonar-project.properties

If `sonar.python.coverage.reportPaths` is not already declared in `sonar-project.properties`, add it:

```
sonar.python.coverage.reportPaths=coverage.xml
```

This makes the coverage path explicit in the project configuration rather than relying only on the workflow args. Both locations work, but declaring it in `sonar-project.properties` is more visible to human reviewers and persists if the workflow args change.

### If no change is needed

If the current workflow args already pass the coverage path correctly and the team prefers to keep it there, `sonar-project.properties` does not need modification. The coder may leave it unchanged.

## Safety boundaries

This PR must not:
- Change Bremen runtime behavior (src/bremen/)
- Change preprocessing semantics
- Change H5 reader behavior
- Change model/joblib behavior
- Change training behavior
- Change test files or test data
- Change config files
- Change documentation (docs/, README, AGENTS.md)
- Change pyproject.toml, environment.yml, Makefile, requirements.txt, .gitignore
- Activate Docker build (the TODO comment stays commented)
- Add Docker publish or GHCR of any kind
- Add deployment of any kind
- Implement config discovery or config validation
- Lower coverage threshold below 80%
- Exclude meaningful runtime code from coverage

## Validation checklist

Precommit-review must execute these checks and report pass/fail for each.

### Static and security checks

```bash
# 1) Working tree state
git status --short

# 2) Changed files — only quality.yml and optionally sonar-project.properties
git diff --name-only

# 3) YAML parse check
python -c "import yaml; yaml.safe_load(open('.github/workflows/quality.yml')); print('YAML OK')"

# 4) Deprecated cache action check
grep -q "actions/cache@v[0-3]" .github/workflows/quality.yml && \
  echo "ERROR: uses deprecated actions/cache version" || \
  echo "No deprecated cache actions"

# 5) No unsafe secret patterns (literal values in committed files)
grep -R -I -n -E "PRIVATE KEY|BEGIN OPENSSH|BEGIN RSA|SONAR_TOKEN=.*[a-zA-Z0-9]|BREMEN_CI_GITHUB_TOKEN=.*[a-zA-Z0-9]|password|secret" \
  .github/workflows/quality.yml sonar-project.properties 2>/dev/null && \
  echo "ERROR: Secrets found" || echo "No secrets committed"

# 6) No Docker commands added
grep -qE "docker build|docker run|docker push|docker/login|ghcr" .github/workflows/quality.yml && \
  echo "ERROR: Docker commands detected — not allowed in this PR" || \
  echo "No Docker commands added"

# 7) No GHCR or publish/deploy patterns
grep -qE "publish|deploy|ghcr\.io|ecr|aws|kubernetes|helm" .github/workflows/quality.yml && \
  echo "ERROR: Publish/deploy detected — not allowed in this PR" || \
  echo "No publish/deploy patterns"

# 8) No H5/HDF5 changes
git diff --name-only | grep -E "\.h5$|\.hdf5$" && exit 1 || echo "OK"

# 9) No tests/data changes
git diff --name-only -- tests/data

# 10) SonarCloud config check — coverage path aligned
test -f sonar-project.properties && \
  grep -q "sonar.python.coverage.reportPaths" sonar-project.properties && \
  echo "coverage path in sonar-project.properties" || \
  echo "coverage path not in sonar-project.properties (may be in workflow args)"
```

### Python and test checks

```bash
# 11) Compile check
python -m compileall src tests

# 12) Identity test
python -m pytest -q tests/test_bremen_import_identity.py

# 13) Full coverage test with threshold enforcement
python -m pytest \
  --cov=bremen \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml \
  --cov-fail-under=80 \
  -q

# 14) coverage.xml exists after coverage run
test -f coverage.xml && echo "coverage.xml exists" || echo "ERROR: coverage.xml not generated"
```

## Rollback plan

### Cache issues

If the `setup-python` built-in cache causes problems:
- **Stale dependencies**: Remove the `cache: pip` line from the workflow. This forces a full re-download but restores deterministic behavior.
- **Wrong cache key**: The `setup-python` built-in uses `hashFiles(pyproject.toml)` automatically. If this does not capture `environment.yml` changes, add a manual `actions/cache@v4` step with an explicit key that includes `environment.yml`.
- **Cache poisoning**: Not possible with pip download cache (all packages are checksum-verified by pip).

### Coverage issues

If the threshold is not met:
- **Do not lower the threshold**. Report the gap and create a separate test-improvement PR.
- If `--cov=bremen` differs from `--cov=src/bremen`, the coder may revert to `--cov=src/bremen` and document the discrepancy.

## Follow-up note (PR 0007)

Docker smoke activation and GHCR publish are deferred to a follow-up PR (currently planned as PR 0007, which may be renumbered). The `# TODO(PR-0006)` comment in `quality.yml` should be updated to reference the correct follow-up PR number:

```
# TODO(PR-0007): enable Docker smoke after Docker dependency handling is hardened.
```

The follow-up PR will also handle:
- Docker build activation (uncomment the build job)
- Docker smoke test (identity test inside container)
- GHCR publish (main-only push, `latest` and `sha` tags)

## Plan Drift Gate

Precommit-review must check each of these drift categories. Any drift blocks merge until resolved.

| Drift category | Check |
|----------------|-------|
| **File drift** | Only `.github/workflows/quality.yml`, `sonar-project.properties` (optional), and PR artifacts changed. |
| **Coverage drift** | Threshold at 80%. `--cov=bremen`. `coverage.xml` generated. No fake coverage or broad exclusions. |
| **Cache drift** | Uses `actions/setup-python@v5` built-in `cache: pip`. No `actions/cache@v4` unless justified. No secrets in cache. No deprecated action versions. |
| **Secret drift** | No new secrets. No literal secrets committed. `BREMEN_CI_GITHUB_TOKEN` and `SONAR_TOKEN` referenced via `${{ secrets.* }}` only. |
| **Docker drift** | No Docker commands added. No Dockerfile modification. Docker TODO comment updated to point to correct follow-up PR. |
| **GHCR/publish drift** | No publish, deploy, GHCR, ECR, AWS, Kubernetes, or Helm patterns. |
| **Runtime drift** | No changes to src/, tests/, config/, examples/, pyproject.toml, environment.yml, Makefile, requirements.txt, or .gitignore. |
| **SonarCloud drift** | Coverage path aligned in sonar-project.properties or workflow args. SonarCloud remains quality visibility, not release gate. |
| **Documentation drift** | No changes to docs/, README.md, AGENTS.md, or .project-memory/memory_index.yml. |
| **Validation drift** | All 14 validation checks pass. Coverage.xml exists. No deprecated cache actions used. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Any file outside the allowed list (quality.yml, sonar-project.properties, PR artifacts) is created or modified.
- Docker commands (`docker build`, `docker run`, `docker push`) are added to the workflow.
- GHCR, ECR, publish, deploy, AWS, Kubernetes, or Helm patterns are added.
- The coverage threshold is lowered below 80%.
- Broad coverage exclusions are added to exclude meaningful runtime code.
- Secrets or credentials are committed (literal token values in files).
- `actions/cache@v3` or earlier deprecated versions are used.
- Runtime source files, test files, config files, or example files are changed.
- `pyproject.toml`, `environment.yml`, `Makefile`, `requirements.txt`, or `.gitignore` are changed.
- Documentation files (docs/, README.md, AGENTS.md, memory_index.yml) are changed.

## Decisions summary

### Allowed files
1. `.github/workflows/quality.yml` — MODIFY (add caching, update coverage target)
2. `sonar-project.properties` — MODIFY if coverage path alignment needed (add `sonar.python.coverage.reportPaths`)

### Forbidden files
- Dockerfile, .dockerignore, README.md, AGENTS.md, docs/**, .project-memory/memory_index.yml
- src/**, tests/**, config/**, examples/**
- pyproject.toml, environment.yml, Makefile, requirements.txt, .gitignore
- packaging/**, agents/**
- Any H5/HDF5 files, any binary/model artifacts

### Current CI baseline
Already has compileall, identity test, full pytest with coverage (80%), SonarCloud scan, and private dep access via BREMEN_CI_GITHUB_TOKEN. Docker smoke is commented out with TODO.

### Coverage design
- Change `--cov=src/bremen` to `--cov=bremen`
- Keep `--cov-fail-under=80`
- Keep `coverage.xml` for SonarCloud
- If coverage dips below 80: report gap, do not fake, propose separate PR

### Cache design
- Use `actions/setup-python@v5` built-in `cache: pip`
- No `actions/cache@v4` unless explicitly justified
- Automatically keyed by `hashFiles(pyproject.toml)` and Python version
- No secrets in cache

### Secret handling
- No new secrets. No SSH flow. `BREMEN_CI_GITHUB_TOKEN` and `SONAR_TOKEN` remain as-is.

### Sonar coverage integration
- Add `sonar.python.coverage.reportPaths=coverage.xml` to `sonar-project.properties` if not already present. Workflow args already pass it — this makes it explicit.

### Safety boundaries
- No runtime, preprocessing, H5, model, training, API, config discovery, or config validation changes.
- No Docker changes. No publish/deploy. No documentation changes.

### Validation checklist
14 checks: static (YAML parse, deprecated cache scan, secret scan, Docker/GHCR/ecr patterns, H5/data, sonar config), Python (compileall, identity test, full coverage test, coverage.xml existence), and git state.

### Rollback plan
- Cache issues: remove `cache: pip` from setup-python step.
- Coverage issues: revert to `--cov=src/bremen`, report gap, create test-improvement PR.
- No lowering of threshold.

### Follow-up note (PR 0007)
Docker smoke activation and GHCR publish are deferred. The TODO comment is updated to reference the correct follow-up PR.

### Plan Drift Gate requirements
11 drift-check criteria: file drift, coverage drift, cache drift, secret drift, Docker drift, GHCR/publish drift, runtime drift, SonarCloud drift, documentation drift, validation drift, blockers.

### Stop conditions
11 block conditions covering: file scope, Docker commands, publish/deploy, coverage threshold, coverage exclusions, secrets, deprecated actions, source/test/config changes, pyproject/environment changes, documentation changes.

### Blockers
- None for writing this PLAN.md. Implementation blocked until plan-review approves.
- Implementation blocked if any of the 11 stop conditions are detected.
- Implementation blocked if the allowed-file scope is violated.

### Warnings
- The roadmap currently describes PR 0006 as the entrypoint PR. This PR is coverage/cache only. The roadmap cannot be updated in this PR (docs/ is forbidden). The discrepancy will be resolved in a later PR.
- If `--cov=bremen` gives a different measurement than `--cov=src/bremen`, the coder may revert and document the discrepancy.
- The Docker TODO comment must be updated to reference the correct follow-up PR (PR 0007 or whichever the next infrastructure PR is).

## Exact human commit instructions for planning artifacts

This PLAN.md is a planning artifact only. No implementation files have been created or modified.

1. Planner writes this file: `.project-memory/pr/0006-ci-coverage-cache/PLAN.md`
2. Human runs: `git add .project-memory/pr/0006-ci-coverage-cache/PLAN.md`
3. Human runs: `git commit -m "PR 0006 — Plan CI coverage and dependency cache"`
4. Human pushes the branch for plan-review.
5. After plan-review approves, the coder implements the allowed files listed above.

## Files read

- `.github/workflows/quality.yml`
- `Dockerfile`
- `.dockerignore`
- `sonar-project.properties`
- `docs/roadmap.md`
- `docs/repository_cleanup.md`
- `.project-memory/project_contract.yml`
- `.project-memory/memory_index.yml`

## Files written

- `.project-memory/pr/0006-ci-coverage-cache/PLAN.md` (this file)

## Files intentionally ignored

- All source files under `src/bremen/`
- All test files under `tests/`
- All config files under `config/`
- All example files under `examples/`
- `README.md`, `AGENTS.md`, `docs/**`
- `.project-memory/memory_index.yml`
- `.gitignore`, `requirements.txt`, `environment.yml`, `Makefile`
- `packaging/`, `agents/`
- Any H5/HDF5 files
- Any binary/model artifacts

## Boundary confirmations

- confirm: only PLAN.md written: yes
- confirm: no implementation files written: yes
- confirm: no Dockerfile modified: yes
- confirm: no .dockerignore modified: yes
- confirm: no GitHub Actions file modified: yes (only by coder after plan approval)
- confirm: no SonarCloud file modified: yes (only by coder after plan approval)
- confirm: no source/runtime code modified: yes
- confirm: no tests modified: yes
- confirm: no docs modified: yes
- confirm: no config discovery implemented: yes
- confirm: no config validation implemented: yes
- confirm: no H5/HDF5 files read or edited: yes
- confirm: no secrets committed: yes
- confirm: no git mutation commands run: yes
- confirm: PR classified as infrastructure/delivery track: yes
- confirm: coverage threshold at 80%, not lowered: yes
- confirm: Docker smoke NOT activated (TODO stays): yes
- confirm: GHCR/Docker publish NOT added: yes
- confirm: no new GitHub secrets required: yes
- confirm: no actions/cache@v3 or earlier deprecated versions: yes
- confirm: roadmap discrepancy documented (not fixed in this PR): yes
