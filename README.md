# Aramis

Aramis is the EOS product draft for binary diagnosis:

```text
BENIGN vs CANCER
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
