# PR 0032 — Plan App Runner Smoke Service Skeleton

Author: plan
Mode: planning only
Branch: 0032-apprunner-smoke-service-skeleton

## Objective

Add an AWS App Runner smoke/proving-target service skeleton alongside the existing ECS Terraform. This PR creates `infra/terraform/apprunner.tf` and supporting changes — the App Runner service can use the ECR image tagged `app-runner` and health check endpoint `/health`, without applying infrastructure, deploying, loading models, fetching model packages, or changing runtime code.

**Note on PR numbering**: The ROADMAP.md currently sequences PR 0032 as model package fetch/staging and PR 0034 as App Runner Terraform. This task reprioritizes App Runner Terraform to PR 0032. The PR sequence in ROADMAP.md will be updated in a future roadmap amendment PR.

## Required reads — observed facts

### Prerequisites confirmed
- **PR 0030 rebaseline present**: `docs/adr/0008-runtime-target-apprunner-proving.md` exists. ROADMAP records App Runner as near-term proving/testing target. ✓
- **PR 0031 ECR tag present**: `.github/workflows/ecr-publish.yml` contains `app-runner` tag. ✓

### Existing Terraform patterns
- `infra/terraform/main.tf` — AWS provider, region from var, no backend, no hardcoded credentials.
- `infra/terraform/variables.tf` — typed variables with descriptions. ECR repository is `bremen` by default. `ecr_repository_name` exists.
- `infra/terraform/outputs.tf` — `ecr_repository_url` and `ecr_repository_arn` reference the ECR repo.
- `infra/terraform/ecr.tf` — `aws_ecr_repository.bremen` resource.
- `infra/terraform/ecs.tf` — ECS Fargate skeleton (cluster, task definition, service, security group, log group). `desired_count` defaults to 0.
- `infra/terraform/iam.tf` — Execution role (ECR pull + CloudWatch logs) and task role (S3 model read).
- `infra/terraform/README.md` — Documents skeleton purpose, human-only apply rule, validation commands.
- No existing Terraform test files exist under `tests/`.
- No existing App Runner Terraform or any App Runner resource exists.

### ECR repository
- Repository name: `var.ecr_repository_name` (default `"bremen"`).
- Repository URL accessible via `aws_ecr_repository.bremen.repository_url`.
- No hardcoded account ID or registry URL anywhere in the Terraform.

## Targeted discovery results
- No existing `tests/test_bremen_terraform_skeleton.py` or similar file.
- Only workflow/infra test is `tests/test_bremen_ecr_publish_workflow.py` (for ECR workflow, not Terraform).
- No existing repository pattern of Terraform text tests exists.

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Allowed implementation files

The coder may create or modify exactly these files:

1. **`infra/terraform/apprunner.tf`** — NEW. App Runner service skeleton.
2. **`infra/terraform/variables.tf`** — MODIFY. Add App Runner-specific variables.
3. **`infra/terraform/outputs.tf`** — MODIFY. Add App Runner outputs.
4. **`infra/terraform/README.md`** — MODIFY. Document App Runner smoke/proving target and human-only apply boundary.

No test file is created — the repository has no existing Terraform text test pattern, and the scope change (adding variables, outputs, and README docs alongside the new resource) is straightforward Terraform work that does not warrant a new test pattern.

## Forbidden files

- `ROADMAP.md`, `docs/**`, `.project-memory/project_contract.yml`
- `src/**`, `tests/**` (except justified infra test, which is not created)
- `.github/**`, `Dockerfile`, `.dockerignore`
- `requirements.txt`, `pyproject.toml`, `config/**`, `examples/**`, `agents/**`
- `infra/terraform/main.tf` (no provider/backend changes)
- `infra/terraform/ecr.tf`, `infra/terraform/s3.tf`, `infra/terraform/ecs.tf`, `infra/terraform/iam.tf` (unchanged)
- Any `.h5`, `.hdf5`, `.joblib`, `.pkl`, `.npy`, `.npz`
- Deployment secrets, AWS account IDs, account-specific registry URLs, access keys, secret keys

## Exact implementation scope

### 1. `infra/terraform/variables.tf` — Add App Runner variables

Add these new variables:

```hcl
variable "app_runner_image_tag" {
  description = "Image tag used by App Runner auto-deploy. Usually 'app-runner'."
  type        = string
  default     = "app-runner"
}

variable "app_runner_instance_role_arn" {
  description = "ARN of an IAM role to associate with the App Runner service for instance-level permissions. Set to null to skip instance role."
  type        = string
  default     = null
}
```

**`app_runner_image_tag`** — Separate from existing `container_image_tag` (which is for ECS). App Runner watches this specific tag. Default `"app-runner"` matches the CI/CD tag added in PR 0031.

**`app_runner_instance_role_arn`** — Defers creation of a dedicated App Runner instance role. The App Runner service resource accepts a `instance_role_arn` attribute. Setting it to `null` means no instance role is attached. A future PR can create a dedicated role when needed. This keeps the skeleton minimal while leaving room for scoped permissions.

### 2. `infra/terraform/apprunner.tf` — App Runner service skeleton

```hcl
# App Runner service skeleton — smoke / proving / testing target only.
# See ADR-0008 for the full decision.
# ECS Fargate remains the long-term primary production target.

resource "aws_apprunner_service" "bremen_smoke" {
  service_name = "${var.project_name}-apprunner-${var.environment}"

  source_configuration {
    authentication_configuration {
      access_role_arn = var.app_runner_instance_role_arn != null ? var.app_runner_instance_role_arn : null
    }

    image_repository {
      image_configuration {
        port = var.container_port
      }

      image_identifier      = "${aws_ecr_repository.bremen.repository_url}:${var.app_runner_image_tag}"
      image_repository_type = "ECR"

      # NOTE: ECR pull is authenticated by App Runner's internal ECR
      # integration.  No credentials are stored in this Terraform.
    }

    auto_deployments_enabled = true
  }

  health_check_configuration {
    # The existing runtime /health endpoint serves as App Runner health check.
    # A future startup-readiness PR will add a readiness endpoint.
    path = "/health"
  }

  # No instance role by default — use var.app_runner_instance_role_arn when available.

  tags = {
    Name        = "${var.project_name}-apprunner-${var.environment}"
    Environment = var.environment
    Subtarget   = "smoke-proving"
  }
}
```

**Key design decisions:**

| Decision | Value |
|----------|-------|
| Image source | `aws_ecr_repository.bremen.repository_url` (existing ECR repo, no hardcoded URL) |
| Image tag | `var.app_runner_image_tag` (default `"app-runner"`) |
| Health check | `"/health"` — existing runtime endpoint (PR 0026) |
| Auto-deploy | `true` — App Runner automatically deploys when a new `app-runner` tag is pushed (PR 0031) |
| Instance role | `null` by default — deferred to future PR |
| Network/VPC | Not configured — App Runner manages its own network (no VPC/subnet required) |
| IAM access role | Same as instance role — optional, configurable via variable |

### 3. `infra/terraform/outputs.tf` — Add App Runner outputs

```hcl
# App Runner outputs (smoke / proving target)

output "app_runner_service_name" {
  description = "Name of the App Runner smoke/proving service."
  value       = aws_apprunner_service.bremen_smoke.service_name
}

output "app_runner_service_url" {
  description = "URL of the App Runner smoke/proving service."
  value       = aws_apprunner_service.bremen_smoke.service_url
}

output "app_runner_service_arn" {
  description = "ARN of the App Runner smoke/proving service."
  value       = aws_apprunner_service.bremen_smoke.arn
}

output "app_runner_image_tag" {
  description = "Image tag used by App Runner auto-deploy."
  value       = var.app_runner_image_tag
}
```

### 4. `infra/terraform/README.md` — Update documentation

Add a row to the Resource Summary table:

```markdown
| **App Runner service** | Smoke/proving target. Uses ECR image tagged `app-runner`. Health check via `/health`. Not production-ready. |
```

Add a paragraph to the Human-Only Steps section:

```markdown
8. **Before applying App Runner resources, verify:**
   - The `app-runner` image tag exists in ECR (pushed by the CI/CD pipeline).
   - The `/health` endpoint is serving from the runtime container.
   - Auto-deploy is intentional — App Runner will redeploy on every `app-runner` tag push.
   - Review estimated App Runner cost (per-hour and per-vCPU pricing).
```

## Non-goals

- No Terraform apply or AWS commands.
- No model package fetch/staging.
- No startup model loading or readiness probe.
- No inference.
- No Dockerfile changes.
- No ECR workflow changes.
- No source code changes.
- No App Runner instance role creation (deferred — `null` by default).
- No ECS Terraform removal or modification.
- No production-ready claim.
- No clinical claim.
- No replacement of ECS Fargate — App Runner is smoke/proving target only.
- No secrets or account-specific identifiers.

## Validation checklist

The implementation phase (coder) must execute these checks:

```bash
# 1-3) Baseline state
git rev-parse --verify HEAD
git branch --show-current
git status --short

# 4) Changed files
git diff --name-only

# 5) File existence
test -f infra/terraform/apprunner.tf || exit 1

# 6) Terraform format and validate (temp copy)
tmpdir="$(mktemp -d)"
cp -R infra/terraform "$tmpdir/terraform"
terraform -chdir="$tmpdir/terraform" fmt -check -recursive || exit 1
terraform -chdir="$tmpdir/terraform" init -backend=false || exit 1
terraform -chdir="$tmpdir/terraform" validate || exit 1
rm -rf "$tmpdir"
```

### Content checks

```bash
# 7) App Runner resource uses existing ECR repo reference (not hardcoded URL)
grep -n "aws_ecr_repository.bremen.repository_url" infra/terraform/apprunner.tf || exit 1

# 8) App Runner uses app-runner tag variable
grep -n "app_runner_image_tag" infra/terraform/apprunner.tf || exit 1

# 9) Health check path is /health
grep -n "/health" infra/terraform/apprunner.tf || exit 1

# 10) Auto-deploy enabled
grep -n "auto_deployments_enabled" infra/terraform/apprunner.tf || exit 1

# 11) No hardcoded account IDs, registry URLs, secrets
grep -R -n "AWS_ACCESS_KEY_ID\|AWS_SECRET_ACCESS_KEY\|aws_secret_access_key\|account ID\|registry URL\|[0-9]\{12\}\.dkr\.ecr\|[0-9]\{12\}\." infra/terraform/apprunner.tf infra/terraform/variables.tf infra/terraform/outputs.tf || true

# 12) No ECS Terraform modified
git diff --name-only -- infra/terraform/ecs.tf infra/terraform/iam.tf infra/terraform/s3.tf infra/terraform/ecr.tf

# 13) No forbidden file changes
git diff --name-only -- ROADMAP.md docs src tests .github Dockerfile .dockerignore requirements.txt pyproject.toml config examples
# Must return nothing
```

## Rollback plan

1. **Revert `infra/terraform/apprunner.tf`** — delete.
2. **Revert `infra/terraform/variables.tf`** — remove the two App Runner variables.
3. **Revert `infra/terraform/outputs.tf`** — remove the four App Runner outputs.
4. **Revert `infra/terraform/README.md`** — remove App Runner documentation.

No other files affected. Existing ECS Terraform and runtime source are untouched.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only `apprunner.tf`, `variables.tf`, `outputs.tf`, `README.md` changed. |
| **App Runner drift** | Uses existing ECR repo. Image tag from variable (default `app-runner`). Health check `/health`. Auto-deploy enabled. |
| **ECS preservation drift** | ECS Terraform files untouched. ECS remains long-term primary target. |
| **Security drift** | No hardcoded account IDs, registry URLs, or secrets. Instance role deferred (null default). |
| **Test drift** | No test file needed — repository has no existing Terraform text test pattern. |
| **Validation drift** | All validation checks pass. Terraform fmt + init -backend=false + validate pass. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- PR 0030 rebaseline is not present (ADR-0008 missing, App Runner not in ROADMAP).
- PR 0031 `app-runner` image tag is not present in ECR workflow.
- App Runner skeleton requires real AWS account IDs, literal registry URLs, or secrets.
- The change requires source/runtime code, Dockerfile edits, or workflow edits.
- The change requires Terraform apply/AWS commands.
- The change removes or modifies ECS Terraform.
- The implementation cannot stay within allowed files.

## Decisions summary

| Decision | Value |
|----------|-------|
| Image source | `aws_ecr_repository.bremen.repository_url` (existing ECR, no hardcoded URL) |
| Image tag variable | `app_runner_image_tag`, default `"app-runner"` |
| Health check | `"/health"` — existing runtime endpoint |
| Auto-deploy | `true` — App Runner auto-deploys on `app-runner` tag push |
| Instance role | `null` by default — deferred to future PR |
| ECS preservation | All existing ECS files untouched |
| Test file | Not created — no existing Terraform text test pattern in repo |
| Outputs | `app_runner_service_name`, `app_runner_service_url`, `app_runner_service_arn`, `app_runner_image_tag` |
| Variables | `app_runner_image_tag`, `app_runner_instance_role_arn` |

## Commit readiness

- **Planning artifact staged**: `.project-memory/pr/0032-apprunner-smoke-service-skeleton/PLAN.md`
- **Review artifact to be created**: `.project-memory/pr/0032-apprunner-smoke-service-skeleton/reviews/plan-review.yml`
- **PLAN.md + plan-review.yml together**: committed in one commit by human after plan-review approval.
- **Implementation + precommit-review.yml together**: committed in one commit by human after implementation and precommit-review.

## Files read

- `.project-memory/pr/0030-roadmap-adr-apprunner-pivot/reviews/precommit-review.yml`
- `.project-memory/pr/0031-ecr-apprunner-image-tag/reviews/precommit-review.yml`
- `.project-memory/architecture/runtime-model-config-roadmap-rebaseline.md`
- `ROADMAP.md`
- `docs/adr/0008-runtime-target-apprunner-proving.md`
- `.github/workflows/ecr-publish.yml`
- `infra/terraform/README.md`
- `infra/terraform/main.tf`
- `infra/terraform/variables.tf`
- `infra/terraform/outputs.tf`
- `infra/terraform/ecr.tf`
- `infra/terraform/ecs.tf`
- `infra/terraform/iam.tf`

## Files written

- `.project-memory/pr/0032-apprunner-smoke-service-skeleton/PLAN.md` (this file)

## Files intentionally ignored

- All source, runtime, test, workflow, config, and dependency files
- ECS Terraform files (unchanged)
- S3 Terraform file (unchanged)

## Boundary confirmations

- confirm: PR 0030 rebaseline present (ADR-0008, App Runner in ROADMAP): yes
- confirm: PR 0031 `app-runner` tag present in ECR workflow: yes
- confirm: App Runner Terraform skeleton planned (smoke/proving target): yes
- confirm: ECS Terraform preserved unmodified: yes
- confirm: no AWS account IDs, registry URLs, secrets planned: yes
- confirm: instance role deferred (null default): yes
- confirm: auto-deploy enabled: yes
- confirm: health check path `/health`: yes
- confirm: no source/runtime/CI/Docker changes planned: yes
- confirm: no test file created (no existing pattern): yes
- confirm: implementation assigned to Agent: coder / Mode: implementation: yes
- confirm: no git mutation commands run: yes
