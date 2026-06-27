# Aramis Examples

These marimo notebooks are package examples. They should run from this folder
without importing helper code from `Clinical_trials/Product/Aramis`.

Files:

```text
aramis_dataframe_one_to_one_v0_1.py
aramis_dataframe_one_to_many_v0_1.py
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
  --archive-path /Users/sad/dev/eos_play/jupyter_notebooks/Clinical_trials/data/product-aramis-data/combined_archive.h5

python -m marimo run examples/aramis_dataframe_one_to_many_v0_1.py -- \
  --archive-path /Users/sad/dev/eos_play/jupyter_notebooks/Clinical_trials/data/product-aramis-data/combined_archive.h5
```

Default Aramis product config:

```text
config/aramis_preprocessing_v0_1_config.json
```

This JSON stores provenance: source preprocessing notebook, generation summary,
documentation links, downstream notebook consumers, and the `selection_contract`
for AgBH monochromaticity accepted dates. Override only when testing a
controlled replacement:

```bash
python -m marimo run examples/aramis_dataframe_one_to_many_v0_1.py -- \
  --archive-path /path/to/combined_archive.h5 \
  --agbh-config-path /path/to/aramis_preprocessing_v0_1_config.json
```

Default branch preprocessing YAMLs:

```text
config/preprocessing/aramis_one_to_one_preprocessing_v0_1.yaml
config/preprocessing/aramis_one_to_many_preprocessing_v0_1.yaml
```

Each notebook reads its own branch YAML by default. The YAML files are commented
and describe raw data, metadata, H5 filters, label grouping, thickness
correction, SNR, normalization, and profile gate settings. Override only when
testing a controlled replacement:

```bash
python -m marimo run examples/aramis_dataframe_one_to_one_v0_1.py -- \
  --archive-path /path/to/combined_archive.h5 \
  --aramis-preprocessing-config-path /path/to/aramis_one_to_one_preprocessing_v0_1.yaml
```

Default output:

```text
examples/outputs/aramis_one_to_one_dataframe.joblib
examples/outputs/aramis_one_to_many_dataframe.joblib
```
