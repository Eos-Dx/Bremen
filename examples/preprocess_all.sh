#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python -m bremen preprocess \
  --config config/preprocessing/bremen_one_to_one_preprocessing_v0_1.yaml

python -m bremen preprocess \
  --config config/preprocessing/bremen_one_to_many_benign_cancer_preprocessing_v0_1.yaml

python -m bremen preprocess \
  --config config/preprocessing/bremen_one_to_many_benign_cancer_biopsy_preprocessing_v0_1.yaml
