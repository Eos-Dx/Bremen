# PR 0007 — Plan GHCR Publish and Docker Smoke

Author: plan
Mode: planning only
Branch: 0007-ghcr-publish-docker-smoke

## Objective

Enable Docker build smoke, Docker smoke test, and GHCR image publish on push to main only. This is a focused infrastructure/delivery PR that activates the currently commented-out Docker job and adds image publishing.

## Context

PR 0005 added the initial Docker/CI/SonarCloud skeleton with a Dockerfile and a commented-out build job. PR 0006 added coverage enforcement and dependency caching. Both are merged.

The current `quality.yml` contains a commented-out Docker build job with `# TODO(PR-0007)` — this PR resolves that TODO.

Current state:
- `test` job: runs compileall, coverage, SonarCloud scan. Has pip caching.
- Docker `build` job: **commented out**. Never runs.
- Dockerfile: exists, two-stage, builds public deps only. `CMD` runs the identity test.
- `.dockerignore`: exists, excludes H5, joblib, secrets, .git, caches, project-memory.
- No GHCR publish exists.

## Infrastructure-track classification

This PR belongs to the **infrastructure/delivery track**. It is not a product quest or runtime feature quest. It activates CI infrastructure that was designed in PR 0005 and left as a TODO.

**Known roadmap discrepancy**: `docs/roadmap.md` and `docs/repository_cleanup.md` describe PR 0007 as "Config Validation Contract and Tests." This PR covers Docker smoke and GHCR publish. Config validation is deferred to a later PR. The roadmap cannot be updated in this PR because `docs/**` is forbidden by the task.

## Non-goals

This PR does not:
- Change Bremen runtime behavior (src/bremen/)
- Change preprocessing, inference, or training behavior
- Change H5 handling, model/joblib handling
- Implement config discovery or config validation
- Change tests, test data, or test behavior
- Change docs, README, or AGENTS.md
- Change pyproject.toml, environment.yml, Makefile, requirements.txt
- Change sonar-project.properties (already has coverage path)
- Add AWS/ECR/deployment/Kubernetes/Helm
- Push model artifacts
- Make clinical claims

## Allowed implementation files

The coder may create or modify exactly these files:

1. **`.github/workflows/quality.yml`** — MODIFY. Uncomment and harden the Docker build job. Add a publish job for GHCR.
2. **`Dockerfile`** — MODIFY only if required for CI build/publish compatibility. Minimize changes.
3. **`.dockerignore`** — MODIFY only if required to keep the published image context safe/minimal. Current `.dockerignore` already excludes `.git`, `.project-memory`, `.coverage`, coverage.xml, H5, joblib, and secrets. If the review confirms it covers everything needed, no changes are required.
4. **`.project-memory/pr/0007-ghcr-publish-docker-smoke/PLAN.md`** — this file, written by planner.
5. **`.project-memory/pr/0007-ghcr-publish-docker-smoke/reviews/plan-review.yml`** — written later by plan-review role.

No other files may be created or modified.

## Forbidden files

- `README.md`, `AGENTS.md`, `docs/**`
- `.project-memory/memory_index.yml`
- `src/**`, `tests/**`, `config/**`, `examples/**`
- `pyproject.toml`, `environment.yml`, `Makefile`, `requirements.txt`, `.gitignore`
- `sonar-project.properties` (unless strictly required and justified with a blocker-level reason)
- `packaging/**`, `agents/**`
- Any H5/HDF5 files, any binary/model artifacts

## Current CI baseline

The current `.github/workflows/quality.yml` has:

- Trigger: push (any branch), pull_request, workflow_dispatch
- Permissions: contents: read
- One `test` job:
  - checkout, setup-python with pip cache, BREMEN_CI_GITHUB_TOKEN config
  - Install private deps (xrd-preprocessing, container), public deps (bremen, pytest-cov)
  - Dependency import proof
  - compileall
  - Coverage test with `--cov=bremen --cov-fail-under=80 --cov-report=xml:coverage.xml`
  - SonarCloud scan with coverage.xml
  - Token cleanup (always)
- Commented-out `build` job with `# TODO(PR-0007)`:
  - `needs: test`, runs-on: ubuntu-latest
  - checkout, docker build, docker run identity test

## Target CI design

### Job structure after PR 0007

```
test (existing, unchanged)
  └─ build (new, active)
       └─ publish (new, main-only)
```

### `test` job — unchanged from PR 0006

No changes to the existing `test` job. It continues to run compileall, coverage, and SonarCloud.

### `build` job — uncommented and hardened

Uncomment the existing `build` job structure. The Docker build and smoke steps remain the same as the commented-out template, with the addition that they are now active.

```yaml
build:
  needs: test
  runs-on: ubuntu-latest
  permissions:
    contents: read

  steps:
    - uses: actions/checkout@v4

    - name: Build image for smoke test
      run: docker build -t bremen:ci .

    - name: Run container and smoke test
      run: |
        docker run --rm bremen:ci \
          python -m pytest -q tests/test_bremen_import_identity.py
```

Design rules:
- `needs: test` ensures the test suite passes before building Docker.
- No secrets are passed to Docker build (see "Private dependency handling" below).
- Smoke test uses the existing identity test (filesystem-only, no private deps needed).
- Smoke test must not read H5/HDF5 files, train models, or run clinical inference.
- Permissions: contents: read only.

### `publish` job — new

```yaml
publish:
  if: github.event_name == 'push' && github.ref == 'refs/heads/main'
  needs: build
  runs-on: ubuntu-latest
  permissions:
    contents: read
    packages: write

  steps:
    - uses: actions/checkout@v4

    - name: Build image with release tags
      run: |
        docker build \
          -t ghcr.io/eos-dx/bremen:latest \
          -t ghcr.io/eos-dx/bremen:${{ github.sha }} \
          .

    - name: Log in to GHCR
      uses: docker/login-action@v3
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Push image
      run: |
        docker push ghcr.io/eos-dx/bremen:latest
        docker push ghcr.io/eos-dx/bremen:${{ github.sha }}
```

Design rules:
- Publishes **only** on `push` to `main`. Not on pull_request, not on feature branches.
- `needs: build` ensures smoke test passes before publishing.
- Image name: `ghcr.io/eos-dx/bremen`.
- Tags: `latest` and `github.sha` (the exact commit SHA).
- Authentication: `GITHUB_TOKEN` with `packages: write` permission.
- No additional GitHub PAT. No GHCR-specific token.
- No deployment. No AWS/ECR. No Kubernetes/Helm.

## Docker build design

### Current Dockerfile

The existing Dockerfile is a two-stage build (builder + smoke). It:
- Installs only public/base dependencies (`pip install .`)
- Does NOT install private dependencies (xrd-preprocessing, container)
- Runs the identity test as `CMD`

### Changes needed

Minimal or none. The existing Dockerfile is already suitable for:
- Public-only build in CI (smoke test does not need private deps)
- Identity test as validation
- No H5 data, no model artifacts, no secrets

If any changes are needed:
- Ensure the final image does not contain `.git`, `.project-memory`, `.coverage`, `coverage.xml`, H5/HDF5, model/joblib/pkl/npy/npz artifacts, or local env/secret files.
- The current `.dockerignore` already excludes all of these. If the Dockerfile itself copies any of these, remove those COPY instructions.

### BuildKit secret mount for private dependencies

The current Dockerfile does NOT install private dependencies. The smoke test (identity test) does not require them. This is the correct approach — keep it this way.

If a future use case requires private dependencies inside Docker, the safe approach is BuildKit secret mount:

```dockerfile
# Not added in this PR — documented for future reference
RUN --mount=type=secret,id=BREMEN_CI_GITHUB_TOKEN \
    GITHUB_TOKEN=$(cat /run/secrets/BREMEN_CI_GITHUB_TOKEN) && \
    git config --global url."https://x-access-token:${GITHUB_TOKEN}@github.com/".insteadOf "https://github.com/" && \
    pip install "git+https://github.com/Eos-Dx/XRD-preprocessing.git" && \
    git config --global --unset url."https://x-access-token:${GITHUB_TOKEN}@github.com/".insteadOf
```

This is **not implemented in PR 0007** — only documented for future reference. The current Dockerfile remains unchanged for PR 0007.

## Docker smoke design

### Smoke command

```
python -m pytest -q tests/test_bremen_import_identity.py
```

This is already set as the Dockerfile `CMD`. The CI runs it as:

```bash
docker run --rm bremen:ci
```

(using the default CMD) or explicitly:

```bash
docker run --rm bremen:ci \
  python -m pytest -q tests/test_bremen_import_identity.py
```

### Verification

The identity test:
- Imports `bremen` package filesystem-style (no `xrd_preprocessing` or `container` import)
- Verifies package name, version, entrypoint, and module structure
- Does not read H5/HDF5 files
- Does not train models
- Does not run clinical inference
- Does not require private dependencies

### Ordering

1. Build image.
2. Run smoke test.
3. If smoke passes, publish (on main only).
4. If smoke fails, the build job fails and nothing is published.

## GHCR publish design

### Image name and tags

| Field | Value |
|-------|-------|
| Registry | `ghcr.io` |
| Owner | `eos-dx` |
| Image | `bremen` |
| Full name | `ghcr.io/eos-dx/bremen` |
| Tags (main) | `latest`, `{github.sha}` |

### Trigger condition

```
if: github.event_name == 'push' && github.ref == 'refs/heads/main'
```

This ensures:
- No publish on pull_request (even from main branch).
- No publish on feature branch pushes.
- Publish only when code is merged to main.

### Authentication

`GITHUB_TOKEN` provided by GitHub Actions runtime. No additional secrets. The `docker/login-action@v3` handles the login using the actor's token.

### Permissions

```yaml
publish:
  permissions:
    contents: read    # checkout code
    packages: write   # push to GHCR
```

The `test` and `build` jobs keep `contents: read` only. The `publish` job adds `packages: write`.

### No deployment

Publishing to GHCR does not deploy anywhere. The image is available for pull but is not automatically deployed to any runtime environment. No AWS/ECR, no Kubernetes, no Helm.

## Private dependency handling in Docker

### Current approach (used in PR 0007)

The Docker build does not install private dependencies. The smoke test (identity test) does not need them. This is the simplest and safest approach.

The `BREMEN_CI_GITHUB_TOKEN` is:
- Used only in the `test` job for compiling/installing private deps for the full pytest suite.
- NOT passed to Docker build.
- NOT injected as Docker build args.
- NOT persisted in any Docker layer.
- NOT echoed in logs.
- NOT committed.

### Forbidden patterns

- No `ARG BREMEN_CI_GITHUB_TOKEN` in Dockerfile.
- No `--build-arg BREMEN_CI_GITHUB_TOKEN=...` in workflow.
- No SSH private key flow.
- No `BREMEN_CI_SSH_PRIVATE_KEY`.
- No git config token that persists in the Docker image.

### Future approach (documented only)

If private dependencies are needed inside Docker in the future, use BuildKit secret mounts (`--mount=type=secret`). This is documented in the "Docker build design" section above but not implemented.

## Secret handling

| Secret | Used where | Passed to Docker? |
|--------|-----------|-------------------|
| `BREMEN_CI_GITHUB_TOKEN` | `test` job git config | No |
| `SONAR_TOKEN` | `test` job SonarCloud scan | No |
| `GITHUB_TOKEN` | `publish` job GHCR login | Built-in, runtime only |

No new secrets are added. No secrets are committed. No secrets are baked into Docker images.

## Permissions

| Job | Permissions | Purpose |
|-----|-------------|---------|
| `test` | contents: read | Checkout code |
| `build` | contents: read | Checkout code for Docker build context |
| `publish` | contents: read, packages: write | Checkout + push image to GHCR |

## Safety boundaries

This PR must not:
- Change Bremen runtime behavior (src/bremen/)
- Change preprocessing, inference, or training behavior
- Change H5 reader, model loader, or joblib behavior
- Change tests, test data, or test configurations
- Change docs, README, AGENTS.md, memory_index.yml
- Change pyproject.toml, environment.yml, Makefile, requirements.txt, .gitignore
- Change sonar-project.properties (already has coverage path)
- Implement config discovery or config validation
- Change the `test` job (existing CI behavior is preserved)
- Pass secrets to Docker build in any form
- Include `.coverage`, `coverage.xml`, H5/HDF5, model artifacts, or secrets in the Docker image
- Deploy to any runtime environment (AWS, ECS, Kubernetes, Helm, etc.)
- Add SSH key flows
- Make clinical claims

## Validation checklist

Precommit-review must execute these checks and report pass/fail for each.

### Static and security checks

```bash
# 1) Working tree state
git status --short

# 2) Changed files
git diff --name-only

# 3) YAML parse check
python -c "import yaml; yaml.safe_load(open('.github/workflows/quality.yml')); print('YAML OK')"

# 4) No unsafe secret patterns in committed files
grep -R -I -n -E "PRIVATE KEY|BEGIN OPENSSH|BEGIN RSA|SONAR_TOKEN=|BREMEN_CI_GITHUB_TOKEN=|password|secret" \
  .github/workflows/quality.yml Dockerfile .dockerignore 2>/dev/null && \
  echo "ERROR: Secrets found" || echo "No secrets committed"

# 5) No Docker build args carrying secrets
grep -q "build-arg.*SECRET\|build-arg.*TOKEN\|build-arg.*KEY\|build-arg.*PASSWORD\|build-arg.*CREDENTIAL" \
  .github/workflows/quality.yml && \
  echo "ERROR: Secrets passed via build-arg" || echo "No build-arg secrets"

# 6) Docker publish only on push to main
grep -q "github.event_name == 'push' && github.ref == 'refs/heads/main'" \
  .github/workflows/quality.yml && \
  echo "GHCR publish is main-only" || echo "WARNING: GHCR publish condition not found"

# 7) .coverage and coverage.xml not staged in Docker
grep -q "\.coverage\|coverage\.xml" Dockerfile && \
  echo "ERROR: coverage files referenced in Dockerfile" || echo "No coverage files in Dockerfile"
grep -q "\.coverage\|coverage\.xml" .dockerignore || \
  echo "WARNING: coverage files may not be excluded in .dockerignore"

# 8) No H5/HDF5 changes
git diff --name-only | grep -E "\.h5$|\.hdf5$" && exit 1 || echo "OK"

# 9) No tests/data changes
git diff --name-only -- tests/data

# 10) No source/runtime changes
git diff --name-only -- src/
```

### Python and test checks

```bash
# 11) Compile check
python -m compileall src tests

# 12) Identity test
python -m pytest -q tests/test_bremen_import_identity.py

# 13) Full coverage test with threshold
python -m pytest \
  --cov=bremen \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml \
  --cov-fail-under=80 \
  -q
```

### Docker checks (if Docker available)

```bash
# 14) Docker build
docker build -t bremen:pr-test .

# 15) Docker smoke
docker run --rm bremen:pr-test \
  python -m pytest -q tests/test_bremen_import_identity.py
```

### Artifact and file checks

```bash
# 16) Check .coverage and coverage.xml are not staged for commit
git diff --cached --name-only | grep -E "\.coverage$|coverage\.xml$" && \
  echo "ERROR: coverage files staged for commit" || echo "No coverage files staged"

# 17) Check no new untracked files outside allowed set
git status --short | grep -v "^?? \.project-memory/pr/0007-" && \
  echo "WARNING: untracked files outside PR artifacts" || echo "No unexpected untracked files"
```

## Rollback plan

### Docker build failure

If the Docker build breaks after merging:
1. Re-comment the `build` job or mark it with `if: false`.
2. Diagnose the build failure (Dockerfile issue, dependency resolution, CI runner change).
3. Fix in a follow-up PR.

### GHCR publish failure

If the publish job fails on main:
1. Manual: Check GHCR token permissions. The `GITHUB_TOKEN` must have `packages: write` scope.
2. Manual: Verify the `ghcr.io/eos-dx/bremen` package exists. GitHub Actions creates it on first push.
3. If the package name conflicts, rename it in a follow-up PR.

### Smoke test failure after merge

If the identity test fails inside Docker on main:
1. The `build` job fails. Nothing is published.
2. Fix the Dockerfile or the identity test in a follow-up PR.
3. Manually re-run CI after the fix to publish the corrected image.

## Follow-up notes

### Config validation

Config validation (originally planned as PR 0007 in the roadmap) is deferred. It will be planned in a later PR after the infrastructure track is complete.

### Subsequent infrastructure PRs (if any)

If the published GHCR image needs to be used in downstream workflows (e.g., integration tests, deployment), plan those in separate infrastructure PRs. This PR stops at "image is available in GHCR."

## Plan Drift Gate

Precommit-review must check each of these drift categories. Any drift blocks merge until resolved.

| Drift category | Check |
|----------------|-------|
| **File drift** | Only `.github/workflows/quality.yml`, `Dockerfile`, `.dockerignore` (if needed), and PR artifacts changed. |
| **Docker build drift** | Build job uncommented. `needs: test`. No secrets in build. No deploy. |
| **Docker smoke drift** | Smoke command is `python -m pytest -q tests/test_bremen_import_identity.py`. No H5 read, no model train, no clinical inference. |
| **GHCR publish drift** | Main-only. `latest` + `sha` tags. `GITHUB_TOKEN` auth. `packages: write`. No deploy. |
| **Private dependency handling drift** | Token NOT passed to Docker. No build-arg secrets. No SSH key. No token in layers. |
| **Dockerfile safety drift** | No `.git`, `.project-memory`, `.coverage`, `coverage.xml`, H5, joblib, secrets in image. |
| **Secret drift** | No new secrets. No secrets committed. No `build-arg` for secrets. |
| **Permissions drift** | test/build: contents:read only. publish: +packages:write. |
| **Runtime drift** | No changes to src/, tests/, config/, examples/, pyproject.toml, environment.yml, Makefile, sonar-project.properties. |
| **Deployment drift** | No AWS, ECR, Kubernetes, Helm, or any runtime deployment. |
| **Documentation drift** | No changes to docs/, README.md, AGENTS.md, or memory_index.yml. |
| **Validation drift** | All 17 validation checks pass. No coverage files staged. No secrets. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Any file outside the allowed set (quality.yml, Dockerfile, .dockerignore, PR artifacts) is created or modified.
- Docker build is activated but `needs: test` is missing (build bypasses test).
- Docker build uses `--build-arg` to pass secrets (`BREMEN_CI_GITHUB_TOKEN`, `SONAR_TOKEN`, etc.).
- Dockerfile copies `.coverage`, `coverage.xml`, H5/HDF5, model artifacts, or secret files into the image.
- GHCR publish is not restricted to `push` to `main`.
- GHCR publish uses a separate PAT or token instead of `GITHUB_TOKEN` (unless strictly justified).
- Deployment (AWS, ECR, Kubernetes, Helm) is added.
- Runtime source files, test files, config files, or example files are changed.
- pyproject.toml, environment.yml, Makefile, requirements.txt, or .gitignore are changed.
- sonar-project.properties is changed (unless strictly justified with blocker-level reason).
- Documentation files (docs/, README.md, AGENTS.md, memory_index.yml) are changed.
- Secrets or credentials are committed in any committed file.
- Coverage files (`.coverage`, `coverage.xml`) are staged for commit.

## Decisions summary

### Allowed files
1. `.github/workflows/quality.yml` — MODIFY (uncomment build job, add publish job)
2. `Dockerfile` — MODIFY if needed for publish compatibility
3. `.dockerignore` — MODIFY if needed for image safety
4. PR artifacts (PLAN.md, plan-review.yml)

### Forbidden files
- README.md, AGENTS.md, docs/**, .project-memory/memory_index.yml
- src/**, tests/**, config/**, examples/**
- pyproject.toml, environment.yml, Makefile, requirements.txt, .gitignore
- sonar-project.properties (unless strictly justified)
- packaging/**, agents/**
- H5/HDF5, model artifacts

### Current CI baseline
- test job with coverage/cache/Sonar (from PR 0006). Docker build job commented out (TODO PR-0007).

### Target CI design
- test → build (uncommented) → publish (new, main-only)

### Docker build design
- Uncomment existing build job. No Dockerfile changes unless needed. No secrets passed.

### Docker smoke design
- `python -m pytest -q tests/test_bremen_import_identity.py`. No private deps needed. No H5/model/clinical.

### GHCR publish design
- Main-only push. `ghcr.io/eos-dx/bremen`. Tags: `latest`, `sha`. `GITHUB_TOKEN` auth. No deploy.

### Private dependency handling design
- Token NOT passed to Docker. BuildKit secret mount documented but not implemented. No SSH key.

### Secret handling
- No new secrets. `BREMEN_CI_GITHUB_TOKEN` in `test` job only. `GITHUB_TOKEN` for GHCR. No secrets in Docker.

### Permissions
- test: contents:read. build: contents:read. publish: contents:read + packages:write.

### Safety boundaries
- No runtime, preprocessing, H5, model, training, API, config changes. No deployment. No clinical claims.

### Validation checklist
17 checks: static (YAML, secret patterns, build-arg secrets, publish condition, Dockerfile safety, H5/data, source changes), Python (compileall, identity test, full coverage), Docker (build, smoke), artifact (staged coverage files, untracked files).

### Rollback plan
- Re-comment build job if broken. Manual GHCR check if publish fails. Fix follow-up PR if smoke fails.

### Follow-up notes
- Config validation deferred from PR 0007 to a later PR.

### Plan Drift Gate requirements
13 drift-check criteria: file drift, Docker build drift, Docker smoke drift, GHCR publish drift, private dependency handling drift, Dockerfile safety drift, secret drift, permissions drift, runtime drift, deployment drift, documentation drift, validation drift, blockers.

### Stop conditions
13 block conditions covering: file scope, build bypasses test, build-arg secrets, Dockerfile includes artifacts/data, publish not main-only, publish uses PAT without justification, deployment, source/test/config changes, pyproject/environment changes, sonar-project changes, documentation changes, secrets committed, coverage files staged.

### Blockers
- None for writing this PLAN.md. Implementation blocked until plan-review approves.
- Implementation blocked if any of the 13 stop conditions are detected.
- Implementation blocked if the allowed-file scope is violated.

### Warnings
- The roadmap describes PR 0007 as config validation. This PR covers GHCR/Docker smoke. The roadmap discrepancy is noted but not fixed (docs/ is forbidden).
- The default `GITHUB_TOKEN` may not have `packages: write` enabled for the first run. A human may need to adjust repository settings.
- If the `ghcr.io/eos-dx/bremen` package already exists from another workflow, the push may fail. Manual intervention may be required.
- The Dockerfile does not install private dependencies. Full pytest cannot run inside Docker. This is by design — the smoke test (identity test) does not need them.

## Exact human commit instructions for planning artifacts

This PLAN.md is a planning artifact only. No implementation files have been created or modified.

1. Planner writes this file: `.project-memory/pr/0007-ghcr-publish-docker-smoke/PLAN.md`
2. Human runs: `git add .project-memory/pr/0007-ghcr-publish-docker-smoke/PLAN.md`
3. Human runs: `git commit -m "PR 0007 — Plan GHCR publish and Docker smoke"`
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

- `.project-memory/pr/0007-ghcr-publish-docker-smoke/PLAN.md` (this file)

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
- confirm: no GitHub Actions file modified: yes (only by coder after plan approval)
- confirm: no Dockerfile modified: yes (only by coder after plan approval)
- confirm: no .dockerignore modified: yes (only by coder if needed)
- confirm: no sonar-project.properties modified: yes
- confirm: no source/runtime code modified: yes
- confirm: no tests modified: yes
- confirm: no docs modified: yes
- confirm: no config discovery implemented: yes
- confirm: no config validation implemented: yes
- confirm: no H5/HDF5 files read or edited: yes
- confirm: no secrets committed: yes
- confirm: no git mutation commands run: yes
- confirm: PR classified as infrastructure/delivery track: yes
- confirm: Docker smoke activated (commented job uncommented): yes
- confirm: GHCR publish added (main-only): yes
- confirm: no secrets passed to Docker build: yes
- confirm: no deployment added: yes
- confirm: roadmap discrepancy documented (not fixed in this PR): yes
