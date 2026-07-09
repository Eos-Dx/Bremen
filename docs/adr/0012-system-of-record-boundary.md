# ADR-0012: System-of-Record Boundary

**Status**: Decided (PR0052)

**Gates**: G-SOR-1 (system-of-record boundary), G-SOR-2 (Matador integration timeline)

---

## Context

Bremen currently supports two H5 input modes:

- **`h5_path`** — Direct local filesystem path. Used for development,
  offline testing, and synthetic smoke tests.
- **`h5_uri`** — S3 URI with optional checksum. Used for staging/CI and
  App Runner proving path with monkeypatched or real S3 staging.

Neither mode represents long-term source-of-record ownership. Both are
convenience/staging modes that bypass the platform system of record
(Matador). As Bremen moves toward production deployment, H5 containers
must be resolved through a platform system of record that owns:

- Patient identity and metadata.
- Scan ref lifecycle (target vs. control selection).
- H5 container location and access credentials.
- Audit trail for data provenance.

PR0052 introduced a typed boundary skeleton for this integration.
It does not implement Matador API calls, credentials, or network adapters.

---

## Decision

1. **Matador is the source of record.** All future patient/scan/H5
   container resolution must go through the Matador system-of-record
   adapter. `h5_path` and `h5_uri` are explicitly not source-of-record
   ownership modes.

2. **PR0052 introduced boundary only.** The module
   `src/bremen/system_of_record.py` defines:
   - `ExternalRecordRef` — typed opaque ref with validation.
   - `ResolvedInput` — resolved H5 source with refs and checksum.
   - `RecordResolver` — protocol for resolver implementations.
   - `UnconfiguredRecordResolver` — default that raises safe error.
   - Safe error hierarchy (`ResolutionError`,
     `ResolutionNotConfiguredError`, `RefValidationError`).

3. **No request schema change in PR0052.** The `PredictionRequest` schema
   does not add a `source_record_ref` field. Current `h5_path`/`h5_uri`
   mode remains the only request input mechanism.

4. **No router change in PR0052.** `handle_submit_prediction` in `app.py`
   was not modified. The boundary is a typed scaffold, not a live code path.

5. **Future Matador resolver** must implement `RecordResolver` protocol
   and be wired into the request path. This is tracked as future work
   (PR0052+ or separate Matador integration PR).

---

## Boundary Contract

### System-of-record refs

- System-of-record refs are opaque strings (`ExternalRecordRef`).
- Ref validation rejects empty refs, local absolute paths (`/` prefix),
  full S3 URIs (`s3://` prefix), and obvious raw patient identifiers
  (`Nova_` prefix).
- Ref validation is a static gate — no network, no database.

### Resolved input

- `ResolvedInput` is a dataclass with exactly one of `h5_uri` or `h5_path`,
  plus `target_scan_ref`, `control_scan_ref`, and optional `h5_checksum`.
- Exactly one H5 source must be present (mutual exclusivity enforced).

### Resolver protocol

- `RecordResolver` is a `Protocol` class with a `resolve()` method.
- Any implementation can be tested via dependency injection.
- The default implementation (`UnconfiguredRecordResolver`) always raises
  `ResolutionNotConfiguredError` — a safe message with no raw refs.

### Safe errors

- All resolution errors must be subclasses of `ResolutionError`.
- Error messages must not include raw external refs, full S3 URIs, or
  local machine paths.
- `ResolutionNotConfiguredError` tells operators to use `h5_path`/`h5_uri`
  directly or configure the Matador resolver.

---

## Current Request Modes

| Mode | Description | Status in PR0052 |
|---|---|---|
| `h5_path` | Direct filesystem path | **Unchanged** — dev/test convenience |
| `h5_uri` | S3 URI with staging | **Unchanged** — staging/smoke mode |
| Source-of-record ref | `ExternalRecordRef` → `RecordResolver` | **Scaffold only** — not wired to request path |

All existing tests, runtime behavior, and API contract endpoints remain
unchanged. `h5_path` and `h5_uri` continue to work exactly as before.

---

## Future Matador Resolver

A future Matador adapter (outside PR0052 scope) must:

1. Implement `RecordResolver` protocol.
2. Accept a configured Matador client (injected, not constructed locally).
3. Resolve `ExternalRecordRef` to `ResolvedInput` with:
   - Staged H5 path or S3 URI.
   - Verified target/control scan refs.
   - Optional checksum for integrity verification.
4. Raise safe `ResolutionError` on failure (no raw refs in error messages).

The adapter must not:
- Import `requests`, `httpx`, `aiohttp`, or any network client at module
  level.
- Store Matador credentials, URLs, or tokens as module constants.
- Log raw refs or patient identifiers.

---

## Safety Rules

1. No full S3 URIs, account IDs, registry URLs, or access keys in
   boundary module or ADR.
2. No raw patient identifiers (`Nova_` patterns) in boundary module or
   ADR.
3. No local machine absolute paths (`/Users/`, `/home/`) in boundary
   module, tests, or ADR.
4. Error messages must never include raw external refs.
5. `UnconfiguredRecordResolver` error message tells operators what to do
   without leaking implementation details.
6. All resolution errors are typed and safe by default.

---

## Non-Goals

1. No FastAPI.
2. No real Matador adapter.
3. No Matador API calls, credentials, tokens, URLs, or network adapters.
4. No DynamoDB or backend persistence.
5. No new dependencies.
6. No change to `PredictionRequest` schema.
7. No change to `app.py` routing or `handle_submit_prediction`.
8. No change to S3 model staging or H5 input staging behavior.
9. No preprocessing or inference changes.
10. No training changes.
11. No Docker, Terraform, or CI changes.
12. No PR0053 decision-support report wrapper.

---

## Consequences

### Positive

1. Future Matador integration has a clear typed boundary with validated
   refs, safe errors, and a documented protocol.
2. Current `h5_path`/`h5_uri` behavior is completely undisturbed.
3. Static ref validation catches invalid refs before they reach any
   future adapter.
4. The boundary is testable via synthetic in-memory resolver without
   network or Matador credentials.
5. The `UnconfiguredRecordResolver` provides a safe default that
   prevents accidental silent fallback to unowned resolution.

### Negative

1. The boundary is not wired into the request path yet. Operators cannot
   use source-of-record refs in PR0052 — they must continue using
   `h5_path`/`h5_uri`.
2. The Matador resolver implementation effort is deferred to a future PR.
3. Static ref validation is a partial safety measure — runtime ref
   validation (e.g., ref matches a real Matador record) is not possible
   without a live resolver.

### Mitigations

- The boundary module includes detailed docstrings explaining the
  integration path.
- ADR-0012 documents the contract so the future Matador PR has a clear
  specification.
- Tests verify that the boundary is importable, all validations work,
  and no network dependencies leak through.
