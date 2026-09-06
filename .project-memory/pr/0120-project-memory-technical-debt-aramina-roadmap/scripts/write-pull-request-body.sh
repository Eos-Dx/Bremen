#!/usr/bin/env bash
set -euo pipefail

PR_DIR=".project-memory/pr/0120-project-memory-technical-debt-aramina-roadmap"
mkdir -p "$PR_DIR"

cat > "$PR_DIR/PULL_REQUEST_BODY.txt" <<'TXT'
SUMMARY

This PR records Bremen technical debt and the forward roadmap in .project-memory.

It adds plain text project-memory documents for:

- Bremen technical debt;
- Bremen future roadmap;
- Aramina integration roadmap.

The most important decision captured here is that Aramina integration must start now and must be treated as a separate model family/workflow, not as another hardcoded Bremen route.

WHAT CHANGED

Added:

.project-memory/technical-debt/BREMEN_TECHNICAL_DEBT.txt
.project-memory/roadmap/BREMEN_FUTURE_ROADMAP.txt
.project-memory/roadmap/ARAMINA_INTEGRATION_ROADMAP.txt

Added helper scripts under:

.project-memory/pr/0120-project-memory-technical-debt-aramina-roadmap/scripts/

ROADMAP DECISIONS RECORDED

1. Add exactly two planned model requirements endpoints first:

GET  /demo/api/models/{model_id}/requirements
POST /demo/api/models/{model_id}/requirements/validate

2. Start them as honest no-op stubs.

The platform should not invent H5 requirement fields until the runner/preprocessing layer can declare them.

3. Begin Aramina integration now.

Aramina should be represented as a separate model family/workflow.

4. Stop treating workflow_id as a permanent global constant.

The SDK/backend should resolve the selected model row from GET /demo/api/models and use model["workflow_id"] for routing.

5. Keep model_version as audit/provenance.

The client should not send model_version for normal job creation.

DEPLOYED VS PLANNED API

This PR records that the currently deployed API is still the existing Bremen production API.

The following endpoints are planned and should not be treated as deployed production SDK calls until implemented:

GET  /demo/api/models/{model_id}/requirements
POST /demo/api/models/{model_id}/requirements/validate

NON-GOALS

No source code changes.

No API implementation.

No SDK implementation.

No deployment changes.

No production configuration changes.

No clinical claims.

No claim that requirements endpoints are currently deployed.

VALIDATION

Docs-only validation expected:

git diff --check
git diff --cached --check
git diff --cached --stat
git status --short

SECURITY AND CLAIMS

No access tokens, refresh tokens, passwords, signed URLs, patient-identifiable data, or production secrets are added.

The documents preserve technical-demo wording and do not claim diagnosis, clinical validation, CE/FDA status, or deployed future endpoints.
TXT

echo "Wrote $PR_DIR/PULL_REQUEST_BODY.txt"
