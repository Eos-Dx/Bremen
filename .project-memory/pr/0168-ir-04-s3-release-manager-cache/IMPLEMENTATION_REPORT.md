# IMPLEMENTATION_REPORT.md — PR0168 IR-04 S3 release manager and verified cache

Status: implementation complete for the local IR-04 gate. Live AWS publication
remains unrun (no authorized access). No model is ACTIVE; the legacy runtime
remains authoritative.

## TASK COMPLETE

One small platform boundary — `bremen.platform.models.release_cache` — turns
the IR-02 catalog reference and the IR-03 release artifacts into a verified,
digest-qualified local installation:

- resolves only the catalog-owned `runtime_release` reference,
- constrains `manifest_key` to the trusted catalog bucket **and prefix**,
- verifies the manifest SHA-256 before trusting its contents,
- fetches only manifest-declared objects (release files, dependency wheels,
  golden fixtures) and verifies key, size, SHA-256 and safe path,
- checks host compatibility before installation,
- enforces cache budget and free-disk admission,
- installs main and auxiliary environments offline from release-local
  wheelhouses,
- runs every release-defined golden case and compares exact expected values,
- writes an atomic READY marker only after all of the above pass,
- serializes concurrent installs per digest,
- evicts only inactive, unprotected READY entries.

## FILES CHANGED

- `src/bremen/release_build/assemble.py` — release-bound wheel closure and
  release-bound golden fixtures; manifest declarations; build counts.
- `src/bremen/platform/models/release_cache.py` — new release manager/cache.
- `tests/test_ir03_plugin_wheel.py` — closure assertions and a synthetic
  release with embedded wheels and a golden fixture.
- `tests/test_ir04_release_cache.py` — 65 tests including the trusted-prefix
  boundary.
- `.project-memory/pr/0168-ir-04-s3-release-manager-cache/IMPLEMENTATION_REPORT.md`
- `.project-memory/pr/0168-ir-04-s3-release-manager-cache/CACHE_INSTALL_EVIDENCE.md`
- `.project-memory/pr/0168-ir-04-s3-release-manager-cache/RELEASE_CLOSURE_EVIDENCE.md`

No scientific code, threshold, preprocessing, QC, feature, training, API,
Docker, CI, infra or contract schema changed.

## FINAL ARCHITECTURE

Trust chain:

```
BREMEN_MODEL_CATALOG_URI
  -> trusted bucket + normalized prefix        (discovery._validate_catalog_uri)
  -> runtime_release.manifest_key inside prefix
  -> trusted manifest SHA-256
  -> verified manifest (bremen.inference-release.v1)
  -> manifest-bound release files, dependency wheels, golden fixtures
  -> release-local offline install
  -> mandatory golden verification
  -> READY
```

Installation is separate from activation. Nothing here mutates catalog
pointers, selects a runtime, supervises a worker or starts a release.

### Release closure

IR-03 assembly copies the exact wheels referenced by each hash-locked file:

```
release/wheelhouse/main/*.whl              role=dependency_wheel
release/wheelhouse/aux/<tag>/*.whl         role=dependency_wheel_aux
release/golden_tests/fixtures/<fixture>    role=golden_fixture
release/golden_tests/cases.json            role=golden_cases
```

Every entry is declared in `manifest.files[]` / `manifest.golden_tests[]` with
relative path, `s3_key`, `size_bytes` and `sha256`. Assembly fails if a lock
hash has no corresponding wheel, so a release can never be built with an
incomplete closure.

`ReleaseCache._verify_wheel_closure` re-proves at install time that every
declared wheel exists and matches its hash, that no undeclared wheel exists in
the release, and that every hash referenced by each lock is present in the
matching release-local directory.

### Trusted manifest digest and prefix

- `manifest_key` comes only from the validated `runtime_release` block.
- Rejected: missing/extra fields, absolute key, `..`, CR/LF, non-hex digest.
- Rejected: any key outside the trusted catalog prefix, including lookalike
  siblings such as `catalog-evil/…`.
- When the configured prefix is empty (root catalog URI), any otherwise-safe
  key in the trusted bucket is allowed.
- The bucket is never a per-call or per-request value.

### Offline installation

Per release: main venv at `<root>/<digest>/env`, auxiliary venvs at
`<root>/<digest>/release/aux/<tag>`, all at their final paths (never moved).
pip runs with `--no-index --only-binary=:all: --require-hashes --find-links
<release-local wheelhouse>`; the plugin wheel installs with `--no-deps`.
Runtime configuration is validated against the manifest afterwards.

### Mandatory golden READY gate

At least one golden case is required. Every case fixture must be a declared,
existing release file. Every case runs through the installed entrypoint, and
the result is compared exactly against the descriptor:

- success: `probability` / `risk_probability`, `threshold_applied` /
  `decision_threshold`, `prediction` / `target_class_risk_level`;
- failure: `status`, `error.code`, and `error.safe_reason` when specified.

Any mismatch, missing fixture or missing case is `smoke_failed`; no READY.

### READY semantics

`<root>/<digest>/READY` is written atomically (temp file + `os.replace`) as the
last install step with `schema_version=bremen.release-ready.v1`, release id,
model id/version, manifest digest, plugin wheel hash, `installed_at`,
`main_python` and `release_dir`. `read_ready` rejects unknown schemas, digest
mismatch, invalid identities, a non-digest interpreter path, a missing
interpreter or a missing release directory — so corrupt markers force a clean
reinstall. A directory without a valid marker is never executable.

### Resource admission

- Every manifest file and golden ref must carry a valid non-negative integer
  `size_bytes` (else `manifest_invalid`).
- Declared bytes must be ≤ `BREMEN_RELEASE_CACHE_MAX_BYTES` (default 8 GiB).
- Free disk must be ≥ `declared × 3 + 16 MiB`.
- `free_space_factor` must be finite and positive.

Admission runs after manifest verification but before any release-object
download, so an impossible install makes no fetches beyond the manifest.

### Eviction

`evict(protected_digests=...)` removes only entries that have a valid READY
marker and are not protected, oldest READY first, until the cache fits the
budget. Partial/in-progress directories and protected digests are never
removed. Staging directories older than one hour are cleaned opportunistically.

## REMOVED EXTERNAL DEPENDENCIES

Normal installation no longer depends on:

- `BREMEN_RELEASE_WHEELHOUSE` (removed entirely)
- `BREMEN_RELEASE_GOLDEN_FIXTURES` (removed entirely)

Configuration is limited to `BREMEN_MODEL_CATALOG_URI`,
`BREMEN_RELEASE_CACHE_ROOT` and `BREMEN_RELEASE_CACHE_MAX_BYTES`.

## REBUILT RELEASES

| Slot | manifest SHA-256 | main wheels | aux wheels | golden files |
|---|---|---|---|---|
| A1 | `12c72fb463a216e16f0feee5ac1196bd293f8844401c3ee737dac66834d35491` | 13 | 54 | 2 |
| A2 | `ec77dfe981224f8fb3ad88aabe93a88e5d4dd7ac9e0a779bec8d0c5b102cf935` | 13 | 54 | 2 |
| B1 | `8f651fc100aceff22fda490b896c4f12569d77678b4a87ff8ca897c8cb7d0e13` | 13 | 0 | 3 |
| B2 | `6f6d5b863e0f9d419dd3bf1f9b3ee098b61d1ba493c34ee981db3280634e88e4` | 13 | 54 | 2 |
| B3 | `ea313396b4bbbef2bea3584ab1ca4f81bba309df4e7968189cb0011ead4f5d17` | 13 | 54 | 2 |

Plugin wheel `029af6c73238cd83d31f1dea31fa52cbbd69f4236e14ba317f076e04affa7e82`;
`main.lock` `5c7127cf…`; aux locks `f0460378…` (v0.1.7-beta) and `c31e23d2…`
(v0.1.9-beta). Artifact hashes unchanged from IR-03. Per-file hashes are in
`RELEASE_CLOSURE_EVIDENCE.md`.

## VALIDATION RESULTS

Environment: `/tmp/bremen-ir01-exec-venv` (Python 3.13.12).

| Command | Result |
|---|---|
| `python3 -m compileall -q src tests` | exit 0 |
| `pytest -q tests/test_ir04_release_cache.py` | **65 passed** |
| `pytest -q tests/test_s3_model_discovery.py tests/test_model_registry.py tests/test_inference_release_contract.py tests/test_worker_protocol_contract.py tests/test_ir04_release_cache.py` | **528 passed** |
| `pytest -q tests/test_ir03_plugin_wheel.py tests/test_ir03_standalone_runtime.py tests/test_ir03_plugin_import_boundary.py` | **59 passed** |
| `pytest -q tests/test_bremen_model_runtime_contract_v1.py tests/test_aramina_v0213_package.py tests/test_aramina_workflow_runtime.py tests/test_bremen_3x3_runtime_parity.py tests/test_ir03_parity.py` | **352 passed** |
| `BREMEN_IR03_RELEASES=/tmp/ir04/releases pytest -q tests/test_ir03_parity.py` | **21 passed** |
| `pytest -q` | **4437 passed, 8 skipped, 40 warnings** |
| `git diff --check` | exit 0 |
| `git status --short` | implementation files + project memory only |
| `git diff --stat` | `assemble.py`, `test_ir03_plugin_wheel.py`, `release_cache.py` (untracked new file), `test_ir04_release_cache.py` (untracked new file) |

Scientific parity is unchanged: the five releases reproduce the IR-01/IR-03
frozen values exactly.

## LIVE S3 STATUS

**NOT RUN - NO AUTHORIZED ACCESS**

No S3 publication, listing, version lookup, credential use or catalog pointer
change was performed, and no AWS result is claimed. S3 was exercised through a
deterministic local stub; pip/venv were real.

## WARNINGS

- Golden cases are mandatory: a release with no golden cases can never become
  READY.
- Exact float equality is intentional; IR-03 parity evidence defines exact
  equality for these fixtures.
- Releases are large (embedded wheels and H5 golden fixtures); admission uses
  the full declared closure.
- Eviction can remain above budget when every remaining entry is protected; it
  never deletes protected or partial entries.
- Non-POSIX hosts fail closed with `lock_unsupported`.
- `matador_raw` remains an unsupported plugin layout (inherited IR-03
  limitation).
- IR-05 (supervisor), IR-06 (App Runner) and activation remain out of scope.
- Live S3 publication/version evidence is still an open operational gate.

## REMAINING BLOCKERS

None for the implemented local IR-04 gate.

## NEXT REQUIRED ACTION

Repeat precommit review.
