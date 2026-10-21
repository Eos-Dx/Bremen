#!/usr/bin/env bash

BASE="${BASE:-https://bremen.matur.co.uk/demo}"
OUT="${OUT:-/tmp/bremen-api-smoke-0157}"
mkdir -p "$OUT"

if [ -z "$ACCESS" ]; then
  echo "FAIL: export ACCESS=<bearer-token> first"
  exit 1
fi

if [ -z "$BREMEN_JOB_ID" ]; then
  echo "FAIL: export BREMEN_JOB_ID=<completed-bremen-job-id>"
  exit 1
fi

if [ -z "$ARAMINA_JOB_ID" ]; then
  echo "FAIL: export ARAMINA_JOB_ID=<completed-aramina-job-id>"
  exit 1
fi

COMMON_KEYS='["analysis_author","created_at","eoscan_version","hardware_version","model_method","model_metrics","model_name","model_version","operator_id","patient_age","patient_id","prediction_comment","report_id","risk_probability","scan_date_time","specific_output","target_class_risk_level","threshold_value"]'

fetch_report() {
  workflow="$1"
  job_id="$2"
  target="$OUT/report-$workflow.json"
  http="$(curl -sS -L \
    -o "$target" \
    -w '%{http_code}' \
    -H "Authorization: Bearer $ACCESS" \
    "$BASE/api/jobs/$job_id/reports/$workflow")"
  echo "$workflow report HTTP=$http"
  if [ "$http" != "200" ]; then
    jq . "$target" 2>/dev/null || cat "$target"
    return 1
  fi
  return 0
}

validate_common() {
  workflow="$1"
  f="$2"

  echo "== $workflow standard_result =="
  jq '.report.standard_result' "$f"

  jq -e --argjson expected "$COMMON_KEYS" '
    (.report.standard_result | type) == "object"
    and ((.report.standard_result | keys | sort) == ($expected | sort))
    and (.report.standard_result.report_id | type == "string")
    and (.report.standard_result.created_at | type == "string")
    and (.report.standard_result.model_name | type == "string")
    and (.report.standard_result.model_version | type == "string")
    and (.report.standard_result.model_method | type == "string")
    and (.report.standard_result.model_metrics | type == "object")
    and ((.report.standard_result.model_metrics.sensitivity == null) or (.report.standard_result.model_metrics.sensitivity | type == "number"))
    and ((.report.standard_result.model_metrics.specificity == null) or (.report.standard_result.model_metrics.specificity | type == "number"))
    and (.report.standard_result.threshold_value | type == "number")
    and (.report.standard_result.risk_probability | type == "number")
    and (.report.standard_result.risk_probability >= 0 and .report.standard_result.risk_probability <= 1)
    and (.report.standard_result.target_class_risk_level == "high" or .report.standard_result.target_class_risk_level == "low")
    and (.report.standard_result.specific_output | type == "object")
  ' "$f" >/dev/null || return 1

  jq -e '
    (.report.standard_result.created_at | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(Z|[+-][0-9]{2}:[0-9]{2})$"))
    and (
      .report.standard_result.scan_date_time == ""
      or (.report.standard_result.scan_date_time | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(Z|[+-][0-9]{2}:[0-9]{2})$"))
    )
  ' "$f" >/dev/null || return 1

  return 0
}

fetch_report bremen "$BREMEN_JOB_ID" || exit 1
fetch_report aramina "$ARAMINA_JOB_ID" || exit 1

validate_common bremen "$OUT/report-bremen.json" || {
  echo "FAIL: Bremen standard_result contract"
  exit 1
}

jq -e '.report.standard_result.specific_output == {}' "$OUT/report-bremen.json" >/dev/null || {
  echo "FAIL: Bremen specific_output must be {}"
  exit 1
}

jq -e '
  .report.payload.report_type == "bremen_mri_triage"
  and (.report.payload.score_and_threshold.p_mri_needed | type == "number")
  and (.report.payload.score_and_threshold.threshold | type == "number")
' "$OUT/report-bremen.json" >/dev/null || {
  echo "FAIL: Bremen legacy report fields changed/missing"
  exit 1
}

validate_common aramina "$OUT/report-aramina.json" || {
  echo "FAIL: Aramina standard_result contract"
  exit 1
}

jq -e '
  (.report.standard_result.specific_output.target_side == "left" or .report.standard_result.specific_output.target_side == "right")
  and (.report.standard_result.specific_output.mammography_suspicious_field | type == "string")
' "$OUT/report-aramina.json" >/dev/null || {
  echo "FAIL: Aramina specific_output contract"
  exit 1
}

jq -e '
  (.report.payload.risk_score | type == "number")
  and .report.payload.technical_demo_only == true
  and (.report.target_side == "left" or .report.target_side == "right")
' "$OUT/report-aramina.json" >/dev/null || {
  echo "FAIL: Aramina legacy report fields changed/missing"
  exit 1
}

echo "PASS: Bremen Standard Model Result Contract v1 + legacy report compatibility"
echo "PASS: Aramina Standard Model Result Contract v1 + legacy report compatibility"
