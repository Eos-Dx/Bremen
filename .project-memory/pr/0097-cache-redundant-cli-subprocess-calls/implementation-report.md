# Implementation Report — PR0097: Cache redundant subprocess.run CLI invocations

## Summary

Added per-file module-scoped `_cli_result_cache` fixtures to three test files to cache identical `subprocess.run` CLI invocations. Files 2 and 3 verified as having no eligible redundancy and were left untouched.

## Files Changed

1. **tests/test_bremen_cli_entrypoint.py** — Added fixture, converted 16 call sites across 4 groups
2. **tests/test_bremen_demo_run.py** — Added fixture, converted 2 call sites (1 group)
3. **tests/test_bremen_demo_smoke.py** — Added fixture, converted 2 call sites (1 group)

## Files Verified (No Changes)

- **tests/test_bremen_model_v01_publication.py** — grep confirmed 10 subprocess.run calls, all using unique tmp_path-derived arguments or unique commands — no eligible redundancy
- **tests/test_bremen_publish_model_package_cli.py** — All 5 call sites reviewed; all use unique tmp_path-derived arguments or unique commands — no eligible redundancy

## Behavior Implemented

- Each modified file gets its own independent `_cli_result_cache` fixture (scope="module")
- The fixture caches `subprocess.CompletedProcess` objects keyed by `tuple(args)`
- First invocation of each unique command executes `subprocess.run` normally
- Subsequent invocations with the same args return the cached result
- Asserts and logic below each call site unchanged
- No HTTPServer-related fixtures touched
- No subprocess-based approach removed in favor of in-process invocation
- No new dependencies

## Call Sites Converted

### File 1 (test_bremen_cli_entrypoint.py) — 16 sites

| Group | Command | Count | Tests |
|-------|---------|-------|-------|
| 1 | `-m bremen --help` | 8 | test_python_m_bremen_help_exits_0, test_python_m_bremen_help_contains_bremen, test_python_m_bremen_help_contains_disclaimer, test_python_m_bremen_help_contains_stubs, test_python_m_bremen_help_contains_preprocess, TestDemoRunCli.test_demo_run_in_main_help, test_help_no_aramis, test_serve_in_main_help |
| 2 | `-m bremen` | 2 | test_python_m_bremen_no_args_exits_0, test_main_help_shows_serve |
| 3 | `-m bremen demo-run --help` | 4 | TestDemoRunCli.test_demo_run_help_exits_0, test_demo_run_help_shows_options, test_demo_run_pretty_in_help, test_demo_run_capture_dir_in_help |
| 4 | `-m bremen serve --help` | 2 | test_serve_help_exits_0, test_serve_help_contains_host_and_port |

### File 4 (test_bremen_demo_run.py) — 2 sites

| Group | Command | Count | Tests |
|-------|---------|-------|-------|
| 1 | `-m bremen demo-run --help` | 2 | TestCliHelp.test_demo_run_help_exits_0, test_demo_run_help_shows_options |

### File 5 (test_bremen_demo_smoke.py) — 2 sites

| Group | Command | Count | Tests |
|-------|---------|-------|-------|
| 1 | `-m bremen demo-smoke --help` | 2 | TestCliHelp.test_demo_smoke_help_exits_0, test_demo_smoke_help_contains_options |

## Sites Confirmed Untouched

- parametrized stub tests (test_stub_help_exits_0, test_stub_invocation_exits_1) — each parametrized value produces a different command
- import safety tests (test_cli_import_does_not_trigger_xrd_preprocessing, test_cli_import_does_not_trigger_heavy_modules) — no subprocess.run
- test_demo_run_in_main_help (demo_run.py) — unique `-m bremen --help` in this file
- test_demo_run_cli_skip_prediction (demo_run.py) — unique command with --timeout=15 --skip-prediction
- test_demo_smoke_in_main_help (demo_smoke.py) — unique `-m bremen --help` in this file
- test_no_ui_flag_in_demo_smoke (demo_smoke.py) — unique `--ui` command
- All HTTPServer-related fixtures in both demo files
- All tests in File 2 and File 3

## Validation Results

### Compilation
```
python -m compileall tests  →  Pass
```

### Five-file test suite
```
python -m pytest tests/test_bremen_cli_entrypoint.py tests/test_bremen_model_v01_publication.py tests/test_bremen_publish_model_package_cli.py tests/test_bremen_demo_run.py tests/test_bremen_demo_smoke.py -v --durations=30
```
- **Pass count**: 122 passed, 1 skipped (same as baseline)
- **Runtime**: 43.26s (baseline: 57.69s)
- **Speedup**: 1.33x (25% faster)

### Full suite
```
python -m pytest -q
```
- **Pass count**: 2225 passed, 11 skipped
- **Runtime**: 64.69s (baseline: 77.67s)
- **Speedup**: 1.20x (17% faster overall)

### Git state
- HEAD: 96eab5765e5f58085343d079cda96762027d67b3
- Branch: 0095-speed-up-api-server-tests
- Only modified files from this PR: tests/test_bremen_cli_entrypoint.py, tests/test_bremen_demo_run.py, tests/test_bremen_demo_smoke.py

## Boundary Confirmations

- [x] Implementation followed approved PLAN.txt
- [x] No review artifact written
- [x] PLAN.txt not modified
- [x] plan-review artifact not modified
- [x] Only PLAN.txt-approved paths changed
- [x] Test discipline rules applied
- [x] Validation commands run and recorded
- [x] No git mutation commands run
- [x] No registry push or secrets introduced
- [x] No /demo/* prohibited fields introduced
- [x] Unavailable model candidates remain display-only and non-executable
- [x] No test pass count changed
- [x] Files 2 and 3 verified and not modified
- [x] This report is at correct path: .project-memory/pr/0097-cache-redundant-cli-subprocess-calls/implementation-report.md
