#!/usr/bin/env bash
# Bremen Production Smoke Script
# ================================
# Runs the full authenticated workflow against production.
#
# Requirements: curl, jq, bash 4+
# No real credentials or tokens are hardcoded.
#
# Usage:
#   bash docs/api/examples/smoke-production.sh
#
# This script reads username/password interactively and writes
# outputs to /tmp/bremen-*.json and /tmp/bremen-report.html.

set -euo pipefail

BASE="${BASE:-https://bremen.matur.co.uk:443}"

echo "=== Bremen Production Smoke ==="
echo "Base URL: $BASE"
echo ""

# ------------------------------------------------------------------
# Step 1: Login
# ------------------------------------------------------------------
echo "--- Step 1: Login ---"
read -rp "Username: " INPUT_USER
read -rsp "Password: " INPUT_PASS
echo ""

curl -sS -L \
  -H "Content-Type: application/json" \
  -X POST "$BASE/demo/api/auth/token" \
  -d "$(jq -n --arg u "$INPUT_USER" --arg p "$INPUT_PASS" '{username:$u,password:$p}')" \
  | tee /tmp/bremen-token.json | jq .

ACCESS="$(jq -r '.access_token // empty' /tmp/bremen-token.json)"
if [ -z "$ACCESS" ]; then
  echo "ERROR: login failed. Check credentials."
  exit 1
fi
echo "ACCESS_LEN=${#ACCESS}"
echo ""

# ------------------------------------------------------------------
# Step 2: List containers
# ------------------------------------------------------------------
echo "--- Step 2: List H5 containers ---"
curl -sS -L \
  -H "Authorization: Bearer $ACCESS" \
  "$BASE/demo/api/h5/containers" \
  | tee /tmp/bremen-containers.json | jq .

SOURCE_ID="$(jq -r '.containers[0].source_id // empty' /tmp/bremen-containers.json)"
PATIENT_NAME="$(jq -r '.containers[0].patient_display_name // .containers[0].display_name // empty' /tmp/bremen-containers.json)"

if [ -z "$SOURCE_ID" ]; then
  echo "ERROR: no containers found."
  exit 1
fi
echo "SOURCE_ID=$SOURCE_ID  PATIENT=$PATIENT_NAME"
echo ""

# ------------------------------------------------------------------
# Step 3: List models
# ------------------------------------------------------------------
echo "--- Step 3: List models ---"
curl -sS -L \
  "$BASE/demo/api/models" \
  | tee /tmp/bremen-models.json | jq .

MODEL_ID="$(jq -r '.models[0].model_id // empty' /tmp/bremen-models.json)"
if [ -z "$MODEL_ID" ]; then
  echo "ERROR: no models found."
  exit 1
fi
echo "MODEL_ID=$MODEL_ID"
echo ""

# ------------------------------------------------------------------
# Step 4: Create job
# ------------------------------------------------------------------
echo "--- Step 4: Create analysis job ---"
jq -n \
  --arg wid "bremen" \
  --arg sid "$SOURCE_ID" \
  --arg pname "$PATIENT_NAME" \
  --arg mid "$MODEL_ID" \
  '{workflow_id:$wid,source_id:$sid,patient_display_name:$pname,model_id:$mid}' \
  | tee /tmp/bremen-job-payload.json

curl -sS -L \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -X POST "$BASE/demo/api/jobs" \
  -d @/tmp/bremen-job-payload.json \
  | tee /tmp/bremen-job-create.json | jq .

JOB_ID="$(jq -r '.job.job_id // .job_id // .id // .jobId // empty' /tmp/bremen-job-create.json)"
if [ -z "$JOB_ID" ]; then
  echo "ERROR: job creation failed. See /tmp/bremen-job-create.json"
  exit 1
fi
echo "JOB_ID=$JOB_ID"
echo ""

# ------------------------------------------------------------------
# Step 5: Poll job status
# ------------------------------------------------------------------
echo "--- Step 5: Job status ---"
curl -sS -L \
  -H "Authorization: Bearer $ACCESS" \
  "$BASE/demo/api/jobs/$JOB_ID" \
  | tee /tmp/bremen-job-status.json | jq .

STATUS="$(jq -r '.overall_status // empty' /tmp/bremen-job-status.json)"
echo "STATUS=$STATUS"
echo ""

# ------------------------------------------------------------------
# Step 6: Event log
# ------------------------------------------------------------------
echo "--- Step 6: Event log ---"
curl -sS -L \
  -H "Authorization: Bearer $ACCESS" \
  "$BASE/demo/api/jobs/$JOB_ID/events" \
  | tee /tmp/bremen-job-events.json | jq .

echo ""

# ------------------------------------------------------------------
# Step 7: Mint stream ticket
# ------------------------------------------------------------------
echo "--- Step 7: Mint stream ticket ---"
curl -sS -L \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -X POST "$BASE/demo/api/jobs/$JOB_ID/auth/ticket" \
  -d '{"purpose":"stream"}' \
  | tee /tmp/bremen-stream-ticket.json | jq .

STREAM_TICKET="$(jq -r '.ticket // empty' /tmp/bremen-stream-ticket.json)"
echo "STREAM_TICKET_LEN=${#STREAM_TICKET}"
echo ""

# ------------------------------------------------------------------
# Step 8: SSE stream
# ------------------------------------------------------------------
echo "--- Step 8: SSE stream (8 seconds) ---"
curl -sS -N --max-time 8 \
  -D /tmp/bremen-sse.headers \
  "$BASE/demo/api/jobs/$JOB_ID/events/stream?auth_ticket=$STREAM_TICKET" \
  -o /tmp/bremen-sse.body || true

cat /tmp/bremen-sse.headers
head -80 /tmp/bremen-sse.body
echo ""

# ------------------------------------------------------------------
# Step 9: Mint report ticket
# ------------------------------------------------------------------
echo "--- Step 9: Mint report ticket ---"
curl -sS -L \
  -H "Authorization: Bearer $ACCESS" \
  -H "Content-Type: application/json" \
  -X POST "$BASE/demo/api/jobs/$JOB_ID/auth/ticket" \
  -d '{"purpose":"report"}' \
  | tee /tmp/bremen-report-ticket.json | jq .

REPORT_TICKET="$(jq -r '.ticket // empty' /tmp/bremen-report-ticket.json)"
echo "REPORT_TICKET_LEN=${#REPORT_TICKET}"
echo ""

# ------------------------------------------------------------------
# Step 10: HTML report
# ------------------------------------------------------------------
echo "--- Step 10: HTML report ---"
curl -sS -L \
  -D /tmp/bremen-report.headers \
  "$BASE/demo/report/$JOB_ID?auth_ticket=$REPORT_TICKET" \
  -o /tmp/bremen-report.html

cat /tmp/bremen-report.headers
echo "REPORT=/tmp/bremen-report.html"
echo ""
echo "=== Smoke Complete ==="
