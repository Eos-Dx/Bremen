# CODER REPORT — PR0116 Hotfix frontend auth refresh/state on report page

## TASK COMPLETE

Yes.

## FILES CHANGED

- `src/bremen/report_ui.py` — added canonical browser auth helpers (`_getSessionStorage`, `_getAccessToken`, `_getRefreshToken`, `_setTokens`, `_clearTokens`, `_redirectToLogin`, `_authFetch`) to the report page JS; replaced plain `fetch(...)` with `_authFetch(...)` for all four protected report endpoints; added graceful degradation when no stored session exists.
- `tests/test_bremen_report_ui.py` — added `TestReportPageAuthFetch` class covering auth helper presence, Bearer attachment, refresh-on-401, token storage, single retry, no refresh loop, token-clear on failure, protected-endpoint wrapping, no plain fetch for protected endpoints, no token-in-URL, no JWT literals, graceful degradation, and sample-mode bypass.

## ROOT CAUSE

- **Which report-page fetches were unwrapped/stale?** All four protected report JSON fetches in `loadReport()` used plain `fetch(...)`:
  - `GET /demo/api/jobs/{job_id}`
  - `GET /demo/api/jobs/{job_id}/reports/bremen`
  - `GET /demo/api/reports/{job_id}/external`
  - `GET /demo/api/reports/{job_id}/internal`
  The report page (`report_ui.py`) had no auth helper at all, so no `Authorization: Bearer` header was attached and no refresh flow existed.
- **Why did refresh not update the request path?** There was no refresh logic on the report page. The Control Room (`control_room_ui.py`) had a working `_authFetch` with refresh+retry, but the report page was a separate document that did not reuse it and did not bootstrap auth state from browser storage.
- **What exact helper now handles those fetches?** The report page now defines and uses `_authFetch(url, opts)`, which reads the access token from the canonical `sessionStorage` key (`bremen_access_token`), attaches `Authorization: Bearer <token>`, and on 401 calls `POST /demo/api/auth/refresh` with the canonical refresh token (`bremen_refresh_token`), stores the new tokens via `_setTokens`, updates the in-memory header, and retries the original request exactly once.
- **How does the page behave if opened with report ticket but no stored session?** `loadReport()` checks `!_getAccessToken() && !_getRefreshToken()` first. If no tokens exist (e.g., a copied report-ticket URL opened in a fresh browser context), it renders a clear "Login required to refresh live report details" message and returns without issuing any protected API requests — no 401 storm, no infinite refresh loop.

## IMPLEMENTATION SUMMARY

- Added the canonical browser auth contract to the report page JS, matching the Control Room's `_authFetch` implementation exactly (same storage keys, same refresh endpoint, same single-retry semantics).
- Replaced all four plain `fetch(...)` calls in `loadReport()` with `_authFetch(...)`.
- Added graceful degradation for the no-session case.
- No backend auth changes. No model behavior changes. No clinical wording changes. No deployment config changes.

## FRONTEND AUTH FLOW

The report page now uses the same canonical auth flow as Control Room:

1. `_getAccessToken()` reads `bremen_access_token` from `sessionStorage`.
2. `_authFetch` attaches `Authorization: Bearer <access_token>`.
3. On 401, `_authFetch` reads `bremen_refresh_token` and calls `POST /demo/api/auth/refresh`.
4. On success, `_setTokens(result.data)` stores the new access/refresh tokens and expiry in the same canonical storage keys.
5. The in-memory `headers` object is updated with the new Bearer token.
6. The original request is retried exactly once.
7. On refresh failure or missing refresh token, tokens are cleared and the user is redirected to `/demo/login`.

## REPORT PAGE FIX

- `loadReport()` now uses `_authFetch` for all four protected endpoints.
- No plain `fetch(...)` remains for protected report endpoints.
- Graceful degradation: if no stored session tokens exist, the page shows a clear login-required message and does not issue protected requests.

## REFRESH RETRY BEHAVIOR

- On 401, `_authFetch` calls the refresh endpoint once.
- If refresh succeeds, the new access token is stored, the in-memory header is updated, and the original request is retried exactly once.
- If refresh fails or the refresh token is missing, tokens are cleared and the user is redirected to login.
- No refresh loop: only one retry per original request.

## TICKET FLOW PRESERVED

- `connectSSE()` in Control Room still mints a `purpose=stream` ticket and uses `auth_ticket` in the EventSource URL.
- `openJob()` in Control Room still mints a `purpose=report` ticket and navigates to `/demo/report/{job_id}?auth_ticket=...`.
- No access_token or refresh_token is placed in URLs.
- The report page ticket navigation flow is unchanged.

## SECURITY NOTES

- No access_token or refresh_token in URLs.
- No token-in-query-parameter patterns added.
- No new token-in-URL patterns introduced.
- No real JWT literals in frontend strings.
- No backend auth rules broadened.
- No ticket auth accepted as Bearer on protected routes.
- No tokens or tickets logged.

## TESTS ADDED/UPDATED

Added `TestReportPageAuthFetch` class to `tests/test_bremen_report_ui.py` with 20 tests covering:

- A. Report page JS uses auth helper for all protected endpoints (job, reports/bremen, external, internal).
- B. Refresh response updates stored access token (`_setTokens(result.data)`).
- C. Refresh endpoint is not called in a loop (only one retry per original request).
- D. Report navigation remains ticket-based (existing Control Room tests still pass).
- E. SSE remains ticket-based (existing Control Room tests still pass).
- F. No raw token leak in frontend strings (no `access_token=`/`refresh_token=` in URLs, no JWT literals).
- G. Existing auth enforcement remains intact (existing FastAPI auth tests still pass).

## VALIDATION RUN

| Command | Exit | Result |
|---|---|---|
| `python -m compileall src/bremen tests` | 0 | Pass |
| `pytest tests/test_bremen_report_ui.py -q` | 0 | 204 passed |
| `pytest tests/test_bremen_control_room.py -q` | 0 | 533 passed |
| `pytest tests/test_bremen_fastapi_auth_enforcement.py -q` | 0 | 47 passed |
| `pytest tests/test_bremen_auth.py -q` | 0 | 64 passed |
| `pytest -q` (full suite) | 0 | 3606 passed, 11 skipped |
| `git diff --check` | 0 | Pass |
| `! grep -RInE 'access_token=.*eyJ\|refresh_token=.*eyJ\|auth_ticket=.*eyJ' src/bremen tests docs README.md` | 0 | Pass (no matches) |
| `! grep -RInE 'access_token=\|refresh_token=' src/bremen/control_room_ui.py tests` | 0 | Pass (no matches) |

## WARNINGS

- The clinical safety grep (`! grep -RInEi 'detects cancer|diagnoses|diagnosis engine|replaces clinician|FDA approved|clinically certified|rules out disease' src/bremen tests docs README.md`) returns matches, but all are pre-existing in unrelated files (`model_playground_page.html`, `demo_evidence.py`, various tests, docs). The diff for this PR introduces no forbidden clinical phrases. The report UI text added ("Login required to refresh live report details") contains no forbidden wording.

## READY FOR REVIEW

Yes.
