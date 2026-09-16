# PRECOMMIT_REVIEW.md — PR0159 (focused metadata-ownership review)

HEAD: `5d4f34e1627030a8523ed8ee4e199b3c49f81056` · snapshot `2026-09-16T18:23:42Z`
Staging area empty; review covers working-tree diff + new files only.

FOCUSED QUESTION: Does the diff produce Standard Result metadata from
model-package-owned adapters, transport it via the normalized RuntimePrediction
contract, and consume it generically in the mapper — without new model-specific
H5/scientific interpretation in generic platform code? **Yes.** All six checks pass.

---

## 1. PACKAGE OWNERSHIP — PASS
- `ls src/bremen/api/h5_source_metadata.py` → No such file. `git ls-files` → not tracked. Confirmed gone.
- New H5 parsing lives only in `src/bremen/model_packages/bremen_v01/source_metadata.py` and
  `.../aramina_v0213/source_metadata.py` (untracked new files, correct paths).
- No API file gained a metadata H5 parser: `git diff -- src/bremen/api | grep '^+' | grep -i h5py` → none;
  no `producer_version`/`backfill_provenance`/`/session`/`operator_username` references appear in any added
  line of the six generic/transport files.
- (Note only: a stale `src/bremen/api/__pycache__/h5_source_metadata.cpython-313.pyc` remains, but `__pycache__/`
  is gitignored and not part of the PR — non-blocking.)

## 2. NORMALIZED TRANSPORT — PASS
- `model_runtime.py` adds frozen dataclasses `SourceMetadata` / `ModelMetadata` / `ModelMetrics` and three
  `RuntimePrediction` fields defaulting to empty (`source_metadata`/`model_metadata`/`model_metrics`).
- Package runtimes attach the contract: `bremen_v01/runtime.py` and `aramina_v0213/runtime.py` populate the
  three fields from their own adapters; `aramina_v0213/inference._run_local_artifact` returns
  `(report, source_metadata, model_metadata, model_metrics)`.
- Providers forward verbatim only: `workflow_bremen.py` / `workflow_aramina.py` add
  `prediction.source_metadata.to_dict()` etc. to the payload (translation, no parsing).

## 3. GENERIC MAPPER — PASS
- `model_result_mapper.py` reads only canonical keys `source_metadata` / `model_metadata` / `model_metrics`
  from `result_summary` (via `_clean_age`, `_clean_eoscan_version`, `_clean_metrics`).
- It knows no `/session` path, `producer_version`, `backfill_provenance`, artifact metric paths, or model
  feature names — `grep` of mapper/standard_model_result/model_runtime for those tokens → zero matches;
  `test_mapper_consumes_only_normalized_names` asserts the same and passes.
- `eoscan_version` correctly typed `str | None` (`standard_model_result.py:79`), absence → `None`.

## 4. EOSCAN PROVENANCE — PASS
- Both adapters hard-set `eoscan_version=None` (`bremen_v01/source_metadata.py:80`,
  `aramina_v0213/source_metadata.py:88`). Neither `producer_version` nor `schema_version` is mapped to
  `eoscan_version` (the only textual mentions are docstring/comments explaining the deliberate non-mapping).
- No alternate guessed alias introduced. Field is not required non-null; `None` is the correct representation.

## 5. MODEL METRIC PROVENANCE — PASS
- Bremen reads metrics from the active package's `final_fit_training_metrics`; Aramina reads from the active
  artifact's `model_performance.held_out_metrics.*.mean`. Both from the loaded package/artifact object.
- `grep` of metric literals (`0.9516129032258065`/`0.391304347826087`/`0.8175`/`0.3763`) → no matches in
  `src/` (they appear only as synthetic test-fixture inputs, then asserted for source→canonical equality).
  No Bremen `0.2.0-research` or Aramina `0.2.12` constants are copied/hardcoded.
- Missing values → `None` (verified by `test_bremen_model_metrics_absent_is_none`,
  `test_aramina_model_metrics_never_hardcoded_from_other_version`).

## 6. ORCHESTRATOR H5 PATH — PASS
- The only PR0159 change in `workflow_orchestrator.py` passes the already-staged `h5_path` into the Bremen
  provider (`provider.execute(canonical, context, h5_path=h5_path)`) with `TypeError` fallbacks; it does not
  interpret model-specific H5 metadata in the added lines. Pre-existing `h5py` use elsewhere in the file is
  out of scope per instructions.

---

## Blockers
None. No concrete violation in the current diff.

## Commands actually run
```
git rev-parse --verify HEAD
git status --short
ls / git ls-files  → src/bremen/api/h5_source_metadata.py absent
git diff -- src/bremen/api src/bremen/model_runtime.py  (added-line token scan: no h5py/H5-metadata tokens)
grep -n "eoscan_version=None"  (both adapters)
git diff -- src/bremen/api/workflow_orchestrator.py
./venv/bin/python -m pytest -q tests/test_bremen_package_metadata_adapters_pr0159.py \
    tests/test_bremen_standard_result_metadata_pr0159.py   → 29 passed
git diff --check   → clean (exit 0)
```

## Out-of-scope notes (not blocking PR0159; carry to PR0160)
- `docs/standard_model_result_contract_v1.md` still shows `eoscan_version: ""` while the implementation now
  emits `null`; `workflow_runs.result_summary` gains three additive transport keys. These are documentation
  gaps, not ownership-boundary violations, and are out of scope for this focused decision.

READY FOR COMMIT
