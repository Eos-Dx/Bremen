# Aramis

Aramis is the EOS research draft product for breast XRD decision support.

The assembly-plan source is:

```text
/Users/sad/Downloads/aramis_assembly_plan_v1.docx
```

## Product Description

Aramis is planned as an ML classifier deployed on the EOS platform and connected
to client-facing software. For XRD scans from patients referred to biopsy, it
provides a breast-level malignancy risk output for decision support.

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

This repository must not present Aramis as autonomous diagnosis, biopsy
replacement, radiologist replacement, FDA-cleared, or clinically validated unless
separate validation and regulatory evidence is added.

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

Assembly-plan target QC criteria are planning targets, not validated product
performance:

```text
sensitivity target: >95%
specificity target: maximize, target >50%
```

## Repository Split

`XRD-preprocessing` is the common preprocessing core for Aramis and Bremen:

```text
H5 raw data
-> normalized azimuthally integrated curves
-> intensity vs q
```

This Aramis repository owns Aramis-specific processing and modeling:

```text
azimuthally integrated curves
-> Aramis features
-> ML classifier training
-> report/QC artifacts
```

Planned Aramis feature families from the assembly plan:

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

python -m marimo run examples/aramis_dataframe_one_to_one_v0_1.py -- \
  --archive-path /Users/sad/dev/eos_play/jupyter_notebooks/Clinical_trials/data/product-aramis-data/combined_archive.h5

python -m marimo run examples/aramis_dataframe_one_to_many_v0_1.py -- \
  --archive-path /Users/sad/dev/eos_play/jupyter_notebooks/Clinical_trials/data/product-aramis-data/combined_archive.h5
```

Default output:

```text
examples/outputs/aramis_one_to_one_dataframe.joblib
examples/outputs/aramis_one_to_many_dataframe.joblib
```

Override output:

```bash
python -m marimo run examples/aramis_dataframe_one_to_one_v0_1.py -- \
  --archive-path /path/to/combined_archive.h5 \
  --output-joblib-path /path/to/aramis_one_to_one_dataframe.joblib
```

Data-quality and monochromaticity limitations are tracked in:

```text
docs/machine_learning_concept.md#data-quality-and-monochromaticity
```

Product versioning/config:

```text
config/aramis_product_versioning.json
config/aramis_preprocessing_v0_1_config.json
config/preprocessing/aramis_one_to_one_preprocessing_v0_1.yaml
config/preprocessing/aramis_one_to_many_preprocessing_v0_1.yaml
```

Reusable preprocessing YAML template/contract lives in:

```text
XRD-preprocessing/src/xrd_preprocessing/configs/preprocessing_branch_config_template.yaml
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
