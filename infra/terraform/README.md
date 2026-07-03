# Bremen Terraform Skeleton

**Purpose**: This is a Terraform skeleton defining Bremen's AWS runtime
infrastructure. It is **not** production-ready and must not be applied
without human review and configuration.

## Resource Summary

| Resource | Purpose |
|----------|---------|
| **ECR repository** | Docker image registry for the Bremen service container. |
| **S3 bucket** | Versioned, encrypted model package store. Public access blocked. |
| **ECS cluster** | Fargate cluster for the Bremen service. |
| **ECS task definition** | Fargate task with IAM roles, environment variables. |
| **ECS service** | Fargate service placed in private subnets. |
| **CloudWatch log group** | Application log delivery. |
| **IAM roles** (execution + task) | Least-privilege: ECR pull, CloudWatch logs, S3 model read. |

## Agent Invariant

**Agents must not run `terraform apply` or `terraform destroy`.**

Agents may run:
- `terraform fmt -check` — format check
- `terraform init -backend=false` — against a **temporary copy** outside the repository
- `terraform validate` — only after backend-disabled init (in the temp copy)

## Human-Only Steps Before Any `apply`

1. **Choose / configure a real AWS account** — verify account ID, region, and
   service limits.
2. **Configure credentials** — locally via AWS CLI profile, environment
   variables, or a deliberate CI OIDC role.
3. **Configure remote state backend** — choose S3 + DynamoDB or a Terraform
   Cloud workspace. Add a `backend` block to `main.tf`.
4. **Review IAM policy line by line** — verify every Action and Resource is
   appropriate.
5. **Review expected cost** — ECS Fargate, S3, CloudWatch Logs.
6. **Set real VPC/subnet variables** — `vpc_id` and `private_subnet_ids` must
   refer to an existing VPC.
7. **Decide `desired_count > 0` intentionally** — the default is 0 (no active
   tasks). A human must explicitly raise this for deployment.

## Validation Commands

```bash
# Format check
terraform fmt -check -recursive .

# Backend-disabled init in a temporary copy
tmpdir="$(mktemp -d)"
cp -R . "$tmpdir/terraform"
terraform -chdir="$tmpdir/terraform" init -backend=false
terraform -chdir="$tmpdir/terraform" validate
rm -rf "$tmpdir"
```

## Production Readiness

This skeleton is **not** production-ready. It is infrastructure scaffolding
for the Platform Readiness Track. Real HTTP service wiring, load balancing,
autoscaling, CI/CD pipeline, disaster recovery, and security hardening are
future work.
