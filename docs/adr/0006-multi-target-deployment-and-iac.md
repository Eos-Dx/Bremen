# ADR-0006: Multi-Target Deployment and Infrastructure-as-Code

**Status**: Accepted (partially superseded by ADR-0008 for runtime target)

## Context (cited from evidence)

- GHCR publish exists and works (PR 0007): `ghcr.io/eos-dx/bremen` with `latest` and `sha` tags on push to main.
- AWS ECR publish exists and works (PR 0022B/0022C).
- Infrastructure-as-Code skeleton exists but has not been applied (`infra/terraform/`).
- **APRANA is retired.** The unverified placeholder name from earlier ADR drafts must not be used as a target, alias, shorthand, PR, gate, or option. See ADR-0008 for the App Runner proving target decision.

## Decisions

### AWS ECR

Add as a second registry target, with the same non-negotiable CI safety rules as GHCR:

- Human-provided secrets only; no baked credentials.
- No destructive infra changes without human review.
- Publish gated to merge-to-main/release tag.

### AWS App Runner (near-term proving target)

See ADR-0008 for the full decision. App Runner is the near-term proving/testing target. ECS Fargate remains the long-term primary production target.

### Infrastructure-as-Code

Required for whichever AWS resources ADR-0003, ADR-0006, and ADR-0008 imply. Not written here.

## OPEN Decision Gate

| Gate ID | Question | Trigger type | Recommended default | Status |
|---------|----------|-------------|-------------------|--------|
| G-INFRA-1 | Terraform vs. AWS CDK vs. CloudFormation | Date-bound (before PR 0022) | Terraform (revisable) | DECIDED (Terraform) |
