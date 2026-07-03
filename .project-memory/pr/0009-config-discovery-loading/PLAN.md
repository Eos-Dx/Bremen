# PR 0009 — Repair PLAN for Minimal Config Discovery and Loading

Author: plan
Mode: planning repair only
Branch: 0009-config-discovery-loading

## Objective

Add a minimal Bremen config discovery/loading module that future workflow commands can use. This PR adds only the config module and its direct tests. No CLI changes, no README changes, no presentation layer.

## Context

PR 0008 added the unified Bremen CLI entrypoint. The next step is a standalone config discovery/loading module that future PRs (CLI subcommand, preflight gates, workflow) will depend on.

- `pyyaml` is already a project dependency.
- `tomllib` is in Python 3.11+ standard library (Bremen requires 3.13, available with no extra dependency).
- No config module exists today.
- No config discovery (env var, default file names, deterministic lookup) exists today.

PR 0009 adds only the module and its tests. CLI presentation, README updates, and `__main__.py` changes are deferred to follow-up PRs.

## Track classification

This is **product/config foundation** work. It establishes the config layer only — no CLI, no presentation, no workflow.

## Current baseline

- `src/bremen/__main__.py` has `preprocess` command (lazy import), stubs (`preflight`, `run`, `report`), and no config subcommand.
- No config module exists.
- No config discovery exists.
- `pyyaml` is in project dependencies.
- `tomllib` is available in stdlib.

## Allowed implementation files

Exactly these files may be created:

1. **`src/bremen/config.py`** — NEW. Config discovery and loading module. Import-safe, no heavy side effects.
2. **`tests/test_bremen_config_loading.py`** — NEW. Direct config discovery/loading tests.

## Forbidden files

- `README.md` — no documentation changes
- `src/bremen/__main__.py` — no CLI changes
- `src/bremen/cli.py` — no CLI module changes
- `tests/test_bremen_cli_entrypoint.py` — no CLI test changes
- `pyproject.toml` — no dependency changes (pyyaml already present, tomllib is stdlib)
- `.github/**`, `Dockerfile`, `.dockerignore`, `sonar-project.properties` — no infrastructure changes
- `AGENTS.md`, `docs/**` — no documentation changes
- `config/**`, `examples/**`, `environment.yml`, `Makefile` — no config/example/infrastructure changes
- `tests/data/**` — no test data changes
- Any H5/HDF5 files — no data changes
- Any model/joblib/pkl/npy/npz artifacts — no artifact changes

## Non-goals

This PR does not:
- Add CLI command surface (`config show`, `config list-paths`, or any `python -m bremen config ...`)
- Modify `src/bremen/__main__.py` or `tests/test_bremen_cli_entrypoint.py`
- Modify README.md
- Implement H5 metadata validation (deferred)
- Implement target/control consistency validation (deferred)
- Implement config schema validation beyond safe parse/load errors (deferred)
- Implement model/joblib loading
- Implement training or inference
- Implement Matador integration
- Implement API server
- Implement clinical workflow behavior
- Read H5/HDF5 data referenced by config
- Load or check model paths by loading artifacts
- Contact external services
- Add Docker, CI, GHCR, or SonarCloud changes
- Change existing config files or preprocessing config behavior
- Change any existing source or test files

## Proposed config discovery design

### Module: `src/bremen/config.py`

Import-safe module. Importing `config` must not:
- Import `pipelines`, `modeling`, `mlflow_tracking`, `xrd_preprocessing`, or `container`
- Read H5/HDF5 files
- Load joblib/model artifacts
- Contact external services
- Require secrets or credentials

### Discovery order (deterministic)

1. **Explicit path** — If the caller passes a `Path`, use it directly.
2. **`BREMEN_CONFIG` environment variable** — If set, use as the config path. Must be a valid filesystem path. If empty or whitespace-only, treat as not set.
3. **`cwd/bremen.yml`** — YAML with `.yml` extension in current working directory.
4. **`cwd/bremen.yaml`** — YAML with `.yaml` extension in current working directory.
5. **`cwd/bremen.toml`** — TOML in current working directory.
6. **No config found** — Raise `ConfigNotFoundError` with a deterministic list of paths searched.

### Behavior rules

- First match wins. No merging of multiple config files.
- No recursive directory search.
- The discovery order is documented in the module docstring.

## Proposed config loading API

### Public types

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ConfigLoadResult:
    """Represents a loaded config file with its metadata."""
    path: Path                    # Resolved absolute path to the config file
    source: str                   # 'explicit' | 'env' | 'discovery'
    data: dict[str, Any]          # Parsed content (dict with string keys)
    warnings: tuple[str, ...] = field(default_factory=tuple)


class ConfigError(Exception):
    """Base exception for config errors."""


class ConfigNotFoundError(ConfigError):
    """No config file found at the specified or discovered paths."""
    def __init__(self, searched: list[Path]) -> None:
        self.searched = searched
        super().__init__(f"No config found. Searched: {searched}")


class ConfigSyntaxError(ConfigError):
    """Config file exists but cannot be parsed."""
    def __init__(self, path: Path, detail: str) -> None:
        self.path = path
        super().__init__(f"Cannot parse {path}: {detail}")
```

### Public functions

```python
def discover_config(
    explicit_path: str | Path | None = None,
    env_var: str | None = "BREMEN_CONFIG",
    cwd: Path | None = None,
) -> ConfigLoadResult:
    """Discover and load a config file using deterministic lookup order.

    Parameters
    ----------
    explicit_path : If provided, use this path directly.
    env_var : Environment variable name to check. Pass None to skip.
    cwd : Working directory for default file discovery. Defaults to Path.cwd().

    Returns a ConfigLoadResult.
    Raises ConfigNotFoundError if no config is found.
    Raises ConfigSyntaxError if a config file exists but is invalid.
    """


def load_config(path: str | Path) -> ConfigLoadResult:
    """Load a config file from an explicit path.

    Supports .yml, .yaml, .toml extensions.
    Raises ConfigNotFoundError if the path does not exist.
    Raises ConfigSyntaxError if the file cannot be parsed.
    """
```

### Format support

| Format | Library | Dependency | Notes |
|--------|---------|------------|-------|
| `.yml` / `.yaml` | `yaml` (PyYAML) | Already in pyproject.toml | `safe_load` only |
| `.toml` | `tomllib` | Standard library (Python 3.11+) | `tomllib.load` / `tomllib.loads` |

- `PyYAML.safe_load` only — no `FullLoader` or arbitrary object loading.
- `tomllib` is always available (Python 3.13 requirement).
- No new dependencies.

### Behavior for edge cases

| Condition | Behavior |
|-----------|----------|
| File does not exist | `ConfigNotFoundError` with paths searched |
| File exists but empty | `ConfigLoadResult` with empty `data` dict and a warning |
| Invalid YAML syntax | `ConfigSyntaxError` with parser detail |
| Invalid TOML syntax | `ConfigSyntaxError` with parser detail |
| File is a directory | `ConfigSyntaxError` with "is a directory" message |
| BOM or encoding issues | `ConfigSyntaxError` with encoding detail |
| `BREMEN_CONFIG` env var is set but empty/whitespace | Treated as not set (skip to next discovery step) |
| `BREMEN_CONFIG` env var points to a non-existent path | `ConfigNotFoundError` (path was explicit via env; must exist) |

### Safety boundaries

- Does not read H5/HDF5 data referenced by config.
- Does not check model paths by loading artifacts.
- Does not contact external services.
- Does not require secrets or credentials.
- Does not import heavy modules at import time.
- Does not execute arbitrary Python code from config files.
- Does not resolve config references or `!include` directives.

## Testing strategy

### New test file: `tests/test_bremen_config_loading.py`

Cover these scenarios:

1. **Explicit path wins** — Create a temp YAML file, load via `load_config()`, verify `ConfigLoadResult.path`, `data`, `source == "explicit"`.
2. **Explicit path TOML** — Same with TOML content.
3. **`BREMEN_CONFIG` env var** — Set env var, call `discover_config()`, verify it uses the env path, `source == "env"`.
4. **Default discovery order** — Create `bremen.yml` in a temp directory, call `discover_config()`, verify it finds the file, `source == "discovery"`.
5. **Discovery order precedence** — Create `bremen.yml` and `bremen.yaml` in the same directory, verify `.yml` wins (first match).
6. **No config found** — Call `discover_config()` in an empty temp directory with no env var, verify `ConfigNotFoundError` is raised.
7. **Missing explicit file** — Call `load_config()` with a non-existent path, verify `ConfigNotFoundError`.
8. **Invalid TOML syntax** — Create a file with bad TOML, verify `ConfigSyntaxError`.
9. **Invalid YAML syntax** — Create a file with bad YAML, verify `ConfigSyntaxError`.
10. **Empty config file** — Create an empty `.toml` file, verify `ConfigLoadResult` with empty `data` and a warning.
11. **Import safety** — Verify that importing `bremen.config` does not import `xrd_preprocessing`, `container`, `pipelines`, `modeling`, or `mlflow_tracking` at top level. Use AST inspection of the module source.
12. **No H5 read** — Verify `discover_config()` and `load_config()` do not attempt to open H5 files or load model artifacts (the functions parse text-only config files and do not follow references).
13. **No Aramis identity** — Verify that user-facing error messages and the module docstring do not contain "Aramis" or "aramis".

### What tests must NOT do

- Read H5/HDF5 files.
- Load joblib/model artifacts.
- Connect to external services.
- Require private dependencies (`xrd_preprocessing`, `container`).
- Modify any repository files (use `tmp_path` fixtures).
- Test CLI behavior (no subprocess calls to `python -m bremen`).

### Existing tests must still pass

All existing tests must pass without modification:
- `test_bremen_import_identity.py`
- `test_bremen_cli_entrypoint.py`
- Preprocessing, modeling, MLflow tests.

## Validation checklist

Precommit-review must execute these checks and report pass/fail for each.

### Static and security checks

```bash
# 1) Working tree state
git status --short

# 2) Changed files — only allowed files
git diff --name-only

# 3) No H5/HDF5 changes
git diff --name-only | grep -E "\.h5$|\.hdf5$" && exit 1 || echo "OK"

# 4) No tests/data changes
git diff --name-only -- tests/data

# 5) No model/joblib artifact changes
git diff --name-only | grep -E "\.joblib$|\.pkl$|\.npy$|\.npz$" && exit 1 || echo "OK"

# 6) No CI/Docker/GHCR/deployment changes
git diff --name-only | grep -E "\.github/|Dockerfile|\.dockerignore|sonar-project\.properties" && \
  echo "ERROR: CI/Docker changes detected" || echo "No CI/Docker changes"

# 7) No forbidden file changes (README, __main__, CLI test, pyproject, config, examples, docs, etc.)
git diff --name-only | grep -E "README\.md|src/bremen/__main__\.py|src/bremen/cli\.py|tests/test_bremen_cli_entrypoint\.py|pyproject\.toml|\.github/|Dockerfile|\.dockerignore|sonar-project\.properties|AGENTS\.md|docs/|config/|examples/|environment\.yml|Makefile|tests/data/" && \
  echo "ERROR: Forbidden file changed" || echo "No forbidden file changes"
```

### Python and import checks

```bash
# 8) Compile check
python -m compileall src tests

# 9) Config module import safety — no heavy imports at top level
python -c "
import ast, sys
from pathlib import Path

config_path = Path('src/bremen/config.py')
tree = ast.parse(config_path.read_text(encoding='utf-8'))

heavy_modules = ['xrd_preprocessing', 'container', 'pipelines', 'modeling', 'mlflow_tracking',
                 'bremen.pipelines', 'bremen.modeling', 'bremen.mlflow_tracking']

for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom):
        module = node.module or ''
        for mod in heavy_modules:
            if mod in module:
                print(f'ERROR: config.py imports {mod} at top level')
                sys.exit(1)
    elif isinstance(node, ast.Import):
        for alias in node.names:
            for mod in heavy_modules:
                if mod in alias.name:
                    print(f'ERROR: config.py imports {mod} at top level')
                    sys.exit(1)
print('config.py import-safe')
"

# 10) Import config module successfully (no side effects)
python -c "from bremen.config import discover_config, load_config, ConfigLoadResult, ConfigNotFoundError, ConfigSyntaxError; print('Import OK')"
```

### Config module behavior checks

```bash
# 11) discover_config with explicit path (YAML) works
python -c "
import tempfile, os
from bremen.config import discover_config, ConfigLoadResult, ConfigNotFoundError

with tempfile.TemporaryDirectory() as tmpdir:
    path = os.path.join(tmpdir, 'test.yml')
    with open(path, 'w') as f:
        f.write('key1: value1\n')
    result = discover_config(explicit_path=path)
    assert result.source == 'explicit'
    assert result.data == {'key1': 'value1'}
print('discover_config explicit YAML OK')
"

# 12) discover_config with explicit path (TOML) works
python -c "
import tempfile, os
from bremen.config import discover_config

with tempfile.TemporaryDirectory() as tmpdir:
    path = os.path.join(tmpdir, 'test.toml')
    with open(path, 'w') as f:
        f.write('key1 = \"value1\"\n')
    result = discover_config(explicit_path=path)
    assert result.data == {'key1': 'value1'}
print('discover_config explicit TOML OK')
"

# 13) BREMEN_CONFIG env var is respected
python -c "
import tempfile, os
from bremen.config import discover_config

with tempfile.TemporaryDirectory() as tmpdir:
    path = os.path.join(tmpdir, 'env_config.yml')
    with open(path, 'w') as f:
        f.write('from_env: true\n')
    os.environ['BREMEN_CONFIG'] = path
    try:
        result = discover_config()
        assert result.source == 'env'
        assert result.data == {'from_env': True}
    finally:
        del os.environ['BREMEN_CONFIG']
print('BREMEN_CONFIG env var OK')
"

# 14) No config found raises ConfigNotFoundError
python -c "
import tempfile, os
from bremen.config import discover_config, ConfigNotFoundError

with tempfile.TemporaryDirectory() as tmpdir:
    try:
        discover_config(cwd=tmpdir)
        assert False, 'Expected ConfigNotFoundError'
    except ConfigNotFoundError:
        pass
print('No config found raises error OK')
"

# 15) Missing explicit file raises ConfigNotFoundError
python -c "
import tempfile, os
from bremen.config import load_config, ConfigNotFoundError

with tempfile.TemporaryDirectory() as tmpdir:
    try:
        load_config(os.path.join(tmpdir, 'nonexistent.yml'))
        assert False, 'Expected ConfigNotFoundError'
    except ConfigNotFoundError:
        pass
print('Missing explicit file raises error OK')
"

# 16) Invalid TOML raises ConfigSyntaxError
python -c "
import tempfile, os
from bremen.config import load_config, ConfigSyntaxError

with tempfile.TemporaryDirectory() as tmpdir:
    path = os.path.join(tmpdir, 'bad.toml')
    with open(path, 'w') as f:
        f.write('key1 = \n')
    try:
        load_config(path)
        assert False, 'Expected ConfigSyntaxError'
    except ConfigSyntaxError:
        pass
print('Invalid TOML raises error OK')
"

# 17) Invalid YAML raises ConfigSyntaxError
python -c "
import tempfile, os
from bremen.config import load_config, ConfigSyntaxError

with tempfile.TemporaryDirectory() as tmpdir:
    path = os.path.join(tmpdir, 'bad.yml')
    with open(path, 'w') as f:
        f.write(': broken yaml\n')
    try:
        load_config(path)
        assert False, 'Expected ConfigSyntaxError'
    except ConfigSyntaxError:
        pass
print('Invalid YAML raises error OK')
"

# 18) Empty config file returns empty data with warning
python -c "
import tempfile, os
from bremen.config import load_config

with tempfile.TemporaryDirectory() as tmpdir:
    path = os.path.join(tmpdir, 'empty.toml')
    with open(path, 'w') as f:
        f.write('')
    result = load_config(path)
    assert result.data == {}
    assert len(result.warnings) > 0
print('Empty config returns empty data with warning OK')
"
```

### Test and coverage checks

```bash
# 19) Existing identity test still passes
python -m pytest -q tests/test_bremen_import_identity.py

# 20) New config loading tests pass
python -m pytest -q tests/test_bremen_config_loading.py

# 21) Full test suite passes
python -m pytest -q
```

### Identity and safety checks

```bash
# 22) No BREMEN_CONFIG typo in plan, source, or tests
grep -R -I -n "BREMEN.CONFIG" .project-memory/pr/0009-config-discovery-loading/PLAN.md src/bremen/config.py tests/test_bremen_config_loading.py 2>/dev/null | grep -v "BREMEN_CONFIG" && \
  echo "WARNING: Possible BREMEN_CONFIG typo found" || echo "No BREMEN_CONFIG typos"

# 23) No Aramis identity in new module or tests
grep -R -I -n -E "Aramis|aramis" src/bremen/config.py tests/test_bremen_config_loading.py 2>/dev/null && \
  echo "ERROR: Aramis identity found" || echo "No Aramis identity"

# 24) No prohibited clinical claims in new module or tests
grep -R -I -n -E "diagnos|diagnostic|clinically validated|replace MRI|replace biopsy|replace radiologist|replace clinician|autonomous clinical" src/bremen/config.py tests/test_bremen_config_loading.py 2>/dev/null && \
  echo "ERROR: Prohibited clinical claim found" || echo "No prohibited clinical claims"

# 25) No H5/model/Matador references in new module
grep -R -I -n -E "h5py|\.h5|\.hdf5|joblib|pickle|Matador|matador|predict|fit\(|train|load_model" src/bremen/config.py tests/test_bremen_config_loading.py 2>/dev/null && \
  echo "WARNING: Possible H5/model/Matador reference" || echo "No H5/model/Matador references"

# 26) Forbidden files not changed
git diff --name-only -- README.md src/bremen/__main__.py src/bremen/cli.py tests/test_bremen_cli_entrypoint.py pyproject.toml .github Dockerfile .dockerignore sonar-project.properties AGENTS.md docs config examples environment.yml Makefile tests/data | head -1 | xargs test -z && \
  echo "No forbidden files changed" || echo "WARNING: Forbidden file may be changed"
```

### Coverage check

```bash
# 27) Coverage stays above 80
python -m pytest \
  --cov=bremen \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml \
  --cov-fail-under=80 \
  -q
```

## Rollback plan

If the config module causes issues:

1. **Revert `src/bremen/config.py`** — delete the file.
2. **Revert `tests/test_bremen_config_loading.py`** — delete the file.

No other files are affected. CLI, README, and existing source/tests remain unchanged.

## Follow-up PRs

After PR 0009, the planned sequence continues:

| PR | Track | Description |
|----|-------|-------------|
| Later | Product/Config | Config CLI surface (`bremen config show`, `bremen config list-paths`) using the module from PR 0009 |
| Later | Product/Runtime | Safety preflight gates — `bremen preflight` becomes real (PR 0010) |
| Later | Product/Runtime | Matador boundary — platform integration contract (PR 0011) |
| Later | Product/Runtime | Workflow wrapper / decision-support output (PR 0012) |
| Later | Product/Runtime + Infra | Config validation (schema contract, strict errors) |

## Plan Drift Gate

Precommit-review must check each of these drift categories. Any drift blocks merge until resolved.

| Drift category | Check |
|----------------|-------|
| **File drift** | Only `src/bremen/config.py` and `tests/test_bremen_config_loading.py` changed. |
| **Config module drift** | `config.py` is import-safe (no heavy imports at top level). Supports YAML (safe_load) and TOML (tomllib). No H5 read, no model load, no external services. |
| **Discovery order drift** | Deterministic: explicit → BREMEN_CONFIG → bremen.yml → bremen.yaml → bremen.toml → ConfigNotFoundError. First match wins. No recursive search. |
| **Config loading drift** | Returns `ConfigLoadResult` with path, source, data, warnings. Raises `ConfigNotFoundError` or `ConfigSyntaxError`. |
| **No CLI drift** | No changes to `__main__.py`, `cli.py`, or `test_bremen_cli_entrypoint.py`. No `config show` or `config list-paths`. No `python -m bremen config ...`. |
| **No README drift** | No changes to README.md. |
| **Import safety drift** | No heavy imports in config.py at top level. No import-time side effects. |
| **Identity drift** | No Aramis identity. No clinical/diagnostic claims. No `BREMEN_CONFIG` spelling errors in config module. |
| **Runtime drift** | No changes to pipelines.py, modeling.py, mlflow_tracking.py, __init__.py. No preprocessing/modeling/inference changes. |
| **Infrastructure drift** | No CI/Docker/GHCR/SonarCloud changes. No pyproject.toml/environment/Makefile changes. |
| **Test drift** | New `test_bremen_config_loading.py` covers all scenarios. Existing tests pass unchanged. No test data changes. |
| **Coverage drift** | Coverage stays above 80%. |
| **Validation drift** | All 27 validation checks pass. No CLI-specific checks in the list. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Any file outside `src/bremen/config.py`, `tests/test_bremen_config_loading.py`, or PR artifacts is created or modified.
- `config.py` has top-level imports of `xrd_preprocessing`, `container`, `pipelines`, `modeling`, `mlflow_tracking`.
- `config.py` reads H5/HDF5 files, loads model artifacts, or contacts external services.
- `README.md`, `__main__.py`, `cli.py`, or `test_bremen_cli_entrypoint.py` is modified.
- `pyproject.toml`, `environment.yml`, `Makefile`, or any infrastructure file is modified.
- `BREMEN_CONFIG` appears incorrectly (typo of `BREMEN_CONFIG`) anywhere in PLAN.md, source, or tests.
- Aramis identity appears in new source or test files.
- Clinical/diagnostic claims appear in new user-facing text.
- H5/HDF5 files or model/joblib artifacts are changed.
- Existing tests break (identity test, CLI entrypoint tests, preprocessing/modeling tests).

## Decisions summary

### Allowed files
1. `src/bremen/config.py` — NEW (config discovery + loading module)
2. `tests/test_bremen_config_loading.py` — NEW (config discovery/loading tests)

### Forbidden files
- `README.md`, `src/bremen/__main__.py`, `src/bremen/cli.py`, `tests/test_bremen_cli_entrypoint.py`
- `pyproject.toml`, `.github/**`, `Dockerfile`, `.dockerignore`, `sonar-project.properties`
- `AGENTS.md`, `docs/**`, `config/**`, `examples/**`
- `environment.yml`, `Makefile`, `tests/data/**`
- Any H5/HDF5 files, any model/joblib/pkl/npy/npz artifacts

### Current baseline
- No config module exists. No config discovery exists. `__main__.py` unchanged.

### Config discovery design
- Order: explicit → `BREMEN_CONFIG` env → `bremen.yml` → `bremen.yaml` → `bremen.toml` → `ConfigNotFoundError`.
- Deterministic, first-match-wins, no recursion, no merging. `BREMEN_CONFIG` used consistently.

### Config loading API
- `discover_config(explicit_path=None, env_var="BREMEN_CONFIG", cwd=None)` → `ConfigLoadResult`
- `load_config(path)` → `ConfigLoadResult`
- Supports `.yml`, `.yaml` (PyYAML safe_load), `.toml` (tomllib).
- Raises `ConfigNotFoundError` or `ConfigSyntaxError`.
- Import-safe, no side effects, no H5/model/Matador/secrets.

### Safety boundaries
- No H5 read, no model load, no external services, no secrets, no clinical claims.
- Import-safe, no heavy imports at module level.
- No changes to existing source, tests, or infrastructure files.

### Testing strategy
- New test file (13 tests): explicit path YAML/TOML, BREMEN_CONFIG env, default discovery, missing config, invalid syntax (YAML + TOML), empty config, import safety, no H5/model reads, no Aramis identity.

### Validation checklist
27 checks: static (file state, H5, data, model, CI/Docker, forbidden files), Python (compileall, import safety), config module behavior (8 behavioral tests), test (identity, new tests, full suite), identity/safety (BREMEN_CONFIG typo check, Aramis, clinical claims, H5/model/Matador, forbidden files), coverage (80%).

### Stop conditions
10 block conditions.

### Rollback plan
Limited to `src/bremen/config.py` (delete) and `tests/test_bremen_config_loading.py` (delete).

### Follow-up PRs
- Config CLI surface is deferred to a later PR.
- PR 0010: Safety preflight gates.
- PR 0011: Matador boundary.
- PR 0012: Workflow wrapper / decision-support output.

## Exact human commit instructions for planning artifacts

This PLAN.md is a planning artifact only. No implementation files have been created or modified. This is a repair of the previous blocked PLAN.md.

1. Planner writes this file: `.project-memory/pr/0009-config-discovery-loading/PLAN.md`
2. Human runs: `git add .project-memory/pr/0009-config-discovery-loading/PLAN.md`
3. Human runs: `git commit -m "PR 0009 — Repair plan for minimal config discovery and loading"`
4. Human pushes the branch for plan-review.
5. After plan-review approves, the coder implements the allowed files listed above.

## Files read

- `.project-memory/pr/0009-config-discovery-loading/PLAN.md` (previous version, to repair)
- `.project-memory/pr/0009-config-discovery-loading/reviews/plan-review.yml` (blocked review feedback)
- `src/bremen/__main__.py`
- `tests/test_bremen_cli_entrypoint.py`
- `tests/test_bremen_import_identity.py`
- `pyproject.toml`
- `docs/roadmap.md`

## Files written

- `.project-memory/pr/0009-config-discovery-loading/PLAN.md` (this repaired file)

## Files intentionally ignored

- All infrastructure files (Dockerfile, .dockerignore, quality.yml, sonar-project.properties)
- All source files not named `config.py`
- All test files not named `test_bremen_config_loading.py`
- `README.md`, `AGENTS.md`, `docs/**`, `.project-memory/memory_index.yml`
- `environment.yml`, `Makefile`, `requirements.txt`, `.gitignore`
- Any H5/HDF5 or binary/model artifacts

## Boundary confirmations

- confirm: no CLI changes planned: yes
- confirm: no README changes planned: yes
- confirm: no `src/bremen/__main__.py` changes planned: yes
- confirm: no `tests/test_bremen_cli_entrypoint.py` changes planned: yes
- confirm: `BREMEN_CONFIG` used consistently: yes
- confirm: no `BREMEN_CONFIG` typo remains in plan text: yes
- confirm: discovery/loading separated from presentation: yes
- confirm: validation narrowed to config module/tests: yes
- confirm: rollback narrowed to config module/tests: yes
- confirm: no H5/model/Matador behavior planned: yes
- confirm: no implementation files modified: yes
- confirm: no git mutation commands run: yes
- confirm: allowed files are exactly `src/bremen/config.py` and `tests/test_bremen_config_loading.py`: yes
- confirm: all CLI references, `config show`, `config list-paths`, and argparse wiring removed: yes
- confirm: no `BREMEN_CONFIG` typo remains in plan text: yes
- confirm: module named `config.py` not `config_loader.py`: yes
- confirm: API uses `ConfigLoadResult`, `ConfigSyntaxError`: yes
