# PR0162 Cut 3

## Before

Cut 2 started with two serving paths. The bounded entrypoint audit found:

| Reference | Location | Disposition |
| --- | --- | --- |
| `bremen.api.server`, `run_server()` | `src/bremen/api/server.py`, CLI and tests | deleted legacy transport |
| `--backend`, `VALID_BACKENDS` | `src/bremen/__main__.py` | removed selector |
| `BREMEN_SERVER_BACKEND` | readiness checks and CLI | removed compatibility switch |
| `serve-fastapi` | CLI/tests | retained as alias to the same FastAPI launcher |
| `bremen.api.s3_model_discovery` | FastAPI startup, tests | moved to `platform/models/discovery.py` |
| `scripts/run_local_control_room.sh` | local launcher | now invokes `bremen serve` |

Docker already used `CMD ["serve", "--host", "0.0.0.0", "--port", "8080"]`; no Docker change was needed.

## Legacy transport disposition

`src/bremen/api/server.py` (1952 lines) was deleted. Its actual remaining
responsibilities were classified as follows:

- HTTP routing, request parsing, response writing, `HTTPServer`, threading and
  legacy backend dispatch: deleted because FastAPI routes cover the public
  contract.
- Authentication configuration singleton: moved to
  `src/bremen/api/http/auth_config.py`.
- Synthetic smoke model helper: moved to
  `src/bremen/api/http/dev_support.py`.
- H5 container listing/upload validation and safe error projection: moved to
  `src/bremen/platform/sources/demo_storage.py`; this is the existing source
  responsibility used by the FastAPI source routes.
- Model startup/discovery: uses platform model registry and discovery.

The old stdlib transport was not copied into another server. `demo_run.py` now
starts the same FastAPI factory through uvicorn in its local thread.

## Serving architecture after

The only request path is:

```text
bremen serve / bremen serve-fastapi
  -> api.fastapi_server.run_fastapi_server
  -> uvicorn bremen.api.http.app:create_app
  -> api/http routers
  -> platform application services
  -> platform model/source/job/report infrastructure
```

`api/http/app.py` is the only authoritative `create_app` composition root.
`serve-fastapi` remains a trivial compatibility alias to the same launcher.

## CLI changes

`bremen serve` no longer accepts `--backend`; it has no environment-driven
transport selection and always calls `run_fastapi_server`. `VALID_BACKENDS`,
`DEFAULT_BACKEND`, `resolve_backend()`, `BREMEN_SERVER_BACKEND`, the `http`
backend option, and the legacy dispatch branch were removed. The local Control
Room script now invokes `bremen serve --host ... --port ...`.

The `serve-fastapi` alias was retained because it is a small, existing public
CLI spelling and contains no separate serving implementation.

## Model discovery ownership

`api/s3_model_discovery.py` (1163 lines) moved unchanged in behavior to
`platform/models/discovery.py`. Relative imports were corrected for the new
owner; lookup semantics, manifest validation, artifact checksums, staging,
cleanup, readiness and safe error categories are unchanged. All production and
test imports now target the platform owner. The old API module is deleted and
has no shim.

## Files deleted

- `src/bremen/api/server.py` — duplicate stdlib HTTP implementation.
- `src/bremen/api/s3_model_discovery.py` — API-owned model infrastructure.
- `tests/test_bremen_concurrent_server.py` — legacy `HTTPServer` concurrency
  subject only; public FastAPI route coverage remains.
- `tests/test_bremen_server_helpers.py` — deleted transport helper subject;
  source validation remains covered by FastAPI/source tests.
- `tests/test_bremen_fastapi_serve_mode.py` — backend-selector/legacy dispatch
  characterization; readiness is covered by the updated script and architecture
  checks.
- `tests/test_bremen_fastapi_release_readiness.py` — obsolete dual-backend
  assertions; replaced by the updated readiness script.

## Tests retired

The four files above exclusively exercised the removed transport, backend
selector, or `run_server()` implementation. Public HTTP behavior was not
removed: route inventory, auth, jobs, reports, events/SSE, UI, model catalog,
and result parity suites continue to run against FastAPI.

## Public contract verification

- FastAPI factory route inventory remains exactly 29 method/path pairs and 27
  unique paths, matching `public_routes.json`.
- Existing result projection and report snapshots remain exact, including
  `risk_score`, `technical_demo_only`, and additive `standard_result`.
- Auth token/refresh, protected-route 401 behavior, source upload/listing,
  jobs, reports, events/SSE, ticket and public UI characterization suites pass.
- No `/reports/{workflow_id}/standard-result` route was added.

## Validation

```text
./venv/bin/python -m compileall -q src tests
PASS

./venv/bin/python scripts/check_fastapi_release_readiness.py
ALL CHECKS PASSED

./venv/bin/python -m pytest --collect-only -q
4087 tests collected in 2.10s

./venv/bin/python -m pytest -q --durations=100
4076 passed, 11 skipped, 1678 warnings in 31.34s

Focused HTTP/discovery/architecture suites:
216 passed, 1 skipped

./venv/bin/ruff check . --output-format=json
162 findings; no new findings after accounting for deleted legacy files.

git diff --check
PASS
```

Static production checks return zero matches for `http.server`,
`BaseHTTPRequestHandler`, `HTTPServer`, `ThreadingMixIn`,
`bremen.api.server`, `run_server()`, `bremen.api.s3_model_discovery`, backend
selector implementation, and `BREMEN_SERVER_BACKEND`. Model discovery is
owned only by `platform/models/discovery.py`.

## LOC delta

| Area | Before | After |
| --- | ---: | ---: |
| `api/server.py` | 1952 | 0 |
| `api/s3_model_discovery.py` | 1163 | 0 |
| `platform/models/discovery.py` | 0 | 1163 |
| `api/http/app.py` | 110 | 109 |
| `api/fastapi_server.py` | 119 | 119 |
| `__main__.py` | 438 | 333 |

The duplicate 1952-line HTTP implementation and backend-selection code were
removed. Discovery was moved for ownership clarity; it was not scientifically
rewritten. Total collected source tests decreased only because the four
legacy-only test files were retired.

## Remaining debt for Cut 4

- `api/http/legacy_jobs.py` remains a compatibility application adapter used by
  existing internal tests; it does not import or start an HTTP server.
- FastAPI startup still uses deprecated `on_event` hooks.
- Legacy H5 layout compatibility remains under `platform/sources` as reviewed.
- Repository-wide inherited Ruff debt remains.

READY FOR 0162 CUT 4
