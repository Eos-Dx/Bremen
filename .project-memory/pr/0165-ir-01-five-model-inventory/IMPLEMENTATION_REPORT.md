# IMPLEMENTATION_REPORT.md — PR0165 ir-01-five-model-inventory

> **Continuation update (2026-10-20, same day):** A second pass used
> local artifact directories supplied at `/tmp/bremen-ir01-models` (five
> model packages, one per catalog slot) as external read-only evidence.
> This resolved checksums and thresholds for all five models and
> answered the open "is B3 real?" question. See §16 onward for the
> continuation's work, evidence, validation and updated gate status.
> Sections 1–15 below are preserved unchanged from the first pass.

## 1. Task Completed

`0165-ir-01-five-model-inventory` — establish the verified inventory,
scientific baselines and App Runner feasibility evidence for IR-01
(two Aramina and three Bremen deployed variants), using authorized
read-only repository access. Documentation and evidence only.

## 2. Branch / PR

- Branch: `0165-ir-01-five-model-inventory`
- HEAD commit at start and end of this task: `16d6f28f7e7f557e1ada55e8cdb30a1dded17913`
  (no commit made by this task)

## 3. Files Changed

Modified (within ALLOWED CHANGES):

- `docs/inference-releases/five-model-inventory.md`
- `docs/inference-releases/operations.md`
- `docs/inference-releases/parity-and-rollout.md`

Created:

- `.project-memory/pr/0165-ir-01-five-model-inventory/IMPLEMENTATION_REPORT.md` (this file)
- `.project-memory/pr/0165-ir-01-five-model-inventory/INVENTORY_EVIDENCE.md`

No `src/`, `tests/`, Docker, CI, or infrastructure file was changed. No
file outside `docs/inference-releases/{five-model-inventory,operations,parity-and-rollout}.md`
and `.project-memory/pr/0165-ir-01-five-model-inventory/` was touched.
Pre-existing untracked paths (`results/`, `testing_results/`,
`.project-memory/agents/master_prompt.md`,
`.project-memory/pr/0163-fix-validation-traces-and-standard-result-contract/`)
were present before this task began and are unrelated to it; they were
read as evidence sources but not modified.

## 4. Work Completed

Performed a read-only repository investigation (no live AWS/S3/App
Runner access was available in this session) and recovered concrete,
citable evidence for all five catalog slots, instead of inferring
identities from Python package names:

1. **Catalog identity.** Found seven separately stored catalog-listing
   captures already committed/present under `results/` and
   `testing_results/` (dated 2026-09-10 through 2026-09-17), all
   reporting the identical five-entry catalog
   (`candidate_count=5`, `available_count=5`, `rejected_count=0`):
   two Aramina model_ids
   (`aramina_target_breast_risk_0_2_12-beta_9bb911189af6`,
   `aramina_target_breast_risk_0_2_13-beta_f5e4a04cad11`) and three
   Bremen model_ids (`bremen-mri-triage-logreg-v0-1`,
   `bremen-paper-reference-v0-2-0`, `bremen-v0-2-0-symmetry-candidate`).
   [Corrected 2026-10-21, precommit review B2: these seven captures are
   not claimed to be independent observations — no capture command,
   session/endpoint identifier, or request metadata in the files
   themselves proves that; only that they are seven separately stored
   historical snapshots that consistently repeat the same five model
   identities. See `INVENTORY_EVIDENCE.md` §1.]
2. **Per-model evidence.** For A1/A2, found fresh production execution
   records (`docs/production-contracts-2026-09-18.md`) giving
   decision thresholds, a confirmed preprocessing-release mapping for
   one shared failing fixture (A1→v0.1.7-beta, A2→v0.1.9-beta), and one
   additional A2 fixture/output pair from a separate capture. For B1,
   found a captured production report with threshold `0.3640352477169748`
   and an explicitly **empty** `model_checksum` field, plus one
   unverified historical SHA256/S3-URI lead that must not be treated as
   confirmed. For B2, cross-confirmed artifact SHA256, threshold, and
   15-feature schema across three independent sources (package manifest,
   training-parity doc, and two production captures), plus the existing
   PR0160 tolerance resolution for a sub-digit probability difference.
   For B3, confirmed the catalog string is real but found **zero**
   evidence anywhere in the repository beyond that string — and
   explicitly ruled out a superficially similar "symmetry" training-run
   name (PR0151/PR0152) as actually belonging to B2, not B3.
3. **Feasibility/resource evidence.** Read `Dockerfile` (four Python
   environments built into the image), `src/bremen/platform/jobs/service.py`
   (`ThreadPoolExecutor(max_workers=2)`), and
   `infra/terraform/apprunner.tf` (an explicitly smoke/proving-only App
   Runner definition, not confirmed production, with no CPU/memory
   override set). Searched the repository for "OpenResty" and found no
   reference outside this roadmap's own planning documents.
4. Wrote `docs/inference-releases/five-model-inventory.md` as a
   from-evidence rewrite (full per-slot table, gate record, and
   explicit "not a live-catalog confirmation" framing),
   `docs/inference-releases/operations.md` (new feasibility-evidence
   subsection), and `docs/inference-releases/parity-and-rollout.md`
   (B2 probability cross-check note), plus the detailed
   `INVENTORY_EVIDENCE.md` citation trail and next-agent instructions.

## 5. Key Decisions Made During Implementation

1. **Treated committed production-smoke captures (`results/`,
   `testing_results/`) as primary evidence**, not "historical
   documentation" in the sense the task prohibits inferring from. These
   are captured API responses from real production job execution
   (job IDs, timestamps, HTTP status codes present), not guesses from
   package names or stale design docs. I still explicitly flagged them
   as a one-month-old snapshot requiring live re-confirmation, per the
   task's own "never invent results... based only on historical
   examples" instruction — the gate verdict (§11) reflects that
   caution.
2. **Did not attempt to contact any live AWS/S3/App Runner endpoint.**
   This session has no deployment credentials, and the HARD RULES
   prohibit unauthorized inference runs / production access. Every
   finding is sourced from files already present in the repository
   working tree.
3. **Explicitly distinguished a genuine evidence match (B2's checksum
   across three sources) from a false-positive name collision (B3 vs.
   the "symmetry" training run)** rather than taking the superficial
   string similarity at face value. This directly implements the task's
   "do not invent results" requirement for the hardest slot.
4. **Did not adopt the PR0039-era SHA256/S3-URI lead for B1 as fact.**
   It predates the catalog captures by many PRs and has no corroborating
   execution evidence in this session; I recorded it as an explicit,
   separately-labeled unverified lead rather than silently presenting it
   as B1's checksum.
5. **Did not re-run `tests/fixtures/bremen_3x3/`** to reconfirm B2's
   golden value, because `pytest` could not run in this environment
   (see §8). I relied on the already-committed capture files instead,
   and recorded the fixture re-run as a required next step rather than
   skipping it silently.

## 6. Deviations From PLAN.md

`.project-memory/pr/ir-01/PLAN.md`'s "Expected change areas" names
Discovery/manifests, model runtime paths, Dockerfile, deployment
configuration as *investigation* boundaries ("investigation boundaries,
not permission to redesign adjacent systems"). This task's own ALLOWED
CHANGES is narrower and more specific: only
`docs/inference-releases/five-model-inventory.md`,
`docs/inference-releases/operations.md`,
`docs/inference-releases/parity-and-rollout.md`, and
`.project-memory/pr/0165-ir-01-five-model-inventory/`. I read the
Dockerfile, discovery/registry code, and Terraform for evidence (as the
"investigation boundary" wording allows) but did not edit any of them —
only the three allowed docs and the new PR-memory files were written.
No deviation from this task's own ALLOWED CHANGES or HARD RULES.

## 7. Warnings / Unresolved Questions

- All findings in this report and in `INVENTORY_EVIDENCE.md` are
  repository-evidence-only and dated to captures from 2026-09-10
  through 2026-09-18. None has been re-confirmed against the live
  catalog/deployment as of today, 2026-10-20. This is the primary
  reason the gate is BLOCKED rather than PASS (§11).
- B3 (`bremen-v0-2-0-symmetry-candidate`) has no evidence beyond its
  catalog-listing string. It cannot be extracted, baselined, or
  resource-budgeted until someone with live/artifact access locates or
  produces a training record, checksum, or fixture for it.
- B1's checksum is an open question: one historical capture shows it
  empty; a much older, unverified PR0039 lead names a specific SHA256
  and S3 URI that has not been corroborated by any execution evidence
  found in this pass.
- A1/A2 full artifact SHA256 (as opposed to the id-suffix hash fragment
  embedded in the model_id string) was not found anywhere in the
  repository.
- `infra/terraform/apprunner.tf` is explicitly a smoke/proving
  definition per its own header comment; the actual production App
  Runner service's CPU/memory/concurrency configuration is not present
  in this repository.
- No OpenResty reference was found in source/infra, consistent with
  (but not proof of) the roadmap's working assumption.

## 8. Validation Commands and Results

```
$ python -m compileall -q src tests
(eval):3: command not found: python
exit code: 127
```

Retried with the available interpreter:

```
$ python3 -m compileall -q src tests
(no output)
exit code: 0
```

Result: **PASS** — no syntax errors (expected; zero `src/`/`tests/`
files were touched by this task).

```
$ pytest -q
... (58 modules)
!!!!!!!!!!!!!!!!!!! Interrupted: 58 errors during collection !!!!!!!!!!!!!!!!!!!
58 errors in 0.59s
```

Result: **FAIL / unusable environment**, reproduced identically to the
PR0164 session on this same machine: `venv/bin/python3.13` is a dangling
symlink (its target under `/opt/homebrew/opt/python@3.13/bin/` does not
exist), and the system `python3` lacks `numpy`/`h5py`. This is
pre-existing and unrelated to this task — confirmed because zero
`src/`/`tests/` files are in this task's diff. Reported honestly, not
filtered, per AGENT_TEST_DEBUGGING_RULES.md Rule 4. This also means the
`tests/fixtures/bremen_3x3/` golden fixture could not be re-executed in
this session to reconfirm B2's numbers (§5, item 5; §9 blocker list).

```
$ git diff --check
(no output)
exit code: 0
```

Result: **PASS**.

```
$ git status --short
 M docs/inference-releases/five-model-inventory.md
 M docs/inference-releases/operations.md
 M docs/inference-releases/parity-and-rollout.md
?? .project-memory/agents/master_prompt.md
?? .project-memory/pr/0163-fix-validation-traces-and-standard-result-contract/
?? .project-memory/pr/0165-ir-01-five-model-inventory/
?? results/
?? testing_results/
```

Matches §3 exactly. Pre-existing untracked paths are unchanged (used
only as read sources).

```
$ git diff --stat
 docs/inference-releases/five-model-inventory.md | 74 +++++++++++++++++++++----
 docs/inference-releases/operations.md           | 41 ++++++++++++++
 docs/inference-releases/parity-and-rollout.md   | 14 +++++
 3 files changed, 117 insertions(+), 12 deletions(-)
```

```
$ git rev-parse --verify HEAD
16d6f28f7e7f557e1ada55e8cdb30a1dded17913
```

Unchanged from the precondition check — confirms no commit was made.

## 9. Safety Checks

- Secrets/forbidden-pattern scan on the diff:
  `git diff -- <3 changed files> | grep -iE "AKIA|SECRET_ACCESS_KEY|dkr\.ecr|/Users/|/home/"` →
  **no matches**.
- `Nova_NNN` patient-reference identifiers and demo container filenames
  (e.g. `benign_one_patient.h5`) appearing in the new text are reused
  verbatim from already-committed repository evidence
  (`docs/production-contracts-2026-09-18.md`, which is already on
  `main`), not newly introduced patient data. No raw H5 content,
  credentials, or full artifact bytes were added.
- No clinical-readiness or diagnostic-claim language was added; all new
  text is inventory/evidence/architecture terminology consistent with
  `AGENTS.md`'s release-language rules.
- Boundary confirmation: only the three allowed docs and the new
  `.project-memory/pr/0165-ir-01-five-model-inventory/` files were
  written; no `src/`, `tests/`, Dockerfile, CI workflow, or
  infrastructure file was modified (all were read-only inputs).

## 10. Boundaries Preserved

- Only `docs/inference-releases/five-model-inventory.md`,
  `docs/inference-releases/operations.md`,
  `docs/inference-releases/parity-and-rollout.md`, and
  `.project-memory/pr/0165-ir-01-five-model-inventory/*` were changed —
  exactly the ALLOWED CHANGES list.
- No source, test, Docker, CI, or infrastructure file was changed
  (confirmed by `git status --short`/`git diff --stat`, §8).
- No production mutation, inference run, or deployment action was
  performed. No live AWS/S3/App Runner endpoint was called.
- No patient data, credentials, or private artifact contents were
  introduced beyond already-committed, already-public-in-this-repo
  evidence identifiers (job IDs, model IDs, numeric outputs, Nova_
  demo-patient references already present in `docs/production-contracts-2026-09-18.md`).
- No scientific behavior, threshold, or feature definition was changed
  — this task only read and cited existing values; it did not alter any
  model, config, or runtime code.

## 11. IR-01 Gate Status: **BLOCKED**

Per `.project-memory/pr/ir-01/PLAN.md`'s own acceptance bar ("All five
identities/artifact hashes resolved; baseline success/failure outputs
reproducible; preprocessing mappings explicit; resource/cost limits
reviewed. Missing access or unresolved identities block the next
gate."), this pass resolved substantially more than a name-based guess,
but does not clear that bar for all five:

| Requirement | Status |
|---|---|
| All five identities resolved | Partially — five model_id/model_version pairs are well-evidenced from repeated historical captures, but not re-confirmed live as of today |
| All five artifact hashes resolved | **No** — only B2 has a cross-confirmed hash; B1 has one unverified lead; A1/A2/B3 have none |
| Baseline success/failure outputs reproducible | Partially — A1, A2 and B1 have at least one captured success example and A1/A2 have a captured failure example; B2 has a cross-confirmed success baseline and an existing committed golden fixture (not re-run this session); B3 has none |
| Preprocessing mappings explicit | Partially — confirmed for A1/A2 on one shared input only; not confirmed for all inputs |
| Resource/cost limits reviewed | **No** — only static repository-code evidence gathered; no live measurement, no confirmed production App Runner sizing |

Given the explicit instruction to "never invent results or declare a
gate complete based only on historical examples," and the concrete gaps
above (no live re-confirmation, no resource measurement, B3 essentially
unevidenced, B1/A1/A2 hashes unresolved), the gate is reported
**BLOCKED**, not PASS. The evidence gathered substantially reduces the
remaining work for the next agent with live access (see
`INVENTORY_EVIDENCE.md` §9 for the exact next steps) but does not by
itself satisfy the gate.

## 12. Blockers and Required Access

1. Live S3 catalog / model registry read access, to re-confirm today's
   exact five identities against the 2026-09 captures used here.
2. Live App Runner / deployment access, to measure CPU/RSS/cost,
   cold/warm timing, and confirm the actual production service
   definition (this repository only has a smoke/proving Terraform
   definition).
3. Access to the actual artifact objects (or their authoritative
   checksums) for A1, A2, and B1, to resolve their currently-unknown
   full SHA256 values and to verify or discard the unverified B1 lead.
4. Any training record, artifact, or fixture for B3 — currently none
   exists anywhere in this repository.
5. A working local Python environment (`numpy`/`h5py` installed, or the
   project `venv`'s interpreter restored) to re-run
   `tests/fixtures/bremen_3x3/` and reconfirm B2's golden values.

## 13. Instructions for the Next Agent

See `INVENTORY_EVIDENCE.md` §9 for the detailed, numbered next steps.
In summary: re-confirm the catalog live; pull real artifact
hashes/manifests for all five; measure actual App Runner resource usage
against the real (not smoke-only) service definition; locate or produce
any evidence at all for B3; and restore a working Python environment to
re-run the existing B2 golden fixture before declaring IR-01 PASS.

## 14. Commit Readiness

Blocked — not a correction to the documentation itself, but because the
IR-01 gate this PR documents is itself BLOCKED pending live access
(§11–§12). The documentation changes are internally consistent, honest
about their evidentiary limits, and within the approved scope; they are
ready for precommit review as an accurate record of a blocked gate, not
as a claim that IR-01 has passed.

## 15. Recommended Next Action (first pass — superseded by §24)

Proceed to precommit review of this documentation/evidence PR. The
precommit-reviewer should confirm: (a) the IR-01 gate is correctly
reported as BLOCKED, not PASS; (b) every claim in
`five-model-inventory.md`/`INVENTORY_EVIDENCE.md` traces to an actual
file in the repository (spot-check a few citations); (c) no file
outside the ALLOWED CHANGES list was touched; (d) the `pytest`
environment failure is independently reproduced or otherwise confirmed
pre-existing before accepting it as unrelated to this change.

---

# Continuation: local artifact-directory evidence (2026-10-20)

## 16. Task Completed (continuation)

`0165-ir-01-five-model-inventory` (implementation-continuation) —
inspect five local model-artifact directories supplied at
`/tmp/bremen-ir01-models`, verify identity/checksums against them, map
them to catalog slots A1/A2/B1/B2/B3, resolve previously-missing facts,
and determine whether B3 is a real artifact or only a catalog string.

## 17. Branch / HEAD (continuation)

Branch: `0165-ir-01-five-model-inventory` (unchanged). HEAD before and
after this continuation: `16d6f28f7e7f557e1ada55e8cdb30a1dded17913`
(unchanged — no commit made).

## 18. Files Changed (continuation)

Modified further (same three files as the first pass, additional
edits):

- `docs/inference-releases/five-model-inventory.md` (substantially
  rewritten with the resolved identity table, B3 resolution, and
  updated gate record)
- `docs/inference-releases/operations.md` (unchanged in this
  continuation — the local-artifact evidence did not add new resource
  facts)
- `docs/inference-releases/parity-and-rollout.md` (added a precision
  note about A1/A2 threshold rounding)

Updated:

- `.project-memory/pr/0165-ir-01-five-model-inventory/INVENTORY_EVIDENCE.md`
  (added §9 "Local artifact-directory pass," §9.1–9.2, renumbered the
  former §9 "Instructions for the next agent" to §10)
- `.project-memory/pr/0165-ir-01-five-model-inventory/IMPLEMENTATION_REPORT.md`
  (this section)

No `src/`, `tests/`, Docker, CI, or infrastructure file was changed. No
file from `/tmp/bremen-ir01-models` was copied into the repository —
confirmed by `git status --short` showing no new/modified `.joblib`,
`.yaml`, or `.json` file under any tracked or untracked repository path
other than the explicitly listed docs/project-memory files above.

## 19. Work Completed (continuation)

1. Inventoried every file in all five `/tmp/bremen-ir01-models`
   subdirectories with `find ... -exec ls -la` (full listing recorded
   in `INVENTORY_EVIDENCE.md` §9).
2. Read every `manifest.json` (all five) and mapped each directory to a
   catalog slot **by the manifest's own declared `model_id` field**,
   not by directory name — directory names (`v0.1`, `v0.2.0`,
   `0.2.0-paper-reference`) are themselves ambiguous/alias-like and
   were deliberately not trusted alone.
3. Computed SHA256 (`shasum -a 256`) for every file in all five
   directories (33 files total) and specifically verified each
   artifact's hash against its own manifest's `model_checksum` field —
   all five self-consistent.
4. Cross-checked each local checksum against prior evidence: A1, A2,
   B2 matched previously-recorded values exactly; B1 matched a
   previously-flagged *unverified* lead exactly (promoting it to
   artifact-confirmed); B3 had no prior value anywhere in the
   repository (new evidence).
5. Used `cmp` to confirm `v0.2.0/model.joblib` and
   `v0.2.0/bremen_mri_triage_symmetry_logreg_v0.2.0.joblib` are
   byte-identical (same artifact, duplicated filename).
6. Used `diff` to compare `aramina_0_2_12-beta/` vs
   `aramina_0_2_13-beta/` sidecar files, confirming the only
   substantive difference is `preprocessing_config.yaml`'s
   `release_tag` (`v0.1.7-beta` vs `v0.1.9-beta`) plus version-identity
   fields — upgrading the A1/A2 preprocessing-release mapping from
   "confirmed for one production fixture" to "artifact-declared in
   general."
7. Read `model_description.yaml`, `feature_schema.json`,
   `label_mapping.json`, `metrics.json`, and `container_requirements.json`
   (where present) for each directory as plain text/YAML/JSON — **no**
   `.joblib` file was loaded/unpickled.
8. Determined B3 is a real, distinct, trained artifact with its own
   manifest, checksum, threshold, feature schema and label provenance —
   explicitly not the same thing as the superficially similarly-named
   B2 training run already ruled out in the first pass.
9. Confirmed B1's manifest itself declares its threshold/QC fields as
   `"unconfirmed_placeholder"` / `-1` — an artifact-level admission that
   this manifest was never completed, not a gap introduced by lack of
   access.
10. Determined baseline execution remains blocked (same broken Python
    environment as the first pass; also no H5 input fixtures were
    supplied alongside the artifact directories to exercise a full
    prediction even if the environment worked). No pickle/joblib file
    was loaded, consistent with the HARD RULE boundary.
11. Updated `five-model-inventory.md`, `parity-and-rollout.md`, and
    both PR0165 project-memory files with all of the above.

## 20. Key Decisions Made During Implementation (continuation)

1. **Mapped directories to slots strictly by manifest `model_id`
   content, never by directory name.** This mattered concretely: the
   directory named `v0.2.0` is B3 (`bremen-v0-2-0-symmetry-candidate`),
   while the directory named `0.2.0-paper-reference` is B2
   (`bremen-paper-reference-v0-2-0`) — a naming scheme easy to
   misassign without reading the manifest content, exactly the mistake
   the task instructions warned against.
2. **Treated matching local checksums against prior "unverified lead"
   evidence (B1) as a promotion to "artifact-confirmed," not as a full
   live reconfirmation.** The local directory is still an externally
   supplied, read-only snapshot whose own provenance (when/how it was
   exported, whether it reflects what is live today) was not
   established in this session — so I did not claim "App Runner
   verification" or "live-confirmed" for any of the five, per the HARD
   RULES.
3. **Did not load any `.joblib` file.** All identity/checksum work used
   file-level hashing (`shasum`) and plain-text sidecar files only. This
   satisfies both the explicit HARD RULE and the general safety
   invariant that joblib must only be loaded through the existing
   checksum-verified controlled path — which this session's broken
   Python environment could not exercise safely anyway.
4. **Flagged B3's exploratory/unreviewed label status explicitly** as a
   safety carry-forward note, rather than only recording it as a
   technical fact, because `AGENTS.md`'s safety invariants and release-
   language rules require distinguishing validated from exploratory
   model status in any downstream documentation.
5. **Left `operations.md` unedited in this continuation** because the
   local-artifact evidence did not change any resource/feasibility fact
   (image size, concurrency, App Runner config) — only model identity
   and checksum facts, which belong in `five-model-inventory.md`.

## 21. Deviations From PLAN.md (continuation)

None beyond what the first pass already recorded. This continuation's
own task prompt narrowed the required outputs to updating
`INVENTORY_EVIDENCE.md`, `IMPLEMENTATION_REPORT.md`, and "the existing
IR-01 documentation only where the new artifact evidence changes or
confirms previous findings" — which is what was done
(`five-model-inventory.md` substantially, `parity-and-rollout.md`
lightly, `operations.md` not touched because nothing there changed).

## 22. Warnings / Unresolved Questions (continuation)

- The provenance of `/tmp/bremen-ir01-models` itself (export date,
  exporting process, whether it is guaranteed to match the artifacts
  the live service currently loads) was not established in this
  session — it was supplied as task input, not fetched by this agent
  from an authorized live source. Precommit-reviewer and any live-access
  holder should treat it as strong corroborating evidence, not as a
  substitute for a live catalog/App Runner check.
- B1 remains the least-documented of the five even with local artifact
  access: no feature schema, no model description, and its own
  manifest admits its threshold/QC fields are placeholders.
- No baseline execution was performed in this continuation either —
  same broken environment, plus no H5 fixtures were available alongside
  the artifact directories.
- B3's exploratory-label status (§19.8) must be carried into any future
  release metadata; this report flags it but does not itself gate or
  enforce that in code (out of scope — documentation/evidence only).

## 23. Validation Commands and Results (continuation)

```
$ git branch --show-current
0165-ir-01-five-model-inventory

$ git status --short   (precondition, before continuation edits)
?? .project-memory/agents/master_prompt.md
?? .project-memory/pr/0163-fix-validation-traces-and-standard-result-contract/
?? results/
?? testing_results/
```

(The first pass's own modified-file lines had already been reconciled
into the working tree per the prior IMPLEMENTATION_REPORT.md note that
no commit was made; `git status --short` at the very start of this
continuation turn showed only the three docs modified from the first
pass plus the same pre-existing untracked paths — consistent.)

Artifact-inspection commands (all read-only; exact output recorded in
`INVENTORY_EVIDENCE.md` §9):

```
find /tmp/bremen-ir01-models -type f -exec ls -la {} \;   (per directory)
cat <dir>/manifest.json                                    (all five)
shasum -a 256 <every file in all five directories>          (33 files)
cmp v0.2.0/model.joblib v0.2.0/bremen_mri_triage_symmetry_logreg_v0.2.0.joblib   -> identical
diff aramina_0_2_12-beta/{training_config,preprocess_and_train_config,preprocessing_config,model_description}.yaml \
     aramina_0_2_13-beta/{...}.yaml
cat <dir>/{model_description.yaml,feature_schema.json,metrics.json,label_mapping.json,container_requirements.json,training_config.yaml}
```

Post-edit validation, run from the repository root after all doc edits:

```
$ python -m compileall -q src tests
(eval):3: command not found: python
exit code: 127

$ python3 -m compileall -q src tests
(no output)
exit code: 0
```

Result: **PASS** (no `src`/`tests` file touched by this continuation
either).

```
$ git diff --check
(no output)
exit code: 0
```

Result: **PASS**.

```
$ git status --short
 M docs/inference-releases/five-model-inventory.md
 M docs/inference-releases/operations.md
 M docs/inference-releases/parity-and-rollout.md
?? .project-memory/agents/master_prompt.md
?? .project-memory/pr/0163-fix-validation-traces-and-standard-result-contract/
?? .project-memory/pr/0165-ir-01-five-model-inventory/
?? results/
?? testing_results/
```

Matches §18 exactly; no file from `/tmp` appears.

```
$ git diff --stat
 docs/inference-releases/five-model-inventory.md | 200 +++++++++++++++++++++---
 docs/inference-releases/operations.md           |  41 +++++
 docs/inference-releases/parity-and-rollout.md   |  23 +++
 3 files changed, 246 insertions(+), 18 deletions(-)
```

(`operations.md`'s and `parity-and-rollout.md`'s line counts include
both the first pass's and this continuation's edits, since both passes
are part of the same uncommitted working-tree diff; only the
`parity-and-rollout.md` precision-note paragraph and the full
`five-model-inventory.md` rewrite are new in this continuation.)

```
$ git rev-parse --verify HEAD
16d6f28f7e7f557e1ada55e8cdb30a1dded17913
```

Unchanged — confirms no commit was made in this continuation.

## 24. Safety Checks (continuation)

- Secrets/forbidden-pattern scan on the diff (same three files):
  `git diff -- <files> | grep -iE "AKIA|SECRET_ACCESS_KEY|dkr\.ecr|/Users/|/home/"` →
  **no matches**.
- No `.joblib` file, raw pickle bytes, or H5 content was copied into the
  repository or quoted in the updated docs — only SHA256 hex digests
  and plain-text YAML/JSON field values already designed to be
  non-sensitive provenance metadata (model names, thresholds, feature
  names, training metrics).
- No patient data was introduced — the artifact sidecar files inspected
  contain training-time aggregate metrics and feature-contract metadata
  only, no raw measurement or patient-identifying content.
- Confirmed via `git status --short` that no file from
  `/tmp/bremen-ir01-models` was staged or copied into the repository.

## 25. Boundaries Preserved (continuation)

- Only the three allowed docs and the two PR0165 project-memory files
  were changed — same ALLOWED CHANGES list as the first pass.
- No model artifact was modified (all `/tmp` files are untouched,
  outside git, read-only inputs).
- No `.joblib`/pickle file was loaded/deserialized — only hashed and
  diffed as plain files, per the HARD RULE.
- No claim of App Runner verification is made anywhere in the updated
  docs — every new claim is explicitly scoped to "local artifact
  evidence" or "repository evidence," with live re-confirmation
  recorded as still outstanding.
- No model mapping is asserted without artifact evidence — every
  directory→slot mapping cites the manifest's own `model_id` field.
- No unresolved issue was hidden: B1's documentation gap, B3's
  exploratory-label status, the broken local Python environment, and
  the unestablished provenance of `/tmp/bremen-ir01-models` are all
  explicitly recorded as open items (§22, and `INVENTORY_EVIDENCE.md`
  §9.2).

## 26. IR-01 Gate Status (continuation): **still BLOCKED**

This continuation substantially advances the inventory (full checksum
resolution for all five; B3 confirmed real and distinct; B1's
documentation gap now explicitly artifact-confirmed rather than merely
suspected) but does not clear the full gate:

| Requirement | Status after continuation |
|---|---|
| All five identities resolved | Strengthened — now corroborated by local artifact manifests, not just repeated historical catalog captures. Still not a live-today re-confirmation. |
| All five artifact hashes resolved | **Yes, from local artifact evidence** — all five SHA256 values now known and self-consistent with their own manifests. Not yet independently confirmed against the live S3 objects. |
| Baseline success/failure outputs reproducible | Unchanged from first pass — no new execution was run (environment broken, no H5 fixtures) |
| Preprocessing mappings explicit | Strengthened for A1/A2 — now artifact-declared, not only single-fixture-evidenced |
| Resource/cost limits reviewed | Unchanged — no live measurement; this continuation is model-identity evidence only |
| B3 real-vs-catalog-only question | **Resolved — confirmed real and distinct** |

Given live re-confirmation and resource/cost review remain outstanding,
and baseline execution has still never been run in this environment,
the gate remains **BLOCKED**, not PASS — but the remaining path to PASS
is now materially shorter and narrower (live re-confirmation + resource
measurement + one execution run), as detailed in
`INVENTORY_EVIDENCE.md` §10.

## 27. Blockers and Required Access (continuation — supersedes §12 where narrower)

1. Live S3 catalog / App Runner access, to confirm today's catalog and
   the live artifacts' identity match this local snapshot.
2. A working Python environment (`numpy`/`h5py` installed, or the
   project `venv` restored) plus H5 input fixtures, to run at least one
   real prediction per model through the existing controlled
   model-loading path (not a direct pickle load) and compare against
   the already-recorded baseline outputs.
3. B1's feature schema / real threshold source — still undocumented
   anywhere, local or repository.
4. Independent confirmation of `/tmp/bremen-ir01-models`'s provenance
   (export date/process/authorization) from whoever supplied it.
5. Actual production App Runner CPU/memory/concurrency configuration —
   unaffected by this continuation, still outstanding.

## 28. Commit Readiness (continuation)

Blocked — same reasoning as §14: the IR-01 gate itself is still
BLOCKED pending live access and execution evidence, even though this
continuation substantially reduces the remaining gap (especially for
checksums and the B3 question). The documentation changes are
internally consistent, cite real local evidence, and are within the
approved scope; they are ready for precommit review as an accurate,
more-complete record of a still-blocked gate.

## 29. Recommended Next Action (continuation — superseded by §40)

Proceed to precommit review. The precommit-reviewer should additionally
confirm, beyond §15's original checks: (e) every local-artifact
checksum/threshold/feature claim in this continuation traces to the
exact commands recorded in `INVENTORY_EVIDENCE.md` §9 (the reviewer
cannot re-run them against `/tmp/bremen-ir01-models` unless that same
local evidence is still present in their environment — note this
dependency explicitly rather than assuming it); (f) no `.joblib` file
was copied into git or committed anywhere; (g) the B3
"exploratory-label, not clinically reviewed" safety note is preserved
verbatim in the final document, not summarized away.

---

# Continuation 2: real local baseline execution (2026-10-21)

## 30. Task Completed (continuation 2)

`0165-ir-01-local-baseline-execution` — run a real local baseline
matrix against the five model packages at `/tmp/bremen-ir01-models` and
49 real H5 smoke fixtures at `/tmp/bremen-ir01-fixtures/v0.1`, through
the existing controlled Bremen/Aramina runtime, and classify every
result honestly (success, expected failure, or unexpected failure).

## 31. Branch / HEAD (continuation 2)

Branch: `0165-ir-01-five-model-inventory` (unchanged). HEAD before and
after: `16d6f28f7e7f557e1ada55e8cdb30a1dded17913` (no commit made).

## 32. Files Changed (continuation 2)

Modified further:

- `docs/inference-releases/five-model-inventory.md` (added "Real local
  baseline execution" section; updated the Gate Record table's "Local
  parity status" column to `passed` for all five, with evidence links;
  updated "What remains blocked")
- `docs/inference-releases/parity-and-rollout.md` (added a short
  cross-reference paragraph to the new baseline execution evidence)
- `docs/inference-releases/operations.md` — **not changed in this
  continuation** (no new resource/feasibility fact was established;
  local execution timing is explicitly not resource/cost evidence)

Created:

- `.project-memory/pr/0165-ir-01-five-model-inventory/FIXTURE_INVENTORY.md`
- `.project-memory/pr/0165-ir-01-five-model-inventory/BASELINE_EXECUTION.md`

Updated:

- `.project-memory/pr/0165-ir-01-five-model-inventory/INVENTORY_EVIDENCE.md`
  (added §10 "Real local baseline execution pass," §11 "What the
  baseline execution pass did NOT do," renumbered the final
  instructions section to §12, and amended its item 3/4/6 to reflect
  what is now resolved)
- `.project-memory/pr/0165-ir-01-five-model-inventory/IMPLEMENTATION_REPORT.md`
  (this section)

No `src/`, `tests/`, `Dockerfile`, `.github/`, `infra/`,
`pyproject.toml`, or `requirements.txt` file was changed. No file from
`/tmp/bremen-ir01-models` or `/tmp/bremen-ir01-fixtures` was copied
into the repository — confirmed by `git status --short` (§36).

## 33. Work Completed (continuation 2)

1. **Resolved the Python 3.13 blocker properly**, per this task's own
   permitted fallback ("use a temporary environment outside the
   repository if a valid Python 3.13 interpreter is available"): found
   `uv` already installed on this machine, ran `uv python install 3.13`
   to obtain a genuine standalone CPython 3.13.12 outside the
   repository, built a disposable venv from it, and installed the
   repository's own `pyproject.toml` dependencies into that venv by
   reading (never editing) that file. The full repository `pytest`
   suite (3975 tests) now passes (0 failed) under this environment —
   confirming the previously reported "broken environment" blocker
   from the first two passes was specific to this machine's existing
   `venv`/system `python3`, not to the repository's code.
2. **Diagnosed and resolved, for this session only, a real
   preprocessing-dependency-provenance mismatch**: Bremen's raw-H5
   preprocessing worker hard-validates the installed `xrd-preprocessing`
   package against an exact pinned git commit
   (`45d5568248e9774b7938a36e028d80e72b130b19`). Installing by the git
   *tag* `v0.1.7-beta` (the normal approach) resolved to a *different*
   commit on this date. Installed the exact commit SHA instead (itself
   a value already present in the B2 artifact's own embedded
   provenance metadata) in a separate disposable venv, which resolved
   it. No repository file was edited to do this; this is a finding
   about external tag/commit drift, not a code fix.
3. Built two further disposable preprocessing venvs (xrd-preprocessing
   `v0.1.7-beta` and `v0.1.9-beta` by tag — no provenance-pin check
   exists for Aramina's preprocessing worker, so the tag-based install
   worked directly) and set the three existing
   `BREMEN*_PREPROCESS*_PYTHON` environment variables to point at them,
   mirroring exactly what the Dockerfile's three dedicated venvs do in
   production.
4. **Ran 91 real executions** (63 Bremen across 21 fixtures, 28 Aramina
   across 7 fixtures × 2 target sides) using *only* existing, unmodified
   controlled entry points:
   `bremen.model_packages_bridge.load_staged_artifact` /
   `aramina_v0213.inference._load_selected_artifact` (checksum-then-load,
   invoked internally by the existing code, never a raw
   `joblib.load` on arbitrary bytes), `bremen.platform.runtime.registry.
   bremen_descriptor`/`aramina_descriptor`, a locally-populated
   `bremen.platform.models.registry.RegistryModelEntry` (a plain
   dataclass, populated the same way the real S3-backed registry
   populates it, with `_artifact_path`/`_checksum` pointed at the local
   files), and the existing top-level
   `bremen.platform.runtime.executor.execute(request, registry=...)`
   orchestration — the same function the real job service calls.
5. Recorded every result's model_id/version/checksum, fixture,
   patient/target_side, execution_status, typed error/failure_stage,
   probability/threshold/decision where produced, and duration — see
   `BASELINE_EXECUTION.md`.
6. Classified every one of the 41 non-completed runs into an existing,
   already-defined safe failure category (no new categories invented):
   `qc_rejection` (the documented `raw_peak_gate_failed` gate),
   `preprocessing_failure` (both Aramina's
   `ARAMINA_UNSUPPORTED_INPUT`/`preprocessing_contract` and Bremen's
   generic `invalid_scientific_profiles`, with two representative
   sub-causes root-caused by direct worker invocation),
   `feature_schema_failure` (post-preprocessing
   `requires_exactly_3_left_3_right` shape gate), `patient_identity_mismatch`
   (`h5_patient_contract`), and `input_incompatible`
   (`normalization_failed`). Zero results fell outside these categories;
   zero unexpected exceptions occurred.
7. Cross-confirmed two results against already-existing evidence rather
   than treating them as new, unverifiable numbers: B2 on
   `benign_one_patient.h5` exactly reproduces the PR0160 golden
   reference (`0.7726940329943811`); A1/A2 on
   `eoscloud-staging/cabce03d-...h5` exactly reproduce the captured
   production result already on disk at
   `results/post0161-prod-smoke-20260917-163154/detail-aramina-success-nova214-left.json`.
8. Explicitly did **not** invent a threshold for B1: confirmed by
   direct execution that the runtime reads B1's real threshold from
   inside the joblib artifact, not from the manifest's
   `"unconfirmed_placeholder"` field.
9. Recorded one real, repository-independent cross-model finding:
   `Nova_103_.h5` (legacy `detector_scoped_v1` layout) is accepted by
   B1 (legacy canonical adapter) but rejected by B2/B3 (raw-container
   pipeline's declared `unsupported_legacy_layouts`) and by A1/A2
   (canonical patient-identity check) — the five variants do not share
   one input-layout compatibility contract today. This is recorded as
   an inventory fact for IR-02+; no behavior was changed.
10. Performed H5 structural discovery for all 49 fixtures (identity,
    side counts, patient-grouping, the known `AlexSynthetic_001/002.h5`
    → `Nova_376` identity-sharing finding, and the `Nova_103_.h5`
    legacy-layout finding) — recorded in `FIXTURE_INVENTORY.md`, using
    only HDF5 structural attribute reads (`h5py.File(...).attrs`), never
    the Bremen/Aramina scientific runtime, for the discovery phase.

## 34. Key Decisions Made During Implementation (continuation 2)

1. **Provisioned Python 3.13 via `uv` rather than declaring the gate
   permanently blocked on environment grounds.** The task explicitly
   permits this ("if a valid Python 3.13 interpreter is available");
   none was initially available, so one was obtained the same way the
   task's own language anticipates — outside the repository, with no
   dependency file edited. This was judged clearly within scope rather
   than "redesigning the runtime," since it only provisions an
   interpreter and installs already-declared dependencies.
2. **Investigated and fixed the preprocessing-subprocess dependency
   mismatch by installing the exact pinned commit SHA**, rather than
   stopping at the first failure or working around the check. The
   commit SHA used was not invented — it was already present, verbatim,
   in the B2 artifact's own `prediction_preprocessing_yaml`
   (`provenance.upstream_xrd_preprocessing_commit`), so using it is
   using the artifact's own declared provenance, not bypassing a safety
   check.
3. **Diagnosed two representative failure sub-causes by directly
   invoking the existing worker script/function** (not by writing new
   inference logic) — the same technique already used in the prior
   continuation to diagnose the `BREMEN_PREPROCESS_PYTHON` environment
   issue. This was judged acceptable because it only *calls* existing
   code more directly to read its own existing (already-written) safe
   diagnostic output, rather than adding new diagnostic code.
4. **Sampled a representative 91-run matrix rather than an exhaustive
   245-run (49×5) sweep**, per the task's explicit instruction not to
   force every fixture through every model when unnecessary, and using
   the patient-identity de-duplication already established in
   `FIXTURE_INVENTORY.md` to avoid redundant same-patient runs.
5. **Did not attempt to "fix" any of the 41 typed failures.** Every one
   is reported as observed; none triggered a change to model, runtime,
   or preprocessing code, per the HARD RULES (no new inference logic,
   no scientific-logic changes, no runtime redesign).
6. **Left `docs/inference-releases/operations.md` unedited** in this
   continuation specifically because local execution duration figures
   are not resource/cost/App-Runner evidence — editing that file with
   local timings would risk being read as such.

## 35. Deviations From PLAN.md (continuation 2)

None beyond what this task's own prompt specifies. This task's ALLOWED
FILES list is a subset of (and consistent with) the first pass's scope;
every file changed in this continuation is on that list.

## 36. Warnings / Unresolved Questions (continuation 2)

- The disposable environments created in `/tmp` for this pass
  (`bremen-ir01-exec-venv`, `bremen-ir01-preprocess-017`, `-017b`,
  `-019`, `bremen-ir01-h5meta-venv`) are not committed and may not
  persist; reproducing this pass's results requires rebuilding them
  per the recipe in `BASELINE_EXECUTION.md`'s "Environment" section.
- The `xrd-preprocessing` `v0.1.7-beta` tag/commit mismatch is a real,
  external finding that this task cannot and must not fix (no
  dependency file was edited); it is flagged for the owner of that
  separate repository.
- Not every one of the 41 typed failures was individually root-caused
  to its specific underlying exception — two representative cases were
  diagnosed in depth; the remainder are recorded at the safe-category
  level only, consistent with the runtime's own intentional
  error-sanitization design.
- `/tmp/bremen-ir01-fixtures` and `/tmp/bremen-ir01-models`'s own
  provenance (who produced them, when, how) remains unestablished in
  this session, same caveat as the prior continuation.

## 37. Validation Commands and Results (continuation 2)

```
$ git branch --show-current
0165-ir-01-five-model-inventory

$ git rev-parse --verify HEAD
16d6f28f7e7f557e1ada55e8cdb30a1dded17913

$ git status --short   (precondition, before this continuation's edits)
?? .project-memory/agents/master_prompt.md
?? .project-memory/pr/0163-fix-validation-traces-and-standard-result-contract/
?? results/
?? testing_results/
```

Baseline-execution-harness commands (full detail and output in
`BASELINE_EXECUTION.md`):

```
uv python install 3.13
/.../cpython-3.13.12-.../bin/python3.13 -m venv /tmp/bremen-ir01-exec-venv
/tmp/bremen-ir01-exec-venv/bin/python -m pip install --quiet "."   # from repo root
/tmp/bremen-ir01-exec-venv/bin/python -m pip install --quiet pytest pytest-cov httpx
# three more disposable venvs for the pinned xrd-preprocessing releases (see BASELINE_EXECUTION.md)
BREMEN_PREPROCESS_PYTHON=... BREMEN_ARAMINA_PREPROCESS_PYTHON=... BREMEN_ARAMINA_PREPROCESS_019_PYTHON=... \
  /tmp/bremen-ir01-exec-venv/bin/python <baseline harness script, outside repo>
  -> 91 JSON records, 50 completed, 41 typed failures, 0 unexpected exceptions, exit code 0
```

Post-edit validation, from the repository root:

```
$ python -m compileall -q src tests
(eval):3: command not found: python
exit code: 127

$ python3 -m compileall -q src tests      # system python3, no deps
(no output)
exit code: 0

$ /tmp/bremen-ir01-exec-venv/bin/python -m compileall -q src tests   # working Python 3.13 + full deps
(no output)
exit code: 0

$ /tmp/bremen-ir01-exec-venv/bin/python -m pytest -q
3975 passed, 8 skipped, 40 warnings in 22.32s
exit code: 0
```

**This is the authoritative, passing `pytest` result for this task** —
run with real dependencies under a genuine Python 3.13 interpreter, not
filtered, not a historical result. It supersedes the "broken
environment, pytest unusable" finding recorded in the first two IR-01
passes for the purpose of *this* validation requirement (the repo's own
`venv` remains broken and unrelated to this change, as before).

```
$ git diff --check
(no output)
exit code: 0

$ git status --short
 M docs/inference-releases/five-model-inventory.md
 M docs/inference-releases/operations.md
 M docs/inference-releases/parity-and-rollout.md
?? .project-memory/agents/master_prompt.md
?? .project-memory/pr/0163-fix-validation-traces-and-standard-result-contract/
?? .project-memory/pr/0165-ir-01-five-model-inventory/
?? results/
?? testing_results/

$ git diff --stat
 docs/inference-releases/five-model-inventory.md | 233 ++++++++++++++++++++++--
 docs/inference-releases/operations.md           |  41 +++++
 docs/inference-releases/parity-and-rollout.md   |  37 ++++
 3 files changed, 293 insertions(+), 18 deletions(-)
```

(`operations.md`'s line count is unchanged from the prior continuation
— confirmed no new edits were made to it in this pass.)

```
$ git rev-parse --verify HEAD
16d6f28f7e7f557e1ada55e8cdb30a1dded17913
```

Unchanged — no commit was made.

## 38. Safety Checks (continuation 2)

- Secrets/forbidden-pattern scan on the diff:
  `git diff -- <3 changed files> | grep -iE "AKIA|SECRET_ACCESS_KEY|dkr\.ecr|/Users/|/home/"` →
  **no matches**.
- No `.h5` or `.joblib` byte content, raw measurement array, or free-text
  clinical field (age, race/ethnicity, biopsy narrative, BI-RADS
  subcategory) was copied into any committed file — `FIXTURE_INVENTORY.md`
  and `BASELINE_EXECUTION.md` reuse only identifiers
  (`Nova_NNN`, `BENIGN`/`ATYPICAL`/`CANCER`) and numeric outputs already
  of the same kind as what is already committed in
  `docs/production-contracts-2026-09-18.md` and the `results/`/
  `testing_results/` evidence files.
- Confirmed via `git status --short` that no `/tmp/bremen-ir01-models`
  or `/tmp/bremen-ir01-fixtures` file was staged or copied into the
  repository.
- No `src/`, `tests/`, `Dockerfile`, `.github/`, `infra/`,
  `pyproject.toml`, or `requirements.txt` file was touched.
- No raw pickle/joblib was loaded outside the existing controlled
  boundary — verified by code-reading
  (`load_staged_artifact`/`_load_selected_artifact` are the only
  deserialization call sites exercised) rather than merely asserted.

## 39. Boundaries Preserved (continuation 2)

- Only the files listed in §32 were changed, matching this task's
  ALLOWED FILES list exactly.
- No model artifact was modified (all `/tmp` inputs remain untouched,
  read-only, outside git).
- No new inference logic was written; every execution used existing,
  unmodified entry points (`execute`, `bremen_descriptor`,
  `aramina_descriptor`, `RegistryModelEntry`, `load_staged_artifact`,
  `_load_selected_artifact`).
- No App Runner verification is claimed anywhere in the updated docs;
  every new claim is explicitly scoped to "local execution."
- No model mapping or numeric claim is asserted without execution or
  citation evidence — every success/failure record traces to the raw
  JSON output file described in `BASELINE_EXECUTION.md`.
- No failure was hidden or reclassified as success; all 41 typed
  failures and their categories are reported plainly, and the one
  dependency-provenance workaround is disclosed rather than silently
  applied.

## 40. IR-01 Gate Status (continuation 2): **still BLOCKED**, materially advanced

| Requirement (per `.project-memory/pr/ir-01/PLAN.md`) | Status after this pass |
|---|---|
| All five identities/artifact hashes resolved | Unchanged from continuation 1 (resolved from local artifacts; live re-confirmation still pending) |
| Baseline success/failure outputs reproducible | **Yes, substantially** — 91 real executions, 50 completed, two bit-exact reproductions of pre-existing golden/production values, 41 cleanly typed failures, 0 unexpected |
| Preprocessing mappings explicit | **Yes, confirmed by execution** (not just artifact config) for A1→v0.1.7-beta / A2→v0.1.9-beta and B1/B2/B3→v0.1.7-beta |
| Resource/cost limits reviewed | **No** — still no live App Runner measurement; local execution timing is not a substitute |
| Live catalog/App Runner re-confirmation | **No** — unchanged, out of scope for a local session |

The gate remains **BLOCKED** because live catalog/App-Runner
re-confirmation and resource/cost review are still outstanding and
cannot be produced locally — but the scientific-baseline portion of the
gate is now substantially satisfied with real, reproducible evidence
rather than static metadata alone.

## 41. Blockers and Required Access (continuation 2 — supersedes §27 where narrower)

1. Live S3 catalog / App Runner access — unchanged, still required.
2. Actual production App Runner CPU/memory/concurrency configuration
   and cost measurement — unchanged, still required; local durations
   recorded in `BASELINE_EXECUTION.md` are not a substitute.
3. Confirmation that `/tmp/bremen-ir01-models` /
   `/tmp/bremen-ir01-fixtures` reflect what is currently live.
4. Resolution (by the `XRD-preprocessing` repository owner, not by this
   task) of the `v0.1.7-beta` tag/commit drift.
5. B3's clinical review status remains open regardless of execution
   evidence.

## 42. Commit Readiness (continuation 2)

Blocked — same reasoning as §14/§28: the IR-01 gate itself remains
BLOCKED pending live access and resource review, even though the
scientific-execution portion of the gate is now strongly evidenced. The
documentation changes in this continuation are internally consistent,
cite real, reproducible execution evidence, and are within the approved
scope; they are ready for precommit review as an accurate record of a
still-blocked-but-substantially-advanced gate.

## 43. Recommended Next Action (continuation 2 — final)

Proceed to precommit review. In addition to the checks listed in §15
and §29, the precommit-reviewer should: (h) spot-check at least one
probability/threshold value in `BASELINE_EXECUTION.md` against its
cited source file; (i) confirm the claim "0 unexpected exceptions
across 91 runs" by independently re-running the harness if the
disposable environments described in §37 can be reconstructed, or by
reviewing the raw JSONL output if it has been preserved; (j) confirm
the `xrd-preprocessing` tag/commit mismatch is reported as an external
finding, not as a change this task made to any dependency file; (k)
confirm the Gate Record table in `five-model-inventory.md` correctly
shows "Local parity: passed" but "App Runner parity: pending" for all
five, and that the overall IR-01 gate status is reported as BLOCKED,
not PASS.

---

# Continuation 3: precommit review fixes (2026-10-21)

## 44. Task Completed (continuation 3)

`0165-ir-01-review-fixes` — resolve the two precommit-review blockers
(B1: six wrong `catalog_timestamp` citations; B2: unsupported claim
that seven catalog captures are "independent") and harden local
artifact/fixture provenance wording, without redoing IR-01 or changing
any scientific/baseline finding.

## 45. Branch / HEAD (continuation 3)

Branch: `0165-ir-01-five-model-inventory` (unchanged). HEAD before and
after: `16d6f28f7e7f557e1ada55e8cdb30a1dded17913` (no commit made).

## 46. Reviewer Blockers Received

From `.project-memory/pr/0165-ir-01-five-model-inventory/reviews/precommit-review.yml`
(`VERDICT: block`):

- **B1 — "Catalog timestamp citations are factually wrong."**
  `INVENTORY_EVIDENCE.md` §1 reported each file's `last_discovery_at`
  field value under a `catalog_timestamp` header for six of seven
  rows (the seventh was correctly labeled `(last_discovery_at)` and
  not flagged by the reviewer).
- **B2 — "Independence of seven captures is not established."**
  The documents stated "seven independent production-catalog
  captures" as fact, with no capture-command/session/endpoint/request
  identifier in any of the seven files to support "independent."

## 47. Exact Corrections Made

1. **`INVENTORY_EVIDENCE.md` §1** — rewrote the evidence table to show
   each file's actual `catalog_timestamp` field value (re-verified
   directly against the JSON on disk with
   `python3 -c "import json; print(json.load(open(path))['catalog_timestamp'])"`
   for all seven files, including the previously-correct seventh row),
   plus `last_discovery_at` as a second, explicitly labeled column so
   the previously-recorded figures are preserved, not deleted. Added a
   "Corrected 2026-10-21" note documenting the mislabeling and the
   re-verification method.
2. **`INVENTORY_EVIDENCE.md` §1** — replaced "Seven independent
   production-catalog captures... reproduced identically seven times"
   with "Seven captured catalog snapshots, stored as separate JSON
   files... each contain an identical five-entry catalog listing," and
   added an explicit paragraph stating the seven files are not claimed
   to be independent observations, naming exactly what evidence is and
   is not present (distinct hashes/timestamps present; capture
   command/session/endpoint/request identifiers absent). The useful
   fact — that model identities and counts repeat consistently across
   all seven — is preserved verbatim.
3. **`IMPLEMENTATION_REPORT.md` §1** (first-pass work-summary item 1)
   — changed "seven independent production-catalog captures" to
   "seven separately stored catalog-listing captures" and added an
   inline correction note cross-referencing `INVENTORY_EVIDENCE.md` §1.
4. **`docs/inference-releases/parity-and-rollout.md`** — changed "two
   independent captured production executions" to "two captured
   production executions ... distinct `job_id`/`request_id` values
   roughly four hours apart, so each reflects a separately executed
   job rather than a duplicated static capture." This is a *weaker*,
   more precisely evidenced claim: it keeps the concrete fact
   (distinct job/request IDs, ~4 hour gap) that actually supports
   non-duplication, without asserting the broader word "independent."
5. **`INVENTORY_EVIDENCE.md` §9, `FIXTURE_INVENTORY.md`,
   `BASELINE_EXECUTION.md`** — added explicit provenance-caveat
   paragraphs describing `/tmp/bremen-ir01-models` and
   `/tmp/bremen-ir01-fixtures` only as **operator-supplied local
   copies**, stating plainly that export session, S3/source endpoint,
   authorization context, and immutable object-version identifiers
   were not captured, and explicitly distinguishing this from
   **artifact integrity** (SHA256 self-consistency against each
   artifact's own manifest, and cross-matches against other repository
   evidence), which remains independently verified and is not
   downgraded by these caveats.

## 48. Claims Intentionally Weakened

- "Seven independent production-catalog captures" → "seven captured
  catalog snapshots" / "seven separately stored ... captures" (no
  claim of independent sessions/sources).
- "Two independent captured production executions" → "two captured
  production executions" with the supporting job_id/request_id/time-gap
  detail kept explicit instead of the word "independent."
- Implicit assumption that `/tmp/bremen-ir01-models` /
  `/tmp/bremen-ir01-fixtures` are verified S3-sourced exports →
  explicitly described as operator-supplied local copies with
  unestablished export/session/authorization/object-version
  provenance.

**Not weakened** (per HARD RULE 6 and the explicit instruction to
distinguish integrity from provenance): the five local artifacts'
SHA256 self-consistency against their own manifests, their cross-matches
against independently-recorded repository evidence (catalog captures,
production executions, the historical PR0039 lead), the B3
real-vs-catalog-only resolution, the 91-run baseline execution matrix
and its two bit-exact reproductions of pre-existing golden/production
values, and the IR-01 BLOCKED gate status are all unchanged — none of
these were the subject of either blocker, and the task instructs not
to redo IR-01 or alter valid baseline findings.

## 49. Files Changed (continuation 3)

Modified:

- `.project-memory/pr/0165-ir-01-five-model-inventory/INVENTORY_EVIDENCE.md`
  (§1 timestamp table + independence wording; §9 provenance caveat)
- `.project-memory/pr/0165-ir-01-five-model-inventory/IMPLEMENTATION_REPORT.md`
  (§1 wording correction; this section)
- `.project-memory/pr/0165-ir-01-five-model-inventory/FIXTURE_INVENTORY.md`
  (provenance caveat added)
- `.project-memory/pr/0165-ir-01-five-model-inventory/BASELINE_EXECUTION.md`
  (provenance caveat added)
- `docs/inference-releases/parity-and-rollout.md` (independence wording
  softened for the B2 probability-pair claim)

Not changed in this continuation:
`docs/inference-releases/five-model-inventory.md`,
`docs/inference-releases/operations.md` — neither contained the flagged
timestamp table or "seven independent" wording, and neither needed a
provenance caveat beyond what they already carried (both already say
"not independently re-verified" / "not independently established" in
appropriately scoped contexts unrelated to the two blockers).

No `src/`, `tests/`, `infra/`, `Dockerfile`, `.github/`,
`pyproject.toml`, or `requirements.txt` file was touched. No file under
`/tmp/bremen-ir01-models/` or `/tmp/bremen-ir01-fixtures/` was read,
copied, or modified in this continuation — only already-recorded values
and the already-committed `results/`/`testing_results/` JSON files were
re-verified.

## 50. Validation Commands and Results (continuation 3)

```
$ git branch --show-current
0165-ir-01-five-model-inventory

$ git rev-parse --verify HEAD
16d6f28f7e7f557e1ada55e8cdb30a1dded17913

$ git status --short   (precondition)
 M docs/inference-releases/five-model-inventory.md
 M docs/inference-releases/operations.md
 M docs/inference-releases/parity-and-rollout.md
?? .project-memory/agents/master_prompt.md
?? .project-memory/pr/0163-fix-validation-traces-and-standard-result-contract/
?? .project-memory/pr/0165-ir-01-five-model-inventory/
?? results/
?? testing_results/
```

Timestamp re-verification (item 1 of the validation checklist) — exact
command and result for all seven files:

```
$ python3 -c "import json; d=json.load(open(path)); print(d['catalog_timestamp'], '|', d['last_discovery_at'])"
testing_results/results/evidence/pre0157-auth-check.json                      -> 2026-09-11T08:53:23.108255+00:00 | 2026-09-10T19:05:54.409789+00:00
results/post0158-live/models.json                                             -> 2026-09-16T12:05:41.863270+00:00 | 2026-09-16T11:59:06.107914+00:00
testing_results/results/live-2026-09-16/models.json                           -> 2026-09-16T11:20:47.419705+00:00 | 2026-09-16T10:51:29.531646+00:00
results/post0158a-live/models.json                                            -> 2026-09-16T13:41:53.960056+00:00 | 2026-09-16T13:34:17.511732+00:00
results/live-pr0160-smoke/models.json                                         -> 2026-09-17T11:05:29.272081+00:00 | 2026-09-17T10:36:17.879908+00:00
results/all-patients-model-matrix-20260917-121431/models.json                 -> 2026-09-17T11:14:44.731223+00:00 | 2026-09-17T10:36:17.879908+00:00
results/post0161-prod-smoke-20260917-163154/models.json                       -> 2026-09-17T15:31:49.268596+00:00 | 2026-09-17T15:11:50.540690+00:00
```

Every value exactly matches both the reviewer's quoted corrections (B1)
and the new table in `INVENTORY_EVIDENCE.md` §1.

Item 2 — search for "independent" and unsupported provenance wording
across all five changed files: performed with
`grep -n "independent" <files>`. Remaining occurrences were individually
reviewed; each refers to one of (a) independently-computed checksums,
(b) cross-matches against separately-sourced repository evidence
(genuinely distinct source types: package manifest vs. docs vs.
production capture), (c) explicit *negative* statements ("not
independently confirmed/established/re-verified"), or (d) fixture
patient-identity analysis unrelated to catalog captures (the
`AlexSynthetic`/`Nova_376` "not independent patients" finding). None of
the remaining occurrences assert that the seven catalog captures, or
the `/tmp` directories' source provenance, are independently
established — the two specific claims the reviewer flagged are the
only ones changed.

```
$ git diff --check
(no output)
exit code: 0

$ git status --short
 M docs/inference-releases/five-model-inventory.md
 M docs/inference-releases/operations.md
 M docs/inference-releases/parity-and-rollout.md
?? .project-memory/agents/master_prompt.md
?? .project-memory/pr/0163-fix-validation-traces-and-standard-result-contract/
?? .project-memory/pr/0165-ir-01-five-model-inventory/
?? results/
?? testing_results/

$ git diff --stat
 docs/inference-releases/five-model-inventory.md | 233 ++++++++++++++++++++++--
 docs/inference-releases/operations.md           |  41 +++++
 docs/inference-releases/parity-and-rollout.md   |  39 ++++
 3 files changed, 295 insertions(+), 18 deletions(-)
```

(`five-model-inventory.md` and `operations.md` line counts are
unchanged from the prior continuation — confirming this pass made no
edits to them. `parity-and-rollout.md` grew by 2 lines from the prior
continuation's 37, reflecting only the independence-wording edit in
§47 item 4.)

`git diff` (full) was reviewed manually for every changed tracked
file; only the intended wording/table changes are present — no
scientific value, checksum, threshold, or gate-status figure was
altered.

```
$ git rev-parse --verify HEAD
16d6f28f7e7f557e1ada55e8cdb30a1dded17913
```

Unchanged — no commit was made.

## 51. Safety Checks (continuation 3)

- Secrets/forbidden-pattern scan on the diff:
  `git diff -- docs/inference-releases/parity-and-rollout.md | grep -iE "AKIA|SECRET_ACCESS_KEY|dkr\.ecr|/Users/|/home/"` →
  no matches.
- No `src/`, `tests/`, `infra/`, `Dockerfile`, `.github/`,
  `pyproject.toml`, or `requirements.txt` file was touched (confirmed
  by `git status --short` above).
- No file under `/tmp/bremen-ir01-models/` or
  `/tmp/bremen-ir01-fixtures/` was read or modified in this
  continuation.
- No new patient data, credentials, or raw artifact content was
  introduced — this pass only corrected timestamp citations and
  wording.

## 52. Boundaries Preserved (continuation 3)

- Only the five files listed in §49 were changed, exactly matching
  this task's ALLOWED FILES list.
- No scientific result, model artifact, or runtime code was changed —
  confirmed: every edit in this continuation is a timestamp correction
  or a wording/caveat change; no probability, threshold, checksum,
  feature count, or execution-status value from the prior passes was
  altered.
- No new baseline runs were performed; no AWS access was attempted; no
  IR-02 work was done; no provenance was fabricated to fill the gaps
  the reviewer identified — per HARD RULE 5, the unsupported claims
  were weakened instead.
- The IR-01 gate status remains reported as **BLOCKED** throughout;
  this continuation did not and does not change that status.

## 53. Request for Precommit Re-Review

Both blockers (B1, B2) are corrected as described in §47, and the
related local-artifact/fixture provenance wording is hardened per the
task's LOCAL ARTIFACT PROVENANCE instructions. **Requesting a fresh
precommit review** of
`.project-memory/pr/0165-ir-01-five-model-inventory/` and the three
changed `docs/inference-releases/` files. The precommit-reviewer should
independently re-verify: (a) all seven `catalog_timestamp` values
against the source JSON files listed in §50; (b) that no remaining
text in the five changed files asserts the seven catalog captures, or
the `/tmp` directories' source provenance, to be independently
established; (c) that artifact integrity findings (checksum
self-consistency, B3 distinctness, the 91-run baseline matrix) remain
unchanged from the prior precommit-reviewed version, since they were
not part of either blocker.
