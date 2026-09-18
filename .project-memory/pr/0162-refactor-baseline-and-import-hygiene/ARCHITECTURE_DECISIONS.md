# Architecture decisions

- Public HTTP/report/event contracts are the boundary; internal import paths may change.
- ModelRuntime remains the only scientific execution interface. Descriptor policies carry legacy input preparation and public result projection; they must not expose feature/inference/execute provider methods.
- Aramina still uses canonical QC before artifact-owned raw preprocessing. Removing that QC would change science: isolate canonical preparation as an explicit legacy input adapter until raw parity is proved. Bremen paper-reference runtime already accepts raw H5.
- Retain legacy http.server transport because it still serves public routes/CLI; remove its ownership of application state.
- Baseline OpenAPI failure is pre-existing; route inventory and live contract tests are the freeze.

## Implemented decisions

- Route groups own HTTP translation, services own job/source/report operations, repository owns process-local state and locks.
- Result and event projection policies preserve legacy wire shapes; they do not invoke estimators or preprocessing.
- No type-signature fallback or workflow-specific argument remains in the executor.
- Generic descriptors contain runtime, input policy and public projection callbacks. Adding a runtime does not require editing the executor; a third-runtime test demonstrates that boundary.
- Seven unused plugin stage dataclasses and the dead duplicate preprocessing bridge were removed after whole-source caller audit.
- `reports/` was globally ignored; `.gitignore` now explicitly includes source code under `src/bremen/platform/reports/` while generated report outputs remain ignored.
- API source inspection tests now target actual owners. Repository singleton tests restore monkeypatched package state between cases; otherwise a test's deletion of process-wide objects left stale references for later tests.
- Full public characterization suites remain. Internal import compatibility is intentionally not preserved.
