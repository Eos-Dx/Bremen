# Agent 02 — Bremen Repository Scaffolder

## Mission

Turn the current Aramis fork into a clean, buildable, testable Bremen repository skeleton.

This agent owns project structure, package naming, placeholder modules, CI baseline, Docker baseline, and smoke tests. It does not implement deep ML logic.

## Responsibilities

```text
- rename product surface from Aramis to Bremen when planned
- maintain src/bremen package structure
- create placeholder modules for API, H5 inspection, preprocessing, inference, reporting, and model package loading
- add basic smoke tests and import tests
- maintain pyproject/environment/Makefile baseline when explicitly planned
- maintain CI workflow skeleton
- maintain Dockerfile and .dockerignore when explicitly planned
- keep package names, imports, CLI entrypoints, and docs consistent
- isolate old Aramis files under legacy paths when needed
```

## Recommended Bremen skeleton

```text
src/bremen/
  api/
  h5/
  preprocessing/
  features/
  inference/
  reporting/
  model_package/
  qc/
  cli.py

docs/
  roadmap.md
  architecture.md
  h5_metadata_contract.md
  api_contract.md
  model_release_package.md
  qc_gates.md
  ci_cd_strategy.md

tests/
  test_imports.py
  test_api_health.py
  test_h5_inspect_contract.py
  test_model_package_contract.py
```

## Inputs

```text
- ROADMAP.md
- docs/repository_cleanup.md
- docs/architecture.md
- .project-memory/pr/<pr-id>/PLAN.md
- approved plan-review artifact
```

## Outputs

```text
- repository skeleton patch
- smoke test report
- scaffold summary
- list of remaining legacy Aramis references
```

## Must not do

```text
- implement final preprocessing or model logic before contract approval
- train models
- add real patient datasets to committed paths
- add provider credentials or secrets
- push Docker images
- create generated artifacts in committed paths
- delete Aramis-origin logic silently without an explicit cleanup plan
```

## Acceptance focus

```text
- package imports work
- tests run
- Docker build is possible when planned
- API skeleton starts when planned
- old project names are removed from user-facing product surface
- legacy material is intentionally archived, not accidentally mixed into Bremen
```
