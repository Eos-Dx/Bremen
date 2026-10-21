#!/usr/bin/env bash

BASE="${BASE:-https://bremen.matur.co.uk/demo}"
OUT="${OUT:-/tmp/bremen-api-smoke-0157}"
mkdir -p "$OUT"

if [ -z "$ACCESS" ]; then
  echo "FAIL: export ACCESS=<bearer-token> first"
  exit 1
fi

echo "== auth + model catalog =="
http="$(curl -sS -L \
  -o "$OUT/models.json" \
  -w '%{http_code}' \
  -H "Authorization: Bearer $ACCESS" \
  "$BASE/api/models")"

echo "HTTP=$http"

if [ "$http" != "200" ]; then
  jq . "$OUT/models.json" 2>/dev/null || cat "$OUT/models.json"
  echo "FAIL: /api/models did not return 200"
  exit 1
fi

jq '{
  status,
  candidate_count,
  available_count,
  models: [.models[] | {
    model_id,
    workflow_id,
    model_version,
    availability,
    technical_ready,
    technical_demo_only
  }]
}' "$OUT/models.json"

bremen_count="$(jq '[.models[] | select(.workflow_id=="bremen" and .availability=="available")] | length' "$OUT/models.json")"
aramina_count="$(jq '[.models[] | select(.workflow_id=="aramina" and .availability=="available")] | length' "$OUT/models.json")"

if [ "$bremen_count" -lt 1 ]; then
  echo "FAIL: no available Bremen model"
  exit 1
fi

if [ "$aramina_count" -lt 1 ]; then
  echo "FAIL: no available Aramina model"
  exit 1
fi

echo "PASS: auth/catalog; Bremen available=$bremen_count; Aramina available=$aramina_count"
