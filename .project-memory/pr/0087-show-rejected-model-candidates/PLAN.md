# PR0087 — Show Every Discovered Joblib Model Candidate as Available or Disabled

## Goal

Extend the S3 model catalog discovery pipeline so that every Joblib model candidate discovered under `BREMEN_MODEL_CATALOG_URI` is product-visible. Previously, candidates that failed validation (manifest missing, invalid JSON, missing identity fields, package incompatibility, duplicate model_id) were silently hidden — visible only as `rejected_count` in the aggregate. PR0087 surfaces these as disabled non-selectable cards in the Start page and as `unavailable_models` in the `GET /demo/api/models` response, while exposing zero raw technical rejection detail.

## Current Production Evidence

Confirmed from the task: real App Runner logs show `candidate_count=2`, `available_count=1`, `rejected_count=1`. v0.1 accepted; v0.2.0 rejected with `portable_logreg missing required fields: {'threshold'}`. The current code correctly rejects v0.2.0 during Phase 3 package validation but surfaces zero public visibility beyond the aggregate count. This is the product gap PR0087 closes.

## PR0086 Baseline Confirmed

- Branch: `0087-show-rejected-model-candidates` — matches exactly.
- `adapt_model_package` present at `src/bremen/api/s3_model_discovery.py` line 22 (import) and line 539 (call).
- Working directory clean.
- HEAD: `063730fcac87b6a1036f2576049b325246cacdb7`.

## Blockers

None.

## Warnings

- No PR0085a (request-time refresh) exists in the codebase. `last_discovery_at` will always reflect the startup discovery timestamp. This is correct for the current architecture.
- The current Start page CSS uses `opacity: 0.5` for `.model-card.disabled`. BREMEN_DESIGN_SPEC_v1.md Section 7 specifies 40% opacity and `aria-disabled="true"`. The plan adjusts to spec.
- The current `candidate_count` counts manifest.json files. PR0087 redefines it to count unique package directories. This is additive and backward-compatible: every manifest.json corresponds to exactly one package directory, so counts for existing scenarios are identical. New scenarios (`.joblib`-only directories) add counted directories.
- Phase 3 failures (artifact staging, checksum, joblib load, package validation) currently increment `rejected_count` and log with `manifest_key` and truncated exception text. PR0087 must ensure that if these logs use `manifest_key`, that is acceptable for server-private logging but must never reach the public API/UI. The `_log.warning` call at line ~550 includes `manifest_key=%s` — this is server-private logging, not public API exposure, and is acceptable. However, the exception text truncation (`str(exc)[:100]`) potentially includes field names like `threshold`, `coef`, etc. The plan calls for sanitizing logged exception text to remove field names from Phase 3 error messages.

## Discovery Inventory Plan

### Current limitation

`_list_candidate_manifests()` (line 112 of `s3_model_discovery.py`) scans only for `manifest.json` objects at exactly one level below the catalog prefix. This excludes any package directory that contains only a `.joblib` artifact without a manifest, or a manifest that cannot be read/parsed.

### New scanner: `_discover_package_directories()`

Add a new function that replaces `_list_candidate_manifests()` as the entry-level scan:

```python
@dataclass
class PackageDirectoryInfo:
    """Internal representation of a discovered package directory."""
    name: str                     # Directory name (never exposed publicly)
    manifest_key: str | None      # S3 key of manifest.json, if any
    joblib_keys: list[str]        # S3 keys of .joblib artifacts found
    has_manifest: bool            # True if manifest.json exists
    has_joblib: bool              # True if at least one .joblib exists


def _discover_package_directories(s3_client, bucket, prefix) -> list[PackageDirectoryInfo]:
    """List all objects under prefix, group by immediate child directory.

    A candidate package directory is any immediate child directory of the
    catalog prefix that contains at least one of:
    - manifest.json
    - a .joblib object

    Returns sorted list (by directory name) for deterministic ordering.
    Does NOT recursively scan nested directories.
    Preserves existing behavior: only one level below prefix.
    """
```

This function:
1. Lists ALL objects under `prefix` using the existing paginator.
2. Groups objects by immediate child directory name (first path component after prefix).
3. For each directory, checks for `manifest.json` and `.joblib` objects.
4. Returns sorted list of `PackageDirectoryInfo` objects.

**Why this is safe**: The S3 list operation is identical to the existing one (same paginator, same bucket/prefix, same error handling). The only change is that the filter is broader (matches any manifest.json OR .joblib at depth 1, rather than only manifest.json).

### Revised `discover_models()` pipeline

```
Phase 0: Discover package directories
    _discover_package_directories() → list of PackageDirectoryInfo
    result.candidate_count = len(package_directories)

Phase 1: Manifest validation (per directory)
    For directories WITH manifest:
        Download and validate (base + discovery fields)
        Track success/failure
    For directories WITHOUT manifest:
        Skip Phase 1 manifest validation

Phase 2: Duplicate detection
    Count model_ids among Phase-1-passed manifests
    Mark duplicates

Phase 3: Full validation (per directory)
    For Phase-1-passed, non-duplicate directories with .joblib:
        Stage → checksum → load → adapt → validate → entry
    For Phase-1-passed, non-duplicate directories WITHOUT .joblib but WITH valid identity:
        Create identified disabled entry (not_compatible)
    For Phase-1-passed directories marked as duplicate:
        Create identified disabled entry (duplicate_entry)
    For directories with .joblib but Phase 1 failed (or no manifest):
        Create unregistered disabled entry (unregistered_package)

    Phase 3 stage failures for directories with valid manifest identity:
        Create identified disabled entry (not_compatible)
    Phase 3 stage failures for directories WITHOUT valid manifest identity:
        If .joblib exists → unregistered_package
        If no .joblib → aggregate only (no card)
```

### Candidate count semantics

- `candidate_count`: number of unique package directories discovered (immediate children of prefix containing at least one manifest.json or .joblib).
- `available_count`: number of entries with `availability="available"` in the registry.
- `rejected_count`: number of non-executable package directories (aggregate, may be >= unavailable_count).
- `unavailable_count`: number of public unavailable_models cards emitted.

### Boundary cases

| Directory contents | Phase 1 outcome | Phase 2 | Phase 3 | Display |
|---|---|---|---|---|
| manifest.json (valid) + .joblib (valid) | Pass | Unique | Pass | Available |
| manifest.json (valid) + .joblib (invalid) | Pass | Unique | Fail | Identified disabled (not_compatible) |
| manifest.json (valid) + no .joblib | Pass | Unique | N/A | Identified disabled (not_compatible) |
| manifest.json (valid, duplicate model_id) + .joblib | Pass | Duplicate | Skipped | Identified disabled (duplicate_entry) |
| manifest.json (valid, duplicate model_id) + no .joblib | Pass | Duplicate | Skipped | Identified disabled (duplicate_entry) |
| manifest.json (invalid JSON) + .joblib | Fail | - | - | Unregistered disabled (unregistered_package) |
| manifest.json (missing identity) + .joblib | Fail | - | - | Unregistered disabled (unregistered_package) |
| manifest.json (invalid identity fields) + .joblib | Fail | - | - | Unregistered disabled (unregistered_package) |
| manifest.json (invalid JSON) + no .joblib | Fail | - | - | Aggregate only (no card) |
| manifest.json (missing identity) + no .joblib | Fail | - | - | Aggregate only (no card) |
| No manifest + .joblib present | N/A | N/A | N/A | Unregistered disabled (unregistered_package) |
| No manifest + no .joblib | N/A | N/A | N/A | Not a candidate (not counted) |

### Phase 3 error-to-card mapping

When Phase 3 fails (artifact staging, checksum mismatch, joblib load failure, package validation failure), and the manifest already validated and passed Phase 1 complete:

- If `data` (validated manifest dict) is available from Phase 1: create identified disabled entry with `reason_category=not_compatible`.
- If `data` is None (can't happen in Phase 3 because only Phase-1-passed entries reach Phase 3): fall back to aggregate only.

### Duplicate handling details

- All manifests with the same `model_id` are rejected at Phase 2.
- At most one disabled identified card is emitted per duplicated `model_id`.
- The card uses the lexicographically first non-empty `display_name` among duplicate manifests.
- If duplicate manifests have different `display_name` values (e.g., "Dup A", "Dup B"), choose the lexicographically first. This is deterministic and stable.
- If duplicates have no valid `display_name` (should not happen since Phase 1 validates discovery fields including display_name), use `model_id` as fallback.

## Data Model Plan

### New type: `CatalogUnavailableEntry` (in `model_registry.py`)

```python
@dataclass(frozen=True)
class CatalogUnavailableEntry:
    """A display-only disabled model catalog entry.

    Not executable. Not selectable. Carries only safe public fields.
    Never carries _package, _checksum, S3 path, filename, or exception text.
    """
    kind: str                          # "identified" or "unregistered"
    reason_category: str               # Fixed public enum: not_compatible, duplicate_entry, unregistered_package
    candidate_label: str | None = None  # Generic ordinal for unregistered (e.g. "Discovered model package 1")
    model_id: str | None = None         # Only for identified kind
    display_name: str | None = None     # Only for identified kind
    workflow_id: str | None = None      # Only for identified kind

    def to_safe_dict(self) -> dict[str, Any]:
        """Return safe public fields only."""
        base = {
            "kind": self.kind,
            "reason_category": self.reason_category,
            "technical_demo_only": True,
            "scientifically_certified": False,
            "availability": "unavailable",
        }
        if self.kind == "identified":
            base["model_id"] = self.model_id
            base["display_name"] = self.display_name
            base["workflow_id"] = self.workflow_id
        else:
            base["candidate_label"] = self.candidate_label
        return base
```

**Home justification**: `model_registry.py` is the natural home because:
- `CatalogUnavailableEntry` is the disabled counterpart of `RegistryModelEntry`.
- Both are entry types that live inside the immutable `ModelRegistry` snapshot.
- Keeping them together makes the registry the single source of truth for both available and unavailable entries.
- `s3_model_discovery.py` remains focused on the discovery pipeline (listing, validation, loading) and produces `CatalogDiscoveryResult` which feeds the registry.

### Extended `ModelRegistry` (in `model_registry.py`)

```python
@dataclass(frozen=True)
class ModelRegistry:
    entries: tuple[RegistryModelEntry, ...] = field(default_factory=tuple)
    unavailable_entries: tuple[CatalogUnavailableEntry, ...] = field(default_factory=tuple)
    catalog_status: str = "not_configured"
    candidate_count: int = 0
    available_count: int = 0
    rejected_count: int = 0
    unavailable_count: int = 0
    last_discovery_at: str | None = None  # ISO-8601 UTC timestamp
```

New property:

```python
@property
def unavailable_count(self) -> int:
    return len(self.unavailable_entries)
```

Note: `unavailable_count` could be computed from `len(self.unavailable_entries)` but storing it explicitly avoids breaking existing constructor call patterns in `server.py`.

### Extended `RegistryModelEntry` (no changes needed)

`RegistryModelEntry.to_safe_dict()` already exposes all required fields. The existing `availability` field is sufficient: `"available"` for executable entries, the disabled entries live in `unavailable_entries` instead. No field changes to `RegistryModelEntry`.

### Extended `CatalogDiscoveryResult` (in `s3_model_discovery.py`)

```python
@dataclass
class CatalogDiscoveryResult:
    entries: list[RegistryModelEntry] = field(default_factory=list)
    unavailable_entries: list[CatalogUnavailableEntry] = field(default_factory=list)
    catalog_status: str = "not_configured"
    candidate_count: int = 0
    available_count: int = 0
    rejected_count: int = 0
    unavailable_count: int = 0
    last_discovery_at: str | None = None
    error_category: str | None = None
```

### Immutable snapshot contract

The `ModelRegistry` (frozen) holds both available and unavailable entries. After `initialize_registry()`, no entries can be added, removed, or modified. Request handlers read only the published snapshot. All aggregate counts and timestamps are frozen at snapshot time.

This preserves the PR0085 architecture: no request performs S3 listing, manifest download, artifact staging, checksum verification, or deserialization.

### Identifier generation for unregistered candidates

```python
def _generate_candidate_labels(unregistered_count: int) -> list[str]:
    """Generate deterministic generic labels for unregistered candidates.

    Labels are "Discovered model package 1", "Discovered model package 2", etc.
    Ordinal is deterministic within the response and does NOT encode
    S3 path, filename, checksum, or manifest contents.
    """
    return [f"Discovered model package {i+1}" for i in range(unregistered_count)]
```

The ordinal assignment must be deterministic: use the lexicographic order of the PackageDirectoryInfo entries sorted by directory name. This ensures the same S3 catalog prefix always produces the same label-to-directory mapping without exposing the directory name.

## API Exposure Plan

### `GET /demo/api/models` — additive changes

Add two new top-level fields to the existing response shape:

```json
{
  "unavailable_models": [
    {
      "kind": "identified",
      "reason_category": "not_compatible",
      "model_id": "bremen-mri-triage-logreg-v0-2-0",
      "display_name": "Bremen v0.2.0",
      "workflow_id": "bremen",
      "technical_demo_only": true,
      "scientifically_certified": false,
      "availability": "unavailable"
    },
    {
      "kind": "unregistered",
      "reason_category": "unregistered_package",
      "candidate_label": "Discovered model package 2",
      "technical_demo_only": true,
      "scientifically_certified": false,
      "availability": "unavailable"
    },
    {
      "kind": "identified",
      "reason_category": "duplicate_entry",
      "model_id": "dup-model",
      "display_name": "Dup A",
      "workflow_id": "bremen",
      "technical_demo_only": true,
      "scientifically_certified": false,
      "availability": "unavailable"
    }
  ],
  "unavailable_count": 3,
  "last_discovery_at": "2026-07-25T10:59:00.000000+00:00"
}
```

**`unavailable_models`**: New array field containing disabled display-only entries. Each entry follows the safe schema above. Empty array when no unavailable candidates exist.

**`unavailable_count`**: Integer length of `unavailable_models`. May be less than `rejected_count` when rejected candidates have no safe display identity and no `.joblib` artifact (aggregate-only).

**`last_discovery_at`**: ISO-8601 UTC timestamp of the discovery attempt that produced the current registry snapshot. Set to the time `discover_models()` returned, captured at the start of discovery.

### Existing fields remain unchanged

- `models` — only available executable entries (same as today).
- `default_model_id` — computed only from available entries.
- `candidate_count`, `available_count`, `rejected_count` — same semantics (redefined `candidate_count` to count directories, but backward-compatible).
- `status`, `catalog_timestamp` — unchanged.
- `request_id`, `technical_demo_only` — unchanged.

### Safety: `resolve_model()` must reject unavailable-only model_ids

The existing `resolve_model()` in `model_catalog.py` calls `registry.get_entry(model_id)` which only searches `entries`, not `unavailable_entries`. This means:

- Submitting a job with a model_id that appears only in `unavailable_models` → `ModelNotFoundError` → HTTP 400 safe error.
- Submitting a job with an unregistered candidate label (not a valid model_id format) → `ModelNotFoundError` → HTTP 400 safe error.

No changes needed to `resolve_model()` or job creation — the existing registry lookup automatically excludes unavailable entries.

### Singular `GET /model/version` unchanged

The singular model version endpoint reads from `ModelState`, not from the catalog registry. It remains unchanged.

## Start Page Rendering Plan

### Disabled cards

The Start page JavaScript at `start_page_ui.py` currently renders model cards from the `models` array. PR0087 must also render cards from the `unavailable_models` array.

**Location**: After the available model cards loop, append disabled cards.

**CSS classing**: Use existing `.model-card.disabled` class with the following adjustments per BREMEN_DESIGN_SPEC_v1.md Section 7:

```css
.model-card.disabled {
  opacity: 0.4;                    /* Changed from 0.5 to 0.4 per spec */
  cursor: not-allowed;
}
.model-card[aria-disabled="true"] {
  opacity: 0.4;
  cursor: not-allowed;
}
```

The existing `.model-card.disabled` rule should be updated to `opacity: 0.4` (was 0.5) to match the spec.

**Status rail**: Use gray status rail with `--status-unconfigured`:

```css
.model-status-rail.unavailable {
  background: var(--tint-error);  /* Changed from --tint-pending to --tint-error? No, spec says gray */

  /* Per spec Section 7: gray status rail using --status-unconfigured */
  background: #9AA3A8;  /* or use variable */
  color: #FFFFFF;
}
```

Wait — let me re-read the spec: "gray status rail using --status-unconfigured". The `--status-unconfigured` token is `#9AA3A8`. So for disabled cards, the status rail should use `--status-unconfigured` background with white text.

Currently the CSS has:
```css
.model-status-rail.unavailable{background:var(--tint-pending);color:var(--status-pending)}
```

This should be replaced with a new class, or the existing `.disabled` card logic should use a different rail color. Let me plan this precisely:

For disabled cards, the status rail should use:
- `background: var(--status-unconfigured)` — `#9AA3A8`
- `color: #FFFFFF` — white text for contrast on gray

**Reason caption**: Static text, not hover-only, present on every disabled card:

| reason_category | Public caption |
|---|---|
| `not_compatible` | "Not compatible with the current runtime" |
| `duplicate_entry` | "Duplicate model identity" |
| `unregistered_package` | "Model package is not registered" |

**No selectable controls**: Disabled cards must not be clickable, must not respond to Enter/Space keys, must not show radio dot selection, and must not be included in the radiogroup.

**DOM structure** for a disabled identified card:

```html
<div class="model-card disabled" aria-disabled="true" role="presentation">
  <div class="model-radio" style="visibility:hidden">
    <div class="model-radio-dot"></div>
  </div>
  <div class="model-info">
    <div class="model-name">Bremen v0.2.0</div>
    <div class="model-meta">Version: v0.2.0</div>
    <div class="model-status-rail unavailable">Unavailable</div>
    <div class="model-reason">Not compatible with the current runtime</div>
  </div>
</div>
```

For unregistered:

```html
<div class="model-card disabled" aria-disabled="true" role="presentation">
  <div class="model-radio" style="visibility:hidden">
    <div class="model-radio-dot"></div>
  </div>
  <div class="model-info">
    <div class="model-name">Discovered model package 2</div>
    <div class="model-meta">Unregistered package</div>
    <div class="model-status-rail unavailable">Unavailable</div>
    <div class="model-reason">Model package is not registered</div>
  </div>
</div>
```

**JavaScript changes in `start_page_ui.js`**:

- The `loadModelCatalog()` callback must render both `data.models` and `data.unavailable_models`.
- Disabled cards append after available cards in the same grid.
- Event listeners attach only to `.model-card:not(.disabled)` as before.
- `role="radiogroup"` remains on the grid but disabled cards use `role="presentation"` to avoid violating radiogroup accessibility.

**Existing disabled card code update**: The current JavaScript already has a disabled card rendering path:

```javascript
var isDisabled = !isAvail ? ' disabled' : '';
```

This path currently renders model cards with `availability="unavailable"` from the `models` array. After PR0087, unavailable cards move to `unavailable_models`. The `models` array should contain only `availability="available"` entries. The existing `models` entries with `availability="unavailable"` should migrate to `unavailable_models`.

Wait — the existing code in `start_page_ui.js` already handles `availability`:

```javascript
var isAvail=m.availability==='available';
var isDisabled=!isAvail?' disabled':'';
```

And the existing `build_model_catalog()` already includes entries with `availability="unavailable"` in the `models` array. Let me check... 

Looking at `build_model_catalog()`:
```python
models = [e.to_safe_dict() for e in registry.entries]
```

And `registry.entries` contains all `RegistryModelEntry` objects, including those with `availability="unavailable"` if someone sets that. Currently, rejected candidates don't get entries at all. So the `availability` field on `RegistryModelEntry` is not used for discovery-pipeline entries — all `RegistryModelEntry` objects in catalog mode have `availability="available"`.

For the legacy `build_legacy_registry()`:
```python
availability="available" if model_ready else "unavailable"
```

So the existing UI JavaScript already has the pattern for handling disabled cards, but it's only used in legacy mode when `model_ready=False`.

For PR0087, the approach is clean: unavailable entries live in `unavailable_models`, not in `models`. The `models` array contains only available entries.

### Catalog caption

Under the model grid, add a small unobtrusive text:

```html
<div class="catalog-caption" id="catalog-caption"></div>
```

CSS:

```css
.catalog-caption{font-size:var(--fs-13);color:var(--text-secondary);text-align:center;margin-top:var(--sp-8);margin-bottom:var(--sp-16)}
```

JavaScript populates this from the API response:

```javascript
var caption = document.getElementById('catalog-caption');
if (data.status === 'discovery_failed') {
  caption.textContent = 'Catalog: discovery unavailable';
} else if (data.candidate_count > 0) {
  var time = data.last_discovery_at ? new Date(data.last_discovery_at).toLocaleTimeString() : '';
  caption.textContent = 'Catalog: ' + data.available_count + ' of ' + data.candidate_count + ' discovered models available' +
    (time ? ' \u00b7 last checked ' + time : '');
}
```

**Placement**: After the model grid but before the actions row (or after actions row, below the CTA button). The exact position is: after `.model-grid` div and before `.start-actions` div, or after `.start-actions`. The task says "under the model-card grid", so between grid and actions, or after actions. After actions is more natural — it's footer-level metadata.

## Catalog Observability Plan

### API response fields (in `GET /demo/api/models`)

| Field | Type | Present when | Description |
|---|---|---|---|
| `catalog_status` | str | always | Already present as `status` field. No duplicate needed. |
| `candidate_count` | int | catalog mode | Already present. |
| `available_count` | int | catalog mode | Already present. |
| `rejected_count` | int | catalog mode | Already present. |
| `unavailable_count` | int | catalog mode | NEW. Number of public unavailable_models cards. |
| `last_discovery_at` | str\|null | catalog mode | NEW. ISO-8601 UTC of last discovery. |

No duplicate fields: `catalog_status` is already carried by `status`. The existing field name `status` is kept and augmented with `unavailable_count` and `last_discovery_at`.

### Start page caption

Small secondary text under the model grid or footer area:

```
Catalog: 1 of 2 discovered models available · last checked 10:59 AM
```

Or for discovery_failed:

```
Catalog: discovery unavailable
```

No raw AWS error. No prominent panel. No fourth hero badge.

### Health `model_ready` unchanged

The health endpoint and `model_ready` semantics remain based only on `available_count > 0`. Unavailable entries do not make the system "healthy" for inference.

## Logging Plan

### Current logs with privacy concerns

Current `_log.warning` at s3_model_discovery.py line ~550:
```python
_log.warning(
    "bremen.catalog.candidate.rejected\t"
    "manifest_key=%s\terror_category=%s",
    manifest_key, str(exc)[:100],
)
```
The `str(exc)[:100]` truncation can leak field names like `threshold`, `coef`, `feature_schema_version`. However, `manifest_key` is server-private logging — not public API.

### Proposed safe logs

| Event | Log line | Location |
|---|---|---|
| Catalog inventory started | `bremen.catalog.inventory.start\tcandidate_count=N` | Start of Phase 0 |
| Catalog inventory completed | `bremen.catalog.inventory.completed\tunique_directories=N` | End of Phase 0 |
| Candidate accepted | `bremen.catalog.candidate.accepted\tmodel_id=X` | Phase 3 success (already exists) |
| Candidate rejected (identified, safe id) | `bremen.catalog.candidate.rejected\treason_category=X\tmodel_id=Y` | Phase 2/3 rejection with safe id |
| Unregistered package found | `bremen.catalog.candidate.unregistered_package` | .joblib-only or Phase 1 failure with .joblib |
| Duplicate found | `bremen.catalog.candidate.rejected\treason_category=duplicate_entry\tmodel_id=X` | Phase 2 duplicate |
| Catalog response emitted | `bremen.catalog.response.emitted\tavailable_count=X\tunavailable_count=Y\tcandidate_count=Z` | `build_model_catalog()` |

### Log sanitization debt

The existing `str(exc)[:100]` in Phase 3 error logging should be replaced with a safe `reason_category` string. The raw exception text is not needed for server-private debugging — the full traceback is captured by `logging.exception()` when available, or the error type alone gives sufficient signal.

**Implementation**: Replace `str(exc)[:100]` with a safe truncated classification:
```python
_log.warning(
    "bremen.catalog.candidate.rejected\t"
    "reason_category=not_compatible\tmodel_id=%s",
    model_id,
)
```

The `manifest_key` in Phase 1 error logs is acceptable for server-private debugging but should not be used in logs that also carry model_id for Phase 3 failures. If Phase 3 rejection uses `manifest_key`, it should be removed in favor of `model_id`.

## Reason Category Set (Fixed Public Enum)

| `reason_category` | Meaning | Public caption |
|---|---|---|
| `not_compatible` | Safe identity or artifact present, but candidate cannot be executed by current runtime | "Not compatible with the current runtime" |
| `duplicate_entry` | Same validated `model_id` appears in more than one manifest | "Duplicate model identity" |
| `unregistered_package` | .joblib artifact exists but no valid safe manifest identity | "Model package is not registered" |
| `discovery_unavailable` | Catalog-level discovery failure | "Catalog discovery unavailable" |

**Never exposed categories**: `portable_logreg`, `feature_schema_version`, `checksum_mismatch`, `manifest_key`, `model_filename`, `joblib_load_error`, `AccessDenied`, `s3_listing`, or any other technical detail.

**UI copy mapping**: A fixed lookup dict in the JavaScript maps `reason_category` to the public caption. Raw `reason_category` is never rendered directly.

```javascript
var reasonCaptions = {
  'not_compatible': 'Not compatible with the current runtime',
  'duplicate_entry': 'Duplicate model identity',
  'unregistered_package': 'Model package is not registered',
  'discovery_unavailable': 'Catalog discovery unavailable'
};
```

## Safety Boundary Confirmation

| Invariant | Confirmed |
|---|---|
| Raw rejection details remain server-private | Yes. Only `reason_category` (fixed enum) and safe identity fields reach API/UI. |
| Phase-1 failures without .joblib or safe identity remain aggregate-only | Yes. No card created. |
| Phase-1 failures WITH .joblib surface only as generic `unregistered_package` | Yes. `candidate_label` only, no model_id, no path. |
| No rejected manifest field name reaches public API/UI | Yes. Never. |
| No rejected manifest value reaches public API/UI | Yes. Never. |
| No object path, filename, checksum, or raw exception reaches public API/UI | Yes. `candidate_label` is a generic ordinal, not a path. |
| Disabled cards are never selectable | Yes. Not in radiogroup, not clickable, no Enter/Space handler. |
| Disabled candidates are never executable | Yes. `resolve_model()` only searches `entries`, not `unavailable_entries`. |
| Scientific certification remains false | Yes. Hardcoded false for both available and unavailable. |
| Technical demo language remains present | Yes. `technical_demo_only: true` on all cards. |
| `default_model_id` computed only from available models | Yes. Original code uses `registry.available_entries` for default. |
| Health `model_ready` depends only on available models | Yes. No change to health logic. |

## Validation Plan

### Python compilation

```bash
python -m compileall src tests
```

### Existing test baseline (must still pass)

```bash
python -m pytest -q tests/test_s3_model_discovery.py -v
python -m pytest -q tests/test_catalog_api_multi_model.py -v
python -m pytest -q tests/test_bremen_api_server.py -v
python -m pytest -q  # Full suite
git diff --check
```

### New test class: `TestUnavailableModels` (in `test_s3_model_discovery.py`)

1. `test_available_model_selectable`: Valid manifest + matching .joblib → appears in `models`, not in `unavailable_models`, selectable.

2. `test_phase3_rejection_identified_disabled`: Valid manifest (model_id, display_name present) but package missing threshold → appears in `unavailable_models` with `reason_category=not_compatible`, `kind=identified`, valid `model_id` and `display_name`, NOT in `models`.

3. `test_phase3_rejection_no_raw_detail`: Same as test 2, but prove no raw exception text, field name, S3 key, or checksum appears anywhere in the public response.

4. `test_duplicate_model_id_disabled_once`: Two manifests with same model_id, one has .joblib, other has .joblib → one disabled card in `unavailable_models` with `reason_category=duplicate_entry`. The other duplicate does not create a second card. Both rejected_count=2.

5. `test_joblib_only_unregistered`: Directory with .joblib, no manifest → `unavailable_models` entry with `kind=unregistered`, `reason_category=unregistered_package`, `candidate_label="Discovered model package 1"`, no `model_id`.

6. `test_joblib_invalid_manifest_unregistered`: Directory with .joblib and invalid JSON manifest → `unavailable_models` entry with `kind=unregistered`, `reason_category=unregistered_package`.

7. `test_joblib_manifest_missing_model_id_unregistered`: Directory with .joblib and manifest missing `model_id` → `unavailable_models` entry with `kind=unregistered`.

8. `test_manifest_only_no_joblib_aggregate`: Directory with manifest only (no .joblib) and invalid identity fields → no `unavailable_models` entry (aggregate-only). `rejected_count` incremented.

9. `test_manifest_only_valid_identity_no_joblib_identified`: Directory with manifest (valid identity) but no .joblib → `unavailable_models` entry with `kind=identified`, `reason_category=not_compatible`.

10. `test_unavailable_not_executable`: model_id appearing only in `unavailable_models` cannot be submitted to POST /demo/api/jobs — fails with safe error.

11. `test_unregistered_label_not_resolvable`: unregistered candidate label cannot be submitted — fails with safe error.

12. `test_available_and_unavailable_coexist`: One available, one identified disabled, one unregistered → both `models` and `unavailable_models` populated correctly.

13. `test_default_model_id_from_available_only`: One available + one unavailable → `default_model_id` is the available model's id.

14. `test_no_default_when_zero_available`: Zero available + two unavailable → `default_model_id` is `None`.

15. `test_catalog_counts`: Three directories (1 available, 1 identified disabled, 1 unregistered) → `candidate_count=3`, `available_count=1`, `rejected_count=2`, `unavailable_count=2`.

### New test class: `TestCatalogApiUnavailable` (in `test_catalog_api_multi_model.py`)

16. `test_unavailable_models_field_present`: `build_model_catalog()` response includes `unavailable_models` (array), `unavailable_count` (int), `last_discovery_at` (str or null).

17. `test_unavailable_models_not_affect_model_version_endpoint`: `GET /model/version` unchanged by unavailable entries.

### New test class: `TestStartPageDisabledCards` (in `test_bremen_api_server.py`)

18. `test_start_page_renders_disabled_cards`: GET /demo returns HTML containing `aria-disabled="true"`, `opacity` styles, and reason caption text for disabled cards.

19. `test_start_page_catalog_caption`: GET /demo returns HTML containing catalog caption with counts and last checked time.

20. `test_start_page_discovery_failed_caption`: When `status=discovery_failed`, catalog caption shows "Catalog: discovery unavailable" and no raw AWS error.

### Safety grep checks

```bash
# No leaked fields in UI
grep -rn "feature_schema_version\\|manifest_key\\|checksum\\|portable_logreg\\|model_filename" src/bremen/start_page_ui.py || true
# Expected: no output

# No raw exception formatting in public response/UI
grep -rn "str(exc)\\|repr(exc)\\|exception" src/bremen/api/model_catalog.py src/bremen/start_page_ui.py || true
# Expected: no output

# No AWS references in UI
grep -rn "AccessDenied\\|assumed-role\\|arn:aws\\|s3://" src/bremen/start_page_ui.py src/bremen/api/model_catalog.py || true
# Expected: no output

# Reason category set validation
grep -n 'reason_category.*=' src/bremen/api/s3_model_discovery.py src/bremen/api/model_registry.py src/bremen/api/model_catalog.py || true
# Confirm only: not_compatible, duplicate_entry, unregistered_package, discovery_unavailable
```

### Log safety check

```bash
grep -rn "manifest_key" src/bremen/api/s3_model_discovery.py
# Confirm manifest_key appears only in Phase 1 log lines, not in Phase 3 log lines with model_id
# If manifest_key appears in Phase 3 rejection logs, it must be removed
```

## Non-Goals Confirmed

- No enabling non-compliant models — disabled cards are display-only, never executable.
- No runtime fallback to execute invalid packages — `resolve_model()` rejects them.
- No public technical rejection detail — only fixed reason_category enum.
- No admin console, auth/RBAC, operator-only page.
- No polling, no new refresh mechanism — startup-only discovery (no PR0085a).
- No S3 writes — reading catalog prefix only.
- No manifest disabled flag — rejected status derived from validation outcome, not manifest field.
- No promotion workflow, no ModelVariant, no comparison mode, no ensemble.
- No scientific certification — hardcoded `false`.
- No training, preprocessing, feature extraction, threshold policy, decision vocabulary changes.
- No Docker, Terraform, AWS, CI changes.
- No React/frontend build step — pure hand-written start_page_ui.py extension.
- POST /predictions schema unchanged: no new fields.
- `GET /model/version` singular endpoint unchanged.
- No raw patient data, H5 contents, or Section 21 prohibited data.

## Stop Conditions Confirmed

| Condition | Status |
|---|---|
| PR0086 adapter fix present? | Confirmed at lines 22 and 539 of s3_model_discovery.py |
| Plan exposes raw exception text, field name, rejected value, S3 key, filename, checksum, AWS ARN, or package internals in public API/UI? | No. Only safe `reason_category` and safe identity fields. |
| Plan makes disabled candidates executable? | No. `resolve_model()` excludes them. |
| Plan changes job schema or inference behavior? | No. Only display/catalog layer. |
| Plan derives public identity from S3 path or filename? | No. `candidate_label` is a generic ordinal. `model_id` comes from manifest only. |
| Plan invents new disabled-card visual treatment instead of reusing Section 2.7? | No. Uses `.model-card.disabled` with `aria-disabled="true"` and `opacity: 0.4` per spec. |
| Plan creates open-ended or per-exception public reason categories? | No. Fixed enum of 4 values. |
| Plan hides discovered .joblib artifacts completely without product-level justification? | No. All .joblib-containing directories surface as cards. |
| Plan requires infrastructure, AWS, Docker, CI, or training changes? | No. |

## Files to Change

| File | Change |
|---|---|
| `src/bremen/api/s3_model_discovery.py` | Add `_discover_package_directories()`, `PackageDirectoryInfo` dataclass, `_generate_candidate_labels()`. Restructure `discover_models()` to use directory-centric flow. Extend `CatalogDiscoveryResult`. Add unavailable entry creation logic. Sanitize Phase 3 error logging. |
| `src/bremen/api/model_registry.py` | Add `CatalogUnavailableEntry` frozen dataclass with `to_safe_dict()`. Extend `ModelRegistry` with `unavailable_entries`, `last_discovery_at`. |
| `src/bremen/api/model_catalog.py` | Extend `build_model_catalog()` to add `unavailable_models`, `unavailable_count`, `last_discovery_at` to response. Serialize `CatalogUnavailableEntry` via `to_safe_dict()`. |
| `src/bremen/api/server.py` | Extend `ModelRegistry()` constructor call in catalog startup path to pass `unavailable_entries`, `last_discovery_at`. |
| `src/bremen/start_page_ui.py` | Update CSS: change `.model-card.disabled` opacity to 0.4, add `aria-disabled` selector, update status rail for disabled cards to use `--status-unconfigured`. Update JavaScript: render `unavailable_models` cards, add catalog caption, add reason caption lookup. |
| `tests/test_s3_model_discovery.py` | Add `TestUnavailableModels` with tests 1-14 listed above. Add helper functions for creating package directories with/without manifests. |
| `tests/test_catalog_api_multi_model.py` | Add `TestCatalogApiUnavailable` with tests 16-17. |
| `tests/test_bremen_api_server.py` | Add `TestStartPageDisabledCards` with tests 18-20. |
| `docs/api_contract.md` | Document new `unavailable_models`, `unavailable_count`, `last_discovery_at` fields in `GET /demo/api/models` contract. Document safety rules for disabled entries. |

## Next Required Action

Present PLAN.md to plan_review agent for approval.

---

Implementation agent: coder
