#!/usr/bin/env bash

BASE="${BASE:-https://bremen.matur.co.uk/demo}"
OUT="${OUT:-/tmp/bremen-api-smoke-0157}"
mkdir -p "$OUT"

if [ -z "$ACCESS" ]; then
  echo "FAIL: export ACCESS=<bearer-token> first"
  exit 1
fi

for name in BREMEN_SOURCE_ID BREMEN_CONTAINER_ID ARAMINA_SOURCE_ID ARAMINA_PATIENT_ID; do
  eval "value=\${$name}"
  if [ -z "$value" ]; then
    echo "FAIL: export $name before running the end-to-end smoke"
    exit 1
  fi
done

ARAMINA_TARGET_SIDE="${ARAMINA_TARGET_SIDE:-left}"

curl -sS -L \
  -H "Authorization: Bearer $ACCESS" \
  "$BASE/api/models" > "$OUT/models.json"

BREMEN_MODEL="${BREMEN_MODEL:-$(jq -r '
  ([.models[] | select(.model_id=="bremen-mri-triage-logreg-v0-1" and .availability=="available")][0].model_id)
  // ([.models[] | select(.workflow_id=="bremen" and .availability=="available")][0].model_id)
  // empty
' "$OUT/models.json")}"

ARAMINA_MODEL="${ARAMINA_MODEL:-$(jq -r '
  ([.models[] | select(.workflow_id=="aramina" and .model_version=="0.2.13-beta" and .availability=="available")][0].model_id)
  // ([.models[] | select(.workflow_id=="aramina" and .availability=="available")][0].model_id)
  // empty
' "$OUT/models.json")}"

if [ -z "$BREMEN_MODEL" ] || [ -z "$ARAMINA_MODEL" ]; then
  echo "FAIL: could not resolve available Bremen/Aramina model IDs"
  exit 1
fi

echo "BREMEN_MODEL=$BREMEN_MODEL"
echo "ARAMINA_MODEL=$ARAMINA_MODEL"

jq -n \
  --arg workflow_id "bremen" \
  --arg model_id "$BREMEN_MODEL" \
  --arg source_id "$BREMEN_SOURCE_ID" \
  --arg container_id "$BREMEN_CONTAINER_ID" \
  '{workflow_id:$workflow_id, model_id:$model_id, source_id:$source_id, container_id:$container_id}' \
  > "$OUT/request-bremen.json"

bremen_http="$(curl -sS -L \
  -o "$OUT/submit-bremen.json" \
  -w '%{http_code}' \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -X POST "$BASE/api/jobs" \
  -d @"$OUT/request-bremen.json")"

BREMEN_JOB_ID="$(jq -r '.job.job_id // .job_id // .existing_job_id // empty' "$OUT/submit-bremen.json")"

echo "BREMEN_SUBMIT_HTTP=$bremen_http BREMEN_JOB_ID=$BREMEN_JOB_ID"

if [ -z "$BREMEN_JOB_ID" ]; then
  jq . "$OUT/submit-bremen.json"
  echo "FAIL: Bremen submit did not return a job id"
  exit 1
fi

jq -n \
  --arg workflow_id "aramina" \
  --arg model_id "$ARAMINA_MODEL" \
  --arg source_id "$ARAMINA_SOURCE_ID" \
  --arg patient_id "$ARAMINA_PATIENT_ID" \
  --arg target_side "$ARAMINA_TARGET_SIDE" \
  '{
    workflow_id:$workflow_id,
    model_id:$model_id,
    source_id:$source_id,
    patient_id:$patient_id,
    target_side:$target_side,
    analysis_author:"Bremen Platform",
    prediction_comment:""
  }' > "$OUT/request-aramina.json"

aramina_http="$(curl -sS -L \
  -o "$OUT/submit-aramina.json" \
  -w '%{http_code}' \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -X POST "$BASE/api/jobs" \
  -d @"$OUT/request-aramina.json")"

ARAMINA_JOB_ID="$(jq -r '.job.job_id // .job_id // .existing_job_id // empty' "$OUT/submit-aramina.json")"

echo "ARAMINA_SUBMIT_HTTP=$aramina_http ARAMINA_JOB_ID=$ARAMINA_JOB_ID"

if [ -z "$ARAMINA_JOB_ID" ]; then
  jq . "$OUT/submit-aramina.json"
  echo "FAIL: Aramina submit did not return a job id"
  exit 1
fi

poll_job() {
  workflow="$1"
  job_id="$2"
  f="$OUT/job-$workflow.json"
  n=0
  while [ "$n" -lt 60 ]; do
    curl -sS -L \
      -H "Authorization: Bearer $ACCESS" \
      "$BASE/api/jobs/$job_id" > "$f"
    status="$(jq -r '.overall_status // empty' "$f")"
    echo "$workflow poll=$n status=$status"
    if [ "$status" = "completed" ] || [ "$status" = "failed" ]; then
      return 0
    fi
    n=$((n + 1))
    sleep 2
  done
  return 1
}

poll_job bremen "$BREMEN_JOB_ID" || {
  echo "FAIL: Bremen job polling timeout"
  exit 1
}

poll_job aramina "$ARAMINA_JOB_ID" || {
  echo "FAIL: Aramina job polling timeout"
  exit 1
}

bremen_status="$(jq -r '.overall_status' "$OUT/job-bremen.json")"
aramina_status="$(jq -r '.overall_status' "$OUT/job-aramina.json")"

if [ "$bremen_status" != "completed" ]; then
  jq . "$OUT/job-bremen.json"
  echo "FAIL: Bremen job status=$bremen_status"
  exit 1
fi

if [ "$aramina_status" != "completed" ]; then
  jq . "$OUT/job-aramina.json"
  echo "FAIL: Aramina job status=$aramina_status"
  exit 1
fi

export BREMEN_JOB_ID
export ARAMINA_JOB_ID

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
"$SCRIPT_DIR/01_existing_job_contract_smoke.sh"
