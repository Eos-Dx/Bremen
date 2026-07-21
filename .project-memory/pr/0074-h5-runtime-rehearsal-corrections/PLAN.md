# PR 0074 — Plan H5 Runtime Rehearsal Corrections

Author: plan
Mode: planning only
Branch: 0074-h5-runtime-rehearsal-corrections

## PR0073 rehearsal postmortem

1. **The route-level test fixture did not contain a calibration image resembling real structure.** The Matador fixture had no 2D calibration dataset under a calibration subtree that could be confused with a patient measurement. PR0073's `_meas_visitor` treated all 2D numeric datasets as measurements — a rule that works for a clean fixture but fails for the real container.

2. **The fixture did not use `organSide`.** The fixture used `side` as the attribute name. The real container uses `organSide`. PR0073's side metadata resolution did not include this attribute key, so the real container raised `Missing side metadata for measurement(s)`.

3. **The fixture did not prove P1/P2/P3 pairing against names containing other tokens.** The fixture had clean dataset names. The real container has measurement dataset names like `measurement_data_P1` which contain position tokens embedded among other text. The fallback pair-key extraction stripped left/right from the dataset name, leaving unwanted tokens.

4. **Session container_id-only regression was not represented correctly.** The session adapter calls `_validate_ref()` before the automatic pair-selection branch. The test fixture always supplied explicit refs, so this code path was never exercised in tests.

5. **Error-stage tests did not cover real exception classes.** `H5ContainerError` and `H5MetadataError` are subclasses of `Exception` but not `RuntimeError`/`ValueError`. The `except (RuntimeError, ValueError, ...)` block does not catch them. They fall through to the generic `except Exception:` which hardcodes `inference_failed`.

6. **Metadata-safety tests did not assert absence of internal H5 paths.** The `str(exc)[:200]` pattern in error details exposed internal dataset paths and measurement filenames.

## Confirmed deployed defects

1. **Session no-ref regression**: `_validate_ref` called before automatic pair detection → `ValueError: target_scan_ref must be a non-empty string`.
2. **Calibration dataset misclassified as measurement**: `_meas_visitor` treats ALL 2D numeric datasets as measurements; calibration 2D datasets incorrectly enter the measurement list.
3. **`organSide` attribute unsupported**: Side metadata reader does not include `organSide`.
4. **Pair-key extraction unreliable**: Fallback stripping left/right from filenames leaves extraneous tokens; position tokens like `P1` must be extracted explicitly.
5. **Incorrect stage classification**: `H5ContainerError`/`H5MetadataError` fall through to generic `except Exception:` which hardcodes `inference_failed`. Stage must be determined by typed exception, not substring matching on error messages.
6. **Unsafe error details**: `str(exc)[:200]` exposes internal H5 paths and measurement filenames.

## Required reads — observed facts

### `src/bremen/api/h5_layouts.py`
- `SessionLayoutH5Adapter.resolve_prediction_context()` calls `_validate_ref()` (line 480-481) BEFORE the automatic pair-selection block (line 494+).
- `MatadorRawH5Adapter._meas_visitor()` walks ALL 2D numeric datasets indiscriminately — does not exclude calibration subtree datasets.
- Side metadata keys: `("side", "breast_side", "sample_side")` — does not include `"organSide"`.
- Pair-key fallback strips left/right from dataset name — does not extract `P<number>` tokens.
- `_resolve_attr()` does case-insensitive lookup but only via explicit key list.

### `src/bremen/api/server.py`
- Stage classification (lines 1051-1063): substring matching against exception message. Falls through to `inference_failed` for exceptions not matched by keywords.
- Exception hierarchy: `H5ContainerError(Exception)`, `H5MetadataError(Exception)` — NOT `RuntimeError`, `ValueError`, `KeyError`, `TypeError`.
- Error detail (line 1068): `f"{type(exc).__name__}: {str(exc)[:200]}"` — exposes internal paths.

### `src/bremen/api/preflight.py`
- `H5ContainerError(Exception)`, `H5MetadataError(Exception)` — both inherit directly from `Exception`.

### Tests
- 1368 tests pass.

## Implementation agent

- **Agent**: coder
- **Mode**: implementation

## Allowed implementation files

1. **`src/bremen/api/h5_layouts.py`** — MODIFY. Fix all 6 defects.
2. **`src/bremen/api/server.py`** — MODIFY. Fix stage classification and error safety.
3. **`tests/test_bremen_h5_layouts.py`** — MODIFY. Add real-like fixture tests.
4. **`tests/test_bremen_api_server.py`** — MODIFY. Add route-level tests.

**Allowed only if justified**:
- `src/bremen/api/preflight.py` — only if exception hierarchy needs restructuring.

## Forbidden files

- `.github/**`, `infra/terraform/**`, `Dockerfile`, `Dockerfile.training`
- `requirements.txt`, `pyproject.toml`, `config/training/**`, `src/bremen/training/**`
- `frontend/**`, `web/**`, `ui/**`, `package.json`, `package-lock.json`, `*.lock`, `node_modules/**`
- `tests/data/**`
- Any `.h5`, `.hdf5`, `.joblib`, `.pkl`, `.npy`, `.npz`, `.tfstate`, `.terraform`
- `docs/**`, `ROADMAP.md`
- Aramis artifacts

## Exact implementation scope

### 1. Session no-ref regression fix (`h5_layouts.py`)

Move `_validate_ref` AFTER the automatic pair detection, or skip it when both refs are empty strings:

```python
def resolve_prediction_context(self, h5_file, target_scan_ref, control_scan_ref):
    # Determine if explicit refs are provided
    t_ref_provided = bool(target_scan_ref and target_scan_ref.strip())
    c_ref_provided = bool(control_scan_ref and control_scan_ref.strip())

    if t_ref_provided and c_ref_provided:
        # Validate and use explicit refs
        t_ref = _validate_ref(target_scan_ref, "target_scan_ref")
        c_ref = _validate_ref(control_scan_ref, "control_scan_ref")
        # ... use provided refs ...
    elif not t_ref_provided and not c_ref_provided:
        # Automatic pair detection
        sets_group = h5_file["/session/sets"]
        # ... existing automatic pair logic ...
    else:
        # Exactly one ref provided — error
        raise ValueError(
            "Both target_scan_ref and control_scan_ref must be provided together"
        )
```

### 2. Calibration dataset exclusion (`h5_layouts.py`)

Replace the generic `_meas_visitor` with a two-phase discovery:

**Phase 1**: Discover calibration subtree(s). Walk the H5 to find groups/datasets that contain calibration/PONI keywords. Record the paths of calibration subtrees.

**Phase 2**: Discover measurement datasets. Walk ONLY non-calibration subtrees. Exclude any dataset whose path starts with a known calibration subtree path.

```python
# Phase 1: Discover calibration subtrees
calib_subtree_prefixes = set()
def _calib_finder(name, obj):
    name_lower = name.lower()
    if any(kw in name_lower for kw in ('poni', 'calib', 'calibration')):
        # Record the containing group
        prefix = "/" + "/".join(name.split("/")[:-1]) if "/" in name else ""
        if prefix:
            calib_subtree_prefixes.add(prefix)
h5_file.visititems(_calib_finder)

# Phase 2: Discover measurement datasets (exclude calibration subtrees)
def _meas_visitor(name, obj):
    if isinstance(obj, h5py.Dataset) and len(obj.shape) >= 2 and obj.dtype.kind in ('f', 'i', 'u'):
        # Exclude datasets under calibration subtrees
        for prefix in calib_subtree_prefixes:
            if name.startswith(prefix.lstrip("/")):
                return
        measurements.append({...})
h5_file.visititems(_meas_visitor)
```

### 3. `organSide` attribute support (`h5_layouts.py`)

Add to the side attribute key list:

```python
SIDE_ATTR_KEYS = ("side", "breast_side", "sample_side", "organSide", "organ_side")
```

The existing `_resolve_attr` already does case-insensitive lookup via `ak.lower() == k.lower()`, so adding `"organSide"` will correctly match `organSide`, `organside`, `OrganSide`, etc.

### 4. Position/pair-key extraction (`h5_layouts.py`)

Replace the fallback pair-key extraction with explicit `P<number>` token extraction:

```python
import re

def _extract_position_token(dataset_name: str) -> str | None:
    """Extract a position token like P1, P2, P3 from a dataset name.

    Returns the matched token (e.g., 'P1') or None if no valid token found.
    Only matches the pattern P followed by digits.
    Does NOT match patient/sample identifiers or other filename components.
    """
    match = re.search(r'[Pp](\d+)', dataset_name)
    if match:
        return f"P{match.group(1)}"
    return None
```

In the measurement visitor, after reading attributes:

```python
# Position from attribute (preferred)
m["pair_key"] = _resolve_attr(attrs, POS_ATTR_KEYS)
# Fallback: extract P<number> token from dataset name (not full filename)
if m["pair_key"] is None:
    ds_name = m.get("dataset_name", "")
    token = _extract_position_token(ds_name)
    if token:
        m["pair_key"] = token
    else:
        # No position token found — cannot pair
        m["pair_key"] = None  # Will be caught by missing-pair validation
```

### 5. Typed stage classification (`server.py`)

Replace substring-based stage inference with typed exception matching:

```python
except (H5ContainerError, H5MetadataError, H5PatientMismatchError, H5SideMismatchError) as exc:
    # Preflight validation failures
    event_name = "h5_preflight_failed"
    _log.exception("bremen.demo.analyze.preflight_failed...")
    
except (PreprocessingBridgeError, PreflightNotPassedError) as exc:
    # Preprocessing/integration failures
    event_name = "preprocessing_failed"
    _log.exception("bremen.demo.analyze.preprocessing_failed...")
    
except (PortableLogRegModelError, FeatureArtifactPredictionError, FeatureArtifactPredictorError) as exc:
    # Model inference failures
    event_name = "inference_failed"
    _log.exception("bremen.demo.analyze.inference_failed...")
    
except (RuntimeError, ValueError, KeyError, TypeError) as exc:
    # General runtime errors — classify by message as fallback
    err_str = str(exc).lower()
    if "preflight" in err_str:
        event_name = "h5_preflight_failed"
    elif "preprocessing" in err_str or "bridge" in err_str:
        event_name = "preprocessing_failed"
    else:
        event_name = "inference_failed"
```

Import the typed exceptions:

```python
from ..api.preflight import H5ContainerError, H5MetadataError, H5PatientMismatchError, H5SideMismatchError
from ..api.preprocessing_bridge import PreprocessingBridgeError, PreflightNotPassedError
from ..inference import PortableLogRegModelError
```

### 6. Safe error details (`server.py`)

Replace `str(exc)[:200]` with a safe detail mapping:

```python
def _safe_error_detail(exc: Exception) -> str:
    """Map an internal exception to a safe public error detail.
    
    No internal H5 paths, measurement filenames, S3 URIs,
    patient/sample identifiers, or attribute values are exposed.
    """
    if isinstance(exc, H5ContainerError):
        return "H5 container structure validation failed"
    if isinstance(exc, H5MetadataError):
        return "H5 metadata validation failed"
    if isinstance(exc, H5PatientMismatchError):
        return "Patient mismatch detected"
    if isinstance(exc, H5SideMismatchError):
        return "Side mismatch detected"
    if isinstance(exc, PreprocessingBridgeError):
        return "Preprocessing failed"
    if isinstance(exc, PreflightNotPassedError):
        return "Preflight not passed"
    if isinstance(exc, (PortableLogRegModelError, FeatureArtifactPredictionError)):
        return "Model inference failed"
    # Fallback for unexpected exceptions
    return f"Internal error: {type(exc).__name__}"
```

The full stack trace is preserved in server logs via `_log.exception()` — this is where developers debug. API responses receive only the safe public message.

## Preflight exception hierarchy (check only)

Verify that `H5ContainerError`, `H5MetadataError`, `H5SideMismatchError`, `H5PatientMismatchError` all inherit from `Exception`. If they do not, they won't be caught by the typed except clauses and will fall through to the generic `except Exception:` fallback.

## Real-like controlled fixtures

**Session fixture** (temp HDF5, not committed):
- `/session/sets/set_001_sample_main/integration/{q,i}` (float arrays)
- `/session/sets/contralateral_set_001_sample_main/integration/{q,i}`
- No `/scans/target`
- No explicit refs in HTTP request body

**Matador fixture** (temp HDF5, not committed):
- `/calibration/distance` (scalar float), `/calibration/poni` (scalar float or string)
- `/measurements_0/measurement_data` (2D float array, shape like (512,512))
  - Attribute `organSide="LEFT"`, dataset name containing `P1`
- `/measurements_1/measurement_data` (same shape)
  - Attribute `organSide="RIGHT"`, dataset name containing `P1`
- Optionally a 2D calibration dataset under `/calibration/calib_image` (2D float) — must be excluded from measurements
- No `/scans/target`, no `/session/sets`, no `/scans/contralateral`

## Route-level tests

**Session success** (no explicit refs):
```python
def test_session_no_refs_success(self, server_info):
    host, port, _ = server_info
    # Create temp session H5
    # Upload/register via S3 mock (use existing test S3 fake)
    # POST /demo/api/h5/analyze with {"container_id": "<key>"}
    # Assert: status completed, events include h5_preflight_completed, preprocessing_completed, model_inference_completed, completed
```

**Matador success**:
```python
def test_matador_real_like_success(self, server_info):
    host, port, _ = server_info
    # Create temp Matador H5 with calibration + measurements + organSide + P1/P2
    # Mock perform_azimuthal_integration at wrapper boundary
    # POST /demo/api/h5/analyze
    # Assert: status completed, calibration excluded, organSide resolved, P1 paired, integration called
```

## Failure tests

- Session with exactly one explicit ref → safe error
- Matador with missing `organSide` → `h5_preflight_failed`
- Matador with unsupported side value → `h5_preflight_failed`
- Matador with missing P token → `h5_preflight_failed`
- Matador with duplicate side/P token → `h5_preflight_failed`
- Matador with incomplete bilateral position → `h5_preflight_failed`
- Calibration dataset never reported as missing-side measurement → verify measurement count excludes calib
- Public error contains no H5 path or measurement filename → regex assertion
- Preflight errors emit only `h5_preflight_failed` → not `inference_failed`
- Preprocessing errors emit only `preprocessing_failed` → not `inference_failed`
- Source H5 checksum unchanged after analyze

## PONI warning

If the real calibration dataset format is not supported by `perform_azimuthal_integration` (which expects PONI text or dataframe calibration), the integration wrapper must fail safely with `preprocessing_failed` and a safe detail. Do not implement dataframe calibration speculatively. The structural fixes in this PR (calibration subtree discovery, organSide, P-token pairing) must be verified independently of integration.

## Non-goals

- No new layouts
- No architecture changes beyond defect fixes
- No physical H5 repacking
- No derived cache
- No new dependencies
- No frontend changes
- No docs/ROADMAP changes

## Validation

```bash
git rev-parse --verify HEAD
git branch --show-current
git status --short
git diff --name-only
git diff --stat

python -m compileall src tests

python -m pytest -q tests/test_bremen_h5_layouts.py
python -m pytest -q tests/test_bremen_api_server.py
python -m pytest -q
python -m bremen --help
python -m bremen serve --help
python -m bremen demo-smoke --help
python -m bremen demo-run --help
```

### Semantic grep checks

```bash
# _validate_ref called before auto-detection in session adapter
grep -n "_validate_ref" src/bremen/api/h5_layouts.py
# Expected: after auto-detection branch, not before

# organSide support
grep -n "organSide\|organ_side" src/bremen/api/h5_layouts.py
# Expected: in SIDE_ATTR_KEYS tuple

# Calibration exclusion from measurements
grep -n "calib_subtree\|calib_root\|_exclude" src/bremen/api/h5_layouts.py
# Expected: calibration datasets excluded from measurement list

# Pair-key extraction uses explicit position tokens
grep -n "pair_key\|_extract_position\|P1\|re.search" src/bremen/api/h5_layouts.py
# Expected: no full-filename fallback

# Typed stage exceptions
grep -n "H5ContainerError\|H5MetadataError\|PreprocessingBridgeError\|PortableLogRegModelError" src/bremen/api/server.py
# Expected: typed except clauses, not substring matching

# str(exc) in API detail — should be replaced by safe mapping
grep -n "str(exc)\[:" src/bremen/api/server.py
# Expected: replaced with _safe_error_detail()

# H5 paths in API details
grep -n "dataset_path\|group_path\|measurement.*path\|\.h5\b" src/bremen/api/server.py
# Expected: no internal paths in API error details

# First-two pairing — should not exist
grep -n "measurements\[0\]\|measurements\[1\]" src/bremen/api/h5_layouts.py
# Expected: no first-two pairing

# Future-work deferral
grep -n "TODO\|FIXME\|future\|deferred" src/bremen/api/ src/bremen/demo_*.py || true
# Expected: no new deferrals that leave a broken path

git diff --name-only -- .github infra/terraform Dockerfile Dockerfile.training \
  requirements.txt pyproject.toml config/training frontend web ui \
  package.json package-lock.json yarn.lock pnpm-lock.yaml tests/data docs ROADMAP.md
# Expected: no output

git diff --name-only | grep -E "\.(h5|hdf5|joblib|pkl|npy|npz|tfstate|tfstate\.backup)$" || true
# Expected: no output

find . -name ".DS_Store" -print
```

## Files changed

Expected: `src/bremen/api/h5_layouts.py`, `src/bremen/api/server.py`, `tests/test_bremen_h5_layouts.py`, `tests/test_bremen_api_server.py`. (4 files)

## Implementation scope

| File | Change |
|------|--------|
| `src/bremen/api/h5_layouts.py` | Fix session no-ref detection, calibration exclusion, organSide, P-token pairing |
| `src/bremen/api/server.py` | Fix typed stage classification, safe error details |
| `tests/test_bremen_h5_layouts.py` | Real-like Matador fixture tests, session no-ref test, calibration exclusion test |
| `tests/test_bremen_api_server.py` | Route-level session success, Matador success, all failure tests |

## Boundary confirmations

- one corrective rehearsal PR: yes
- no-ref session path fixed: yes
- exactly-one-ref rejected: yes
- calibration datasets excluded from measurements: yes
- organSide supported: yes
- evidence-based P1/P2/P3 pairing: yes
- no full-filename pair keys: yes
- no first-two pairing: yes
- typed stage classification: yes
- no substring-based stage inference: yes (typed exceptions as primary)
- public errors sanitized: yes
- no internal paths or identifiers exposed: yes
- real-like route fixtures required: yes
- PONI limitation retained honestly: yes
- no speculative dataframe calibration: yes
- source H5 immutable: yes
- no committed H5/model/data artifacts: yes
- no physical repacking/cache: yes
- native/session/Matador regressions required: yes
- implementation assigned to coder: yes
- no git mutation commands run: yes
