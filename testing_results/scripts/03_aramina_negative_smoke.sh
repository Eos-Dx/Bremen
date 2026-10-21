#!/usr/bin/env bash

BASE="${BASE:-https://bremen.matur.co.uk/demo}"
OUT="${OUT:-/tmp/bremen-api-smoke-0157}"
mkdir -p "$OUT"

if [ -z "$ACCESS" ]; then
  echo "FAIL: export ACCESS=<bearer-token> first"
  exit 1
fi

ARAMINA_NEG_PATIENT_ID="${ARAMINA_NEG_PATIENT_ID:-Nova_384}"
ARAMINA_NEG_TARGET_SIDE="${ARAMINA_NEG_TARGET_SIDE:-left}"

curl -sS -L \
  -H "Authorization: Bearer $ACCESS" \
  "$BASE/api/models" > "$OUT/models-negative.json"

ARAMINA_MODEL="${ARAMINA_MODEL:-$(jq -r '
  ([.models[] | select(.workflow_id=="aramina" and .model_version=="0.2.13-beta" and .availability=="available")][0].model_id)
  // ([.models[] | select(.workflow_id=="aramina" and .availability=="available")][0].model_id)
  // empty
' "$OUT/models-negative.json")}"

if [ -z "$ARAMINA_MODEL" ]; then
  echo "FAIL: no available Aramina model"
  exit 1
fi

if [ -z "$ARAMINA_NEG_SOURCE_ID" ]; then
  curl -sS -L \
    -H "Authorization: Bearer $ACCESS" \
    "$BASE/api/h5/containers" > "$OUT/h5-negative.json"

  ARAMINA_NEG_SOURCE_ID="$(jq -r --arg p "$ARAMINA_NEG_PATIENT_ID" '
    [.containers[] | select(.display_name==$p or .patient_display_name==$p)][0].source_id // empty
  ' "$OUT/h5-negative.json")"
fi

if [ -z "$ARAMINA_NEG_SOURCE_ID" ]; then
  echo "SKIP: no source found for $ARAMINA_NEG_PATIENT_ID"
  exit 0
fi

jq -n \
  --arg workflow_id "aramina" \
  --arg model_id "$ARAMINA_MODEL" \
  --arg source_id "$ARAMINA_NEG_SOURCE_ID" \
  --arg patient_id "$ARAMINA_NEG_PATIENT_ID" \
  --arg target_side "$ARAMINA_NEG_TARGET_SIDE" \
  '{
    workflow_id:$workflow_id,
    model_id:$model_id,
    source_id:$source_id,
    patient_id:$patient_id,
    target_side:$target_side,
    analysis_author:"Bremen Platform",
    prediction_comment:""
  }' > "$OUT/request-aramina-negative.json"

http="$(curl -sS -L \
  -o "$OUT/response-aramina-negative.json" \
  -w '%{http_code}' \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -X POST "$BASE/api/jobs" \
  -d @"$OUT/request-aramina-negative.json")"

echo "HTTP=$http"

jq '(.job // .) as $j | ($j.workflow_runs.aramina // {}) as $w | {
  job_id: ($j.job_id // $j.existing_job_id // ""),
  overall_status: ($j.overall_status // ""),
  workflow_status: ($w.status // ""),
  failure: ($w.failure // ""),
  failure_stage: ($w.failure_stage // ""),
  failure_reason_code: ($w.failure_reason_code // ""),
  failure_detail: ($w.failure_detail // ""),
  remediation: ($w.remediation // ""),
  safe_details: ($w.safe_details // {})
}' "$OUT/response-aramina-negative.json"

jq -e '
  (.job // .) as $j
  | ($j.workflow_runs.aramina // {}) as $w
  | $j.overall_status == "failed"
    and $w.status == "failed"
    and $w.failure == "ARAMINA_UNSUPPORTED_INPUT"
    and $w.failure_stage == "preprocessing_contract"
    and $w.failure_reason_code == "ARAMINA_UNSUPPORTED_INPUT_PREPROCESSING_CONTRACT"
' "$OUT/response-aramina-negative.json" >/dev/null || {
  echo "FAIL: negative-path contract did not match the known allowlisted failure"
  exit 1
}

if grep -Eqi '(s3://|/tmp/|traceback|aws_access|secret_access|bearer |token=)' "$OUT/response-aramina-negative.json"; then
  echo "FAIL: possible private/internal data leakage in failure response"
  exit 1
fi

echo "PASS: Aramina safe negative-path contract"
