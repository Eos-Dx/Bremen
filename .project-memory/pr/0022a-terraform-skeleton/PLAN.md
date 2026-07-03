# PR 0022A — Plan Terraform Skeleton for AWS Runtime Foundation

Author: plan
Mode: planning only
Branch: 0022a-terraform-skeleton

## Objective

Add a Terraform skeleton defining Bremen's AWS runtime infrastructure: ECR repository, S3 versioned bucket, ECS Fargate cluster/service/task definition, CloudWatch log group, and scoped IAM roles. This is PR 0022A (Terraform only). PR 0022B adds the GitHub Actions ECR publish workflow.

## Context

This PR implements infrastructure decisions already recorded:

- G-INFRA-1 = DECIDED: Terraform (PR 0012)
- G-API-2 = DECIDED: ECS Fargate (PR 0012)
- ADR-0006 = AWS ECR and IaC required; APRANA remains unverified
- ADR-0007 = initial model artifact store is an S3 versioned bucket
- PR 0019 = API contract + async microservice skeleton exists
- PR 0021 = local container dependency path hygiene completed

This PR does not deploy infrastructure, does not apply Terraform, and does not use real AWS credentials. It creates a validatable but not-yet-applied IaC skeleton.

## Split convention

PR 0022A (this PR) = Terraform files only.
PR 0022B (future) = GitHub Actions ECR publish job / OIDC / CI wiring.

## Precondition verification

```
git rev-parse --verify HEAD -> 450f25ff753c3f32a5ab25c4cfd307ac7125e11a
git branch --show-current -> 0022a-terraform-skeleton
test -f docs/adr/0006-multi-target-deployment-and-iac.md -> present
test -f docs/adr/0007-model-artifact-lifecycle.md -> present
grep -n "G-INFRA-1" ROADMAP.md -> found, line 58 (DECIDED: Terraform)
grep -n "G-API-2" ROADMAP.md -> found, line 55 (DECIDED: ECS Fargate)
grep "DECIDED" ROADMAP.md -> 5 occurrences
grep "Terraform" ROADMAP.md -> found (DECIDED)
grep "ECS Fargate" ROADMAP.md -> found (DECIDED)
```

All preconditions satisfied.

## Exact allowed implementation files

The coder may create exactly these 8 files under `infra/terraform/`:

1. `infra/terraform/main.tf`
2. `infra/terraform/variables.tf`
3. `infra/terraform/outputs.tf`
4. `infra/terraform/ecr.tf`
5. `infra/terraform/s3.tf`
6. `infra/terraform/ecs.tf`
7. `infra/terraform/iam.tf`
8. `infra/terraform/README.md`

## Forbidden files

- `.github/**`, `docs/adr/**`, `ROADMAP.md`, `docs/architecture.md`, `docs/api_contract.md`
- `README.md`, `docs/roadmap.md`, `docs/machine_learning_concept.md`, `docs/repository_cleanup.md`
- `docs/product_development_rules.md`, `AGENTS.md`
- `src/**`, `tests/**`, `config/**`, `examples/**`
- `Dockerfile`, `.dockerignore`, `sonar-project.properties`, `requirements.txt`, `pyproject.toml`, `environment.yml`, `Makefile`
- `agents/**`
- Any `*.tfstate`, `*.tfstate.backup`, `.terraform/` directories
- Any H5/HDF5 files, joblib/pkl/npy/npz artifacts
- `.project-memory/**` outside this PR's own PLAN/reviews

## Required reads (completed for this PLAN.md)

- `docs/adr/0006-multi-target-deployment-and-iac.md` — ECR and IaC requirements
- `docs/adr/0007-model-artifact-lifecycle.md` — S3 versioned bucket for model packages
- `ROADMAP.md` — G-INFRA-1/G-API-2 decisions, PR 0022 description
- `docs/architecture.md` — AWS runtime/deployment default decisions
- `docs/api_contract.md` — API endpoints for context
- `Dockerfile` — current build (establishes port 8000 is not yet configured; container_port default 8000 is forward-looking scaffolding)
- `.github/workflows/quality.yml` — current CI (no ECR publish)
- `requirements.txt` — no AWS SDK dependencies
- `.project-memory/project_contract.yml` — safety invariants
- `AGENTS.md` — agent role definitions

## Directory decision: `infra/terraform/`

Using `infra/terraform/` rather than a bare root-level `terraform/` directory keeps deployment infrastructure isolated from Bremen runtime source, docs, and future non-AWS deployment assets (e.g., `infra/helm/`, `infra/cdk/`) while leaving room for future infra subdirectories. It is a convention used in many production repositories to separate infrastructure code from application code.

## Implementation phase assignment

- **Agent**: coder
- **Mode**: implementation

## Human-only cloud mutation boundary

The following rules are binding for all agents:

- Agents may write Terraform files only.
- Agents may run `terraform fmt -check`.
- Agents may run `terraform init -backend=false` only against a **temporary copy outside the repository**.
- Agents may run `terraform validate` only after local backend-disabled init in the temporary copy.
- Agents must NOT run `terraform apply`.
- Agents must NOT run `terraform destroy`.
- Agents must NOT run Terraform init against a real or remote backend.
- Agents must NOT use real AWS credentials.
- Agents must NOT create, update, or destroy cloud resources.
- Real backend configuration and first apply are human-only actions.

## Planned Terraform files

### 1. `infra/terraform/main.tf`

```hcl
terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }

  # Backend intentionally omitted.
  # Human operators must configure a remote backend before any apply.
}

provider "aws" {
  region = var.aws_region

  # No hardcoded credentials. Use AWS CLI / environment variables / IAM role.
}
```

Rules:
- No `backend` block — comment explains remote backend is intentionally absent until a human explicitly configures it.
- No hardcoded AWS account ID.
- No hardcoded credentials.
- Region from `var.aws_region`.

### 2. `infra/terraform/variables.tf`

Required variables with descriptions:

| Variable | Default | Description |
|----------|---------|-------------|
| `aws_region` | (required, no default) | AWS region for all resources |
| `project_name` | `"bremen"` | Project name for resource tagging/names |
| `environment` | `"dev"` | Deployment environment (dev, staging, prod) |
| `service_name` | `"bremen"` | Service name for ECS resources |
| `ecr_repository_name` | `"bremen"` | ECR repository name for the Bremen service image |
| `model_bucket_name` | (required, no default) | Name of the S3 bucket for model packages. Human must provide a globally unique name. |
| `model_package_prefix` | `"model-packages/"` | Prefix within the model bucket for model package objects |
| `vpc_id` | (required, no default) | VPC ID where ECS resources are deployed |
| `private_subnet_ids` | (required, no default) | List of private subnet IDs for ECS service placement |
| `allowed_ingress_cidr_blocks` | `[]` | List of CIDR blocks allowed to reach the service (dev-only placeholder by default) |
| `container_port` | `8000` | Port the Bremen container listens on (planned; PR 0019 skeleton does not yet serve HTTP) |
| `container_cpu` | `512` | CPU units for the Fargate task |
| `container_memory` | `1024` | Memory (MiB) for the Fargate task |
| `desired_count` | `0` | Desired number of ECS service tasks. Default 0 — human must intentionally raise for deployment |
| `container_image_tag` | `"latest"` | Tag of the Bremen image to deploy |
| `log_retention_days` | `14` | CloudWatch log group retention in days |

Rules:
- All variables have descriptions.
- No secret values.
- No local machine paths.
- No account-specific defaults.
- `desired_count` default is 0 (no automatic deployment).
- `model_bucket_name` has no default — human must provide a globally unique name.

### 3. `infra/terraform/ecr.tf`

```hcl
resource "aws_ecr_repository" "bremen" {
  name                 = var.ecr_repository_name
  image_tag_mutability = "MUTABLE"

  # Image scanning on push enabled for vulnerability detection
  image_scanning_configuration {
    scan_on_push = true
  }

  # TODO: Add lifecycle policy when retention requirements are known.
  # Current default: no automatic deletion. A lifecycle policy should be
  # added before production use to manage untagged and old images.
}

output "ecr_repository_url" {
  value = aws_ecr_repository.bremen.repository_url
}

output "ecr_repository_arn" {
  value = aws_ecr_repository.bremen.arn
}
```

Rules:
- Image scanning on push enabled.
- Tag mutability: MUTABLE (deliberately chosen for dev agility; reconsider before production).
- Lifecycle policy left as a TODO comment (not an arbitrary retention assumption).
- Outputs consumed via `outputs.tf`.

### 4. `infra/terraform/s3.tf`

```hcl
resource "aws_s3_bucket" "model_packages" {
  bucket = var.model_bucket_name

  # Human responsibility: ensure bucket name is globally unique.
  # No force_destroy true by default — protect against accidental deletion.
}

resource "aws_s3_bucket_versioning" "model_packages" {
  bucket = aws_s3_bucket.model_packages.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "model_packages" {
  bucket = aws_s3_bucket.model_packages.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "model_packages" {
  bucket = aws_s3_bucket.model_packages.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

Rules:
- Bucket name from `var.model_bucket_name` (human-provided, globally unique).
- Versioning enabled.
- Server-side encryption enabled (AES256).
- Public access block with all four settings true.
- No public bucket policy.
- No write permissions granted in this PR.
- No model artifacts committed.

### 5. `infra/terraform/ecs.tf`

```hcl
# CloudWatch log group for ECS service logs
resource "aws_cloudwatch_log_group" "bremen" {
  name              = "/ecs/${var.service_name}"
  retention_in_days = var.log_retention_days
}

# ECS cluster
resource "aws_ecs_cluster" "bremen" {
  name = "${var.project_name}-${var.environment}"
}

# Security group for the ECS service
resource "aws_security_group" "bremen_service" {
  name        = "${var.service_name}-${var.environment}"
  description = "Security group for Bremen ECS service"
  vpc_id      = var.vpc_id

  # Ingress from allowed CIDRs (dev-only by default)
  dynamic "ingress" {
    for_each = var.allowed_ingress_cidr_blocks
    content {
      from_port   = var.container_port
      to_port     = var.container_port
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  # Egress: allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.service_name}-${var.environment}"
    Environment = var.environment
  }
}

# Task definition
resource "aws_ecs_task_definition" "bremen" {
  family                   = var.service_name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.container_cpu
  memory                   = var.container_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = var.service_name
      image     = "${aws_ecr_repository.bremen.repository_url}:${var.container_image_tag}"
      essential = true

      portMappings = [
        {
          containerPort = var.container_port
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "BREMEN_MODEL_BUCKET"
          value = aws_s3_bucket.model_packages.bucket
        },
        {
          name  = "BREMEN_MODEL_PREFIX"
          value = var.model_package_prefix
        },
        {
          name  = "BREMEN_MODEL_VERSION"
          value = ""
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.bremen.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  # NOTE: This is infrastructure scaffolding. PR 0019 created a
  # framework-neutral API skeleton, not a real HTTP server. A future
  # PR will wire an actual service runner before any production
  # deployment. desired_count defaults to 0 to prevent automatic
  # deployment.
}

# ECS service
resource "aws_ecs_service" "bremen" {
  name            = "${var.service_name}-${var.environment}"
  cluster         = aws_ecs_cluster.bremen.id
  task_definition = aws_ecs_task_definition.bremen.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [aws_security_group.bremen_service.id]
    assign_public_ip = false
  }

  # NOTE: This is scaffolding pending real HTTP serving / deployment
  # decisions. desired_count defaults to 0. No load balancer is
  # configured at this stage.
}
```

Rules:
- Task definition uses Fargate compatibility, awsvpc network mode.
- CPU/memory from variables.
- ECR repository URL by Terraform reference, not hardcoded.
- Image tag from variable.
- Log driver: awslogs, linked to the CloudWatch log group.
- Environment variables: `BREMEN_MODEL_BUCKET`, `BREMEN_MODEL_PREFIX`, `BREMEN_MODEL_VERSION` (optional/empty).
- Service uses launch_type FARGATE, private subnets, security group.
- `desired_count` defaults to 0.
- No load balancer in this PR.
- Comment stating this is scaffolding, not a functioning production API.

### 6. `infra/terraform/iam.tf`

```hcl
# ECS task execution role
resource "aws_iam_role" "ecs_execution" {
  name = "${var.service_name}-execution-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

# ECS task execution role policy — scoped to ECR pull and CloudWatch logs
resource "aws_iam_role_policy" "ecs_execution" {
  name = "${var.service_name}-execution-policy-${var.environment}"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECRAuth"
        Effect = "Allow"
        Action = "ecr:GetAuthorizationToken"
        Resource = "*"
        # AWS-required: ECR does not support repository-level scoping
        # for GetAuthorizationToken. This is the only wildcard Resource
        # exception.
      },
      {
        Sid    = "ECRPull"
        Effect = "Allow"
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchCheckLayerAvailability",
        ]
        Resource = aws_ecr_repository.bremen.arn
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "${aws_cloudwatch_log_group.bremen.arn}:*"
      },
    ]
  })
}

# ECS task role
resource "aws_iam_role" "ecs_task" {
  name = "${var.service_name}-task-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

# ECS task role policy — scoped to model package read access only
resource "aws_iam_role_policy" "ecs_task" {
  name = "${var.service_name}-task-policy-${var.environment}"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3ModelRead"
        Effect = "Allow"
        Action = "s3:GetObject"
        Resource = "${aws_s3_bucket.model_packages.arn}/${var.model_package_prefix}*"
      },
    ]
  })
}
```

IAM least-privilege summary:

| Permission | Resource scope | Notes |
|------------|---------------|-------|
| `ecr:GetAuthorizationToken` | `*` | Wildcard exception required by AWS; ECR does not support repository-level scoping for this action. Commented with explanation. |
| `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer`, `ecr:BatchCheckLayerAvailability` | This ECR repository ARN | Scoped to this project's ECR repo |
| `logs:CreateLogStream`, `logs:PutLogEvents` | Log group ARN plus `:*` suffix | Scoped to this project's log group |
| `s3:GetObject` | Bucket ARN with model package prefix | Read-only model artifact access |
| `s3:PutObject`, `s3:DeleteObject` | — | NOT granted |
| `s3:ListBucket` | — | NOT granted (no reason identified) |
| Managed policies (`AmazonECSTaskExecutionRolePolicy`, etc.) | — | NOT used (no broad managed policy attachments) |
| Wildcard `Action` | — | NOT used |
| Wildcard `Resource` (except ecr:GetAuthorizationToken with comment) | — | NOT used |

### 7. `infra/terraform/outputs.tf`

Include outputs for:

- `ecr_repository_url` — URL of the ECR repository.
- `ecr_repository_arn` — ARN of the ECR repository.
- `model_bucket_name` — Name of the model package S3 bucket.
- `model_bucket_arn` — ARN of the model package S3 bucket.
- `model_package_prefix` — Prefix for model package objects.
- `ecs_cluster_name` — Name of the ECS cluster.
- `ecs_service_name` — Name of the ECS service.
- `task_definition_arn` — ARN of the ECS task definition.
- `task_execution_role_arn` — ARN of the ECS task execution role.
- `task_role_arn` — ARN of the ECS task role.
- `log_group_name` — Name of the CloudWatch log group.
- `service_security_group_id` — ID of the ECS service security group.

PLAN.md states: PR 0020 (cloud-aware config sourcing) should consume these outputs later. These outputs are not secrets.

### 8. `infra/terraform/README.md`

Must include:
- Purpose of the Terraform skeleton.
- Resource summary (ECR, S3, ECS, CloudWatch, IAM).
- Explicit statement: agents must not run `terraform apply`.
- Human-only steps before any apply:
  1. Choose/configure real AWS account.
  2. Configure credentials locally or via deliberate CI role.
  3. Configure remote state backend deliberately.
  4. Review IAM policy line by line.
  5. Review expected cost.
  6. Set real VPC/subnet variables.
  7. Decide `desired_count > 0` intentionally.
- Validation commands for humans/agents:
  - `terraform fmt -check`
  - `terraform init -backend=false` against temp copy
  - `terraform validate`
- No production readiness claim.
- No APRANA instructions.
- No secrets.

## Validation checklist

The implementation phase (coder) must execute these checks. For Terraform validation, use a temporary copy as described.

```bash
# 1-3) Baseline state
git rev-parse --verify HEAD
git branch --show-current
git status --short

# 4) Changed files
git diff --name-only

# 5-12) File existence
test -f infra/terraform/main.tf || exit 1
test -f infra/terraform/variables.tf || exit 1
test -f infra/terraform/outputs.tf || exit 1
test -f infra/terraform/ecr.tf || exit 1
test -f infra/terraform/s3.tf || exit 1
test -f infra/terraform/ecs.tf || exit 1
test -f infra/terraform/iam.tf || exit 1
test -f infra/terraform/README.md || exit 1

# 13) Terraform format check
terraform fmt -check -recursive infra/terraform/

# 14) Terraform validate (against temp copy to avoid .terraform/ in repo)
cp -r infra/terraform /tmp/terraform-validate-0022a
terraform -chdir=/tmp/terraform-validate-0022a init -backend=false
terraform -chdir=/tmp/terraform-validate-0022a validate
rm -rf /tmp/terraform-validate-0022a
```

### IAM content checks

```bash
# 15) ECR auth wildcard exception present with AWS-required comment
grep -n "ecr:GetAuthorizationToken" infra/terraform/iam.tf
grep -n "AWS-required" infra/terraform/iam.tf

# 16) ECR repo-scoped actions present
grep -n "ecr:BatchGetImage" infra/terraform/iam.tf
grep -n "ecr:GetDownloadUrlForLayer" infra/terraform/iam.tf
grep -n "ecr:BatchCheckLayerAvailability" infra/terraform/iam.tf

# 17) S3 read-only scope present
grep -n "s3:GetObject" infra/terraform/iam.tf

# 18) Logs stream scope present
grep -n "logs:CreateLogStream" infra/terraform/iam.tf
grep -n "logs:PutLogEvents" infra/terraform/iam.tf

# 19) Forbidden IAM patterns must return no output
grep -R -I -n "s3:PutObject\|s3:DeleteObject\|AdministratorAccess\|AmazonECSTaskExecutionRolePolicy" infra/terraform/iam.tf || true
```

### S3 content checks

```bash
# 20) Public access block settings present
grep -n "block_public_acls\|block_public_policy\|ignore_public_acls\|restrict_public_buckets" infra/terraform/s3.tf

# 21) Versioning present
grep -n "versioning" infra/terraform/s3.tf
```

### ECR and ECS content checks

```bash
# 22) ECR repository resource present
grep -n "aws_ecr_repository" infra/terraform/ecr.tf

# 23) ECS resources present
grep -n "aws_ecs_cluster\|aws_ecs_service\|aws_ecs_task_definition" infra/terraform/ecs.tf

# 24) desired_count references
grep -n "desired_count" infra/terraform/ecs.tf infra/terraform/variables.tf

# 25) desired_count default is 0
grep -n "default *= *0" infra/terraform/variables.tf
```

### Security and compliance checks

```bash
# 26) No AWS credentials committed
grep -R -I -n "AKIA\|aws_access_key\|aws_secret_access_key\|BEGIN RSA\|private_key" infra/terraform/ || true

# 27) No APRANA references
grep -R -I -n "APRANA\|aprana" infra/terraform/ || true

# 28) No tfstate artifacts
find infra/terraform -name "*.tfstate*" -o -name ".terraform" -type d

# 29) No forbidden files changed
git diff --name-only -- .github README.md docs docs/adr ROADMAP.md docs/architecture.md src tests config examples Dockerfile .dockerignore requirements.txt pyproject.toml environment.yml Makefile agents || true

# 30) .DS_Store check
find . -name ".DS_Store" -print
```

## Rollback plan

1. Remove the 8 `infra/terraform/` files.
2. Confirm no `.terraform/`, `.tfstate`, or credentials were committed.
3. No source/runtime rollback needed because no runtime files are touched.

## Non-goals

- No GitHub Actions / CI workflow changes (delegated to PR 0022B).
- No ECR publish workflow.
- No `terraform apply` or `terraform destroy`.
- No real/remote backend init by agents.
- No real AWS credentials.
- No cloud resource creation.
- No source/runtime code changes.
- No API behavior changes.
- No model loading, inference, H5/HDF5 reads, or preprocessing.
- No Matador integration.
- No config sourcing implementation.
- No dependency changes.
- No Dockerfile changes.
- No tests directory changes.
- No docs/ADR/ROADMAP/architecture changes.
- No APRANA resources.
- No hardcoded AWS account IDs or secrets.

## Follow-up PRs

- **PR 0022B** — GitHub Actions ECR publish workflow using OIDC.
- **PR 0020** — Cloud-aware config sourcing consuming Terraform outputs.
- **Future human-only action/PR** — Configure remote Terraform state and perform first reviewed apply.
- **Future PR** — Actual HTTP server / runtime runner wiring before `desired_count` is raised above 0.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only the 8 `infra/terraform/` files changed. No other files. |
| **Terraform drift** | All 8 files present. Valid format and validate. No backend block. No hardcoded account IDs or credentials. |
| **IAM drift** | Least-privilege. ECR auth wildcard with AWS-required comment. No wildcard Action. No broad managed policies. No s3 write/delete. |
| **S3 drift** | Versioning enabled. Public access block all four settings true. Server-side encryption enabled. |
| **ECS drift** | Fargate. awsvpc. Scaffolding comment. desired_count default 0. No load balancer. |
| **PR split drift** | No CI/GitHub Actions content. Delegated to PR 0022B. |
| **Human-only cloud mutation drift** | Agents must not run terraform apply/destroy. Must not use real AWS credentials. Must not init against real backend. |
| **Validation drift** | All 30 validation checks pass. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Any of the 8 Terraform files is missing from the plan.
- PR includes GitHub Actions or CI workflow content (delegated to PR 0022B).
- Plan allows agent-run `terraform apply` or `terraform destroy`.
- Plan allows real-backend Terraform init by agents.
- Plan uses real AWS credentials.
- Plan hardcodes AWS account IDs, access keys, or secrets.
- Plan attaches broad AWS managed IAM policies.
- Plan allows wildcard `Action`.
- Plan allows wildcard `Resource` except `ecr:GetAuthorizationToken` with an AWS-required comment.
- Plan grants `s3:PutObject` or `s3:DeleteObject`.
- Plan omits S3 versioning.
- Plan omits S3 public access block.
- Plan sets `desired_count` default above 0.
- Plan describes ECS as a functioning production API.
- Plan modifies `.github`, source, tests, docs, ROADMAP, requirements, pyproject, Dockerfile, config, examples, agents, H5/model artifacts.
- Implementation phase is not Agent: coder / Mode: implementation.

## Decisions summary

### Allowed files
`infra/terraform/main.tf`, `infra/terraform/variables.tf`, `infra/terraform/outputs.tf`, `infra/terraform/ecr.tf`, `infra/terraform/s3.tf`, `infra/terraform/ecs.tf`, `infra/terraform/iam.tf`, `infra/terraform/README.md` (all NEW).

### Precondition summary
- G-INFRA-1 DECIDED: Terraform ✓
- G-API-2 DECIDED: ECS Fargate ✓
- ADR-0006 present ✓
- ADR-0007 present ✓

### Terraform resource summary
- `main.tf` — AWS provider, region from variable, no backend, no hardcoded credentials.
- `variables.tf` — 15 variables with descriptions, no secrets, no machine paths, `desired_count` default 0.
- `ecr.tf` — ECR repository, scan on push, tag mutability MUTABLE, lifecycle policy TODO.
- `s3.tf` — S3 versioned bucket, encryption, all-four public access block, no write permissions.
- `ecs.tf` — CloudWatch log group, cluster, security group, Fargate task definition, service, desired_count 0.
- `iam.tf` — Execution role (ECR pull + CloudWatch logs), task role (S3 model read-only), no broad managed policies, no wildcard Action.
- `outputs.tf` — 12 outputs for downstream consumption.
- `README.md` — Purpose, resource summary, human-only apply rule, validation commands.

### IAM least-privilege summary
- ECR auth wildcard exception: `ecr:GetAuthorizationToken` with AWS-required comment.
- ECR repo-scoped actions: `BatchGetImage`, `GetDownloadUrlForLayer`, `BatchCheckLayerAvailability`.
- S3 object read-only scope: `s3:GetObject` with prefix restriction.
- Logs stream scope: `logs:CreateLogStream`, `logs:PutLogEvents`.
- Forbidden IAM shortcuts: No `s3:PutObject`, no `s3:DeleteObject`, no `AdministratorAccess`, no `AmazonECSTaskExecutionRolePolicy`, no wildcard Action.
- No s3 write/delete: enforced.
- No wildcard Action: enforced.

### Human-only cloud mutation boundary
Agents write Terraform only. Agents may run `fmt -check`, `init -backend=false` (temp copy), `validate`. Agents must NOT run `apply`, `destroy`, real-backend init, or use AWS credentials.

### Validation summary
30 checks: git state, file existence (8), terraform fmt, terraform validate, IAM content (7), S3 content (2), ECR/ECS content (4), security/compliance (5), forbidden files (1), .DS_Store.

### Follow-up sequencing
PR 0022B (ECR publish CI) → PR 0020 (cloud config sourcing) → human configure backend/apply → future HTTP server wiring.

## Exact human commit instructions for planning artifacts

This PLAN.md is a planning artifact only. No implementation files have been created or modified.

1. Planner writes this file: `.project-memory/pr/0022a-terraform-skeleton/PLAN.md`
2. Human runs: `git add .project-memory/pr/0022a-terraform-skeleton/PLAN.md`
3. Human runs: `git commit -m "PR 0022A — Plan Terraform skeleton for AWS runtime foundation"`
4. Human pushes the branch for plan-review.
5. After plan-review approves, the coder implements the eight allowed files.

## Files read

- `docs/adr/0006-multi-target-deployment-and-iac.md`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `ROADMAP.md`
- `docs/architecture.md`
- `docs/api_contract.md`
- `Dockerfile`
- `.github/workflows/quality.yml`
- `requirements.txt`
- `.project-memory/project_contract.yml`
- `AGENTS.md`

## Files written

- `.project-memory/pr/0022a-terraform-skeleton/PLAN.md` (this file)

## Files intentionally ignored

- All source files (`src/**`)
- All test files (`tests/**`)
- All config, example files
- All infrastructure files outside the Terraform directory (CI, Docker, pyproject)
- All docs files not in the required-reads set
- Any H5/HDF5 or model artifact files

## Boundary confirmations

- confirm: precondition gates G-INFRA-1/G-API-2 verified DECIDED: yes
- confirm: ADR-0006 and ADR-0007 present: yes
- confirm: this PR plans only the 8 infra/terraform files: yes
- confirm: no CI/GitHub Actions content planned; delegated to PR 0022B: yes
- confirm: no terraform apply/destroy planned for agents: yes
- confirm: no real-backend init planned for agents: yes
- confirm: no real AWS credentials planned: yes
- confirm: IAM wildcard Resource exception limited to ecr:GetAuthorizationToken: yes
- confirm: no wildcard Action planned: yes
- confirm: no broad AWS managed policy planned: yes
- confirm: S3 versioning planned: yes
- confirm: S3 public access block planned: yes
- confirm: desired_count default 0 planned: yes
- confirm: ECS described as scaffolding, not functioning production API: yes
- confirm: implementation phase assigned to Agent: coder / Mode: implementation: yes
- confirm: no git mutation commands run: yes
