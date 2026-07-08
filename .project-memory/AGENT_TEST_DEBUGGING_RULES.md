# Agent Test Debugging Protocol

## Scope

This protocol applies to all agent-driven test debugging during Bremen development.
It is required reading for any agent discovering or debugging test failures during
implementation or review.

---

## Rule 1: Do not use tail/head on failing pytest output

`tail` and `head` truncate exception context, making root cause undiagnosable.
The first failing run must capture the complete output.

## Rule 2: First failing run command

```bash
python -m pytest -q -x --tb=long -vv
```

- `-x` stops at first failure.
- `--tb=long` prints full traceback with variable values.
- `-vv` shows verbose diff for assertion errors.
- If the output is too long to inspect, proceed to Rule 3.

## Rule 3: Isolate the single failing test

```bash
python -m pytest -q <test-path>::<test-name> -vv --tb=long
```

- Run just the failing test.
- No noise from passing tests.
- Full traceback visible.

## Rule 4: Anti-loop rule

After 3 unsuccessful attempts or 20 minutes on the same failure family,
**stop and classify**. Do not make blind production-code changes after the
third attempt.

Classification categories:

- **product regression**: A change broke existing behavior. Revert or fix.
- **brittle test assertion**: Assertion depends on implementation detail or
  ordering. Fix the test.
- **exception identity / import-order**: Exception is the right type and
  message but `pytest.raises` does not catch it. Check import paths —
  exception classes imported through different module paths are different
  Python types.
- **global state leakage**: Test passes alone but fails when run after other
  test files. Look for shared mutable state (`ModelState`, loggers,
  module-level caches). Add `reset_for_tests()` or fixture isolation.
- **test order dependency**: Tests assume prior test state. Pytest should
  be stateless — fix the fixture or add cleanup.
- **environment issue**: Missing env vars, wrong working directory,
  incompatible Python version, missing system packages.

## Rule 5: Expected exception text visible but pytest.raises does not catch it

Suspect exception class identity / import-order issue. Verify the exception
being raised is literally the same class as the one in the `except` clause /
`pytest.raises`. Check that the exception module is imported at the top of
the test file, not conditionally.

## Rule 6: Test passes alone but fails after other files

Suspect global state leakage. Likely candidates: `ModelState` singleton,
module-level caches, global loggers with handlers attached, `sys.path`
modifications. Add `ModelState.reset_for_tests()` in fixtures or cleanup.

## Rule 7: Test isolation preferences

- Prefer fixing test isolation (fixtures, cleanup, reset) over changing
  production code.
- Prefer centralised exception imports (one canonical module) over
  duplicating exception class references.
- Do not add sleep/timing-based workarounds. If timing matters, use
  `pytest-timeout` or explicit wait loops with backoff.

## Rule 8: No external dependencies in unit tests

- No real AWS, Docker, Terraform, or network calls by default.
- No real H5 files or model artifacts in unit tests — use synthetic data.
- All real-resource tests must be skipped by default
  (`pytest.mark.skipif` with env var guard).

## Rule 9: No sensitive data in logs or exceptions

- No raw patient identifiers.
- No full S3 URIs.
- No raw feature values.
- No raw scan arrays.
- No secrets, account IDs, or registry URLs.
