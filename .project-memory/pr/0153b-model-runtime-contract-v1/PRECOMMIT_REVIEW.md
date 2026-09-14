# PR0153B Pre-Commit Review — Model Runtime Contract v1

## Branch
`0153b-model-runtime-contract-v1` (verified via `git branch --show-current`)

## HEAD
`a2fabd74737dc4133273f19e4b5ecee5da6d3995` (verified via `git rev-parse --verify HEAD`;
base commit is "docs: define model runtime contract v1, #213". No commit created by this
review; worktree at review time 2026-09-14T20:42:06Z)

## PLAN reviewed
`.project-memory/pr/0153b-model-runtime-contract-v1/PLAN.md` — read in full (interface
form, Bremen/Aramina adaptation strategy, requirements wiring, error-compatibility
strategy, expected files, test strategy). `IMPLEMENTATION_REPORT.txt` present alongside.

## ADR/contract reviewed
- `docs/adr/0016-model-runtime-contract-v1.md` (Accepted; committed at base #213) —
  read in full. Semantic responsibilities requirements()/validate()/predict();
  WorkflowProvider MUST NOT implement model-specific feature engineering; no public
  API/error/report changes authorized; framework adoption explicitly out of scope.
- `docs/model_runtime_contract_v1.md` — read in full including the PR0153B
  implementation notes and PR0154 coupling additions (working-tree diff changes status
  Proposed→Accepted and appends implementation notes only; Part 1 rules untouched).

## PR0152 evidence reviewed
`.project-memory/pr/0152-bremen-3x3-runtime-parity/{PLAN.md,PRECOMMIT_REVIEW.md}` and
`docs/bremen_3x3_training_parity.md` (Parts 1+2) — read (unchanged in git status;
PR0152 review is this repository's prior frozen baseline: golden parity diff 0.0,
probability 0.7388733541967353, atol 1e-10/rtol 0, 3+3 contract, runtime-owned science).

## Changed files (all read completely)
`git diff --name-status`: 7 modified; untracked: `src/bremen/model_runtime.py` (NEW),
`tests/test_bremen_model_runtime_contract_v1.py` (NEW),
`.project-memory/pr/0153b…/{PLAN.md,IMPLEMENTATION_REPORT.txt}`.

| File | Status |
| --- | --- |
| `docs/model_runtime_contract_v1.md` | M (status + implementation notes + PR0154 coupling) |
| `src/bremen/model_runtime.py` | NEW (contract, types, error categories) |
| `src/bremen/bremen_runtime.py` | M (contract methods; error hierarchy link; science untouched) |
| `src/bremen/api/workflow_bremen.py` | M (contract routing; envelope-preserving translation) |
| `src/bremen/api/workflow_aramina.py` | M (AraminaRuntime adapter; provider delegates) |
| `src/bremen/api/workflow_provider.py` | M (additive `model_runtime()` accessor) |
| `src/bremen/api/model_requirements.py` | M (runtime-derived requirements, additive) |
| `tests/test_bremen_model_runtime_contract_v1.py` | NEW (36 tests) |
| `tests/test_bremen_3x3_runtime_parity.py` | M (+1 contract-wiring test; nothing removed) |

No ZIP, H5, joblib, pickle, training repository, private data, binary model or large
binary fixture added (status scanned; only .py/.md/.txt artifacts).

## Common runtime abstraction assessment
**PASS — one real, non-cosmetic contract.** `src/bremen/model_runtime.py` defines
`ModelRuntime` (structural `typing.Protocol`, `runtime_checkable`) with exactly the
three semantic responsibilities — `model_requirements() -> ModelRequirements`,
`validate_model_input(ModelInput) -> ModelValidation`,
`predict_model(ModelInput) -> RuntimePrediction` — plus the frozen dataclass carriers
and the internal ownership error categories (`ModelRuntimeError` base;
`ModelInputInvalidError` / `ModelInputUnsupportedError` /
`ModelConfigurationRequiredError` / `ModelPreprocessingFailedError` /
`ModelInferenceFailedError`). Method names carry a `model_` prefix to stay unambiguous
against `WorkflowProvider` lifecycle methods — repository convention justifies it
(protocol precedent: `EventSink`, `RecordResolver`). It is not cosmetic: both
production providers route compatibility checks, requirements derivation and the
single scientific execution through it (`validate_model_input` in
`BremenProvider.validate_compatibility`, one `predict_model` call per `execute`),
and a minimal fake runtime drives `BremenProvider.execute` end-to-end without any
provider change (contract suite §5). It is not overly broad: no HTTP, auth, job
persistence, report URLs, frontend, storage credentials or registry concepts appear
in the contract module (grep-verified; imports are stdlib only).

## Dependency-direction assessment
**PASS.** `bremen/model_runtime.py` imports only stdlib (`collections.abc`,
`dataclasses`, `typing`) — nothing from `bremen.api`, `bremen_runtime`,
`bremen_features`, `workflow_*`, Aramina preprocessing/symmetry, or any model science
(grep + dedicated test `test_model_runtime_imports_no_platform_or_model_specific_code`).
Platform orchestration depends on the contract (`workflow_bremen`, `workflow_aramina`,
`model_requirements` import `bremen.model_runtime`); the contract depends on nothing
platform-side. No circular imports (compileall passes; contract module is a leaf).
No FastAPI/Request objects anywhere in the contract or either runtime
(`grep fastapi|Request` → none in `model_runtime.py`, `bremen_runtime.py`; Aramina
runtime consumes a plain `ModelInput` carrier).

## Bremen adaptation
**PASS — direct conformance, zero scientific change.**
`BremenRuntime` implements the contract directly (no wrapper): `model_requirements()`
declares exact 3 LEFT + 3 RIGHT (six total), `requires_target_side=False`,
`request_fields=("container_id","source_id")`, version `0.2.0-paper-reference`;
`validate_model_input()` wraps the frozen `validate_bremen_shape` and returns the
established safe reason; `predict_model()` delegates to the untouched PR0152 `run()`
sequence (validate → features → score → decide; proven by
`test_bremen_predict_preserves_frozen_sequence` asserting exactly one `run()` call and
`test_provider_executes_through_model_runtime_contract_v1` asserting exactly one
`predict_model` + one `run` per `execute`). `BremenRuntimeError` now derives from
`ModelRuntimeError` (still a `ValueError` with the same string argument), so existing
`except BremenRuntimeError` boundaries keep working; safe reasons are byte-identical
(`requires_exactly_3_left_3_right`, `invalid_scientific_profiles`,
`raw_peak_gate_failed`, `model_not_ready`, `model_execution_failed`,
`invalid_feature_schema`). `workflow_bremen.py` remains an orchestration adapter:
compatibility via `runtime.validate_model_input`, one `predict_model` call, category→
envelope translation (`Incompatible: <reason>`,
`Workflow configuration required for multi-position input`, `Model execution failed`,
`Feature construction failed: <safe_reason>`), identical payload projection. No
Bremen preprocessing or feature generation returned to the provider (grep of the
provider class for scientific patterns → none; the only numpy use is `np.isnan`/
`np.isfinite` counting in `validate_features` event diagnostics — pre-existing
platform observability).

## Bremen parity results
**PASS — all required parity dimensions green (executed during this review):**
- `tests/test_bremen_3x3_runtime_parity.py` + `tests/test_bremen_3x3_training_parity.py`
  + `tests/test_bremen_workflow_bremen.py` + `tests/test_bremen_runtime_plugin.py`
  → **151 passed** (was 150 before the +1 wiring test).
- 15-feature golden parity: unchanged (atol 1e-10, rtol 0; diff 0.0).
- Golden probability: unchanged (`0.7388733541967353`; `test_bremen_predict_returns_
  structured_result` asserts it through the contract `predict_model` path).
- 3+3 contract: unchanged (9 invalid shapes fail closed before science/scoring;
  runtime-level shape rejections additionally covered by the contract suite).
- All-six participation: unchanged (6 mutations vs frozen `intermediates.json`).
- Permutation invariance: unchanged (12 provider-level + 12 H5-enumeration cases).
- Raw-H5 parity: unchanged (`test_synthetic_h5_production_job_path` via
  `_normalize_h5(workflow_id="bremen")` and full `run_workflow_request`).
- Invalid-shape behavior: unchanged error strings.

## Aramina adaptation
**PASS — adapter, not rewrite.** `AraminaRuntime` lives in the authoritative
`api/workflow_aramina.py` module and composes the existing functions unchanged
(`_build_aramina_request_json` → `_run_local_artifact`, which itself performs
artifact load/validation, target selection, artifact-owned preprocessing, profile
matrix, LR1 scoring + logit aggregation, symmetry features, final model, threshold).
The diff shows **zero modifications** to any Aramina scientific function — only the
additive runtime class, additive constants, and the provider's request construction
moved into a `ModelInput`. `target_side` semantics unchanged (explicit left/right,
normalized lowercase, `ARAMINA_INVALID_REQUEST` preserved); model selection unchanged
(registry entry-driven, `get_provider_for_model` untouched); preprocessing release
gating and safe preprocessing failure classification unchanged
(`ARAMINA_UNSUPPORTED_INPUT` + `preprocessing_contract` + allowlisted worker
diagnostic); LR1/symmetry/final-model/probability/threshold code paths byte-identical;
report payload identical (`risk_probability`, `risk_score` alias, `target_side`,
`model_name/version`, reliability fields). One subtle coercion in the adapter
(`str(parameters.get("analysis_author", "") or "")`) was checked against both
production `AraminaProviderRequest` construction sites
(`aramina_provider.py:144`, `job_api_handler.py:492`): both guarantee `str` fields
before the provider ever sees them, so behavior is identical on all reachable paths.

## Aramina regression results
**PASS.** `test_aramina_workflow_runtime.py` + `test_aramina_provider_contract.py` +
`test_bremen_workflow_aramina_scaffold.py` → **282 passed**. Extended Aramina-adjacent
run (report parity, decision support, model catalog, FastAPI jobs/report parity,
defer-interpretation parity) → **365 passed**. No Aramina prediction or failure-contract
change observed.

## WorkflowProvider boundary assessment
**PASS.** `WorkflowProvider` gains only a non-abstract `model_runtime()` returning
`None` by default (purely additive; scaffold/display-only providers unaffected).
Provider scientific-pattern scan and classification:
- `workflow_bremen.py` (provider class): per-side measurement counts, readiness flags,
  event emission, `np.isnan/isfinite` diagnostic counting in `validate_features`,
  payload copying → **platform adapter logic, acceptable**. No feature formulas,
  scaler math, estimator math or threshold application remain (grep → none).
- `workflow_aramina.py` (provider class): request-carrier construction, one
  `predict_model` call, error→`WorkflowResult` translation → **platform adapter
  logic, acceptable**. All Aramina science (LR1 loop, logit aggregation, symmetry,
  final estimator, threshold) sits in the module's pipeline functions consumed via
  `AraminaRuntime` → **runtime-owned and correct**.
- No classification of "scientific logic incorrectly remaining in provider" applies;
  the blocking condition is not met.

## Model Requirements integration assessment
**PASS — backward compatible, additive, non-duplicating.**
`_runtime_input_requirements(model_id)` resolves entry → provider (existing registry
routing, no redesign; `get_provider_for_model` constructs providers from in-memory
registry packages — no artifact I/O, no jobs, no persistent state) → `model_runtime()
-> model_requirements().to_input_requirements()`, defensively returning `None` on any
unreachability. In `_build_declared_requirements_response`: runtime-declared
request fields are used **only** when the manifest declares none; the container
contract gains an additive `model_runtime: {contract_version, input_requirements}`
block (static model-declared values only). Endpoint paths, existing field names and
types unchanged (`test_model_requirements_endpoint_paths_and_fields_unchanged`);
no-manifest/display-only responses unchanged (`test_requirements_noop_without_manifest_
unchanged`, `test_display_only_aramina_has_no_runtime_derivation`); the full PR0122–
PR0127 requirements API suite passes (within the 96-test run). Bremen and Aramina
expose genuinely different requirements behind the same contract type
(`test_model_specific_requirements_differ_behind_same_type`). The single
requirements-truth source is now the runtime; the retained manifest-declaration path
is a harmless compatibility adapter, not a competing requirements system.

## Validation-boundary assessment
**PASS.** Model runtimes own scientific input compatibility only (Bremen shape via
frozen `validate_bremen_shape`; Aramina explicit target_side via the existing request
validator). Platform concerns were NOT migrated into runtimes: authorization, source
existence, job lookup, storage routing, and job identity remain in the
orchestrator/job handler; `_validate_aramina_source` (patient/H5 binding) stays where
it already executed inside the existing Aramina pipeline — position unchanged and
documented as PR0154 coupling, not newly moved. Bremen invalid input still fails
before any scientific work (regression suite green).

## Error compatibility
**PASS.** No public error code was renamed: Bremen envelopes byte-identical to
PR0152 (proven by the four `test_bremen_provider_preserves_*_envelope_from_runtime_
error` tests using injected runtimes), full `ARAMINA_*` code/stage/diagnostic
taxonomy propagates unchanged through `AraminaRuntime`
(`test_aramina_predict_preserves_workflow_error_taxonomy`). Contract error categories
carry constant safe reasons only; the safe-reason values equal the established
externals. Leak scan of the new code: no source paths, S3 keys, artifact paths, raw
exceptions, tracebacks, tokens or environment variables
(`test_requirements_payload_is_safe_and_serializable` and
`test_model_requirements_response_additive_and_safe` assert forbidden substrings;
`ModelRuntimeError` accepts only the fixed reason string). `ModelInput.container_path`
exists on the internal carrier only and is never serialized publicly.

## Registry/orchestrator assessment
**PASS.** `workflow_orchestrator.py` and `workflow_registry.py` are untouched by this
PR — model selection, routing, job lifecycle, source identity, auth and S3 discovery
are unchanged. The requirements API reuses `get_provider_for_model` rather than adding
a second routing path. Multi-model selection behavior re-verified green
(registry/multi-model/catalog/training-runtime-separation suites → 96 passed).

## Public API compatibility
**PASS.** Bremen `WorkflowResult.payload` keys byte-identical to PR0152 (diff-verified
projection rewrite is key-for-key identical). Aramina payload identical. Job API, auth,
report envelopes, frontend, PDF untouched. The only additions are (a) the additive,
sanitized `container_requirements.model_runtime` block on requirements responses when a
runtime is reachable, and (b) internal structured types (`ModelRequirements`,
`ModelValidation`, `RuntimePrediction`) that never become public envelopes by
themselves. Both are additive and backward compatible; existing clients see no change
on any existing field.

## Scientific deduplication assessment
**PASS.** One authoritative Bremen production science path
(`BremenRuntime` → `bremen_features`/`inference`, unchanged); one authoritative
Aramina production science path (the `workflow_aramina` pipeline functions +
`aramina_preprocessing` + `aramina_symmetry`, unchanged). Both runtimes are
composition adapters over these paths; no feature/scoring formula is duplicated.
`bremen/model_runtime.py` is the single common runtime abstraction (no duplicate
protocol found; `system_of_record.py`'s runtime_checkable protocol is the unrelated
RecordResolver). Production does not import from tests (grep → none).

## Security/privacy assessment
**PASS.** No new leak paths: contract types carry static safe values; runtime errors
are constant-category with fixed safe reasons; the requirements payload excludes
paths/checksums/tokens/internals (asserted by tests); providers redact nothing new
because nothing sensitive is newly produced. No real H5, patient data, credentials or
binaries added. The internal `ModelInput.container_path`/`patient_id` fields mirror
data that already flowed to the same pipeline functions pre-contract; exposure surface
is unchanged.

## PR0154 remaining coupling (explicitly identified, V1 boundary real)
1. `ModelInput.container_path` — Aramina artifact preprocessing consumes a
   platform-staged filesystem path; PR0154 should move to a platform-owned container
   abstraction.
2. `ModelInput.patient_id` — Aramina patient identity binding (`_validate_aramina_source`)
   still executes inside the model pipeline; belongs to the platform in PR0154.
3. `bremen_features.build_bremen_features` lazily imports
   `validate_canonical_measurement` from `bremen.api.xrd_normalization` (carried over
   from PR0152; unchanged).
4. Bremen model identity constants in `bremen_runtime.py` mirror frozen release
   evidence; PR0154 should source identity from the model package manifest.
Assessment: `BremenRuntime`'s scientific core (`run`/`score`/`build_features` +
`bremen_features`) is a concrete, platform-light unit (platform imports: the
decision-contract builder and the lazy canonical validation above); the V1 boundary is
real and the move to an inference-complete package in PR0154 is plausible without
major re-entanglement.

## Targeted tests (executed during this review)
- `python -m compileall -q src tests` → **exit 0**.
- `pytest -q tests/test_bremen_model_runtime_contract_v1.py` → **36 passed**.
- Bremen parity (PR0151+PR0152 suites + workflow + plugin) → **151 passed**.
- Aramina runtime/provider/scaffold → **282 passed**; extended Aramina/report/decision/
  catalog run → **365 passed**.
- Requirements + registry + multi-model + catalog-multi-model + training-runtime
  separation → **96 passed**.

## Full pytest
`pytest -q` → **4150 passed, 11 skipped, 0 xfailed** (39.50s, exit 0). Collection
reconciliation: 4161 collected = 4150 passed + 11 skipped; base + the 37 new tests
(36 contract + 1 parity wiring) accounts for the delta; no test removed or weakened
(the parity diff is purely additive).

## Changed-file Ruff
8 of 9 changed/new Python files → **All checks passed!**
`src/bremen/api/workflow_provider.py` → 1 × F401 (`dataclasses.field` imported but
unused, line 14). **Verified pre-existing**: the identical import line exists at HEAD
(`git show HEAD:…workflow_provider.py`) and Ruff reports the same single finding on
the HEAD version; this PR's diff does not touch that line and introduces **zero** new
findings. Reported separately per the task's pre-existing allowance; recommend
removing the unused import in routine cleanup.

## git diff --check
**exit 0** (no whitespace errors).

## Legacy searches
- `left_ms[0]` / `right_ms[0]` in `src/` (**.py**): **none**. `first_pair`: **none**.
- Workflow providers scanned for feature formulas, model-specific scaler math, direct
  estimator math, scientific threshold application: **none in either provider class**
  (classification table above).
- Production imports from tests: **none**.
- Duplicate common runtime abstractions: **none** (single `ModelRuntime` protocol;
  `system_of_record.py` protocol is the unrelated RecordResolver).
- Out-of-scope framework dependencies (MLflow/BentoML/Kerve-like): **none**.

## Risks / non-gating notes
1. Pre-existing F401 in `workflow_provider.py` (see Changed-file Ruff) — untouched
   line, verified identical at HEAD; not introduced by this PR.
2. PLAN listed a `src/bremen/bremen_features.py` "import-safe error base" change that
   proved unnecessary — the implementation changes that file not at all. Conservative
   deviation from the PLAN's expected-file list; no science impact.
3. `BremenProvider.__init__` now accepts an injected `runtime` and
   `_validate_model_internal` treats a runtime without `model_ready` as ready — this
   path exists for contract/fake runtimes in tests; production `BremenRuntime` always
   provides `model_ready`, and no production caller injects a runtime.
4. `ModelInputUnsupportedError` is defined and tested for category ownership but not
   yet raised by either runtime — reserved category, no behavior impact.
5. The additive `container_requirements.model_runtime` block appears only where a
   manifest is declared AND a runtime is reachable; consumers asserting exact dict
   equality on `container_requirements` would see the new key — no such consumer
   exists in the suite (all requirements tests green).
6. Aramina `on_features` is an intentional contract-compatibility no-op (no Aramina
   feature-stage boundary exists); no behavior added.
7. `AraminaRuntime` uses relative import `..model_runtime` from `bremen.api` —
   consistent with the module's existing relative-import style.

## FINAL VERDICT

**READY FOR COMMIT**

All required conditions hold: one real common runtime contract exists
(requirements/validation/prediction represented, dependency direction enforced);
`BremenRuntime` conforms with zero scientific change (PR0151/PR0152 parity green:
golden features, golden probability, 3+3, all-six participation, permutations,
raw-H5, invalid shapes); Aramina conforms via an adapter with byte-identical science
and green regression suites; both providers remain orchestration adapters with no
model-specific scientific computation; Model Requirements API is backward compatible
with an additive sanitized runtime-derived block; routing/model selection unchanged;
no public report/API break; no security/privacy regression; no out-of-scope framework
adoption; no duplicate active scientific implementations; full pytest (4150 passed,
11 skipped), changed-file Ruff (zero new findings; one verified pre-existing F401
reported separately) and `git diff --check` all pass.

Do not commit (review-only task).
