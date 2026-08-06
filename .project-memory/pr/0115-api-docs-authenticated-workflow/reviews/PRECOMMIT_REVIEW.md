# PR0115 Precommit Review — Authenticated Bremen API Documentation

VERDICT: approved
READY_FOR_COMMIT: true
READY_FOR_PULL_REQUEST: true

## Summary

PR0115 adds a Swagger-style API reference for the current Bremen technical demo API. The documentation covers all 18 active FastAPI endpoints, the authenticated workflow (login → containers → models → create job → status → events → SSE ticket → report ticket), and includes a runnable production smoke script. All examples use placeholders — no real secrets, tokens, or credentials are committed. The docs accurately describe the current implemented/deployed API flow.

## Files Reviewed

- docs/API.md (new)
- docs/api/auth.md (new)
- docs/api/models-and-containers.md (new)
- docs/api/jobs.md (new)
- docs/api/events-and-sse.md (new)
- docs/api/reports.md (new)
- docs/api/errors-and-troubleshooting.md (new)
- docs/api/examples/token-request.json (new)
- docs/api/examples/create-job.json (new)
- docs/api/examples/smoke-production.sh (new)
- README.md (modified — added API documentation link section)
- .project-memory/pr/0115-api-docs-authenticated-workflow/CODER_REPORT.md (new)

## Source Cross-Checks

Verified docs against implementation:

- `POST /demo/api/jobs` is the current submit endpoint (fastapi_app.py line 302).
- `POST /demo/api/jobs/{job_id}/auth/ticket` exists (fastapi_app.py line 1102).
- `GET /demo/api/jobs/{job_id}/events/stream` exists (fastapi_app.py line 1167).
- `GET /demo/report/{job_id}` exists (fastapi_app.py line 587).
- `POST /demo/api/auth/token` and `POST /demo/api/auth/refresh` exist (fastapi_app.py lines 644, 705).
- `create_stream_ticket` / `decode_stream_ticket` / `TicketClaims` exist in auth.py.
- `_authFetchTicket`, `connectSSE`, `openJob` with `auth_ticket` query param exist in control_room_ui.py.
- Error messages "Multiple available models — model_id is required." and "The selected source has already been used." exist in source (model_catalog.py, source_registry.py).

## Documentation Accuracy

All 15 key facts verified correct:

1. ✅ Current submit endpoint is `POST /demo/api/jobs`.
2. ✅ `/predictions` is documented as **not** the current production submit route (only in troubleshooting, with fix to use `POST /demo/api/jobs`).
3. ✅ `/openapi.json` is documented as not exposed in production (both API.md and troubleshooting).
4. ✅ Auth token endpoint is `POST /demo/api/auth/token`.
5. ✅ Protected API calls use `Authorization: Bearer $ACCESS`.
6. ✅ Native EventSource uses short-lived `auth_ticket` (cannot send Authorization headers).
7. ✅ Direct report navigation uses short-lived `auth_ticket` (browser navigation cannot attach headers).
8. ✅ Ticket mint endpoint is `POST /demo/api/jobs/{job_id}/auth/ticket`.
9. ✅ Ticket purpose is exactly `stream` or `report`.
10. ✅ Ticket response documents `expires_in=60`, `token_type=stream_ticket`, `job_id`, `purpose`.
11. ✅ Job creation includes `model_id` when multiple models are available.
12. ✅ `job_id` extraction uses `.job.job_id` (documented as nested, with fallback chain).
13. ✅ Rerun/source guard documented: "The selected source has already been used. Please select another container."
14. ✅ Successful smoke is clearly marked as technical-demo evidence, not clinical validation.
15. ✅ Decision language is safe: `MRI_REVIEW_DEFER` = "Defer MRI pending clinician review". Not "no MRI needed"; not "cancer ruled out".

## Endpoint Coverage

All 18 active FastAPI endpoints documented with method, path, auth, request/response examples, and errors. Browser-only routes (GET /demo/api-docs, /demo/login, etc.) noted as UI/browser routes.

## Auth and Ticket Flow Review

- Auth token/refresh flow documented correctly.
- Bearer header usage documented correctly.
- Ticket minting endpoint documented with purpose validation.
- SSE fallback with `auth_ticket` documented.
- Report fallback with `auth_ticket` documented.
- Access/refresh tokens never appear in URLs (only `auth_ticket`).

## Smoke Example Review

- `docs/api/examples/smoke-production.sh` is runnable (bash -n passes).
- Reads credentials interactively — no hardcoded secrets.
- Uses placeholders for all tokens.
- Extracts `JOB_ID` from `.job.job_id` with fallback chain.
- Includes `model_id` in create-job payload.
- Mints stream and report tickets correctly.
- Uses `auth_ticket` query param for SSE and report navigation.
- Clearly marked as technical-demo evidence.

## Safety Language Review

- No "detects cancer", "diagnoses", "diagnosis engine", "replaces clinician", "FDA approved", or "clinically certified" claims in new docs.
- Consistent "technical demo only", "decision-support", "clinician review" framing.
- `MRI_REVIEW_DEFER` = "Defer MRI pending clinician review" — safe language.
- Report is described as "decision-support communication artifact, not a diagnosis".

## Secret-Leak Review

- No leaked JWT tokens (`eyJ...` pattern) in docs.
- No `auth_ticket=.*eyJ` patterns.
- No `BREMEN_AUTH_JWT_SECRET=...` values.
- No access/refresh tokens in URLs.
- All examples use placeholders (`<ACCESS_TOKEN>`, `<SOURCE_ID>`, etc.).
- JSON examples are valid and use placeholders.

## Validation Commands

- `git diff --check`: clean
- `find docs -maxdepth 4 -type f | sort`: all expected files present
- `test -f` for all 10 expected docs files: all present
- `jq .` on both JSON examples: valid
- `bash -n docs/api/examples/smoke-production.sh`: syntax valid
- `grep -RInE 'eyJ[a-zA-Z0-9_-]{20,}' docs README.md`: 0 hits
- `grep -RInEi 'detects cancer|diagnoses|...' docs/API.md docs/api/`: 0 hits in new docs
- `grep -RIn "auth_ticket=.*eyJ" docs README.md`: 0 hits
- `grep -RIn "BREMEN_AUTH_JWT_SECRET=.*" docs README.md`: 0 hits
- `/predictions` only in troubleshooting, explicitly marked as not current

## Findings

No blocking findings. All documentation accurately reflects the current implemented API.

## Required Changes

None.

## Warnings

- Pre-existing files (`docs/adr/0008-two-image-build-training-pipeline-separation.md`, `docs/repository_cleanup.md`) contain the word "diagnoses" in safe negation/context framing. These are NOT part of this PR and are not unsafe claims.

## Final Decision

Approved. This PR would let a new engineer reproduce the successful production smoke without asking for route names or payload shape, while staying inside safe technical-demo / decision-support language.
