# Architecture and normative contracts

Status: target design, not a description of an implemented release loader. MUST denotes a gate for this roadmap.

## Ownership and request flow

Terminology used throughout this document: the **Harness** is the platform-side component that authenticates, resolves, installs and supervises; the **Model Runner** is the per-release installed environment plus its pinned entrypoint; the **Worker** is the OS process the Harness spawns from that Model Runner to run one job; the **ML plugin** is the release's scientific code (artifact loading, compatibility, preprocessing, inference, postprocessing) that executes inside the Worker.

The Harness authenticates a request, resolves its existing model ID to a pinned release digest, obtains authorized source files, performs source/patient binding, and schedules work under the per-instance execution limit. The release manager verifies and installs the selected release (the Model Runner). The Harness's supervisor invokes that release's Python executable as a Worker process; the Worker, running the ML plugin, performs the scientific chain and returns the established result. The Harness applies existing API/report projection and job-state transitions.

**Ownership boundary:** the Harness, Model Runner, common Worker launcher, process supervision and the wire protocol are platform-owned. The ML plugin, its preprocessing, inference and scientific postprocessing are ML-team-owned and live entirely inside the release. This is an import boundary, not only an organizational one: **the Harness MUST NOT import ML plugin code.** The Harness only ever starts the release's Worker process and exchanges the file-based protocol defined below with it; it never links against, imports, or deserializes objects belonging to plugin source in its own process.

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
| entrypoint | Allowlisted module from the installed ML plugin wheel; no shell command |
| files | Role, relative path, S3 object key, byte size and SHA-256 for every wheel, lock, artifact, config and provenance record |
| environments | Main and optional auxiliary environments; exact wheel closures and hash-locked requirements per environment |
| scientific_metadata | Preprocessing release/commit, feature-order/config hashes, artifact checksum and threshold source |
| golden_tests | Role, relative path, S3 object key and SHA-256 for the release's golden-fixture inputs/expected-outputs used to smoke-verify an installation before READY |
| build | Source repository and full commit, build identity and provenance reference |

The manifest's `entrypoint` and `files[].role=plugin_wheel` together define the **ML plugin wheel** for this release: the installable unit that contains all ML-team-owned scientific code. The catalog pins the manifest SHA-256; it is computed over the exact manifest bytes and is not a self-referential field. Reject path traversal, symlink escapes, duplicate paths, missing objects, hash mismatch, incompatible ABI and undeclared dependencies. Checksums provide integrity relative to a trusted catalog; S3 write IAM and build provenance establish trust. Continue existing trusted-artifact loading controls.

Extend existing catalog entries additively with an optional `runtime_release` object: `schema_version`, `release_id`, `manifest_key`, `manifest_sha256`. IR-02 defines and tests this extension; it is not currently supported. Legacy manifests continue to validate. Release storage must be outside the immediate-child legacy discovery layout, or discovery must explicitly exclude it. Do not create multiple catalog entries with the same model_id. Existing strict Aramina manifest allowlists need an explicit compatible update.

### Release lifecycle

A release moves through four explicit states, never skipped and never inferred from file presence alone:

| State | Meaning |
|---|---|
| PUBLISHED | Immutable blobs (manifest, plugin wheel, artifacts, wheelhouse, golden tests) are uploaded to S3. Publication alone MUST NOT activate a model. |
| VERIFIED | Manifest/checksum/ABI validation and golden-test smoke-check have passed against the published blobs. |
| READY | The release is installed into a digest-qualified local environment and is admissible for scheduling. A READY marker is written only after installation and smoke validation succeed. |
| ACTIVE | An authorized operator has switched the existing catalog reference to this release digest, for this one model_id, through a separate reviewed operation. |

Reject mutation of an already-published identity; record S3 version IDs where enabled. No `latest` dependency resolution. Moving from PUBLISHED to ACTIVE always passes through VERIFIED and READY; there is no shortcut path.

## Worker protocol v1 (to implement in IR-02)

Protocol identifier `bremen.worker.v1`; a **file-based** protocol, not stdin/stdout JSON Lines. The Harness stages one job directory per invocation containing `request.json` (the request envelope and payload) and `input.h5` (the staged measurement file); the Worker writes `result.json` into that same directory on completion. stdout and stderr carry diagnostics only — never the authoritative result — and MUST NOT be parsed as a result channel. Define maximum request/result file size, event count and diagnostic bytes in validated platform configuration; exceeding a limit is a typed worker failure, never unbounded buffering.

`request.json` contains protocol, request_id, operation, model_id, release_digest and payload. Supported operations are `requirements`, `validate`, and `predict`, preserving the existing ModelRuntime semantics. A predict operation MUST perform scientific validation even if validate was previously called. Start a fresh worker for each invocation in this first design.

Predict payload represents the existing ModelInput fields explicitly: authorized staged measurement paths and metadata (including the path to the staged `input.h5`), canonical metadata needed by compatibility validation, patient/target binding information and allowed parameters. IR-02 must enumerate every current contract field and its JSON type, nullability and units. No implicit dataclass serialization, arbitrary Python object, pickle payload, or user-supplied executable/module path.

Optional structured progress events preserve the existing event semantics (`started`, `features`, `result`/`error` as the terminal state) but are carried as diagnostics (for example, newline-delimited JSON on stderr or an auxiliary events file), never on stdout and never as a substitute for `result.json`. Exactly one terminal result/error is authoritative and it is always the content of `result.json`. Features events map to the existing on_features callback. Result serialization must preserve the existing RuntimePrediction/result contracts, source metadata, ordering and meaningful nulls. JSON cannot contain NaN/Infinity: explicitly encode existing missing/nonfinite semantics without changing scientific imputation.

### Typed error codes

`result.json` reports failure using one of the following typed error codes, mapped deliberately to existing external behavior with contract tests:

| Code | Meaning |
|---|---|
| INPUT_INVALID | Request payload or staged input failed structural/contract validation before scientific processing |
| QC_FAILED | Scientific QC (canonical validation, measurement/metadata checks) rejected the input |
| MODEL_NOT_READY | The release/model is not in READY/ACTIVE state for this invocation |
| INFERENCE_FAILED | The scientific chain raised during preprocessing, feature construction or prediction |
| TIMEOUT | The Worker did not produce a terminal result within the execution deadline |
| RESOURCE_EXHAUSTED | Capacity/admission limits (concurrency, memory, disk, cache) prevented execution |
| PROTOCOL_ERROR | Malformed request/result file, wrong identity/digest, unsolicited/invalid events, duplicate terminal state or premature process exit |

Reject wrong identity/digest, unsolicited events, invalid event sequence, duplicate terminal events, a missing/malformed `result.json` and nonzero exit after a claimed success — all as `PROTOCOL_ERROR` unless a more specific code above applies. Logs must not pollute stdout or expose source content/patient data. Success requires a valid `result.json` terminal result and clean process exit.

## Supervisor and installer

The Harness's supervisor spawns argv directly with the release environment Python, an allowlisted entrypoint, restricted environment and a dedicated per-job working directory. It stages only authorized inputs into that directory as `request.json` and `input.h5` before launch, and reads `result.json` from it after the Worker exits. Do not inherit platform AWS credentials unnecessarily. Apply execution deadline and process-group termination (graceful then forceful), await exit and clean request/result files on every path. Separate installation deadlines from inference deadlines; retain per-model timeout behavior until baseline evidence justifies changes.

Initial target is at most one scientific invocation per instance, subject to IR-01 resource evidence. Existing job threads are not permission for multiple scientific workers. Account for auxiliary children and native numerical threads. Define overload behavior without silently changing the public API. Cancellation/restart behavior must match documented service guarantees.

Installation uses an interprocess lock per release digest. Verify all files before use; install wheels (the ML plugin wheel and its pinned dependency closure) offline with hashes and no source builds. Build a venv at its final digest-qualified path: moving a built venv may break absolute interpreter paths. Run the release's golden tests as the smoke check gating the PUBLISHED→VERIFIED and VERIFIED→READY transitions; write a READY marker only after installation and smoke validation pass — interrupted installations are never executable. Evict only unreferenced inactive releases under a disk budget. Never evict a running worker's environment. No public endpoint may choose arbitrary S3 keys or install arbitrary packages.

## Feature library architecture (to implement in IR-07)

Status: target design for IR-07, added 2026-10-23. Not implemented by this documentation change. This section documents the target dependency direction only; it changes no scientific definitions.

The XRD inference feature computation must be separated from Bremen into its own standalone, independently versioned Python wheel before legacy cleanup (IR-08) proceeds. Target dependency direction:

```text
Bremen Harness
    -> Model Release
        -> ML plugin wheel
        -> XRD feature-library wheel
        -> model artifact
        -> pinned dependencies
        -> golden tests
```

The feature library is **not** globally installed into the Bremen/App Runner runtime. Each Model Release independently binds the exact feature-library wheel it needs (filename, version and SHA-256 recorded in that release's manifest, consistent with `scientific_metadata` above) and installs it into that release's own venv. Different releases may use the same wheel SHA, different wheel versions, or different frozen scientific contracts — but none may depend on a mutable or shared runtime installation.

### The 15 frozen Bremen feature functions

The exact names and this exact order are part of the model contract and MUST NOT change under extraction:

```text
weightedrms1
sigma_l1
sigma_r1
mahalanobis1
weightedrms2
sigma_l2
sigma_r2
mahalanobis2
peak14_intensity
mean_peak_value_raw
wasserstein_distance_muLR
cosine_distance_full_q2
wasserstein_distance_full_q2
meanrms1
meanrms2
```

### Scientific contracts remain distinct

IR-07 does not unify computation modes. At minimum the feature library preserves, as separate frozen contracts:

- **Bremen v0.1 contract** — existing v0.1 ROI/normalization/pairing semantics.
- **Bremen v0.2 contract** — existing v0.2 ROI/normalization/pairing semantics.
- **Aramina** — consumes its existing frozen feature subset/derived values only; Aramina must not be forced to consume all 15 Bremen features.

No silent unification of ROI, normalization or pairing behavior across contracts.

### Ownership

| Owner | Responsibility |
|---|---|
| Platform/Bremen | Harness, catalog routing, ReleaseCache, venv installation, Worker supervision, protocol, report projection |
| Feature library | Reusable XRD feature computation, frozen scientific feature contracts, feature schema/order validation, unit/golden tests |
| ML plugin | Selecting the contract/version, model-specific preprocessing orchestration, model artifact loading, inference/postprocessing |

## Final architectural acceptance

The design is accepted for this roadmap block only if a new, conforming Model Release — manifest, artifacts, ML plugin wheel, pinned dependencies, provenance and golden tests — can be published and carried through VERIFIED → READY → ACTIVE without rebuilding the Bremen application image and without changing any Harness code. Onboarding model six (or later) is an operational/catalog action bounded by the contracts in this document, not a platform source change.
