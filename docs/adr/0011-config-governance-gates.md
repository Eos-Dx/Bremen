# ADR-0011: Config Governance Gates

**Status**: Decided

**Drift audit / gates PR**: PR0051

**G-CFG-1**: DECIDED — lightweight in-repo governance; no external config platform.
**G-CFG-2**: DEFERRED — no DynamoDB/backend until Matador/system-of-record boundary.
**G-CFG-3**: DECIDED — validation gates as repository tests/static checks using existing Python/pytest infrastructure; no new validation dependency.

---

## Context

Bremen has multiple config surfaces (runtime, training, preprocessing, model
package, deployment). Each surface has different validation needs and
lifecycle requirements. The previous ADR-0009 identified three open gates
(G-CFG-1, G-CFG-2, G-CFG-3) that needed resolution.

PR0051 resolves these three gates. It does not implement backend
persistence, DynamoDB, or Matador integration — those are separately
tracked in PR0052 (Matador boundary / system-of-record adapter skeleton)
and subsequent platform work.

---

## Decision

### G-CFG-1: Build vs. adopt config management product

**DECIDED**: Bremen uses lightweight in-repo config governance for now.

No external config platform (Consul, Vault, etcd, AWS AppConfig, or any
third-party product) is adopted in PR0051. Config validation is implemented
through Python/pytest static gates and ADR documentation.

Rationale:
- The project is in early platform-readiness phase. A full config management
  platform would be premature until runtime operations workload justifies it.
- In-repo governance is sufficient for current needs: synthetic configs,
  explicit schema checks, and documented taxonomy.
- A future shift to an external platform will be re-evaluated when
  Matador/system-of-record boundary work (PR0052) clarifies the ops
  contract.

### G-CFG-2: Config state history store

**DEFERRED**: No DynamoDB, database, or backend persistence is implemented
in PR0051.

Persistence backend decisions are deferred until the Matador/system-of-record
boundary is defined (planned PR0052). At that point the data model,
consistency requirements, and operational load will be clearer.

Until then, all config state is:
- Static files in `config/` (YAML, TOML).
- Environment variables consumed at runtime startup.
- Synthetic configs for tests (no real artifact paths).

### G-CFG-3: Config validation schema

**DECIDED**: Validation gates are repository tests and static checks using
existing Python/pytest infrastructure. No new validation dependency is added.

Gates include:
- Existence checks for required ADR documents.
- Surface taxonomy checks that each config surface is documented.
- Runtime config env-var key inventories.
- Model package required metadata checks.
- Training/runtime import separation checks (existing).
- Safety checks that config and test files do not contain secrets, account
  IDs, registry URLs, or raw sensitive paths.

All gates run via `pytest` in CI. No TOML/JSON Schema library, Pydantic
model, or custom validator is added beyond the standard library and existing
project dependencies.

---

## Config Surface Taxonomy

Bremen has the following config surfaces, each with distinct governance:

| Surface | Location / mechanism | Governance gate | Lifecycle |
|---|---|---|---|
| Runtime config | Environment vars (`BREMEN_*`) at container startup | Inventory check; safe boolean exposure via `model_uri_configured`, `checksum_configured` | Per-deployment |
| Model artifact metadata | `manifest.json` in model package (`model_package.py` validation) | Full manifest validation; checksum verification | Per-model-version |
| Preprocessing config | `config/preprocessing/*.yaml` | Static existence / taxonomy check | Offline only; not consumed by runtime |
| Training config | `config/training/*.yaml` (referenced in `config/training/` directory) | Required fields validation in training pipeline | Offline only |
| Deployment config | `infra/terraform/`, environment vars | Not in PR0051 scope | Ops-owned |
| Test-only synthetic config | Inline in `tests/` or `tmp_path` YAML files | No real artifact paths; no secrets | Test lifecycle only |

---

## Validation Gates

Implemented in `tests/test_bremen_config_governance.py`:

1. ADR-0011 exists and records G-CFG-1, G-CFG-2, G-CFG-3 decisions.
2. ADR-0011 records lightweight in-repo governance (G-CFG-1).
3. ADR-0011 records no DynamoDB/backend until Matador boundary (G-CFG-2).
4. ADR-0011 records validation gates as repo tests/static checks (G-CFG-3).
5. Config surface taxonomy is documented (6 surfaces).
6. Runtime model env keys are inventoried (`BREMEN_MODEL_VERSION`,
   `BREMEN_MODEL_URI`, `BREMEN_MODEL_CHECKSUM`, `BREMEN_MODEL_STAGING_DIR`).
7. Model package required metadata is explicit (from `model_package.py`).
8. Training config remains offline-only; runtime does not import training.
9. Preprocessing config is distinct from runtime model readiness config.
10. Config surfaces do not include real artifact files.
11. Config docs/tests do not contain account IDs, registry URLs, full S3
    URIs, raw patient identifiers, raw scan refs, or local-machine paths.
12. Runtime config loading does not depend on local machine paths.
13. Model source/API leakage remains safe (raw URI/checksum are bools in
    API response, not raw strings).
14. PR0052 Matador integration is not implemented by PR0051.
15. FastAPI remains deferred.
16. DynamoDB/backend is mentioned only as deferred, never imported/used.

---

## Boundaries and Non-Goals

- **No FastAPI.** PR0051 does not add FastAPI, uvicorn, starlette, or any
  web framework. FastAPI remains a later thin transport adapter (deferred).
- **No Matador integration.** PR0052 is the Matador boundary PR. PR0051
  defers to PR0052.
- **No DynamoDB/backend implementation.** G-CFG-2 is explicitly deferred.
- **No new dependencies.** All gates use existing Python/pytest infrastructure.
- **No runtime source changes.** PR0051 is docs/tests/config only.
- **No model lifecycle changes.** Runtime model loading, checksum boundary,
  S3 staging, and startup-only loading are unchanged.
- **No training behavior changes.** Training config validation already exists
  in `pipeline.py`. PR0051 adds only a boundary check that runtime does not
  import training.
- **No preprocessing changes.** Preprocessing config taxonomy is documented;
  preprocessing math and schema are unchanged.

---

## Consequences

### Positive

1. Three previously open governance gates are now resolved (two decided, one
   explicitly deferred).
2. Config surface taxonomy is documented, making it clear which configs are
   runtime-sensitive vs. offline-only.
3. Static test gates provide automated enforcement of governance decisions.
4. Safety gates prevent sensitive data from appearing in config/docs/test
   files.
5. No new dependencies added — all gates use existing `pytest` + standard
   library.
6. Matador and FastAPI remain explicitly out of scope, preventing scope
   creep.

### Negative

1. Config governance is limited to what can be checked in static analysis
   and ADR documentation. Runtime config drift (e.g., env var set to wrong
   value at deployment time) is not caught by PR0051 — that requires
   runtime validation or a future config agent.
2. Deferred G-CFG-2 means config state history is not tracked. Operators
   must rely on deployment logs and environment variable snapshots.
3. The in-repo governance model assumes disciplined commit/review practice.
   A config change bypassing review could violate governance until the
   next CI run.

### Mitigations

- CI runs all governance gates on every PR. Violations are visible before
  merge.
- The config surface taxonomy and env-var inventory make future automation
  (e.g., runtime config agent) easier to design.
- G-CFG-2 deferral is explicitly documented in ROADMAP.md and ADR-0011,
  so it will not be silently dropped.
