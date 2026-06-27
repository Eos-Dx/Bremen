# Aramis Data Preprocessing

Status: research draft.

This document defines the current Aramis data-preprocessing contract for model
development. Aramis output remains decision support: `p_cancer` and suggested
BENIGN/CANCER class, requiring radiologist / qualified clinician review.

## Identifier Levels

All filtering and transformations must state the data level.

```text
measurementId level:
  one detector measurement / one XRD frame-derived profile

specimenId level:
  one breast side / specimen
  all valid measurements from the same specimen inherit the same product label

patientId level:
  one patient
  contains left and right breast-side specimen groups when both are available
```

Do not mix these levels silently. Counts and filters must report whether they
operate on `measurementId`, `specimenId`, or `patientId`.

## Shared H5-Level Product Filters

These filters run before GFRM decode and before `h5_to_df` materializes the
model DataFrame.

```text
1. measurementId/session level:
   keep sessions whose dates pass AgBH monochromaticity QC

2. measurementId/session level:
   keep sessions whose PONI geometry can provide the required q range

3. measurementId/session level:
   require sample thickness metadata
   no thickness means azimuthal integration with thickness correction is invalid

4. measurementId/session level:
   require calibrant_thickness_mm in H5 metadata
   current AgBH safety range: 10..40 mm

5. measurementId/session level:
   keep only canonical measurement positions P1, P2, P3 before frame loading

6. measurementId/session level:
   read detector data from the source declared in the branch preprocessing YAML
   allowed source values: gfrm, npy, tiff
```

`calibrant_thickness_mm` is calibrant-generic. Current AgBH data use 10 or 40
mm. Later calibrants, for example LaB6, may use different values but must keep
an explicit field and documented safety range.

Production policy:

```text
prefer gfrm when original vendor bytes are available
use npy/tiff only when explicitly declared in the branch preprocessing YAML
do not silently mix gfrm, npy, and tiff source types in one product run
```

Thickness correction is required for azimuthal integration:

```text
filters.thickness.sample.column:
  H5/sample attribute for specimen thickness filtering
  current value: sample_thickness_mm

filters.thickness.calibrant.column:
  H5/session attribute for calibrant/reference thickness filtering
  current value: calibrant_thickness_mm

correction:
  AzimuthalIntegration receives the same two YAML column names
  missing or invalid thickness means the measurement cannot be used
```

The YAML thickness contract is shared by H5 filtering and integration. If the
filter column and integration column differ, preprocessing must fail instead of
silently integrating with another thickness attribute.

## Shared Measurement-Level XRD Pipeline

After H5 filtering and `h5_to_df`, both model branches use the same
measurement-level XRD preprocessing:

```text
1. measurementId level:
   FaultyPixelDetector

2. measurementId level:
   AzimuthalIntegration(error_model="poisson")
   use YAML thickness_correction columns

3. measurementId level:
   SNRTransformer(snr_method="poisson")

4. measurementId level:
   SNRFilter(min_snr_db=18.0 in current notebooks)

5. measurementId level:
   QRangeNormalizer(q_min=6.7, q_max=7.1)

6. measurementId level:
   radial-profile signal gate
```

The historical canonical threshold was 20 dB. Current exploratory Aramis
notebooks use 18 dB. Any final product change must be versioned and logged in
MLflow with the selected measurement IDs and dropped measurement IDs.

## Pipeline Entrypoints

Current draft code composes reusable `xrd_preprocessing` transformers. Aramis
does not own preprocessing transformer implementations.

```text
XRD-preprocessing/src/xrd_preprocessing/config.py
  load_preprocessing_config(...)

XRD-preprocessing/src/xrd_preprocessing/configs/preprocessing_branch_config_template.yaml
  reusable branch-specific preprocessing YAML template/contract
  reusable preprocessing YAML template/contract

Aramis/config/preprocessing/aramis_one_to_one_preprocessing_v0_1.yaml
Aramis/config/preprocessing/aramis_one_to_many_preprocessing_v0_1.yaml
  concrete Aramis project preprocessing config

src/aramis/pipelines.py
  AramisOneToOnePreprocessingPipeline(...).fit_transform(h5_path)
  AramisOneToManyPreprocessingPipeline(...).fit_transform(h5_path)
  run_one_to_one_preprocessing_pipeline(...)
  run_one_to_many_preprocessing_pipeline(...)
```

The pipeline classes follow the sklearn transformer contract:

```text
input object X:
  H5 container path

output object:
  final preprocessing DataFrame

fit(X):
  no-op, returns self

transform(X):
  reads the H5, applies configured preprocessing, returns DataFrame

fit_transform(X):
  one-call DataFrame build
```

Each pipeline returns the final DataFrame and can write the same DataFrame to a
`.joblib` file. This is preprocessing output, not a trained classifier.

Synthetic tests use one known H5 container with both `raw/data` and
`processed/data` 2D arrays:

```text
tests/synthetic_aramis_h5.py
```

Expected fixture behavior:

```text
P1: BENIGN-CANCER pair
  one-to-one: keep
  one-to-many: keep both specimens

P2: single BENIGN breast
  one-to-one: drop
  one-to-many: keep

P3: NORMAL-ATYPICAL pair
  one-to-one: keep as CANCER-NORMAL
  one-to-many: keep ATYPICAL as CANCER, drop NORMAL

P4: BENIGN-CANCER pair but one side lacks sample thickness
  one-to-one: drop patient after thickness/sample-pair validity
  one-to-many: keep valid CANCER side only

P5: CANCER with calibrant_thickness_mm=50
  both branches: drop by calibrant thickness safety range
```

The tests verify exact final DataFrame columns, expected patients/specimens,
label grouping, thickness-correction metadata, dropped heavy detector payloads,
and joblib roundtrip equality.

## Label Grouping

Label grouping is defined at `specimenId` / breast-side level.

```text
specimenId level: BENIGN -> BENIGN
specimenId level: CANCER -> CANCER
specimenId level: ATYPICAL -> CANCER
specimenId level: PRE_CANCEROUS -> CANCER
specimenId level: NORMAL -> NORMAL
specimenId level: NA -> exclude
```

Preserve the original `specimen_status`. Write product labels to a separate
column so label mapping remains auditable.

All scalar H5 metadata should be preserved in every preprocessing DataFrame.
Biopsy metadata is especially important because it tracks whether the diagnosis
context is biopsy-associated:

```text
biopsy / sample_biopsy:
  whether biopsy was taken for the patient/specimen context

sample_biopsy_type:
  Pre-biopsy / Post-biopsy when present

sample_status:
  Non-cancer / Cancer / Prior cancer context when present
```

## One-To-Many Dataset

Purpose:

```text
specimenId-level BENIGN vs CANCER classifier
compare one breast side against breast sides from other patients
```

Preprocessing steps:

```text
1. H5 measurementId/session level:
   apply shared AgBH-date, q-range, sample-thickness, and calibrant-thickness filters

2. H5 specimenId level:
   keep BENIGN, CANCER, ATYPICAL, PRE_CANCEROUS
   exclude NORMAL and NA for this binary dataset

3. h5_to_df measurementId level:
   materialize only selected SAMPLE/SAMPLE measurement rows from GFRM

4. DataFrame specimenId level:
   group labels:
     BENIGN -> BENIGN
     CANCER/ATYPICAL/PRE_CANCEROUS -> CANCER

5. measurementId level:
   run shared XRD preprocessing

6. specimenId level:
   apply post-SNR validity
   current rule: at least 1 valid measurement per specimen

7. patientId level:
   retain patientId only for leakage control and split logic
   do not require both breasts for one-to-many
```

Output unit:

```text
model rows are measurement-level/profile rows
labels are specimenId-level breast-side labels
splits must be patient-safe
```

## One-To-One Dataset

Purpose:

```text
patientId-level paired-breast symmetry model
compare left and right breast profiles within the same patient
```

Preprocessing steps:

```text
1. H5 measurementId/session level:
   apply shared AgBH-date, q-range, sample-thickness, and calibrant-thickness filters

2. H5 patientId level:
   keep patients with at least one informative breast-side status:
   BENIGN, CANCER, ATYPICAL, or PRE_CANCEROUS

3. H5 specimenId level:
   exclude NA specimen rows
   preserve paired breast context, including NORMAL

4. h5_to_df measurementId level:
   materialize selected SAMPLE/SAMPLE measurement rows from GFRM

5. DataFrame specimenId level:
   group labels:
     BENIGN -> BENIGN
     CANCER/ATYPICAL/PRE_CANCEROUS -> CANCER
     NORMAL -> NORMAL

6. DataFrame patientId level:
   keep first ML pair types:
     BENIGN-CANCER
     BENIGN-NORMAL
     CANCER-NORMAL

7. DataFrame patientId level:
   exclude first ML pair types:
     BENIGN-BENIGN
     NORMAL-NORMAL
     CANCER-CANCER

8. measurementId level:
   run shared XRD preprocessing

9. patientId level after SNR:
   require paired breast availability
   current rule:
     min_measurements_per_specimen = 1
     min_specimens_per_patient = 2
```

Output unit:

```text
model features are derived from paired breast profiles
pair validity is patientId-level
breast labels are specimenId-level
raw profiles remain measurementId-level
```

## Fusion Dataset

Purpose:

```text
combine one-to-many evidence and one-to-one symmetry evidence
produce final p_cancer decision-support score
```

Fusion input concept:

```text
patientId level:
  left breast one-to-many score
  right breast one-to-many score
  one-to-one symmetry coefficient / asymmetry risk

output:
  patient-level p_cancer
  BENIGN/CANCER decision-support class
```

Preprocessing contract:

```text
1. patientId level:
   join one-to-many breast-side outputs and one-to-one patient-pair outputs

2. specimenId level:
   preserve side-specific one-to-many scores and product labels
   keep left and right breast scores separately

3. patientId level:
   preserve one-to-one symmetry coefficient / asymmetry risk

4. patientId level:
   train fusion model with patient-safe splits only
```

The fusion model must not re-split measurement rows independently. Patient,
specimen, and measurement lineage must remain traceable to the original H5
container.

## Required Audit Artifacts

Every dataset build should produce MLflow artifacts:

```text
preprocessing_config.json
product_filter_rules.json
selected_measurement_ids.csv
dropped_measurements.csv
preprocessed_dataset.parquet or .csv
feature_schema.json
label_mapping.json
train_test_split.csv
```

Every stage counter must say which level was counted:

```text
measurementId count
specimenId count
patientId count
diagnosis/status count at specimenId level
```
