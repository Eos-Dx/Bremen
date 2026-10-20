# FIXTURE_INVENTORY.md — IR-01 local smoke-fixture inventory

Source: `/tmp/bremen-ir01-fixtures/v0.1` (49 files, ~318 MB, external
read-only input per task HARD RULES — not copied into git). All H5
content below was read structurally only (HDF5 group/attribute
introspection: `h5py.File(path, "r")`, `.attrs`, `.keys()`), never
through the Bremen/Aramina scientific runtime, and never by dumping raw
measurement arrays. No H5 file, patient free-text, or raw metadata is
reproduced verbatim here beyond identifiers and counts already used
elsewhere in this repository's committed evidence (e.g. `Nova_227`,
`benign_one_patient.h5`, `BENIGN`/`ATYPICAL`/`CANCER` labels already
appear in `docs/production-contracts-2026-09-18.md`).

**Provenance caveat (added 2026-10-21, precommit review):** this
directory is described here only as an **operator-supplied local
copy**, understood to originate from the project's H5 source storage
but not independently confirmed as such in this session. No export
session, endpoint, request/authorization metadata, or object-version
identifier was captured alongside it to establish when, how, or from
which exact source snapshot it was produced. The internal-identity
findings below (resolved `patientId`/`specimenId` values, structural
layout, side counts) are read directly from the file bytes present on
disk and are accurate descriptions of *this local copy's content*;
they are not a claim about its chain of custody from any live system.

## Tooling note (environment boundary)

HDF5 structural introspection required `h5py`, which is not installed
in this repository's (broken) `venv` or in the system `python3`. A
disposable virtual environment was created **outside the repository**,
at `/tmp/bremen-ir01-h5meta-venv`, using the system `python3` (3.14),
solely to run `h5py.File(...).attrs`/`.keys()` calls — plain HDF5
container/attribute reads, not Bremen/Aramina scientific code, not
model loading, not inference. No dependency file in this repository was
edited to create or use this environment. This is distinct from, and
does not substitute for, the Python 3.13 Bremen runtime needed for
actual baseline execution (see `BASELINE_EXECUTION.md`).

Commands used (full list; also recorded in `IMPLEMENTATION_REPORT.md`):

```
find /tmp/bremen-ir01-fixtures/v0.1 -type f -name "*.h5" | sort   # -> 49 files
python3 -m venv /tmp/bremen-ir01-h5meta-venv
/tmp/bremen-ir01-h5meta-venv/bin/pip install --quiet h5py
shasum -a 256 <each of the 49 .h5 files>
<local h5py script>  # reads f.attrs, f["session"].attrs, f["session/sample"],
                      # f["session/sets"][*].attrs only — no array data read
```

## Discovery summary

- 49 files total: 11 at the fixture root, 9 under `eoscloud-dev/`, 29
  under `eoscloud-staging/`.
- 48 of 49 use the expected `session` root group
  (`schema_version: "0.3"`, `format: "xrd-session"` where present at
  root, or structurally equivalent per-file).
- **1 file, `Nova_103_.h5`, does NOT use the `session` layout at all.**
  Its single top-level group is named
  `SILVER_1_2025-02-06_720mm`, and that group's own attribute is
  `layout_version: "detector_scoped_v1"`. This string is an **exact,
  literal match** for the `unsupported_legacy_layouts` entry declared in
  every Bremen model's `container_requirements.json` (B1, B2, B3 all
  declare `"unsupported_legacy_layouts": ["detector_scoped_v1"]`). This
  is a confirmed, contract-level incompatibility — no execution was
  needed to determine it (see "input incompatible" in
  `BASELINE_EXECUTION.md`).
- Do not manually assume filename ⇒ patient identity (per task
  instruction). This was verified file-by-file via
  `session/sample/patient_name` (a dataset, not an attribute) and
  `session/sets/*/attrs/patientId`:
  - For the five `Nova_NNN.h5`-named root-level files
    (`Nova_376/378/379/383/384.h5`), the internal identity **does**
    match the filename.
  - For `AlexSynthetic_001.h5` and `AlexSynthetic_002.h5`, the internal
    identity is **`Nova_376`** — the same patient as `Nova_376.h5`, not
    an independent synthetic patient, despite the distinct filename and
    differing file size/bytes (`cmp` confirms they are not byte-identical
    to `Nova_376.h5` or to each other). These are variant captures under
    the Nova_376 identity scaffold. **Do not treat `AlexSynthetic_001`/
    `AlexSynthetic_002` as independent patients when building a model/
    fixture matrix** — they add preprocessing/measurement variation on
    the same identity, not fixture diversity.
  - For the UUID-named files (all of `eoscloud-dev/`, all of
    `eoscloud-staging/`), the UUID filename is an opaque container
    identifier with **no relationship** to the resolved internal
    `Nova_NNN` patient identity — confirmed by reading
    `session/sample/patient_name` for all 38 UUID-named files.
  - `Nova_103_.h5` has no resolvable patient identity at all (no
    `session` group).

## Per-file table (identity, structure, checksum prefix)

Full 49-row table. `sha256(12)` is the first 12 hex characters of
`shasum -a 256` output (full digests were computed and are available on
request; truncated here for table readability — none of these are
secrets). `sides` is the measurement-set count per side as declared by
`session/sets/*/attrs/side`.

| File | Resolved patient_id | sides | sha256(12) |
|---|---|---|---|
| `AlexSynthetic_001.h5` | Nova_376 (see note above) | L3/R3 | `5b4ad1453de0` |
| `AlexSynthetic_002.h5` | Nova_376 (see note above) | L3/R3 | `7bbf4493e489` |
| `Nova_103_.h5` | **unresolved — no `session` group; legacy `detector_scoped_v1` layout** | n/a | `ca8bcc2d796b` |
| `Nova_376.h5` | Nova_376 | L3/R3 | `ffbc248f9093` |
| `Nova_378.h5` | Nova_378 | L3/R3 | `71a49b8ae1f0` |
| `Nova_379.h5` | Nova_379 | L3/R3 | `53d1f48efdd7` |
| `Nova_383.h5` | Nova_383 | L3/R3 | `4a68dbdbf218` |
| `Nova_384.h5` | Nova_384 | L3/R3 | `98d263c77644` |
| `atypical_one_patient.h5` | Nova_257 (fixture_target_side=right, historical_status=ATYPICAL) | L3/R3 | `52e51f0eba35` |
| `benign_one_patient.h5` | Nova_227 (fixture_target_side=right, historical_status=BENIGN) | L3/R3 | `95a2ff8245f1` |
| `cancer_one_patient.h5` | Nova_214 (fixture_target_side=left, historical_status=CANCER) | L3/R3 | `f09d6f5745af` |
| `eoscloud-dev/03028aa6-...h5` | Nova_402 | L3/R3 | `c6094449b36c` |
| `eoscloud-dev/3e7c88e2-...h5` | Nova_402 | **L6/R6** (doubled: `sample_main`+`sample_transmission` per position) | `bce380cf2b87` |
| `eoscloud-dev/3f429718-...h5` | Nova_402 | L3/R3 | `8ebd03f95511` |
| `eoscloud-dev/654c9bb2-...h5` | Nova_402 | **L6/R6** (doubled) | `86fdd0eb5903` |
| `eoscloud-dev/8863104e-...h5` | Nova_402 | **L6/R6** (doubled) | `931a9229e526` |
| `eoscloud-dev/890030bc-...h5` | Nova_420 | R3/L3 | `972dbe844ecf` |
| `eoscloud-dev/c5d4c61b-...h5` | Nova_402 | L3/R3 | `1290c9141489` |
| `eoscloud-dev/e81dbedc-...h5` | Nova_420 | R3/L3 | `d7a82978e4bf` |
| `eoscloud-dev/fb276c15-...h5` | Nova_402 | L3/R3 | `a7b0bbf2e533` |
| `eoscloud-staging/01ebdbb9-...h5` | Nova_106 | R3/L3 | `efc646f04ba8` |
| `eoscloud-staging/03a89fd2-...h5` | Nova_305 | L3/R3 | `bd92c33a642a` |
| `eoscloud-staging/07ff0a20-...h5` | Nova_101 | R3/L3 | `d33f578f693c` |
| `eoscloud-staging/133e790f-...h5` | Nova_106 | R3/L3 | `b4a1ed1d8ec2` |
| `eoscloud-staging/1604b921-...h5` | Nova_214 | R3/L3 | `6e51bfedca6c` |
| `eoscloud-staging/25c67e4d-...h5` | Nova_423 | R3/L3 | `e4cd927fc6c5` |
| `eoscloud-staging/32fe85ae-...h5` | Nova_304 | R3/L3 | `61f518ae114a` |
| `eoscloud-staging/3cf1139a-...h5` | Nova_420 | R3/L3 | `e0bd0d466805` |
| `eoscloud-staging/43e1f30b-...h5` | Nova_304 | R3/L3 | `e0bc277dd769` |
| `eoscloud-staging/4744e842-...h5` | Nova_101 | R3/L3 | `66204eff2edb` |
| `eoscloud-staging/4a47fc89-...h5` | Nova_423 | R3/L3 | `f8e6686e6bca` |
| `eoscloud-staging/4beec7e2-...h5` | Nova_440 | L3/R3 | `c9b6fbf807a3` |
| `eoscloud-staging/614851e7-...h5` | Nova_420 | R3/L3 | `e6d6bf5fc578` |
| `eoscloud-staging/67de8161-...h5` | Nova_106 | R3/L3 | `5a313fdd2257` |
| `eoscloud-staging/7cc250ce-...h5` | Nova_214 | R3/L3 | `2c9e45b72733` |
| `eoscloud-staging/7e16be33-...h5` | Nova_214 | R3/L3 | `e53783bf3eeb` |
| `eoscloud-staging/95ae9017-...h5` | Nova_301 | L3/R3 | `247736f7b56b` |
| `eoscloud-staging/aaa5f335-...h5` | Nova_304 | R3/L3 | `a2357ad2c0c5` |
| `eoscloud-staging/ac4410fb-...h5` | Nova_305 | R3/L3 | `bee2a058c3f8` |
| `eoscloud-staging/bc212aa6-...h5` | Nova_305 | L3/R3 | `df7fbe959522` |
| `eoscloud-staging/cabce03d-...h5` | **Nova_214** | R3/L3 | `f1da22b94fc4` |
| `eoscloud-staging/d3d66ee8-...h5` | Nova_432 | R3/L3 | `13324d4c05a4` |
| `eoscloud-staging/da687405-...h5` | Nova_412 | R3/L3 | `9e0f4557dc5d` |
| `eoscloud-staging/e2beba8f-...h5` | Nova_101 | R3/L3 | `e70b882a6443` |
| `eoscloud-staging/e348dd20-...h5` | Nova_214 | R3/L3 | `2315b559ab3d` |
| `eoscloud-staging/e9b3b555-...h5` | Nova_214 | R3/L3 | `8ac597bbd470` |
| `eoscloud-staging/fdf9eb00-...h5` | Nova_305 | R3/L3 | `0cc9ffacee4d` |
| `eoscloud-staging/ffa047a5-...h5` | Nova_432 | L3/R3 | `846fd5969d79` |
| `eoscloud-staging/ffb45753-...h5` | Nova_423 | R3/L3 | `0aaf470a8905` |

**`eoscloud-staging/cabce03d-f9c4-43db-91d1-aec20007ee18.h5` (bolded
above) is the exact fixture file referenced by `container_id` in the
already-committed production-execution capture
`results/post0161-prod-smoke-20260917-163154/detail-aramina-success-nova214-left.json`**
(A2 / `aramina_target_breast_risk_0_2_13-beta_f5e4a04cad11`,
`target_side=left`, `risk_probability=0.869387073973647`). This is a
direct, confirmed tie between a local fixture and a previously captured
real production result for the same model — see
`BASELINE_EXECUTION.md` for how this is used as a non-executed
cross-reference, not a freshly reproduced result.

## Patient-identity grouping (19 unique identities + 1 unresolved)

Several container files share the same resolved patient identity
(repeated captures/sessions). Do not treat these as independent
fixtures when sampling for future execution:

| Patient | File count | Files |
|---|---|---|
| Nova_101 | 3 | `eoscloud-staging/{07ff0a20,4744e842,e2beba8f}-...h5` |
| Nova_106 | 3 | `eoscloud-staging/{01ebdbb9,133e790f,67de8161}-...h5` |
| Nova_214 | 7 | `cancer_one_patient.h5`; `eoscloud-staging/{1604b921,7cc250ce,7e16be33,cabce03d,e348dd20,e9b3b555}-...h5` |
| Nova_227 | 1 | `benign_one_patient.h5` |
| Nova_257 | 1 | `atypical_one_patient.h5` |
| Nova_301 | 1 | `eoscloud-staging/95ae9017-...h5` |
| Nova_304 | 3 | `eoscloud-staging/{32fe85ae,43e1f30b,aaa5f335}-...h5` |
| Nova_305 | 4 | `eoscloud-staging/{03a89fd2,ac4410fb,bc212aa6,fdf9eb00}-...h5` |
| Nova_376 | 3 | `Nova_376.h5`, `AlexSynthetic_001.h5`, `AlexSynthetic_002.h5` (same identity, not independent) |
| Nova_378 | 1 | `Nova_378.h5` |
| Nova_379 | 1 | `Nova_379.h5` |
| Nova_383 | 1 | `Nova_383.h5` |
| Nova_384 | 1 | `Nova_384.h5` |
| Nova_402 | 7 | `eoscloud-dev/{03028aa6,3e7c88e2,3f429718,654c9bb2,8863104e,c5d4c61b,fb276c15}-...h5` |
| Nova_412 | 1 | `eoscloud-staging/da687405-...h5` |
| Nova_420 | 4 | `eoscloud-dev/{890030bc,e81dbedc}-...h5`, `eoscloud-staging/{3cf1139a,614851e7}-...h5` |
| Nova_423 | 3 | `eoscloud-staging/{25c67e4d,4a47fc89,ffb45753}-...h5` |
| Nova_432 | 2 | `eoscloud-staging/{d3d66ee8,ffa047a5}-...h5` |
| Nova_440 | 1 | `eoscloud-staging/4beec7e2-...h5` |
| (unresolved) | 1 | `Nova_103_.h5` |

## Structural compatibility notes relevant to the five models

- **Bremen (B1/B2/B3) require exactly 3 LEFT + 3 RIGHT measurement
  sets** (`MEASUREMENT_SIDES = (("LEFT",3),("RIGHT",3))` in
  `src/bremen/model_packages/bremen_v01/manifest.py`). 45 of the 49
  files have exactly 3+3. **Three files
  (`eoscloud-dev/3e7c88e2-...h5`, `654c9bb2-...h5`, `8863104e-...h5`,
  all patient Nova_402) have 6+6** — each position (P1/P2/P3) per side
  carries **two** measurement-type sets
  (`*_sample_main` and `*_sample_transmission`) instead of one. Whether
  Bremen's `H5SessionSelectorTransformer`/profile-selection logic
  accepts, filters, or rejects this doubled structure was **not
  determined** in this pass — it requires actual code execution, not
  static inspection, and is recorded as an open question in
  `BASELINE_EXECUTION.md`, not guessed.
- **Aramina (A1/A2) requires an explicit `target_side` request
  parameter**, not derived from the file (`REQUIRES_TARGET_SIDE = True`
  in `src/bremen/model_packages/aramina_v0213/manifest.py`). Every
  3+3-or-6+6-sided file structurally supports testing **both**
  `target_side=left` and `target_side=right` as separate cases, per the
  task instruction to test both sides separately. The three
  `fixture_target_side`-labeled demo files (`atypical_one_patient.h5`
  →right, `benign_one_patient.h5`→right, `cancer_one_patient.h5`→left)
  additionally carry a curator-assigned "primary" side, but this is a
  fixture label, not a request-contract constraint — both sides remain
  nominally testable for Aramina on any of these files.
- **`Nova_103_.h5` is incompatible with all five models** by direct
  `unsupported_legacy_layouts`/missing-`session`-group contract
  evidence (no execution needed to determine this).
- `required_metadata` for Aramina (`session.sets.*.attrs.thickness_raw_mm`,
  `.age`, `.patientId`, `.specimenId`, `.side`, `.position`) was spot-checked
  present on every inspected `L3/R3` and `L6/R6` file; `Nova_103_.h5`
  obviously lacks all of it.

## What this inventory did NOT do

- Did not read any raw measurement array (detector image / profile
  data) — only group/attribute structure.
- Did not run the Bremen/Aramina H5 reader, session selector, QC, or
  any scientific transformer.
- Did not determine pass/fail for any model/fixture pair — that
  requires execution (see `BASELINE_EXECUTION.md`).
- Did not copy any `.h5` file, byte range, or raw clinical narrative
  field (age, race/ethnicity, biopsy free text, BI-RADS subcategory)
  into this document or any committed file. Only already-public-pattern
  identifiers (`Nova_NNN`, `BENIGN`/`ATYPICAL`/`CANCER` status labels
  already used in `docs/production-contracts-2026-09-18.md`, side
  counts, and file-level SHA256 prefixes) are recorded here.
