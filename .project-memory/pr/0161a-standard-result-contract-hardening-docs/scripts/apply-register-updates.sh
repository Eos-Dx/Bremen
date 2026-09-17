#!/usr/bin/env bash

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PR_DIR="$ROOT/.project-memory/pr/0161a-standard-result-contract-hardening-docs"
ROADMAP="$ROOT/.project-memory/roadmap/BREMEN_FUTURE_ROADMAP.txt"
DEBT="$ROOT/.project-memory/technical-debt/BREMEN_TECHNICAL_DEBT.txt"

if [ ! -f "$ROADMAP" ]; then
  echo "Missing roadmap file: $ROADMAP"
  exit 1
fi

if [ ! -f "$DEBT" ]; then
  echo "Missing technical debt file: $DEBT"
  exit 1
fi

if ! grep -Fq "R-0161A: Standard Result Contract Hardening documentation and spike" "$ROADMAP"; then
  printf '\n\n' >> "$ROADMAP"
  cat "$PR_DIR/ROADMAP_APPEND.txt" >> "$ROADMAP"
  echo "Appended R-0161A/R-0161 roadmap entries."
else
  echo "Roadmap entries already present; skipped."
fi

if ! grep -Fq "TD-0161-01: Standard Result scan_date_time format/timezone drift" "$DEBT"; then
  printf '\n\n' >> "$DEBT"
  cat "$PR_DIR/TECHNICAL_DEBT_APPEND.txt" >> "$DEBT"
  echo "Appended TD-0161 technical debt entries."
else
  echo "Technical debt entries already present; skipped."
fi

echo "PR0161A project-memory updates applied."
