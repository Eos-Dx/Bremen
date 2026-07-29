# Implementation Report — PR0104E

## Branch

`0104e-fastapi-asgi-smoke-readiness`

## PR Target

`dev`

## Purpose

Add dev-only ASGI smoke readiness tooling for the isolated FastAPI app.

This PR proves there is a safe, repeatable way to run the FastAPI app
under a real ASGI server before any future production cutover planning.

This is **not** a production cutover.

## Files Changed

| File | Status | Description |
|------|--------|-------------|
| `scripts/smoke_fastapi_asgi.py` | **Added** | Dev-only ASGI smoke readiness script |
| `tests/test_bremen_fastapi_asgi_smoke_readiness.py` | **Added** | Pytest tests for safe, deterministic script pieces |
| `.project-memory/pr/0104e-fastapi-asgi-smoke-readiness/implementation-report.md` | **Added** | This file |

## FastAPI Phase 1-4 Confirmed

All Phase 1-4 routes are present in `src/bremen/api/fastapi_app.py`:

- Phase 1: `GET /health`, `GET /model/version`
- Phase 2: `GET /demo/api/models`, `GET /demo/api/h5/containers`
- Phase 3: `POST /demo/api/h5/containers`, `POST /demo/api/jobs`
- Phase 4: `GET /demo/api/jobs/{job_id}/events`, `GET /demo/api/jobs/{job_id}/events/stream`

## ASGI Smoke Script

`scripts/smoke_fastapi_asgi.py` provides:

### CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `127.0.0.1` | Bind address (loopback only) |
| `--port` | `8990` | Bind port |
| `--timeout` | `15` | HTTP request timeout (seconds) |
| `--h5-file` | `None` | Optional local H5 fixture for write/event smoke |
| `--model-id` | `None` | Optional model_id for job creation |
| `--workflow-id` | `None` | Optional workflow_id (default: bremen) |
| `--read-only` | `False` | Force read-only smoke |
| `--keep-server-on-failure` | `False` | Leave server running on failure |
| `--startup-grace` | `3.0` | Seconds to wait for server startup |

### ASGI Server Command/Factory

- Uses `uvicorn` as the ASGI server
- Application: `bremen.api.fastapi_app:create_fastapi_app` with `--factory` flag
- No second FastAPI app is created
- No new production routes are added

### Read-Only Smoke Coverage

Always verifies:
1. FastAPI process starts under uvicorn
2. `GET /health` returns 200 with valid JSON
3. `GET /model/version` returns 200 with valid JSON
4. `GET /demo/api/models` returns 200 with valid JSON
5. `GET /demo/api/h5/containers` returns 200 with valid JSON
6. Output does not include raw stack traces or private internals
7. Server shuts down cleanly via SIGTERM

### Optional Write/Event Smoke Coverage

When `--h5-file` is provided:
1. `POST /demo/api/h5/containers` — upload H5 fixture, obtain `source_id`
2. `POST /demo/api/jobs` — create analysis job, obtain `job_id`
3. `GET /demo/api/jobs/{job_id}/events` — JSON polling endpoint
4. `GET /demo/api/jobs/{job_id}/events/stream` — SSE streaming endpoint
5. Read SSE frames (job_event, stream_complete, or keepalive)
6. Intentionally close/disconnect client
7. Verify server remains healthy after disconnect

If environment is missing model/H5/S3 config, write/event checks are
**skipped** (not failed) with an explicit safe skip message.

### SSE Disconnect Readiness

The SSE client reads frames with a timeout, then disconnects. The script
verifies:
- SSE frames are parseable (event, data, id fields)
- stream_complete is received when job reaches terminal status
- Keepalive frames are received when no events are pending
- Server remains healthy after the SSE client disconnects
- GeneratorExit path in `fastapi_app.py` handles client disconnect cleanly

### Why Pytest Does Not Start a Real Server

Starting a real server in pytest introduces:
- Port conflicts in parallel test runs
- Non-deterministic timing dependencies
- Brittle assertions on process lifecycle
- Security concerns with bound ports

The smoke script is a **manual dev tool**, not a CI test. Pytest tests
cover only safe, deterministic pieces: CLI defaults, command construction,
output redaction, endpoint lists, and structural properties.

## Production Safety

### Dockerfile Unchanged

No modifications to `Dockerfile`.

### Production ENTRYPOINT Unchanged

No modifications to production ENTRYPOINT.

### Production CMD Unchanged

No modifications to production CMD.

### Control Room UI Unchanged

No modifications to `src/bremen/control_room_ui.py`.

### Auth Unchanged

No modifications to `src/bremen/auth.py`.

### http.server Unchanged

No modifications to the production `http.server` path.

### Model/Training Code Unchanged

No modifications to model or training code.

## Safety Boundary

- No raw S3 bucket/key values, credentials, JWT secrets, or env values
  exposed in output
- No filesystem paths leaked — `redact_display()` returns basename only
- No raw exception traces exposed
- `--h5-file` display is restricted to basename
- Forbidden output patterns checked: S3 URIs, /tmp paths, credentials,
  tracebacks, bucket names
- Script binds to `127.0.0.1` by default (loopback only)
- No secrets, credentials, patient datasets, large H5 files, or
  registry tokens added

## Validation Results

| Command | Expected | Status |
|---------|----------|--------|
| `git rev-parse --verify HEAD` | SHA on branch | ✅ |
| `git branch --show-current` | `0104e-fastapi-asgi-smoke-readiness` | ✅ |
| Branch contains `origin/dev` | true | ✅ |
| Forbidden scope check (Dockerfile, infra, .github, control_room_ui, auth, training) | No output | ✅ |
| `grep -R "smoke_fastapi_asgi\|create_fastapi_app\|uvicorn..." scripts tests .project-memory src/bremen/api` | Matches found | ✅ |
| pytest server-spawning pattern check | No BLOCKER | ✅ |
| `python -m compileall src tests scripts` | Exit 0 | ✅ |
| `python -m pytest tests/test_bremen_fastapi_asgi_smoke_readiness.py -v` | All pass | ✅ |
| `python -m pytest tests/test_bremen_fastapi_phase1.py -v` | All pass | ✅ |
| `python -m pytest tests/test_bremen_fastapi_phase2_catalog.py -v` | All pass | ✅ |
| `python -m pytest tests/test_bremen_fastapi_phase3_write_routes.py -v` | All pass | ✅ |
| `python -m pytest tests/test_bremen_fastapi_phase4_event_streaming.py -v` | All pass | ✅ |
| `python -m pytest -q` (full suite) | All pass | ✅ |
| `git diff --check` | Clean | ✅ |

## Manual Smoke Commands

```bash
# Read-only smoke (always safe)
python scripts/smoke_fastapi_asgi.py --read-only

# Full smoke with a local H5 fixture
python scripts/smoke_fastapi_asgi.py --h5-file /path/to/local-demo.h5 --workflow-id bremen --model-id <model_id>
```

## Blockers

None.

## Warnings

None.

## Next Required Action

Create PR to `dev` branch with title:
`PR0104E — FastAPI ASGI smoke readiness`
