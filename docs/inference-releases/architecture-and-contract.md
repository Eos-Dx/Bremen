# Architecture and normative contracts

Status: target design, not a description of an implemented release loader. MUST denotes a gate for this roadmap.

## Ownership and request flow

The platform authenticates a request, resolves its existing model ID to a pinned release digest, obtains authorized source files, performs source/patient binding, and schedules work under the per-instance execution limit. The release manager verifies and installs the selected release. The supervisor invokes that release's Python executable; the worker performs the scientific chain and returns the established result. The platform applies existing API/report projection and job-state transitions.

Keep scientific QC inside the release. In particular, Aramina's canonical-input validation currently precedes artifact-specific raw preprocessing; do not delete that stage because the worker receives H5. Extract the necessary legacy/canonical compatibility support without making the worker depend on the whole application. Keep generic authorization and source binding in the platform.

The neutral contract library, if used, must have no platform imports, discovery, AWS configuration or scientific runtime side effects. Releases must import and execute without `bremen.platform`, the full Bremen distribution, a repository checkout or a network package index. Existing package bridges must be removed or adapted within the release boundary.

## Release manifest v1 (to implement in IR-02)

Use schema identifier `bremen.inference-release.v1`. Required fields and meanings:

| Field | Requirement |
|---|---|
| schema_version | Exact supported schema identifier; reject unknown major versions |
| release_id | Immutable human-readable release identity; never infer it from family name |
| model | Existing model_id, model version, workflow family and artifact identity |
| compatibility | Python implementation/version/ABI, OS/architecture, required native libraries, worker protocol version |
| entrypoint | Allowlisted module from the installed inference wheel; no shell command |
| files | Role, relative path, S3 object key, byte size and SHA-256 for every wheel, lock, artifact, config and provenance record |
| environments | Main and optional auxiliary environments; exact wheel closures and hash-locked requirements per environment |
| scientific_metadata | Preprocessing release/commit, feature-order/config hashes, artifact checksum and threshold source |
| build | Source repository and full commit, build identity and provenance reference |

The catalog pins the manifest SHA-256; it is computed over the exact manifest bytes and is not a self-referential field. Reject path traversal, symlink escapes, duplicate paths, missing objects, hash mismatch, incompatible ABI and undeclared dependencies. Checksums provide integrity relative to a trusted catalog; S3 write IAM and build provenance establish trust. Continue existing trusted-artifact loading controls.

Extend existing catalog entries additively with an optional `runtime_release` object: `schema_version`, `release_id`, `manifest_key`, `manifest_sha256`. IR-02 defines and tests this extension; it is not currently supported. Legacy manifests continue to validate. Release storage must be outside the immediate-child legacy discovery layout, or discovery must explicitly exclude it. Do not create multiple catalog entries with the same model_id. Existing strict Aramina manifest allowlists need an explicit compatible update.

Publish immutable blobs first and the release manifest last. Publication does not activate a model. Activation changes the existing catalog reference through a separate reviewed operation. Reject mutation of an already-published identity; record S3 version IDs where enabled. No `latest` dependency resolution.

## Worker protocol v1 (to implement in IR-02)

Protocol identifier `bremen.worker.v1`; UTF-8 JSON Lines over dedicated stdin/stdout pipes. stderr is diagnostic output. Define maximum line size, total result size, event count and diagnostic bytes in validated platform configuration; exceeding a limit is a typed worker failure, never unbounded buffering.

Every request contains protocol, request_id, operation, model_id, release_digest and payload. Supported operations are `requirements`, `validate`, and `predict`, preserving the existing ModelRuntime semantics. A predict operation MUST perform scientific validation even if validate was previously called. Start a fresh worker for each invocation in this first design.

Predict payload represents the existing ModelInput fields explicitly: authorized staged measurement paths and metadata, canonical metadata needed by compatibility validation, patient/target binding information and allowed parameters. IR-02 must enumerate every current contract field and its JSON type, nullability and units. No implicit dataclass serialization, arbitrary Python object, pickle payload, or user-supplied executable/module path.

Events contain protocol, request_id, sequence, event_type and payload. Allowed events: `started`, `features`, `result`, `error`; exactly one terminal result/error. Features events map to the existing on_features callback. Result serialization must preserve the existing RuntimePrediction/result contracts, source metadata, ordering and meaningful nulls. JSON cannot contain NaN/Infinity: explicitly encode existing missing/nonfinite semantics without changing scientific imputation. Error codes distinguish model input/QC failures, artifact/release failures, timeout, capacity and worker crash; map them to existing external behavior deliberately, with contract tests.

Reject wrong identity/digest, unsolicited events, invalid sequence, duplicate terminal events, premature EOF and nonzero exit after a claimed success. Logs must not pollute stdout or expose source content/patient data. Success requires a valid terminal result and clean process exit.

## Supervisor and installer

Spawn argv directly with the release environment Python, an allowlisted entrypoint, restricted environment and dedicated working directory. Do not inherit platform AWS credentials unnecessarily. Stage only authorized inputs. Apply execution deadline and process-group termination (graceful then forceful), await exit and clean request files on every path. Separate installation deadlines from inference deadlines; retain per-model timeout behavior until baseline evidence justifies changes.

Initial target is at most one scientific invocation per instance, subject to IR-01 resource evidence. Existing job threads are not permission for multiple scientific workers. Account for auxiliary children and native numerical threads. Define overload behavior without silently changing the public API. Cancellation/restart behavior must match documented service guarantees.

Installation uses an interprocess lock per release digest. Verify all files before use; install wheels offline with hashes and no source builds. Build a venv at its final digest-qualified path: moving a built venv may break absolute interpreter paths. Write a READY marker only after installation and smoke validation; interrupted installations are never executable. Evict only unreferenced inactive releases under a disk budget. Never evict a running worker's environment. No public endpoint may choose arbitrary S3 keys or install arbitrary packages.
