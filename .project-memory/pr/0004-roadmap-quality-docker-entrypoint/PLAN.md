# PR 0004 — Correct Roadmap-Only PLAN for Docker, Quality Gates, CI, and Unified Entrypoint

Author: planner
Mode: planning correction only
Branch: 0004-roadmap-quality-docker-entrypoint

## Goal

Rewrite PLAN.md so PR 0004 is strictly a roadmap/documentation-only update. This PR must only update planning/roadmap documentation. It must not implement Docker, GitHub Actions, SonarCloud, unified entrypoint, config discovery, config validation, runtime code, tests, configs, examples, or packaging behavior.

This PR's sole artifact written by planner is this PLAN.md. The coder writes only the allowed documentation files listed below, after plan-review approval.

## Correction context

The previous PLAN.md was blocked by plan-review because:
1. It was not strictly bounded as a docs-only roadmap PR.
2. It mixed roadmap planning with implementation-adjacent details (e.g., specific CLI flags, Dockerfile content, GitHub Actions workflow steps).
3. It did not make the future-test policy enforceable enough (required specific test/check lists per future PR).

## Strict scope

PR 0004 is **documentation-only**. No source code, tests, configs, examples, Dockerfiles, CI workflows, SonarCloud configuration, or infrastructure files may be created or modified.

The only outcome of PR 0004 is an updated set of planning documents that describe what future PRs (0005, 0006, 0007, and later) will implement. Nothing described in the roadmap is implemented in PR 0004.

## Allowed implementation files (coder may create or modify)

PLAN.md selects these exact files. No other files may be changed.

1. **`docs/roadmap.md`** — NEW file. The primary roadmap document for Bremen. Must:
   - Describe completed milestones (PR 0001, PR 0002, PR 0003) in one to two sentences each.
   - Describe future PRs 0005, 0006, 0007, and later PRs using **future-tense roadmap language only**.
   - State that every future implementation PR requires tests (see "Future test policy" section below for the required test categories per PR).
   - Use only roadmap-level acceptance criteria. Do not include CLI command syntax, function signatures, Dockerfile instructions, YAML workflow definitions, or any code-level design.

2. **`docs/repository_cleanup.md`** — MODIFY. Append a "Future PR Sequencing" section after the existing cleanup tables. Must:
   - List planned follow-up PRs (0005, 0006, 0007) with one-sentence descriptions.
   - Reference `docs/roadmap.md` as the authoritative roadmap.
   - Not alter existing cleanup documentation.

3. **`README.md`** — MODIFY. Add a "Development Roadmap" section (or update the existing "Planned Product Deliverables" section) that:
   - Links to `docs/roadmap.md` as the authoritative roadmap.
   - Summarizes the next three planned PRs in one sentence each.
   - Does not duplicate the full roadmap content.
   - Preserves all existing Bremen identity, safety, and disclaimer language.

4. **`.project-memory/memory_index.yml`** — MODIFY. Add entries for:
   - `docs/roadmap.md` as a new planning artifact.
   - `pr/0004-roadmap-quality-docker-entrypoint/` directory reference.
   - `pr/0005-docker-gha-sonarcloud/` as a future planned PR.
   - `pr/0006-unified-entrypoint-config-discovery/` as a future planned PR.
   - `pr/0007-config-validation/` as a future planned PR.
   - Do not remove or alter existing entries.

No other files may be created or modified by the coder in PR 0004.

## Forbidden files (must not be created or modified in PR 0004)

- `src/**`
- `tests/**`
- `config/**`
- `examples/**`
- `Dockerfile`
- `.dockerignore`
- `.github/**`
- `sonar-project.properties`
- `pyproject.toml`
- `environment.yml`
- `Makefile`
- `packaging/**`
- `agents/**`
- `docs/architecture.md`
- `docs/api_contract.md`
- `docs/h5_metadata_contract.md`
- `docs/model_release_package.md`
- `docs/qc_gates.md`
- Any H5/HDF5 files
- Any binary/model artifacts

## Wording constraints for docs/roadmap.md

The coder must follow these wording rules when writing `docs/roadmap.md`:

- Every future PR must be described using future-tense language: "PR 0005 **will add** Docker packaging…", "PR 0006 **will converge** to one entrypoint…", "PR 0007 **will introduce** config validation…"
- Never write "PR 0005 creates Dockerfile" — instead write "PR 0005 will add a Dockerfile and .dockerignore."
- Never write "PR 0005 adds GitHub Actions" — instead write "PR 0005 will add a GitHub Actions workflow with compileall, pytest, Docker build, and SonarCloud scan."
- Never write "Bremen has a unified entrypoint" — instead write "PR 0006 will converge Bremen to one command surface."
- Never write "Config validation checks for missing fields" — instead write "PR 0007 will introduce config validation that checks for missing required fields."
- Do not include implementation commands (e.g., `docker build`, `pytest -q`, sonar-scanner flags, CLI function signatures, config file paths).
- Do not claim SonarCloud is a release gate. State that it is quality visibility only.
- Do not claim config validation exists yet. State that it is deferred to PR 0007.
- Do not claim a unified entrypoint exists yet. State that it is planned for PR 0006.
- Do not claim Docker/GitHub Actions/SonarCloud exist yet. State that they are planned for PR 0005.
- Use only roadmap-level acceptance criteria. Do not include code-level design details.

## Future PR descriptions (roadmap content level)

The roadmap must describe these future PRs at the acceptance-criteria level only, using future-tense wording:

### PR 0005 — Docker + GitHub Actions + SonarCloud skeleton

A future PR that will add:
- Docker packaging (Dockerfile, .dockerignore) for the Bremen application.
- A container smoke test (e.g., verify the container starts and `--help` works).
- No model or H5 data baked into the image.
- No secrets in the image.
- A GitHub Actions workflow that will run:
  - `compileall` check across source and test files.
  - `pytest` to execute the existing test suite.
  - Docker build check (verify the image builds).
  - SonarCloud scan for static quality visibility.
- SonarCloud configuration with project key, organization, and token sourced from human-provided GitHub secrets only. No secrets committed.
- SonarCloud is quality visibility, not a release gate.
- Tests and checks mandatory (compileall, pytest, Docker build smoke, SonarCloud scan execution).

### PR 0006 — Unified Bremen entrypoint and config discovery/loading

A future PR that will add:
- One Bremen command surface, converging from multiple config-specific scripts.
- Config selection by name, by explicit file path, or by default discovery.
- A command to list available configs when no argument is given.
- Loading of existing config files without changing their semantics.
- No changes to preprocessing behavior, model behavior, or config file structure.
- Tests mandatory: entrypoint tests, config discovery and listing tests, config path/name/default resolution tests.
- Precommit-review evidence with command outputs required.

### PR 0007 — Config validation contract and tests

A future PR that will add:
- A config schema/contract defining required fields and structure.
- Strict validation errors for missing required fields, invalid paths, unsupported modes, and target/control consistency.
- Integration with the unified entrypoint from PR 0006.
- No changes to preprocessing behavior, model behavior, or config file structure.
- No H5/HDF5 file modification.
- Tests mandatory: config validation unit tests, negative validation tests (expecting rejection), target/control consistency tests.
- Precommit-review evidence with command outputs required.

### Later PRs (after PR 0007)

The roadmap may list these at the description level only (one sentence each):
- **Model package contract**: Define the controlled joblib package format, checksum verification, model metadata schema, and loading gate.
- **H5 metadata gate**: Validate H5 metadata against contract, enforce target/control same-patient/opposite-side rules.
- **Inference API**: Prediction endpoint with feature schema validation, QC gates, and required prediction metadata fields.
- **Matador integration**: Platform API integration with Matador as system of record.

## Future test policy

This PR (0004) is docs-only — no tests required. However, every future implementation PR must require tests, and `docs/roadmap.md` must explicitly state the test categories per PR. The coder must include this test policy table or equivalent in `docs/roadmap.md`:

| Future PR | Required tests / checks |
|-----------|------------------------|
| PR 0005 | compileall, pytest, Docker build smoke verification, SonarCloud scan execution |
| PR 0006 | Entrypoint unit tests, config discovery/listing tests, config path/name/default resolution tests |
| PR 0007 | Config validation unit tests, negative validation tests (rejection of invalid configs), target/control consistency tests |
| All later PRs | Precommit-review evidence with command outputs for each check |

## Validation commands for precommit-review

Precommit-review must execute these commands before allowing code commits.

### 1) Working tree state
```bash
git status --short
```

### 2) Changed files
```bash
git diff --name-only
```

### 3) Roadmap content check — future PR references
```bash
grep -R -I -n -E "Docker|SonarCloud|GitHub Actions|unified entrypoint|config discovery|config validation|PR 0005|PR 0006|PR 0007" docs/roadmap.md README.md .project-memory 2>/dev/null
```
Must show that these topics are referenced in the roadmap.

### 4) Future/deferred language check
```bash
grep -R -I -n -E "future PR|deferred|roadmap" docs/roadmap.md README.md .project-memory 2>/dev/null
```
Must show that the roadmap uses future/deferred language.

### 5) Docker infrastructure not created
```bash
test ! -e Dockerfile && echo "Dockerfile absent" || echo "ERROR: Dockerfile exists"
test ! -e .dockerignore && echo ".dockerignore absent" || echo "ERROR: .dockerignore exists"
```

### 6) GitHub Actions not created
```bash
test ! -d .github && echo ".github absent" || echo "ERROR: .github exists"
```

### 7) SonarCloud config not created
```bash
test ! -e sonar-project.properties && echo "sonar-project.properties absent" || echo "ERROR: sonar-project.properties exists"
```

### 8) Forbidden-path check
```bash
git diff --name-only | grep -E "^(src/|tests/|config/|examples/|Dockerfile|\.dockerignore|\.github/|sonar-project\.properties|pyproject\.toml|environment\.yml|Makefile)" && exit 1 || echo "OK"
```
Must print "OK". Any match means the commit includes a forbidden path.

### 9) .DS_Store check
```bash
find . -name ".DS_Store" -print
```

### 10) H5/HDF5 check
```bash
find . -type f \( -name "*.h5" -o -name "*.hdf5" \) -print
```

## Plan Drift Gate

Precommit-review must check each of these drift categories. Any drift blocks merge until resolved.

| Drift category | Check |
|----------------|-------|
| **File drift** | Only the four allowed files (docs/roadmap.md, docs/repository_cleanup.md, README.md, .project-memory/memory_index.yml) appear in `git diff --name-only`. No forbidden paths. |
| **Roadmap-only drift** | PR 0004 modifies only planning/roadmap documentation. No implementation code, tests, configs, examples, or infrastructure. |
| **PR sequencing drift** | docs/roadmap.md sequences PR 0005 before PR 0006 before PR 0007. Later PRs are after 0007. |
| **Docker implementation drift** | No Dockerfile, .dockerignore, or docker commands appear in the commit. Docker is described only as a future PR. |
| **GitHub Actions implementation drift** | No .github/ directory or workflow files appear in the commit. GitHub Actions is described only as a future PR. |
| **SonarCloud implementation drift** | No sonar-project.properties or scanner configuration appears in the commit. SonarCloud is described only as a future PR. |
| **Unified-entrypoint implementation drift** | No entrypoint CLI code or function signatures appear in the commit. Unified entrypoint is described only as a future PR. |
| **Config-discovery implementation drift** | No config-discovery or config-loading code appears in the commit. Config discovery is described only as a future PR. |
| **Config-validation implementation drift** | No config-validation code or validation logic appears in the commit. Config validation is described only as a future PR (0007). |
| **Runtime drift** | No changes to src/, tests/, config/, examples/. No changes to preprocessing, H5, joblib, or model behavior. |
| **Test-policy drift** | docs/roadmap.md explicitly requires tests for every future implementation PR. Test categories per PR are listed. |
| **Validation drift** | All validation commands (1-10) pass without error. |
| **Future-scope drift** | Later PRs (model package, H5 gate, inference API, Matador) are described at high level only with no implementation details. |
| **Blockers** | Any blocking condition (see Stop conditions) found during drift gate evaluation prevents merge. |

## Stop conditions

Implementation is blocked if any of these conditions are detected during plan-review or precommit-review:

- Block if PR 0004 attempts to implement Docker (Dockerfile, .dockerignore, or docker commands in the commit).
- Block if PR 0004 attempts to add GitHub Actions (.github/ directory or workflow files in the commit).
- Block if PR 0004 attempts to add SonarCloud config (sonar-project.properties in the commit).
- Block if PR 0004 attempts to add unified entrypoint code (CLI implementation, function signatures, or entrypoint logic in the commit).
- Block if PR 0004 attempts to add config discovery/loading code.
- Block if PR 0004 attempts to add config validation code or validation logic.
- Block if PR 0004 changes src/ (source), tests/ (tests), config/ (configs), or examples/ (example files).
- Block if PR 0004 changes pyproject.toml, environment.yml, or Makefile.
- Block if PR 0004 does not make future tests mandatory and enforceable (test policy table missing from docs/roadmap.md).
- Block if PR 0004 modifies H5/HDF5 files or model artifacts.
- Block if the working tree contains unrelated implementation files or dirty state not caused by the allowed files.

## Decisions summary

### Allowed files
1. `docs/roadmap.md` — NEW, primary roadmap (future-tense, acceptance-criteria level only)
2. `docs/repository_cleanup.md` — MODIFY, append future PR sequencing section
3. `README.md` — MODIFY, add roadmap section/link
4. `.project-memory/memory_index.yml` — MODIFY, add roadmap and future PR references

### Forbidden files
- `src/**`, `tests/**`, `config/**`, `examples/**`
- `Dockerfile`, `.dockerignore`, `.github/**`, `sonar-project.properties`
- `pyproject.toml`, `environment.yml`, `Makefile`
- `packaging/**`, `agents/**`
- `docs/architecture.md`, `docs/api_contract.md`, `docs/h5_metadata_contract.md`, `docs/model_release_package.md`, `docs/qc_gates.md`
- Any H5/HDF5 or binary/model artifacts

### Roadmap-only boundary
PR 0004 modifies only planning/roadmap documentation. All feature descriptions use future-tense language. No implementation, no infrastructure, no tests, no configs, no examples.

### PR 0005 roadmap
Future PR that will add Docker packaging (Dockerfile, .dockerignore, container smoke test), GitHub Actions workflow (compileall, pytest, Docker build, SonarCloud scan), and SonarCloud configuration (quality visibility only, no secrets committed). Not implemented in PR 0004.

### PR 0006 roadmap
Future PR that will converge to one Bremen command surface with config selection by name/path/default discovery, config listing, and config file loading without changing semantics. Not implemented in PR 0004.

### PR 0007 roadmap
Future PR that will introduce config validation with schema/contract checks, strict error reporting for invalid configs, and integration with the unified entrypoint. Not implemented in PR 0004.

### Later PR roadmap
Model package contract, H5 metadata gate, inference API, Matador integration — described at high level only.

### Future test policy
PR 0004 is docs-only. PR 0005 requires compileall, pytest, Docker build smoke, SonarCloud scan execution. PR 0006 requires entrypoint/config discovery/resolution tests. PR 0007 requires config validation unit tests, negative tests, and target/control consistency tests. All later PRs require precommit-review evidence with command outputs.

### Validation commands
Ten validation commands covering working tree state, changed files, roadmap content (future PR references and future/deferred language), Docker/GitHub Actions/SonarCloud absence, forbidden-path check, .DS_Store, and H5/HDF5 files.

### Stop conditions
Eleven block conditions covering implementation drift in Docker, GitHub Actions, SonarCloud, entrypoint, config discovery, config validation, source/tests/config/examples, pyproject/environment/Makefile, test policy, H5/model artifacts, and dirty tree.

### Plan Drift Gate requirements
Fourteen drift-check criteria enforced by precommit-review: file drift, roadmap-only drift, PR sequencing drift, Docker/CI/SonarCloud/entrypoint/config-discovery/config-validation implementation drift, runtime drift, test-policy drift, validation drift, future-scope drift, and blockers.

### Blockers
- None for writing this corrected PLAN.md. Implementation blocked until plan-review approves.
- Implementation blocked if any validation command fails during precommit-review.
- Implementation blocked if the corrected wording constraints are violated (future-tense, no implementation language).

### Warnings
- The previous PLAN.md was blocked for mixing roadmap planning with implementation-adjacent details. This corrected PLAN.md removes all implementation language.
- `docs/architecture.md` is not an allowed file in PR 0004. If needed, it must be added in a later PR.
- All feature descriptions must use future-tense language only. Any present-tense implementation claim in the roadmap is a drift violation.
- This PR must not be used to sneak in any implementation work, even as "documentation examples."

## Files read
- `.project-memory/pr/0004-roadmap-quality-docker-entrypoint/PLAN.md` (previous version, to correct)
- `.project-memory/project_contract.yml`
- `.project-memory/memory_index.yml`
- `.project-memory/pr/0001-bremen-agent-workflow/PLAN.md`
- `.project-memory/pr/0001-bremen-agent-workflow/reviews/precommit-review.yml`
- `.project-memory/pr/0003-full-aramis-to-bremen-alignment/PLAN.md`
- `.project-memory/pr/0003-full-aramis-to-bremen-alignment/reviews/precommit-review.yml`
- `README.md`
- `AGENTS.md`
- `docs/product_development_rules.md`
- `docs/repository_cleanup.md`
- `docs/data_preprocessing.md`
- `docs/machine_learning_concept.md`
- `docs/mlflow.md`
- `docs/agbh_quality_exclusions.md`
- `docs/eosproduct_environment.md`

## Files written
- `.project-memory/pr/0004-roadmap-quality-docker-entrypoint/PLAN.md` (this corrected file)

## Files intentionally ignored
- All source code under `src/bremen/`
- All tests under `tests/`
- All configs under `config/`
- All examples under `examples/`
- All agent configs under `agents/`
- `packaging/`
- `environment.yml`, `Makefile`, `.gitignore`
- Any non-existent files (Dockerfile, .dockerignore, .github/, sonar-project.properties)
- Any H5/HDF5 files
- Any binary/model artifacts

## Boundary confirmations

- confirm: only PLAN.md written: yes
- confirm: no code written: yes
- confirm: no tests written: yes
- confirm: no review artifact written: yes
- confirm: no Docker/CI/SonarCloud files written: yes
- confirm: no runtime behavior changed: yes
- confirm: no unified entrypoint implemented: yes
- confirm: no config discovery implemented: yes
- confirm: no config validation implemented: yes
- confirm: future implementation PRs require tests: yes
- confirm: no H5/HDF5 files read or edited: yes
- confirm: no git mutation commands run: yes
- confirm: all feature descriptions use future-tense language: yes
- confirm: no implementation commands or code-level design included: yes
- confirm: allowed files are strictly limited to docs/planning surfaces: yes
- confirm: test policy per future PR is explicit and enforceable: yes
- confirm: Plan Drift Gate includes all fourteen required drift checks: yes

## Final output

PLAN written: yes
