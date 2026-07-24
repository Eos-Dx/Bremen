PLAN COMPLETE

PLAN FILE

.project-memory/pr/0085-s3-model-catalog-discovery/PLAN.md

HEAD

434cb9679c22de6184e4388e1d872f0698a1dd23

BRANCH

0085-s3-model-catalog-discovery

STATUS

valid

BLOCKERS

None.

WARNINGS

Implementation requires a distinct S3 prefix with at least one valid
Bremen model package. AWS IAM permissions for ListBucket and GetObject
on the configured prefix are the deployment owner's responsibility.
This PR does not modify infrastructure, IAM, or deployment configuration.

CURRENT STATE

The current runtime loads exactly one model from BREMEN_MODEL_URI at
startup via ModelState.load_at_startup(). The model catalog
(model_catalog.py) builds a single entry from ModelState with
model_id="bremen-current". The job API resolves model_id through
resolve_model() which reads catalog entries built from ModelState.

The existing model_catalog.py build_model_catalog() is called per
API request and reads ModelState. resolve_model() also calls
build_model_catalog(). Neither performs S3 work per request.

The workflow registry (workflow_orchestrator.py get_default_registry())
reads ModelState.get_model() and constructs a BremenProvider with that
package. All jobs, regardless of model_id, receive the same singleton
package from ModelState.

Existing model_package.py validates local package directories with
manifest.json reading, required field validation, SHA-256 checksum,
and path-traversal prevention.

Existing model_artifacts.py provides S3 staging with stage_model_artifact
and stage_s3_model_artifact supporting checksum verification.

The start_page_ui.py loads GET /demo/api/models and renders radio card
selection. model_id is URL-persistent to the Control Room.

The job API (job_api_handler.py create_analysis_job) accepts model_id
and passes it through to the orchestrator.

ARCHITECTURE

Introduce one new startup module and one new registry module.

s3_model_discovery.py
  Startup-only module. Reads BREMEN_MODEL_CATALOG_URI. Lists manifests
  under the configured S3 prefix. Validates each candidate. Stages
  and loads valid packages. Returns a list of CatalogEntry objects.

model_registry.py
  Immutable process-local singleton that owns the list of all
  discovered and validated CatalogEntry records. Initialized once
  at startup by the discovery module. Survives module reload via
  bremen-package storage. Read-only after initialization.

The existing model_catalog.py build_model_catalog() is replaced by
a call to the registry snapshot. The existing resolve_model() is
updated to read from the registry instead of building per-request.

At startup, server.py run_server() calls:
  1. Check for BREMEN_MODEL_CATALOG_URI. If present, run discovery
     and initialize the registry. If absent, fall back to existing
     ModelState path and create a single-entry registry from it.
  2. ModelState is no longer the authoritative model source after
     bootstrap. The registry is the single source of truth.

CONFIGURATION

One new environment variable:

BREMEN_MODEL_CATALOG_URI = "s3://bucket/allowlisted/prefix/"

The value must include a non-empty bucket and non-empty prefix.
Prefix must end with /.

When BREMEN_MODEL_CATALOG_URI is present:
  Catalog mode is active.
  BREMEN_MODEL_URI, BREMEN_MODEL_VERSION, BREMEN_MODEL_CHECKSUM are
  ignored. A safe startup log warns that legacy settings were overridden.
  Do not log the catalog URI, bucket, prefix, object keys, or filenames.

When BREMEN_MODEL_CATALOG_URI is absent:
  Preserve current legacy single-model behavior.
  ModelState.load_at_startup() is called as today.
  The registry is built with one entry from ModelState,
  model_id="bremen-current".

BREMEN_MODEL_STAGING_DIR is respected in catalog mode for staging
discovered model artifacts. Unchanged in legacy mode.

S3 LAYOUT

Recognized layout:

catalog-prefix/package-directory/manifest.json
catalog-prefix/package-directory/model-file-named-by-manifest

Example with BREMEN_MODEL_CATALOG_URI = "s3://demo-models/bremen/":

s3://demo-models/bremen/v1-0/manifest.json
s3://demo-models/bremen/v1-0/model.joblib
  -> model_id: "bremen-v1", display_name: "Bremen V1"

s3://demo-models/bremen/v2-0/manifest.json
s3://demo-models/bremen/v2-0/model.joblib
  -> model_id: "bremen-v2", display_name: "Bremen V2"

Rules:
  Only keys ending in /manifest.json are candidates.
  The manifest must be an immediate child of exactly one package
  directory below the configured prefix.
  Do not accept nested manifests (e.g., prefix/sub/deep/manifest.json).
  The model_filename field in the manifest is a basename only.
  The artifact must resolve within the same package directory.
  No identity derived from S3 paths, filenames, ordering, or timestamps.

Support S3 pagination via list_objects_v2 with ContinuationToken.

Sort manifest keys lexicographically before validation for
deterministic startup behavior.

Hard maximum of 50 candidate manifests. If more than 50 keys are
returned, fail catalog discovery with status=too_many_manifests and
publish no models.

Maximum manifest body size: 65,536 bytes. Reject oversized manifests
without parsing.

MANIFEST CONTRACT

Reuse the existing base manifest fields:

  artifact_type (must be "bremen.joblib.model_package")
  model_version (non-empty string)
  model_checksum (64-char hex)
  model_filename (basename, no path separators)
  feature_schema_version (non-empty string)
  threshold_version (non-empty string)
  threshold_value (numeric)
  qc_criteria_version (non-empty string)

Add discovery-specific fields (required only for catalog discovery):

  model_id: lowercase stable public identifier matching ^[a-z0-9][a-z0-9._-]{0,63}$
  display_name: trimmed non-empty string, max 80 characters
  workflow_id: must equal "bremen"

Do not add these three fields to the legacy _REQUIRED_MANIFEST_FIELDS set
in model_package.py. The existing validator must remain unchanged so that
legacy packages without discovery fields remain valid.

Reject model_id and display_name containing control characters.

Do not add sensitivity, specificity, reliability, performance, demographic,
age, race, ethnicity, promotion, default, or certification fields.

DISCOVERY AND VALIDATION PIPELINE

Exact startup sequence in s3_model_discovery.py:

function discover_models(catalog_uri: str, staging_dir: str | Path) -> CatalogDiscoveryResult:

1. Validate catalog_uri format. Parse bucket and prefix.

2. Initialize S3 client. List objects with prefix, delimiter=/ to get
   common prefixes one level deep (potential package directories).
   If prefix does not end with /, append it temporarily for listing
   but use the original prefix for identity resolution.

   Better approach: List objects with prefix=catalog_prefix and no
   delimiter. Filter for keys ending in /manifest.json that are at
   depth prefix + one directory level + manifest.json.

   Use pagination. Collect all candidate keys.

3. If total candidates > 50, return discovery_failed with a safe
   too_many_manifests category.

4. Sort candidate keys lexicographically.

5. For each candidate key in order:
   a. Check manifest body size by reading Content-Length header
      or by streaming only up to 65,536 bytes. If oversized,
      skip with a count and continue.
   b. Download the manifest object body.
   c. Parse JSON. If invalid, skip.
   d. Run the existing base manifest validator
      (model_package.validate_model_manifest).
   e. Run discovery-specific validator:
      - model_id matches pattern, no control chars
      - display_name non-empty, max 80, no control chars
      - workflow_id == "bremen"
   f. Resolve model_id uniqueness. If model_id already seen
      in this run, reject all occurrences of that model_id.
      do not select by S3 order.
   g. Resolve the artifact key: package_dir = manifest key's
      parent directory. model_filename from manifest is basename.
      artifact_key = package_dir + "/" + model_filename.
      Verify artifact_key starts with catalog prefix and is within
      the same package directory.
   h. Stage the artifact via stage_s3_model_artifact.
   i. Verify SHA-256 against manifest model_checksum.
   j. Load via joblib.load().
   k. Validate loaded dict has key "portable_logreg" with the
      expected structure (same as existing validate_portable_logreg_model).
   l. Validate workflow_id compatibility.
   m. Validate feature_schema_version compatibility with current
      runtime (must match expected v0.1 or compatible).
   n. Create a registry entry with the loaded package and safe
      metadata.
   o. On any validation failure for this candidate: skip, increment
      rejected_count, log a safe error category, continue to next
      candidate.

6. After processing all candidates, return:
   - entries: list of CatalogEntry objects (validated and loaded)
   - candidate_count: total manifest candidates found
   - available_count: number of successfully loaded entries
   - rejected_count: number of candidates that failed validation
   - catalog_status: "available" if at least one entry,
     "no_valid_models" if zero valid entries, "discovery_failed"
     if S3 listing failed or too many manifests,
     "not_configured" if BREMEN_MODEL_CATALOG_URI is absent.

FAILURE POLICY

Catalog-level failure (invalid URI, S3 listing failure, >50 manifests):
  Do not crash the process. Initialize an empty registry with
  catalog_status="discovery_failed". Serve APIs with honest
  unavailable state. Analysis disabled.

Individual candidate failure:
  Skip the candidate. Continue processing other candidates.
  Log a safe error category only.
  Do not expose the manifest, key, path, exception, or package
  content in any API response.

Partial success:
  When some candidates pass and some fail, available_count reflects
  only the passing candidates. rejected_count reflects the failing
  ones. The catalog API returns all available models.

MODEL REGISTRY

model_registry.py:

@dataclass(frozen=True)
class RegistryModelEntry:
    model_id: str
    display_name: str
    workflow_id: str
    model_version: str
    artifact_type: str
    feature_schema_version: str
    decision_policy_id: str
    decision_policy_version: str
    technical_ready: bool
    scientifically_certified: bool
    technical_demo_only: bool
    # Private fields (never exposed in API responses)
    package: dict  # the loaded portable_logreg package
    checksum: str
    staged_path: str | None  # for lifecycle management if needed

@dataclass(frozen=True)
class ModelRegistry:
    entries: dict[str, RegistryModelEntry]  # model_id -> entry
    catalog_timestamp: str
    candidate_count: int
    available_count: int
    rejected_count: int
    catalog_status: str  # "available" | "empty" | "no_valid_models" |
                        # "discovery_failed" | "not_configured"

Singleton stored on bremen package (same pattern as ModelState):

_bremen_model_registry: ModelRegistry | None = None

Functions:
  initialize_registry(entries, ...) -> called once at startup
  get_registry() -> ModelRegistry | None
  get_model_entry(model_id) -> RegistryModelEntry | None
  get_model_package(model_id) -> dict | None (returns private package)

The registry is immutable after initialization. No mutation after
startup. No per-request S3 work.

LEGACY COMPATIBILITY

When BREMEN_MODEL_CATALOG_URI is absent:

server.py run_server calls ModelState.load_at_startup() as today.
After ModelState loads, build a ModelRegistry with one entry:
  model_id="bremen-current"
  display_name="Bremen Current"
  workflow_id="bremen"
  model_version from ModelState
  artifact_type="portable_logreg"
  feature_schema_version from package
  decision_policy_id and version from decision_contract
  technical_ready = ModelState.is_ready()
  scientifically_certified = False
  technical_demo_only = True
  package = ModelState.get_model()

Initialize the registry with this single entry.

All existing ModelState tests remain unchanged because the legacy
path still exercises the same load_at_startup code.

CATALOG API

GET /demo/api/models:

model_catalog.py build_model_catalog() is replaced. It now reads from
the registry snapshot:

  registry = get_registry()
  if registry is None:
      return {"status": "not_configured", "models": []}
  entries = [entry.to_public_dict() for entry in registry.entries.values()]
  sort entries by model_id (deterministic order)
  default_id = entry.model_id if len(entries) == 1 else None
  return {
      "schema_version": "v1",
      "catalog_timestamp": registry.catalog_timestamp,
      "candidate_count": registry.candidate_count,
      "available_count": registry.available_count,
      "rejected_count": registry.rejected_count,
      "models": entries,
      "default_model_id": default_id,
      "status": registry.catalog_status,
  }

The to_public_dict() method on RegistryModelEntry exposes only safe
metadata (not the private package, checksum, or path).

START PAGE

No change to the approved PR0082b start_page_ui.py design. The Start
page already reads GET /demo/api/models and renders radio cards. With
multiple available models, no card is pre-selected. With exactly one
available, it is pre-selected. With zero available, entry disabled
with status message.

The start_page_ui.py already handles multiple models correctly.
No changes needed.

JOB BINDING

job_api_handler.py create_analysis_job(model_id=...):

The existing code calls resolve_model() which reads the catalog.
resolve_model() is updated to read from the registry.

After resolving model_id, the code stores model_id in the job record
input_summary. This is already done.

The model_id is stored before execution begins. It is immutable for
the lifetime of the job.

EXECUTION BINDING

This is the critical architectural change.

Currently, workflow_orchestrator.py get_default_registry() creates
BremenProvider with model_package from ModelState.get_model(). All
jobs get the same singleton package.

In catalog mode, the provider must receive the package from the
registry entry matching the job's model_id.

The change:

workflow_orchestrator.py get_default_registry() or a new function
get_provider_for_model(model_id) reads the registry entry and
constructs a BremenProvider with that entry's package:

  entry = get_model_entry(model_id)
  if entry is None:
      raise ModelNotFoundError(...)
  provider = BremenProvider(
      model_package=entry.package,
      model_checksum=entry.checksum,
      model_version=entry.model_version,
      model_id=entry.model_id,
  )

The provider is created fresh for each job with its specific package.
Model_id already flows through the orchestrator. The change is in
how the provider is constructed: instead of reading the global
ModelState, it reads from the registry entry.

The function run_workflow_request() in workflow_orchestrator.py
already accepts model_id. The change is inside get_default_registry()
or a new provider factory that uses model_id to select the right
package.

Concurrent jobs with different model_ids each receive their own
provider instance with their own package. No shared mutable state
between providers.

BremenProvider.__init__ already accepts model_package, model_checksum,
and model_version. A new model_id parameter is added (default None)
for the provider to use in its payload output.

HEALTH

GET /health:

In legacy mode: model_ready = ModelState.is_ready() (unchanged).

In catalog mode: model_ready = (registry is not None and
registry.available_count > 0).

When catalog discovery failed or found no valid models:
model_ready = False. HTTP 200 still returned (service is running).

MODEL VERSION

GET /model/version:

In legacy mode: unchanged behavior from ModelState.

In catalog mode:
  Zero available models: same as legacy "not_configured" response.
  Exactly one available model: return that model's safe metadata.
  Multiple available models:
    model_configured = True
    model_status = "selection_required"
    model_version = null
    model_checksum = null
    feature_schema_version = null
    threshold_version = null
    threshold_value = null
    qc_criteria_version = null

Do not expose a random, first, or lexicographically selected model.

PRIVACY

No S3 URI, bucket, prefix, object key, manifest content, model filename,
local staging path, or environment variable value appears in public API
responses, browser HTML, events, logs, or error messages.

Safe structured logs contain only:
  catalog_status (string category)
  candidate_count (integer)
  available_count (integer)
  rejected_count (integer)
  model_id (for valid entries)
  error_category (for failures, e.g., "invalid_manifest", "checksum_mismatch")

No private package data, coefficients, intercepts, scaler values,
imputer values, or reference distributions enter public responses.

THREAD SAFETY

The registry is written exactly once during startup (single-threaded
initialization phase). After that it is immutable and read-only.
Reads from request handler threads are safe without locks.

The initialization function is protected by a threading.Lock with
double-checked pattern (same as existing job_api_handler.py singletons).

The registry reference is stored on the bremen package. Module reloads
that purge bremen.api.* but retain the bremen package will retain the
registry reference.

EXPECTED FILES

New files:

src/bremen/api/s3_model_discovery.py
  S3 manifest listing, validation pipeline, artifact staging and
  loading. Functions:
    discover_models(catalog_uri, staging_dir) -> CatalogDiscoveryResult
    _validate_catalog_uri(uri) -> (bucket, prefix)
    _list_candidate_manifests(s3_client, bucket, prefix) -> list[str]
    _validate_manifest_body(body_bytes) -> dict
    _validate_discovery_fields(data) -> dict
    _resolve_artifact_key(manifest_key, model_filename, catalog_prefix) -> str
    _stage_and_load_artifact(s3_client, bucket, artifact_key,
      expected_checksum, staging_dir) -> dict
    _validate_loaded_package(package, entry) -> bool

src/bremen/api/model_registry.py
  RegistryModelEntry dataclass.
  ModelRegistry dataclass.
  initialize_registry(entries, ...) function.
  get_registry() function.
  get_model_entry(model_id) function.
  get_model_package(model_id) function.

Modified files:

src/bremen/api/model_catalog.py
  build_model_catalog() reads from model_registry instead of ModelState.
  resolve_model() reads from model_registry.
  Add candidate_count, available_count, rejected_count to catalog
  response when registry mode.

src/bremen/api/model_state.py
  No changes to ModelState class. The singleton and legacy path
  remain untouched.
  Add a function or startup adapter to convert a ModelState-loaded
  package into a registry entry.

src/bremen/api/workflow_orchestrator.py
  get_default_registry() or a new get_provider_for_model(model_id)
  function that reads from model_registry to get the package for
  the requested model_id.
  When model_id is provided, construct BremenProvider with the
  registry entry's package.
  Fall back to ModelState when registry is not configured
  (legacy mode).

src/bremen/api/workflow_bremen.py
  Add model_id parameter to __init__ (default None).
  Use model_id in result payload when provided.
  No change to execution logic.

src/bremen/api/server.py
  run_server() startup changes:
    1. Check for BREMEN_MODEL_CATALOG_URI.
    2. If present, run discovery and initialize registry.
    3. If absent, load ModelState as today, build legacy registry.
    4. Set up the registry singleton before handling requests.
  GET /model/version handler updated for multi-model response.

src/bremen/api/app.py
  handle_model_version() updated to read from registry and return
  selection_required status when multiple models exist.

docs/api_contract.md
  Document BREMEN_MODEL_CATALOG_URI.
  Document GET /model/version selection_required state.
  Document GET /demo/api/models aggregate counts.

docs/release_readiness_operator_notes.md
  Document catalog mode vs legacy mode.
  Document S3 permission requirements.
  Document startup behavior.

ROADMAP.md
  Add PR0085 as current milestone.

New test files:

tests/test_s3_model_discovery.py
  Catalog URI validation.
  S3 pagination mock.
  Manifest key sorting.
  Zero, one, multiple manifest scenarios.
  More than 50 manifests rejection.
  Oversized manifest rejection.
  Invalid JSON rejection.
  Missing base fields rejection.
  Missing discovery fields rejection.
  Invalid model_id rejection.
  Invalid display_name rejection.
  Wrong workflow_id rejection.
  Path traversal rejection.
  Artifact outside package directory rejection.
  Missing artifact rejection.
  Checksum mismatch rejection.
  Wrong artifact type rejection.
  Unsupported feature schema rejection.
  Invalid portable_logreg rejection.
  Joblib load failure handling.
  Duplicate model_id rejection.
  Partial success (3 valid, 2 invalid).
  S3 listing failure handling.

tests/test_model_registry.py
  Registry creation.
  Immutability after creation.
  get_model_entry returns correct entry.
  get_model_package returns private package.
  Registry surviving module reload.
  Concurrent read safety.
  Legacy single-entry construction from ModelState.
  Catalog mode with multiple entries.

tests/test_multi_model_execution.py
  Two synthetic models with differing coefficients.
  Job created with model A produces expected output A.
  Job created with model B produces expected output B.
  Concurrent jobs with different models.
  Provider isolation (no cross-bleed).
  model_id in result payload matches selected model.

tests/test_catalog_api_multi_model.py
  Catalog returns multiple entries.
  Catalog in deterministic order.
  default_model_id is null when multiple entries.
  default_model_id is set when one entry.
  status available, empty, no_valid_models, discovery_failed.
  No private fields in catalog response.

tests/test_health_multi_model.py
  health model_ready true when at least one model.
  health model_ready false when zero models.
  health model_ready false when discovery failed.

tests/test_model_version_multi_model.py
  model/version with zero models returns not_configured.
  model/version with one model returns that model's data.
  model/version with multiple models returns selection_required.

Modified test files:

tests/test_bremen_model_catalog.py
  Extend with multi-model catalog tests.

tests/test_bremen_start_page.py or test_bremen_control_room.py
  Extend with multi-model start page behavior.
  Zero models disables entry.
  One model pre-selected.
  Multiple models require selection.

implementation report:

.project-memory/pr/0085-s3-model-catalog-discovery/implementation-report.md

ACCEPTANCE CRITERIA

1. Catalog URI validation: Bad URI rejected with safe startup log.
2. S3 pagination: All candidate keys under prefix discovered.
3. Deterministic ordering: Same manifest set produces same order.
4. >50 manifests: Catalog fails safe with typed status.
5. Oversized manifest: Skipped, counted in rejected_count.
6. Valid manifest with all fields: Creates one registry entry.
7. Missing discovery fields: Candidate rejected, others unaffected.
8. Invalid model_id pattern: Candidate rejected.
9. Duplicate model_id: All occurrences rejected.
10. Path traversal in model_filename: Candidate rejected.
11. Artifact outside package dir: Candidate rejected.
12. Checksum mismatch: Candidate rejected.
13. Partial success: 2 valid, 2 invalid -> 2 available, 2 rejected.
14. S3 listing failure: catalog_status="discovery_failed".
15. Legacy BREMEN_MODEL_URI fallback: Single entry bremen-current.
16. Catalog mode precedence: Legacy settings ignored with warning.
17. Registry immutable after startup.
18. get_model_package returns correct package per model_id.
19. Job with valid model_id: Succeeds, uses that package.
20. Job with unknown model_id: Rejected with typed error.
21. Job with no model_id and 2+ models: Rejected ambiguous.
22. Two concurrent jobs with different models: Each returns correct
    output from its own package.
23. GET /demo/api/models: Returns all available entries sorted.
24. default_model_id null when 2+ models, set when 1 model.
25. No private fields in catalog, job, event, report, or page response.
26. GET /health model_ready reflects available_count > 0.
27. GET /model/version returns selection_required when 2+ models.
28. GET /model/version returns singular data when 1 model.
29. Start page: Zero models disables entry. One model pre-selected.
    Multiple models requires selection.
30. Full legacy test suite passes unchanged.

TEST STRATEGY

All tests use injected fake S3 clients (moto or monkeypatch) and
synthetic model packages. No real AWS calls. No real model artifacts.

Synthetic packages are small dicts with controlled coefficients,
created inline in tests, saved to temp dirs, and loaded via joblib.
No real model files.

The two-model execution test (test_multi_model_execution.py) constructs
two synthetic packages with different coef values (e.g., [0.1]*15 vs
[0.9]*15) and different thresholds (e.g., 0.3 vs 0.7). It creates
controlled canonical XRD input with known intensity profiles. It
asserts that each job produces the expected probability for its model.

NON-GOALS

No continuous polling.
No hot reload.
No model upload UI.
No automatic newest-model selection.
No automatic promotion.
No default marker in manifests.
No model comparison or ensemble.
No multiple models in one job.
No ModelVariant or model_variant_id contract.
No production role-based access control.
No clinical approval workflow.
No scientific certification changes.
No sensitivity, specificity, reliability, demographic, age, race,
  ethnicity metadata in manifests or catalog.
No training.
No H5 contract changes.
No preprocessing or feature changes.
No threshold or decision-vocabulary changes.
No Aramis model discovery.
No React, npm, frontend framework, or build step.
No Docker, Terraform, AWS, or CI changes.

STOP CONDITIONS

Stop with a blocker if:

The branch is not 0085-s3-model-catalog-discovery.
The base does not include the query-routing and health-log hotfix
  (commit 434cb96).
The existing manifest contract cannot be extended with a separate
  discovery validator without breaking legacy packages.
The selected model package cannot be bound to BremenProvider
  without changing scientific behavior.
The implementation would mutate one global current model per
  user selection.
The plan relies on filenames, timestamps, or S3 order for identity.
The plan requires real AWS or private model inspection.
The plan exposes S3 identity or model internals.
The plan introduces polling, promotion, training, scientific metrics,
  or future governance scope.

VALIDATION COMMANDS

The implementation must pass:

git rev-parse --verify HEAD
git branch --show-current
git status --short
python -m compileall src tests
python -m pytest -q
git diff --check

And focused test runs for model package, artifact staging, ModelState,
model catalog, workflow orchestrator, job API, Start page, Control Room,
report, health, API server, concurrency, privacy, and logging tests.

PLAN ARTIFACT

.project-memory/pr/0085-s3-model-catalog-discovery/PLAN.md

Implementation agent: coder
