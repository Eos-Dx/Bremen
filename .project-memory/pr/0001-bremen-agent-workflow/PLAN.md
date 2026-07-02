# PR 0001 — Adapt Agent Workflow to Bremen Plan

Author: planner
Branch: 0001-bremen-agent-workflow

Goal
----
Create a precise, unambiguous PLAN.md to adapt the copied agent workflow/configuration from the previous project into Bremen. This PR's sole artifact is this PLAN.md. No code, tests, or review artifacts are to be written in this PR.

Scope and constraints
---------------------
- Allowed write path (this PR):
  - .project-memory/pr/0001-bremen-agent-workflow/PLAN.md (this file)
- Files explicitly permitted for later changes by roles (listed below) but NOT in this PR.
- Forbidden in this PR: any edits to src/, tests/, Docker files, CI pipelines, API files, model packages, H5 logic, or any other runtime implementation.
- Agents must not run git mutation commands. Human reviewers/committers will perform any commits after plan approval.

Required reads (already consulted by planner)
--------------------------------------------
- agents/universal_agent_workflow_anti_drift_manual.md
- agents/01_platform_architect.md
- agents/02_repository_scaffolder.md
- agents/03_runner_patch_engineer.md
- agents/04_qa_contracts_reviewer.md
- agents/architect.yml
- agents/plan-review.yml
- agents/coder.yml
- agents/precommit-review.yml

Note: These files are repository-visible source-material under agents/ and are REQUIRED for plan-review verification. If any are absent the plan-review must block (see Stop conditions).

Principles and preservation guarantees
--------------------------------------
This PLAN.md enforces the Bremen identity and non-negotiable safety invariants. The following guarantees are preserved by process and must be included in the Plan Drift Gate and later PR checks:
- planner writes only PLAN.md in this PR.
- plan-review role writes only plan-review.yml (in the plan-review step).
- coder changes only files explicitly approved by PLAN.md.
- precommit-review writes only precommit-review.yml (in the precommit step).
- Human actors (not agents) perform git add / commit / push.
- No implementation work (coding, tests, CI, Docker, API, H5, preprocessing, model inference) before approved plan-review completion.

Decisions made in this plan
---------------------------
Planned files to add or update (exact paths)
- .project-memory/pr/0001-bremen-agent-workflow/PLAN.md  (this file, planner-only)
- .project-memory/project_contract.yml  (created/updated in future coder PRs only; referenced here)
- agents/plan-review.yml                (adaptation to Bremen; written by plan-review role)
- agents/coder.yml                      (adaptation to Bremen; written by coder role)
- agents/precommit-review.yml           (adaptation to Bremen; written by precommit-review role)
- .project-memory/agents/archived_workflow_mappings.yml (optional, coder role)

Exact project-memory structure (paths and purpose)
- .project-memory/
  - pr/0001-bremen-agent-workflow/
    - PLAN.md           # this file (planner)
    - evidence/         # (future) runtime-captured evidence collected by human reviewers
  - project_contract.yml  # canonical project contract for Bremen (created/maintained by coder + reviewers)
  - agents/              # store adapted agent configs and mapping docs (managed by coder and reviewers)

Exact agent config files to adapt (names and exact paths)
- agents/plan-review.yml        # must be adapted to reference PLAN.md and Plan Drift Gate rules (plan-review role writes only this file during plan review step)
- agents/coder.yml              # must be adapted to limit coder actions to approved files and rules
- agents/precommit-review.yml   # must implement Plan Drift Gate checks for content/paths and write only the precommit-review.yml file

Source reference materials (read-only source material required for plan verification)
- agents/universal_agent_workflow_anti_drift_manual.md
- agents/01_platform_architect.md
- agents/02_repository_scaffolder.md
- agents/03_runner_patch_engineer.md
- agents/04_qa_contracts_reviewer.md
- agents/architect.yml
- agents/plan-review.yml
- agents/coder.yml
- agents/precommit-review.yml

Important: agents/* are repository-visible source-material. They are NOT to be edited as part of this planner PR. If the files exist they should be explicitly included as source reference materials in plan-review. If they do not exist, plan-review must block (see Stop conditions).

Exact docs to create (paths)
- docs/agent_workflow.md  (coder role — deferred to later PR after plan approval)
- docs/bremen_safety_rules.md (coder role — deferred)
- docs/plan_drift_gate.md (precommit-review role — deferred)

Old-project-name removal rules
-------------------------------
- Do not perform source rename from Aramis -> Bremen in this PR.
- Document all occurrences of legacy names in .project-memory/report (coder responsibility in subsequent PR).
- The first coder PR that touches source code must include an explicit mapping of legacy names to retained identifiers or planned rename steps. This PR must be reviewed under Plan Drift Gate.
- Any automated rename tools are forbidden until explicit approval by plan-review and precommit-review.

Bremen-specific safety rules (to be encoded in agent configs and project_contract.yml)
------------------------------------------------------------------------------------
- Bremen is a controlled ML decision-support product, not just a joblib file.
- Bremen must never be described or marketed as a standalone diagnostic system.
- No prediction made unless required H5 metadata is present and validated.
- Target/control scan roles must be explicit and validated against H5 metadata before any downstream action.
- Target and control scans must belong to the same patient/study and be opposite anatomical sides.
- Feature schema must be explicit and must match the model package schema before inference.
- Joblib model packages are controlled artifacts; joblib must be loaded only from checksum-verified model packages.
- Every prediction result MUST include: prediction_id, model_version, model_checksum, feature_schema_version, threshold version/value, qc_status, qc_flags.
- Matador remains the system of record for measurements and prediction results.
- Platform API MUST NOT depend on local machine paths; all platform paths must be abstracted in project_contract.yml.
- Docker/CI/API/H5/model implementation work is deferred to later PRs and is out-of-scope for PR 0001.

Allowed implementation files (files coder may change after plan approval)
-------------------------------------------------------------------------
- Files explicitly listed in a future coder PR that references and follows this PLAN.md. Examples (not to be changed in this PR):
  - agents/plan-review.yml
  - agents/coder.yml
  - agents/precommit-review.yml
  - .project-memory/project_contract.yml
  - docs/*.md referenced above

Source-material vs adapted agent files (explicit distinction)
-----------------------------------------------------------
- Source-material (read-only for planner & plan-review verification): agents/*
  - These are the original governance/manual/agent templates copied from prior projects for review and reference and exist at top-level agents/.
  - They may be committed into the repository and must be present for plan-review verification.
- Adapted Bremen agent files (to be created/modified after plan approval): agents/*.yml (same directory)
  - These are the Bremen-specific agent configurations (plan-review.yml, coder.yml, precommit-review.yml) and must NOT be created or modified in this planner PR.

Forbidden files (must not be changed in this PR)
-------------------------------------------------
- Any file under src/
- Any file under tests/
- Dockerfiles, docker-compose files, and scripts under ci/ or .github/workflows/
- API implementation files (e.g. docs/api_contract.md, src/api, fastapi apps)
- H5 reader, preprocessing, model, or joblib-related files
- Any file that performs runtime inference or training

Validation commands (to be run by precommit-review agent or human precommit reviewer)
------------------------------------------------------------------------------------
The precommit-review step must execute these validations before allowing code commits. They should be implemented in agents/precommit-review.yml and enforced by the human precommit reviewer.
1) Source-material existence check (planner/plan-review validation):
   - test -f agents/universal_agent_workflow_anti_drift_manual.md || exit 1
   - test -f agents/01_platform_architect.md || exit 1
   - test -f agents/02_repository_scaffolder.md || exit 1
   - test -f agents/03_runner_patch_engineer.md || exit 1
   - test -f agents/04_qa_contracts_reviewer.md || exit 1
   - test -f agents/architect.yml || exit 1
   - test -f agents/plan-review.yml || exit 1
   - test -f agents/coder.yml || exit 1
   - test -f agents/precommit-review.yml || exit 1
   - If any of the above tests fail, plan-review must BLOCK the plan and require the planner to supply or correct the source-material paths.
2) Files written check (Plan adherence):
   - git diff --name-only --staged | sort
     - Expected: only files explicitly allowed by the approved PLAN.md and any files referenced in plan-review.yml updates.
3) No forbidden path changes:
   - git diff --name-only --staged | grep -E "^(src/|tests/|Dockerfile|ci/|\.github/|docs/api_contract.md)" && exit 1 || exit 0
4) Planner/Role artifact checks:
   - Ensure planner committed only PLAN.md in this PR.
   - Ensure plan-review writes only plan-review.yml (only when plan-review role runs).
   - Ensure coder changes match the approved file list in the PLAN.md.
5) Anti-drift content checks (content validation):
   - Search for legacy project name uses in changed files: grep -R --line-number "Ariadne|Aramis" $(git diff --name-only --staged) || true
   - If legacy names are changed in source files, block — a rename may only be planned and executed in a dedicated PR following the approved plan.
6) Bremen safety invariants presence:
   - Any PR that will later introduce inference must include checks for: H5 metadata validation, target/control role validation, joblib checksum verification, model metadata outputs (prediction_id, model_version, etc.). Precommit must verify presence of TODOs or placeholders if implementation is deferred.
7) Plan Drift Gate enforcement (see below).

Stop conditions (when to halt and require re-planning)
-----------------------------------------------------
- Any attempt to modify forbidden files in this PR.
- Discovery of missing required reads or missing agent config files referenced in this PLAN.md.
- Any agent or automation performing git add/commit/push.
- Discovery that planner wrote files other than .project-memory/pr/0001-bremen-agent-workflow/PLAN.md.
- Any deviation from the exact planned project-memory structure above.
- If required agents/* files are absent or incomplete, plan-review must block the plan until the planner supplies the exact files at agents/ or updates the PLAN.md to reference correct, present paths.

Plan Drift Gate requirements for precommit-review
------------------------------------------------
Precommit-review must enforce a Plan Drift Gate before allowing any commit that implements the plan. The gate requires:
1) Plan hash match: the committed PLAN.md (at .project-memory/pr/<pr-id>/PLAN.md) must match the approved plan-review artifact. The plan-review role should sign or include a hash of the approved PLAN.md in agents/plan-review.yml.
2) File list freeze: the list of files modified by the coder must be explicitly enumerated in the approved PLAN.md or plan-review.yml. Any deviation blocks the commit.
3) Safety-invariant checklist: coder PRs that will introduce runtime behavior must include passing unit/integration tests or TODOs referencing the required safety checks (H5 validation, target/control checks, joblib checksum, feature schema matching, model metadata output). Precommit-review verifies presence of these tests or TODOs.
4) Legacy name policy: no silent rename of legacy project names; any rename must be in a separate, explicitly approved PR.
5) Evidence capture: precommit must ensure that any claims by agents are accompanied by runtime-captured or explicitly observed evidence stored under .project-memory/pr/<pr-id>/evidence/ before implementation merges.

Deferred capabilities (explicitly out of scope for PR 0001)
---------------------------------------------------------
- Dockerfile or containerisation changes.
- CI/CD pipeline implementation or edits to .github/workflows.
- FastAPI or any runtime API implementation.
- HDF5 reader implementation and H5 metadata parsing.
- Preprocessing, feature extraction code.
- Joblib model loading or inference logic.
- Any training/model-build pipelines.
- Any automated rename of source package names.

Plan execution roles and exact write permissions
-----------------------------------------------
- planner (this PR): writes only .project-memory/pr/0001-bremen-agent-workflow/PLAN.md
- plan-review: writes only agents/plan-review.yml (during plan-review step), and must include plan hash/signature referencing this PLAN.md
- coder: after plan approval, coder may modify only files listed in approved PLAN.md. Coder must not change other files. Coder commits must be human-made.
- precommit-review: writes only agents/precommit-review.yml (to implement Plan Drift Gate), and performs the gate validations before merge.

Manifest of non-goals (explicit)
--------------------------------
- Do not plan or implement source package rename from Aramis -> Bremen in this PR.
- Do not plan or implement CI, Docker, API, H5 reader, preprocessing, or joblib inference in this PR.

Plan verification checklist (what the plan-review role must verify)
------------------------------------------------------------------
- Planner constraint: confirm planner wrote only .project-memory/pr/0001-bremen-agent-workflow/PLAN.md and nothing else.
- The PLAN.md contains an explicit list of allowed future files and forbidden files.
- The Plan Drift Gate requirements are present and enforceable by precommit-review.
- Bremen-specific safety rules are listed and will be required in future PRs that implement runtime.
- Project-memory structure is clearly specified.
- No code, tests, Docker, CI, or API edits are planned in this PR.
- Confirm presence of required source-material files under agents/ (see Required reads). If missing, block and require planner correction.

Decisions summary
-----------------
- planned files:
  - .project-memory/pr/0001-bremen-agent-workflow/PLAN.md (written by planner in this PR)
  - agents/plan-review.yml (to be written by plan-review role)
  - agents/coder.yml (to be written by coder role)
  - agents/precommit-review.yml (to be written by precommit-review role)
  - .project-memory/project_contract.yml (to be created/updated by coder in a later PR)
- forbidden files:
  - any under src/, tests/, Docker, CI, API, H5, preprocessing, model-related paths
- Bremen-specific agent rules:
  - see "Bremen-specific safety rules" section above
- validation commands:
  - see "Validation commands" section above
- Plan Drift Gate requirements:
  - see "Plan Drift Gate requirements" section above
- deferred capabilities:
  - see "Deferred capabilities" section above
- blockers:
  - None for writing this PLAN.md by planner. Implementation is blocked until plan-review approves.
- warnings:
  - Any accidental edits to forbidden paths will block the PR and trigger re-planning.

Files read
----------
- agents/universal_agent_workflow_anti_drift_manual.md (expected)
- agents/01_platform_architect.md (expected)
- agents/02_repository_scaffolder.md (expected)
- agents/03_runner_patch_engineer.md (expected)
- agents/04_qa_contracts_reviewer.md (expected)
- agents/architect.yml (expected)
- agents/plan-review.yml (expected)
- agents/coder.yml (expected)
- agents/precommit-review.yml (expected)

If any of the above agents/* files are missing, plan-review must block and request the planner to supply the missing files or to correct the referenced paths in this PLAN.md.

Files written
-------------
- .project-memory/pr/0001-bremen-agent-workflow/PLAN.md

Files intentionally ignored (not to be touched in this PR)
---------------------------------------------------------
- All source code under src/
- tests/
- Docker and CI files
- Any runtime implementation files

Boundary confirmations
----------------------
- confirm: only PLAN.md written: yes
- confirm: no code written: yes
- confirm: no tests written: yes
- confirm: no review artifact written: yes
- confirm: no Aramis-to-Bremen source rename performed: yes
- confirm: no Docker/CI/API/H5/model implementation planned for this PR: yes
- confirm: Plan Drift Gate required: yes
- confirm: no git mutation commands run: yes

Final output
------------
PLAN written: yes

