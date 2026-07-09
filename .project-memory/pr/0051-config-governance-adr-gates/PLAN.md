# PR 0051 — Plan: Config Governance ADR Gates

## 1. Title / Branch / Objective

- **Title**: Config Governance ADR Gates
- **Branch**: `0051-config-governance-adr-gates`
- **Objective**: Close or narrow the three open config governance decision gates (G-CFG-1, G-CFG-2, G-CFG-3) through a new ADR, config surface taxonomy documentation, and static governance validation tests. No runtime behavior changes, no new infrastructure, no new dependencies.

---

## 2. Precondition Verification

```
$ git rev-parse --verify HEAD
baa1e4f4d0b53296ee975373d0576458db55322a

$ git branch --show-current
0051-config-governance-adr-gates

$ git status --short
(clean — no uncommitted changes)
```

Branch matches. Working tree clean.

---

## 3. Roadmap Alignment

1. **PR0051 is the next roadmap item after PR0050.** The ROADMAP.md "Next Execution Sequence" table shows PR0050 → PR0051 → PR0052 → PR0053 → PR0054. PR0050 (model/version readiness cleanup) has been merged (confirmed by PR0050 precommit-review.yml and working tree state). PR0051 is the next scheduled item.

2. **PR0051 is config governance ADR/gates.** ROADMAP.md: "Close G-CFG-1/G-CFG-2/G-CFG-3 or explicitly defer with rationale. Config audit/history architecture only, no UI unless separately planned."

3. **PR0052 remains Matador boundary or system-of-record adapter skeleton.** This plan does not start any PR0052 work.

4. **FastAPI remains deferred.** No FastAPI, uvicorn, starlette, or ASGI references in this PR.

5. **PR0051 does not start PR0052 work.** No Matador adapter, system-of-record interface, or platform integration code.

---

## 4. Config Inventory Plan

### 4.1 Surface taxonomy

All config surfaces in the Bremen repository, classified by their lifecycle and owner:

| # | Surface | Location | Classification | Key characteristics |
|---|---------|----------|---------------|-------------------|
| 1 | Runtime model env vars | `src/bremen/config.py` (`read_cloud_config`), `src/bremen/api/model_state.py`, `src/bremen/logging_config.py` | **runtime config** | Environment variables read at startup. No hot-reload. No network calls. Values: `BREMEN_MODEL_BUCKET`, `BREMEN_MODEL_PREFIX`, `BREMEN_MODEL_VERSION`, `BREMEN_MODEL_MANIFEST_KEY`, `BREMEN_SERVICE_ENV`, `BREMEN_AWS_REGION`, `BREMEN_MODEL_URI`, `BREMEN_MODEL_CHECKSUM`, `BREMEN_MODEL_STAGING_DIR`, `BREMEN_CONFIG`, `BREMEN_LOG_LEVEL`. |
| 2 | CloudConfig dataclass | `src/bremen/config.py` | **runtime config** | Derived from environment at startup. No I/O, no network. Used by `model_source.py` to derive safe API response metadata. |
| 3 | Model source config | `src/bremen/api/model_source.py` | **runtime config** | Calls `derive_model_source()` which reads `CloudConfig`. Returns dict matching `ModelVersionResponse` field names. No model loading. |
| 4 | Model package manifest fields | `src/bremen/model_package.py` | **model artifact metadata** | 8 required manifest fields. Validated by `validate_model_manifest()`. SHA-256 checksum mandatory. Path traversal prevention. No joblib/pickle. |
| 5 | Preprocessing config YAMLs | `config/preprocessing/*.yaml` (5 files) | **preprocessing config** | HUMAN-1 product preprocessing branch configs. Contains local machine paths. Contains Aramis-derived excluded session IDs. Not imported by runtime at all. |
| 6 | Training config YAML | `config/training/bremen_v0_1_train.yaml` | **training config** | Example training config with 4 sections, 30+ fields. Contains local machine paths. Validated by `_validate_training_config()` in `pipeline.py`. Offline-only. |
| 7 | Terraform variable definitions | `infra/terraform/variables.tf`, `infra/terraform/ecs.tf`, `infra/terraform/apprunner.tf` | **deployment config** | Wires `BREMEN_MODEL_VERSION`, `BREMEN_MODEL_URI`, `BREMEN_MODEL_CHECKSUM` as Terraform variables. Validated by `test_bremen_model_package_terraform_env.py`. |
| 8 | API contract config fields | `docs/api_contract.md` | **runtime config** (documented) | `/model/version` response fields derived from config: `model_configured`, `model_status`, `model_uri_configured`, `checksum_configured`, `error_category`. |
| 9 | Test fixtures with config expectations | `tests/test_bremen_cloud_config.py`, `tests/test_bremen_config_loading.py`, `tests/test_bremen_model_package.py`, `tests/test_bremen_training_config.py`, `tests/test_bremen_model_package_terraform_env.py` | **test-only synthetic config** | Synthetic env vars, tempfile-based YAML files, in-memory config dicts. No real credentials. No real S3. |

### 4.2 Cross-surface observations

- **Runtime config (surfaces 1–3)** and **model artifact metadata (surface 4)** are the two surfaces that directly affect runtime prediction behavior. They have the highest governance priority.
- **Preprocessing config (surface 5)** and **training config (surface 6)** are offline-only. They are never imported by runtime modules. This boundary exists and is verified by existing AST-based import safety tests.
- **Deployment config (surface 7)** bridges runtime env vars to infrastructure. Already validated by static Terraform-env tests.
- **Test fixtures (surface 9)** are synthetic. No real H5, joblib, or credentials.
- Local machine paths exist in preprocessing and training configs (`io.input_h5_path`, `io.output_joblib_path`). These are offline-only and are used only during development/training, not during runtime.
- The `BREMEN_MODEL_URI` env var (surface 1) already supports `s3://`, `file://`, and plain filesystem paths. The `CloudConfig` validates that `BREMEN_MODEL_BUCKET` is not an `s3://` URI or a local path.
- The `model_uri_configured` and `checksum_configured` booleans in the API contract (surface 8) were introduced in PR0050 and provide safe config-presence indicators without leaking raw values.

---

## 5. Governance Decision Plan

### 5.1 G-CFG-1 — Build vs adopt (currently OPEN)

| Aspect | Value |
|--------|-------|
| Question | Build in-house config management vs. adopt existing config-management/feature-flag product |
| Recommended outcome | **Build lightweight in-repo governance now. No external config platform.** |
| Rationale | The project currently uses environment variables and YAML files for all config — standard-library Python. No existing config management product is in use. Adding an external config platform before the architecture is matured (before Matador boundary, before FastAPI migration, before config editing surface) introduces dependency risk, CI/CD complexity, and security surface without proven benefit. In-repo patterns (dataclasses, AST checks, static tests) work. The config editing surface (PR 0024) is explicitly deferred in ROADMAP.md. |
| Preserves boundaries | Yes — no new dependencies, no network calls, no infrastructure change. |
| Future escape | If Matador integration reveals a requirement for remote config or feature flags, a config management product can be evaluated at that point. G-CFG-1 would be reopened with specific requirements. |

### 5.2 G-CFG-2 — Persistence backend (currently OPEN)

| Aspect | Value |
|--------|-------|
| Question | Config state history store: DynamoDB vs. other |
| Recommended outcome | **Defer. No DynamoDB or database persistence until Matador/system-of-record boundary is designed.** |
| Rationale | ADR-0009 recommends DynamoDB as the recommended default but acknowledges no implementation yet. A config state history store requires: (a) a design for what states need versioning, (b) a query/audit API, (c) integration with the prediction audit trail, (d) IAM permissions and Terraform provisioning. None of these exist today. Building a database before the Matador boundary (PR0052) would risk designing the wrong schema. The runtime currently has no hot-reload or config editing. All config is static and set at deployment time. |
| Preserves boundaries | Yes — no DynamoDB, no AWS SDK usage, no database clients, no network calls. |
| Future trigger | G-CFG-2 is reopened when PR0052 (Matador boundary) is complete and config state history is a documented requirement. |

### 5.3 G-CFG-3 — Validation schema (currently OPEN)

| Aspect | Value |
|--------|-------|
| Question | Config validation schema: JSON Schema vs. Pydantic vs. custom |
| Recommended outcome | **Use existing Python infrastructure: dataclasses + custom validators + AST-based static checks + pytest gates. No new validation library.** |
| Rationale | The project already has working validation for all config surfaces: `CloudConfig` uses custom validation (`_validate_bucket`, `_validate_prefix`) in `config.py`; `model_package.py` uses `_REQUIRED_MANIFEST_FIELDS` dict + 6 validation functions; `pipeline.py` uses `_validate_training_config()` with required-section checks; `config.py` uses `discover_config()` with file-format-aware parsing; AST-based import safety tests prevent runtime/training cross-contamination; and the governance test file (planned in this PR) will add static gates. All of this uses standard-library Python + pytest. Adding JSON Schema, Pydantic, or any other validation library would introduce a dependency for marginal benefit over the current approach. |
| Preserves boundaries | Yes — no new dependencies, no dependency changes. |
| Future escape | If a config editing surface or API requires a formal schema contract (UI form generation, external validation, OpenAPI integration), Pydantic or JSON Schema could be evaluated as a FastAPI integration. That is deferred until FastAPI migration. |

### 5.4 Gate status matrix after PR0051

| Gate ID | Status before PR0051 | Status after PR0051 | Rationale reference |
|---------|---------------------|-------------------|-------------------|
| G-CFG-1 | OPEN | DECIDED — lightweight in-repo governance | Section 5.1 |
| G-CFG-2 | OPEN | DEFERRED — no backend until Matador boundary | Section 5.2 |
| G-CFG-3 | OPEN | DECIDED — existing Python infra (dataclasses + validators + tests) | Section 5.3 |

The ROADMAP.md Decision Gate Register will be updated to reflect these statuses after PR0051 merges.

---

## 6. ADR Plan

### 6.1 New ADR: `docs/adr/0011-config-governance-gates.md`

**Status**: Accepted (proposed in this PR)

**Structure**:

1. **Context** — References ADR-0004 (configuration management strategy, deferred editing surface) and ADR-0009 (config governance and audit state, config change classes A–D, config identity in predictions). Summarizes the three open gates.

2. **Config surface taxonomy** — Table from Section 4.1 of this plan, classifying 9 config surfaces by lifecycle and owner.

3. **Decision: G-CFG-1 — Lightweight in-repo governance** — No external config platform now. In-repo patterns (dataclasses, env vars, YAML, static tests) are sufficient. Escape clause: revisit if Matador or FastAPI integration reveals a remote config requirement.

4. **Decision: G-CFG-2 — No config backend until Matador boundary** — No DynamoDB, no database, no state history store implementation. ADR-0009's config change classes (A–D) remain valid architectural guidance but are not implemented. Escape clause: reopen when PR0052 (Matador boundary) is complete and config state history is a documented requirement.

5. **Decision: G-CFG-3 — Existing Python infrastructure for validation** — Dataclasses + custom validators + AST checks + pytest gates. No JSON Schema, Pydantic, or other validation library. The existing patterns in `config.py`, `model_package.py`, and `pipeline.py` are the governance pattern. Escape clause: revisit during FastAPI migration if a formal schema contract is needed.

6. **Config editing surface note** — PR 0024 remains deferred per ROADMAP.md. No config UI, API, or editing surface is implemented or designed in this ADR.

7. **Non-goals** — Same as this plan's Section 14.

8. **Consequences** — G-CFG-1 and G-CFG-3 are DECIDED, G-CFG-2 is DEFERRED. The static governance test file (`tests/test_bremen_config_governance.py`) documents the validation pattern. The config surface taxonomy will be maintained in the ADR.

### 6.2 Existing ADR changes

- **`docs/adr/0009-config-governance.md`**: No rewrite needed. The ADR's config change classes (A–D) and config identity in predictions remain valid architectural guidance. The "Future gates" section will be updated with a reference to ADR-0011. Minimal update only — one sentence and one cross-reference added at the end of the "Future gates" section.

### 6.3 Reference inventory expected in ADR-0011

The ADR must reference:
- ADR-0004 (configuration management strategy)
- ADR-0009 (config governance and audit state)
- ADR-0007 (model artifact lifecycle — for model package config boundary)
- ROADMAP.md Decision Gate Register
- `src/bremen/config.py` (CloudConfig validation)
- `src/bremen/model_package.py` (manifest validation)
- `src/bremen/training/pipeline.py` (`_validate_training_config`)

---

## 7. Gate Plan

### 7.1 Governance test file: `tests/test_bremen_config_governance.py`

A new test file implementing static/synthetic governance gates. No AWS, Docker, Terraform, App Runner, network calls, real H5, or real model artifacts.

#### Test class A: `TestRuntimeModelEnvVars` — Required runtime model env vars

1. `test_required_model_env_vars_are_documented` — AST-parses `src/bremen/config.py` for all `_ENV_*` constants, verifies each is documented in `docs/api_contract.md` or the ADR. Catches undocumented env vars.
2. `test_uri_checksum_booleans_are_safe` — Verifies `model_uri_configured` and `checksum_configured` in the `ModelVersionResponse` schema are `bool`, not `str`. (Regression guard for PR0050 contract.)

#### Test class B: `TestModelPackageManifestGovernance` — Manifest field stability

3. `test_required_manifest_fields_are_explicit` — Verifies `_REQUIRED_MANIFEST_FIELDS` dict in `model_package.py` has at least 8 entries and includes all fields: `artifact_type`, `model_version`, `model_checksum`, `model_filename`, `feature_schema_version`, `threshold_version`, `threshold_value`, `qc_criteria_version`.
4. `test_manifest_checksum_pattern` — Verifies `_SHA256_HEX_PATTERN` regex is `^[a-f0-9]{64}$` (lowercase only, no sha256: prefix). Verifies `compute_sha256` uses SHA-256 algorithm.

#### Test class C: `TestTrainingConfigOfflineBoundary` — Training/runtime separation

5. `test_training_config_not_imported_by_runtime` — AST-check: `src/bremen/config.py` must not import from `src/bremen/training/`. (Already tested implicitly by existing import safety tests; this makes the governance boundary explicit.)
6. `test_training_pipeline_config_not_used_by_runtime` — AST-check: `src/bremen/api/` modules must not import from `src/bremen/training/` or from `config/training/`.

#### Test class D: `TestPreprocessingConfigBoundary` — Preprocessing/runtime separation

7. `test_preprocessing_config_not_imported_by_runtime` — AST-check: `src/bremen/api/` modules must not import from `config/preprocessing/` or from any module under `src/bremen` that reads preprocessing YAML files at import time.
8. `test_preprocessing_yaml_not_in_runtime_paths` — Verifies that preprocessing config `io.input_h5_path` paths use offline-only patterns (e.g., relative paths starting with `../../../` or explicit data directories), not runtime paths.

#### Test class E: `TestNoSecretsInConfig` — Safe config surfaces

9. `test_no_full_s3_uri_in_config_surfaces` — Scans `config/` and `tests/test_bremen_config_governance.py` for `s3://` patterns that are NOT in synthetic test data, placeholder docs, or validation message strings. (Safe references are allowed; actual full S3 URIs are not.)
10. `test_no_account_ids_in_config_docs` — Scans `config/README.md`, `docs/adr/0009-config-governance.md`, and the ADR-0011 draft for account ID patterns.
11. `test_no_local_machine_paths_in_runtime_config` — Verifies that `src/bremen/config.py` `CloudConfig` and `model_source.py` `derive_model_source()` do not return local machine paths through any API response field. The `model_uri_configured` bool is the safe alternative.

#### Test class F: `TestConfigGovernanceDocAlignment` — ADR-to-test alignment

12. `test_config_governance_decisions_reflected_in_adr` — Reads `docs/adr/0011-config-governance-gates.md` (after this PR creates it) and verifies key phrases: "G-CFG-1", "G-CFG-2", "G-CFG-3", "DECIDED" or "DEFERRED", "lightweight in-repo", "no external config platform", "Matador boundary", "no DynamoDB".
13. `test_adr_references_existing_adrs` — Verifies ADR-0011 references ADR-0004 and ADR-0009.

#### Test class G: `TestModelSourceConfigSafety` — API safety

14. `test_model_source_does_not_return_raw_uri` — AST-check and runtime test: `derive_model_source()` returns a dict with `model_uri_configured` bool, not a raw URI string. The `model_checksum` field may return the checksum string (already exposed), but `model_checksum` is a known field — `checksum_configured` is the safe presence indicator.
15. `test_model_source_no_env_leakage` — Verifies `derive_model_source()` returns `None` for fields whose values are not yet known (e.g., `model_checksum` is `None` until package is fetched). The function reads only config metadata, not the model artifact itself.

### 7.2 Existing test file updates

#### `tests/test_bremen_cloud_config.py` — narrow addition

Add one test class:
- `TestCloudConfigSentinelSafety`: Verifies that `_ABSOLUTE_PATH_SENTINELS` in `config.py` includes `/Users/`, `/home/`, and `file://`. This formalizes the existing sentinel check as a governance gate.

#### `tests/test_bremen_config_loading.py` — no changes expected

The existing config loading tests already validate discovery order, path resolution, syntax errors, and import safety. No governance-specific changes needed.

#### `tests/test_bremen_training_runtime_separation.py` — new file (if created)

If the implementation agent prefers a dedicated file for training/runtime separation tests, it may create `tests/test_bremen_training_runtime_separation.py` instead of placing those tests in the governance test file. This is optional — either location is acceptable as long as the tests exist.

### 7.3 No source changes expected

This PR is docs + tests only. No `src/bremen/` source files must change. The governance gates validate existing behavior — they do not add new validation logic to runtime code.

**Exception**: If a tiny missing public constant or pure helper is needed for static validation (e.g., exporting `_REQUIRED_MANIFEST_FIELDS` from `model_package.py` when it is currently a module-private variable), the plan allows a single-line change. The implementation agent must document any such change in a Deviations section of the implementation commit message.

---

## 8. File Change Plan

### 8.1 New files

| File | Purpose |
|------|---------|
| `docs/adr/0011-config-governance-gates.md` | New ADR documenting config surface taxonomy, G-CFG-1/G-CFG-2/G-CFG-3 decisions, validation pattern, non-goals, escape clauses |
| `tests/test_bremen_config_governance.py` | Static governance validation tests — 7 test classes, ~15 test methods. All tests are AST-based or synthetic/mocked. |

### 8.2 Modified files

| File | Change type | Scope |
|---|---|---|
| `docs/adr/0009-config-governance.md` | Modify (one sentence + cross-reference) | Append reference to ADR-0011 at end of "Future gates" section. No existing content changed. |
| `tests/test_bremen_cloud_config.py` | Modify (one test class added) | Add `TestCloudConfigSentinelSafety` with 1–3 test methods verifying `_ABSOLUTE_PATH_SENTINELS`. |
| `config/README.md` | Optional modify (one section) | If the implementation agent chooses: add a brief "Config Governance" section at the end documenting the config surface taxonomy or pointing to ADR-0011. This is optional — the ADR alone is sufficient. |

### 8.3 No changes

| File | Rationale |
|------|-----------|
| `src/bremen/config.py` | No source changes needed. Governance tests validate existing behavior. |
| `src/bremen/api/model_source.py` | No source changes needed. Already returns safe booleans via PR0050. |
| `src/bremen/api/schemas.py` | No source changes needed. PR0050 already added governance-safe fields. |
| `src/bremen/model_package.py` | No source changes needed. Manifest validation already exists. Exception noted in Section 7.3. |
| `src/bremen/training/pipeline.py` | No source changes needed. Training config validation already exists. |
| `tests/test_bremen_config_loading.py` | No changes needed. Existing tests are sufficient. |
| `tests/test_bremen_model_package.py` | No changes needed. Already validates manifest fields and checksum. |
| `tests/test_bremen_model_package_terraform_env.py` | No changes needed. Already validates deployment env var wiring. |
| `tests/test_bremen_training_config.py` | No changes needed. Already validates training config structure. |

---

## 9. Preserved Boundaries

1. No FastAPI — preserved.
2. No Matador integration — preserved.
3. No DynamoDB/backend implementation — preserved.
4. No new deployment target — preserved.
5. No Docker changes — preserved.
6. No Terraform changes — preserved.
7. No dependency changes — preserved.
8. No training behavior changes — preserved.
9. No runtime model lifecycle changes — preserved.
10. No S3 staging changes — preserved.
11. No H5 staging changes — preserved.
12. No preprocessing changes — preserved.
13. No inference math changes — preserved.
14. No production smoke execution — preserved.
15. No clinical validation claims — preserved.
16. No runtime source code changes — preserved (exception noted in Section 7.3 for a single-line constant export if absolutely necessary).
17. No config editing surface — preserved (PR 0024 remains deferred).
18. No config state history store — preserved (G-CFG-2 deferred).

---

## 10. Validation Plan

### 10.1 Implementation validation

```bash
python -m compileall src tests

python -m pytest -q tests/test_bremen_config_governance.py -v
python -m pytest -q tests/test_bremen_cloud_config.py -v
python -m pytest -q tests/test_bremen_config_loading.py -v
python -m pytest -q tests/test_bremen_model_package.py -v
python -m pytest -q tests/test_bremen_model_package_terraform_env.py -v
python -m pytest -q tests/test_bremen_training_config.py -v
python -m pytest -q

python -m pytest -q -k "training_runtime_separation" -v  # if separate file created
```

### 10.2 Safety validation

```bash
# 1. Verify only allowed files changed
git diff --name-only

# 2. Verify no source, Docker, Terraform, CI, training, or roadmap changes
git diff --name-only -- src Dockerfile Dockerfile.training infra .github \
  requirements.txt pyproject.toml src/bremen/training ROADMAP.md || true

# 3. Verify no binary artifact changes
git diff --name-only | grep -E '\.(h5|hdf5|joblib|pkl|npy|npz|tfstate|tfstate\.backup)$' || true

# 4. Verify no FastAPI/DynamoDB/boto3/botocore introduced
grep -R "FastAPI\|fastapi\|uvicorn\|starlette\|DynamoDB\|boto3\|botocore" \
  -n src tests docs config requirements.txt pyproject.toml || true

# 5. Verify no secrets or full S3 URIs in new/modified governance files
grep -R "AKIA\|SECRET_ACCESS_KEY\|dkr.ecr\|Nova_\|s3://" \
  -n docs/adr/0011-config-governance-gates.md \
  tests/test_bremen_config_governance.py \
  tests/test_bremen_cloud_config.py || true

# 6. Verify ADR exists and has required sections
grep -c "## " docs/adr/0011-config-governance-gates.md
python -c "
with open('docs/adr/0011-config-governance-gates.md') as f:
    content = f.read()
checks = [
    'G-CFG-1' in content,
    'G-CFG-2' in content,
    'G-CFG-3' in content,
    'Context' in content,
    'Decision' in content or 'DECIDED' in content or 'DEFERRED' in content,
    'Consequences' in content or 'Non-goals' in content,
]
for i, c in enumerate(checks):
    assert c, f'ADR check {i} failed'
print(f'All {len(checks)} ADR checks passed')
"
```

### 10.3 Gate status verification

```bash
# Verify the ADR records all three gate decisions
python -c "
with open('docs/adr/0011-config-governance-gates.md') as f:
    text = f.read()
assert 'G-CFG-1' in text and ('DECIDED' in text or 'lightweight' in text)
assert 'G-CFG-2' in text and ('DEFERRED' in text or 'Matador' in text)
assert 'G-CFG-3' in text and ('DECIDED' in text or 'existing Python' in text)
print('All three gate decisions present in ADR')
"

# Verify existing ADR-0009 updated
python -c "
with open('docs/adr/0009-config-governance.md') as f:
    text = f.read()
assert 'ADR-0011' in text or '0011' in text
print('ADR-0009 references ADR-0011')
"
```

---

## 11. Non-Goals

1. No FastAPI.
2. No Matador adapter.
3. No config backend.
4. No DynamoDB implementation.
5. No AWS calls.
6. No App Runner deployment.
7. No Docker or Terraform change.
8. No dependency change.
9. No runtime model loading change.
10. No model package format change.
11. No preprocessing or inference change.
12. No training behavior change.
13. No production smoke execution.
14. No clinical validation claims.
15. No config editing surface (PR 0024 remains deferred).
16. No config state history store implementation (G-CFG-2 deferred).
17. No runtime source code changes (exception: one-line public constant export if needed for test validation — see Section 7.3).
18. No new validation schema library.
19. No prediction output or API contract shape changes (PR0050 already established the shape).
20. No roadmap changes during this PR (ROADMAP.md is a forbidden file during planning).

---

## 12. Implementation Agent Assignment

**Agent**: coder

**Ordered task list**:
1. Read this PLAN.md and the required artifacts listed in the task prompt (already all read by the plan agent).
2. Create `docs/adr/0011-config-governance-gates.md` following Section 6 of this plan.
3. Update `docs/adr/0009-config-governance.md` — add one sentence + cross-reference to ADR-0011 at end of "Future gates" section. Do not rewrite any existing content.
4. Create `tests/test_bremen_config_governance.py` following Section 7.1 of this plan (7 test classes, ~15 test methods).
5. Update `tests/test_bremen_cloud_config.py` — add `TestCloudConfigSentinelSafety` class (1–3 test methods).
6. Optionally update `config/README.md` — add brief "Config Governance" section pointing to ADR-0011.
7. Optionally create `tests/test_bremen_training_runtime_separation.py` if training/runtime separation tests are placed there instead of in the governance file.
8. Run validation checklist (Section 10) and fix any failures.
9. If any source change is required (Section 7.3 exception), document in a Deviations section of the implementation commit message.
10. Commit all changes. Verify no forbidden artifacts.

---

PLAN COMPLETE: yes

BLOCKERS: none

WARNINGS:
1. `bremen_one_to_many_preprocessing_v0_1.yaml` does not exist as a filename — the actual file is `bremen_one_to_many_benign_cancer_preprocessing_v0_1.yaml`. The task prompt listed the shorter name in required reads but the actual inventory has the longer name. The plan agent read the correct existing files (`bremen_one_to_one_preprocessing_v0_1.yaml` and the one_to_many_benign_cancer equivalents). No impact on the plan.
2. The `test_bremen_config_governance.py` file has 15 test methods across 7 classes. This is deliberately larger than the typical single-class pattern because governance tests are inherently multi-class (one class per config surface or governance concern). Each class follows TEST_DESIGN_STANDARD.md Rule 5 (one file, one testing pattern): the pattern is "static governance validation."
3. Safety validation step 5 (`grep -R ... s3://`) will match `s3://` patterns in validation error messages in `config.py` and in synthetic test data. These are safe — the grep output should be checked, not hidden. If only safe references are found, report them as safe. If any unexpected full S3 URIs appear, report them as blockers.
4. The plan permits an optional narrow source change (Section 7.3 exception) if a private constant needs to become public for test validation. The implementation agent must document any such change. No source changes are expected.

FILES CHANGED:
- `.project-memory/pr/0051-config-governance-adr-gates/PLAN.md` — written
- `.project-memory/pr/0051-config-governance-adr-gates/reviews/plan-review.yml` — future artifact

ROADMAP ALIGNMENT:
PR0051 is confirmed as the next roadmap item after merged PR0050. PR0052 (Matador boundary) is confirmed as the subsequent item. This plan does not start PR0052 work. FastAPI remains deferred.

CONFIG INVENTORY PLAN:
9 config surfaces identified and classified: runtime model env vars (1–3), model package manifest metadata (4), preprocessing config files (5), training config files (6), Terraform deployment config (7), API contract documented config fields (8), and test fixtures with synthetic config expectations (9). Each classified as runtime config, model artifact metadata, preprocessing config, training config, deployment config, or test-only synthetic config.

GOVERNANCE DECISION PLAN:
G-CFG-1: DECIDED — lightweight in-repo governance, no external config platform. G-CFG-2: DEFERRED — no backend until Matador boundary (PR0052 complete). G-CFG-3: DECIDED — existing Python infrastructure (dataclasses + validators + AST checks + pytest gates), no new validation library. All three decisions preserve no-network/no-new-dependency boundaries with documented escape clauses.

ADR PLAN:
New ADR (0011) with 8 sections covering context, config surface taxonomy, three gate decisions with rationales, config editing surface note, non-goals, and consequences. Existing ADR-0009 minimally updated (one cross-reference sentence added). ADR references ADR-0004, ADR-0007, ADR-0009, and ROADMAP.md.

GATE PLAN:
15 test methods across 7 classes in a new governance test file. One existing test file (test_bremen_cloud_config.py) gets a single class addition. All tests are static/synthetic (AST-parsing, regex scanning, dataclass inspection). No AWS, Docker, Terraform, App Runner, network calls, real H5, or real model artifacts.

FILE CHANGE PLAN:
2 new files (ADR-0011, governance test file). 1 modified existing doc (ADR-0009, one sentence). 1 modified existing test (test_bremen_cloud_config.py, one class). 1 optional doc (config/README.md). No source file changes expected. Exception path documented for a single-line public constant export if needed.

PRESERVED BOUNDARIES:
All 20 boundaries preserved. No runtime lifecycle, no FastAPI, no Matador, no config backend, no DynamoDB, no Docker, no Terraform, no dependencies, no training, no preprocessing, no inference, no production smoke, no clinical claims, no config editing surface design, no state history store implementation.

VALIDATION PLAN:
Compileall + 7 test suite commands + full suite + 6 safety/diff/grep scans + 2 ADR content verification scripts.

NON-GOALS:
20 non-goal categories listed. Key: no config backend, no state history store, no editing surface, no runtime source changes, no new validation library, no prediction contract changes, no roadmap changes during PR.

---

Implementation agent: coder
