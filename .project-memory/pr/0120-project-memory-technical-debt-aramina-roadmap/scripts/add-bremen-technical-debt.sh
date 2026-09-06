#!/usr/bin/env bash
set -euo pipefail

mkdir -p .project-memory/technical-debt

cat > .project-memory/technical-debt/BREMEN_TECHNICAL_DEBT.txt <<'TXT'
BREMEN TECHNICAL DEBT

Status:
Active technical debt register.

Purpose:
Record current Bremen integration gaps so they are not forgotten during Aramina work and future model requirements API work.

CURRENT PRODUCTION BASELINE

Current deployed API:

POST /demo/api/auth/token
GET  /demo/api/models
GET  /demo/api/h5/containers
POST /demo/api/jobs
GET  /demo/api/jobs/{job_id}
GET  /demo/api/jobs/{job_id}/events
GET  /demo/api/reports/{job_id}/external
GET  /demo/api/jobs/{job_id}/reports/bremen
POST /demo/api/jobs/{job_id}/auth/ticket

Current production job creation contract:

{
  "container_id": "<display-or-filename>.h5",
  "source_id": "<fresh source_id from GET /demo/api/h5/containers>",
  "workflow_id": "<workflow_id from selected model/catalog row>",
  "model_id": "<selected model_id>"
}

Important:
source_id must be fresh from GET /demo/api/h5/containers.

display_name is metadata and may repeat.

display_name may come from H5 patient metadata, not from the S3 filename.

stable_source_key is returned by catalog but is not currently the launch field for POST /demo/api/jobs.

TECHNICAL DEBT ITEMS

TD-001: Model requirements endpoints are not deployed yet.

Planned endpoints:

GET  /demo/api/models/{model_id}/requirements
POST /demo/api/models/{model_id}/requirements/validate

These endpoints must not be documented as deployed production API until they return non-404 in production.

TD-002: Raw H5 requirement fields are not declared by the model/runner yet.

Do not invent fields such as height, weight, age, or other required patient fields unless they are actually declared by the runner/preprocessing layer.

Correct future source of truth:

model_id
-> workflow runner
-> preprocessing bridge
-> H5 normalization
-> generated features

TD-003: Requirements endpoints should start as honest no-op stubs.

GET requirements should return:

requirements_available=false
status=requirements_not_declared

POST requirements/validate should return:

validation_available=false
validation.status=not_available
ready_to_run=null
inference_job_created=false
report_created=false

TD-004: H5 catalog resolution is not yet ideal for external integration.

Current path:

GET /demo/api/h5/containers
-> filter catalog
-> extract fresh source_id
-> POST /demo/api/jobs

This is acceptable for smoke testing but not ideal for an external platform.

Future path should use stable catalog-backed container identity.

TD-005: workflow_id must not remain a global assumption.

Current Bremen models use workflow_id=bremen.

Aramina will likely use workflow_id=aramina.

SDK/backend code must take workflow_id from the selected model catalog row.

TD-006: model_version is audit/provenance only.

The client should not send model_version for normal job creation.

Persist model_version when Bremen returns it in job/report results.

TD-007: Aramina integration must start now.

Aramina should be added as a separate model family/workflow.

Do not route Aramina jobs into Bremen by accident.

Do not mark Aramina as available until its runner path exists.

IDENTIFIER RULES

model_id:
Client-controlled model selection key.

workflow_id:
Bremen runtime routing key.

model_version:
Concrete artifact/build that actually ran; audit/provenance only.

Rule:

model_id       = client selection
workflow_id    = runtime routing
model_version  = audit/provenance

SECURITY AND CLAIMS

Do not log raw access tokens.

Do not log raw refresh tokens.

Do not put long-lived tokens in URLs.

Report/workspace/stream tickets are short-lived and job-bound.

Do not claim clinical validation.

Do not claim diagnosis.

Do not claim deployed endpoints that still return 404.
TXT

echo "Wrote .project-memory/technical-debt/BREMEN_TECHNICAL_DEBT.txt"
