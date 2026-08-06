# CODER REPORT — PR0115 Document the authenticated Bremen API workflow

## TASK COMPLETE

Yes.

## FILES CHANGED

| File | Status | Description |
|------|--------|-------------|
| `docs/API.md` | NEW | Main entry point — endpoint overview, workflow summary, smoke summary |
| `docs/api/auth.md` | NEW | Auth token and refresh documentation |
| `docs/api/models-and-containers.md` | NEW | Model catalog and H5 container listing |
| `docs/api/jobs.md` | NEW | Job creation, listing, and status |
| `docs/api/events-and-sse.md` | NEW | Event log, ticket minting, SSE streaming |
| `docs/api/reports.md` | NEW | Report JSON and HTML page access |
| `docs/api/errors-and-troubleshooting.md` | NEW | Common errors and fixes |
| `docs/api/examples/token-request.json` | NEW | Example login payload |
| `docs/api/examples/create-job.json` | NEW | Example job creation payload |
| `docs/api/examples/smoke-production.sh` | NEW | Runnable production smoke script |
| `README.md` | UPDATED | Added API documentation link section |

## SUMMARY

Created a Swagger-style API reference for the current Bremen technical demo API.
All 18 active FastAPI endpoints are documented. Examples use placeholders
(`<ACCESS_TOKEN>`, `<SOURCE_ID>`, etc.) — no real secrets committed.

The documentation is standalone (does not depend on `/openapi.json`, which
returns 404 in production). It covers:
- Authentication flow (token + refresh)
- Model catalog and H5 container listing
- Job creation, status, and event polling
- SSE streaming with short-lived purpose-bound tickets
- Report JSON and HTML page access with purpose-bound tickets
- Common errors and troubleshooting
- A runnable production smoke script

## CURRENT API WORKFLOW DOCUMENTED

1. Login → Bearer token
2. List H5 containers (Bearer)
3. List models (no auth)
4. Create job with source_id + model_id (Bearer)
5. Read job status (Bearer)
6. Read event log (Bearer)
7. Mint stream ticket (Bearer)
8. Open SSE with auth_ticket query param
9. Mint report ticket (Bearer)
10. Open HTML report with auth_ticket query param

## ENDPOINTS DOCUMENTED

All 18 endpoints confirmed present in `src/bremen/api/fastapi_app.py`:
- POST /demo/api/auth/token
- POST /demo/api/auth/refresh
- GET /demo/api/models
- GET /demo/api/h5/containers
- POST /demo/api/h5/containers
- POST /demo/api/jobs
- GET /demo/api/jobs
- GET /demo/api/jobs/{job_id}
- GET /demo/api/jobs/{job_id}/events
- POST /demo/api/jobs/{job_id}/auth/ticket
- GET /demo/api/jobs/{job_id}/events/stream
- GET /demo/api/jobs/{job_id}/reports
- GET /demo/api/jobs/{job_id}/reports/{workflow_id}
- GET /demo/api/reports/{job_id}/external
- GET /demo/api/reports/{job_id}/internal
- GET /demo/report/{job_id}
- GET /health
- GET /model/version

Plus browser-only routes (GET /demo/api-docs, GET /demo/login, etc.) noted
as UI/browser routes without full endpoint cards.

## EXAMPLES ADDED

- `docs/api/examples/token-request.json` — valid JSON with placeholder
- `docs/api/examples/create-job.json` — valid JSON with placeholder
- `docs/api/examples/smoke-production.sh` — runnable script, reads credentials
  interactively, no hardcoded secrets

## SAFETY LANGUAGE CONFIRMED

- All examples use placeholders: `<ACCESS_TOKEN>`, `<REFRESH_TOKEN>`,
  `<STREAM_TICKET>`, `<REPORT_TICKET>`, `<USERNAME>`, `<PASSWORD>`,
  `<SOURCE_ID>`, `<JOB_ID>`, `<MODEL_ID>`
- No real tokens, secrets, or passwords in any file
- `grep -RInE 'eyJ[a-zA-Z0-9_-]{20,}'` found 0 hits in docs
- Safety framing consistently uses: "technical demo only", "decision-support",
  "probability score", "MRI continuation / deferral review support",
  "clinician review"
- No "detects cancer", "diagnoses", "replaces clinician", "FDA approved",
  or "clinically certified" claims in new files
- Existing hits for "diagnoses" in docs/ are in files that say
  "No claim that Bremen diagnoses disease" (safe framing)

## LEGACY /predictions HANDLING

Only mentioned in `docs/api/errors-and-troubleshooting.md` as a troubleshooting
entry:
> `/predictions` is **not** the current production submit route.
> Use `POST /demo/api/jobs`.

This is the intended treatment per the task spec.

## OPENAPI / Swagger NOTE

`/openapi.json` returns 404 in production. The documentation uses
"Swagger-style reference" wording (not "OpenAPI-generated reference").
This is honest about the source of the documentation.

## VALIDATION RUN

```
git diff --check                           → PASS (no issues)
git status --short                         → clean (new files + README.md)
find docs -maxdepth 4 -type f | sort       → all expected files present
for f in docs/api/examples/*.json; jq .    → both JSON files valid
bash -n docs/api/examples/smoke-production.sh → syntax valid
grep -RInE 'eyJ[a-zA-Z0-9_-]{20,}' docs   → 0 hits (no leaked tokens)
grep -RInEi 'detects cancer|...' docs      → 0 hits in new files
grep -RIn "/predictions" docs/API.md       → 0 hits (only in troubleshooting)
```

## WARNINGS

None.

## READY FOR REVIEW

Yes.
