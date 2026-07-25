# ADR-0013: Process-Isolated Aramis Runtime Exception

**Status**: Accepted

**Supersedes**: ADR-0002 for the specific case of process-isolated,
Docker-level Aramis runtime bundling for smoke/integration purposes.
ADR-0002 remains in full force for all product-facing surfaces
(public API, UI, reports, model catalog, demo routes, decision
vocabulary).

## Context

ADR-0002 currently prohibits Aramis as an active dependency, runtime,
shared feature set, API, or configuration target for Bremen.

An inert `AramisProvider` scaffold exists at
`src/bremen/api/workflow_aramis.py`, registered in
`src/bremen/api/workflow_orchestrator.py`, returning
`workflow_unavailable`.

Product owner now wants a second workflow path
(`workflow_id: "aramis"`) for parallel decision support, with strict
process isolation and phased gates.

## Decision

Permit Aramis runtime only as process-isolated subprocess integration
under the explicit phased sequence defined below.

The following are permitted:

- Docker-level bundling in an isolated Python virtual environment
  (separate from Bremen's site-packages, e.g. `/opt/aramis-venv`).
- One-shot subprocess invocation per job.
- Subprocess within the same container (no network service).

The following remain prohibited by ADR-0002 and this exception does
not alter that:

- In-process imports of Aramis Python modules into the Bremen Python
  process.
- Shared Python site-packages between Bremen and Aramis.
- Shared feature sets, label mappings, or preprocessing configurations.
- Shared decision vocabulary or clinical-equivalence mapping.
- Public `/demo` routes exposing Aramis content.
- Bremen model catalog allowlisting Aramis workflow IDs.
- Raw Aramis directive clinical report wording in Bremen product
  surfaces.
- Bremen product API returning Aramis-specific fields.
- Clinical-equivalence claims between Aramis and Bremen outputs.

## Boundary conditions

| Concern | Permitted | Not Permitted |
|---------|-----------|---------------|
| Python environment | Separate venv (`/opt/aramis-venv`) | Bremen's own site-packages |
| Process model | One-shot subprocess per job | Persistent daemon, pool, IPC server |
| Network | Same-container subprocess only | TCP/UDP service, HTTP server, RPC |
| Vocabulary | Aramis keeps native output | Mapping into Bremen decision codes |
| Product exposure | Internal Docker smoke only | Public UI, API, `/demo` routes |
| Report wording | Aramis native output files only | Copying directive language into Bremen reports |
| Patient data | Synthetic/approved fixtures only | Real patient H5 files |
| Source guessing | Must use official bundle/contract | Fabricating dependencies or CLI syntax |

## Source access gate

Docker work (Phase 1) cannot begin until **at least one** of the
following is provided as a verifiable artifact in the repository:

1. Official Aramis runtime source tree (e.g. cloned from
   `https://github.com/Eos-Dx/Aramis.git` at a tagged release).
2. Official Aramis Docker/runtime bundle (e.g.
   `aramis_docker_training_bundle_*`).
3. Official `requirements.txt`, `environment.yml`, or `pyproject.toml`
   from the Aramis runtime.
4. Official `predict.sh`, `run_prediction_docker.sh`, or equivalent
   CLI entrypoint from the Aramis team.
5. Written subprocess/CLI contract from the Aramis team specifying:
   invocation syntax, required input paths, expected output files,
   exit codes, and environment variables.

**Every future implementation plan must cite the exact source/bundle
used.** No plan may guess, reverse-engineer, or fabricate Aramis
behavior.

## Phased sequence

| Phase | Title | Description | Depends on |
|-------|-------|-------------|------------|
| 1 | Docker-level smoke proof | Install Aramis into isolated venv in Docker image. Smoke command runs Aramis subprocess, exits 0, produces expected output. No product code wiring. | ADR-0013 + Aramis source/bundle |
| 2 | Provider subprocess invocation | Wire `AramisProvider.execute()` to spawn Aramis subprocess. Parse exit code and output file existence. No clinical parsing. | Phase 1 + confirmed Aramis CLI contract |
| 3 | Checksummed artifact/manifest | Load Aramis via checksum-verified manifest (parallel to Bremen's model package). | Phase 2 |
| 4 | Workflow allowlist | Add `aramis` to workflow allowlist for public workflow selection. | Phase 3 + safety review |
| 5 | Safe native-result presentation | Display Aramis's native output in controlled UI surface with appropriate disclaimers. No Bremen vocabulary mapping. | Phase 4 + presentation safety review |

## Non-goals

This exception does **not** authorize:

- Clinical-equivalence mapping between Aramis and Bremen.
- `p_cancer → p_mri_needed` mapping.
- `CANCER/NON-CANCER → CONTINUE_MRI` or `MRI_REVIEW_DEFER` mapping.
- Aramis report language copied into Bremen `/demo` or product
  surfaces.
- Immediate runtime activation after ADR-0013 alone.
- Model catalog allowlist changes (deferred to Phase 4).
- Persistent process, process pool, IPC server, or network service.
- Real patient data in Phase 1 or Phase 2.
- Guessing Aramis dependencies, CLI contract, or output schema.

## Test and policy migration

Existing `test_no_aramis_*` tests (19 tests across 11 test files)
remain valid for product-facing surfaces:

| Test file | Test method |
|-----------|-------------|
| `test_bremen_api_contract.py` | `test_no_aramis_identity` |
| `test_bremen_cli_entrypoint.py` | `test_help_no_aramis` |
| `test_bremen_config_loading.py` | `test_no_aramis_in_docstring` |
| `test_bremen_config_loading.py` | `test_no_aramis_in_error_messages` |
| `test_bremen_decision_vocabulary.py` | `test_no_aramis_decision_code_in_bremen` |
| `test_bremen_demo_capture.py` | `test_no_aramis_in_capture_files` |
| `test_bremen_demo_capture.py` | `test_no_aramis_in_module_source` |
| `test_bremen_demo_evidence.py` | `test_no_aramis_in_evidence_bundle` |
| `test_bremen_demo_evidence.py` | `test_no_aramis_in_build_function` |
| `test_bremen_demo_evidence.py` | `test_rejects_bundle_with_aramis_in_optional_field` |
| `test_bremen_demo_presentation.py` | `test_no_aramis_in_pretty_output` |
| `test_bremen_demo_presentation.py` | `test_no_aramis_in_module_source` |
| `test_bremen_demo_ui.py` | `test_no_aramis_in_html` |
| `test_bremen_demo_ui.py` | `test_no_aramis_in_json` |
| `test_bremen_demo_ui.py` | `test_no_aramis_in_module_source` |
| `test_bremen_import_identity.py` | `test_bremen_pipelines_no_aramis_class_names` |
| `test_bremen_import_identity.py` | `test_no_aramis_class_names_in_src` |
| `test_bremen_model_package.py` | `test_no_aramis_references` |
| `test_bremen_execution_showcase.py` | (inline assertions) |

No existing test is weakened by this ADR. PR0090 introduces no
source, test, or runtime changes.

Future implementation PRs must scope new tests to avoid the same
check paths as product-facing tests — Docker smoke artifacts are
internal only and not shipped to end users.

## Consequences

- A governance exception now exists permitting Docker-level,
  process-isolated Aramis bundling under strict boundary conditions
  and a source-access gate.
- All product-facing surfaces remain governed by ADR-0002.
- The source-access gate prevents Docker work from proceeding
  without official Aramis artifacts.
- The phased sequence prevents premature product exposure or
  workflow integration.
- Existing no-aramis test policy is preserved and documented.

## Rollback

Removing this ADR (`docs/adr/0013-aramis-process-isolated-runtime-exception.md`)
restores ADR-0002 prohibition to full force for all concerns
including process-isolated bundling. No code changes are required
for rollback of this governance PR itself (it creates no runtime
behavior). Rollback of future implementation phases would require
separate PRs.
