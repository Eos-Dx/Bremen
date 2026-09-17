# Refactor Evidence Index

This directory is the evidence pack for the Bremen Platform hard-refactor spike.
It exists to keep architecture decisions reviewable and separate observed facts from proposed changes.

## Repository evidence

- `ARCHITECTURE_SPIKE_PLATFORM_SIMPLIFICATION.md` — measured repository shape, architectural debt, import cycles, deletion candidates and target boundaries.
- `module_inventory.csv` — per-module inventory used to drive KEEP / REFACTOR / MOVE / DELETE decisions.
- `TARGET_STRUCTURE.md` — target package layout and dependency direction.
- `REFACTOR_ROADMAP.md` — migration sequence R0–R10 and suggested PR slicing.

## API/report evidence

- `evidence/standard-result-contract.png` — Standard Model Result is additive under the existing workflow report response (`report.standard_result`); legacy payload remains untouched.
- `evidence/standard-result-route-analysis.png` — evidence that no `/standard-result` child route exists; the existing `/reports/{workflow_id}` surface is the consumption path.
- `evidence/standard-result-route-404.png` — live curl evidence: `/reports/bremen/standard-result` returns 404 while `/reports/bremen` is a real authenticated route.

## Decision boundary

Evidence files describe the current system and contractual observations. They do not, by themselves, authorize deleting a module.
Deletion requires reference/dependency confirmation plus contract tests or golden fixtures showing the public behaviour is preserved.
