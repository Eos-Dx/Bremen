# Install PR0161A documentation package

Target branch:

`0161a-standard-result-contract-hardening-docs`

From the Bremen repository root:

```bash
git switch main
git pull --ff-only
git switch -c 0161a-standard-result-contract-hardening-docs
unzip -o /path/to/0161a-standard-result-contract-hardening-docs.zip -d .
bash .project-memory/pr/0161a-standard-result-contract-hardening-docs/scripts/apply-register-updates.sh
git status --short
git diff --check
```

The ZIP contains only documentation/project-memory material.

The apply script appends the roadmap and technical-debt entries idempotently.
It does not stage or commit anything.

Recommended explicit staging after review:

```bash
git add .project-memory/pr/0161a-standard-result-contract-hardening-docs
git add .project-memory/roadmap/BREMEN_FUTURE_ROADMAP.txt
git add .project-memory/technical-debt/BREMEN_TECHNICAL_DEBT.txt
git diff --cached --name-only
git diff --cached --check
```

Do not use `git add -A`.
