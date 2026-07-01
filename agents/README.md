# Bremen Agents v1

This folder contains Bremen-specific replacements for copied Aramis/Ariadne agents.

## Recommended active agent set

1. `configs/architect.yml` — product/architecture/ADR/roadmap gate.
2. `configs/plan-review.yml` — PLAN.md review gate.
3. `configs/coder.yml` — scoped implementation agent.
4. `configs/precommit-review.yml` — final evidence and contract gate.

## Role docs

- `roles/01_bremen_product_architect.md`
- `roles/02_bremen_repository_scaffolder.md`
- `roles/03_bremen_coder.md`
- `roles/04_bremen_precommit_reviewer.md`

## Bremen-specific controlled contracts

- H5 metadata contract
- target/control contract
- preprocessing output contract
- feature schema contract
- joblib model package contract
- prediction API contract
- QC_FAIL contract
- CI/CD and Docker/registry contract
