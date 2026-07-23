PR0081 Implementation Report

Starting plan HEAD: 7d59bfd1821f4fc6216a13c7d517e211754f21fd
Implementation complete: yes

Approved Vocabulary

Positive machine code: CONTINUE_MRI
Negative machine code: MRI_REVIEW_DEFER
Positive display name: Continue MRI evaluation
Negative display name: Defer MRI pending clinician review
Positive explanation: The model score meets or exceeds the configured decision threshold. This case is flagged for clinician review regarding continuation to MRI.
Negative explanation: The model score is below the configured decision threshold. MRI continuation may be deferred, subject to clinician review and the complete clinical context.
Decision policy ID: bremen_mri_continuation_threshold
Decision policy version: 0.1.0
Legacy MRI_RECOMMENDED: deprecated alias for CONTINUE_MRI
Legacy MRI_RULE_OUT: deprecated alias for MRI_REVIEW_DEFER
Legacy triage_recommendation: preserved field with canonical value

Files Added

src/bremen/api/decision_contract.py -- authoritative decision policy contract
tests/test_bremen_decision_vocabulary.py -- 43 behavioral tests
.project-memory/decisions/bremen-decision-vocabulary-v0_1.txt -- decision record

Files Modified

src/bremen/api/workflow_bremen.py -- replaced TRIAGE_RECOMMENDED/TRIAGE_RULE_OUT with canonical codes, uses build_decision, emits canonical decision_code and new fields
src/bremen/api/feature_artifact_prediction.py -- imports canonical codes from decision_contract
src/bremen/api/inference_handler.py -- imports canonical codes from decision_contract
src/bremen/api/decision_support.py -- string comparisons accept both canonical and legacy codes
src/bremen/api/report_bremen.py -- string comparisons accept both canonical and legacy codes
src/bremen/workspace_ui.py -- CSS class comparison accepts CONTINUE_MRI and legacy MRI_RECOMMENDED
tests/test_bremen_api_server.py -- asserts accept both canonical and legacy values
tests/test_bremen_api_skeleton.py -- test data uses CONTINUE_MRI
tests/test_bremen_decision_support_output.py -- test data uses CONTINUE_MRI and MRI_REVIEW_DEFER
tests/test_bremen_inference_integration.py -- asserts accept both canonical and legacy values
tests/test_bremen_predictions.py -- test data uses CONTINUE_MRI

Numerical Contract Verification

Probability field: probability (float, sigmoid output)
Threshold source: portable_logreg.threshold from model package
Comparison operator: prob >= threshold (unchanged)
Prediction 1: maps to positive outcome (proven: above-threshold)
Prediction 0: maps to negative outcome (proven: below-threshold)
Model package metadata: no class_labels, positive_class, decision_policy_id, decision_policy_version
Current source locations that created MRI_RECOMMENDED/MRI_RULE_OUT: workflow_bremen.py lines 47-48 (now updated)

Training Source Finding

The training pipeline produces numerical output only. No decision vocabulary strings exist in training code. LABEL_MAP in modeling.py (BENIGN=0, CANCER=1) is a research draft not used by runtime inference. The MRI vocabulary was a runtime construct originating from PR0039 and never sourced from training labels.

MRI_RULE_OUT Origin

Introduced in PR0039 planning (line 286) as the negative alternative to MRI_RECOMMENDED. Implemented as TRIAGE_RULE_OUT in workflow_bremen.py, feature_artifact_prediction.py, and inference_handler.py. Never sourced from training labels. Never approved through a product decision gate.

Class Order

prediction=1 maps to above-threshold (positive for MRI continuation). prediction=0 maps to below-threshold (negative). Class order is implicit in the threshold comparison: prediction = 1 if prob >= threshold else 0. No ambiguity. No class_labels in model package.

Threshold Source

Threshold value from portable_logreg.threshold float in model package. Computed during training via threshold calibration. Threshold value unchanged by this PR. The same >= operator preserved.

Authoritative Decision Architecture

decision_contract.BremenDecision is the single source of truth for Bremen decision vocabulary. Created exactly once per inference run via build_decision(score, threshold). No API, event, report, trace, or workspace surface may independently apply thresholds, map labels, or define vocabulary.

DecisionOutput Relationship to BremenDecision

DecisionOutput (lifecycle_contracts.py) is a downstream event projection. It receives decision_code from the parent BremenDecision object. It does NOT independently apply thresholds, map labels, or define vocabulary. This resolves plan-review warning W001.

Model Metadata Adapter

The current portable_logreg model package lacks class_labels, positive_class, decision_policy_id, and decision_policy_version. get_decision_policy_for_model() supplies these at runtime without mutating the stored package. Adapter version 0.1.0. Numerical inference unchanged.

Legacy Compatibility

triage_recommendation field preserved with canonical value (CONTINUE_MRI or MRI_REVIEW_DEFER). decision_code field added alongside it in all outputs. Both always equal (no contradictory fields). Legacy aliases accepted at validation boundary only: MRI_RECOMMENDED maps to CONTINUE_MRI, MRI_RULE_OUT maps to MRI_REVIEW_DEFER. Events always emit canonical codes. Reports always use canonical codes. Workspace UI accepts both canonical and legacy for display.

API and Jobs

WorkflowResult.payload now includes: decision_code, decision_display_name, decision_policy_id, decision_policy_version alongside preserved triage_recommendation. Job API response includes these fields in workflow_runs result_summary. Legacy prediction API (CompletedResult) carries triage_recommendation with canonical value.

Event Schema

No event schema version bump. decision_code field in runtime.decision.completed now carries CONTINUE_MRI or MRI_REVIEW_DEFER. decision_policy_id changed from bremen_threshold_v1 to bremen_mri_continuation_threshold. decision_policy_version field added (0.1.0). Field structure unchanged. Downstream consumers in controlled demo accept arbitrary string values. Resolves plan-review warning W003.

Reports

Bremen report provider uses canonical decision codes. MRI continuation assessment text unchanged ("may be recommended" / "may not be indicated"). String comparisons accept both canonical and legacy codes. No diagnostic wording. No cancer-ruled-out claim.

Workspace and Showcase

CSS class logic updated: accepts CONTINUE_MRI and legacy MRI_RECOMMENDED for positive styling. triage_recommendation field read from result summary carries canonical value. No layout changes. No new panels. No animations. Resolves plan-review warning W002.

Bremen and Aramis Separation

No Aramis files modified. Bremen decision vocabulary does not affect Aramis decision codes, policy identity, threshold, reports, events, readiness, or provider behavior. Shared lifecycle contracts (lifecycle_contracts.py) not modified.

Privacy

No feature values, coefficients, weights, intercept, scaler/imputer parameters, raw arrays, private paths, or patient identifiers in decision output. Decision.to_dict() excludes score and threshold.

Focused Tests

test_bremen_decision_vocabulary.py -- 43 tests
  Canonical positive: 10 tests
  Canonical negative: 3 tests
  Threshold boundary: 5 tests
  Prediction value mapping: 2 tests
  Legacy compatibility: 6 tests
  Model metadata adapter: 4 tests
  Decision.to_dict: 3 tests
  Input validation: 5 tests
  No diagnostic wording: 3 tests
  Bremen/Aramis separation: 2 tests

Full Suite

1687 passed, 11 skipped, 0 failures.

Deviations

None. All vocabulary fields approved and implemented as specified.

Blockers

None.

Warnings

None. All three plan-review warnings (W001, W002, W003) resolved.

---

## Documentation Correction (Precommit Review)

D001 resolved: docs/api_contract.md updated.
  prediction_summary now documents canonical machine codes (CONTINUE_MRI,
  MRI_REVIEW_DEFER), decision_code, decision_display_name, decision_policy_id,
  decision_policy_version.  triage_recommendation documented as deprecated
  compatibility field.  Legacy aliases documented as compatibility inputs only.
  Safety rules updated with deprecation policy.

D002 resolved: docs/workspace_contract.md updated.
  New PR0081 section documenting: clinical question, approved machine codes,
  decision policy identity, canonical decision contract architecture,
  DecisionOutput relationship, numerical behavior preservation, legacy alias
  policy, scientific boundaries, Bremen/Aramis separation.

D003 resolved: ROADMAP.md sequence corrected.
  PR0081 renamed from Provider-Owned Model Variants to Bremen Decision
  Vocabulary Reconciliation with accurate scope description and Implemented
  status.  PR0080 (Investor Control Room) updated with PR0081 dependency.
  PR0082 added for Provider-Owned Model Variants.

Validation from correction run:
  Full suite: 1687 passed, 11 skipped, 0 failures.
  git diff --check: no whitespace errors.
  Security check: no credentials, no private artifacts.
  All three documentation files updated and consistent with approved vocabulary.

---

## Documentation Correction 2 (Precommit Review Iteration)

D004 resolved: docs/release_readiness_operator_notes.md updated.
  Threshold-based triage line now uses canonical codes (CONTINUE_MRI /
  MRI_REVIEW_DEFER) with legacy alias documentation.  Example response
  in section 8 updated with decision_code, decision_display_name,
  decision_policy_id, decision_policy_version.  Section 9
  prediction_summary documentation updated with canonical field names.
  Section 14 clinical-safety boundaries updated to note
  triage_recommendation is deprecated and decision_code is canonical.

D005 resolved: ROADMAP.md numbering corrected.
  PR0080 now correctly listed as Container v0.3.0 Immutable Re-Pin in
  the completed foundation PRs section.  PR0081 remains Bremen Decision
  Vocabulary Reconciliation (Implemented).  PR0082 is now Bremen
  Investor Control Room (Next milestone).  PR0083 is XRD-Preprocessing
  Training-Runtime Parity.  PR0084 is Bremen Paper-Reference versus
  Product-Contract Investigation.  PR0085 is Provider-Owned Model
  Variants and Independent Model Runs.
  No completed PR number reused.  No historical PRs renumbered.

Validation from correction run:
  Full suite: 1687 passed, 11 skipped, 0 failures.
  git diff --check: no whitespace errors.
  Security check: no credentials, no private artifacts.
