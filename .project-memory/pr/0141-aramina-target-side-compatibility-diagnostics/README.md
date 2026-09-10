# PR0141 — Aramina target-side compatibility diagnostics

Goal:
Find the exact safe failure reason for Aramina model_id + patient_id + target_side combinations.

Scope:
- API/runtime diagnostics only.
- No frontend layout work.
- No model artifact changes.
- No scoring changes unless a proven adapter bug is found.
- No async/Celery work.
