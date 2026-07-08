# Bremen Test Design Standard

## Scope

This standard governs the design of all tests in the Bremen project. It
complements AGENT_TEST_DEBUGGING_RULES.md by defining how tests should be
structured to avoid common failure modes and design anti-patterns.

---

## Rule 1: Production-like smoke tests must be in-process

Production-like end-to-end smoke tests must run **in-process** — they must call
application handlers directly without starting a real HTTP server. This ensures:

- Deterministic execution with no port conflicts.
- No thread-safety races between server and test code.
- No dependency on ephemeral network resources.
- Fast setup and teardown.

**Exception**: A PR that **explicitly targets server transport behavior** (e.g.,
HTTP keep-alive, connection pooling, TLS termination) may use a real server.
Such tests must be in a dedicated file named `test_bremen_api_server.py` or
similarly scoped, and must be clearly separated from production smoke tests.

---

## Rule 2: Server-class tools belong only in dedicated server tests

The following patterns and modules belong **only** in dedicated server tests
(e.g., `tests/test_bremen_api_server.py`). They must not appear in production
smoke tests or other domain tests:

| Pattern / Module                  | Reason                                    |
|-----------------------------------|-------------------------------------------|
| `http.server.HTTPServer`          | Starts a real TCP listener                |
| `http.server.BaseHTTPRequestHandler` | Part of the server handler class       |
| `threading.Thread`                | Introduces concurrency races              |
| `socket.` (any socket API)        | Opens real network sockets                |
| `http.client`                     | Makes real HTTP requests                  |
| `.serve_forever()`                | Blocks forever in server loop             |
| `time.sleep()`                    | Hides race conditions / fragile timing    |
| `_find_free_port()`               | Implicit network dependency               |

**Design principle**: If a test needs a real network stack, it is a server test,
not a smoke test. Name it accordingly and place it in the server test file.

---

## Rule 3: Prefer direct handler calls over HTTP round-trips

When testing API behavior (submit prediction, get prediction, health, model
version), call the handler functions directly:

```python
from bremen.api.app import handle_submit_prediction, handle_get_prediction

response = handle_submit_prediction(payload, store)
```

Do not start an HTTP server and use `urllib.request.urlopen` to test API logic.
The handler functions **are** the API contract. If the contract changes, the
handler signatures change. HTTP round-trips add latency, flakiness, and
concurrency overhead without improving coverage.

---

## Rule 4: Prefer monkeypatch over fixtures that create servers

If a test requires a model or job store, use fixtures that set up the
dependency directly. Do not create server fixtures that start threads or
network listeners. Prefer `monkeypatch` to replace external dependencies
(H5 staging, S3 clients, inference handlers).

---

## Rule 5: One test file, one testing pattern

Each test file should follow a single pattern:

| File name pattern                        | Testing pattern                              |
|------------------------------------------|----------------------------------------------|
| `test_bremen_api_server.py`              | Real HTTPServer + threading for server tests |
| `test_bremen_production_smoke.py`        | In-process handler calls, no network         |
| `test_bremen_predictions.py`             | In-process handler calls, no network         |
| `test_bremen_*.py` (all others)          | Pure unit tests, no network, no server       |

Mixing patterns in a single file creates confusion about what the file tests
and makes it harder to enforce policy checks.

---

## Rule 6: No synthetic model loading in smoke tests unless unavoidable

Production smoke tests should load models through `ModelState.load_at_startup()`
using a synthetic joblib package created in the test. Do not add production
model artifacts to the repository. If a synthetic model is needed, create it
inline with `joblib.dump()` on a temporary path.

---

## Rule 7: Policy-enforcement tests must be in test_bremen_test_policy.py

Tests that enforce test-design standards (e.g., AST-based checks that
forbidden patterns do not appear in specific files) must be placed in
`tests/test_bremen_test_policy.py`. This provides a single location for
policy enforcement and makes the policy rules discoverable.
