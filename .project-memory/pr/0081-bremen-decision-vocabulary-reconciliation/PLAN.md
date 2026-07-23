PLAN COMPLETE

PLAN FILE

.project-memory/pr/0081-bremen-decision-vocabulary-reconciliation/PLAN.md

HEAD

4c1e32fd8df02541ac9b04c6e509f858225aa13c

BRANCH

0081-bremen-decision-vocabulary-reconciliation

SOURCE REFS

Bremen application repository
  Default branch: main
  Inspected commit: 4c1e32fd8df02541ac9b04c6e509f858225aa13c
  Date: current HEAD of 0081 branch

Eos-Dx/bremen-training-pipeline (external repository)
  Not cloned locally. Evidence obtained from bremen-training-pipeline source
  embedded in this repository under src/bremen/training/ and src/bremen/modeling.py.
  The training pipeline repository lives at Eos-Dx/bremen-training-pipeline
  and was used as the remote source for the training code committed here.
  The config/training/bremen_v0_1_train.yaml references this pipeline.

TRAINING VOCABULARY

The local training source (src/bremen/training/pipeline.py and src/bremen/modeling.py)
was inspected. Key findings:

Training config (config/training/bremen_v0_1_train.yaml):
  label_column: "label"
  model.type: "patient_m0_m1_m2_logistic_set"
  selected_models: ["M0", "M1", "M2"]
  The config does not define any decision vocabulary strings, class labels,
  positive class, or decision codes. It only names the column containing labels.

Training pipeline (src/bremen/training/pipeline.py):
  Built for healthy-versus-disease classification (NORMAL vs BENIGN+CANCER).
  Outputs: probability, prediction (0/1), threshold.
  No MRI_RULE_OUT, MRI_RECOMMENDED, CONTINUE_MRI, or MRI_REVIEW_DEFER strings
  exist in the training pipeline.

Legacy modeling module (src/bremen/modeling.py):
  LABEL_MAP = {"BENIGN": 0, "CANCER": 1}
  This is a legacy research-draft module. The labels are BENIGN/CANCER,
  not MRI continuation vocabulary. This module is NOT used by the current
  runtime inference path.

Inference module (src/bremen/inference.py):
  predict_proba_portable returns:
    probability (float)
    prediction (0 or 1)
    threshold_applied (float)
  No decision vocabulary strings. The output is purely numerical.
  The inference module does not know about MRI_RULE_OUT or MRI_RECOMMENDED.

Model package format:
  portable_logreg contains:
    feature_columns, imputer_statistics, scaler_mean, scaler_scale,
    coef, intercept, threshold
  No decision-policy ID, decision-policy version, class_labels, positive_class,
  or display_name fields exist in the model package.

Conclusion for training vocabulary:
  The training pipeline produces numerical output (probability, prediction 0/1).
  It does NOT produce any decision vocabulary strings.
  The vocabulary MRI_RECOMMENDED/MRI_RULE_OUT is added entirely by the runtime.
  There is no source evidence that training uses CONTINUE_MRI or MRI_REVIEW_DEFER.

RUNTIME VOCABULARY

The current runtime defines decision vocabulary in five separate locations:

workflow_bremen.py (primary, authoritative provider):
  TRIAGE_RECOMMENDED = "MRI_RECOMMENDED"
  TRIAGE_RULE_OUT = "MRI_RULE_OUT"
  decision_policy_id emitted in events: "bremen_threshold_v1"

feature_artifact_prediction.py (legacy prediction path):
  TRIAGE_RECOMMENDED = "MRI_RECOMMENDED"
  TRIAGE_RULE_OUT = "MRI_RULE_OUT"

inference_handler.py (legacy inference path):
  TRIAGE_RECOMMENDED = "MRI_RECOMMENDED"
  TRIAGE_RULE_OUT = "MRI_RULE_OUT"

decision_support.py (report wrapper):
  triage_recommendation carries MRI_RECOMMENDED or MRI_RULE_OUT
  recommendation_label uses display text built from triage value

report_bremen.py (report provider):
  Uses triage_recommendation field; compares to string "MRI_RECOMMENDED" and "MRI_RULE_OUT"
  Builds MRI continuation assessment text from triage value

workspace_ui.py (frontend):
  References triage_recommendation and displays it directly in HTML
  Uses triage value to choose CSS class for decision visualization

MRIRULEOUT ORIGIN

MRI_RULE_OUT was introduced in PR0039 (v0.1 schema rebaseline) as the
negative alternative to MRI_RECOMMENDED. It appears first in the plan at:
  .project-memory/pr/0039-inference-integration/PLAN.md line 286:
    "triage_recommendation": str,  # "MRI_RECOMMENDED" or "MRI_RULE_OUT"

It was subsequently implemented as TRIAGE_RULE_OUT = "MRI_RULE_OUT" in
feature_artifact_prediction.py, inference_handler.py, and workflow_bremen.py.
It was never sourced from training labels. It was never approved through
a product decision gate. It was assumed as the inverse of MRI_RECOMMENDED.

The string "MRI_RULE_OUT" implies that MRI follow-up has been ruled out.
This is stronger language than the controlled decision-support scope permits.
The product question is "Should the patient continue to MRI?" The negative
outcome should indicate that continuation to MRI may not be indicated, not
that it has been definitively ruled out.

CLASS ORDER

The model package stores coef, scaler_mean, scaler_scale, imputer_statistics.
These are numerical arrays. No class_labels field exists.
The inference in workflow_bremen.py computes:
  logit = dot(coef, scaled) + intercept
  prob = 1.0 / (1.0 + exp(-logit))
  prediction = 1 if prob >= threshold else 0
  triage = MRI_RECOMMENDED if prob >= threshold else MRI_RULE_OUT

The positive class (prediction=1) maps to MRI_RECOMMENDED.
The negative class (prediction=0) maps to MRI_RULE_OUT.
Class order is implicit in the threshold comparison, not stored in the package.
The training data labels (BENIGN/CANCER mapped to 0/1) are not directly
related to the MRI continuation decision code.

THRESHOLD SOURCE

The threshold is loaded from the model package:
  plr = self._model_package["portable_logreg"]
  threshold = float(plr["threshold"])

The threshold is stored in the portable_logreg sub-dict as a float.
It was computed during training via threshold calibration and published
with the model package. The numerical value of the threshold is not changed
by this PR. Only the vocabulary around it is reconciled.

DECISION CONTRACT

Plan one explicit Bremen decision contract implemented as a dataclass or
simple namespace in a new file. The contract defines:

  workflow_id = "bremen"
  decision_policy_id = "bremen_threshold_v1"
  decision_policy_version = "v0.1"
  decision_code: str  (canonical machine-readable code)
  decision_display_name: str  (human-readable label)
  decision_explanation: str  (one-line clinical context)
  score: float
  threshold: float
  positive_class: str  (meaning of prediction=1)
  class_labels: dict[int, str]
  scientifically_certified: bool
  technical_demo_only: bool

The decision contract is the single source of truth for all decision
vocabulary. Every surface (API, events, reports, UI, execution trace)
must derive its vocabulary from this contract. No surface may define
its own decision vocabulary constants.

MACHINE CODES

Machine codes and display text are separate.

Canonical machine codes (to be approved):
  Positive: CONTINUE_MRI
  Negative: MRI_REVIEW_DEFER

These are the stable, versioned values suitable for API, events, audit,
and internal use. They must not change without a versioned policy update.

Legacy machine code:
  MRI_RULE_OUT

The legacy value is treated as a deprecated alias only. It is never the
canonical value. During a compatibility period, the API may accept
MRI_RULE_OUT as input and map it to MRI_REVIEW_DEFER. Output APIs
return the canonical value.

DISPLAY TEXT

Display text is controlled human-facing wording. Current display text:

Current positive display text: "Based on the model output, MRI follow-up
may be recommended for this patient." (from decision_support.py)

Current negative display text: "Based on the model output, MRI follow-up
may not be indicated for this patient." (from decision_support.py)

These display texts are already within the decision-support scope. They
do NOT claim cancer is ruled out. The plan retains these display strings
but updates the machine codes that drive them. The display text is driven
by decision_code, not by a separately maintained string literal comparison.
The display text may change in the future without changing the machine code.

HUMAN DECISION GATE

Source inspection establishes current behavior. It does not establish
approved product vocabulary. The implementation may proceed only after
the authorized product or clinical owner approves:

  Canonical positive machine code: recommended CONTINUE_MRI
  Canonical negative machine code: recommended MRI_REVIEW_DEFER
  Positive display text: current text retained ("may be recommended")
  Negative display text: current text retained ("may not be indicated")
  Compatibility treatment of MRI_RULE_OUT: deprecated alias
  Decision-policy identifier: bremen_threshold_v1
  Decision-policy version: v0.1

This is a planning recommendation, not an approved decision. The
implementation must wait for the decision gate to close. The plan
provides a recommended baseline grounded in source evidence. The
approved values may differ from this recommendation.

DECISION RECORD

Create a plain-text decision record during implementation.

Path: .project-memory/decisions/bremen-decision-vocabulary-v0_1.txt

Contents:
  Decision status: pending approval
  Approver role: product owner or clinical owner
  Approval date: to be filled
  Clinical question: Should the patient continue to MRI?
  Canonical positive machine code: CONTINUE_MRI (recommended)
  Canonical negative machine code: MRI_REVIEW_DEFER (recommended)
  Positive display text: current text retained
  Negative display text: current text retained
  Legacy aliases: MRI_RULE_OUT (deprecated)
  Decision-policy ID: bremen_threshold_v1
  Decision-policy version: v0.1
  Training source SHA: from training pipeline main branch
  Runtime source SHA: 4c1e32fd8df02541ac9b04c6e509f858225aa13c
  Compatibility policy: MRI_RULE_OUT mapped to MRI_REVIEW_DEFER
  Prohibited wording: "cancer ruled out", "no disease", "safe discharge",
    "no biopsy needed", "no further clinical review required", "diagnosis"
  Scientific boundary: controlled decision support, not autonomous medical decision

The decision record must not claim approval until approval has actually
been supplied.

POLICY OWNERSHIP

bremen-training-pipeline owns:
  Training labels (BENIGN/CANCER/NORMAL)
  Positive class definition
  Threshold provenance
  Training decision-policy metadata
  Class order in stored model

Bremen runtime owns:
  Validated interpretation of the promoted model package
  Runtime policy enforcement
  Public API projection
  Report delivery
  UI presentation
  Decision vocabulary mapping from numerical prediction to machine code

The approved decision record owns cross-surface canonical terminology.

The frontend must not invent or reinterpret machine codes. The report
renderer must not redefine the decision. The API serializer must not
derive terminology from score alone when a provider decision already
exists. The runtime must not silently override training metadata
without an explicit versioned adaptation contract.

MODEL PACKAGE METADATA

The current portable_logreg package does not contain:
  class_labels: dict[int, str]
  positive_class: str
  decision_policy_id: str
  decision_policy_version: str
  feature_schema_version (available at runtime configuration, not in package)

The plan adds a minimal metadata adapter in the runtime that maps the
model package to the expected decision policy. No changes to the model
package on S3. No retraining. The adapter maps:

  model package threshold -> runtime threshold
  model package coef/intercept -> runtime coefficients
  model package nothing -> class_labels injected by runtime decision contract
  model package nothing -> decision_policy_id injected by runtime
  model package nothing -> decision_policy_version injected by runtime

This adapter lives in the Bremen provider and is applied during
package adaptation (existing adapt_model_package function may be
extended or a new decision_policy_adapter added).

BACKWARD COMPATIBILITY

Existing consumers of decision vocabulary:

  API responses: triage_recommendation field in completed result
  Job API: workflow_runs[].result_summary.triage_recommendation
  Reports: triage_recommendation in payload
  Events: decision_code in runtime.decision.completed details
  Execution trace: safe_summary fields
  Workspace UI: triage_recommendation displayed in pipeline and decision viz
  Tests: string comparisons against MRI_RULE_OUT and MRI_RECOMMENDED
  Docs: api_contract.md, workspace_contract.md, operator notes

Migration strategy:

  Phase 1 (this PR): Add canonical decision_code alongside legacy
    triage_recommendation. Both fields present in responses. Both
    values are derived from the same decision object. No contradictory
    values. The legacy triage_recommendation still appears but its
    value is changed to the canonical machine code (CONTINUE_MRI or
    MRI_REVIEW_DEFER) when the approvee vocabulary is approved. The
    legacy field name is preserved to avoid breaking API shape.
    Phase 1 must not introduce two contradictory fields.

  Phase 2 (future PR, after approval): Remove triage_recommendation
    legacy field. Keep only canonical decision_code. Or keep both
    but with explicit deprecation header.

  The plan requires that during the compatibility period, exactly
  one authoritative decision object produces both the canonical
  decision_code and any legacy-format fields. No surface may
  independently derive the decision.

  The legacy value MRI_RULE_OUT is replaced with MRI_REVIEW_DEFER
  in all runtime output. If a client sends MRI_RULE_OUT in a
  request, it is treated as equivalent to MRI_REVIEW_DEFER.

  All existing tests that compare against MRI_RULE_OUT are updated
  to accept both the canonical and the legacy value as valid,
  or are changed to canonical only depending on the test purpose.

API AND SCHEMA

The existing response schema carries:
  triage_recommendation (str)
  decision_support_report (dict)

The plan adds:
  decision_code (str): canonical machine-readable code
  decision_display_name (str): human-readable label
  decision_policy_id (str): which policy was applied
  decision_policy_version (str): version of the policy

These fields appear in:
  WorkflowResult payload
  Job API response (workflow_runs[*].result_summary)
  Report envelope payload
  Event details (runtime.decision.completed)

The decision_code and the legacy triage_recommendation are derived
from the same decision object. They are never contradictory. If the
score is above threshold, decision_code = CONTINUE_MRI and
triage_recommendation = CONTINUE_MRI. If below threshold,
decision_code = MRI_REVIEW_DEFER and triage_recommendation =
MRI_REVIEW_DEFER. The legacy triage_recommendation field keeps
its name but carries the canonical value.

Unknown decision codes: If a decision code is not recognized
(should not happen in practice because the code is always derived
from the known threshold comparison), the response renders
decision_code = UNKNOWN and triage_recommendation = UNKNOWN.

Unavailable decision: If the workflow did not complete (failed,
unavailable, configuration_required), decision_code and
triage_recommendation are both null.

EVENTS AND EXECUTION TRACE

The event runtime.decision.completed currently emits:
  decision_policy_id = "bremen_threshold_v1"
  decision_code = triage (currently MRI_RECOMMENDED or MRI_RULE_OUT)

After this PR, decision_code is the canonical value (CONTINUE_MRI
or MRI_REVIEW_DEFER). The events schema version is not bumped
because the field name and structure are unchanged. Only the
enumeration of valid decision_code values changes.

The execution trace safe_summary for the decision_completed stage
reflects the canonical decision_code.

Events must not emit conflicting decision vocabularies. Machine
code appears only in the decision_code details field. Display text
is not emitted in events.

REPORTS

The report_bremen.py provider currently generates triage-driven
display text.

After this PR, the report renderer receives the canonical decision
object (with decision_code, display_name, explanation). The report
payload includes decision_code alongside the existing
triage_recommendation (both canonical). The human-readable
assessment text continues to use the existing controlled language
("may be recommended" / "may not be indicated"). The assessment
text is determined by the decision_code, not by a separate string
comparison on a hardcoded value.

No diagnostic wording. No cancer-ruled-out claim. No biopsy
recommendation. Scientific certification flag remains visible.

FRONTEND BOUNDARY

The workspace UI currently reads triage_recommendation from
workflow result_summary and displays it directly. It also uses
the value to select CSS class for decision visualization.

After this PR, the UI reads decision_code (canonical) from the
result summary. The display text shown to the user is derived
from the decision_code using an allowlisted mapping. The UI does
not independently interpret or override the decision code.

Frontend changes are limited to:
  Updating the JS variable name (triage_recommendation ->
  decision_code) where either field is present
  Adding decision_display_name to the rendered output
  Removing hardcoded MRI_RULE_OUT string references from JS
  Updating CSS class logic to work with canonical codes

No layout changes. No new panels. No model selector. No
animations. No presentation mode. This is vocabulary reconciliation
only, not the PR0082 control room.

NO NUMERICAL CHANGE

This PR must not change:
  Model coefficients
  Model artifact
  Feature calculation
  Preprocessing
  Class order
  Threshold value
  Threshold selection methodology
  Probability calculation
  Scientific performance claims

The task is terminology and contract reconciliation only.
If source inspection showed that vocabulary drift is caused by a
deeper class-order or threshold mismatch, that would be a blocker.
Inspection confirms the drift is terminology only. The numerical
path is prob >= threshold -> positive. prob < threshold -> negative.
Only the string name of the negative outcome changes.

TESTING

Behavioral tests planned for:

  Training source vocabulary evidence: Verify that training pipeline
    output does not contain MRI_RULE_OUT. Verify that training labels
    are BENIGN/CANCER/NORMAL, not continuation vocabulary. (source-grep
    supplement)

  Runtime vocabulary inventory: Verify every file that defines or
    references MRI_RULE_OUT. All must be updated to canonical vocabulary.
    (source-grep supplement)

  Canonical positive decision: workflow_bremen with prob >= threshold
    produces decision_code = CONTINUE_MRI (or approved value).
    triage_recommendation (legacy) equals decision_code.

  Canonical negative decision: workflow_bremen with prob < threshold
    produces decision_code = MRI_REVIEW_DEFER (or approved value).
    triage_recommendation (legacy) equals decision_code.

  Threshold boundary:
    Score exactly equal to threshold produces positive class.
    Score below threshold produces negative class.
    Numerical behavior unchanged (same prediction 0/1).

  No contradictory fields: In every response (job API, events, reports),
    decision_code and triage_recommendation have the same value.

  Job API output: workflow_runs[*].result_summary contains
    decision_code, decision_display_name, decision_policy_id.

  Legacy prediction API output: CompletedResult contains
    decision_code alongside triage_recommendation.

  Event output: runtime.decision.completed details contain
    decision_code in canonical form.

  Report output: Report payload contains decision_code and
    decision_display_name. Assessment text uses controlled language.

  Workspace output: UI renders decision_display_name, not raw
    MRI_RULE_OUT.

  Unknown decision code: Not possible in practice, but the code
    handles UNKNOWN gracefully.

  Missing policy metadata: If decision_policy_id is not configured,
    the decision still produces canonical codes (the code logic is
    built into the provider, not fetched dynamically).

  Bremen and Aramis separation: No decision vocabulary from Bremen
    leaks into Aramis. No Aramis vocabulary leaks into Bremen.

  Privacy allowlists: No patient identifiers, feature values, or
    model parameters in decision output.

  No diagnostic wording: Report assessment text uses "may be
    recommended" / "may not be indicated" only.

  Backward compatibility: triage_recommendation field preserved
    with canonical value. MRI_RULE_OUT not present in output.

  Full regression: All existing tests pass with updated values.

DOCUMENTATION

Update ROADMAP.md:
  Add this PR as current milestone.
  Document that PR0082 is blocked until vocabulary reconciliation
  is approved and implemented.

Update docs/workspace_contract.md:
  Document canonical machine codes.
  Document decision_policy_id and version.
  Document legacy alias policy.
  Document the one-decision-object rule.

Update or confirm docs/api_contract.md:
  Document decision_code field in completed result.
  Document that triage_recommendation is preserved with canonical value.

Update or confirm docs/release_readiness_operator_notes.md:
  Update any MRI_RULE_OUT reference to canonical vocabulary.

Create .project-memory/decisions/bremen-decision-vocabulary-v0_1.txt:
  Plain text decision record.
  Not claiming approval until approval is supplied.
  Recommended values documented.

PR0082 BOUNDARY

PR0082 becomes: Bremen Investor Control Room

PR0082 may begin only after:
  Canonical decision vocabulary is approved via human decision gate.
  Runtime and reports use the approved contract.
  Events use the approved contract.
  Frontend no longer depends on MRI_RULE_OUT unless explicitly
  retained as a deprecated compatibility alias.

PR0082 scope remains:
  One real Bremen model.
  Default visible redesign.
  Central real execution pipeline.
  Docked structured live-event panel.
  Professional investor presentation.
  No model selector required.

LATER PR BOUNDARIES

This PR must not absorb:
  XRD-preprocessing parity work
  Paper-reference versus product-contract investigation
  AUC investigation
  Model promotion catalog
  Multiple model variants
  Aramis integration

Those remain later independent work.

EXPECTED FILES

New files:
  src/bremen/api/decision_contract.py
    BremenDecisionContract dataclass or namespace.
    Single authoritative source for machine codes, display text,
    policy identity, and vocabulary mapping.
    Includes legacy alias map from MRI_RULE_OUT to canonical.

  .project-memory/decisions/bremen-decision-vocabulary-v0_1.txt
    Plain text decision record.
    Pending approval status.

  tests/test_bremen_decision_vocabulary.py
    Behavioral tests for canonical decision codes.
    Threshold boundary tests.
    No contradictory fields tests.
    Legacy compatibility tests.
    Privacy and diagnostic-wording checks.

Modified files:
  src/bremen/api/workflow_bremen.py
    Replace TRIAGE_RULE_OUT constant with canonical value.
    Replace triage assignment to use decision contract.
    Add decision_code, decision_display_name, decision_policy_id,
    decision_policy_version to result payload.
    Remove hardcoded MRI_RULE_OUT string.

  src/bremen/api/workflow_provider.py
    Add decision_code, decision_display_name, decision_policy_id,
    decision_policy_version to WorkflowResult or result contract.

  src/bremen/api/feature_artifact_prediction.py
    Replace TRIAGE_RULE_OUT constant.
    Update triage assignment.

  src/bremen/api/inference_handler.py
    Replace TRIAGE_RULE_OUT constant.
    Update triage assignment.

  src/bremen/api/decision_support.py
    Replace MRI_RULE_OUT string comparison.
    Use canonical decision_code for display text selection.
    Recommendation_label controlled text unchanged.

  src/bremen/api/report_bremen.py
    Replace MRI_RULE_OUT string comparison.
    Use canonical decision_code for assessment text.
    Report payload includes canonical decision fields.

  src/bremen/api/event_schema.py
    No schema version bump. The decision_code field in event
    details carries canonical values.

  src/bremen/api/job_api_handler.py
    Ensure job response includes decision_code in result_summary.

  src/bremen/api/lifecycle_contracts.py
    Update DecisionOutput decision_code type documentation.

  src/bremen/workspace_ui.py
    Update JavaScript to read decision_code and
    decision_display_name instead of triage_recommendation.
    Remove hardcoded MRI_RULE_OUT references from JS logic.
    Update CSS class mapping.

  ROADMAP.md
    Add current milestone section for vocabulary reconciliation.
    Document PR0082 blocked until approval.

  docs/workspace_contract.md
    Document canonical machine codes.
    Document legacy alias policy.

  docs/api_contract.md
    Document decision_code field.
    Document triage_recommendation preserved with canonical value.

Tests updated:
  test_bremen_workflow_bremen.py
    Triaging comparisons against MRI_RULE_OUT updated.
    Tests verify canonical decision_code.

  test_bremen_decision_support_output.py
    MRI_RULE_OUT references updated.

  test_bremen_api_skeleton.py
    MRI_RECOMMENDED references preserved or updated as needed.

  test_bremen_execution_showcase.py
    MRI_RULE_OUT reference updated.

  test_bremen_demo_evidence.py
  test_bremen_demo_presentation.py
  test_bremen_predictions.py
  test_bremen_production_smoke.py
  test_bremen_api_server.py
  test_bremen_inference_integration.py
    Update MRI_RULE_OUT assertions to canonical values.
    Add decision_code assertions where applicable.

Files NOT modified:
  src/bremen/training/  (no runtime changes needed in training code)
  src/bremen/inference.py  (numerical computation unchanged)
  src/bremen/modeling.py  (legacy research draft, no runtime impact)
  src/bremen/api/xrd_normalization.py
  src/bremen/api/h5_layouts.py
  src/bremen/api/event_store.py
  src/bremen/api/runtime_plugin.py
  src/bremen/api/execution_context.py
  src/bremen/api/execution_trace.py
  src/bremen/api/report_provider.py
  src/bremen/api/report_aramis.py
  src/bremen/api/model_state.py
  src/bremen/api/schemas.py
  src/bremen/api/job_models.py
  All Docker, CI/CD, Terraform files

RISKS

Risk 1: Training labels may be internal rather than approved public
vocabulary. Mitigation: The training pipeline produces numerical
output only. Decision vocabulary is a runtime construct. This
reconciliation makes the runtime vocabulary explicit, versioned,
and subject to product approval.

Risk 2: MRI_RULE_OUT may be consumed by an undocumented client.
Mitigation: The triage_recommendation field is preserved (with
canonical value) during the compatibility period. No existing
API shape is removed. Legacy alias maps MRI_RULE_OUT to canonical.

Risk 3: The current model package may lack decision-policy metadata.
Mitigation: Decision-policy metadata is injected by the runtime
adapter. No model package changes needed. The adapter maps the
known threshold and class order to the decision contract.

Risk 4: Class order may be implicit. Mitigation: Confirmed that
prediction=1 maps to above-threshold (positive for MRI continuation)
and prediction=0 maps to below-threshold (negative). Class order
is implicit in the threshold comparison, not in model coefficients.

Risk 5: Reports and API may derive decisions independently.
Mitigation: Both derive from the same decision object produced
by the provider. The decision contract is the single source of truth.

Risk 6: A label-only change may hide a deeper scientific mismatch.
Mitigation: The task is specifically vocabulary reconciliation.
If any deeper mismatch is discovered during inspection, it must
be elevated as a blocker. No such mismatch was found.

Risk 7: Legacy compatibility may accidentally expose contradictory
fields. Mitigation: The canonical decision_code and the legacy
triage_recommendation both come from the same decision object.
They are guaranteed to be equal. Tests verify no contradictory
values.

Risk 8: Frontend fixtures may hardcode stale labels.
Mitigation: Every occurrence of MRI_RULE_OUT in tests, workspace_ui,
and docs is identified and updated.

STOP CONDITIONS

Stop planning with a blocker if:

The training source cannot be inspected. (Not a blocker: training
source is available locally. The remote training pipeline is not
needed because the committed training code contains no decision
vocabulary strings.)

The runtime decision source cannot be identified. (Not a blocker:
the decision source is clearly workflow_bremen.py.)

The current model class order cannot be established. (Not a blocker:
class order is explicit in the threshold comparison. prediction=1
is positive, prediction=0 is negative.)

The threshold source cannot be established. (Not a blocker:
threshold comes from model package portable_logreg.threshold.)

MRIRULEOUT cannot be traced to its source. (Not a blocker:
source is PR0039 planning docs and subsequent runtime constants.)

The drift reflects a class-order or threshold mismatch rather than
terminology only. (Not a blocker: inspection confirms it is
terminology only.)

An authoritative product or clinical owner is required but no
approval gate can be defined. (Not a blocker: the approval gate
is defined in the HUMAN DECISION GATE section. Implementation
waits for approval.)

The implementation would require retraining. (Not required.)

The implementation would require changing numerical inference.
(Not required.)

The implementation would require Aramis terminology.
(Not required.)

The implementation would require the PR0082 UI redesign.
(Not required.)

Private artifacts or patient data would be required.
(Not required.)

ACCEPTANCE CRITERIA

Gate 1: Training vocabulary traced to exact source.
  Verified that training pipeline output is numerical only.
  No decision vocabulary strings in training code.

Gate 2: Runtime vocabulary traced to exact source.
  Every occurrence of MRI_RULE_OUT identified across 5 runtime files,
  tests, workspace UI, and documentation. All updated.

Gate 3: MRI_RULE_OUT origin identified.
  Origin traced to PR0039 planning. The value was a runtime construct
  never sourced from training labels.

Gate 4: Class order verified.
  prediction=1 maps to above-threshold (positive).
  prediction=0 maps to below-threshold (negative).
  No ambiguity.

Gate 5: Threshold source verified.
  Threshold comes from model package portable_logreg.threshold.
  No change to numerical value.

Gate 6: Numerical decision behavior preserved.
  prob >= threshold produces positive decision_code.
  prob < threshold produces negative decision_code.
  Same 0/1 prediction output.

Gate 7: Machine codes separated from display text.
  decision_code is stable, versioned, suitable for API/audit.
  decision_display_name is human-readable, non-diagnostic,
  controlled separately.

Gate 8: Canonical vocabulary requires explicit approval.
  Decision record created. Implementation waits for approval.
  Recommended values clearly labeled as recommendations.

Gate 9: Decision-policy identity is versioned.
  decision_policy_id = "bremen_threshold_v1".
  decision_policy_version = "v0.1".

Gate 10: Legacy compatibility is explicit.
  triage_recommendation field preserved with canonical value.
  MRI_RULE_OUT treated as deprecated alias.

Gate 11: API, jobs, events, reports, and UI use one decision object.
  DecisionContract is the single source of truth.
  No surface has its own decision vocabulary constants.

Gate 12: No contradictory decision fields.
  decision_code and triage_recommendation always equal.
  Tests verify this property.

Gate 13: No diagnostic or rule-out claim.
  Report assessment text uses "may be recommended" / "may not be
  indicated". No cancer-ruled-out claim.

Gate 14: Bremen and Aramis remain separate.
  Bremen decision contract does not affect Aramis.
  Aramis decision vocabulary (when implemented) is its own contract.

Gate 15: No xrd-preprocessing change.
  No preprocessing files modified.

Gate 16: No model change.
  No model artifact modified. No retraining.

Gate 17: No retraining.
  Training pipeline unchanged.

Gate 18: No Control Room redesign.
  No layout changes. No new panels. No animations.

Gate 19: Behavioral tests planned.
  All gates 1-14 have corresponding behavioral tests.

Gate 20: Full regression planned.
  All existing tests pass with updated values.

Gate 21: PR0082 is blocked until vocabulary reconciliation is
  approved and implemented.
  ROADMAP.md documents this dependency.

