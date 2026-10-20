# Source audit and limits

Inspected repository: Eos-Dx/Bremen, snapshot `1b08958fe75dda822f02f725e606d5cd4737da01`, 2026-10-20. Links below are immutable. Documentation describes repository behavior at that snapshot, not a live deployment inspection.

Aramina analysis here is of the Aramina runtime integrated into Bremen, which is the service being migrated. This is not an audit of the entire separate Eos-Dx/Aramina training repository. No live S3 catalog, private model binaries or deployed environment were available for this documentation pass; those remain IR-01 evidence requirements.

| Source | Finding |
|---|---|
| [src/bremen/platform/models/discovery.py](https://github.com/Eos-Dx/Bremen/blob/1b08958fe75dda822f02f725e606d5cd4737da01/src/bremen/platform/models/discovery.py) | Immediate-child catalog scanning, strict manifest handling, parent Bremen artifact loading and Aramina deferred artifact loading. |
| [src/bremen/platform/runtime/registry.py](https://github.com/Eos-Dx/Bremen/blob/1b08958fe75dda822f02f725e606d5cd4737da01/src/bremen/platform/runtime/registry.py) | Two family factories and descriptor adapters; not a five-model inventory. |
| [src/bremen/platform/runtime/executor.py](https://github.com/Eos-Dx/Bremen/blob/1b08958fe75dda822f02f725e606d5cd4737da01/src/bremen/platform/runtime/executor.py) | Validation, source binding, feature callbacks, projection and failure mapping. |
| [src/bremen/contracts/model_runtime.py](https://github.com/Eos-Dx/Bremen/blob/1b08958fe75dda822f02f725e606d5cd4737da01/src/bremen/contracts/model_runtime.py) | Requirements, ModelInput and prediction contract to preserve through explicit serialization. |
| [src/bremen/model_packages/bremen_v01/runtime.py](https://github.com/Eos-Dx/Bremen/blob/1b08958fe75dda822f02f725e606d5cd4737da01/src/bremen/model_packages/bremen_v01/runtime.py) | Raw-H5 paper-reference versus legacy paths; namespace is not deployed identity. |
| [src/bremen/model_packages/bremen_v01/predictor.py](https://github.com/Eos-Dx/Bremen/blob/1b08958fe75dda822f02f725e606d5cd4737da01/src/bremen/model_packages/bremen_v01/predictor.py) | Portable logistic inference and artifact adaptation semantics. |
| [src/bremen/model_packages/bremen_v01/preprocessing.py](https://github.com/Eos-Dx/Bremen/blob/1b08958fe75dda822f02f725e606d5cd4737da01/src/bremen/model_packages/bremen_v01/preprocessing.py) | Existing separate preprocessing environment. |
| [src/bremen/model_packages/aramina_v0213/runtime.py](https://github.com/Eos-Dx/Bremen/blob/1b08958fe75dda822f02f725e606d5cd4737da01/src/bremen/model_packages/aramina_v0213/runtime.py) | Entry-driven Aramina runtime shared by variant identities. |
| [src/bremen/model_packages/aramina_v0213/artifact_compat.py](https://github.com/Eos-Dx/Bremen/blob/1b08958fe75dda822f02f725e606d5cd4737da01/src/bremen/model_packages/aramina_v0213/artifact_compat.py) | Distinct legacy and target-breast compatibility classes. |
| [src/bremen/model_packages/aramina_v0213/inference.py](https://github.com/Eos-Dx/Bremen/blob/1b08958fe75dda822f02f725e606d5cd4737da01/src/bremen/model_packages/aramina_v0213/inference.py) | Artifact checks, canonical validation, raw preprocessing and scientific chain. |
| [src/bremen/model_packages/aramina_v0213/preprocessing.py](https://github.com/Eos-Dx/Bremen/blob/1b08958fe75dda822f02f725e606d5cd4737da01/src/bremen/model_packages/aramina_v0213/preprocessing.py) | Version-selected preprocessing environments; mapping must be read from artifacts. |
| [src/bremen/platform/jobs/service.py](https://github.com/Eos-Dx/Bremen/blob/1b08958fe75dda822f02f725e606d5cd4737da01/src/bremen/platform/jobs/service.py) | Thread-pool orchestration; process isolation is not already provided for the full chain. |
| [Dockerfile](https://github.com/Eos-Dx/Bremen/blob/1b08958fe75dda822f02f725e606d5cd4737da01/Dockerfile) | Python 3.13 base and embedded preprocessing environments. |
| [pyproject.toml](https://github.com/Eos-Dx/Bremen/blob/1b08958fe75dda822f02f725e606d5cd4737da01/pyproject.toml) | Single application wheel and broad dependency constraints. |
| [.github/workflows/ecr-publish.yml](https://github.com/Eos-Dx/Bremen/blob/1b08958fe75dda822f02f725e606d5cd4737da01/.github/workflows/ecr-publish.yml) | Existing container publication; no proof of independent inference release publishing. |
| [docs/production-contracts-2026-09-18.md](https://github.com/Eos-Dx/Bremen/blob/1b08958fe75dda822f02f725e606d5cd4737da01/docs/production-contracts-2026-09-18.md) | Historical Aramina identities and a Bremen identity, not a current complete inventory. |
| [docs/mlflow_model_packaging_spike.md](https://github.com/Eos-Dx/Bremen/blob/1b08958fe75dda822f02f725e606d5cd4737da01/docs/mlflow_model_packaging_spike.md) | Research proposal, not implemented MLflow packaging or a mandatory serving dependency. |
| [docs/model_architecture_roadmap_0157_0162.md](https://github.com/Eos-Dx/Bremen/blob/1b08958fe75dda822f02f725e606d5cd4737da01/docs/model_architecture_roadmap_0157_0162.md) | Historical sequencing superseded by this rebaseline. |

## Planning conclusions

The repository already moved toward ModelRuntime and model-package ownership; this is a continuation, not a from-scratch rewrite. Existing preprocessing subprocesses are useful prior art, but the full platform/scientific dependency boundary is not yet a standalone S3 release. Historical architecture plans, implemented refactors and current production contracts must not be conflated.

The root package now uses lazy loading; do not repeat the old MLflow spike's eager-root-import concern as an unverified current blocker. The spike did not establish a tested production MLflow packaging path. Existing ADR/result semantics remain useful independently of packaging technology.

No runtime tests, production predictions, deployment actions or parity certifications were performed by generating this documentation. Package checks cover only document structure, baseline preservation and archive integrity.
