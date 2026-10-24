# PR0174 Precommit Review — Cross-Platform Golden Probability Tolerance

BASE: HEAD == merge-base == `905c725b11d14972fc7ed477196ee3aefd202c79` (all PR0174
work is unstaged/untracked as received; reviewer staged nothing).
Branch `0174-cross-platform-golden-tolerance`. Snapshot 2026-10-24T21:20:52Z.
NOTE: the documented `./venv/bin/python` is broken in this worktree (venv/bin has
no `python` symlink); reviewer used `.venv/bin/python` (CPython 3.13.12) — the
same interpreter the implementation report cites. Non-blocking environment fact.

## Scope / hygiene verification

`git status --short`: exactly ` M src/bremen/platform/models/release_cache.py`,
` M tests/test_ir04_release_cache.py`, `?? .claude/`,
`?? .project-memory/pr/0174-…/` (PLAN.md, IMPLEMENTATION_REPORT.md,
FIVE_RELEASE_READY.md). `git diff --cached` empty. `.claude/` untouched
(`worktrees/` only), not staged, not referenced by the diff — out of scope, as
required. Declared PR content = allowed 5 files; this artifact is the reviewer's.
`git diff --stat HEAD`: 2 files, +234/−1 — matches the report exactly.

## Implementation review — PASS

`release_cache.py` diff (read in full):
- `GOLDEN_PROBABILITY_ABS_TOLERANCE = 1e-12` exported; task rule honored
  (max observed drift 4.6629e-15 < 1e-13 ⇒ 1e-12; not wider).
- `_verify_golden_case`: all six previously-checked fields remain checked —
  `threshold_applied`, `decision_threshold`, `prediction`,
  `target_class_risk_level` stay exact; `probability`, `risk_probability` move
  to `_golden_probability_matches`; status/error_code/safe_reason path untouched
  and returns before payload comparison.
- `_golden_probability_matches` rejects `bool`, any non-(int,float), NaN and
  ±inf for BOTH actual and expected, then absolute-only `<= 1e-12` with no
  relative fallback. Non-finite expectation can no longer match, which equals the
  old strict-`!=` behavior for NaN (NaN != NaN raised before). No silent weakening:
  tolerance is the exact intended superset for finite numerics only.

## Test-quality review — PASS

New `TestGoldenProbabilityTolerance` (17 collected) +
`test_golden_tolerance_is_narrow_and_documented` drive the **real**
`ReleaseCache.install()` offline path (FakeRunner result → mandatory golden
smoke → `_verify_golden_case` → READY marker / `smoke_failed`), not just the
private helper. Coverage: exact pass; observed Darwin/Linux B2 pair
(0.7726940329943811 vs …845) pass; +5e-13 pass; +2e-12 fail; NaN/±inf fail;
"0.77"/None/True/[0.77] fail; threshold +1e-15 fail (no tolerance leak);
prediction mismatch fail; target_class mismatch fail; error-code mismatch fail;
safe_reason mismatch fail; A1 risk_probability drift pass; constant == 1e-12.
Reviewer-counted: focused file = 83 tests (65 at HEAD + 18 new), matching the
report's arithmetic.

## Evidence verification (claims independently reproduced)

- Five release manifest digests: `shasum -a 256 ~/ir07-linux-amd64-work/releases/*/manifest.json`
  → `0f4b3876…/8ad42898…/825de1d3…/1ead9f84…/059575df…` — all five equal the
  FIVE_RELEASE_READY.md table; releases mtime 10:33–10:58 vs installs 15:0x ⇒
  "not rebuilt" claim consistent.
- READY markers physically exist at all five digests under
  `cache-0174/<variant>/<digest>/READY`.
- Per-variant drift/`exact:false`/threshold-diff-0 values in
  `cache-0174-predict.json` match the doc tables (max |Δ| = B3 4.6629e-15).
- macOS B2 regression READY marker verified on disk:
  `/private/tmp/ir0174/cache-macos/d6df5c67bee4c9…dc312321/READY` (doc "d6df5c67…2321").
- Emulation caveat (x86_64 userland in container, not a native host) is
  disclosed in the report WARNINGS — honest, not a durability/production claim.
- AWS not used: deterministic directory reader only; no credentials in diff.

## Validation (commands run by reviewer)

```
git status --short / git diff --cached            → scope as above; staging empty
git diff --check HEAD                             → exit 0
.venv/bin/python -m compileall -q src tests       → exit 0
.venv/bin/python -m pytest -q tests/test_ir04_release_cache.py
                                                  → 83 passed (was 65)
.venv/bin/python -m pytest -q                     → 4550 passed, 19 skipped,
                                                    39 warnings in 29.33s
                                                    (matches reported 4550/19/40)
ruff regression (same .venv ruff, HEAD blobs vs worktree):
  release_cache.py     18 findings → 18 findings (delta 0)
  test_ir04…py          6 findings →  6 findings (delta 0)
  concise lines ≥ new-code ranges (rc≥1056, tests≥1256): none
  ⇒ zero new findings attributable to PR0174
digest/READY/marker checks                        → as listed above
```

## Findings

Blockers: none.

Non-blocking observations (exact locations; no action required for commit):
1. `FIVE_RELEASE_READY.md` labels the digest column "Manifest SHA-256 (release
   digest)"; for release dirs containing a plain `manifest.json` these are equal,
   but the release-digest concept elsewhere is dir-sha256 — wording could conflate
   the two for future release layouts.
2. Evidence split: `cache-0174-result.json` holds only the B2 install record;
   per-variant install seconds live in `cache-0174-predict.json`. Fine, but a
   single index file would make re-audit easier.
3. `_golden_probability_matches` accepts ints for probability fields; harmless
   (exact 0/1 would already be caught by `prediction`/class checks).
4. The stale `./venv` (no `bin/python`) in this worktree contradicts the
   documented validation path; `.venv` works. Environment hygiene, not PR0174.
5. Report itself flags the right future rule: drift >1e-12 must stop and be
   investigated, never widen the constant. Consider an ADR note when IR-09
   schedules it.

## Conclusion

Scope is exactly the two permitted code files plus three permitted PR docs;
`.claude/` untouched and unstaged; the tolerance is narrow, absolute,
probability-only, honestly evidenced, exhaustively regression-tested through the
real install path; discrete/contract checks remain exact; full suite and diff
gate pass; no new lint; all five Linux releases and the macOS regression
install-READY claims independently reproduced from on-disk artifacts.

REVIEW ARTIFACT WRITTEN: yes
VERDICT: pass (READY FOR COMMIT)
BLOCKERS
- none
WARNINGS
- (all non-blocking; listed above)
VALIDATION
- compileall exit 0; focused 83 passed; full 4550 passed / 19 skipped / 39 warnings / 29.33s;
  git diff --check exit 0; ruff delta 0 (18→18, 6→6); digests/READY markers reproduced
FILES READ
- PR0174 PLAN.md, IMPLEMENTATION_REPORT.md, FIVE_RELEASE_READY.md; full diff of
  release_cache.py and test_ir04_release_cache.py; _verify_golden_case/_smoke/install
  regions; external evidence JSONs and READY markers
FILES WRITTEN
- .project-memory/pr/0174-cross-platform-golden-tolerance/PRECOMMIT_REVIEW.md
SNAPSHOT DELTA
- 2 tracked modified files (+234/−1), 3 PR docs untracked, staging empty, .claude/ untouched
PLAN COMPLIANCE
- matches PLAN scope exactly; no artifact/threshold/protocol/schema changes
BREMEN CONTRACT CHECK
- golden smoke still mandatory before READY; exact discrete-field and typed-error
  admission intact; offline install path unchanged
VALIDATION COMPLETENESS CHECK
- all report claims re-run or physically verified; deviations (venv path) documented
EVIDENCE COMPLETENESS CHECK
- five manifest digests, five READY markers, predict JSON, macOS marker all on disk
DIFF COMPLETENESS CHECK
- every changed line reviewed; new-code lint clean; no unrelated edits
BOUNDARY CHECKS
- .claude/ untouched/unstaged/out of scope; no secrets; no patient data in diff

READY FOR COMMIT
