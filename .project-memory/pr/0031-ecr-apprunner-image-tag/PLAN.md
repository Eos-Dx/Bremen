# PR 0031 — Plan ECR App Runner Image Tag

Author: plan
Mode: planning only
Branch: 0031-ecr-apprunner-image-tag

## Objective

Update the ECR publish workflow so the Bremen ECR image is pushed with three tags: an immutable SHA tag for audit, a stable mutable `app-runner` tag for App Runner auto-deploy, and `latest` as human convenience. This is a narrow CI/CD workflow PR only — no runtime, infra, or docs changes.

## Required reads — observed facts

### ROADMAP.md (post-PR-0030)
- PR 0031 described as: "ECR workflow: add stable App Runner image tag (`app-runner` tag alongside existing SHA + latest)."
- CI/CD image tag policy section: "The ECR workflow should keep immutable SHA tags for audit. A stable mutable tag named `app-runner` should be added for App Runner auto-deploy (planned PR 0031). The `latest` tag may remain as human convenience but should NOT be the App Runner deploy trigger."

### ADR-0008 (Runtime Target Pivot — App Runner Proving Target)
- "App Runner uses ECR as the image source. The stable mutable tag `app-runner` (added in a separate CI/CD PR) will trigger auto-deployment."
- Consequences include: "A CI/CD PR is required to add the `app-runner` stable mutable tag to the ECR publish workflow (PR 0031)."

### `.github/workflows/ecr-publish.yml` (current)
- Trigger: `workflow_dispatch` + `push` to `main`.
- Permissions: `contents: read`.
- Auth: static IAM user credentials from secrets (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`).
- Build/push: runs `docker build` with `BREMEN_CI_GITHUB_TOKEN` build arg, pushes with:
  - `${{ github.sha }}` (immutable SHA tag)
  - `latest` (mutable convenience tag)
- No `app-runner` tag. No App Runner deploy action.

### `tests/test_bremen_ecr_publish_workflow.py` (current)
- Static tests that parse/read the workflow YAML text.
- Tests verify: triggers, permissions, credential pattern, tags (`github.sha` and `:latest`), forbidden patterns (no Terraform, no ECS deploy, no hardcoded keys).
- Test `test_workflow_builds_and_pushes_docker_image_to_ecr` currently asserts:
  - `"${{ github.sha }}" in text`
  - `":latest" in text`
- This test must be updated to also assert `":app-runner" in text`.
- No other tests reference `app-runner`.

### Targeted discovery
- `tests/test_bremen_ecr_publish_workflow.py` exists — must be updated.
- No other workflow test files discovered.

### Branch blocker
Current branch is `0030-roadmap-adr-apprunner-pivot`, not `0031-ecr-apprunner-image-tag`. The implementation phase must be on the correct branch.

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Allowed implementation files

The coder may create or modify exactly these files:

1. **`.github/workflows/ecr-publish.yml`** — MODIFY. Add `app-runner` tag to build/push.
2. **`tests/test_bremen_ecr_publish_workflow.py`** — MODIFY. Update test assertions to include `app-runner` tag.

## Forbidden files

- `ROADMAP.md`, `docs/**`, `.project-memory/project_contract.yml`
- `src/**`, `tests/**` except the one existing workflow test
- `.github/workflows/quality.yml`, other `.github/workflows/**`
- `infra/**`, `Dockerfile`, `.dockerignore`
- `requirements.txt`, `pyproject.toml`, `config/**`, `examples/**`, `agents/**`
- Any `.h5`, `.hdf5`, `.joblib`, `.pkl`, `.npy`, `.npz`
- Deployment secrets or account-specific URLs

## Exact implementation scope

### 1. `.github/workflows/ecr-publish.yml` — Add `app-runner` tag

Add the `app-runner` tag to the existing build and push commands. The current build line:

```bash
docker build \
  --build-arg BREMEN_CI_GITHUB_TOKEN="${BREMEN_CI_GITHUB_TOKEN}" \
  -t "${IMAGE_URI}:${IMAGE_TAG}" \
  -t "${IMAGE_URI}:latest" \
  .
```

Should become:

```bash
docker build \
  --build-arg BREMEN_CI_GITHUB_TOKEN="${BREMEN_CI_GITHUB_TOKEN}" \
  -t "${IMAGE_URI}:${IMAGE_TAG}" \
  -t "${IMAGE_URI}:app-runner" \
  -t "${IMAGE_URI}:latest" \
  .
```

The push sequence:

```bash
docker push "${IMAGE_URI}:${IMAGE_TAG}"
docker push "${IMAGE_URI}:app-runner"
docker push "${IMAGE_URI}:latest"
```

**Nothing else changes** — triggers, permissions, credentials, build args all remain identical.

### 2. `tests/test_bremen_ecr_publish_workflow.py` — Update assertions

In `test_workflow_builds_and_pushes_docker_image_to_ecr`, add an assertion:

```python
assert ":app-runner" in text
```

This confirms the `app-runner` tag is present in the workflow YAML.

Consider whether a separate test is needed (e.g., `test_workflow_tags_include_app_runner`) or the assertion is added to the existing test. Single assertion addition is sufficient — one focused test for `app-runner` keeps intent clear.

## Tag policy

| Tag | Type | Purpose | Deploy trigger? |
|-----|------|---------|-----------------|
| `${{ github.sha }}` | Immutable | Audit, rollback, traceability | No (reference only) |
| `app-runner` | Mutable | App Runner auto-deploy source | Yes — App Runner watches this tag |
| `latest` | Mutable | Human convenience, local dev | No — NOT the App Runner deploy trigger |

## Workflow trigger preservation

- `workflow_dispatch` — preserved. Allows manual trigger.
- `push` to `main` — preserved. Automatic publish on merge to main.
- No `pull_request` trigger — preserved. ECR push from PR branches remains forbidden.

## Existing workflow test decision

The existing `tests/test_bremen_ecr_publish_workflow.py` file exists and covers workflow shape assertions. It must be updated to include `app-runner` in the tag assertions. No new test file is needed.

## Non-goals

- No App Runner service creation, deploy, or action.
- No Terraform changes.
- No Dockerfile changes.
- No source code changes.
- No dependency changes.
- No GHCR workflow changes.
- No quality workflow changes.
- No runtime behavior changes.
- No ADR or documentation changes.
- No AWS account IDs, registry URLs, access keys, or secret values exposed.

## Validation checklist

The implementation phase (coder) must execute these checks:

```bash
# 1-3) Branch and baseline
git rev-parse --verify HEAD
git branch --show-current
git status --short

# 4) Changed files
git diff --name-only

# 5) Compile check
python -m compileall src tests

# 6) Workflow test passes
python -m pytest -q tests/test_bremen_ecr_publish_workflow.py

# 7) Tag verification in workflow
grep -n "app-runner\|latest\|github.sha\|IMAGE_TAG\|ECR_REPOSITORY" .github/workflows/ecr-publish.yml

# 8) No secrets/account IDs in workflow or tests
grep -R "AWS_ACCESS_KEY_ID\|AWS_SECRET_ACCESS_KEY\|aws_secret_access_key\|account ID\|registry URL" .github/workflows/ecr-publish.yml tests/test_bremen_ecr_publish_workflow.py || true

# 9) No forbidden file changes
git diff --name-only -- ROADMAP.md docs src infra Dockerfile .dockerignore requirements.txt pyproject.toml config examples .github/workflows/quality.yml
# Must return nothing
```

## Rollback plan

1. **Revert `.github/workflows/ecr-publish.yml`** — remove the `app-runner` tag from build and push commands.
2. **Revert `tests/test_bremen_ecr_publish_workflow.py`** — remove the `app-runner` assertion.

No other files affected.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only `.github/workflows/ecr-publish.yml` and `tests/test_bremen_ecr_publish_workflow.py` changed. |
| **Tag policy drift** | `app-runner` added as stable mutable tag. SHA tag preserved. `latest` preserved. No other tags. |
| **Trigger drift** | workflow_dispatch and push to main preserved. No pull_request. |
| **Auth drift** | Static IAM credentials preserved. No change to auth approach. |
| **App Runner drift** | Tag added only. No App Runner deploy action or service creation. |
| **Test drift** | Existing test updated to assert `app-runner` tag. No new test file. |
| **Validation drift** | All validation checks pass. No forbidden file changes. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- PR 0030 rebaseline changes are not present on main (ROADMAP.md must mention `app-runner` planned in PR 0031).
- `.github/workflows/ecr-publish.yml` is missing.
- The change requires App Runner service creation, Terraform, Dockerfile edits, source/runtime code edits, or dependency edits.
- The workflow currently cannot be safely updated without exposing account-specific registry URLs or secrets.
- The implementation cannot stay within allowed files.
- Branch is not `0031-ecr-apprunner-image-tag`.

## Decisions summary

| Decision | Value |
|----------|-------|
| Tag policy | `github.sha` (immutable, audit) + `app-runner` (mutable, App Runner deploy) + `latest` (mutable, human convenience) |
| Workflow file | `.github/workflows/ecr-publish.yml` — 3-line change (add `-t` and `docker push` for `app-runner`) |
| Test file | `tests/test_bremen_ecr_publish_workflow.py` — add one `:app-runner` assertion |
| Triggers | Unchanged (workflow_dispatch + push to main, no pull_request) |
| Auth | Unchanged (static IAM user credentials) |
| App Runner deploy | NOT implemented in this PR |
| New test file | NOT created — existing test updated |

## Commit readiness

- **Planning artifact staged**: `.project-memory/pr/0031-ecr-apprunner-image-tag/PLAN.md`
- **Review artifact to be created**: `.project-memory/pr/0031-ecr-apprunner-image-tag/reviews/plan-review.yml`
- **PLAN.md + plan-review.yml together**: committed in one commit by human after plan-review approval.
- **Implementation + precommit-review.yml together**: committed in one commit by human after implementation and precommit-review.

## Branch note

The current working tree is on branch `0030-roadmap-adr-apprunner-pivot`. PR 0030 is the rebaseline PR. PR 0031 must be created from a base that includes PR 0030's merged changes. The implementation phase must switch to or create branch `0031-ecr-apprunner-image-tag` from the correct base before making changes.

## Files read

- `.project-memory/pr/0030-roadmap-adr-apprunner-pivot/reviews/precommit-review.yml`
- `.project-memory/architecture/runtime-model-config-roadmap-rebaseline.md`
- `ROADMAP.md`
- `docs/adr/0008-runtime-target-apprunner-proving.md`
- `.github/workflows/ecr-publish.yml`
- `tests/test_bremen_ecr_publish_workflow.py`

## Files written

- `.project-memory/pr/0031-ecr-apprunner-image-tag/PLAN.md` (this file)

## Files intentionally ignored

- All source, infra, Docker, config, and dependency files
- All docs files not in required reads
- All other workflow files

## Boundary confirmations

- confirm: PR 0030 rebaseline changes present in ROADMAP.md (PR 0031 referenced): yes
- confirm: ECR workflow file exists: yes
- confirm: existing workflow test file exists: yes
- confirm: only workflow file and its test file planned: yes
- confirm: no App Runner service creation/deploy planned: yes
- confirm: no Terraform, Dockerfile, or source code changes planned: yes
- confirm: branch note recorded (current branch is 0030, must switch to 0031): yes
- confirm: no git mutation commands run: yes
- confirm: implementation assigned to Agent: coder / Mode: implementation: yes
