# Bremen

Bremen is an XRD-based ML decision-support product candidate. It processes HDF5 target/control scan containers, validates metadata, runs preprocessing and feature extraction, loads a controlled joblib model package, and returns prediction, QC, and model metadata to the platform.

This repository was derived from the Aramis project. Aramis was the EOS research draft product for breast XRD decision support. Bremen carries forward the inherited source code and pipeline architecture while establishing an independent product identity.

## Product Description

Bremen is planned as an ML classifier deployed on the EOS platform and connected to client-facing software.

**Clinical question** (verbatim):

```text
Should patient continue to MRI?
```

**Classification task**: healthy vs. disease (NORMAL vs. BENIGN+CANCER), explicitly distinct from a malignant-vs-benign task.

**Target population**: patients referred to MRI after suspicious mammography findings (dense breast / low-efficacy mammography).

Bremen is an XRD-based ML decision-support workflow for patients referred to MRI after suspicious mammography findings. It is not a diagnostic replacement. Bremen must not claim clinical validation. Bremen must not replace MRI, biopsy, radiologists, clinicians, or clinical judgment.

### Bremen feature families

Bremen's own healthy-vs-disease symmetry/distance approach uses the following seven feature families:

- `sigma_l1`
- `sigma_l2`
- `Mahalanobis1`
- `Mahalanobis2`
- `wasserstein_distance_full_q2`
- `meanrms2`
- `weightedrms1`

These implement Bremen's healthy-vs-disease classification task and are not interchangeable with Aramis's azimuthal-integration/cosine-asymmetry approach.

### Architecture constraints

- Runtime Bremen service must not train models.
- Matador is the system of record for measurements and prediction results.
- Platform APIs must not depend on local machine paths.

## Planned Product Deliverables

Assembly-plan deliverables:

```text
ML classifier in joblib format
standardized documented code
reproducible training pipeline
training QC criteria
public clinical report YAML/template
internal clinical report YAML/template
platform integration plan
```

Draft classifier use:

```text
input:
  XRD scan of both left and right breast sides
  at least one measurement per side
  H5 container input
  model-training config file

output:
  prediction with healthy/disease risk assessment
  decision-support report YAML
  classifier training QC criteria
```

Assembly-plan target QC criteria are planning targets, not validated product performance:

```text
sensitivity target: >95%
specificity target: maximize, target >50%
```

## Repository Split

`XRD-preprocessing` is the common preprocessing core for Bremen and Aramis:

```text
H5 raw data
-> normalized azimuthally integrated curves
-> intensity vs q
```

This Bremen repository owns Bremen-specific processing and modeling:

```text
azimuthally integrated curves
-> Bremen features
-> ML classifier training
-> report/QC artifacts
```

## CLI Usage

Show available commands (safe, no heavy imports):

```bash
python -m bremen --help

# Available commands:
#   preprocess   Build a Bremen preprocessing DataFrame from a YAML config.
#   preflight    Run safety preflight checks (not yet implemented).
#   run          Run Bremen analysis workflow (not yet implemented).
#   report       Generate decision-support report (not yet implemented).
```

Run preprocessing:

```bash
python -m bremen preprocess --config /path/to/preprocess.yaml
```

Planned command-level product interface:

```text
python -m bremen preprocess --config /path/to/preprocess.yaml
python -m bremen training --config /path/to/training.yaml
python -m bremen predict --config /path/to/predict.yaml
```

> **Note:** CLI entrypoints now use the `bremen` package name. The inherited `aramis` entrypoint is preserved as a backward-compatibility alias.

`preprocess` config owns input H5 path, output DataFrame/joblib path, raw-data source, H5 quality exclusions, branch rules, and XRD preprocessing parameters.
`training` config will own dataset paths, split logic, model family, MLflow tracking, and trained model output.
`predict` config will own one-patient H5 input, fixed preprocessing/model versions, and JSON/YAML report output.

Prediction input contract for the first draft:

```text
one H5 container
one patient
two breast-side specimen groups when available
output: healthy/disease risk assessment for decision support
requires radiologist review
```

MLflow is part of the product run because preprocessing defines the dataset.

Product-development rules:

```text
docs/product_development_rules.md
```

Machine-learning concept:

```text
docs/machine_learning_concept.md
```

Data-preprocessing contract:

```text
docs/data_preprocessing.md
```

Preprocessing code split:

```text
src/bremen/pipelines.py
  sklearn-style transformers:
    BremenOneToOnePreprocessingPipeline(...).fit_transform(h5_path)
    BremenOneToManyPreprocessingPipeline(...).fit_transform(h5_path)
  run_one_to_one_preprocessing_pipeline(...)
  run_one_to_many_preprocessing_pipeline(...)
  optional DataFrame joblib export
```

> **Note:** Classes were renamed from `Aramis*` to `Bremen*` as part of the full alignment.

Synthetic regression tests:

```text
tests/synthetic_bremen_h5.py
  one known H5 fixture with raw/data and processed/data 2D arrays

tests/test_bremen_preprocessing_one_to_one.py
  checks one-to-one DataFrame fields and joblib roundtrip

tests/test_bremen_preprocessing_one_to_many.py
  checks one-to-many DataFrame fields and joblib roundtrip
```

Run real-H5 DataFrame examples:

```bash
conda activate bremen
cd /Users/alexred/Projects/Bremen

python -m bremen preprocess --config \
  config/preprocessing/bremen_one_to_one_preprocessing_v0_1.yaml

python -m bremen preprocess --config \
  config/preprocessing/bremen_one_to_many_benign_cancer_preprocessing_v0_1.yaml
```

> **Note:** The examples above reference the Bremen project path. The original Aramis workspace path was `cd /Users/sad/dev/Aramis` with old `aramis_*` config filenames.

Interactive edit mode:

```bash
python -m marimo edit examples/bremen_dataframe_one_to_one_v0_1.py -- \
  --bremen-preprocessing-config-path config/preprocessing/bremen_one_to_one_preprocessing_v0_1.yaml

python -m marimo edit examples/bremen_dataframe_one_to_many_v0_1.py -- \
  --bremen-preprocessing-config-path config/preprocessing/bremen_one_to_many_benign_cancer_preprocessing_v0_1.yaml

python -m marimo edit examples/bremen_one_to_many_product_model_v0_1.py -- \
  --standard-dataframe-joblib-path examples/outputs/bremen_one_to_many_benign_cancer_dataframe.joblib \
  --biopsy-dataframe-joblib-path examples/outputs/bremen_one_to_many_benign_cancer_biopsy_dataframe.joblib
```

> **Note:** Example notebooks and helper filenames have been renamed from `aramis_*` to `bremen_*` as part of the full package alignment.

```text
default settings run automatically
changed settings are frozen until Validate settings is clicked
visualizations stay inside the notebook
joblib DataFrame export is the only default file output
```

Default output:

```text
examples/outputs/bremen_one_to_one_dataframe.joblib
examples/outputs/bremen_one_to_many_benign_cancer_dataframe.joblib
```

Biopsy-only one-to-many output is produced by running the same one-to-many notebook with:

```text
config/preprocessing/bremen_one_to_many_benign_cancer_biopsy_preprocessing_v0_1.yaml
examples/outputs/bremen_one_to_many_benign_cancer_biopsy_dataframe.joblib
```

Input H5 and output joblib paths are owned by each preprocessing YAML under `io.input_h5_path` and `io.output_joblib_path`.

Data-quality and monochromaticity limitations are tracked in:

```text
docs/machine_learning_concept.md#data-quality-and-monochromaticity
```

Product versioning/config:

```text
config/aramis_product_versioning.json
  Human-1 batch/source-line/calibrant-thickness product versioning

config/aramis_preprocessing_v0_1_config.json
  AgBH monochromaticity QC audit artifact
  contains purpose/provenance/selection_contract
  YAML filters.quality_exclusions drives H5-level filtering before GFRM loading

config/preprocessing/bremen_one_to_one_preprocessing_v0_1.yaml
  commented one-to-one branch preprocessing config
  decision unit: patientId

config/preprocessing/bremen_one_to_many_benign_cancer_preprocessing_v0_1.yaml
  commented standard one-to-many BENIGN/CANCER branch preprocessing config

config/preprocessing/bremen_one_to_many_benign_cancer_biopsy_preprocessing_v0_1.yaml
  commented biopsy-only one-to-many BENIGN/CANCER branch preprocessing config
  decision unit: specimenId
```

Reusable preprocessing YAML template/contract lives in:

```text
XRD-preprocessing/src/xrd_preprocessing/configs/preprocessing_branch_config_template.yaml
  commented reusable branch YAML template
```

Product metadata README:

```text
config/README.md
```

Run draft notebook:

```bash
conda env update -f environment.yml
conda activate eosproduct
marimo run examples/bremen_mlflow_draft.py
```

Local MLflow UI:

```bash
mlflow ui --backend-store-uri ./mlruns --port 5000
```

Open:

```text
http://127.0.0.1:5000
```

## Development Roadmap

See [ROADMAP.md](ROADMAP.md) (repository root) for the authoritative Bremen development roadmap. This file replaces the prior `docs/roadmap.md` as the single source of truth for planned PR sequencing.

The roadmap is maintained as root-level `ROADMAP.md` only. The file `docs/roadmap.md` is retained as a redirect stub.

## Repository Cleanup Status

See [docs/repository_cleanup.md](docs/repository_cleanup.md) for the current status of repository identity cleanup, Aramis legacy classification, and deferred items.
