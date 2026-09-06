#!/usr/bin/env bash
set -euo pipefail

bash .project-memory/pr/0120-project-memory-technical-debt-aramina-roadmap/scripts/add-bremen-technical-debt.sh
bash .project-memory/pr/0120-project-memory-technical-debt-aramina-roadmap/scripts/add-bremen-future-roadmap.sh
bash .project-memory/pr/0120-project-memory-technical-debt-aramina-roadmap/scripts/add-aramina-roadmap.sh

echo
echo "Written project-memory documents:"
find .project-memory/technical-debt .project-memory/roadmap -type f -name '*.txt' | sort
