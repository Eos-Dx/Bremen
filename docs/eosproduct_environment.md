# eosproduct Environment

Bremen product preprocessing depends on `xrd-preprocessing`.

Canonical development environment:

```text
conda env update -n eosproduct -f environment.yml
conda activate eosproduct
```

Required package groups:

```text
H5/container:
  h5py
  eosdx-container from /Users/sad/dev/container

RAW GFRM / XRD physics:
  xrd-preprocessing
  pyFAI
  fabio
  scipy
  scikit-learn
  joblib

DataFrames / storage:
  numpy
  pandas
  pyarrow
  PyYAML

Product notebooks:
  marimo
  matplotlib

ML tracking and baseline models:
  mlflow
  lightgbm

Development / validation:
  pytest
  ruff
```

Current product config references:

```text
xrd_preprocessing.release_tag = v0.1.5-beta
```

For local development, `environment.yml` installs:

```text
/Users/sad/dev/container
/Users/sad/dev/XRD-preprocessing[dev]
/Users/sad/dev/Bremen[dev]
```

For reproducible package metadata, `pyproject.toml` points Bremen to:

```text
xrd-preprocessing @ git+https://github.com/Eos-Dx/XRD-preprocessing.git@v0.1.5-beta
```

Validation commands:

```text
python -m ruff check .
pytest -q
python -m marimo check examples/bremen_dataframe_one_to_one_v0_1.py examples/bremen_dataframe_one_to_many_v0_1.py
```

> **Note:** This document was originally authored for the Aramis project.
> Active project references have been updated to Bremen. Historical dataset
> paths and environment setup references to `/Users/sad/dev/Aramis` are
> preserved as legacy documentation.
