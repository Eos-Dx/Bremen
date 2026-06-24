# Aramis Human-1 Product Metadata

This directory contains canonical JSON/CSV metadata for the Aramis Human-1
research draft product workflow.

These files are product metadata prepared for Aramis by Slava Shcherbakov
(Viacheslav SHCHERBAKOV). Treat them as controlled product inputs, not as
ad-hoc notebook outputs.

Aramis is clinical decision support research draft work. These metadata do not
make the model clinically validated, FDA-cleared, or suitable for autonomous
diagnosis.

## Files

### `aramis_product_versioning.json`

Purpose:

```text
Human-1 versioning
data_batch definitions
K-alpha / K-beta source-line rules
Nova patient ranges
AgBH reference thickness rules
required H5 metadata fields
product filtering policy
```

Use this file when deciding whether a measurement batch is product-usable for a
K-alpha-only Aramis workflow.

Current conservative rule recorded in JSON:

```text
include data_batch: 3, 4, 5, 7
exclude data_batch: 1, 2, 6
review required: null / unknown
```

Important: AgBH shoulder-metric review can supersede this draft batch policy.
If batch 5 is confirmed bad for the product workflow, update this JSON first,
then update downstream notebooks, docs, and MLflow artifacts.

AgBH thickness rule recorded in JSON:

```text
before 2026-04-22: 40 mm
from 2026-04-22: 10 mm
preferred field: agbh_thickness_mm
```

### `human1_diagnoses_metadata.json`

Purpose:

```text
canonical Human-1 clinical metadata
diagnosis labels
patient/specimen metadata
BI-RADS fields
MRI / biopsy fields
specimen status
source Excel normalization
external_id -> patient/side/position parsing
```

Source workbook:

```text
/Users/sad/Downloads/Human-1 Diagnoses for Matador v4(5).xlsx
```

Do not use the Excel file directly in product notebooks. Product code should
read this JSON. If the Excel source changes, regenerate this JSON and rerun the
H5 audit.

Key contract:

```text
External ID format:
Nova_<patient_number>_<LEFT|RIGHT>_P<point_number>

Comparison key:
patient_external_id | side | position
```

### `human1_diagnoses_metadata_h5_audit.json`

Purpose:

```text
audit of JSON clinical metadata against combined_archive.h5
matched measurement keys
Excel-only keys
H5-only keys
duplicate keys
metadata mismatch summary
```

Use this file before building a product dataset from H5. It shows where H5
metadata differs from the canonical clinical metadata JSON.

Current audit summary:

```text
excel rows: 2086
excel unique measurement keys: 2083
h5 unique measurement keys: 2001
matched keys: 1996
excel-only keys: 87
h5-only keys: 5
mismatch rows: 779
mismatched keys: 558
```

### `human1_diagnoses_metadata_h5_mismatches.csv`

Purpose:

```text
row-level mismatch table for H5 vs canonical JSON
external_id_key
field
Excel value
H5 value
source row
H5 session path
H5 set name
```

Use this file to decide which mismatches are harmless normalization differences
and which require H5 backfill or product-filter changes.

## Product Rules

Canonical metadata flow:

```text
Excel/source document
-> canonical JSON
-> H5 audit
-> product filter
-> h5_to_df
-> preprocessing
-> MLflow dataset artifact
```

Do not silently change:

```text
data_batch policy
K-alpha / K-beta policy
AgBH thickness rule
diagnosis label mapping
BI-RADS fields
patient/specimen identifiers
H5-vs-JSON mismatch handling
```

Any change must update:

```text
JSON metadata
docs
notebooks/helpers
selected/dropped measurement manifests
MLflow artifacts
```

