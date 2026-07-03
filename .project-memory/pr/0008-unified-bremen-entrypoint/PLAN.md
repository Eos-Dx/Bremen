# PR 0008 — Plan Unified Bremen Entrypoint

Author: plan
Mode: planning only
Branch: 0008-unified-bremen-entrypoint

## Objective

Introduce a unified Bremen entrypoint that establishes one clear place for future Bremen workflow commands without implementing full runtime inference, H5 validation, Matador integration, config discovery, or clinical behavior. This is the first product/runtime foundation PR after the infrastructure track (PR 0005-0007).

## Context

The infrastructure track is complete:
- PR 0005: CI/SonarCloud/Docker skeleton
- PR 0006: Coverage gate and dependency cache
- PR 0007: Docker smoke and GHCR publish

The current `__main__.py` already exists but has problems:
- `from .pipelines import run_preprocessing_from_config` is a top-level import, meaning `python -m bremen --help` imports `xrd_preprocessing` and all its transitive dependencies as a side effect.
- The parser requires a subcommand (`required=True`), so `python -m bremen` with no arguments errors instead of showing help.
- Only one command (`preprocess`) is exposed. No stubs for future workflow stages.
- The preprocess command immediately executes a real workflow — there is no safe "check the setup" or "show available stages" command.

PR 0008 fixes these issues by restructuring the entrypoint to be safe, explicit about deferred commands, and free of import-time side effects.

## Track classification

This PR is **product/runtime foundation** work. It is the first PR after the infrastructure track that touches source code and defines the user-facing command surface.

It is not a full product feature PR — no real clinical workflow, no inference, no H5 validation, no Matador integration. It establishes the command structure for future PRs to build on.

## Current baseline

### Current `src/bremen/__main__.py`

```python
"""Command-line entrypoint for Bremen product workflows."""
from __future__ import annotations
import argparse
from pathlib import Path
from .pipelines import run_preprocessing_from_config  # heavy import at module level

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bremen")
    subparsers = parser.add_subparsers(dest="command", required=True)
    preprocess = subparsers.add_parser("preprocess", help="...")
    preprocess.add_argument("--config", required=True, type=Path, help="...")
    args = parser.parse_args(argv)
    if args.command == "preprocess":
        df = run_preprocessing_from_config(args.config)
        print(...)
        return 0
    raise ValueError(f"Unknown command: {args.command}")
```

### Current behavior

| Command | Behavior | Problem |
|---------|----------|---------|
| `python -m bremen --help` | Shows help but imports xrd_preprocessing at module level | Side-effect import; slow; risks errors if private dep unavailable |
| `python -m bremen preprocess --help` | Same side-effect import | Same |
| `python -m bremen` | Errors: "argument command is required" | No helpful output; no indication of available commands |
| `python -m bremen preprocess --config ...` | Runs real preprocessing pipeline | Acceptable for existing behavior, but the import should be lazy |

### Current pyproject.toml entrypoint

`[project.scripts] bremen = "bremen.__main__:main"` — already configured.

The `bremen` console script already works.

## Proposed entrypoint design

### Design principles

1. **Lazy imports**: No heavy imports (`pipelines`, `xrd_preprocessing`, `container`, `mlflow`, `modeling`) at module level. Import only inside the command handler that needs them.
2. **Safe defaults**: `python -m bremen` with no arguments shows help and exits 0.
3. **Explicit stubs**: Future workflow commands (`preflight`, `run`, `report`) appear in help output with clear "not yet implemented" messages.
4. **Predictable exit codes**:
   - `--help`: exit 0
   - known stub command help: exit 0
   - unimplemented workflow action: exit 1 with clear message
5. **No clinical claims**: Help text must state Bremen is a decision-support workflow foundation, not a diagnostic replacement.
6. **No import-time side effects**: No model loading, H5 reading, service connection, or config parsing at import time.

### Command surface

#### `python -m bremen [--help]`

Shows top-level help with available commands. No heavy imports. Exits 0.

Help text must include the Bremen identity statement:
> "Bremen — XRD-based ML decision-support workflow foundation. Not a diagnostic replacement."

#### `python -m bremen preflight [--help]`

Placeholder for future safety preflight checks. Help text states "Not yet implemented. Planned for a future PR." Exits 0 for `--help`, exits 1 if invoked directly.

#### `python -m bremen run [--help]`

Placeholder for future inference/analysis run. Help text states "Not yet implemented. Planned for a future PR." Exits 0 for `--help`, exits 1 if invoked directly.

#### `python -m bremen report [--help]`

Placeholder for future decision-support report generation. Help text states "Not yet implemented. Planned for a future PR." Exits 0 for `--help`, exits 1 if invoked directly.

#### `python -m bremen preprocess --config PATH`

Existing preprocessing command, preserved. Heavy imports (`run_preprocessing_from_config`) happen only inside the handler, not at module level.

### Implementation sketch

```python
"""Unified command-line entrypoint for Bremen — XRD-based ML decision-support workflow foundation.

Not a diagnostic replacement.
"""

from __future__ import annotations

import argparse
import sys


def _add_preprocess_subcommand(subparsers: argparse._SubParsersAction) -> None:
    """Add the 'preprocess' subcommand (imports heavy dependencies lazily)."""
    from pathlib import Path

    preprocess = subparsers.add_parser(
        "preprocess",
        help="Build a Bremen preprocessing DataFrame from a YAML config.",
    )
    preprocess.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to Bremen preprocessing YAML.",
    )
    preprocess.set_defaults(_cmd_handler="preprocess")


def _add_stub_command(
    subparsers: argparse._SubParsersAction,
    name: str,
    help_text: str,
    deferral_note: str,
) -> None:
    """Add a stub subcommand that prints a deferral message."""
    cmd = subparsers.add_parser(name, help=help_text)
    cmd.set_defaults(_cmd_handler="stub", _stub_name=name, _stub_note=deferral_note)


def _handle_preprocess(args: argparse.Namespace) -> int:
    """Execute the preprocess command (lazy import)."""
    from .pipelines import run_preprocessing_from_config  # noqa: PLC0415

    df = run_preprocessing_from_config(args.config)
    print(f"rows={len(df)}")
    print(f"columns={len(df.columns)}")
    print(f"config={args.config}")
    return 0


def _handle_stub(args: argparse.Namespace) -> int:
    """Print a deferral message for stub commands."""
    print(f"'{args._stub_name}' is not yet implemented.")
    print(args._stub_note)
    return 1


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="bremen",
        description=(
            "XRD-based ML decision-support workflow foundation. "
            "Not a diagnostic replacement."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    # Real commands
    _add_preprocess_subcommand(subparsers)

    # Stub commands for future workflow stages
    _add_stub_command(
        subparsers,
        "preflight",
        "Run safety preflight checks (not yet implemented).",
        "Planned for a future PR.",
    )
    _add_stub_command(
        subparsers,
        "run",
        "Run Bremen analysis workflow (not yet implemented).",
        "Planned for a future PR.",
    )
    _add_stub_command(
        subparsers,
        "report",
        "Generate decision-support report (not yet implemented).",
        "Planned for a future PR.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    handler = getattr(args, "_cmd_handler", None)
    if handler == "preprocess":
        return _handle_preprocess(args)
    if handler == "stub":
        return _handle_stub(args)

    # Fallback (should not be reached with current commands)
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### Key design decisions

1. **`subparsers` is NOT `required=True`** — `python -m bremen` with no args shows help (exit 0).
2. **Heavy imports are inside `_handle_preprocess`** — `--help` and stub commands do not import `pipelines` or `xrd_preprocessing`.
3. **Stub commands use `argparse.Namespace` attributes** (`_cmd_handler`, `_stub_name`, `_stub_note`) to dispatch without heavy machinery.
4. **No config files are read** at import or help time.
5. **No H5 files, model artifacts, or external services** are accessed.
6. **The `preprocess` command requires `--config`** — unchanged from current behavior.

## Allowed implementation files

The coder may create or modify exactly these files:

1. **`src/bremen/__main__.py`** — MODIFY. Restructure as described above.
2. **`src/bremen/cli.py`** — NEW (optional). If the entrypoint logic grows large enough to warrant a separate module. This file contains parser builders and stub handlers. `__main__.py` imports from `cli.py` for the main function.
3. **`tests/test_bremen_cli_entrypoint.py`** — NEW. Tests for the unified entrypoint behavior.
4. **`pyproject.toml`** — MODIFY only if the console script entrypoint changes (unlikely — already `bremen = "bremen.__main__:main"`).
5. **`README.md`** — MODIFY only if minimal usage documentation is needed (e.g., updating the `python -m bremen` example or adding the stub commands section).

Prefer the simplest approach. If `__main__.py` alone is sufficient without a separate `cli.py`, do not create `cli.py`.

## Forbidden files

- `Dockerfile`, `.dockerignore` — no Docker changes
- `.github/workflows/quality.yml` — no CI changes
- `sonar-project.properties` — no SonarCloud changes
- `src/bremen/pipelines.py` — no preprocessing changes
- `src/bremen/modeling.py` — no modeling changes
- `src/bremen/mlflow_tracking.py` — no MLflow changes
- `src/bremen/__init__.py` — no package API changes
- `tests/test_bremen_import_identity.py` — no changes to existing identity test
- `tests/data/` — no test data changes
- `config/**` — no config changes
- `examples/**` — no example changes
- `AGENTS.md`, `docs/**`, `.project-memory/memory_index.yml` — no documentation changes
- `environment.yml`, `Makefile`, `requirements.txt`, `.gitignore` — no infrastructure changes
- Any H5/HDF5 files — no data changes
- Any binary/model artifacts — no artifact changes

## Non-goals

This PR does not:
- Implement real model inference
- Implement training logic
- Read or validate H5/HDF5 files
- Implement Matador integration
- Implement config discovery or config loading
- Implement config validation
- Implement safety preflight checks (stub only)
- Implement run workflow (stub only)
- Implement report generation (stub only)
- Start an API server
- Change Docker, CI, GHCR, or SonarCloud configuration
- Change preprocessing behavior, modeling behavior, or pipeline behavior
- Change test data or create real data fixtures
- Change the existing `test_bremen_import_identity.py` test
- Change AGENTS.md, docs, or project-memory planning surfaces
- Make clinical claims or diagnostic assertions

## Safety boundaries

This PR must ensure:
- `python -m bremen --help` does not import `xrd_preprocessing`, `container`, `pipelines`, `modeling`, or `mlflow`.
- `python -m bremen` (no args) shows help and exits 0.
- No command reads H5/HDF5 files.
- No command loads joblib/model artifacts.
- No command trains or infers.
- No command depends on local data paths.
- No command requires Matador.
- No command requires secrets or credentials.
- Help text includes the Bremen identity statement and explicitly says Bremen is not a diagnostic replacement.
- Stub commands clearly state they are not yet implemented.
- The `preprocess` command remains functional with the same behavior (lazy import delayed to handler).
- Exit codes are predictable: `--help` → 0, stub help → 0, unimplemented stub invocation → 1, preprocess success → 0, preprocess failure → 1 (existing behavior).

## Testing strategy

### New test file: `tests/test_bremen_cli_entrypoint.py`

Cover these scenarios:

1. **`python -m bremen --help`** — exits 0, output contains "Bremen" and "Not a diagnostic replacement", does not import heavy modules. Verify by checking `stderr`/`stdout` or by asserting `importlib.import_module` does not trigger `xrd_preprocessing`.

2. **`python -m bremen` (no args)** — exits 0, shows help (same output as `--help`).

3. **Stub commands (`preflight`, `run`, `report`) with `--help`** — exits 0, shows help for that subcommand.

4. **Stub commands without `--help`** — exits 1, prints "not yet implemented" message.

5. **`python -m bremen preprocess --help`** — exits 0, shows preprocess help. Does not trigger heavy imports.

6. **No active Aramis identity** in help output or command names. Grep new files for `aramis` or `Aramis` — must not appear.

7. **Console script `bremen --help`** (if applicable) — same behavior as `python -m bremen --help`.

8. **Preprocess command still works** with a valid config (integration-level check, can use a minimal YAML fixture from `config/`).

### What tests must NOT do

- Read H5/HDF5 files.
- Load joblib/model artifacts.
- Connect to external services (MLflow, Matador APIs).
- Require private dependencies (`xrd_preprocessing`, `container`) unless executing the preprocess command.
- Modify test data or config files.

### Existing tests must still pass

All existing tests in `tests/` must pass without modification. The new entrypoint must not break:
- `test_bremen_import_identity.py` — filesystem inspection, no import of heavy modules.
- Preprocessing tests — use the `preprocess` command or call pipeline functions directly.
- Modeling tests — unaffected by entrypoint changes.
- MLflow tracking tests — unaffected by entrypoint changes.

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
git diff --name-only | grep -E "\.github/workflows/quality|Dockerfile|\.dockerignore|sonar-project\.properties" && \
  echo "ERROR: CI/Docker changes detected" || echo "No CI/Docker changes"
```

### Python and import checks

```bash
# 7) Compile check
python -m compileall src tests

# 8) New entrypoint help works without heavy imports
python -c "
import sys, subprocess, importlib
# Verify --help does not import xrd_preprocessing
result = subprocess.run([sys.executable, '-m', 'bremen', '--help'], capture_output=True, text=True)
assert result.returncode == 0, f'Return code: {result.returncode}'
assert 'Bremen' in result.stdout, 'Missing Bremen in help'
assert 'diagnostic replacement' in result.stdout, 'Missing disclaimer'
assert 'preflight' in result.stdout
assert 'run' in result.stdout
assert 'report' in result.stdout
print('--help OK')
"

# 9) No-args shows help
python -c "
import sys, subprocess
result = subprocess.run([sys.executable, '-m', 'bremen'], capture_output=True, text=True)
assert result.returncode == 0, f'Return code: {result.returncode}'
assert 'preflight' in result.stdout
print('no-args help OK')
"

# 10) Stub commands exit 1 with message
python -c "
import sys, subprocess
for cmd in ['preflight', 'run', 'report']:
    result = subprocess.run([sys.executable, '-m', 'bremen', cmd], capture_output=True, text=True)
    assert result.returncode == 1, f'{cmd}: Return code {result.returncode}'
    assert 'not yet implemented' in result.stdout or 'not yet implemented' in result.stderr, \
        f'{cmd}: missing deferral message'
print('Stub commands OK')
"

# 11) Stub commands --help exit 0
python -c "
import sys, subprocess
for cmd in ['preflight', 'run', 'report']:
    result = subprocess.run([sys.executable, '-m', 'bremen', cmd, '--help'], capture_output=True, text=True)
    assert result.returncode == 0, f'{cmd} --help: Return code {result.returncode}'
print('Stub --help OK')
"

# 12) Console script works (if console script entrypoint is configured)
python -c "
import sys, subprocess
result = subprocess.run(['bremen', '--help'], capture_output=True, text=True)
assert result.returncode == 0, f'Console script return code: {result.returncode}'
print('Console script OK')
" || echo "Console script check skipped (not on PATH in CI)"

# 13) No Aramis identity in new or modified source files
git diff --name-only | grep -E "\.py$" | xargs grep -l "aramis\|Aramis" 2>/dev/null && \
  echo "ERROR: Aramis identity found in changed files" || echo "No Aramis identity in changed files"
```

### Test checks

```bash
# 14) Existing identity test still passes
python -m pytest -q tests/test_bremen_import_identity.py

# 15) New entrypoint tests pass
python -m pytest -q tests/test_bremen_cli_entrypoint.py

# 16) Full test suite passes
python -m pytest -q
```

### Coverage check

```bash
# 17) Coverage stays above 80
python -m pytest \
  --cov=bremen \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml \
  --cov-fail-under=80 \
  -q
```

## Rollback plan

If the new entrypoint breaks existing workflows:

1. **Revert `__main__.py`** to the previous version (pre-PR-0008). The old `prog="bremen"` and `preprocess` command are preserved in the reverted version.
2. **Revert `cli.py`** (if created) — delete the file.
3. **Revert `tests/test_bremen_cli_entrypoint.py`** — delete the file.
4. **Revert `pyproject.toml`** if changed (unlikely).
5. **Revert `README.md`** if changed.
6. The `bremen --help` behavior reverts to the old behavior (side-effect import of xrd_preprocessing). This is acceptable as a rollback — it worked before.

If stub commands cause confusion:
- Remove the stub commands. Keep only the lazy import and help improvements.
- File a follow-up PR to add stubs when the team is ready.

## Follow-up PRs

After PR 0008, the planned sequence for product/runtime features:

| PR | Track | Description |
|----|-------|-------------|
| PR 0009 | Product/Runtime | Config discovery and loading — list/resolve existing config files, support named config and explicit path. No deep validation. |
| PR 0010 | Product/Runtime | Safety preflight gates — validate target/control metadata, H5 file existence, config structure integrity. Stubs from PR 0008 become real commands. |
| PR 0011 | Product/Runtime | Matador boundary — establish the platform integration contract. Bremen sends structured output to Matador. No real inference yet. |
| PR 0012 | Product/Runtime | Workflow wrapper / decision-support output — first end-to-end workflow (preprocess → QC → inference → report). Decision-support language only. |
| Later | Infrastructure | Config validation (schema contract, strict errors) — originally PR 0007 in the roadmap, now deferred to after the product/runtime foundation is stable. |

## Plan Drift Gate

Precommit-review must check each of these drift categories. Any drift blocks merge until resolved.

| Drift category | Check |
|----------------|-------|
| **File drift** | Only allowed files (__main__.py, optionally cli.py, test file, pyproject.toml if needed, README.md if needed) changed. |
| **Entrypoint drift** | `--help` does NOT import xrd_preprocessing/pipelines/modeling/mlflow. No args shows help exit 0. Stub commands exit 1 with deferral message. |
| **Help text drift** | Contains "Bremen" and "Not a diagnostic replacement." No clinical claims. |
| **Lazy import drift** | Heavy imports are inside command handlers, not at module level. |
| **Identity drift** | No Aramis identity in new or modified files. `prog="bremen"` preserved. |
| **Runtime drift** | No changes to pipelines.py, modeling.py, mlflow_tracking.py, __init__.py. No H5/model/joblib/config changes. |
| **Infrastructure drift** | No CI/Docker/GHCR/SonarCloud changes. No Dockerfile, .dockerignore, or quality.yml changes. |
| **Test drift** | New test file covers all entrypoint scenarios. Existing tests pass unchanged. No test data changes. |
| **Documentation drift** | README.md changes are minimal (usage examples only). No AGENTS.md, docs/, or memory_index.yml changes. |
| **Coverage drift** | Coverage stays above 80%. No broad exclusions added. |
| **Validation drift** | All 17 validation checks pass. |
| **Blockers** | Any blocking condition found during drift gate evaluation prevents merge. |

## Stop conditions

Block if:
- Any file outside the allowed set is created or modified.
- Heavy imports (`xrd_preprocessing`, `container`, `pipelines`, `modeling`, `mlflow`) are at the top level of `__main__.py` or `cli.py`.
- `python -m bremen --help` triggers import errors related to private dependencies.
- Help text omits the "Not a diagnostic replacement" disclaimer.
- Aramis identity appears in new or modified source files.
- Changes are made to infrastructure files (Dockerfile, .dockerignore, quality.yml, sonar-project.properties).
- Changes are made to preprocessing, modeling, or MLflow source files.
- Changes are made to `__init__.py` (package API).
- Changes are made to test data or config files.
- Existing tests break (identity test, preprocessing tests, modeling tests).
- The `preprocess` command no longer works with a valid config.
- H5/HDF5 files or model/joblib artifacts are changed.

## Decisions summary

### Allowed files
1. `src/bremen/__main__.py` — MODIFY (restructure with lazy imports, stubs, non-required subparsers)
2. `src/bremen/cli.py` — NEW (optional, if __main__.py grows large)
3. `tests/test_bremen_cli_entrypoint.py` — NEW (entrypoint behavior tests)
4. `pyproject.toml` — MODIFY only if console script entrypoint changes
5. `README.md` — MODIFY only if minimal usage documentation needed

### Forbidden files
- `Dockerfile`, `.dockerignore`, `.github/workflows/quality.yml`, `sonar-project.properties`
- `src/bremen/pipelines.py`, `modeling.py`, `mlflow_tracking.py`, `__init__.py`
- `tests/test_bremen_import_identity.py`, `tests/data/`
- `config/**`, `examples/**`
- `AGENTS.md`, `docs/**`, `.project-memory/memory_index.yml`
- `environment.yml`, `Makefile`, `requirements.txt`, `.gitignore`
- Any H5/HDF5 or binary/model artifacts

### Current baseline
- `__main__.py` has top-level import of `run_preprocessing_from_config` from `pipelines`.
- `prog="bremen"` already set.
- `subparsers` has `required=True` — no-arg invocation errors.
- `bremen` console script already configured in pyproject.toml.

### Proposed entrypoint design
- `build_parser()` returns an `ArgumentParser` with non-required subparsers.
- `--help` and no-args show help without heavy imports.
- Stub commands (`preflight`, `run`, `report`) dispatch to `_handle_stub` that prints deferral message and exits 1.
- `preprocess` command works identically, with lazy import inside `_handle_preprocess`.
- Help text includes "Not a diagnostic replacement."

### Command surface
| Command | Behavior | Exit code |
|---------|----------|-----------|
| `bremen` / `bremen --help` | Show help with commands list | 0 |
| `bremen preprocess --config PATH` | Run preprocessing (existing behavior) | 0 on success, 1 on error |
| `bremen preflight [--help]` | Show stub help or deferral message | 0 with --help, 1 without |
| `bremen run [--help]` | Show stub help or deferral message | 0 with --help, 1 without |
| `bremen report [--help]` | Show stub help or deferral message | 0 with --help, 1 without |

### Safety boundaries
- No H5 read, no model load, no training, no inference, no Matador, no secrets, no clinical claims.
- Lazy imports for heavy dependencies.
- Help text has mandatory disclaimer.

### Testing strategy
- New `tests/test_bremen_cli_entrypoint.py` with tests for: help output, no-args help, stubs, lazy imports, no Aramis identity, console script.
- Existing identity test unchanged.
- Full test suite must pass.

### Validation checklist
17 checks: static (git state, H5, data, model, CI/Docker), Python (compileall, help output, no-args, stubs, console script, Aramis grep), test (identity test, new entrypoint test, full suite), coverage (80%).

### Rollback plan
- Revert __main__.py to previous version. Delete cli.py and new test file if created.

### Follow-up PRs
- PR 0009: Config discovery/loading
- PR 0010: Safety preflight gates
- PR 0011: Matador boundary
- PR 0012: Workflow wrapper / decision-support output
- Later: Config validation (deferred from original PR 0007)

### Plan Drift Gate requirements
12 drift-check criteria: file drift, entrypoint drift, help text drift, lazy import drift, identity drift, runtime drift, infrastructure drift, test drift, documentation drift, coverage drift, validation drift, blockers.

### Stop conditions
12 block conditions covering: file scope, top-level heavy imports, help import errors, missing disclaimer, Aramis identity, infrastructure changes, source changes (pipelines/modeling/mlflow/__init__), test data/config changes, existing test breakage, preprocess command broken, H5/model artifact changes.

### Blockers
- None for writing this PLAN.md. Implementation blocked until plan-review approves.
- Implementation blocked if any of the 12 stop conditions are detected.
- Implementation blocked if the allowed-file scope is violated.

### Warnings
- The `preprocess` command still requires `xrd_preprocessing` and `container` at runtime. The lazy import only defers the import to handler execution — if those packages are not installed, the command will fail when invoked.
- Stub commands (`preflight`, `run`, `report`) create user expectations. The help and deferral messages must be clear that these are planned, not missing features.
- This is the first source-code PR after the infrastructure track. Reviewers should pay extra attention to import safety and side-effect checking.
- The existing `test_bremen_import_identity.py` checks for `'Bremen product workflows'` in the `__main__.py` docstring. If the docstring is changed, the test must still pass. Update the docstring to contain both the old reference and the new content, or verify the test assertion is adjusted.

## Exact human commit instructions for planning artifacts

This PLAN.md is a planning artifact only. No implementation files have been created or modified.

1. Planner writes this file: `.project-memory/pr/0008-unified-bremen-entrypoint/PLAN.md`
2. Human runs: `git add .project-memory/pr/0008-unified-bremen-entrypoint/PLAN.md`
3. Human runs: `git commit -m "PR 0008 — Plan unified Bremen entrypoint"`
4. Human pushes the branch for plan-review.
5. After plan-review approves, the coder implements the allowed files listed above.

## Files read

- `src/bremen/__main__.py`
- `src/bremen/__init__.py`
- `tests/test_bremen_import_identity.py`
- `pyproject.toml`
- `docs/roadmap.md`
- `docs/repository_cleanup.md`
- `.project-memory/project_contract.yml`
- `.project-memory/memory_index.yml`

## Files written

- `.project-memory/pr/0008-unified-bremen-entrypoint/PLAN.md` (this file)

## Files intentionally ignored

- All infrastructure files (Dockerfile, .dockerignore, quality.yml, sonar-project.properties)
- All source files not in the allowed list (pipelines.py, modeling.py, mlflow_tracking.py, __init__.py)
- All existing test files not in the allowed list
- All config files, example files
- `AGENTS.md`, `docs/**`, `.project-memory/memory_index.yml`
- `environment.yml`, `Makefile`, `requirements.txt`, `.gitignore`
- Any H5/HDF5 or binary/model artifacts

## Boundary confirmations

- confirm: only PLAN.md written: yes
- confirm: no implementation files written: yes
- confirm: no Docker/CI/GHCR/SonarCloud files modified: yes
- confirm: no preprocessing/modeling/mlflow source files modified: yes
- confirm: no __init__.py modified: yes
- confirm: no existing tests modified: yes
- confirm: no test data modified: yes
- confirm: no config files modified: yes
- confirm: no document files modified: yes (docs/, README, AGENTS.md)
- confirm: no H5/HDF5 files read or edited: yes
- confirm: no secrets committed: yes
- confirm: no git mutation commands run: yes
- confirm: PR classified as product/runtime foundation: yes
- confirm: `--help` does not import heavy dependencies: yes
- confirm: stub commands exit 1 with deferral message: yes
- confirm: help text includes "Not a diagnostic replacement": yes
- confirm: no Aramis identity in new or modified files: yes
- confirm: existing identity test assertion for __main__.py docstring preserved: yes
