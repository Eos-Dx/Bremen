# IR-06 release-runtime cutover

## TASK COMPLETE

The catalog/runtime boundary now treats a validated `runtime_release` as the
authoritative execution route. Legacy entries without that field retain the
existing embedded path for compatibility.

## ARCHITECTURE BEFORE / AFTER

Before: catalog discovery fetched/staged legacy artifacts and imported the
embedded scientific package; the registry selected subprocess execution only
through the IR-05 candidate allowlist.

After: release-backed discovery validates catalog metadata only and can create
a manifest-only entry. Registry construction selects `SubprocessRuntime`
automatically; execution remains lazy through `ReleaseCache.install()` and the
existing offline wheelhouse, digest-qualified venv, Worker, `result.json`, and
platform projection. No per-model candidate allowlist is required.

## LIVE AWS / APP RUNNER

NOT PART OF THIS IMPLEMENTATION PASS. No AWS calls, App Runner inspection,
CloudWatch, billing, deployment, activation, or remote writes were performed.

## VALIDATION

- `python -m compileall -q src tests`: passed
- focused discovery/registry/IR-05 suites: 223 passed
- IR-03/IR-04/worker suites: 385 passed
- five-release parity: 21 passed
- full suite: 4503 passed, 8 skipped, 40 warnings
- `git diff --check`: passed

## WARNINGS

The supplied `/tmp/ir05/releases` evidence is local IR-05 evidence and is not
live deployment evidence. Operational App Runner rollout remains a separate
authorized activity.

## NEXT ARCHITECTURAL STEP

IR-07 external XRD feature-library integration. The 15 Bremen XRD feature
functions must be extracted into a standalone, independently versioned
Python wheel, release-bound per Model Release, before legacy cleanup
(renumbered IR-08) proceeds. No feature-library extraction work has been
done as part of this IR-06 pass; see
[ROADMAP.md](../../../ROADMAP.md) and
[architecture-and-contract.md](../../../docs/inference-releases/architecture-and-contract.md#feature-library-architecture-to-implement-in-ir-07).
