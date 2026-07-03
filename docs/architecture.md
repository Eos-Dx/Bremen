# Bremen Architecture Baseline

## Product scope

Bremen is an XRD-based ML decision-support workflow for patients referred to MRI after suspicious mammography findings (dense breast / low-efficacy mammography). Bremen processes target/control HDF5 scan containers, validates metadata, runs preprocessing/feature extraction, loads a controlled joblib model package, and returns prediction/QC/model metadata. Bremen is not a diagnostic replacement and must not claim clinical validation. See ADR-0001 for the full product identity definition.

## Current CLI/config foundation

PR 0008 and PR 0009 delivered the current CLI and config foundation:

- CLI entrypoint with `preprocess` command (lazy import), stub commands (`preflight`, `run`, `report`).
- Config discovery/loading module (`config.py`) with deterministic file lookup (explicit path → `BREMEN_CONFIG` env var → `bremen.yml` → `bremen.yaml` → `bremen.toml`).

## Intended core chain

> Matador → Bremen API → H5 inspect gate → preprocessing/feature extraction → joblib inference → QC → prediction JSON → Matador storage/report layer

## Project Contract Invariant Inventory

1. "Bremen is a controlled ML decision-support product, not just a joblib file."
2. "Bremen must never be described or marketed as a standalone diagnostic system."
3. "No prediction made unless required H5 metadata is present and validated."
4. "Target/control scan roles must be explicit and validated against H5 metadata before any downstream action."
5. "Target and control scans must belong to the same patient/study and be opposite anatomical sides."
6. "Feature schema must be explicit and must match the model package schema before inference."
7. "Joblib model packages are controlled artifacts; joblib must be loaded only from checksum-verified model packages."
8. "Every prediction result MUST include: prediction_id, model_version, model_checksum, feature_schema_version, threshold version/value, qc_status, qc_flags."
9. "Matador remains the system of record for measurements and prediction results."
10. "Platform API MUST NOT depend on local machine paths; all platform paths must be abstracted in project_contract.yml."
11. "Clinical/report wording must remain supplementary decision-support language only."

## Current implementation state

- CLI foundation exists.
- Config discovery/loading exists.
- Docker/CI/GHCR skeleton exists (image built and published, but not used by runtime).
- Real API, H5 gates, inference workflow, Matador integration, cloud deployment, and product-core classifier artifacts remain future work.

## Closing note

PR 0011C / ADR-C is the next architecture bundle, to be planned only after this baseline is merged.
