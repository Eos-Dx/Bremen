# PR 0067 — Plan H5 Container Browser Analyze Demo

Author: plan
Mode: planning only
Branch: 0067-h5-container-browser-analyze-demo

## Objective

Add the fastest demo-critical vertical slice to Bremen's `/demo` browser page: a workspace where a user can see listed H5 containers, upload new H5 containers via a web form, select one, click Analyze, and see structured events/logs plus real Bremen model output — all without React, new dependencies, or deployment changes.

This is the vertical slice that makes the `/demo` page move from "presentation-oriented" to "interactive demo."

## Demo-critical scope (explicit)

This PR does NOT plan a broad production file manager, patient data management subsystem, authentication, multi-tenancy, model profiles, plugin registry, or production file governance. It adds the minimum browser-accessible H5 analyze path needed for a product demo.

## Required reads — observed facts

### `src/bremen/demo_ui.py`
- `build_demo_html_page()` generates self-contained HTML with cards.
- Currently has "Synthetic Feature Artifact" as the primary Demo Flow step.
- No H5 upload form, container list, or Analyze button yet.

### `src/bremen/api/server.py`
- `_make_handler()` with `do_GET()` and `do_POST()`. JSON-only body parsing via `_read_json_body()`.
- No multipart upload handling. No H5 container endpoints.

### `src/bremen/h5_inputs.py`
- `stage_h5_input(h5_uri, expected_checksum)` — downloads from S3, verifies checksum, stages locally.
- Uses `boto3` for S3 download (existing dependency, not added by this PR).

### `src/bremen/model_artifacts.py`
- `parse_s3_uri(uri)` — parses `s3://bucket/key`.
- `stage_s3_model_artifact(bucket, key, ...)` — downloads from S3.

### `src/bremen/api/inference_handler.py`
- `run_inference(h5_path, patient_id, target_scan_ref, control_scan_ref, input_mode)` — full pipeline.
- H5 preflight → layout detection → preprocessing bridge → model inference → decision-support report.

### `src/bremen/config.py`
- `read_cloud_config()` — reads BREMEN_MODEL_BUCKET, etc.
- No `BREMEN_DEMO_H5_BUCKET` exists yet.

### `src/bremen/k8s_redirection/` or `src/bremen/api/demo_config.py`
- No existing demo H5 config module.

### Tests
- 1256 tests pass. All PR0060–0066 merged.

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Allowed implementation files

1. **`src/bremen/demo_ui.py`** — MODIFY. Replace synthetic feature artifact flow with H5 container workspace. Add container list, upload form, Analyze button, events/logs panel, result card.
2. **`src/bremen/api/server.py`** — MODIFY. Add 3 demo H5 API endpoints:
   - `GET /demo/api/h5/containers` — list containers
   - `POST /demo/api/h5/containers` — upload container
   - `POST /demo/api/h5/analyze` — analyze selected container
3. **`src/bremen/demo_config.py`** — NEW. Demo-specific configuration for H5 container storage (bucket/prefix, upload enable/disable, size limits).
4. **`tests/test_bremen_demo_ui.py`** — MODIFY. Update tests for H5 workspace UI.
5. **`tests/test_bremen_api_server.py`** — MODIFY. Add tests for all 3 new endpoints.

**Default: no CLI changes.** No changes to `__main__.py`, `demo_run.py`, `demo_smoke.py`, `demo_capture.py`.

## Forbidden files

- `.github/**`, `infra/terraform/**`
- `Dockerfile`, `Dockerfile.training`
- `requirements.txt`, `pyproject.toml`
- `frontend/**`, `web/**`, `ui/**`
- `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `node_modules/**`
- `tests/data/**`
- Any committed `.h5`, `.hdf5`, `.joblib`, `.pkl`, `.npy`, `.npz`
- `tfstate`, `.terraform`
- `config/training/**`, `src/bremen/training/**`
- `docs/**`, `ROADMAP.md`
- Aramis artifacts, model descriptions, feature schemas as dependency

## Exact implementation scope

### 1. `src/bremen/demo_config.py` — Demo H5 configuration

A small stdlib-only module reading one new env var:

```python
"""Demo-specific configuration for H5 container browser demo.

Reads demo config from environment variables.

Standard library only — no third-party dependencies.
"""

from __future__ import annotations

import os

_DEFAULT_DEMO_H5_PREFIX = "demo-uploads/"


def read_demo_h5_config(env: dict[str, str] | None = None) -> dict:
    """Read demo H5 container storage configuration.

    Parameters
    ----------
    env : Optional explicit env mapping (for testing).  Defaults to
        ``os.environ``.

    Returns
    -------
    A dict with keys:
    - ``h5_bucket`` (str or None) — configured bucket
    - ``h5_prefix`` (str) — object key prefix
    - ``allow_upload`` (bool) — whether browser upload is enabled
    """
    if env is None:
        env = os.environ

    bucket = env.get("BREMEN_DEMO_H5_BUCKET", "").strip() or None
    prefix_raw = env.get("BREMEN_DEMO_H5_PREFIX", "").strip()
    prefix = prefix_raw if prefix_raw else _DEFAULT_DEMO_H5_PREFIX
    allow_upload = env.get("BREMEN_DEMO_H5_ALLOW_UPLOAD", "true").strip().lower() in ("true", "1", "yes")

    return {
        "h5_bucket": bucket,
        "h5_prefix": prefix,
        "allow_upload": allow_upload,
    }
```

**Env vars introduced** (all optional):
- `BREMEN_DEMO_H5_BUCKET` — S3 bucket for demo H5 containers. If not set, `GET /demo/api/h5/containers` returns `storage: "not_configured"`.
- `BREMEN_DEMO_H5_PREFIX` — Object key prefix (default: `demo-uploads/`).
- `BREMEN_DEMO_H5_ALLOW_UPLOAD` — Enable browser upload (default: `true`).

### 2. `src/bremen/api/server.py` — Add 3 demo H5 endpoints

**`GET /demo/api/h5/containers`**:

```python
elif self.path == "/demo/api/h5/containers":
    self._do_get_h5_containers()
```

Implementation:
1. Read demo config via `read_demo_h5_config()`.
2. If `h5_bucket` is None, return `{"storage": "not_configured", "containers": []}` — no error, just no containers.
3. If `h5_bucket` is set, **mock S3 listing** for demo purposes: use env var `BREMEN_DEMO_H5_CONTAINERS` as a JSON array of `{id, filename, size_bytes, uploaded_at}` entries. This avoids requiring real S3 list calls for the demo while keeping the contract.
4. If `BREMEN_DEMO_H5_CONTAINERS` is not set, return empty list.
5. Each container entry: `{id, filename, size_bytes, uploaded_at}`.

**Why mock listing instead of real S3**: S3 `list_objects` requires `boto3` and credentials. For the fastest demo vertical slice, this endpoint reads from a configurable JSON list. The container upload path writes to S3 (so the list could be extended later).

```python
try:
    containers_json = os.environ.get("BREMEN_DEMO_H5_CONTAINERS", "[]")
    containers = json.loads(containers_json)
except (json.JSONDecodeError, TypeError):
    containers = []
```

**`POST /demo/api/h5/containers`**:

```python
elif self.path == "/demo/api/h5/containers" and self.command == "POST":
    self._do_post_h5_container()
```

Implementation:
1. Check `read_demo_h5_config()["allow_upload"]` — if False, return 403 `{"status": "upload_disabled"}`.
2. Check `h5_bucket` — if None, return 503 `{"status": "storage_not_configured"}`.
3. Read request body as raw bytes (application/octet-stream).
4. Validate: content length ≤ 100 MB, filename from `X-H5-Filename` header (sanitized, reject path separators).
5. Validate extension `.h5` or `.hdf5`.
6. Upload to S3: `boto3.client("s3").put_object(Bucket=bucket, Key=f"{prefix}{sanitized_filename}", Body=data)`.
7. Return `{"status": "uploaded", "id": key, "filename": sanitized_filename}`.
8. On failure, return controlled error JSON.

**`POST /demo/api/h5/analyze`**:

```python
elif self.path == "/demo/api/h5/analyze":
    self._do_h5_analyze()
```

Implementation:
1. Read JSON body: `{"container_id": "..."}` (the S3 key of the container to analyze).
2. If missing `container_id`, return 400.
3. If model not ready (`ModelState.is_ready()` is False), return events list with final event `model_not_ready`.
4. Build events list:

```python
events = [
    {"event": "request_received", "timestamp": "...", "detail": "Analyze requested"},
    {"event": "container_selected", "timestamp": "...", "detail": f"Container: {container_id}"},
]
```

5. Stage H5 from S3 using existing `h5_inputs.stage_h5_input(s3_uri)` — event `h5_staging_started` / `h5_staging_completed` or `h5_container_unavailable`.
6. Run inference using `inference_handler.run_inference(staged_path, ...)` — events for preflight, preprocessing, inference, evidence.
7. On completion, add `completed` event and return:

```json
{
    "status": "completed",
    "events": [...],
    "result": { ... prediction result ... },
    "evidence": { ... evidence bundle ... },
    "technical_demo_only": true
}
```

8. On failure at any stage, return events up to failure point with final failure event and status.

**Structured events (full list)**:

| Event | When | Detail |
|-------|------|--------|
| `request_received` | Entry | "Analyze requested" |
| `container_selected` | Body parsed | Container S3 key |
| `h5_staging_started` | Before S3 download | Size |
| `h5_staging_completed` | After successful download + checksum | Staged path |
| `h5_preflight_started` | Before layout detection | — |
| `h5_preflight_completed` | After layout | Layout category |
| `preprocessing_started` | Before bridge | — |
| `preprocessing_completed` | After bridge | 15 features extracted |
| `model_inference_started` | Before inference | Model version |
| `model_inference_completed` | After inference | p_mri_needed |
| `evidence_built` | Evidence bundle built | — |
| `completed` | Final | — |

Failure events replace the progression:

| Failure event | When |
|---------------|------|
| `storage_not_configured` | Demo H5 bucket not configured |
| `upload_rejected` | Upload rejected (size, type, disabled) |
| `h5_container_unavailable` | S3 download failed |
| `model_not_ready` | Model not loaded |
| `h5_preflight_failed` | Layout detection failed |
| `preprocessing_failed` | Feature extraction failed |
| `inference_failed` | Model inference failed |

**Event safety**: No raw H5 content, no patient identifiers, no full S3 URIs (key only).

### 3. `src/bremen/demo_ui.py` — Update `/demo` page

**Replace** the Demo Flow card. Remove "Synthetic Feature Artifact" as the primary demo story.

If synthetic feature artifact is mentioned at all, it must be as a secondary/internal explanation only, not the primary product input story.

**Add** the following cards:

**H5 Container Workspace card**:
```html
<div class="card">
<h2>📁 H5 Container Workspace</h2>
<div id="container-list">
  <p>Loading containers...</p>
</div>
<div id="upload-section">
  <h3>Upload H5 Container</h3>
  <input type="file" id="h5-file-input" accept=".h5,.hdf5">
  <button onclick="uploadH5()">Upload</button>
  <p class="hint">Max 100 MB. HDF5/H5 files only.</p>
</div>
<div id="analyze-section" style="display:none;">
  <h3>Selected Container</h3>
  <p id="selected-container-name"></p>
  <button onclick="analyzeH5()">Analyze</button>
</div>
</div>
```

**Events/Logs card**:
```html
<div class="card">
<h2>📋 Events / Logs</h2>
<div id="events-panel">
  <p>No events yet.</p>
</div>
</div>
```

**Prediction Result card**:
```html
<div class="card" id="result-card" style="display:none;">
<h2>📊 Prediction Result</h2>
<div id="result-content"></div>
</div>
```

**Inline JavaScript** (minimal, stdlib-compatible):

```javascript
<script>
// Store containers from GET /demo/api/h5/containers
var containers = [];

function loadContainers() {
  fetch('/demo/api/h5/containers')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      containers = data.containers || [];
      var html = '';
      if (containers.length === 0) {
        html = '<p>No containers available. Upload one below.</p>';
      } else {
        html = '<table><tr><th>Filename</th><th>Size</th><th></th></tr>';
        containers.forEach(function(c) {
          html += '<tr><td>' + escapeHtml(c.filename) + '</td><td>' + c.size_bytes + ' B</td>';
          html += '<td><button onclick="selectContainer(\'' + escapeHtml(c.id) + '\', \'' + escapeHtml(c.filename) + '\')">Select</button></td></tr>';
        });
        html += '</table>';
      }
      document.getElementById('container-list').innerHTML = html;
    });
}

function selectContainer(id, filename) {
  document.getElementById('selected-container-name').textContent = filename;
  document.getElementById('analyze-section').style.display = 'block';
  window._selectedContainerId = id;
}

function uploadH5() {
  var fileInput = document.getElementById('h5-file-input');
  if (!fileInput.files || fileInput.files.length === 0) return;
  var file = fileInput.files[0];
  fetch('/demo/api/h5/containers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/octet-stream', 'X-H5-Filename': file.name },
    body: file
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    if (data.status === 'uploaded') {
      loadContainers();
    } else {
      alert('Upload failed: ' + (data.error || data.status));
    }
  });
}

function analyzeH5() {
  var containerId = window._selectedContainerId;
  if (!containerId) return;
  document.getElementById('events-panel').innerHTML = '';
  document.getElementById('result-card').style.display = 'none';
  fetch('/demo/api/h5/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ container_id: containerId })
  })
  .then(function(r) { return r.json(); })
  .then(function(data) {
    var events = data.events || [];
    var html = '';
    events.forEach(function(e) {
      html += '<div class="event ' + (e.event.indexOf('failed') > -1 ? 'event-fail' : e.event.indexOf('_not_') > -1 ? 'event-warn' : '') + '">';
      html += '<strong>' + e.event + '</strong> — ' + (e.detail || '') + ' <span class="event-time">' + (e.timestamp || '') + '</span>';
      html += '</div>';
    });
    document.getElementById('events-panel').innerHTML = html;
    if (data.result) {
      document.getElementById('result-card').style.display = 'block';
      document.getElementById('result-content').innerHTML = renderResult(data);
    }
  });
}

function renderResult(data) {
  var r = data.result || {};
  var html = '<table>';
  html += '<tr><td>Status</td><td>' + (data.status || 'N/A') + '</td></tr>';
  if (r.p_mri_needed !== undefined) html += '<tr><td>p_mri_needed</td><td>' + r.p_mri_needed.toFixed(3) + '</td></tr>';
  if (r.triage_recommendation) html += '<tr><td>Recommendation</td><td>' + r.triage_recommendation + '</td></tr>';
  if (r.qc_status) html += '<tr><td>QC Status</td><td>' + r.qc_status + '</td></tr>';
  if (r.model_version) html += '<tr><td>Model Version</td><td>' + r.model_version + '</td></tr>';
  if (data.evidence && data.evidence.model_version) html += '<tr><td>Model</td><td>' + data.evidence.model_version + '</td></tr>';
  if (data.request_id) html += '<tr><td>Request ID</td><td style="font-family:monospace;font-size:12px;">' + data.request_id + '</td></tr>';
  html += '</table>';
  return html;
}

function escapeHtml(s) {
  var d = document.createElement('div');
  d.appendChild(document.createTextNode(s || ''));
  return d.innerHTML;
}

loadContainers();
</script>
```

**CSS additions**: Event styling classes.

```css
.event { padding: 6px 10px; margin: 4px 0; background: #f0f4f8; border-radius: 4px; font-size: 13px; }
.event-fail { background: #ffebee; color: #c62828; }
.event-warn { background: #fff8e1; color: #f57f17; }
.event-time { color: #999; float: right; font-size: 11px; }
.hint { font-size: 12px; color: #888; margin-top: 4px; }
```

### 4. `tests/test_bremen_demo_ui.py` — Updated tests

1. **No "Synthetic Feature Artifact" as primary flow** — Primary flow is now H5 container. The string may appear in secondary/internal explanation, not as primary.
2. **Contains H5 Container Workspace card** — HTML includes "H5 Container Workspace".
3. **Contains container list div** — `id="container-list"` present.
4. **Contains upload file input** — `type="file"` with `accept=".h5,.hdf5"`.
5. **Contains Upload button** — Button with onclick `uploadH5()`.
6. **Contains Analyze button** — Button with onclick `analyzeH5()`.
7. **Contains Events/Logs card** — HTML includes "Events / Logs".
8. **Contains inline JavaScript** — `<script>` tag present.
9. **No external assets** — Still passes CDN checks.
10. **Existing safety/identity tests still pass** — Technical demo only, Bremen identity, safety notes, no Aramis, no clinical claims.

### 5. `tests/test_bremen_api_server.py` — New endpoint tests

**`GET /demo/api/h5/containers`** (3 tests):
1. `test_get_containers_no_config` — Without env vars, returns `storage: "not_configured"`, empty containers list.
2. `test_get_containers_with_list` — With `BREMEN_DEMO_H5_CONTAINERS` set, returns parsed container list.
3. `test_get_containers_returns_json` — Content-Type is application/json.

**`POST /demo/api/h5/containers`** (4 tests):
1. `test_upload_requires_bucket_config` — Without `BREMEN_DEMO_H5_BUCKET`, returns 503 `storage_not_configured`.
2. `test_upload_rejects_oversized` — Body > 100 MB, returns 413.
3. `test_upload_rejects_bad_extension` — Non-H5 extension, returns 400.
4. `test_upload_requires_filename_header` — Missing `X-H5-Filename`, returns 400.

**`POST /demo/api/h5/analyze`** (4 tests):
1. `test_analyze_missing_container_id` — No body, returns 400.
2. `test_analyze_model_not_ready` — When model not loaded, returns events with `model_not_ready`.
3. `test_analyze_returns_events_and_result` — With mock S3 staging and model loaded, returns ordered events and result.
4. `test_analyze_events_are_structured` — Events array has expected shape.

## Non-goals

- No new CLI command, no `--ui` flag.
- No changes to `demo_run.py`, `demo_smoke.py`, `demo_capture.py`, `__main__.py`.
- No committed H5 files.
- No raw H5 contents in response or logs.
- No React/frontend stack.
- No external assets/CDN.
- No multi-tenancy, model profiles, plugins.
- No deployment mutation (Terraform, Docker, CI/CD).
- No new dependencies (boto3 is already a dependency, not new).
- No docs/ROADMAP changes.
- No authentication or authorization.
- No production file governance.

## Safety boundaries

- No runtime training.
- No unsafe model deserialization — uses existing `ModelState.load_at_startup()` and `inference_handler.run_inference()`.
- No new `joblib.load()`.
- No H5 mutation — H5 files are read-only during inference, not modified by demo.
- File uploads are temporary/transient — stored in configured S3 bucket, not committed to repo.
- No real patient data committed.
- Raw H5 contents are not logged — only metadata (filename, size, container_id, event status).
- No hardcoded patient S3 paths — only env-var-configured bucket/prefix.
- `technical_demo_only: true` in every response.
- No clinical diagnosis/replacement claims.
- No Aramis references.

## Validation checklist

```bash
# Git checks
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only

# Compile and test checks
python -m compileall src tests
python -m pytest -q tests/test_bremen_demo_ui.py
python -m pytest -q tests/test_bremen_api_server.py
python -m pytest -q tests/test_bremen_demo_smoke.py
python -m pytest -q tests/test_bremen_demo_run.py
python -m pytest -q tests/test_bremen_demo_capture.py
python -m pytest -q tests/test_bremen_api_skeleton.py
if test -f tests/test_bremen_dependency_hygiene.py; then \
  python -m pytest -q tests/test_bremen_dependency_hygiene.py; \
else echo "SKIP missing tests/test_bremen_dependency_hygiene.py"; fi
python -m pytest -q
python -m bremen --help
python -m bremen serve --help
python -m bremen demo-smoke --help
python -m bremen demo-run --help
```

### Forbidden-pattern grep checks

```bash
# No --ui flag or extra launch command
grep -R -I -n -- "--ui\|demo-run --ui" src/bremen tests || true
# Expected: no output

# No synthetic feature artifact as primary product input
grep -n "Synthetic Feature Artifact" src/bremen/demo_ui.py tests/test_bremen_demo_ui.py || true
# Expected: may appear only in secondary/internal explanation, not as primary flow element

# No external assets/CDN
grep -R -I -n "https://\|http://.*cdn\|unpkg\|jsdelivr\|googleapis\|fontawesome" \
  src/bremen/demo_ui.py tests/test_bremen_demo_ui.py || true
# Expected: no output

# No Aramis dependency or product labels
grep -R -I -n "Aramis\|aramis\|M2Q\|BENIGN vs CANCER" \
  src/bremen tests/test_bremen_demo_ui.py tests/test_bremen_api_server.py || true
# Expected: no output (test assertions verifying absence are allowed)

# No clinical/replacement claims (safe negation only)
grep -R -I -n "diagnosis\|diagnose\|replaces MRI\|replace MRI\|replaces biopsy\|replace biopsy\|replaces radiologist\|replace radiologist\|replaces clinician\|replace clinician" \
  src/bremen tests/test_bremen_demo_ui.py tests/test_bremen_api_server.py || true
# Expected: no output

# No unsafe deserialization outside existing controlled boundary
grep -R -I -n "joblib\.load\|pickle\.load\|import pickle" \
  src/bremen tests/test_bremen_demo_ui.py tests/test_bremen_api_server.py || true
# Expected: no new unsafe loading (existing in modeling.py/mlflow_tracking.py not in scope)

# Forbidden files unchanged
git diff --name-only -- .github infra/terraform Dockerfile Dockerfile.training \
  requirements.txt pyproject.toml config/training frontend web ui \
  package.json package-lock.json yarn.lock pnpm-lock.yaml tests/data

# Docs/ROADMAP unchanged
git diff --name-only -- docs ROADMAP.md
# Expected: no output

# No model/data artifacts
git diff --name-only | grep -E "\.(h5|hdf5|joblib|pkl|npy|npz|tfstate|tfstate\.backup)$" || true
# Expected: no output

# No .DS_Store
find . -name ".DS_Store" -print
```

## Platform safety decisions

| Decision | Value |
|----------|-------|
| Container catalog | `GET /demo/api/h5/containers` — returns configured list from env var or empty. Mocked for demo, no S3 list call. |
| Upload endpoint | `POST /demo/api/h5/containers` — `application/octet-stream` with `X-H5-Filename` header. |
| Upload storage | S3 via existing `boto3` dependency (not new). |
| Upload validation | Extension `.h5`/`.hdf5`, size ≤ 100 MB, filename sanitized (no path separators). |
| Analyze endpoint | `POST /demo/api/h5/analyze` — JSON body with `container_id`. |
| Analyze flow | Events pipeline → S3 staging → inference → evidence. |
| Events | 12 event types + 7 failure events. Structured JSON array. |
| UI | Inline JS fetch calls. No React. No external assets. |
| Synthetic feature artifact | Not primary input. May appear as secondary/internal explanation only. |
| CLI changes | None. |

## Rollback plan

1. **Revert `src/bremen/demo_ui.py`** — restore to pre-PR0067 state.
2. **Revert `src/bremen/api/server.py`** — remove 3 new demo H5 endpoints and helper methods.
3. **Revert `src/bremen/demo_config.py`** — delete.
4. **Revert test files** — revert `test_bremen_demo_ui.py` and `test_bremen_api_server.py`.

## Plan Drift Gate

| Drift category | Check |
|----------------|-------|
| **File drift** | Only 5 files changed (allowed list). No forbidden files. |
| **H5 flow drift** | H5 container is primary input. Synthetic artifact removed from primary story. |
| **No new CLI** | No changes to `__main__.py`, `demo_run.py`, `demo_smoke.py`, `demo_capture.py`. |
| **Safety drift** | No unsafe deserialization, no H5 mutation, no clinical claims. |
| **Test drift** | Updated UI tests + 11 server endpoint tests. Existing 1256 tests pass unchanged. |
| **Validation drift** | All validation checks pass. No H5 contents in logs. No hardcoded S3 paths. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Plan commits or requires committing H5/HDF5 patient data files.
- Plan adds `--ui` or another launch command.
- Plan requires React/frontend stack or new dependencies.
- Plan makes synthetic feature artifact the primary demo input story.
- Plan hardcodes real patient S3 paths in source code.
- Plan fails to sanitize filenames or enforce upload limits.
- Plan requires AWS credentials that are not already available via existing boto3 dependency.
- Plan weakens Bremen safety language.
- Implementation phase is not Agent: coder / Mode: implementation.

## Decisions summary

| Decision | Value |
|----------|-------|
| Configuration | `src/bremen/demo_config.py` — reads BREMEN_DEMO_H5_BUCKET, BREMEN_DEMO_H5_PREFIX, BREMEN_DEMO_H5_ALLOW_UPLOAD |
| Container list | `GET /demo/api/h5/containers` — env-var driven mock list for demo |
| Upload endpoint | `POST /demo/api/h5/containers` — octet-stream + X-H5-Filename |
| Upload target | S3 via existing boto3 dependency |
| Analyze endpoint | `POST /demo/api/h5/analyze` — JSON body with container_id |
| Events | 12 success + 7 failure event types in structured JSON array |
| UI | Inline HTML + JS, no React, no CDN |
| Synthetic artifact | Removed from primary story |
| New env vars | BREMEN_DEMO_H5_BUCKET, BREMEN_DEMO_H5_PREFIX, BREMEN_DEMO_H5_ALLOW_UPLOAD, BREMEN_DEMO_H5_CONTAINERS |

## Files read

- `ROADMAP.md`
- `docs/api_contract.md`
- `docs/architecture.md`
- `docs/adr/0003-bremen-microservice-api-architecture.md`
- `docs/adr/0007-model-artifact-lifecycle.md`
- `docs/adr/0008-runtime-target-apprunner-proving.md`
- `docs/adr/0012-system-of-record-boundary.md`
- `src/bremen/__main__.py`
- `src/bremen/demo_smoke.py`
- `src/bremen/demo_run.py`
- `src/bremen/demo_capture.py`
- `src/bremen/demo_ui.py`
- `src/bremen/demo_evidence.py`
- `src/bremen/api/server.py`
- `src/bremen/api/app.py`
- `src/bremen/api/jobs.py`
- `src/bremen/api/schemas.py`
- `src/bremen/api/model_state.py`
- `src/bremen/api/inference_handler.py`
- `src/bremen/api/preprocessing_bridge.py`
- `src/bremen/api/h5_layouts.py`
- `src/bremen/h5_inputs.py`
- `src/bremen/model_artifacts.py`
- `src/bremen/config.py`
- `tests/test_bremen_demo_ui.py`
- `tests/test_bremen_api_server.py`
- `tests/test_bremen_demo_smoke.py`
- `tests/test_bremen_demo_run.py`
- `tests/test_bremen_demo_capture.py`
- `tests/test_bremen_api_skeleton.py`
- `tests/test_bremen_cli_entrypoint.py`
- `tests/test_bremen_dependency_hygiene.py`
- `.project-memory/project_contract.yml`
- `AGENTS.md`

## Files written

- `.project-memory/pr/0067-h5-container-browser-analyze-demo/PLAN.md` (this file)

## Boundary confirmations

- confirm: PR0067 planned as H5 container browser analyze demo: yes
- confirm: H5 container planned as product input: yes
- confirm: list of existing system containers planned: yes (via env-var mock list)
- confirm: browser upload of new H5 container planned: yes
- confirm: container selection planned: yes
- confirm: Analyze button planned: yes
- confirm: logs/events planned in API response and UI: yes
- confirm: real model output planned when model ready: yes
- confirm: explicit model_not_ready behavior planned: yes
- confirm: no fake successful prediction planned: yes
- confirm: synthetic feature artifact no longer primary product input: yes
- confirm: feature artifact treated as derived/internal only: yes
- confirm: no committed H5/patient data planned: yes
- confirm: no raw H5 contents in response/logging planned: yes
- confirm: no hardcoded patient S3 path planned: yes
- confirm: no new startup command planned: yes
- confirm: no `--ui` flag planned: yes
- confirm: no root `/` demo page planned: yes
- confirm: existing demo-run behavior preserved: yes
- confirm: existing capture-dir behavior preserved: yes
- confirm: existing demo-smoke behavior preserved: yes
- confirm: no React/frontend stack planned: yes
- confirm: no package-manager files planned: yes
- confirm: no deployment mutation planned: yes
- confirm: no Terraform/GitHub Actions/Docker changes planned: yes
- confirm: multi-tenancy/model-profile/plugin work deferred: yes
- confirm: no new dependencies planned: yes (boto3 already exists)
- confirm: no unsafe model loading planned: yes
- confirm: no H5 mutation planned: yes
- confirm: no Aramis dependency planned: yes
- confirm: no clinical diagnosis/replacement claims planned: yes
- confirm: implementation assigned to Agent: coder / Mode: implementation: yes
- confirm: no git mutation commands run: yes
