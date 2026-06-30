# Aramis Examples

These marimo notebooks are package examples. They should run from this folder
without importing helper code from `Clinical_trials/Product/Aramis`.

Files:

```text
aramis_dataframe_one_to_one_v0_1.py
aramis_dataframe_one_to_many_v0_1.py
aramis_one_to_many_logistic_baseline_v0_1.py
aramis_one_to_many_product_model_v0_1.py
aramis_final_experimental_model_v0_1.py
aramis_product_notebook_helpers.py
```

The helper file intentionally lives beside the notebooks because marimo examples
import it directly:

```python
import aramis_product_notebook_helpers as helpers
```

Run:

```bash
cd /Users/sad/dev/Aramis
conda activate eosproduct

python -m marimo run examples/aramis_dataframe_one_to_one_v0_1.py -- \
  --aramis-preprocessing-config-path config/preprocessing/aramis_one_to_one_preprocessing_v0_1.yaml

python -m marimo run examples/aramis_dataframe_one_to_many_v0_1.py -- \
  --aramis-preprocessing-config-path config/preprocessing/aramis_one_to_many_benign_cancer_preprocessing_v0_1.yaml

python -m marimo run examples/aramis_one_to_many_logistic_baseline_v0_1.py -- \
  --dataframe-joblib-path examples/outputs/aramis_one_to_many_benign_cancer_dataframe.joblib

python -m marimo run examples/aramis_one_to_many_product_model_v0_1.py -- \
  --standard-dataframe-joblib-path examples/outputs/aramis_one_to_many_benign_cancer_dataframe.joblib \
  --biopsy-dataframe-joblib-path examples/outputs/aramis_one_to_many_benign_cancer_biopsy_dataframe.joblib

python -m marimo run examples/aramis_final_experimental_model_v0_1.py -- \
  --one-to-many-joblib-path examples/outputs/aramis_one_to_many_benign_cancer_biopsy_dataframe.joblib \
  --one-to-one-joblib-path examples/outputs/aramis_one_to_one_dataframe.joblib
```

Default Aramis product config:

```text
config/aramis_preprocessing_v0_1_config.json
```

This JSON stores provenance: source preprocessing notebook, generation summary,
documentation links, downstream notebook consumers, and the `selection_contract`
for AgBH monochromaticity exclusions. Runtime input/output paths are stored in
the branch YAML, not passed as command-line paths.

Default branch preprocessing YAMLs:

```text
config/preprocessing/aramis_one_to_one_preprocessing_v0_1.yaml
config/preprocessing/aramis_one_to_many_benign_cancer_preprocessing_v0_1.yaml
config/preprocessing/aramis_one_to_many_benign_cancer_biopsy_preprocessing_v0_1.yaml
```

Each notebook reads its own branch YAML by default. The YAML files are commented
and describe raw data, metadata, H5 filters, label grouping, thickness
correction, SNR, normalization, and profile gate settings. Override only when
testing a controlled replacement:

```bash
python -m marimo run examples/aramis_dataframe_one_to_one_v0_1.py -- \
  --aramis-preprocessing-config-path /path/to/aramis_one_to_one_preprocessing_v0_1.yaml
```

Default output:

```text
examples/outputs/aramis_one_to_one_dataframe.joblib
examples/outputs/aramis_one_to_many_benign_cancer_dataframe.joblib
```

To keep more columns in preprocessing joblib, edit the branch YAML:

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
python -m marimo run examples/aramis_dataframe_one_to_many_v0_1.py -- \
  --aramis-preprocessing-config-path config/preprocessing/aramis_one_to_many_benign_cancer_biopsy_preprocessing_v0_1.yaml
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
