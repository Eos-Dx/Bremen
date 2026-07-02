# Bremen Examples

These marimo notebooks are package examples. They should run from this folder
without importing helper code from `Clinical_trials/Product/Aramis`.

Files:

```text
bremen_dataframe_one_to_one_v0_1.py          (content updated)
bremen_dataframe_one_to_many_v0_1.py         (content updated)
bremen_one_to_many_logistic_baseline_v0_1.py (imports updated)
bremen_one_to_many_product_model_v0_1.py     (imports updated)
bremen_mlflow_draft.py                       (imports and identity updated)
bremen_final_experimental_model_v0_1.py      (imports updated)
bremen_product_notebook_helpers.py           (helper module)
preprocess_one_to_one.sh
preprocess_one_to_many.sh
preprocess_one_to_many_biopsy.sh
preprocess_one_to_one_minimal.sh
preprocess_one_to_many_minimal.sh
preprocess_one_to_many_biopsy_minimal.sh
preprocess_all.sh
```

> **Note:** Example filenames have been renamed from `aramis_*` to `bremen_*` as part of the full package alignment.

The helper file intentionally lives beside the notebooks because marimo examples
import it directly:

```python
import bremen_product_notebook_helpers as helpers
```

Run:

```bash
cd ~/dev/eosproduct/Bremen
conda activate eosproduct
```

Preprocess DataFrames directly from YAML:

```bash
python -m bremen preprocess --config config/preprocessing/bremen_one_to_one_preprocessing_v0_1.yaml
python -m bremen preprocess --config config/preprocessing/bremen_one_to_many_benign_cancer_preprocessing_v0_1.yaml
python -m bremen preprocess --config config/preprocessing/bremen_one_to_many_benign_cancer_biopsy_preprocessing_v0_1.yaml
```

Minimal joblib exports:

```bash
python -m bremen preprocess --config config/preprocessing/bremen_one_to_one_minimal_v0_1.yaml
python -m bremen preprocess --config config/preprocessing/bremen_one_to_many_benign_cancer_minimal_v0_1.yaml
python -m bremen preprocess --config config/preprocessing/bremen_one_to_many_benign_cancer_biopsy_minimal_v0_1.yaml
```

Equivalent example scripts:

```bash
./examples/preprocess_one_to_one.sh
./examples/preprocess_one_to_many.sh
./examples/preprocess_one_to_many_biopsy.sh
./examples/preprocess_one_to_one_minimal.sh
./examples/preprocess_one_to_many_minimal.sh
./examples/preprocess_one_to_many_biopsy_minimal.sh
./examples/preprocess_all.sh
```

Each branch YAML owns both input and output paths:

```yaml
io:
  input_h5_path: ../../../data/combined_archive.h5
  output_joblib_path: ../../examples/outputs/bremen_one_to_one_dataframe.joblib
```

Run marimo notebooks:

```bash
python -m marimo run examples/bremen_dataframe_one_to_one_v0_1.py -- \
  --bremen-preprocessing-config-path config/preprocessing/bremen_one_to_one_preprocessing_v0_1.yaml

python -m marimo run examples/bremen_dataframe_one_to_many_v0_1.py -- \
  --bremen-preprocessing-config-path config/preprocessing/bremen_one_to_many_benign_cancer_preprocessing_v0_1.yaml

python -m marimo run examples/bremen_one_to_many_logistic_baseline_v0_1.py -- \
  --dataframe-joblib-path examples/outputs/bremen_one_to_many_benign_cancer_dataframe.joblib

python -m marimo run examples/bremen_one_to_many_product_model_v0_1.py -- \
  --standard-dataframe-joblib-path examples/outputs/bremen_one_to_many_benign_cancer_dataframe.joblib \
  --biopsy-dataframe-joblib-path examples/outputs/bremen_one_to_many_benign_cancer_biopsy_dataframe.joblib

python -m marimo run examples/bremen_final_experimental_model_v0_1.py -- \
  --one-to-many-joblib-path examples/outputs/bremen_one_to_many_benign_cancer_biopsy_dataframe.joblib \
  --one-to-one-joblib-path examples/outputs/bremen_one_to_one_dataframe.joblib
```

Default product config:

```text
config/aramis_preprocessing_v0_1_config.json
```

This JSON stores provenance: source preprocessing notebook, generation summary,
documentation links, downstream notebook consumers, and the `selection_contract`
for AgBH monochromaticity exclusions. Runtime input/output paths are stored in
the branch YAML, not passed as command-line paths.

Default branch preprocessing YAMLs:

```text
config/preprocessing/bremen_one_to_one_preprocessing_v0_1.yaml
config/preprocessing/bremen_one_to_many_benign_cancer_preprocessing_v0_1.yaml
config/preprocessing/bremen_one_to_many_benign_cancer_biopsy_preprocessing_v0_1.yaml
```

Each notebook reads its own branch YAML by default. The YAML files are commented
and describe raw data, metadata, H5 filters, label grouping, thickness
correction, SNR, normalization, and profile gate settings. Override only when
testing a controlled replacement:

```bash
python -m marimo run examples/bremen_dataframe_one_to_one_v0_1.py -- \
  --bremen-preprocessing-config-path /path/to/bremen_one_to_one_preprocessing_v0_1.yaml
```

Default output:

```text
examples/outputs/bremen_one_to_one_dataframe.joblib
examples/outputs/bremen_one_to_many_benign_cancer_dataframe.joblib
```

To keep more columns in preprocessing joblib, edit the branch YAML:

```yaml
metadata:
  output_columns:
    - patientId
    - specimenId
    - q_range
    - radial_profile_data_raw
    - radial_profile_data

normalization:
  save_initial_data: true
```

If `metadata.output_columns` is empty, the joblib keeps all scalar/audit columns
after dropping heavy detector payloads. If it is set, the final joblib contains
only those columns. Columns listed in `metadata.output_columns` are protected
from payload-drop, so `radial_profile_data_raw` is kept automatically when it is
listed there.

```yaml
metadata:
  drop_payload_columns: false
```

This keeps heavy intermediate arrays such as `measurement_data`, `raw_data`,
and masks. For a smaller debug export, keep only selected profile columns:

```yaml
metadata:
  drop_payload_columns: true
  keep_payload_columns:
    - radial_profile_data_raw
    - radial_profile_sigma

normalization:
  save_initial_data: true
```

`radial_profile_data` is always the final normalized profile. With
`save_initial_data: true`, `radial_profile_data_raw` stores the profile before
normalization.

Biopsy-only one-to-many output:

```bash
python -m marimo run examples/bremen_dataframe_one_to_many_v0_1.py -- \
  --bremen-preprocessing-config-path config/preprocessing/bremen_one_to_many_benign_cancer_biopsy_preprocessing_v0_1.yaml
```

The first model notebook starts from the one-to-many joblib and does not reopen
the H5 container. It trains `LogisticRegression` on the full normalized
`radial_profile_data` profile over 20 repeated patient-safe 70/30 splits and
plots ROC curves for BENIGN vs CANCER.

The first product-model notebook compares the standard one-to-many joblib with
the biopsy-only one-to-many joblib. For each DataFrame it trains
`LogisticRegression` on measurement profiles, aggregates measurement
probabilities to specimen/breast rows, selects thresholds on train OOF specimen
scores, and evaluates ROC/threshold metrics on held-out test patients over
repeated patient-safe 70/30 splits.

The final experimental-model notebook starts from biopsy-only one-to-many
targets and the one-to-one paired DataFrame. It compares M0-M3 fusion concepts:
one-to-many only, one-to-many plus symmetry, plus quality, and plus age/BMI. It
also includes control ablations for age-only, BMI-only, availability-only,
single availability flags, M2+age, and M2+BMI. All splits remain patient-safe.
Missing symmetry is encoded with an explicit availability flag and a zero value,
not as a biological zero.
