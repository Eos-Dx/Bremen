# Implementation Report — PR0104F

## Branch

`0104f-fastapi-serve-mode`

## PR Target

`dev`

## Purpose

Add an explicit FastAPI serve mode so developers can run the isolated
FastAPI app through the project CLI (`python -m bremen serve-fastapi`).

This is **not** a production cutover.  It does not change the default
`python -m bremen serve` command.

## Files Changed

| File | Status | Description |
|------|--------|-------------|
| `src/bremen/__main__.py` | **Modified** | Added `serve-fastapi` subcommand |
| `src/bremen/api/fastapi_server.py` | **Added** | Thin uvicorn serve helper module |
| `tests/test_bremen_fastapi_serve_mode.py` | **Added** | Fast pytest tests (no server-spawning) |
| `.project-memory/pr/0104f-fastapi-serve-mode/implementation-report.md` | **Added** | This file |

## Command Added

```
python -m bremen serve-fastapi --host 127.0.0.1 --port 8080
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `127.0.0.1` | Bind address (loopback only) |
| `--port` | `8080` | Bind port |
| `--reload` | `False` | Enable auto-reload for dev |
| `--log-level` | `info` | Uvicorn log level |

## Uvicorn Factory Target

`bremen.api.fastapi_app:create_fastapi_app`

Called via `uvicorn.run(..., factory=True)`.

## Default Bind and Port

- Host: `127.0.0.1` (loopback only — never defaults to 0.0.0.0)
- Port: `8080`

## Legacy Serve Default Preserved

`python -m bremen serve` still uses the existing http.server path.
No default runtime switch in this PR.

## Fast Test Policy Followed

- 40 tests in `test_bremen_fastapi_serve_mode.py`
- uvicorn.run is monkeypatched — no real server spawned
- No urlopen, HTTPServer, ThreadingHTTPServer, serve_forever,
  real sockets, 127.0.0.1 connections, or localhost in tests
- All tests are fast (sub-second)

## No pytest server-spawning tests

Tests use:
- argparse parser introspection
- monkeypatched `uvicorn.run`
- AST analysis for forbidden patterns
- source string checks for safe error output

## Dockerfile Unchanged

No modifications to `Dockerfile`.

## Production ENTRYPOINT Unchanged

No modifications to production ENTRYPOINT.

## Production CMD Unchanged

No modifications to production CMD.

## Control Room Unchanged

No modifications to `src/bremen/control_room_ui.py`.

## Auth Unchanged

No modifications to `src/bremen/auth.py`.

## No Production Cutover

This PR adds an explicit dev serve mode.  The production runtime
is unchanged.  The existing `python -m bremen serve` command is
preserved with its http.server backend.

## Safety Boundary

- No raw S3 keys, credentials, JWT secrets, or env values exposed
- Missing-uvicorn path prints safe install hint, not traceback
- Uvicorn error path prints type name only, not raw exception
- Default bind is loopback (127.0.0.1)

## Validation Results

| Command | Expected | Status |
|---------|----------|--------|
| `git rev-parse --verify HEAD` | SHA on branch | ✅ |
| `git branch --show-current` | `0104f-fastapi-serve-mode` | ✅ |
| Branch contains origin/dev | true | ✅ |
| Forbidden scope check | No output | ✅ |
| `python -m compileall src tests` | Exit 0 | ✅ |
| `python -m pytest tests/test_bremen_fastapi_serve_mode.py -v` | 33 passed | ✅ |
| `python -m pytest tests/test_bremen_fastapi_asgi_smoke_readiness.py -v` | 65 passed | ✅ |
| `python -m pytest tests/test_bremen_fastapi_phase1.py -v` | 27 passed | ✅ |
| `python -m pytest -k "fastapi and (serve or asgi or smoke or phase1)" --tb=short` | 138 passed | ✅ |
| `git diff --check` | Clean | ✅ |

## Blockers

None.

## Warnings

None.

## Next Required Action

Commit, create PR to `dev` with title:
`PR0104F — FastAPI serve mode`
