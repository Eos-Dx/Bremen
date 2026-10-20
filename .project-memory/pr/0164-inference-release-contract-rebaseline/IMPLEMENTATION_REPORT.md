# IMPLEMENTATION_REPORT.md — PR0164 inference-release-contract-rebaseline

## 1. Task Completed

`0164-inference-release-contract-rebaseline` — align Bremen roadmap and
architecture documentation with the approved independent Model Release
design (Harness / Model Runner / common Worker / ML plugin ownership
split, file-based Worker protocol v1, typed error codes, explicit release
lifecycle, CI/CD separation note, final onboarding-acceptance criterion,
and V2/V3 future-direction documentation). Documentation only.

## 2. Branch / PR

- Branch: `0164-inference-release-contract-rebaseline`
- PR identifier: 0164 (logical, not yet opened as a GitHub PR)
- HEAD commit at start and end of this task: `6588c3b13b5ecfbf2b59790a73268b6603f5f604`
  (no commit was made by this task; working tree only)

## 3. Files Changed

Modified (tracked files, all within the ALLOWED CHANGES list):

- `ROADMAP.md`
- `docs/adr/0019-independent-inference-releases-app-runner.md`
- `docs/inference-releases/architecture-and-contract.md`
- `docs/inference-releases/implementation-plan.md`
- `docs/inference-releases/operations.md`
- `docs/inference-releases/parity-and-rollout.md`
- `.project-memory/pr/ir-02/PLAN.md`
- `.project-memory/pr/ir-03/PLAN.md`
- `.project-memory/pr/ir-05/PLAN.md`
- `.project-memory/pr/ir-06/PLAN.md`

Created:

- `.project-memory/pr/0164-inference-release-contract-rebaseline/IMPLEMENTATION_REPORT.md` (this file)

Deliberately **not** changed (explicitly within the allowed-change scope
but assessed as not requiring edits — see §5):

- `.project-memory/pr/ir-01/PLAN.md`
- `.project-memory/pr/ir-04/PLAN.md`
- `.project-memory/pr/ir-07/PLAN.md`

No file outside the ALLOWED CHANGES list was touched. No `src/`, `tests/`,
Docker, CI workflow, or dependency file was modified. Confirmed by
`git status --short` (see §8) showing only the files above as modified,
plus the pre-existing untracked directories (`results/`, `testing_results/`,
`.project-memory/agents/master_prompt.md`,
`.project-memory/pr/0163-fix-validation-traces-and-standard-result-contract/`)
which were present before this task started and were left untouched.

## 4. Implementation Summary

Rewrote the independent-inference-release documentation bundle to use a
single, consistent vocabulary and to remove the one real contradiction
that existed in the already-committed docs (the architecture doc
specified a stdin/stdout JSON-Lines worker protocol while this task's
instructions require a file-based protocol).

- **ADR 0019** (`docs/adr/0019-...md`): introduced the Harness / Model
  Runner / Worker / ML plugin ownership split and the explicit
  "Harness MUST NOT import ML plugin code" rule; renamed "inference
  wheel" to "ML plugin wheel" and added "golden tests" to what a Model
  Release delivers; replaced the stdin/stdout JSON protocol description
  with the file-based `request.json` + `input.h5` -> `result.json`
  protocol, referencing the typed error codes and the detailed wire
  format in `architecture-and-contract.md`; added the explicit
  PUBLISHED → VERIFIED → READY → ACTIVE release lifecycle; added the
  final architectural acceptance statement (new conforming release
  onboarded without rebuilding Bremen or changing Harness code); added a
  new "Future directions (non-binding)" section documenting V2
  persistent workers and V3 OCI-packaged releases as optional,
  not-yet-reviewed amendments.
- **`architecture-and-contract.md`**: added a terminology paragraph
  defining Harness/Model Runner/Worker/ML plugin and the import-boundary
  rule; added `golden_tests` to the release manifest table and renamed
  the entrypoint field's wheel reference to "ML plugin wheel"; replaced
  the entire "Worker protocol v1" section's `bremen.worker.v1` definition
  from UTF-8 JSON Lines over stdin/stdout to the file-based protocol,
  explicitly stating stdout/stderr are diagnostics-only and optional
  structured events are never a substitute for `result.json`; added a
  new "Typed error codes" subsection enumerating the seven required codes
  with their meaning and how pre-existing failure categories map onto
  them; added a "Release lifecycle" subsection defining the four states;
  updated the "Supervisor and installer" section to describe staging
  `request.json`/`input.h5` and reading `result.json`, and to tie the
  READY marker to running the release's golden tests; added a "Final
  architectural acceptance" section matching Required Change #9.
- **`implementation-plan.md`**: updated IR-02's Work line to name the
  file-based protocol, the `golden_tests` manifest field, the typed
  error codes, and the Harness/plugin import boundary; updated IR-03's
  Work line to say "ML plugin wheels", add golden tests, and state that
  Model Release CI/CD is documented as separate from Bremen's
  application CI/CD (no workflow files touched); updated IR-05's Work
  line to use Harness/Model Runner terminology and the file-based
  protocol; updated IR-06's Work line to name the VERIFIED → READY →
  ACTIVE lifecycle explicitly during activation.
- **`operations.md`**: added a new "CI/CD separation (documentation
  only)" section stating Model Release CI/CD is a distinct,
  release-only pipeline from the existing application CI/CD workflow,
  with no workflow file created or modified by this task; extended the
  "Required diagnostics" paragraph to name the lifecycle phase values
  and the typed worker error code.
- **`parity-and-rollout.md`**: one-line update to the activation
  paragraph naming the VERIFIED → READY → ACTIVE lifecycle and linking
  to `architecture-and-contract.md`.
- **`ROADMAP.md`**: added a new "Contract terminology and final
  acceptance (2026-10-20 rebaseline)" paragraph after the execution
  sequence table, summarizing the terminology/protocol/lifecycle
  rebaseline and the final onboarding-acceptance criterion, and stating
  IR-01 through IR-07 and their order are unchanged.
- **`.project-memory/pr/ir-02/PLAN.md`, `ir-03/PLAN.md`,
  `ir-05/PLAN.md`, `ir-06/PLAN.md`**: minor Work-section wording updates
  mirroring the corresponding `implementation-plan.md` edits above, so
  the per-PR draft briefs stay consistent with the rebaselined
  terminology. No entry/gate/rollback/exclusion text, dependency
  relationship, or scope was changed in any of these four files.

## 5. Key Decisions Made During Implementation

1. **Which `ir-0N/PLAN.md` files to edit.** The task prompt allows
   editing all of `ir-01` through `ir-07`, but the actual IR-01, IR-04
   and IR-07 draft briefs do not mention the worker protocol, wheel
   terminology, or CI/CD split at all — editing them would have been
   cosmetic and risked unrelated scope drift in an otherwise tightly
   scoped documentation task. I edited only IR-02, IR-03, IR-05 and
   IR-06, where the existing text concretely named the stdin/stdout
   protocol, wheel terminology, or activation step that the rebaseline
   changes. IR-01, IR-04 and IR-07 are left byte-for-byte unchanged and
   are explicitly recorded as "no change required" rather than silently
   skipped.
2. **CI/CD separation (Required Change #6) is documentation-only.** The
   task's own HARD RULES forbid any CI/CD or workflow-file change. I
   interpreted "separate model release CI/CD from application CI/CD in
   documentation only" as adding explanatory text (in `operations.md`
   and `implementation-plan.md`'s IR-03 entry) that *describes* the
   intended separation for a future implementation PR, without creating,
   renaming or editing any `.github/workflows/*` file. No workflow file
   was touched (verified by `git status --short`, §8).
3. **Where to put the release lifecycle and final-acceptance statements.**
   Both were added to `architecture-and-contract.md` as the canonical,
   detailed definition (since it already carries all other normative
   contract tables), with a short cross-referencing summary added to
   `ROADMAP.md` and `ADR 0019` rather than duplicating full prose in all
   three places.
4. **Optional events channel.** The original architecture doc modeled
   `started`/`features`/`result`/`error` as JSON-Lines events on the
   single stdin/stdout channel. Since the new protocol's result channel
   is a file, I kept the same four event *names* and semantics but moved
   them to an explicitly diagnostics-only channel (stderr or an auxiliary
   events file), with `result.json` as the sole authoritative terminal
   state. This was necessary to satisfy "preserve ... event semantics"
   together with "stdout/stderr are diagnostics only" without inventing
   a second result channel.

## 6. Deviations From PLAN.md

This task's prompt explicitly states it is the authoritative
implementation instruction and that no separate plan-review agent or
`plan-review.yml` is required, and that the existing `PLAN.md` status
should not block. For completeness: the previously-existing
`.project-memory/pr/0164-inference-release-contract-rebaseline/PLAN.md`
and its plan-review verdict (`warning`, non-blocking, see
`reviews/plan-review.yml`) are consistent with the work performed here —
same Goal, same Allowed Files, same Non-goals. No deviation from that
PLAN.md's Required Changes, Allowed Files or Non-goals was made. The one
difference from that earlier PLAN.md's Allowed Files list is that this
task's prompt grants edit access to `.project-memory/pr/ir-01/`
through `ir-07/PLAN.md` directly (the earlier PLAN.md listed the same
paths), and that scope was used only where concretely necessary (§5.1).

## 7. Warnings / Unresolved Questions

- **Environment is broken for `pytest`/`compileall` via `python`.** See
  §8 — `venv/bin/python3.13` (and the `venv/bin/python` symlink chain to
  it) does not exist on this machine, and `pytest`/`pip` inside `venv/`
  are therefore unusable. The system `python3` (Homebrew) lacks
  `numpy`/`h5py`/etc., so `pytest -q` fails at collection for 58 modules
  before any test runs. This is a pre-existing local-environment issue,
  not caused by this task: zero `src/` or `tests/` files were touched by
  this change (confirmed by `git status --short` and `git diff --stat`
  in §8/§3). Precommit-reviewer should independently confirm this is
  pre-existing (e.g. by checking out HEAD without this task's changes
  and re-running `pytest -q`) rather than relying solely on this report.
- No other unresolved questions.

## 8. Validation Commands and Results

```
$ python -m compileall -q src tests
(eval):3: command not found: python
exit code: 127
```

`python` is not on PATH in this shell; retried with the available
interpreter:

```
$ python3 -m compileall -q src tests
(no output)
exit code: 0
```

Result: **PASS** — no syntax errors in any `src/`/`tests/` file (expected,
since this task touched zero files under `src/` or `tests/`).

```
$ pytest -q
ERROR tests/test_aramina_v0213_package.py
... (58 modules total)
!!!!!!!!!!!!!!!!!!! Interrupted: 58 errors during collection !!!!!!!!!!!!!!!!!!!
58 errors in 0.92s
exit code: 0 (pytest's own reported exit status for this collection-interrupted run)
```

Root cause investigated: `venv/bin/pytest`'s shebang points to
`venv/bin/python3.13`, which is a dangling symlink to
`/opt/homebrew/opt/python@3.13/bin/python3.13` — that file does not exist
on this machine (`ls` confirms `/opt/homebrew/opt/python@3.13/bin/` does
not exist). Re-running with the system `python3 -m pytest -q` collects
further but still fails on `ModuleNotFoundError: No module named 'numpy'`
(and `h5py`) for the same 58 modules, because the system `python3` is a
different, bare interpreter than the one the project's `venv` was built
against (numpy *is* present under `venv/lib/python3.13/site-packages/`,
but that venv's own interpreter binary is missing, so it cannot be
invoked at all — `venv/bin/pip --version` also fails with "bad
interpreter"). This is reported as a **FAIL / unusable environment**,
not hidden or filtered, per AGENT_TEST_DEBUGGING_RULES.md Rule 4. It is
pre-existing and unrelated to this documentation-only change.

```
$ git diff --check
(no output)
exit code: 0
```

Result: **PASS** — no whitespace/conflict-marker errors in the diff.

```
$ git status --short
 M .project-memory/pr/ir-02/PLAN.md
 M .project-memory/pr/ir-03/PLAN.md
 M .project-memory/pr/ir-05/PLAN.md
 M .project-memory/pr/ir-06/PLAN.md
 M ROADMAP.md
 M docs/adr/0019-independent-inference-releases-app-runner.md
 M docs/inference-releases/architecture-and-contract.md
 M docs/inference-releases/implementation-plan.md
 M docs/inference-releases/operations.md
 M docs/inference-releases/parity-and-rollout.md
?? .project-memory/agents/master_prompt.md
?? .project-memory/pr/0163-fix-validation-traces-and-standard-result-contract/
?? .project-memory/pr/0164-inference-release-contract-rebaseline/
?? results/
?? testing_results/
```

Result: matches exactly the files listed in §3; the five pre-existing
untracked paths were present before this task began and are unrelated to
it (preserved, not touched).

```
$ git diff --stat
 .project-memory/pr/ir-02/PLAN.md                   |  2 +-
 .project-memory/pr/ir-03/PLAN.md                   |  2 +-
 .project-memory/pr/ir-05/PLAN.md                   |  2 +-
 .project-memory/pr/ir-06/PLAN.md                   |  2 +-
 ROADMAP.md                                         |  4 ++
 ...9-independent-inference-releases-app-runner.md  | 21 ++++++--
 .../architecture-and-contract.md                   | 56 +++++++++++++++++-----
 docs/inference-releases/implementation-plan.md     |  8 ++--
 docs/inference-releases/operations.md              |  6 ++-
 docs/inference-releases/parity-and-rollout.md       |  2 +-
 10 files changed, 80 insertions(+), 25 deletions(-)
```

## 9. Safety Checks

- Secrets/forbidden-pattern scan run against the full diff:
  `git diff -- <all 10 changed files> | grep -iE "AKIA|SECRET_ACCESS_KEY|dkr\.ecr|s3://[a-zA-Z0-9._-]+/[^ ]|Nova_|/Users/|/home/"` →
  **no matches** ("no forbidden patterns found").
- No AKIA-style access key IDs, `SECRET_ACCESS_KEY`, ECR registry
  hostnames, literal `s3://bucket/key` object paths, `Nova_`-prefixed
  identifiers, or local absolute paths (`/Users/`, `/home/`) were
  introduced.
- Clinical-claims check: no new clinical/release-readiness language was
  added; all new text is platform/architecture terminology (Harness,
  Worker, ML plugin, lifecycle states, error codes). No mention of
  "diagnoses", "FDA-ready", "clinically proven", "approved", "safe for
  deployment", or similar forbidden language per `AGENTS.md`.
- Boundary confirmation: every changed file is in the task's ALLOWED
  CHANGES list; no `src/`, `tests/`, Dockerfile, `.github/workflows/*`,
  or dependency manifest (`pyproject.toml`, lockfiles) was modified.

## 10. Boundaries Preserved

- Only documentation and `.project-memory/pr/ir-0N/PLAN.md` draft briefs
  were changed, exactly as the ALLOWED CHANGES list permits.
- No source, test, Docker, CI, infrastructure, or dependency file was
  changed (confirmed by `git status --short`/`git diff --stat`, §8).
- No scientific behavior, model mathematics, feature schema, threshold,
  or public API was changed — none of this task's edits touch any file
  capable of expressing such behavior.
- `Model Runtime Contract v1`, `Model Package Standard v1`, and
  `Standard Model Result Contract v1` were not edited
  (`docs/model_runtime_contract_v1.md`,
  `docs/standard_model_result_contract_v1.md` are untouched); the new
  text in `architecture-and-contract.md` explicitly instructs preserving
  their existing semantics (e.g. "preserving the existing ModelRuntime
  semantics", "RuntimePrediction/result contracts").
- No deployment, S3 publication, or model activation was performed or
  authorized by this change; the new "release lifecycle" and "final
  architectural acceptance" text describes states/criteria for later
  implementation PRs (IR-02 onward), it does not execute them.
- IR-01 through IR-07 dependency order and gates are unchanged; only
  Work-line wording in IR-02/03/05/06 was updated for terminology
  consistency, per §5.1.

## 11. Commit Readiness

**Blocked — requires human review of one item before commit, not a
correction to the documentation itself:** the local test environment
(`venv/bin/python3.13` missing; system `python3` missing `numpy`/`h5py`)
prevents running `pytest -q` to completion in this session. `compileall`
and `git diff --check` both pass, and the change is documentation-only
with zero `src/`/`tests/` files touched, so this is very unlikely to be
caused by or related to this task's content — but it could not be
independently confirmed as "pre-existing" by actually running the full
suite against unmodified `HEAD` in this session. Recommend the
precommit-reviewer either reproduce this environment issue independently
or have a working Python environment available before issuing a final
verdict.

Aside from that environment caveat, the documentation changes themselves
are internally consistent, within the approved scope, and ready for
commit.

## 12. Recommended Next Action

Proceed to precommit review. Precommit-reviewer should: (a) diff this
report's file list against `git diff --name-only` independently; (b)
confirm the `pytest` collection failure is a pre-existing environment
issue (e.g. by checking it reproduces on `HEAD` without this task's
changes, or by using a working Python environment with `numpy`/`h5py`
installed); (c) spot-check that no scientific/API/CI/infrastructure file
was touched, consistent with §8/§10 above.
