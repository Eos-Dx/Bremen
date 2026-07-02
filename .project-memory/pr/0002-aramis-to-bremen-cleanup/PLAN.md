# PR 0002 — Aramis to Bremen Repository Cleanup Plan

Author: planner
Branch: 0002-aramis-to-bremen-cleanup

## Goal

Create a precise, bounded PLAN.md for the first Aramis-to-Bremen repository cleanup. This PR makes the repository identity clearly "Bremen" on public/project surfaces while avoiding changes to runtime code, ML logic, preprocessing, API, Docker, CI, H5 reader, joblib inference, or any test/example/config file that would require a source package rename.

This PR's sole artifact is this PLAN.md. No code, tests, or review artifacts are to be written in this PR.

## Scope and constraints

- **Allowed write path (this PR):**
  - `.project-memory/pr/0002-aramis-to-bremen-cleanup/PLAN.md` (this file)

- **Files coder may change after plan approval (allowed files):**
  - `README.md` — rewrite project identity to Bremen; retain Aramis reference as source material
  - `AGENTS.md` — convert from mixed Aramis/Bremen Codex rules to Bremen-focused rules; preserve shared pipeline discipline and regulatory posture; reference Aramis only as historical context
  - `pyproject.toml` — update `description` field only (change from "Aramis cancer-classification product draft." to a Bremen-appropriate description); **do not change** `name`, `[project.scripts]`, or any other field
  - `docs/repository_cleanup.md` — NEW file documenting repository cleanup status, Aramis legacy classification, and deferred items

- **Forbidden files (must not be changed in this PR):**
  - `src/aramis/*` — any file under the source package
  - `tests/*` — any test file, test data, or test fixture
  - `config/*` — any config, preprocessing YAML, versioning JSON, or audit file
  - `examples/*` — any notebook, script, or shell file
  - `packaging/*` — any eosproduct bundle file
  - `docs/*` except the single new `docs/repository_cleanup.md`
  - `agents/*` — all agent configs and role definitions (adapted in PR 0001)
  - `.project-memory/*` — all project-memory artifacts
  - `environment.yml` — symlink to `../XRD-preprocessing/environment.yml` (external dependency)
  - `requirements.txt` — dependency file referencing external repos
  - `.gitignore`, `.github/*`, Docker files, CI files — no infrastructure changes
  - Any file that performs runtime inference, training, H5 reading, preprocessing, or API serving

## Principles and preservation guarantees

- planner writes only PLAN.md in this PR.
- plan-review role writes only plan-review.yml (in the plan-review step).
- coder changes only files explicitly listed in "Files coder may change" above.
- precommit-review writes only precommit-review.yml (in the precommit step).
- Human actors (not agents) perform git add / commit / push.
- No automated search-and-replace of project names across the repository.
- No src/ package rename, import rename, or entrypoint rename in this PR.
- No runtime behavior changes of any kind.

## Aramis reference classification

All observable Aramis references in the repository are classified below.

### Active public identity reference — change in this PR

| File | Reference | What to do |
|------|-----------|------------|
| `README.md` | `# Aramis` (H1), entire document describes "Aramis" as live product | Rewrite to Bremen identity; preserve Aramis as source-material context |
| `AGENTS.md` | `# Codex Rules For Aramis Product Development` (title), "Aramis:" block with full product context, mix of Aramis/Bremen instructions | Convert title and primary context to Bremen; retain Aramis as historical note |
| `pyproject.toml` | `description = "Aramis cancer-classification product draft."` | Update to Bremen-appropriate description |

### Inherited code/package path — defer (do not change in this PR)

| File | Reference | Rationale |
|------|-----------|-----------|
| `src/aramis/__init__.py` | Package docstring `"""Aramis product draft package."""`, all exports | Rename would break imports across tests, examples, configs; deferred to future refactor PR |
| `src/aramis/__main__.py` | `prog="aramis"`, `aramis` module references | Same — entrypoint change requires coordinated rename |
| `src/aramis/pipelines.py` | `AramisOneToManyPreprocessingPipeline`, `AramisOneToOnePreprocessingPipeline` | Class names inherited; rename deferred |
| `src/aramis/mlflow_tracking.py` | Internal Aramis references | Rename deferred |
| `src/aramis/modeling.py` | Internal Aramis references | Rename deferred |
| `pyproject.toml` | `name = "aramis"`, `[project.scripts] aramis = "aramis.__main__:main"`, `packages = ["src/aramis"]` | Package name change would break all imports; deferred |
| All `<something>.py` files | `import aramis` or `from aramis import ...` | Deferred until source package rename |

### Historical/source-material reference — may remain with clear context

| File | Reference | Status |
|------|-----------|--------|
| `config/README.md` | `# Aramis Human-1 Product Metadata`, "Aramis" throughout | Historical config documentation for the original product dataset |
| `config/aramis_preprocessing_v0_1_config.json` | `"product": "Aramis"`, provenance paths | Audit artifact from Aramis preprocessing pipeline; valid as source material |
| `config/aramis_product_versioning.json` | `"product": "Aramis"` | Versioning metadata for Human-1 dataset; source material |
| `config/human1_diagnoses_metadata_h5_audit.json` | `"product": "Aramis"` | H5 audit artifact; source material |
| `config/human1_diagnoses_metadata.json` | Embedded Aramis references | Clinical metadata; source material |
| `config/preprocessing/*.yaml` | `product: Aramis`, `canonical_location: Aramis/...` | Preprocessing configs referencing the original Aramis product |
| `docs/product_development_rules.md` | "Aramis" and "Bremen" product sections | Shared development rules; Bremen content already present |
| `docs/data_preprocessing.md` | Aramis references | Preprocessing documentation for inherited pipeline |
| `docs/machine_learning_concept.md` | Aramis references | ML concept doc for inherited pipeline |
| `docs/mlflow.md` | Aramis references | MLflow tracking doc for inherited pipeline |
| `docs/agbh_quality_exclusions.md` | Aramis context | Quality exclusion documentation |
| `docs/eosproduct_environment.md` | Aramis context | Environment documentation |
| `packaging/eosproduct_bundle/` | All scripts/docs reference "Aramis" as an external repo | Bundle builds reference the upstream Aramis repository; valid as packaging layer |
| `requirements.txt` | `-e /Users/sad/dev/Aramis[dev]` | Points to external Aramis checkout; not a Bremen runtime dependency |
| `README.md` examples section | `cd /Users/sad/dev/Aramis`, `python -m aramis ...` commands | After README rewrite, these examples will be replaced or contextualized as legacy usage |

### Test fixture/reference — remain (do not change in this PR)

| File | Rationale |
|------|-----------|
| `tests/data/aramis_real_h5_subset_20260128_5_patients.h5` | H5 data file with "aramis" in filename; renaming would break H5 content references |
| `tests/synthetic_aramis_h5.py` | Synthetic fixture helper; rename deferred until src/ rename |
| `tests/test_aramis_preprocessing_one_to_one.py` | Test file; rename deferred |
| `tests/test_aramis_preprocessing_one_to_many.py` | Test file; rename deferred |
| `tests/test_aramis_pipeline_config.py` | Test file; rename deferred |
| `tests/test_mlflow_tracking.py` | Test file (content references Aramis); rename deferred |
| `tests/test_modeling.py` | Test file (content references Aramis); rename deferred |
| `tests/test_real_h5_subset_reader.py` | Test file; rename deferred |
| `examples/aramis_*.py` | All example notebooks; rename deferred |
| `examples/preprocess_*.sh` | All example shell scripts; rename deferred |

### Generated/incidental artifact — ignore

| File | Rationale |
|------|-----------|
| `.DS_Store` | macOS metadata; excluded by `.gitignore` |
| `.idea/` | JetBrains IDE config; excluded by `.gitignore` |

## Old-project-name handling policy

- **Active identity surfaces** (README.md, AGENTS.md, pyproject.toml description): change "Aramis" to "Bremen" as the primary project identity. Always include a sentence that explicitly states "This repository was derived from the Aramis project" to maintain honest provenance.
- **Inherited code/package paths**: do not rename. Mark clearly in `docs/repository_cleanup.md` as deferred.
- **Historical/source-material references**: do not change. May remain with clear contextual framing (e.g., "Aramis product metadata" in config/).
- **Test fixtures**: do not change. No search-and-replace across tests.
- **No automated tools**: do not run `sed`, `awk`, `grep -r --replace`, or any bulk rename tool.

## What counts as public/project surface

Public/project surfaces are files that present the project identity to external readers:
- `README.md` — the first file a visitor reads
- `AGENTS.md` — describes how Codex agents should behave in this repository
- `pyproject.toml` — package metadata visible to `pip`, PyPI, and build tools

Files that are **not** public identity surface (even if they contain "Aramis"):
- `src/aramis/*` — implementation package
- `tests/*` — test files
- `config/*` — operational config data
- `examples/*` — runnable notebooks/scripts
- `packaging/*` — deployment bundle
- `docs/*` — documentation content (except the new repository_cleanup.md)
- `agents/*` — agent configuration (already Bremen-adapted in PR 0001)

## What counts as inherited runtime code that must not be changed yet

Inherited runtime code is any file under `src/aramis/` and any file that references the `aramis` Python package via import or entrypoint. These may not be renamed, refactored, or modified in this PR because:
- The `aramis` package name is wired into tests, examples, configs, and entrypoints
- A coordinated rename would require simultaneous updates across many files
- The rename PR must be separately planned, reviewed, and tested

## Validation commands

Precommit-review must execute these validations before allowing code commits:

### 1) Allowed file changes check
```bash
git diff --name-only --cached | sort
```
Expected output must match exactly:
```
AGENTS.md
README.md
docs/repository_cleanup.md
pyproject.toml
```
No other files may appear.

### 2) Forbidden path check
```bash
git diff --name-only --cached | grep -E "^(src/|tests/|config/|examples/|packaging/|agents/|\.project-memory/|\.github/|environment\.yml|requirements\.txt|\.gitignore)" && exit 1 || echo "OK"
```
Must print "OK". Any match means the commit includes a forbidden path.

### 3) No runtime code changed
```bash
git diff --cached -- src/ tests/ config/ examples/ packaging/ agents/ .project-memory/ 2>/dev/null | head -1
```
Must produce no output (or only an empty diff).

### 4) pyproject.toml limited to description field
```bash
git diff --cached -- pyproject.toml | grep -E "^[+-]" | grep -v "^[+-]{3}" | grep -v "^[+-]description"
```
Must produce no output (no changes outside description field).

### 5) No automated search-and-replace
```bash
git diff --cached -- README.md AGENTS.md | grep -E "^\+.*Aramis" || echo "No new Aramis references added"
```
Acceptable either way — but if new Aramis references appear in changed files, they must be in legitimate source-material context, not accidentally removed from all files.

### 6) AGENTS.md still contains shared pipeline rules
```bash
grep -q "H5SessionSelectorTransformer" AGENTS.md && echo "Pipeline rules preserved" || echo "ERROR: pipeline rules missing"
```
Must print "Pipeline rules preserved".

### 7) README.md mentions Bremen as primary identity
```bash
grep -q "^# Bremen" README.md && echo "Bremen H1 present" || echo "ERROR: Bremen H1 missing"
```
Must print "Bremen H1 present".

### 8) docs/repository_cleanup.md exists and contains legacy classification
```bash
test -f docs/repository_cleanup.md && echo "cleanup doc exists" || echo "ERROR: cleanup doc missing"
grep -q "Aramis" docs/repository_cleanup.md && echo "Aramis classification present" || echo "WARNING: no Aramis classification found"
```

### 9) No `.DS_Store` staged
```bash
git diff --name-only --cached | grep -q "\.DS_Store" && exit 1 || echo "OK"
```
Must print "OK".

### 10) Working tree clean after changes
```bash
git status --short
```
Only the four allowed files should appear as staged. No untracked or modified files outside the allowed set.

## Stop conditions

- Block if the working tree is dirty before coder begins (uncommitted changes to files outside the allowed set).
- Block if any file outside `README.md`, `AGENTS.md`, `pyproject.toml`, or `docs/repository_cleanup.md` appears in `git diff --name-only --cached`.
- Block if `pyproject.toml` changes include anything beyond the `description` field.
- Block if any `src/`, `tests/`, `config/`, `examples/`, `packaging/`, `agents/`, `.project-memory/`, or infrastructure file is modified.
- Block if automated search-and-replace was used instead of targeted edits.
- Block if import or entrypoint paths are modified.
- Block if runtime behavior, ML logic, preprocessing, H5 reading, Docker, CI, API, or inference is changed.
- Block if repository state cannot be validated against the above validation commands.

## Plan Drift Gate requirements

Precommit-review must enforce a Plan Drift Gate before allowing any commit that implements this plan. The gate requires:

1. **File list freeze**: the four allowed files (README.md, AGENTS.md, pyproject.toml, docs/repository_cleanup.md) must match the staged files exactly. Any additional file blocks the commit.

2. **Scope freeze**: no changes to src/, tests/, config/, examples/, packaging/, agents/, .project-memory/, Docker, CI, API, H5, preprocessing, model, or inference code.

3. **Safety-invariant checklist**: this PR does not introduce runtime behavior. The safety invariants (H5 validation, target/control, joblib checksum, feature schema, prediction metadata) remain deferred and are not affected by identity cleanup.

4. **Legacy name policy**: no silent rename. Allowed identity files must acknowledge Aramis as the source material provenance.

5. **Evidence capture**: precommit-review must run the validation commands listed above and capture output evidence under `.project-memory/pr/0002-aramis-to-bremen-cleanup/evidence/` before merge.

## Deferred capabilities (explicitly out of scope for PR 0002)

- Source package rename (`src/aramis/` → `src/bremen/`)
- Import rename across tests, examples, and configs
- Entrypoint rename (`aramis` → `bremen` CLI)
- Class/function rename (`AramisOneToManyPreprocessingPipeline`, etc.)
- Config file rename or content update
- Test file rename or content update
- Example file rename or content update
- Documentation rewrite (beyond the four allowed files)
- Any runtime, ML, preprocessing, H5, Docker, CI, API, or model changes
- Automated search-and-replace of project names
- Cleanup of `packaging/` eosproduct bundle scripts
- Cleanup of `docs/` content beyond new `docs/repository_cleanup.md`

## Plan execution roles and exact write permissions

- **planner (this PR)**: writes only `.project-memory/pr/0002-aramis-to-bremen-cleanup/PLAN.md`
- **plan-review**: writes only `.project-memory/pr/0002-aramis-to-bremen-cleanup/reviews/plan-review.yml` (must include plan hash/signature referencing this PLAN.md)
- **coder**: after plan approval, coder may modify only the four allowed files exactly as described. Coder must not change any other file. Coder commits must be human-made.
- **precommit-review**: writes only `.project-memory/pr/0002-aramis-to-bremen-cleanup/reviews/precommit-review.yml`, runs validation commands, and enforces the Plan Drift Gate before merge.

## Manifest of non-goals (explicit)

- Do not rename `src/aramis/` to `src/bremen/` in this PR.
- Do not change Python imports, entrypoints, or package names.
- Do not modify any file under `src/`, `tests/`, `config/`, `examples/`, or `packaging/`.
- Do not modify any file under `agents/` or `.project-memory/` (these are PR 0001 domain).
- Do not modify `docs/` except for the single new `docs/repository_cleanup.md`.
- Do not modify Docker, CI, `.github/`, or infrastructure files.
- Do not modify H5 reader, preprocessing, model, or inference code.
- Do not run automated search-and-replace tools.

## Plan verification checklist (what the plan-review role must verify)

- Planner constraint: confirm planner wrote only `.project-memory/pr/0002-aramis-to-bremen-cleanup/PLAN.md` and nothing else.
- The PLAN.md contains an explicit list of allowed files (4 files) and forbidden files (all runtime/infrastructure/config/test paths).
- Aramis references are classified into the five required categories (active identity, inherited code, historical, test fixture, incidental).
- The Plan Drift Gate requirements are present and enforceable by precommit-review.
- Validation commands are specific, actionable, and executable in a shell.
- Stop conditions are enumerated and cover the blocking cases.
- No source rename, import rename, or runtime changes are planned in this PR.
- The old-project-name handling policy explicitly forbids silent rename and automated tools.
- The coder's allowed scope is clearly bounded and cannot drift into runtime or infrastructure changes.

## Decisions summary

### Allowed files
- `README.md`
- `AGENTS.md`
- `pyproject.toml` (description field only)
- `docs/repository_cleanup.md` (new file)

### Forbidden files
- `src/aramis/*`, `tests/*`, `config/*`, `examples/*`, `packaging/*`
- `agents/*`, `.project-memory/*`
- `docs/*` except `docs/repository_cleanup.md`
- `environment.yml`, `requirements.txt`, `.gitignore`
- Any Docker, CI, `.github/`, or infrastructure file

### Aramis reference classification
- Active identity: README.md, AGENTS.md, pyproject.toml description
- Inherited code: src/aramis/ (all), pyproject.toml name/entrypoint
- Historical/source-material: config/, docs/, packaging/, requirements.txt, README.md examples section
- Test fixture: tests/, examples/
- Incidental: .DS_Store, .idea/

### Rename/defer strategy
- Active identity → change to Bremen, acknowledge Aramis provenance
- Inherited code → defer to future refactor PR
- Historical → leave unchanged, contextualize as source material
- Test fixtures → leave unchanged
- No automated rename tools

### Validation commands
See "Validation commands" section above (10 command blocks).

### Stop conditions
See "Stop conditions" section above.

### Plan Drift Gate requirements
See "Plan Drift Gate requirements" section above.

### Deferred capabilities
See "Deferred capabilities" section above.

### Blockers
- None for writing this PLAN.md by planner. Implementation is blocked until plan-review approves.

### Warnings
- `environment.yml` is a symlink to `../XRD-preprocessing/environment.yml` (outside the repository). It must not be changed in this PR.
- `requirements.txt` references `/Users/sad/dev/` paths that are specific to the original developer's environment. These are recognized as legacy dependency wiring and will need separate cleanup in future PRs.
- The `pyproject.toml` package `name` field remains `"aramis"` because changing it would break imports. This is intentional and documented as deferred.

## Files read
- `.project-memory/project_contract.yml`
- `.project-memory/memory_index.yml`
- `.project-memory/pr/0001-bremen-agent-workflow/PLAN.md`
- `.project-memory/pr/0001-bremen-agent-workflow/reviews/plan-review.yml`
- `.project-memory/pr/0001-bremen-agent-workflow/reviews/precommit-review.yml`
- `README.md`
- `pyproject.toml`
- `AGENTS.md`
- `src/aramis/__init__.py`
- `src/aramis/__main__.py`
- `agents/roles/01_bremen_product_architect.md`
- `agents/roles/04_bremen_precommit_reviewer.md`
- `agents/README.md`
- `agents/architect.yml`
- `agents/coder.yml`
- `agents/plan-review.yml`
- `agents/precommit-review.yml`
- `.gitignore`
- `requirements.txt`
- `packaging/eosproduct_bundle/environment.yml`

## Files written
- `.project-memory/pr/0002-aramis-to-bremen-cleanup/PLAN.md` (this file)

## Files intentionally ignored (not to be touched in this PR)
- All source code under `src/aramis/`
- All tests under `tests/`
- All configs under `config/`
- All examples under `examples/`
- All packaging under `packaging/`
- All agent configs under `agents/`
- All project-memory under `.project-memory/`
- All documentation under `docs/` (except planned new file `docs/repository_cleanup.md`)
- `environment.yml` (symlink to external)
- `requirements.txt`
- `.gitignore`
- All Docker, CI, and `.github/` files (none present)
- All infrastructure files

## Boundary confirmations

- confirm: only PLAN.md written: yes
- confirm: no code written: yes
- confirm: no tests written: yes
- confirm: no review artifact written: yes
- confirm: no runtime behavior changed: yes
- confirm: no source package rename performed: yes
- confirm: no import rename performed: yes
- confirm: no Docker/CI/API/H5/model/preprocessing/inference work planned for this PR: yes
- confirm: no automated search-and-replace planned: yes
- confirm: no git mutation commands run: yes
- confirm: Plan Drift Gate required: yes
- confirm: legacy name policy enforced: yes

## Final output

PLAN written: yes
