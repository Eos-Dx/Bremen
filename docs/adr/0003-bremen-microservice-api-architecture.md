# ADR-0003: Bremen Microservice / API Architecture

**Status**: Accepted

## Decisions

Bremen runtime is a containerized AWS microservice with API endpoints, extending (not replacing) the core chain already in `docs/architecture.md`:

> Matador → Bremen API → H5 inspect gate → preprocessing/feature extraction → joblib inference → QC → prediction JSON → Matador storage/report layer

### Minimum endpoint skeleton (sketch only, not a final contract)

- `POST /predictions` — Submit target/control H5 references. Returns `job_id` or full result depending on Gate G-API-1 resolution.
- `GET /predictions/{id}` — Retrieve prediction result by ID.
- `GET /health` — Health check endpoint.
- `GET /model/version` — Current model version metadata.

### Mandatory prediction response fields

Every prediction response must carry these fields, restated verbatim from the Project Contract Invariant Inventory in `project_contract.yml`:

- `prediction_id`
- `model_version`
- `model_checksum`
- `feature_schema_version`
- threshold version/value
- `qc_status`
- `qc_flags`

### Runtime must not train models

Restated as an API-level constraint: the runtime microservice exposes prediction/health endpoints only. Training is a separate offline workflow.

### Not a final contract

This ADR does NOT create `docs/api_contract.md`. The full API contract is delegated to PR 0019.

## OPEN Decision Gates (explicitly revisable, not final)

| Gate ID | Question | Trigger type | Recommended default | Status |
|---------|----------|-------------|-------------------|--------|
| G-API-1 | Sync request/response vs. async submit-then-poll | Date-bound (before PR 0019) | Async submit-then-poll (latency is uncharacterized) | OPEN |
| G-API-2 | AWS compute target (ECS Fargate vs. Lambda-container vs. EKS) | Date-bound (before PR 0019, PR 0022) | ECS Fargate (reuses existing Dockerfile) | OPEN |
