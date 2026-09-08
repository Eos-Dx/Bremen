#!/usr/bin/env bash
set -euo pipefail

TARGET_ROOT="${1:-${HOME}/dev/eosproduct}"
SCOPE="${2:-all}"
ENV_NAME="${ENV_NAME:-eosproduct}"

run_xrd() {
  echo "Testing XRD-preprocessing"
  (cd "${TARGET_ROOT}/XRD-preprocessing" && conda run -n "${ENV_NAME}" python -m ruff check .)
  (cd "${TARGET_ROOT}/XRD-preprocessing" && conda run -n "${ENV_NAME}" pytest -q)
}

run_aramina() {
  echo "Testing Aramina"
  (cd "${TARGET_ROOT}/Aramina" && conda run -n "${ENV_NAME}" python -m ruff check .)
  (cd "${TARGET_ROOT}/Aramina" && conda run -n "${ENV_NAME}" pytest -q)
  (cd "${TARGET_ROOT}/Aramina" && conda run -n "${ENV_NAME}" python -m marimo check examples/aramina_dataframe_one_to_one_v0_1.py)
  (cd "${TARGET_ROOT}/Aramina" && conda run -n "${ENV_NAME}" python -m marimo check examples/aramina_dataframe_one_to_many_v0_1.py)
}

case "${SCOPE}" in
  xrd) run_xrd ;;
  aramina) run_aramina ;;
  all) run_xrd; run_aramina ;;
  *) echo "Usage: $0 [target_root] [all|xrd|aramina]" >&2; exit 2 ;;
esac
