# ADR-0008: Runtime Target Pivot — App Runner Proving Target

**Status**: Accepted

## Context

- ECS Fargate remains the long-term primary production target (G-API-2, DECIDED in PR 0012).
- AWS App Runner provides faster operational launch (source-to-code or image-based deployment, auto-scaling, built-in load balancer, no VPC/subnet management) suitable for smoke testing, integration validation, and proving the runtime model binding lifecycle end-to-end.
- "APRANA" was an unverified placeholder name from earlier ADR drafts. **APRANA is retired.** It is not a synonym for App Runner. It must not be used as a target, alias, shorthand, PR, gate, or option.
- The existing ECS Terraform skeleton (`infra/terraform/ecs.tf`) is retained but not currently prioritized.

## Decision

- **AWS App Runner is the near-term proving/testing target.**
- **ECS Fargate remains the long-term primary production target.**
- This is an operational addition, not a replacement. ECS is not abandoned.
- App Runner uses ECR as the image source. The stable mutable tag `app-runner` (added in a separate CI/CD PR) will trigger auto-deployment.
- The runtime `/health` endpoint serves as the App Runner health check. The future readiness endpoint (startup model load PR) serves as the readiness gate.
- The runtime image must not contain model artifacts. Model binding occurs at deployment/startup time, not request time.

## Consequences

- A CI/CD PR is required to add the `app-runner` stable mutable tag to the ECR publish workflow (PR 0031).
- A model fetch/staging PR is required to download model packages from S3 to a local staging directory (PR 0032).
- A startup readiness PR is required to wire model fetch + validate + load into server startup (PR 0033).
- An App Runner service config/infra PR is required to define the App Runner service resource (PR 0034).
- The existing ECS Terraform skeleton (`infra/terraform/`) is retained for later use without modification.
- G-API-2 is amended to: **"ECS Fargate (primary/long-term), App Runner (near-term proving)"** — recorded in the ROADMAP.md Decision Gate Register.
