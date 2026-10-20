# PR0164 — Inference Release Contract Rebaseline

Status: Proposed — pending independent plan review.

## Goal
Align the existing Bremen inference roadmap with the agreed Model Release, plugin and isolated Worker architecture. Documentation only.

## Current State
Bremen uses AWS App Runner and the existing S3 catalog/manifests.
ROADMAP.md defines IR-01 through IR-07.
The current proposed worker protocol uses stdin/stdout JSONL instead of the agreed file-based V1 protocol.

## Required Changes
1. Preserve App Runner and existing S3 model registry.
2. Define immutable Model Release: manifest, model artifacts, plugin wheel, pinned dependencies, provenance and golden tests.
3. Platform owns Harness, common Worker, protocol and supervision.
4. ML team owns plugin, preprocessing, inference and scientific postprocessing.
5. V1 protocol: request.json + input.h5 -> result.json.
6. stdout/stderr carry diagnostics only; optional structured events must preserve existing event semantics.
7. Define typed errors: INPUT_INVALID, QC_FAILED, MODEL_NOT_READY, INFERENCE_FAILED, TIMEOUT, RESOURCE_EXHAUSTED, PROTOCOL_ERROR.
8. Separate Model Release CI/CD from Bremen application CI/CD.
9. Distinguish publication, READY and controlled activation.
10. Align IR-01 through IR-07 without changing their dependency order.
11. Add future-model onboarding without Bremen rebuild as a final architecture gate.
12. Document V2 persistent workers and V3 OCI as future, non-binding options.

## Allowed Files
ROADMAP.md
docs/adr/0019-independent-inference-releases-app-runner.md
docs/inference-releases/architecture-and-contract.md
docs/inference-releases/implementation-plan.md
docs/inference-releases/operations.md
docs/inference-releases/parity-and-rollout.md
.project-memory/pr/ir-01/PLAN.md
.project-memory/pr/ir-02/PLAN.md
.project-memory/pr/ir-03/PLAN.md
.project-memory/pr/ir-04/PLAN.md
.project-memory/pr/ir-05/PLAN.md
.project-memory/pr/ir-06/PLAN.md
.project-memory/pr/ir-07/PLAN.md
.project-memory/pr/0164-inference-release-contract-rebaseline/IMPLEMENTATION_REPORT.md

## Non-goals
No source, tests, Docker, CI workflows, dependencies or infrastructure changes.
No scientific changes, S3 publication, release activation or deployment.
No second registry, ECS migration or mandatory MLflow serving.

## Contracts to Preserve
Model Runtime Contract v1.
Model Package Standard v1.
Standard Model Result Contract v1.
Existing model IDs, scientific behavior, public API, reports and job lifecycle.
No automatic activation or silent fallback.

## Validation
python -m compileall -q src tests
pytest -q
git diff --check
Verify all tracked, staged and untracked changes.
Check privacy, security and documentation consistency.

## Acceptance Criteria
1. All updated documents describe the same V1 architecture.
2. S3 remains the registry authority.
3. File protocol replaces stdout JSONL as the normative result channel.
4. Worker and plugin ownership is explicit.
5. IR-01 through IR-07 remain coherent.
6. No files outside approved scope are modified by Coder.
7. Coder writes IMPLEMENTATION_REPORT.md with exact evidence.
8. Independent precommit review is required before commit.

## Risks
Exact five-model inventory and App Runner resource feasibility remain IR-01 gates.
Executable schemas and implementation remain IR-02 onward.
No clinical or production readiness is claimed.
