# ADR-0007: Model Artifact Lifecycle

**Status**: Accepted

## Context

- Application Docker image and model package have different release cycles.
- Application image contains service code and inference wrapper logic.
- Model package contains trained joblib artifact and metadata.
- Runtime service must not train models.
- joblib is not built by the normal application Docker image CI/CD pipeline.

## Decision

- Bremen will use a separate, controlled, checksum-verified model package lifecycle.
- Offline training pipeline creates model packages.
- Runtime service loads only approved checksum-verified model packages.
- Initial model artifact store is an S3 versioned bucket.
- Docker image registry and model artifact store are separate.

## Model package contents

A controlled model package must include at minimum:

- joblib model artifact
- `model_version`
- `model_checksum`
- `feature_schema_version`
- threshold version/value
- QC criteria metadata
- training/config provenance reference
- creation timestamp
- checksum manifest

## Runtime loading rules

- Runtime resolves configured `model_version` or model package reference.
- Runtime loads only checksum-verified packages.
- Runtime verifies feature schema compatibility before inference.
- Runtime fails closed on package/checksum/schema/metadata validation failure.
- Runtime never builds, retrains, mutates, or overwrites model artifacts.

## Security note for joblib.load()

`joblib.load()` uses pickle deserialization and can execute arbitrary code. The following rules apply:

- Checksum verification is a security boundary **only if** the checksum is computed at the training-pipeline trust boundary.
- Checksum must not be derived post-hoc from the stored artifact by the runtime.
- Checksum manifest write access must be restricted separately from model artifact read access.
- Model artifact read access alone must not allow checksum manifest modification.
- Runtime must load only from trusted, checksum-verified, approved model packages.

## Relationship to CI/CD

- Application CI/CD builds/tests/publishes service image.
- Model package release pipeline builds/tests/publishes model artifact.
- Updating a model must not require rebuilding the application image unless application code changes are also required.
- Updating application image must not silently change `model_version`.

## Relationship to prediction API

Every prediction response must include:

- `prediction_id`
- `model_version`
- `model_checksum`
- `feature_schema_version`
- threshold version/value
- `qc_status`
- `qc_flags`

## Non-goals

- No source code.
- No CI YAML.
- No Terraform/IaC.
- No API contract.
- No model artifact.
- No training implementation.
- No publication pipeline implementation.
