# Failure Analysis

## Test Failures Reproduced

Initial reproduction on branch `0118-fix-auth-flow-test-misalignments`:

1. `tests/test_bremen_fastapi_auth_enforcement.py` — collection error:
   `SyntaxError: invalid character '—' (U+2014)` in `src/bremen/api/fastapi_app.py`
   line 1374. This blocked the entire test module.

2. After fixing the syntax error:
   - `TestAuthEnabledMissingToken::test_report_bootstrap_route_no_token_returns_shell`
     — `TypeError: Invalid type for url. Expected str or httpx.URL, got tuple`.
   - `TestReportRouteTicketFallback::test_report_route_rejects_no_auth`
     — `assert 200 == 302` (stale redirect expectation).
   - `TestEnforcementScopePreserved::test_browser_nav_routes_redirect_to_login`
     — `assert 200 == 302` for `/demo/report/test` (stale redirect expectation).

## Failure Classification

### 1. `src/bremen/api/fastapi_app.py` — SyntaxError (code regression)

- **test name**: collection error for `tests/test_bremen_fastapi_auth_enforcement.py`
- **file**: `src/bremen/api/fastapi_app.py`
- **current assertion**: N/A (collection error)
- **expected product behavior**: The file must parse as valid Python.
- **classification**: `code_regression`
- **planned fix**: Remove leftover duplicated code in `demo_report_page` that was
  left behind by the PR0116-D edit. The leftover old docstring tail and old gate
  logic created an unterminated triple-quoted string, causing a cascade of
  misparsing.

### 2. `test_report_bootstrap_route_no_token_returns_shell` — fixture/helper mismatch

- **test name**: `TestAuthEnabledMissingToken::test_report_bootstrap_route_no_token_returns_shell`
- **file**: `tests/test_bremen_fastapi_auth_enforcement.py`
- **current assertion**: iterates `REPORT_BOOTSTRAP_ROUTES` and calls
  `client.get(path)` where `path` is a tuple.
- **expected product behavior**: `REPORT_BOOTSTRAP_ROUTES` should be a list of
  path strings; the test should call `client.get(path)` with a string.
- **classification**: `fixture_mismatch`
- **planned fix**: Fix `REPORT_BOOTSTRAP_ROUTES` to contain only the report path
  string (remove leftover tuples from the old `BROWSER_NAV_ROUTES`).

### 3. `test_report_route_rejects_no_auth` — stale test expectation

- **test name**: `TestReportRouteTicketFallback::test_report_route_rejects_no_auth`
- **file**: `tests/test_bremen_fastapi_auth_enforcement.py`
- **current assertion**: `assert resp.status_code == 302` and
  `assert resp.headers.get("location", ...)`.
- **expected product behavior**: Bare `/demo/report/{job_id}` returns a 200 HTML
  safe bootstrap shell (not a redirect).
- **classification**: `stale_test`
- **planned fix**: Update the test to expect 200 bootstrap shell with
  `data-report-bootstrap` marker and no raw JSON auth error.

### 4. `test_browser_nav_routes_redirect_to_login` — stale test expectation

- **test name**: `TestEnforcementScopePreserved::test_browser_nav_routes_redirect_to_login`
- **file**: `tests/test_bremen_auth_activation_readiness.py`
- **current assertion**: includes `/demo/report/test` in `browser_routes` and
  expects 302 redirect.
- **expected product behavior**: Bare `/demo/report/{job_id}` returns a 200 HTML
  safe bootstrap shell (not a redirect). The report bootstrap behavior is already
  covered by `test_report_bootstrap_route_returns_shell`.
- **classification**: `stale_test`
- **planned fix**: Remove `/demo/report/test` from `browser_routes` (the report
  route is covered separately by the bootstrap shell test).

## Misalignment Themes

1. **Code regression from PR0116-D**: The `demo_report_page` edit left behind
   duplicated old code, causing a SyntaxError. This is the primary blocker.
2. **Stale redirect expectations for bare report URL**: Tests still expected the
   bare `/demo/report/{job_id}` to redirect to login, but the deployed behavior
   returns a safe bootstrap shell (200 HTML).
3. **Fixture/helper mismatch**: `REPORT_BOOTSTRAP_ROUTES` was corrupted with
   leftover tuples from the old `BROWSER_NAV_ROUTES`.

## Code Fixes Needed

- `src/bremen/api/fastapi_app.py`: Remove leftover duplicated code in
  `demo_report_page` (old docstring tail and old gate logic).

## Test Fixes Needed

- `tests/test_bremen_fastapi_auth_enforcement.py`:
  - Fix `REPORT_BOOTSTRAP_ROUTES` to contain only the report path string.
  - Update `test_report_route_rejects_no_auth` to expect 200 bootstrap shell.
- `tests/test_bremen_auth_activation_readiness.py`:
  - Remove `/demo/report/test` from `browser_routes` in
    `test_browser_nav_routes_redirect_to_login`.
