#!/usr/bin/env bash
#
# PR0142 — Aramina preprocessing root-cause smoke.
#
# Research draft / technical verification only. Requires radiologist review.
#
# Runs the four deployed checks that currently fail with
# failure_stage=preprocessing_contract, and prints the allowlisted
# preprocessing subdiagnostic so the exact failing worker stage and rejecting
# transformer are visible.
#
# A FRESH source_id is fetched from /demo/api/h5/containers before every POST,
# because source handles are single-use and expire after one hour.
#
# Usage:
#   BASE_URL=https://<host> ./PREPROCESSING_ROOT_CAUSE_SMOKE.sh
#   BASE_URL=http://127.0.0.1:8000 ./PREPROCESSING_ROOT_CAUSE_SMOKE.sh
#
# Optional:
#   AUTH_TOKEN=<bearer>   when the deployment has auth enabled
#   OUT_DIR=<dir>         where the sanitized report is written
#
# Safety:
#   - Prints only sanitized public fields.
#   - Never prints S3 bucket/key, filesystem paths, tokens, or raw bodies.

set -uo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
OUT_DIR="${OUT_DIR:-$(cd "$(dirname "$0")" && pwd)}"
OUT_FILE="${OUT_DIR}/PREPROCESSING_ROOT_CAUSE_RESULT.txt"

# model_version|patient_display_name|target_side
MATRIX=(
  "0.2.12|Nova_379|left"
  "0.2.12|Nova_379|right"
  "0.2.13|Nova_384|left"
  "0.2.13|Nova_384|right"
)

AUTH_HEADER=()
if [[ -n "${AUTH_TOKEN:-}" ]]; then
  AUTH_HEADER=(-H "Authorization: Bearer ${AUTH_TOKEN}")
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Extract a dotted JSON field without requiring jq. Empty string when absent.
json_get() {
  local json="$1" key="$2"
  printf '%s' "$json" | python3 -c '
import json, sys
key = sys.argv[1]
try:
    data = json.load(sys.stdin)
except Exception:
    print("")
    raise SystemExit(0)
cur = data
for part in key.split("."):
    if isinstance(cur, dict) and part in cur:
        cur = cur[part]
    else:
        print("")
        raise SystemExit(0)
if cur is None:
    print("")
elif isinstance(cur, (dict, list)):
    print(json.dumps(cur))
else:
    print(cur)
' "$key"
}

# Fetch a fresh single-use source_id for a patient display name.
fresh_source_id() {
  local patient="$1"
  local listing
  listing="$(curl -sS "${AUTH_HEADER[@]}" "${BASE_URL}/demo/api/h5/containers" 2>/dev/null)"
  printf '%s' "$listing" | python3 -c '
import json, sys
patient = sys.argv[1]
try:
    data = json.load(sys.stdin)
except Exception:
    print("")
    raise SystemExit(0)
for c in data.get("containers", []):
    name = c.get("patient_display_name") or ""
    if name == patient:
        print(c.get("source_id", ""))
        raise SystemExit(0)
print("")
' "$patient"
}

# Resolve the model_id for a version label from the catalog.
model_id_for_version() {
  local version="$1"
  local catalog
  catalog="$(curl -sS "${AUTH_HEADER[@]}" "${BASE_URL}/demo/api/models" 2>/dev/null)"
  printf '%s' "$catalog" | python3 -c '
import json, sys
version = sys.argv[1]
try:
    data = json.load(sys.stdin)
except Exception:
    print("")
    raise SystemExit(0)
for m in data.get("models", []):
    if m.get("workflow_id") != "aramina":
        continue
    if m.get("model_version") == version:
        print(m.get("model_id", ""))
        raise SystemExit(0)
print("")
' "$version"
}

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

{
  echo "PR0142 — Aramina preprocessing root-cause smoke"
  echo "Research draft / technical verification only; requires radiologist review."
  echo "Base URL: ${BASE_URL}"
  echo "Started: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "A fresh source_id is fetched before every POST."
  echo

  for row in "${MATRIX[@]}"; do
    IFS='|' read -r version patient side <<<"$row"

    model_id="$(model_id_for_version "$version")"
    if [[ -z "$model_id" ]]; then
      echo "=== ${version} | ${patient} | ${side} ==="
      echo "model_id: NOT FOUND in catalog for version ${version}"
      echo
      continue
    fi

    source_id="$(fresh_source_id "$patient")"
    if [[ -z "$source_id" ]]; then
      echo "=== ${version} | ${patient} | ${side} ==="
      echo "model_id: ${model_id}"
      echo "source_id: NOT AVAILABLE (patient not listed)"
      echo
      continue
    fi

    body="$(python3 -c '
import json, sys
print(json.dumps({
    "workflow_id": "aramina",
    "model_id": sys.argv[1],
    "source_id": sys.argv[2],
    "patient_id": sys.argv[3],
    "target_side": sys.argv[4],
}))
' "$model_id" "$source_id" "$patient" "$side")"

    response="$(curl -sS -w '\n%{http_code}' "${AUTH_HEADER[@]}" \
      -X POST "${BASE_URL}/demo/api/jobs" \
      -H 'Content-Type: application/json' \
      -d "$body" 2>/dev/null)"
    http_status="$(printf '%s' "$response" | tail -n1)"
    payload="$(printf '%s' "$response" | sed '$d')"

    job_id="$(json_get "$payload" "job.job_id")"

    echo "=== ${version} | ${patient} | ${side} ==="
    echo "http_status: ${http_status}"
    echo "model_id: ${model_id}"
    echo "job_id: ${job_id}"

    if [[ -z "$job_id" ]]; then
      echo "error_code: $(json_get "$payload" "error_code")"
      echo "reason_code: $(json_get "$payload" "reason_code")"
      echo "remediation: $(json_get "$payload" "remediation")"
      echo
      continue
    fi

    detail="$(curl -sS "${AUTH_HEADER[@]}" "${BASE_URL}/demo/api/jobs/${job_id}" 2>/dev/null)"

    echo "overall_status: $(json_get "$detail" "overall_status")"
    echo "failure: $(json_get "$detail" "workflow_runs.aramina.failure")"
    echo "failure_stage: $(json_get "$detail" "workflow_runs.aramina.failure_stage")"
    echo "failure_reason_code: $(json_get "$detail" "workflow_runs.aramina.failure_reason_code")"
    echo "preprocessing_stage: $(json_get "$detail" "workflow_runs.aramina.safe_details.preprocessing_stage")"
    echo "preprocessing_exception_class: $(json_get "$detail" "workflow_runs.aramina.safe_details.preprocessing_exception_class")"
    echo "preprocessing_transformer: $(json_get "$detail" "workflow_runs.aramina.safe_details.preprocessing_transformer")"
    echo "preprocessing_release: $(json_get "$detail" "workflow_runs.aramina.safe_details.preprocessing_release")"
    echo "preprocessing_reason_code: $(json_get "$detail" "workflow_runs.aramina.safe_details.preprocessing_reason_code")"
    echo "remediation: $(json_get "$detail" "workflow_runs.aramina.remediation")"
    echo
  done

  echo "Finished: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} | tee "$OUT_FILE"

echo
echo "Sanitized report written to: $(basename "$OUT_FILE")"
