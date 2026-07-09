# PR 0052 — Plan: Matador Boundary Adapter Skeleton

## 1. Title / Branch / Objective

- **Title**: Matador Boundary Adapter Skeleton
- **Branch**: `0052-matador-boundary-adapter-skeleton`
- **Objective**: Define the Bremen system-of-record boundary contract through a typed module, an ADR, and static/synthetic tests. Matador is the source of record; the boundary makes this explicit. No real Matador integration, no schema changes, no runtime path changes.

---

## 2. Precondition Verification

```
$ git rev-parse --verify HEAD
6466314ca31666fd3a260b1f34685d927a213db0

$ git branch --show-current
0052-matador-boundary-adapter-skeleton

$ git status --short
(clean — no uncommitted changes)
```

Branch matches. Working tree clean.

---

## 3. Problem Summary

### Current state

Bremen supports two H5 input modes for prediction requests:

| Mode | Field | Current semantics | Source of record? |
|------|-------|------------------|-------------------|
| Local path | `h5_path` | Direct filesystem path | No — dev/test convenience only |
| S3 URI | `h5_uri` | S3 staging via `stage_h5_input()` | No — controlled staging, not system of record |

Both modes work. Both are tested. Both are documented in `docs/api_contract.md` and `docs/production_e2e_smoke.md`.

### The gap

1. **No typed boundary.** There is no explicit type, interface, or module that captures "this is a system-of-record reference." The existing `h5_path` and `h5_uri` strings are just strings — no semantic or type-level distinction.

2. **No documented seam.** A future Matador integration needs a clear seam where opaque platform references (`external_record_ref`, `system_of_record_ref`) are resolved into runtime staging inputs. Today, that seam does not exist.

3. **No boundary tests.** There are no tests that verify `h5_path` and `h5_uri` are NOT treated as system-of-record modes, or that a future resolver interface exists.

### What PR0052 does

- Adds a typed module (`src/bremen/api/system_of_record.py`) with a `SystemOfRecordRef` branded type, a `ResolvedInput` dataclass, a `RecordResolver` protocol, and an `UnconfiguredResolver` implementation.
- Adds an ADR (`docs/adr/0012-system-of-record-boundary.md`) documenting the boundary contract, the resolver protocol, and the Matador integration roadmap.
- Adds a test file (`tests/test_bremen_system_of_record_boundary.py`) with pure synthetic tests for all boundary types and resolver behaviors.
- Adds a static gate to the existing governance test file acknowledging the new boundary.
- Does NOT change the public prediction request schema (`PredictionRequest`). Does NOT change `validate_prediction_request()`. Does NOT change `app.py`, `h5_inputs.py`, `inference_handler.py`, or any existing runtime path.

---

## 4. Roadmap Alignment

1. **PR0052 follows PR0051.** ROADMAP.md "Next Execution Sequence" shows PR0050 → PR0051 → PR0052 → PR0053 → PR0054. PR0051 (config governance ADR/gates) has been merged (confirmed by PR0051 precommit-review.yml showing 624 passed tests and all governance gates implemented). PR0052 is the next scheduled item.

2. **PR0052 is Matador boundary or system-of-record adapter skeleton.** ROADMAP.md: "Contract only, no local path dependency, no raw patient data logging."

3. **PR0053 remains decision-support report or output wrapper.** ROADMAP.md: "Controlled output around prediction result. No diagnosis, no clinical validation claim."

4. **This plan does not start PR0053 work.** No report template, no output wrapper, no clinical formatting.

5. **FastAPI remains deferred.** No FastAPI, uvicorn, starlette, or ASGI references in this PR.

---

## 5. Boundary Contract Plan

### 5.1 Core types (`src/bremen/api/system_of_record.py`)

New module, pure Python, standard library only. No network, no credentials, no imports from `boto3`, `requests`, `httpx`, `matador`, `joblib`, `h5py`, or any ML library.

#### `SystemOfRecordRef` — branded opaque reference type

```python
from typing import NewType

SystemOfRecordRef = NewType("SystemOfRecordRef", str)
```

A `SystemOfRecordRef` is an opaque string owned by the source-of-record layer (Matador). It must:
- Contain no raw local filesystem paths (`/Users/`, `/tmp/`, `/home/`).
- Contain no raw patient identifiers (`Nova_376`).
- Contain no full S3 URIs (`s3://bucket/key.h5`).
- Contain no secrets, account IDs, or registry URLs.
- Be resolvable only by a `RecordResolver` implementation.

The type is a `NewType` for type-checking safety but remains a `str` at runtime for serialization compatibility.

#### `ResolvedInput` — result of resolving a system-of-record ref

```python
@dataclass(frozen=True)
class ResolvedInput:
    """Result of resolving a SystemOfRecordRef into a runtime staging input."""
    input_uri: str  # S3 URI or local path for staging
    checksum: str | None = None  # Optional sha256:<64hex>
    target_scan_ref: str | None = None  # Optional explicit target ref override
    control_scan_ref: str | None = None  # Optional explicit control ref override
    resolution_source: str = "unknown"  # e.g. "matador", "synthetic", "unconfigured"
```

This dataclass captures everything needed to feed into the existing `stage_h5_input()` pipeline. It is a pure data object — no methods, no network calls.

#### `RecordResolver` — protocol/interface

```python
class RecordResolver(Protocol):
    """Protocol for resolving a SystemOfRecordRef into a ResolvedInput."""

    def resolve(self, ref: SystemOfRecordRef) -> ResolvedInput:
        """Resolve a system-of-record reference.

        Parameters
        ----------
        ref : Opaque reference string owned by the source-of-record layer.

        Returns
        -------
        A ResolvedInput with the staging URI and optional metadata.

        Raises
        ------
        ResolutionError
            If the ref cannot be resolved (unrecognized, unavailable, 
            network error, permission denied).
        """
        ...
```

The protocol is defined using `typing.Protocol` (structural subtyping). It has no base class dependency. Implementations must provide `resolve()`. The protocol is import-safe: no network, no credentials, no `boto3`.

#### `UnconfiguredResolver` — default no-op resolver

```python
class UnconfiguredResolver:
    """Default resolver that always returns not-implemented/unconfigured.

    Used when no real record resolver (Matador, synthetic, etc.) has
    been configured. This is the production default until Matador
    integration is implemented.
    """

    def resolve(self, ref: SystemOfRecordRef) -> ResolvedInput:
        raise ResolutionNotConfiguredError(
            "System of record resolver is not configured. "
            "No Matador integration is active. "
            "Use h5_path or h5_uri for development and staging, "
            "or configure a real RecordResolver."
        )
```

The `UnconfiguredResolver` is the default implementation injected when no real resolver is available. It raises `ResolutionNotConfiguredError` on any `resolve()` call.

#### Exception hierarchy

```python
class ResolutionError(Exception):
    """Base exception for resolution failures."""

class ResolutionNotConfiguredError(ResolutionError):
    """Resolver is not configured (no-op default)."""

class ResolutionInvalidRefError(ResolutionError):
    """Ref is invalid (empty, malformed, contains forbidden patterns)."""
```

All exceptions carry safe messages only — no raw ref values, no identifiers.

#### Static validation helpers

```python
_SYSTEM_OF_RECORD_REF_FORBIDDEN_PATTERNS = frozenset({
    "/Users/", "/home/", "/tmp/",
    "s3://", "AKIA", "SECRET_ACCESS_KEY",
    "dkr.ecr",
})

def validate_system_of_record_ref(ref: SystemOfRecordRef) -> SystemOfRecordRef:
    """Validate a SystemOfRecordRef for safety.

    Raises ResolutionInvalidRefError if the ref contains forbidden
    patterns (local paths, S3 URIs, access keys, registry URLs).
    """
    ...
```

### 5.2 Design decisions

| Decision | Rationale |
|----------|-----------|
| `SystemOfRecordRef` is `NewType("SystemOfRecordRef", str)` | Type safety at dev time, runtime transparency. Does NOT change `PredictionRequest` schema. |
| No changes to `PredictionRequest` in this PR | Adding `source_record_ref` to the schema would require `validate_prediction_request()` changes, third mutually-exclusive branch, and test updates — without a real resolver. The schema change is deferred to the Matador integration PR. |
| `RecordResolver` is `typing.Protocol`, not ABC | Structural subtyping. No base class dependency. Any object with a `resolve()` method satisfying the signature is a valid resolver. |
| `UnconfiguredResolver` as default | Production safety. Without a configured resolver, any attempt to resolve a ref raises a clear error. |
| `ResolvedInput` is frozen dataclass | Immutable, serializable, hashable. Can be used as a dict key or passed through JSON for cross-process boundary. |
| Input validation uses constants, not runtime I/O | Pure Python string matching. No network calls. No regex runtime compilation. |
| All exceptions carry safe messages | No raw ref values, no identifiers, no credentials in exception text. Matches existing `model_state.py` error safety pattern. |

### 5.3 Existing input modes remain unchanged

| Mode | h5_path | h5_uri | source_record_ref (future) |
|------|---------|--------|---------------------------|
| Status | Unchanged — dev/test convenience | Unchanged — controlled staging | Not added yet — deferred to Matador integration PR |
| Validation | Existing `validate_prediction_request()` | Existing `validate_prediction_request()` | Will add third mutually-exclusive branch |
| In-band check | None needed | None needed | Will add `validate_system_of_record_ref()` |
| Source of record? | No — explicitly NOT source of record | No — explicitly NOT source of record | Yes — when implemented |

---

## 6. Request Contract Plan

### Decision: No schema change in PR0052

`PredictionRequest` and `validate_prediction_request()` remain unchanged. The `source_record_ref` / `system_of_record_ref` field is NOT added to the public API contract in this PR.

Reasons:
1. Without a real resolver, the field would always be rejected or return not-configured errors. This provides no value to API consumers and creates confusion.
2. Adding the field requires a third mutually-exclusive branch in `validate_prediction_request()`, which changes the existing request contract and requires existing test updates.
3. The boundary contract is adequately proven through the typed module (types, protocol, unconfigured resolver), the ADR, and the tests. The schema change is the last step, not the first.
4. The schema change is better scoped to a future PR that implements the first real resolver (synthetic test resolver or Matador integration stub).

### Future schema shape (documented in ADR, not implemented)

The ADR will document the planned future `PredictionRequest` shape:

```python
@dataclass
class PredictionRequest:
    target_scan_ref: str
    control_scan_ref: str
    h5_path: str | None = None       # dev/test — not source of record
    h5_uri: str | None = None         # S3 staging — not source of record
    source_record_ref: str | None = None  # Matador system of record — FUTURE
    h5_checksum: str | None = None
    request_id: str | None = None
```

Exactly one of `h5_path`, `h5_uri`, or `source_record_ref` must be provided. This is documented as the planned future contract but not implemented in PR0052.

---

## 7. File Change Plan

### 7.1 New files

| File | Purpose |
|------|---------|
| `src/bremen/api/system_of_record.py` | Typed boundary module: `SystemOfRecordRef`, `ResolvedInput`, `RecordResolver` protocol, `UnconfiguredResolver`, exception hierarchy, `validate_system_of_record_ref()` |
| `docs/adr/0012-system-of-record-boundary.md` | New ADR documenting the boundary contract, resolver protocol, typed ref contract, deferred scope, and Matador integration roadmap |
| `tests/test_bremen_system_of_record_boundary.py` | Static/synthetic tests for all boundary types and resolver behaviors |

### 7.2 Modified files

| File | Change type | Scope |
|------|-------------|-------|
| `tests/test_bremen_config_governance.py` | Modify — add one test class | Add `TestSystemOfRecordBoundaryGovernance` with 3–4 test methods verifying that the boundary module exists, does not import forbidden modules, and that no `source_record_ref` field has been added to `PredictionRequest` prematurely |
| `docs/api_contract.md` | Modify — add boundary section | Add "System of Record Boundary" section documenting `SystemOfRecordRef`, `ResolvedInput`, the resolver protocol, and that `h5_path`/`h5_uri` are explicitly NOT system-of-record modes. The existing request/response contracts remain unchanged. |

### 7.3 No changes

| File | Rationale |
|------|-----------|
| `src/bremen/api/schemas.py` | No schema change. `PredictionRequest` unchanged. |
| `src/bremen/api/app.py` | No routing change. `handle_submit_prediction()` unchanged. |
| `src/bremen/api/inference_handler.py` | No inference pipeline change. |
| `src/bremen/h5_inputs.py` | No staging change. |
| `src/bremen/api/preflight.py` | No preflight change. |
| `src/bremen/api/h5_layouts.py` | No layout adapter change. |
| `src/bremen/api/preprocessing_bridge.py` | No preprocessing change. |
| `tests/test_bremen_predictions.py` | No prediction test changes (no schema change). |
| `tests/test_bremen_h5_input_staging.py` | No staging test changes (no staging change). |
| `tests/test_bremen_h5_layouts.py` | No layout test changes. |
| `tests/test_bremen_production_smoke.py` | No smoke test changes (smoke uses `h5_uri` mode, which remains unchanged). |
| `docs/production_e2e_smoke.md` | No smoke doc changes (smoke uses `h5_uri` mode). |

---

## 8. ADR Plan

### 8.1 New ADR: `docs/adr/0012-system-of-record-boundary.md`

**Status**: Accepted (proposed in this PR)

**Structure**:

1. **Context** — Bremen currently supports `h5_path` and `h5_uri` input modes. Both are convenient for development and controlled staging, but neither represents a system-of-record boundary. Matador is the system of record for measurements and prediction results (Project Contract). A typed seam is needed before real Matador integration.

2. **System of record definition** — Matador owns patient data, measurement metadata, scan references, and clinical labels. Bremen consumes H5 containers and returns predictions. Matador provides the opaque references that Bremen resolves into staging inputs.

3. **Boundary contract** — Three-layer input hierarchy:
   - `h5_path` — Local filesystem convenience. NOT source of record. Safe only for development, CI, and opt-in real H5 smoke tests.
   - `h5_uri` — S3 staging convenience. NOT source of record. Safe for controlled staging, production smoke, and operator workflows. Does not imply Matador ownership.
   - `source_record_ref` (future) — Opaque Matador reference. IS source of record. Resolved through `RecordResolver` protocol. No local paths, no raw identifiers.

4. **Resolver protocol** — `RecordResolver` with single `resolve(SystemOfRecordRef) -> ResolvedInput` method. Default is `UnconfiguredResolver` which raises `ResolutionNotConfiguredError`. Future PRs add `MatadorResolver`, `SyntheticTestResolver`.

5. **Deferred scope** — The following are explicitly deferred:
   - Real Matador API calls, credentials, SDK, or network adapter.
   - `source_record_ref` field in `PredictionRequest` schema.
   - `validate_prediction_request()` third mutually-exclusive branch.
   - Database or backend persistence for ref-state mapping.

6. **Safety rules** — Same as Project Contract: no raw patient identifiers, no raw scan refs, no full S3 URIs, no secrets, no account IDs, no registry URLs in refs, errors, or logs.

7. **Non-goals** — Same as this plan's Section 13.

8. **Consequences** — The boundary module exists as a typed seam. All existing runtime code is unaffected. Future Matador PRs implement the resolver behind the seam.

### 8.2 Existing ADR changes

No existing ADRs need modification. ADR-0011's "Matador" references remain valid as-is. ADR-0003 (microservice API architecture) describes the async submit-poll pattern but does not constrain input modes — no conflict.

---

## 9. Test Plan

### 9.1 New test file: `tests/test_bremen_system_of_record_boundary.py`

All tests are synthetic/mocked. No AWS, Docker, Terraform, App Runner, network, real H5, real model artifact, real Matador, or credentials.

#### Class A: `TestSystemOfRecordRef` — typed ref safety

1. `test_ref_is_str_at_runtime` — `SystemOfRecordRef("abc-123")` is an instance of `str`.
2. `test_validate_ref_rejects_local_path` — `/Users/alice/data.h5` raises `ResolutionInvalidRefError`.
3. `test_validate_ref_rejects_full_s3_uri` — `s3://bucket/key.h5` raises `ResolutionInvalidRefError`.
4. `test_validate_ref_rejects_access_key` — Ref containing `AKIA` pattern raises `ResolutionInvalidRefError`.
5. `test_validate_ref_accepts_valid_opaque_ref` — `"matador://study/patient/scan"` passes validation.
6. `test_validate_ref_rejects_empty` — Empty string raises `ResolutionInvalidRefError`.

#### Class B: `TestResolvedInput` — resolved input dataclass

7. `test_resolved_input_has_required_fields` — `ResolvedInput(input_uri="s3://bucket/file.h5")` has `input_uri`, `checksum`, `target_scan_ref`, `control_scan_ref`, `resolution_source`.
8. `test_resolved_input_is_frozen` — Attempting to set an attribute raises `dataclass.FrozenInstanceError`.
9. `test_resolved_input_default_resolution_source` — Default `resolution_source` is `"unknown"`.
10. `test_resolved_input_carries_checksum` — `ResolvedInput(..., checksum="sha256:" + "a"*64)` preserves checksum.

#### Class C: `TestRecordResolverProtocol` — protocol structural typing

11. `test_any_object_with_resolve_is_resolver` — A class with `def resolve(self, ref): ...` satisfies the protocol (structural subtyping check via `isinstance(..., Protocol)` or `assert isinstance(obj, RecordResolver)`).
12. `test_resolver_protocol_has_resolve_method` — `hasattr(resolver, "resolve")` is True.

#### Class D: `TestUnconfiguredResolver` — default resolver behavior

13. `test_unconfigured_resolver_raises_not_configured` — `UnconfiguredResolver().resolve(SystemOfRecordRef("any"))` raises `ResolutionNotConfiguredError`.
14. `test_unconfigured_resolver_message_is_safe` — Error message does not contain the ref value.
15. `test_unconfigured_resolver_is_default` — `UnconfiguredResolver` can be instantiated without arguments.

#### Class E: `TestModuleAPISafety` — module boundary safety

16. `test_module_does_not_import_forbidden` — AST-check: `system_of_record.py` does not import `boto3`, `botocore`, `requests`, `httpx`, `matador`, `joblib`, `pickle`, `h5py`, `numpy`, `fastapi`, `uvicorn`, `starlette`.
17. `test_module_imports_successfully` — `import bremen.api.system_of_record` succeeds.
18. `test_no_network_imports` — AST-check: no `socket`, `http.client`, `urllib.request`.

#### Class F: `TestExistingModesAreNotSourceOfRecord` — static governance for existing modes

19. `test_h5_path_documented_as_not_source_of_record` — `docs/api_contract.md` explicitly states `h5_path` is NOT source of record.
20. `test_h5_uri_documented_as_not_source_of_record` — `docs/api_contract.md` explicitly states `h5_uri` is NOT source of record (or documents the three-layer hierarchy).

#### Class G: `TestPredictionRequestHasNoSourceRecordRef` — governance guard

21. `test_prediction_request_has_no_source_record_ref` — `PredictionRequest` does NOT have `source_record_ref` or `system_of_record_ref` attribute (governance guard against premature schema change).
22. `test_validate_prediction_request_not_changed` — `validate_prediction_request()` has exactly two input modes (`h5_path`, `h5_uri`), not three.

### 9.2 Existing test modifications

#### `tests/test_bremen_config_governance.py`

Add one class at end of file:

- `TestSystemOfRecordBoundaryGovernance` with 3–4 test methods:
  - `test_system_of_record_module_exists` — `src/bremen/api/system_of_record.py` exists.
  - `test_system_of_record_adt_ref_not_in_prediction_request` — `PredictionRequest` does not have `source_record_ref`.
  - `test_system_of_record_module_no_forbidden_imports` — AST check: module does not import `boto3`, `requests`, `matador`.
  - `test_system_of_record_adr_exists` — `docs/adr/0012-system-of-record-boundary.md` exists.

### 9.3 No changes to existing test files

The following test files are reviewed but not changed:
- `tests/test_bremen_predictions.py` — 12 test classes, all pass. No schema change means no test changes.
- `tests/test_bremen_h5_input_staging.py` — 5 test classes, all pass. No staging change.
- `tests/test_bremen_production_smoke.py` — 6 test classes, all pass. Smoke uses `h5_uri` mode exclusively.

---

## 10. Preserved Boundaries

1. No FastAPI — preserved.
2. No real Matador integration — preserved.
3. No Matador credentials or endpoints — preserved.
4. No DynamoDB/backend implementation — preserved.
5. No new deployment target — preserved.
6. No Docker changes — preserved.
7. No Terraform changes — preserved.
8. No dependency changes — preserved.
9. No training behavior changes — preserved.
10. No runtime model lifecycle changes — preserved.
11. No S3 model staging changes — preserved.
12. No S3 H5 input staging changes — preserved (except the optional governance test verifying the boundary).
13. No preprocessing changes — preserved.
14. No inference math changes — preserved.
15. No production smoke execution — preserved.
16. No clinical validation claims — preserved.
17. No prediction request schema changes — preserved (the `source_record_ref` field is deferred).
18. No changes to `validate_prediction_request()` — preserved.
19. No changes to `handle_submit_prediction()` — preserved.
20. No changes to `docs/production_e2e_smoke.md` — preserved.

---

## 11. Validation Plan

### 11.1 Implementation validation

```bash
python -m compileall src tests

python -m pytest -q tests/test_bremen_system_of_record_boundary.py -v
python -m pytest -q tests/test_bremen_config_governance.py -v
python -m pytest -q tests/test_bremen_predictions.py -v
python -m pytest -q tests/test_bremen_h5_input_staging.py -v
python -m pytest -q tests/test_bremen_production_smoke.py -v
python -m pytest -q
```

### 11.2 Safety validation

```bash
# 1. Verify only allowed files changed
git diff --name-only

# 2. Verify no forbidden files changed
git diff --name-only -- ROADMAP.md Dockerfile Dockerfile.training infra .github \
  requirements.txt pyproject.toml src/bremen/training || true

# 3. Verify no binary artifact changes
git diff --name-only | grep -E '\.(h5|hdf5|joblib|pkl|npy|npz|tfstate|tfstate\.backup)$' || true

# 4. Verify no FastAPI/uvicorn/starlette introduced
grep -R "FastAPI\|fastapi\|uvicorn\|starlette" -n src tests docs requirements.txt pyproject.toml || true

# 5. Verify no DynamoDB/boto3/botocore introduced in boundary module or tests
grep -R "DynamoDB\|boto3\|botocore" -n src tests docs requirements.txt pyproject.toml || true

# 6. Verify no Matador network/credentials/URLs introduced
grep -R "matador.*http\|http.*matador\|MATADOR_\|Matador.*token\|Matador.*URL" \
  -n src tests docs requirements.txt pyproject.toml || true

# 7. Verify no secrets/identifiers in new boundary files
grep -R "AKIA\|SECRET_ACCESS_KEY\|dkr.ecr\|Nova_\|s3://" \
  -n src/bremen/api/system_of_record.py \
  tests/test_bremen_system_of_record_boundary.py \
  docs/adr/0012-system-of-record-boundary.md \
  tests/test_bremen_config_governance.py \
  docs/api_contract.md || true

# 8. Verify ADR exists and has required sections
grep -c "## " docs/adr/0012-system-of-record-boundary.md
python -c "
with open('docs/adr/0012-system-of-record-boundary.md') as f:
    content = f.read()
checks = [
    'System of Record' in content,
    'Matador' in content,
    'h5_path' in content,
    'h5_uri' in content,
    'RecordResolver' in content or 'resolver' in content.lower(),
    'UnconfiguredResolver' in content or 'not configured' in content.lower(),
    'deferred' in content.lower() or 'not implemented' in content.lower(),
    'source_record_ref' in content or 'system_of_record_ref' in content,
]
for i, c in enumerate(checks):
    assert c, f'ADR content check {i} failed'
print(f'All {len(checks)} ADR content checks passed')
"
```

---

## 12. Non-Goals

1. No FastAPI.
2. No real Matador adapter.
3. No Matador API calls.
4. No Matador credentials.
5. No config backend.
6. No DynamoDB implementation.
7. No AWS calls.
8. No App Runner deployment.
9. No Docker or Terraform change.
10. No dependency change.
11. No runtime model loading change.
12. No model package format change.
13. No preprocessing or inference change.
14. No training behavior change.
15. No production smoke execution.
16. No clinical validation claims.
17. No PR0053 decision-support report/output wrapper.
18. No `source_record_ref` field in `PredictionRequest`.
19. No changes to `validate_prediction_request()`.
20. No changes to `handle_submit_prediction()`.
21. No real `MatadorResolver` implementation.
22. No `SyntheticTestResolver` that does anything beyond test-time protocol compliance.

---

## 13. Implementation Agent Assignment

**Agent**: coder

**Ordered task list**:
1. Read this PLAN.md and the required artifacts listed in the task prompt (already all read by the plan agent).
2. Create `src/bremen/api/system_of_record.py` — new module with types, protocol, resolver, exceptions, static validation.
3. Create `docs/adr/0012-system-of-record-boundary.md` — new ADR documenting the boundary contract.
4. Create `tests/test_bremen_system_of_record_boundary.py` — 7 test classes, ~22 test methods. All synthetic/static.
5. Modify `tests/test_bremen_config_governance.py` — add `TestSystemOfRecordBoundaryGovernance` class (3–4 tests).
6. Modify `docs/api_contract.md` — add "System of Record Boundary" section documenting the three-layer input hierarchy.
7. Run validation checklist (Section 11) and fix any failures.
8. Commit all changes. Verify no forbidden artifacts.

---

PLAN COMPLETE: yes

BLOCKERS: none

WARNINGS:
1. Safety validation step 7 (`grep -R ... s3://`) will match `s3://` in the boundary module's `validate_system_of_record_ref()` function (the FORBIDDEN_PATTERNS check) and in synthetic test data. These are safe — the grep output should be inspected and classified. If only safe references are found, report them as safe.
2. The `RecordResolver` protocol uses `typing.Protocol` which is available in Python 3.8+. The project already uses `typing` throughout. No import issues expected.
3. `SystemOfRecordRef` uses `NewType` which is a zero-runtime-overhead type annotation. It does not affect serialization or validation behavior. Runtime `isinstance(ref, SystemOfRecordRef)` will behave the same as `isinstance(ref, str)` — tests should use `isinstance(ref, str)` for runtime checks and the branded type only for type-checking.
4. The `docs/api_contract.md` change is a new section added at the end of the document describing the boundary. No existing contract sections are modified.

FILES CHANGED:
- `.project-memory/pr/0052-matador-boundary-adapter-skeleton/PLAN.md` — written
- `.project-memory/pr/0052-matador-boundary-adapter-skeleton/reviews/plan-review.yml` — future artifact

ROADMAP ALIGNMENT:
PR0052 confirmed as next after PR0051. PR0053 deferred. FastAPI deferred. No PR0053 work started.

PROBLEM SUMMARY:
Current Bremen supports two input modes (h5_path, h5_uri) but has no typed system-of-record boundary. Matador is the source of record. A typed seam (types, protocol, default resolver) must exist before real Matador integration. No schema or runtime path changes in PR0052.

BOUNDARY CONTRACT PLAN:
Core types: SystemOfRecordRef (NewType), ResolvedInput (frozen dataclass with input_uri/checksum/refs/resolution_source), RecordResolver (Protocol with resolve() method), UnconfiguredResolver (raises ResolutionNotConfiguredError). Exception hierarchy: ResolutionError → ResolutionNotConfiguredError, ResolutionInvalidRefError. Static validation: validate_system_of_record_ref() checks forbidden patterns. All types are pure Python standard library — no network, no credentials, no imports from boto3/requests/Matador.

REQUEST CONTRACT PLAN:
Decision: no schema change in PR0052. PredictionRequest and validate_prediction_request() remain unchanged. The source_record_ref field is deferred to the Matador integration PR. The ADR documents the planned future schema shape.

FILE CHANGE PLAN:
3 new files: boundary module (src/bremen/api/system_of_record.py), ADR-0012, boundary test file (22 tests). 2 modified files: governance test (+1 class, 3–4 tests), api_contract.md (+1 section). No changes to 7 existing runtime modules, 3 existing test files, or smoke/production docs.

ADR PLAN:
ADR-0012 documents the three-layer input hierarchy (h5_path → h5_uri → source_record_ref), the resolver protocol, the safety rules, the deferred scope, and the Matador integration roadmap. No existing ADRs modified.

TEST PLAN:
7 test classes (A–G), 22 test methods. Tests cover: typed ref validation (6), resolved input dataclass (4), protocol structural typing (2), unconfigured resolver behavior (3), module import safety (3), existing modes governance (2), premature schema change guard (2). All synthetic/static. No AWS, Docker, Terraform, network, real artifacts, or credentials.

PRESERVED BOUNDARIES:
All 20 boundaries preserved. No schema change. No runtime path change. No Matador implementation. No dependencies. No FastAPI.

VALIDATION PLAN:
Compileall + 5 test suite commands + full suite + 8 safety/diff/grep scans + ADR content verification script.

NON-GOALS:
22 non-goal categories listed. Key: no schema change, no Matador implementation, no changes to existing runtime code, no PR0053 work.

---

Implementation agent: coder
