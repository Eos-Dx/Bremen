# PR 0022B — Plan ECR Publish Workflow with GitHub OIDC

Author: plan
Mode: planning only
Branch: 0022b-ecr-publish-workflow

## Objective

Add a GitHub Actions workflow for publishing the Bremen Docker image to AWS ECR, authenticated via GitHub OIDC. This is the second half of the 0022 split (0022A = Terraform skeleton, 0022B = CI/ECR publish wiring).

This PR adds a new workflow file and focused static tests. It does not modify Terraform, runtime source, Dockerfile, or dependencies.

## Context

PR 0022A added the Terraform-only AWS runtime foundation with an ECR repository, S3 bucket, ECS Fargate skeleton, and scoped IAM roles. The ECR repository exists as a Terraform resource but there is no workflow to publish images to it.

The existing `quality.yml` publishes to GHCR only (`ghcr.io/eos-dx/bremen`). PR 0022B adds a separate workflow for ECR publish.

## Precondition verification

```
git rev-parse --verify HEAD -> 7a47455196db9a9aaa9773c2932a37bad4df3591
git branch --show-current -> 0022b-ecr-publish-workflow
test -f infra/terraform/main.tf -> present
test -f infra/terraform/ecr.tf -> present
test -f infra/terraform/outputs.tf -> present
test -f Dockerfile -> present
test -f .github/workflows/quality.yml -> present
grep "aws_ecr_repository" infra/terraform/ecr.tf -> found
grep "ecr_repository_url" infra/terraform/outputs.tf -> found
```

All preconditions satisfied. The HEAD contains the PR 0022A Terraform skeleton.

## Architectural split

- PR 0022A = Terraform skeleton (ECR, S3, ECS, IAM, CloudWatch)
- PR 0022B = GitHub Actions ECR publish workflow + OIDC + CI wiring (this PR)

## Exact allowed implementation files

The coder may create or modify exactly these files:

1. **`.github/workflows/ecr-publish.yml`** — NEW. ECR publish workflow.
2. **`tests/test_bremen_ecr_publish_workflow.py`** — NEW. Static workflow tests.

## Exact forbidden files

- `infra/terraform/**` — no Terraform changes
- `src/**` — no source code changes
- `docs/**`, `docs/adr/**`, `ROADMAP.md`, `docs/architecture.md`, `docs/api_contract.md`, `README.md` — no documentation changes
- `requirements.txt`, `pyproject.toml` — no dependency changes
- `Dockerfile`, `.dockerignore` — no Docker build changes
- `.github/workflows/quality.yml` — no changes to existing CI workflow
- `config/**`, `examples/**`, `tests/data/**` — no config/example/data changes
- `agents/**`
- Any H5/HDF5 files, joblib/pkl/npy/npz artifacts
- Any `*.tfstate`, `*.tfstate.backup`, `.terraform/` directories
- `.project-memory/**` outside this PR's own PLAN/reviews

## Required reads (completed for this PLAN.md)

- `.project-memory/project_contract.yml` — safety invariants, human-only git mutation rule
- `AGENTS.md` — agent role definitions
- `Dockerfile` — existing CI build context
- `.github/workflows/quality.yml` — existing GHCR publish workflow as reference for patterns
- `infra/terraform/ecr.tf` — ECR repository name (default `bremen`), confirms repository exists as a resource
- `infra/terraform/outputs.tf` — `ecr_repository_url` output for downstream consumption
- `infra/terraform/README.md` — human-only apply rules
- `docs/adr/0006-multi-target-deployment-and-iac.md` — ECR and IaC decisions
- `docs/adr/0007-model-artifact-lifecycle.md` — model package lifecycle
- `ROADMAP.md` — PR 0022 description

## Implementation phase assignment

- **Agent**: coder
- **Mode**: implementation

## Workflow design: `.github/workflows/ecr-publish.yml`

### Trigger behavior

```yaml
on:
  workflow_dispatch:
  push:
    branches: [main]
```

Rules:
- `workflow_dispatch` — allows manual trigger.
- `push` to `main` — automatic publish on merge to main.
- No `pull_request` trigger — no ECR push from PR branches. PR builds are covered by `quality.yml` (compile, test, GHCR smoke).
- No ECR push from feature branches.

### Permissions

```yaml
permissions:
  contents: read
  id-token: write
```

Rules:
- `contents: read` — checkout repository code.
- `id-token: write` — required for GitHub OIDC to obtain an AWS credential.
- No `packages: write` — this is ECR, not GHCR. ECR authentication uses OIDC, not GITHUB_TOKEN.

### AWS authentication via OIDC

```yaml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: ${{ vars.AWS_ROLE_TO_ASSUME }}
    aws-region: ${{ vars.AWS_REGION }}
```

Rules:
- Uses `aws-actions/configure-aws-credentials@v4` with OIDC.
- `role-to-assume` from `vars.AWS_ROLE_TO_ASSUME` (repository or organization variable configured by human).
- `aws-region` from `vars.AWS_REGION` (repository or organization variable configured by human).
- No static AWS access keys (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`).
- No hardcoded account IDs.
- No committed secret values.

### ECR login and build/push

```yaml
- name: Log in to Amazon ECR
  id: login-ecr
  uses: aws-actions/amazon-ecr-login@v2

- name: Build and push image
  id: build-push
  env:
    ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
    ECR_REPOSITORY: ${{ vars.ECR_REPOSITORY || 'bremen' }}
    IMAGE_TAG: ${{ github.sha }}
  run: |
    docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
    docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG

    # On push to main, also tag and push 'latest'
    if [ "${{ github.ref }}" = "refs/heads/main" ]; then
      docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
      docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest
    fi
```

Rules:
- Uses `aws-actions/amazon-ecr-login@v2` for ECR authentication.
- ECR repository name from `vars.ECR_REPOSITORY` with default `"bremen"`.
- Image tag with `${{ github.sha }}` on every push to main.
- `latest` tag added only on `push` to `main` (the only event that triggers automatic runs).
- Uses the repository's existing Dockerfile (no changes, build context `.`).
- Skips Docker build if Docker daemon is unavailable (handled by the runner type).

### What the workflow does NOT do

- No `terraform apply`, `terraform destroy`, or `terraform init`.
- No `aws ecs update-service`.
- No `kubectl` or `helm` commands.
- No deployment to ECS or any runtime environment.
- No Docker Compose.
- No publish to GHCR (separate workflow for that).
- No modification of Terraform or runtime source.

### Recommended shape

```yaml
name: ECR Publish

on:
  workflow_dispatch:
  push:
    branches: [main]

permissions:
  contents: read
  id-token: write

env:
  AWS_REGION: ${{ vars.AWS_REGION }}
  AWS_ROLE_TO_ASSUME: ${{ vars.AWS_ROLE_TO_ASSUME }}
  ECR_REPOSITORY: ${{ vars.ECR_REPOSITORY || 'bremen' }}

jobs:
  publish:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ env.AWS_ROLE_TO_ASSUME }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Log in to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push image
        id: build-push
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build \
            -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG \
            .

          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG

          docker tag \
            $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG \
            $ECR_REGISTRY/$ECR_REPOSITORY:latest

          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest
```

## Static workflow tests: `tests/test_bremen_ecr_publish_workflow.py`

The test file must parse/read `.github/workflows/ecr-publish.yml` (YAML) and verify:

1. Workflow file exists.
2. Trigger includes `workflow_dispatch`.
3. Trigger includes `push` to `main` (via branch name match or ref pattern).
4. Trigger does NOT include `pull_request`.
5. Permissions include `id-token: write`.
6. Permissions include `contents: read`.
7. Workflow uses `aws-actions/configure-aws-credentials`.
8. Workflow uses `aws-actions/amazon-ecr-login`.
9. Workflow uses Docker build action or `docker build` command.
10. Workflow references Docker build context `.`.
11. Workflow tags with `github.sha`.
12. Workflow does NOT run `terraform apply`.
13. Workflow does NOT run `terraform destroy`.
14. Workflow does NOT run `terraform init`.
15. Workflow does NOT run `aws ecs update-service`.
16. Workflow does NOT run `kubectl`.
17. Workflow does NOT run `helm`.
18. Workflow does NOT contain `AWS_ACCESS_KEY_ID`.
19. Workflow does NOT contain `AWS_SECRET_ACCESS_KEY`.
20. Workflow does NOT contain hardcoded AWS access-key-looking values (e.g., AKIA pattern).
21. Workflow does NOT publish on `pull_request`.
22. Workflow does NOT modify or depend on local machine paths.
23. Terraform files are unchanged in this PR (verify via `git diff --name-only` — this is a test assertion, not a production import).

Tests use `yaml.safe_load` to parse the workflow file (import `yaml` is already available as a project dependency). No subprocess calls to GitHub Actions runner.

## Non-goals

- No Terraform changes.
- No `terraform apply`/`destroy`/`init`.
- No ECS deploy or `update-service`.
- No runtime source changes.
- No API behavior changes.
- No Dockerfile changes.
- No dependency changes (`pyproject.toml`, `requirements.txt`).
- No model loading, inference, preprocessing.
- No H5/HDF5 reads.
- No Matador integration.
- No config sourcing implementation.
- No docs/ADR/ROADMAP changes.
- No APRANA work.
- No static AWS credentials.
- No GHCR workflow changes (existing `quality.yml` unaffected).

## Validation checklist

The implementation phase (coder) must execute these checks:

```bash
# 1-3) Baseline state
git rev-parse --verify HEAD
git branch --show-current
git status --short

# 4) Changed files
git diff --name-only

# 5-6) File existence
test -f .github/workflows/ecr-publish.yml || exit 1
test -f tests/test_bremen_ecr_publish_workflow.py || exit 1

# 7-12) Python compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_ecr_publish_workflow.py
python -m pytest -q tests/test_bremen_dependency_hygiene.py
python -m pytest -q tests/test_bremen_api_skeleton.py
python -m pytest -q
python -m bremen --help

# 13) No pull_request trigger — ECR not published from PRs
grep -R -I -n "pull_request" .github/workflows/ecr-publish.yml || true

# 14-15) Required actions present
grep -n "aws-actions/configure-aws-credentials" .github/workflows/ecr-publish.yml
grep -n "aws-actions/amazon-ecr-login" .github/workflows/ecr-publish.yml

# 16) OIDC permission present
grep -n "id-token: write" .github/workflows/ecr-publish.yml

# 17) No Terraform commands
grep -R -I -n "terraform apply\|terraform destroy\|terraform init" .github/workflows/ecr-publish.yml || true

# 18) No ECS deploy or Kubernetes
grep -R -I -n "aws ecs update-service\|kubectl\|helm" .github/workflows/ecr-publish.yml || true

# 19) No static AWS credentials
grep -R -I -n "AWS_ACCESS_KEY_ID\|AWS_SECRET_ACCESS_KEY\|aws_access_key_id\|aws_secret_access_key\|AKIA" .github/workflows/ecr-publish.yml || true

# 20) No forbidden file changes
git diff --name-only -- infra/terraform src docs ROADMAP.md docs/architecture.md docs/api_contract.md requirements.txt pyproject.toml Dockerfile .dockerignore config examples tests/data agents
# Must return nothing

# 21) No H5/model/tfstate artifacts
git diff --name-only | grep -E "\.(h5|hdf5|joblib|pkl|npy|npz|tfstate|tfstate\.backup)$" || true

# 22) .DS_Store check
find . -name ".DS_Store" -print
```

## Rollback plan

1. Remove `.github/workflows/ecr-publish.yml`.
2. Remove `tests/test_bremen_ecr_publish_workflow.py`.
3. No Terraform rollback needed — Terraform files are unchanged.
4. No runtime rollback needed — no runtime files are touched.
5. No cloud rollback needed — this PR does not deploy or apply.

## Follow-up PRs

- **PR 0020** — Cloud-aware config sourcing consuming Terraform outputs and ECR image naming conventions.
- **Future PR** — ECS deploy/update-service workflow, only after runtime server wiring and human cloud readiness gates.
- **Future PR** — Actual HTTP server/runtime runner wiring before raising ECS `desired_count` above 0.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only `.github/workflows/ecr-publish.yml` and `tests/test_bremen_ecr_publish_workflow.py` changed. |
| **Workflow drift** | Triggered by workflow_dispatch and push to main. No pull_request. Permissions: contents:read + id-token:write. Uses OIDC. No static AWS keys. No Terraform commands. No ECS deploy. |
| **Terraform drift** | No Terraform files changed. No changes to infra/terraform/. |
| **Source/Docker drift** | No source, Dockerfile, or dependency changes. |
| **Test drift** | Static workflow tests cover all requirements. No subprocess calls. |
| **Validation drift** | All validation checks pass. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- PLAN omits `.github/workflows/ecr-publish.yml`.
- PLAN omits focused static workflow tests.
- PLAN modifies Terraform files (`infra/terraform/**`).
- PLAN modifies source/runtime code (`src/**`).
- PLAN modifies Dockerfile or dependencies.
- PLAN includes `terraform apply`/`destroy`/`init` commands.
- PLAN deploys ECS (`aws ecs update-service`).
- PLAN uses static AWS access keys (not OIDC).
- PLAN allows ECR push on `pull_request`.
- PLAN hardcodes AWS credentials or account IDs.
- PLAN implements APRANA.
- Implementation phase is not Agent: coder / Mode: implementation.

## Decisions summary

### Allowed files
1. `.github/workflows/ecr-publish.yml` — NEW
2. `tests/test_bremen_ecr_publish_workflow.py` — NEW

### Forbidden files
- `infra/terraform/**`, `src/**`, `docs/**`, all ADRs, ROADMAP.md, README.md
- `Dockerfile`, `.dockerignore`, `.github/workflows/quality.yml`
- `requirements.txt`, `pyproject.toml`, `config/**`, `examples/**`, `tests/data/**`
- `agents/**`, H5/HDF5, model artifacts, tfstate files

### Precondition summary
- PR 0022A Terraform skeleton present ✓
- `infra/terraform/ecr.tf`, `infra/terraform/outputs.tf`, `infra/terraform/main.tf` all present ✓
- ECR repository resource exists in Terraform ✓

### ECR workflow summary
- Trigger: `workflow_dispatch` + `push` to `main`.
- No `pull_request` trigger.
- Permissions: `contents: read`, `id-token: write`.
- AWS auth: OIDC via `aws-actions/configure-aws-credentials@v4` (role-to-assume from vars).
- ECR login: `aws-actions/amazon-ecr-login@v2`.
- Build: existing Dockerfile.
- Push: tagged with `github.sha` and `latest`.
- No Terraform, ECS deploy, Kubernetes, or Helm.

### OIDC / credential boundary summary
- No static AWS access keys.
- No `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY`.
- No hardcoded account IDs.
- No committed secret values.
- All configurable values from repository/org variables (`vars.*`).

### Testing summary
1 test file, 23 assertions: trigger checks, permission checks, action presence, Terraform/K8s prohibition, static credential prohibition, local-path checks.

### Validation summary
22 checks: git state, file existence, compileall, workflow tests, existing tests (dependency hygiene, API skeleton, full suite), CLI help, workflow content checks (pull_request, OIDC actions, Terraform, K8s, static credentials), forbidden path check, artifact scan, .DS_Store.

### Rollback summary
Delete the workflow file and test file. No Terraform/runtime/cloud rollback needed.

### Follow-up sequencing
PR 0020 (cloud config) → future ECS deploy workflow → future HTTP server wiring.

## Exact human commit instructions for planning artifacts

This PLAN.md is a planning artifact only. No implementation files have been created or modified.

1. Planner writes this file: `.project-memory/pr/0022b-ecr-publish-workflow/PLAN.md`
2. Human runs: `git add .project-memory/pr/0022b-ecr-publish-workflow/PLAN.md`
3. Human runs: `git commit -m "PR 0022B — Plan ECR publish workflow with GitHub OIDC"`
4. Human pushes the branch for plan-review.
5. After plan-review approves, the coder implements the two allowed files.

## Files read

- `.project-memory/project_contract.yml`
- `AGENTS.md`
- `Dockerfile`
- `.github/workflows/quality.yml`
- `infra/terraform/ecr.tf`
- `infra/terraform/outputs.tf`
- `infra/terraform/README.md`
- `docs/adr/0006-multi-target-deployment-and-iac.md`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `ROADMAP.md`

## Files written

- `.project-memory/pr/0022b-ecr-publish-workflow/PLAN.md` (this file)

## Files intentionally ignored

- All Terraform files — not modified.
- All source files — not modified.
- All docs files — not modified.
- Existing CI workflow (quality.yml) — not modified.
- Dockerfile — not modified.
- Any H5/HDF5 or model artifact files.

## Boundary confirmations

- confirm: PR 0022A Terraform skeleton present on branch HEAD: yes
- confirm: this PR plans exactly workflow + static workflow tests: yes
- confirm: no Terraform changes planned: yes
- confirm: no source/runtime changes planned: yes
- confirm: no Dockerfile/dependency changes planned: yes
- confirm: no terraform apply/destroy/init planned: yes
- confirm: no ECS deploy/update-service planned: yes
- confirm: no ECR push on pull_request planned: yes
- confirm: OIDC planned, static AWS keys forbidden: yes
- confirm: no APRANA planned: yes
- confirm: implementation assigned to Agent: coder / Mode: implementation: yes
- confirm: no git mutation commands run: yes
