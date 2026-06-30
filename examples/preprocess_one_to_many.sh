#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python -m aramis preprocess \
  --config config/preprocessing/aramis_one_to_many_benign_cancer_preprocessing_v0_1.yaml
