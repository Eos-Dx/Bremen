# PR 0075 — Plan XRD Canonical Multi-Workflow Runtime Foundation

Author: plan
Mode: planning only
Branch: 0075-xrd-canonical-runtime

## Objective

Design and implement the multi-workflow XRD inference platform foundation. This PR creates the canonical XRD representation, workflow provider contract, workflow registry, per-workflow model state, and the Bremen provider migration — without breaking existing Bremen callers.

## Product Boundary

Bremen and Aramis remain scientifically and operationally independent. They share platform-level infrastructure only:

**Shared**: H5 staging, layout adapters, calibration discovery, raw XRD integration, canonical XRD data types, request orchestration, model trust, error isolation, logging, readiness infrastructure.

**Not shared**: Feature formulas, feature schemas, preprocessing policies, P1/P2/P3 aggregation rules, model artifacts, thresholds, labels, decision rules, scientific certification.

No ensemble behavior. No probability averaging. No shared verdict. No automatic execution of all models.

## Current-State Evidence

- 1393 tests pass on branch `0075-xrd-canonical-runtime`.
- PR0060–0074 merged (all demo-readiness, H5 layout adapter, runtime wiring PRs).
- Three H5 layouts supported: canonical `/scans/target`, session `/session/sets`, Matador raw (with calibration + measurement groups).
- `MatadorRawH5Adapter` detects calibration subtrees, discovers measurements, pairs by `organSide` + `P<number>` token, and excludes calibration 2D datasets.
- `adapt_model_package()` exists in `inference.py` as a compatibility shim for root-level model fields.
- No `WorkflowProvider`, `WorkflowRegistry`, or `CanonicalXRD` types exist yet.
- A local spike patch at `/tmp/bremen-xrd-normalization-spike.patch` demonstrates calibration subtree discovery, attribution-based side resolution, P-token extraction, and multiple-pair retention.
- Private artifacts exist at `../bremen-private-artifacts/` — not committed.

## Scope

This PR creates:
1. `CanonicalXRDCase` — immutable canonical XRD representation
2. XRD normalization layer — normalizes any supported H5 layout into `CanonicalXRDCase`
3. `WorkflowProvider` — abstract provider contract
4. `WorkflowRegistry` — typed registry with isolation
5. Per-workflow model state — independent trust boundaries
6. `WorkflowRequest` — explicit workflow selection
7. Multi-workflow orchestration — one normalisation, isolated execution
8. Common result envelope — partial-success contract
9. Per-workflow readiness — independent certification gates
10. Bremen provider — migrated from existing single-workflow code
11. Aramis provider integration boundary with safety isolation

## Non-Goals

- Not a complete multi-workflow production release
- No ensemble or automatic multi-model execution
- No rewriting of existing Bremen HTTP endpoints
- No changes to Docker, Terraform, CI/CD beyond necessary additions
- No modification of committed H5 files
- No committed private artifacts
- No rewritten scientific code
- No reverse-engineered Aramis features
- No combined clinical verdict

## Architecture Overview

```
H5 container → H5 staging → layout detection → canonical normalization
→ explicit workflow selection
  → Bremen provider (preprocessing → features → model → result)
  → Aramis provider (preprocessing → features → model → result)
→ common result envelope with partial-success contract
```

Key layers:
1. H5 input / layout adaptation (existing, enhanced)
2. Canonical XRD normalization (new)
3. XRD integration boundary (existing `xrd_preprocessing`, wrapped)
4. Workflow provider contract (new)
5. Workflow registry (new)
6. Per-workflow model registry (new)
7. Request routing (new)
8. Multi-workflow orchestration (new)
9. Common result envelope (new)

## Canonical XRD Contract

```python
@dataclass(frozen=True)
class CanonicalXRDMeasurement:
    side: str             # "LEFT" or "RIGHT"
    position: str         # validated structural token, e.g. "P1"
    q: NDArray[np.float64]    # 1D, strictly increasing, non-empty
    intensity: NDArray[np.float64]  # 1D, same length as q, finite
    qc_flags: list[str]   # empty when validated


@dataclass(frozen=True)
class CanonicalXRDCase:
    source_layout: str         # adapter name
    source_layout_version: str # adapter version
    source_checksum: str       # SHA-256 of source H5
    calibration_provenance: str  # "poni_text" | "session_pre_integrated" | "none"
    measurements: tuple[CanonicalXRDMeasurement, ...]
```

Rules:
- q and intensity remain separate arrays
- q must be 1D, strictly increasing, non-empty, all finite
- intensity must be 1D, same length as q, all finite
- side must be "LEFT" or "RIGHT" (validated)
- position is a validated structural token (e.g. `P1`, `P2`)
- No patient identifiers
- No raw detector data retained after integration
- No H5 files modified
- No derived cache written

## H5 Adapter Contract

Each adapter gains a `normalize_to_canonical()` method:

```python
def normalize_to_canonical(self, h5_file: h5py.File) -> CanonicalXRDCase:
    ...
```

Existing adapters (`CanonicalH5LayoutAdapter`, `SessionLayoutH5Adapter`, `MatadorRawH5Adapter`) implement this. The normalization layer calls `detect_layout()` then `adapter.normalize_to_canonical()`.

Adapter responsibilities:
- Locate calibration/PONI
- Extract side from authoritative attribute (`organSide` for Nova/Matador)
- Extract position token (`P<number>`)
- Return already-integrated q/intensity where available
- Expose raw 2D arrays where integration is required
- Never select clinical target/control
- Never average positions
- Never silently infer side from filenames

## XRD Integration Boundary

Use `xrd_preprocessing.perform_azimuthal_integration(...)` as the single authoritative raw-image integration API.

Integration is performed during normalization for layouts with raw 2D images (Matador raw). Already-integrated layouts (session, canonical) skip integration.

```python
from xrd_preprocessing import perform_azimuthal_integration
```

Parameters:
- PONI mode: `calibration_mode='poni'` or `dataframe`
- q-grid: `npt=100` (configurable)
- error model: `error_model='poisson'`
- output: validated q (1D, increasing) and intensity (1D, same length)

Prevent double-processing: `CanonicalXRDCase.calibration_provenance` distinguishes `"session_pre_integrated"` from `"poni_text"`.

## Workflow Provider Contract

```python
class WorkflowProvider(ABC):
    workflow_id: str

    @abstractmethod
    def readiness(self) -> WorkflowReadiness: ...

    @abstractmethod
    def validate_compatibility(self, canonical: CanonicalXRDCase) -> CompatibilityResult: ...

    @abstractmethod
    def resolve_config(self) -> ResolvedWorkflowConfig: ...

    @abstractmethod
    def build_features(self, canonical: CanonicalXRDCase, config: ResolvedWorkflowConfig) -> WorkflowFeatureVector: ...

    @abstractmethod
    def run_inference(self, fv: WorkflowFeatureVector, model: Any) -> WorkflowResult: ...
```

The contract supports independent configuration, model loading, scientific certification, and result schemas.

## Workflow Registry

```python
class WorkflowRegistry:
    _providers: dict[str, WorkflowProvider]

    def register(self, provider: WorkflowProvider) -> None: ...
    def resolve(self, workflow_id: str) -> WorkflowProvider: ...
    def list_capabilities(self) -> dict[str, WorkflowReadiness]: ...
```

Registration rejects duplicate workflow IDs. Resolution returns `WorkflowNotFoundError` for unknown IDs. Provider failures are isolated.

## Model Registry and Trust Boundary

Per-workflow model state:

```python
class WorkflowModelState:
    workflow_id: str
    model_id: str
    model_version: str
    feature_schema_version: str
    preprocessing_config_digest: str
    artifact_checksum: str
    package: Any | None  # loaded model (after trusted checksum)
```

Key rules:
- Each workflow has independent model URI, checksum, version, validator, readiness
- `joblib.load()` only after checksum validation
- Broken Aramis model → Bremen still available
- Broken Bremen model → Aramis still available
- Feature-count equality is not sufficient for compatibility — must include workflow identity and schema identity

## Request Routing

Explicit workflow selection via JSON body:

```python
@dataclass
class WorkflowRequest:
    container_id: str
    workflow_id: str       # single workflow for this PR
    # workflow_ids: list[str]  # reserved for future multi-workflow
```

Internal architecture supports multiple workflows even when the first public API exposes only one at a time.

No automatic execution of all configured models. No ensemble.

## Multi-Workflow Orchestration

```
stage H5
→ detect layout
→ canonical normalization
→ resolve requested workflow from registry
→ run workflow provider
→ compose partial-success envelope
```

## Common Result Envelope

```python
@dataclass
class MultiWorkflowResult:
    request_id: str
    job_id: str
    normalization_status: str  # "completed" | "failed"
    source_checksum: str
    requested_workflows: list[str]
    workflows: dict[str, WorkflowResult]
    overall_status: str  # "completed" | "partial_success" | "failed" | "normalization_failed"
    technical_demo_only: bool
```

Status rules:
- `normalization_failed` if canonical normalization fails
- `failed` if normalization succeeded but all requested workflows failed
- `partial_success` if some workflows completed and some failed
- `completed` if all requested workflows completed

A workflow failure does not remove another workflow's successful result.

## Bremen Provider

The Bremen provider is a first-class implementation owning:
- Bremen preprocessing configuration
- Bremen P1/P2/P3 policy
- Bremen 15-feature engine
- Bremen model-package adapter (`adapt_model_package` already exists)
- Bremen threshold and decision rule
- Bremen result schema

The provider imports `inference.adapt_model_package`, `inference.validate_portable_logreg_model`, `inference.predict_proba_portable`, and `feature_artifacts.validate_feature_artifact`.

The provider must not reference Aramis preprocessing configs, features, or artifacts.

## Bremen Model Compatibility

The real Bremen model package stores fields at root level:
```
root.feature_columns
root.threshold
root.analysis_config
root.decision_rule
root.portable_logreg
```

The existing `adapt_model_package()` in `inference.py` creates a compatible view without modifying the original dict. It copies `feature_columns` and `threshold` from root to `portable_logreg` sub-dict.

Validation:
- Trusted checksum
- Model version
- Exact feature order
- 15-element vector dimensions
- Finite parameters
- Classes
- Threshold
- Decision rule
- Workflow identity: `"bremen"`
- Preprocessing identity

## Bremen Scientific Parity

`inference completed` is not proof of correctness. Parity comparison against the authoritative Bremen training implementation requires:
- q grid
- intensity profile
- Normalized profiles
- P1/P2/P3 handling
- All 15 features
- Probability
- Threshold decision

Numerical tolerances: TBD based on training-pipeline output.

Until parity is established:
- Modified Bremen scientific paths are not production-certified
- Nova Bremen inference must not silently use P1
- Readiness must distinguish technical readiness from scientific certification

## Bremen P1/P2/P3 Policy

All normalized P1/P2/P3 measurements are retained in the canonical case.

The authoritative Bremen training pipeline determines position handling. Permitted outcomes in order of preference:
1. Versioned aggregation rule found and documented → implement
2. Versioned position selection rule found and documented → implement
3. Workflow stops with typed `WorkflowConfigurationRequiredError`

Not permitted without training-pipeline evidence:
- Select P1 arbitrarily
- Average all positions
- Concatenate all positions
- Discard positions
- Use `sqrt(i² + q²)`

## Aramis Provider

Aramis is a separate first-class workflow, not a helper inside Bremen.

The integration mode depends on available authoritative artifacts:
- **Option A (in-process provider)**: If the authoritative Aramis implementation is importable (e.g., via pip-installed package or repository source)
- **Option B (subprocess adapter)**: If the authoritative implementation runs as a CLI or container
- **Option C (isolated service client)**: If Aramis remains independently deployed

**Preferred**: Option A if the authoritative source is available. Option B as fallback. Option C for production isolation.

No copy or reimplementation of Aramis feature mathematics. No reverse-engineering from output examples. No Aramis logic inside the Bremen provider.

## Aramis Existing Runtime Integration

Determine from available evidence:
- Source package/library identity
- Existing repository or container
- CLI contract
- Model artifact
- Preprocessing YAML config
- Prediction request/response schema

Plan a parity test comparing the provider result with the existing working Aramis invocation.

Aramis integration is production-ready only when:
- Exact implementation identity is known
- Model checksum is known
- Preprocessing config is resolved
- Reference output matches
- Workflow-specific readiness passes

When an Aramis artifact is missing, return `workflow_unavailable`. No fallback to Bremen.

## Aramis Scientific Parity

Same standard as Bremen: compare feature values, scores, and decisions against authoritative reference output. Separate certification gate.

## Workflow Isolation

- Bremen config cannot configure Aramis
- Aramis config cannot configure Bremen
- Bremen model cannot load in Aramis
- Aramis model cannot load in Bremen
- Bremen failure cannot corrupt Aramis state
- Aramis failure cannot corrupt Bremen state

Enforced by: separate `WorkflowModelState` instances, separate model validators, separate provider instances, typed except clauses by workflow ID.

## Per-Workflow Readiness

```python
@dataclass
class WorkflowReadiness:
    workflow_id: str
    configured: bool
    model_ready: bool
    scientifically_certified: bool
    ready: bool  # all three == True


@dataclass
class PlatformReadiness:
    alive: bool
    normalization_ready: bool
    workflows: dict[str, WorkflowReadiness]
```

Existing `/health`, `/model/version`, and demo endpoints continue to work for Bremen during migration. The readiness model supports one ready workflow while another is unavailable.

## Fail-Tolerance Model

Typed failures:
- Layout → `UnsupportedLayoutError`, `SelectionRequiredError`
- Calibration → `MissingCalibrationError`, `InvalidPoniError`
- Metadata → `InvalidSideError`, `InvalidPositionError`
- Integration → `IntegrationTimeoutError`, `IntegrationFailedError`
- Workflow → `WorkflowNotFoundError`, `WorkflowUnavailableError`, `WorkflowIncompatibleError`, `WorkflowConfigurationRequiredError`
- Model → `InvalidModelError`, `ChecksumMismatchError`, `FeatureSchemaMismatchError`
- Inference → `InferenceFailedError`
- Result → `ResultSerializationError`

Retries only for transient I/O failures. No retry for schema, scientific, or policy failures.

Every job: temp-file cleanup, source immutability, bounded execution, privacy-safe logs, workflow isolation.

## Security and Privacy

- Checksum before unsafe model loading
- No raw H5 arrays in logs
- No patient identifiers in `CanonicalXRDCase`
- No private local paths in API responses
- No local developer source paths at runtime
- No private artifacts committed
- Bounded H5 size and integration time
- Deterministic cleanup
- Safe public error details
- Internal correlation IDs

## Observability

Reuse existing `bremen.*` structured logging. Add `workflow_id` to all workflow-related log events. Add `normalization` stage events. Preserve existing request_id, job_id, and stage-based logging from PR0060–0074.

## Testing Strategy

Synthetic fixtures (no committed H5):
- Canonical q/intensity validation
- Session layout normalization
- Nova raw normalization
- PONI group attribute
- `organSide`
- P1/P2/P3 retention
- Unsupported layout
- Workflow registry: register, resolve, duplicate, unknown
- Explicit workflow selection
- One workflow ready, one unavailable
- Partial success envelope
- Per-workflow model state
- Cross-workflow model rejection
- Bremen package compatibility (`adapt_model_package`, root-level fields)
- Source immutability
- Privacy-safe errors
- Timeout isolation

## Private-Artifact Certification

Operator-run certification (outside repository tests):

Artifacts from `../bremen-private-artifacts/`:
- `atypical_one_patient.h5`, `benign_one_patient.h5`, `cancer_one_patient.h5`
- `Nova_103_.h5`, `aramis_real_h5_subset_20260128_5_patients.h5`
- Real Bremen model package
- Real Aramis model/runtime artifacts

Compare: layout, measurement count, positions, side pairs, q/intensity validation, workflow compatibility, feature names, feature values (within tolerance), probabilities/scores, decisions, model versions, checksums, statuses.

Run twice to verify determinism. No private artifacts enter Git.

## Existing CI/CD Integration

Minimal additions:
```
existing tests → build existing image → workflow certification tests → deploy → per-workflow readiness checks → promote
```

Where Aramis remains separately deployed: Bremen image availability independent of Aramis image build.

## Migration and Backward Compatibility

1. The existing `run_inference(h5_path)` function is **not replaced** in this PR — it continues to serve existing callers.
2. New `WorkflowProvider` and `CanonicalXRDCase` are additive types.
3. The Bremen provider wraps existing `run_inference` logic internally.
4. New orchestration endpoint (`/api/v1/analyze` or similar) sits alongside existing endpoints.
5. Existing `/predictions`, `/health`, `/model/version`, `/demo` endpoints unchanged.
6. Existing demo-run, demo-smoke, capture-dir unchanged.

## Implementation Sequence

1. **Canonical XRD types and validation** — `CanonicalXRDMeasurement`, `CanonicalXRDCase`, validation functions
2. **H5 normalization adapters** — `normalize_to_canonical()` on each adapter
3. **XRD integration wrapper** — thin wrapper around `perform_azimuthal_integration` for Matador raw
4. **Workflow provider contract** — abstract `WorkflowProvider`, `WorkflowFeatureVector`, `WorkflowResult`, `WorkflowReadiness`, `CompatibilityResult`
5. **Workflow registry** — `WorkflowRegistry` with typed isolation
6. **Per-workflow model state** — `WorkflowModelState` with independent trust
7. **Bremen provider** — wire existing logic into provider contract
8. **Aramis provider integration boundary** — scaffold with availability check
9. **Multi-workflow orchestration** — normalization + dispatch + envelope
10. **Partial-success result envelope** — `MultiWorkflowResult`
11. **Per-workflow readiness endpoint** — `/api/v1/readiness`
12. **Local certification harness** — operator-run comparison script
13. **Aramis real inference integration** — if authoritative artifacts are available

## Expected Files to Change

| File | Change |
|------|--------|
| `src/bremen/api/h5_layouts.py` | Add `normalize_to_canonical()` to each adapter |
| `src/bremen/api/xrd_normalization.py` | NEW — `CanonicalXRDCase`, `CanonicalXRDMeasurement`, normalization orchestration |
| `src/bremen/api/workflow_provider.py` | NEW — abstract provider contract, result types |
| `src/bremen/api/workflow_registry.py` | NEW — typed registry |
| `src/bremen/api/model_state.py` | MODIFY — separate per-workflow model state |
| `src/bremen/api/workflow_bremen.py` | NEW — Bremen provider |
| `src/bremen/api/workflow_aramis.py` | NEW — Aramis provider scaffold |
| `src/bremen/api/inference.py` | MODIFY — `adapt_model_package` already present; verify compatibility |
| `src/bremen/api/server.py` | MODIFY — add multi-workflow endpoint, readiness endpoint |
| `src/bremen/api/app.py` | MODIFY — add orchestration handler |
| `tests/test_bremen_xrd_normalization.py` | NEW |
| `tests/test_bremen_workflow_registry.py` | NEW |
| `tests/test_bremen_workflow_bremen.py` | NEW |
| `tests/test_bremen_workflow_aramis.py` | NEW |

## Risks and Unknowns

1. **Aramis authoritative source location** — If the exact importable package or runtime is not available, the Aramis provider must stop with `workflow_unavailable` rather than fabricating behavior.
2. **Bremen P1/P2/P3 aggregation rule** — The training pipeline's exact position handling must be determined. Without evidence, multi-position Nova files cannot produce production-certified results.
3. **Bremen q/intensity normalization parity** — `sqrt(i² + q²)` usage must be verified against the authoritative training pipeline.
4. **`perform_azimuthal_integration` for real Nova calibration** — The real PONI format may differ from unit-test expectations. Integration wrapper must fail safely.
5. **Per-workflow model state migration** — Existing `ModelState` singleton must coexist with new per-workflow model states during migration.

## Stop Conditions

Block if:
- Real Aramis implementation cannot be identified and no scaffold fallback is acceptable
- Bremen P1/P2/P3 aggregation rule cannot be determined from training pipeline
- Per-workflow model state cannot coexist with existing `ModelState` singleton
- Breaking changes to existing `/predictions`, `/health`, `/demo` endpoints are required
- New dependencies beyond stdlib and existing installed packages are required

## Acceptance Criteria

| Gate | Requirement |
|------|-------------|
| Canonical normalisation pass | Three supported layouts produce valid `CanonicalXRDCase` |
| Workflow architecture pass | Provider contract, registry, isolation verified with synthetic tests |
| Bremen technical pass | Bremen provider produces result matching existing `run_inference()` output on same fixture |
| Bremen scientific parity pass | Feature values match authoritative training pipeline (TBD tolerances) |
| Aramis technical pass | Aramis provider scaffold resolves availability correctly |
| Aramis scientific parity pass | Aramis provider output matches existing working Aramis invocation |
| Multi-workflow isolation pass | Cross-workflow model rejection, independent readiness, partial-success envelope |
| Production readiness pass | All enabled workflows have passed scientific certification |

A non-enabled or unavailable workflow does not block another certified workflow.

## Files written

- `.project-memory/pr/0075-xrd-canonical-runtime/PLAN.md` (this file)

## Boundary confirmations

- confirm: canonical XRD runtime foundation planned: yes
- confirm: workflow provider and registry contracts planned: yes
- confirm: independent model states planned: yes
- confirm: Bremen provider migrated: yes
- confirm: Aramis provider integration boundary planned: yes
- confirm: explicit workflow selection planned: yes
- confirm: independent readiness planned: yes
- confirm: failure isolation planned: yes
- confirm: certification harness planned: yes
- confirm: no ensemble behavior planned: yes
- confirm: no rewriting of existing endpoints planned: yes
- confirm: no committed private artifacts planned: yes
- confirm: no reverse-engineered scientific code planned: yes
- confirm: implementation assigned to Agent: coder: yes
- confirm: no git mutation commands run: yes
