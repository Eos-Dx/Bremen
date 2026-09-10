# Frontend context / non-goals for PR0143

PR0143 is backend/API report-contract work only.

Known frontend state:

- Aramina patient submission from UI is still broken/incomplete.
- Aramina report viewing from UI is still broken or Bremen-oriented.
- This PR must not claim Aramina UI readiness.

Required reviewer statement:

- Backend/API Aramina report contract: PASS or BLOCKED.
- Frontend Aramina patient submission: NOT IN SCOPE / still known broken.
- Frontend Aramina report viewing: NOT IN SCOPE / still known broken.

Follow-up frontend PR required:

- Send complete Aramina submit payload:
  - workflow_id
  - model_id
  - source_id
  - patient_id
  - target_side
  - analysis_author
  - prediction_comment
- Refresh source_id immediately before POST.
- Route reports to /demo/api/jobs/{job_id}/reports/aramina.
- Display target_side, model_version, risk_score, technical_demo_only, disclaimer.
- Display Aramina safe failure diagnostics.
- Remove Bremen-only copy from Aramina UI.
