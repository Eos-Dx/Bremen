# Bremen

Bremen is an XRD-based ML decision-support product candidate. It processes HDF5 target/control scan containers, validates metadata, runs preprocessing and feature extraction, loads a controlled joblib model package, and returns prediction, QC, and model metadata to the platform.

This repository was derived from the Aramis project. Aramis was the EOS research draft product for breast XRD decision support. Bremen carries forward the inherited source code and pipeline architecture while establishing an independent product identity.

## Product Description

Bremen is planned as an ML classifier deployed on the EOS platform and connected to client-facing software. For XRD scans from patients referred to biopsy, it provides a breast-level malignancy risk output for decision support.

Clinical problem:

```text
reduce unnecessary biopsies for patients with suspicious tumors after mammography
support tumor malignancy risk assessment
provide supplementary decision support
require qualified clinician / radiologist review
```

Draft target population:

```text
patients with suspicious breast findings after mammography analysis
patients referred to biopsy
Nova-study Human-1 patients 101-438 for model-development data
```

Draft classification task:

```text
malignant vs benign
low/high p_cancer class
breast/sample-level output for suspicious side
```

This repository must not present Bremen as autonomous diagnosis, biopsy replacement, radiologist replacement, FDA-cleared, or clinically validated unless separate validation and regulatory evidence is added.

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
  p_cancer / low-high malignancy-risk class
  YAML with information for public/internal reports
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

Planned Bremen feature families from the assembly plan:

```text
complete azimuthal integration, components approach
cosine asymmetry distance, symmetry approach
```

Current draft focus:

```text
H5 container
-> product split/filter
-> XRD preprocessing
-> model-ready dataset
-> classifier
-> MLflow lineage
```

Planned command-level product interface:

```text
python -m aramis preprocess --config /path/to/preprocess.yaml
python -m aramis training --config /path/to/training.yaml
python -m aramis predict --config /path/to/predict.yaml
```

> **Note:** CLI entrypoints still use the inherited `aramis` package name. A coordinated rename to `bremen` is planned for a future refactor PR after CI and tests are in place.

`preprocess` config owns input H5 path, output DataFrame/joblib path, raw-data source, H5 quality exclusions, branch rules, and XRD preprocessing parameters.
`training` config will own dataset paths, split logic, model family, MLflow tracking, and trained model output.
`predict` config will own one-patient H5 input, fixed preprocessing/model versions, and JSON/YAML report output.

Prediction input contract for the first draft:

```text
one H5 container
one patient
two breast-side specimen groups when available
output: p_cancer / suggested class for decision support
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
src/aramis/pipelines.py
  sklearn-style transformers:
    AramisOneToOnePreprocessingPipeline(...).fit_transform(h5_path)
    AramisOneToManyPreprocessingPipeline(...).fit_transform(h5_path)
  run_one_to_one_preprocessing_pipeline(...)
  run_one_to_many_preprocessing_pipeline(...)
  optional DataFrame joblib export
```

> **Note:** The `src/aramis/` package and class names (`AramisOneToManyPreprocessingPipeline`, etc.) are inherited from the Aramis project and will be renamed in a future refactor PR.

Synthetic regression tests:

```text
tests/synthetic_aramis_h5.py
  one known H5 fixture with raw/data and processed/data 2D arrays

tests/test_aramis_preprocessing_one_to_one.py
  checks one-to-one DataFrame fields and joblib roundtrip

tests/test_aramis_preprocessing_one_to_many.py
  checks one-to-many DataFrame fields and joblib roundtrip
```

Run real-H5 DataFrame examples:

```bash
conda activate eosproduct
cd /Users/sad/dev/Aramis

python -m aramis preprocess --config \
  config/preprocessing/aramis_one_to_one_preprocessing_v0_1.yaml

python -m aramis preprocess --config \
  config/preprocessing/aramis_one_to_many_benign_cancer_preprocessing_v0_1.yaml
```

> **Note:** The examples above reference a legacy Aramis workspace path. Bremen development should use updated paths once the repository is fully migrated.

Interactive edit mode:

```bash
python -m marimo edit examples/aramis_dataframe_one_to_one_v0_1.py -- \
  --aramis-preprocessing-config-path config/preprocessing/aramis_one_to_one_preprocessing_v0_1.yaml

python -m marimo edit examples/aramis_dataframe_one_to_many_v0_1.py -- \
  --aramis-preprocessing-config-path config/preprocessing/aramis_one_to_many_benign_cancer_preprocessing_v0_1.yaml

python -m marimo edit examples/aramis_one_to_many_product_model_v0_1.py -- \
  --standard-dataframe-joblib-path examples/outputs/aramis_one_to_many_benign_cancer_dataframe.joblib \
  --biopsy-dataframe-joblib-path examples/outputs/aramis_one_to_many_benign_cancer_biopsy_dataframe.joblib
```

Notebook behavior:

```text
default settings run automatically
changed settings are frozen until Validate settings is clicked
visualizations stay inside the notebook
joblib DataFrame export is the only default file output
```

Default output:

```text
examples/outputs/aramis_one_to_one_dataframe.joblib
examples/outputs/aramis_one_to_many_benign_cancer_dataframe.joblib
```

Biopsy-only one-to-many output is produced by running the same one-to-many notebook with:

```text
config/preprocessing/aramis_one_to_many_benign_cancer_biopsy_preprocessing_v0_1.yaml
examples/outputs/aramis_one_to_many_benign_cancer_biopsy_dataframe.joblib
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

config/preprocessing/aramis_one_to_one_preprocessing_v0_1.yaml
  commented one-to-one branch preprocessing config
  decision unit: patientId

config/preprocessing/aramis_one_to_many_benign_cancer_preprocessing_v0_1.yaml
  commented standard one-to-many BENIGN/CANCER branch preprocessing config

config/preprocessing/aramis_one_to_many_benign_cancer_biopsy_preprocessing_v0_1.yaml
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
marimo run examples/aramis_mlflow_draft.py
```

Local MLflow UI:

```bash
mlflow ui --backend-store-uri ./mlruns --port 5000
```

Open:

```text
http://127.0.0.1:5000
```

## Repository Cleanup Status

See [docs/repository_cleanup.md](docs/repository_cleanup.md) for the current status of repository identity cleanup, Aramis legacy classification, and deferred items.
