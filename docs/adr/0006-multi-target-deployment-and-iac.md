# ADR-0006: Multi-Target Deployment and Infrastructure-as-Code

**Status**: Accepted

## Context (cited from evidence)

- GHCR publish exists and works (PR 0007): `ghcr.io/eos-dx/bremen` with `latest` and `sha` tags on push to main.
- No AWS ECR target exists.
- No Infrastructure-as-Code exists.
- No target referred to as "APRANA" exists or is configured. **IMPORTANT: APRANA IS UNVERIFIED** — confirm exact platform name, EOL timeline, and access model before any implementation PR touches it.

## Decisions

### AWS ECR

Add as a second registry target, with the same non-negotiable CI safety rules as GHCR:

- Human-provided secrets only; no baked credentials.
- No destructive infra changes without human review.
- Publish gated to merge-to-main/release tag.

### APRANA (UNVERIFIED)

**EXPLICITLY UNVERIFIED** — Before any implementation PR touches APRANA, a human must confirm:

- The exact platform name.
- Its EOL and migration timeline.
- The access / authentication model.

This ADR records intent only and does not invent technical specifics. APRANA is explicitly deprioritized relative to AWS/ECR. **(IMPORTANT: APRANA IS UNVERIFIED — the name/URL/access model used here is a placeholder. Do not implement against it without human confirmation.)**

### Infrastructure-as-Code

Required for whichever AWS resources ADR-0003 and ADR-0006 imply. Not written here.

## OPEN Decision Gate

| Gate ID | Question | Trigger type | Recommended default | Status |
|---------|----------|-------------|-------------------|--------|
| G-INFRA-1 | Terraform vs. AWS CDK vs. CloudFormation | Date-bound (before PR 0022) | Terraform (revisable) | OPEN |
