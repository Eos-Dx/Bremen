# Bremen API Reference

> **Technical demo only.** Bremen returns a decision-support probability score
> and report. Bremen does not diagnose disease and does not replace clinician
> judgment.

## Base URL

Production technical demo:

```
https://bremen.matur.co.uk:443
```

Local development (if running locally):

```
http://localhost:8000
```

## Current Workflow Summary

The validated production workflow (as of the 2025-08-05 smoke) follows these steps:

1. **Login** and receive a Bearer access token.
2. **List H5 containers** available for analysis.
3. **List available models** (no auth required).
4. **Create an analysis job** with a `source_id` and `model_id`.
5. **Read job status** to confirm completion.
6. **Read event log** for pipeline trace.
7. **Mint a short-lived stream ticket** for SSE access.
8. **Open SSE stream** with `auth_ticket` query parameter.
9. **Mint a short-lived report ticket** for browser navigation.
10. **Open the HTML report** with `auth_ticket` query parameter.

## Endpoint Overview

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/demo/api/auth/token` | None | Issue access + refresh tokens |
| `POST` | `/demo/api/auth/refresh` | None | Refresh an access token |
| `GET` | `/demo/api/models` | None | List available models |
| `GET` | `/demo/api/h5/containers` | Bearer | List H5 containers |
| `POST` | `/demo/api/h5/containers` | Bearer | Upload an H5 file |
| `POST` | `/demo/api/jobs` | Bearer | Create an analysis job |
| `GET` | `/demo/api/jobs` | Bearer | List recent jobs |
| `GET` | `/demo/api/jobs/{job_id}` | Bearer | Get job status and traces |
| `GET` | `/demo/api/jobs/{job_id}/events` | Bearer | JSON event log |
| `POST` | `/demo/api/jobs/{job_id}/auth/ticket` | Bearer | Mint a short-lived ticket |
| `GET` | `/demo/api/jobs/{job_id}/events/stream` | Bearer or ticket | SSE event stream |
| `GET` | `/demo/api/jobs/{job_id}/reports` | Bearer | List reports for a job |
| `GET` | `/demo/api/jobs/{job_id}/reports/{workflow_id}` | Bearer | Get a specific report |
| `GET` | `/demo/api/reports/{job_id}/external` | Bearer | External report JSON |
| `GET` | `/demo/api/reports/{job_id}/internal` | Bearer | Internal report JSON |
| `GET` | `/demo/report/{job_id}` | Bearer or ticket | HTML report page |
| `GET` | `/health` | None | Service health check |
| `GET` | `/model/version` | None | Model package metadata |
| `GET` | `/demo/api-docs` | None | API documentation page (browser) |

> **Note:** `/openapi.json` is not currently exposed in production. This
> Swagger-style static reference serves as the API documentation instead.

## Current Production Smoke Summary

The following result was observed in the 2025-08-05 production smoke test.
This is a **technical-demo example**, not clinical evidence or model performance data.

| Field | Value |
|-------|-------|
| `job_id` | `b3e423e6-7d06-41ed-9d46-61abe386fa99` |
| patient / container | Nova_378 / Nova_378.h5 |
| `model_id` | `bremen-mri-triage-logreg-v0-1` |
| `overall_status` | completed |
| `decision_code` | MRI_REVIEW_DEFER |
| `report_status` | available |
| `probability` | 0.24370102950734568 |
| `threshold` | 0.3640352477169748 |

The decision `MRI_REVIEW_DEFER` means **"Defer MRI pending clinician review"**.
It does **not** mean "No MRI needed" or "Cancer ruled out."

## Documentation Pages

- [Authentication](api/auth.md) — token issuance and refresh
- [Models & Containers](api/models-and-containers.md) — model catalog and H5 listing
- [Jobs](api/jobs.md) — create and query analysis jobs
- [Events & SSE](api/events-and-sse.md) — event log and streaming
- [Reports](api/reports.md) — report JSON and HTML pages
- [Errors & Troubleshooting](api/errors-and-troubleshooting.md) — common issues and fixes
- [Examples](examples/) — runnable shell scripts and JSON payloads
