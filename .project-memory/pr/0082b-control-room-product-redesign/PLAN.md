PLAN COMPLETE

PLAN FILE

.project-memory/pr/0082b-control-room-product-redesign/PLAN.md

HEAD

082b384d5379b920aa3f69013ecc57ce20d8d5d3

BRANCH

0082b-control-room-product-redesign

CURRENT UI FINDINGS

The current deployed UI was produced by PR0082a. Key findings:

GET /demo serves build_control_room_page from control_room_ui.py (994 lines).
  This is a single combined page with model info, container selection, pipeline,
  events, decision, and report link. It uses dark theme (background #0d1117).
  Model catalog and container catalog APIs exist. model_id and source_id are
  in the job contract. The control room is the only GET /demo experience.

No separate Start page exists. No separate Report page exists. No URL-based
model_id persistence. No light theme. No design-system spacing, color palette,
or typography roles from the authoritative specification.

GET /demo/workspace serves build_workspace_page from workspace_ui.py (1265 lines).
  This is the legacy technical workspace (PR0077/PR0078). Not connected to
  the new control-room or model-selection flow.

GET /demo/api/models serves the model catalog (model_catalog.py, PR0082a).

Existing API routes all serve the PR0082a contracts: /health, /model/version,
/predictions, /demo/api/jobs, /demo/api/jobs/{job_id}/events,
/demo/api/jobs/{job_id}/events/stream, /demo/api/jobs/{job_id}/reports,
/demo/api/h5/containers, /demo/api/stage, /demo/api/h5/analyze.

DESIGN SPEC COMMIT

BREMEN_DESIGN_SPEC_v1.md is the visual source of truth. It is committed under
docs/design/BREMEN_DESIGN_SPEC_v1.md during this PR. The design spec document
contains the authoritative color tokens, typography roles, spacing scale,
radii, shadows, component CSS, layout rules, and status rail specifications.
All implementation must derive from that document. The PLAN below summarizes
the spec but the committed .md file is the final authority.

ROUTES

The route plan uses server.py do_GET dispatch. Three routes change and one new
route is added. Backend job, model, SSE, decision, and report contracts remain
unchanged.

server.py route dispatch ordering:
  1. exact /health
  2. exact /model/version
  3. exact /predictions plus /predictions/{uuid} pattern
  4. exact /demo (Start page)
  5. /demo/control-room and /demo/control-room/{job_id}
  6. /demo/report/{job_id}
  7. /demo/workspace and /demo/workspace/{job_id}
  8. /demo/api/* endpoints
  9. 404 fallback

This ordering prevents route conflicts. /demo/control-room/ matches before
/demo/workspace/. /demo/report/ matches before /demo/workspace/.

GET /demo -> start_page_ui.py owns this route
  Serves the Start page. Model selection from PR0082a model catalog.
  Carries workflow_id and model_id in the rendered destination URL
  (/demo/control-room?workflow_id=bremen&model_id=bremen-current).

GET /demo/control-room -> control_room_ui.py owns this route and its deep links
  Serves the Control Room page. Accepts optional query parameters
  workflow_id and model_id. When absent, loads default from catalog.
  The page header shows the selected model as a link back to GET /demo.

GET /demo/control-room/{job_id} -> deep-link within control room route.
  Loads the control room with a preselected job.

GET /demo/report/{job_id} -> report_ui.py owns this route
  Serves the product-grade Report page. Reads job data from
  GET /demo/api/jobs/{job_id} and report data from
  GET /demo/api/jobs/{job_id}/reports/bremen.

GET /demo/workspace -> workspace_ui.py preserved as legacy technical workspace.
GET /demo/workspace/{job_id} -> unchanged.

Preserved with no changes:
  GET /health, GET /model/version, POST /predictions, GET /predictions/{job_id}
  GET /demo/api/models, GET /demo/api/evidence
  GET /demo/api/h5/containers, POST /demo/api/h5/containers
  POST /demo/api/stage, POST /demo/api/h5/analyze
  GET /demo/api/jobs, POST /demo/api/jobs
  GET /demo/api/jobs/{job_id}, GET /demo/api/jobs/{job_id}/events
  GET /demo/api/jobs/{job_id}/events/stream
  GET /demo/api/jobs/{job_id}/reports
  GET /demo/api/jobs/{job_id}/reports/{workflow_id}

Legacy redirect: GET /demo (previous combined page) is replaced by the Start
page. The old combined behavior is no longer accessible at /demo. Users can
reach the Control Room at /demo/control-room after selecting a model.

DESIGN SYSTEM

All tokens are from the authoritative specification BREMEN_DESIGN_SPEC_v1.md.
No other colors, spacing, radii, shadows, or typography may be used.

Base colors:
  --bg-page: #F7F8F8
  --bg-surface: #FFFFFF
  --text-primary: #16202A
  --text-secondary: #5B6570
  --accent: #1F6F6B
  --border: #E3E7E6

Status colors:
  --status-available: #2E7D5B
  --status-pending: #B8894A
  --status-unconfigured: #9AA3A8
  --status-error: #C1483D

Tint colors:
  --tint-accent: #F1F5F4
  --tint-pending: #FBF3E9
  --tint-error: #FBEEEC

No additional colors. No #0969da, #1a7f37, #cf222e, #9a6700, #d0d7de, #656d76,
#1f2328, or any other color outside the specification. No gradients. No pink.
No rose. No blue accent system. No GitHub palette.

Typography:
  Font stack: system font (-apple-system, BlinkMacSystemFont, "Segoe UI",
    Roboto, Helvetica, Arial, sans-serif).
  Six size values: 32px, 22px, 17px, 14px, 13px, 11px.
  No other sizes.
  h1: 32px, weight 700.
  h2: 22px, weight 600.
  h3: 17px, weight 600.
  Body: 14px, weight 400.
  Small/caption: 13px, weight 400.
  Tiny/identifier: 11px, weight 400, monospace for code values.

Spacing scale: 4px, 8px, 12px, 16px, 24px, 32px, 48px, 64px.
  No 20px, 40px, or any other spacing values.

Radii:
  Card radius: 10px.
  Pill radius: 999px.
  Primary button radius on Start page: 10px.
  No 6px radius.

Shadow:
  Only two shadow values are allowed:
    0 1px 2px rgba(22,32,42,0.04)
    0 1px 8px rgba(22,32,42,0.03)
  No other shadow values.

Status rails:
  State-bearing cards: 3px left rail.
  Event and history rows: 2px left rail.

Disabled opacity: Model-card content uses opacity reduction for disabled
state. The status rail retains full opacity. This ensures the rail color
is always visible regardless of disabled state.

Field/value gap: 16px minimum gap between label and value columns.

Page maximum width: 1440px.
Desktop side padding: 32px.

START PAGE

Default route: GET /demo. Owned by start_page_ui.py.

The Start page loads the model catalog from GET /demo/api/models on page load.
It renders real configured models. Uses only the approved design tokens.

Page centered, max-width 1440px, 32px side padding.
Background: --bg-page (#F7F8F8).
Cards: --bg-surface (#FFFFFF) with 1px solid --border (#E3E7E6).
Selected card: 2px solid --accent (#1F6F6B).
Disabled card: content uses reduced opacity. Status rail retains full opacity.
Primary CTA button: background --accent (#1F6F6B), text white, border-radius
  10px, padding 12px 32px, font-weight 600, font-size 17px.
Primary button disabled: background --status-unconfigured (#9AA3A8).
All text: --text-primary (#16202A) or --text-secondary (#5B6570) as
  appropriate.

Header bar with Bremen wordmark and "Should the patient continue to MRI?"
Model selection section with radio-button card layout, exactly one model
selectable.

Model contract: real PR0082a GET /demo/api/models with model_id. No
ModelVariant, no model_variant_id, no list_model_variants, no workflow model
endpoints, no promotion, no comparison, no PR0085 architecture. Only the
existing PR0082a model_id contract.

For each available model: card with display_name, model_version,
feature_schema_version, decision_policy_id. Radio input. Accessible selected
state with accent border.

For unavailable models: card with disabled radio, content opacity reduced,
status rail at full opacity, visible reason text.

When zero models configured: message with CTA disabled.
When one model available: pre-selected, CTA enabled.
When multiple available: user must pick one.

Selected model_id carried to Control Room URL:
  /demo/control-room?workflow_id=bremen&model_id=bremen-current

CONTROL ROOM

Route: GET /demo/control-room. Owned by control_room_ui.py.

Three-column layout:
  Left column: 320px fixed width.
  Center column: flexible, minimum 480px.
  Right column: 360px fixed width.

Page max-width: 1440px, 32px side padding.
Background: --bg-page (#F7F8F8).
All cards: --bg-surface (#FFFFFF), 1px solid --border (#E3E7E6), radius 10px,
  card shadow: 0 1px 2px rgba(22,32,42,0.04), 0 1px 8px rgba(22,32,42,0.03).
State-bearing cards: 3px left rail.
Text: --text-primary (#16202A) for primary, --text-secondary (#5B6570) for
  secondary.

Page header:
  Bremen wordmark.
  "Should the patient continue to MRI?"
  Selected model name as link back to Start page.
  Readiness badges using status colors.

Left column (320px):
  Selected model info as field/value table. Label column 160px fixed,
    16px gap. Monospace values, ellipsis overflow with title tooltip.
  Container catalog with list of technical containers from
    GET /demo/api/h5/containers. No filename-based filtering. No removal of
    containers whose name contains "Aramis". Server-side validation only.
    Unsupported file extensions, missing objects, and oversize conditions are
    rejected by the server, not by frontend filename pattern.
  Each container as card, selected state with 2px --accent border.
  aria-current="true" on selected.
  Upload New H5 File as secondary action.
  Primary Analyze button: full-width, background --accent (#1F6F6B), white text,
    disabled state using --status-unconfigured.

Center column (flexible):
  Execution pipeline using approved colors.
  Each stage: 3px status rail, icon, label, optional duration.
  Upcoming: rail --border (#E3E7E6).
  Active: rail --accent (#1F6F6B), background --tint-accent (#F1F5F4).
  Completed: rail --status-available (#2E7D5B).
  Failed: rail --status-error (#C1483D), background --tint-error (#FBEEEC).
  Terminal state reconciled with job overall_status.
  Decision summary card after completion: recommended headline using PR0081
    approved display_name, score bar when data exists, "Open report" button
    with --accent.

Right column (360px):
  Job History: max 280px height, independent scrolling. 2px rail on rows.
  Live Events: empty state at fixed height 120px, centered "Analysis events
    will appear here." The 120px value is a fixed height for the collapsed
    empty state only. When events arrive, the container expands with flex-grow
    to fill remaining space. Not min-height -- the empty state is exactly
    120px fixed. The parent flex container handles expansion.
  Events during analysis: newest at bottom, auto-scroll, pause/follow. 2px
    status rails per event row. Max 200 DOM rows. No full-page rerender.

REPORT PAGE

Route: GET /demo/report/{job_id}. Owned by report_ui.py.

Uses the shared 1440px content system. Internal readable column uses existing
spacing rules (32px padding, cards at --bg-surface, --border borders).

No 960px maximum. Content is centered within the shared 1440px layout with
internal padding for a readable column width.

Top recommendation card:
  Background --bg-surface, border 1px --border, radius 10px, card shadow.
  Recommendation headline: approved PR0081 display_name.
  Not raw machine code as primary headline.
  Score bar when authoritative data exists (p_mri_needed and threshold).
  No fabricated reliability, data-quality, or measurement-quality statements.
  Do not render Reliability or data-quality captions unless those values
    already exist in the authoritative report API response.
  Do not add sensitivity or specificity fields in PR0082b.
  Technical-demo notice using --tint-pending background and --status-pending
    accent.

Field/value panels:
  Label column 160px fixed, 16px gap, monospace values, ellipsis overflow.
  Model panel: model, version, feature_schema, decision_policy, certification.
  Audit panel: job_id, workflow_id, created_at, completed_at, source, duration.

"View technical trace" expandable section using same field layout.
  Shows stage-by-stage trace from execution_traces.
  Do not expose BREMEN_MODEL_URI, S3 URIs, bucket names, object keys,
    environment values, or local paths in Technical Trace.
  Only safe stage metadata (label, status, duration) is shown.
  Not expanded by default.

Header: Bremen wordmark, back to Control Room link.

MODEL SELECTION

Use the real PR0082a model_id contract only. GET /demo/api/models with model_id.
No ModelVariant, no model_variant_id, no list_model_variants, no workflow model
endpoints, no promotion, no comparison, no PR0085 architecture.
Exactly one model per job. Real configured models only. Unavailable models
shown as disabled with reason. URL-persistent selection.

PIPELINE

10 stages from PR0082a. Approved colors only. Active: --accent rail,
--tint-accent background. Completed: --status-available rail. Failed:
--status-error rail, --tint-error background. Upcoming: --border rail.
Terminal reconciliation with job overall_status. No fake completion.

LIVE EVENTS

Collapsed empty state: fixed height 120px (not min-height). The value 120px
is the fixed collapsed height. When events arrive, the parent flex container
allows the event list to expand with flex-grow. 2px rails using status colors.
200-row DOM limit. Auto-scroll with pause/follow.

CONTAINER CATALOG

All server-provided containers preserved. No filename-based inference. No
removal of containers whose name includes "Aramis". Server-side validation
is the only gate. Unsupported file extensions, missing objects, and oversize
conditions are server-rejected conditions, not frontend filename pattern rules.

STATE COVERAGE

All pages handle: loading, configured/unconfigured, available/unavailable,
running, completed, failed, reconnecting, expired. No blank panels.

RESPONSIVE

Desktop: three columns at 1440px+. Compact/tablet: vertical stacking
(header, controls, pipeline, history, events). Mobile: same stacking with
minimum padding. No horizontal overflow.

ACCESSIBILITY

Keyboard model/container selection. Radio semantics. aria-current. visible
focus. non-color status labels. aria-live on events. prefers-reduced-motion.
Semantic headings, lists. WCAG AA contrast with approved colors.

TESTING

Behavioral tests for Start page catalog/selection/URL, Control Room
layout/pipeline/events/report, Report page vocabulary/privacy, responsive
stacking, keyboard behavior, legacy API compatibility. No source-grep-only
tests for interaction behavior.

DOCUMENTATION

Commit BREMEN_DESIGN_SPEC_v1.md to docs/design/BREMEN_DESIGN_SPEC_v1.md as the
visual source of truth.

Update docs/workspace_contract.md with three-page journey, routes, design
tokens. Update ROADMAP.md with current milestone. PR0083 paused until
deployment and visual acceptance.

EXPECTED FILES

New:
  docs/design/BREMEN_DESIGN_SPEC_v1.md (design specification, source of truth)
  src/bremen/start_page_ui.py (owns GET /demo)
  src/bremen/report_ui.py (owns GET /demo/report/{job_id})

Modified:
  src/bremen/api/server.py (minimal route dispatch changes)
  src/bremen/control_room_ui.py (complete redesign with spec tokens, owns
    GET /demo/control-room and its deep links)
  docs/workspace_contract.md
  ROADMAP.md
  tests (additions)
  implementation-report.md (new)

Ownership summary:
  start_page_ui.py owns GET /demo
  control_room_ui.py owns GET /demo/control-room and its deep links
  report_ui.py owns GET /demo/report/{job_id}
  workspace_ui.py remains a preserved legacy technical workspace
  server.py owns minimal route dispatch changes

Unchanged backend contracts: all job, model, SSE, decision, report,
health, legacy analyze APIs.

Unchanged scientific runtime: no model artifacts, preprocessing, thresholds,
decision policy, vocabulary, or report schema changes.

BLOCKERS

None.

WARNINGS

The Live Events empty state uses fixed height 120px, not min-height. When
events arrive the flex container handles expansion. Implementation must
ensure the parent flex container has flex-grow: 1 on the event list so it
expands from the fixed 120px collapsed state.

Model contract is real PR0082a model_id only. Do not introduce ModelVariant,
model_variant_id, list_model_variants, or workflow model endpoints.

Disabled card content uses opacity reduction. The status rail retains full
opacity so the rail color is always visible.

Technical Trace must not expose BREMEN_MODEL_URI, S3 URIs, bucket names,
object keys, environment values, or local paths.

Do not render Reliability or data-quality captions unless those values
already exist in the authoritative report API response.

Do not add sensitivity or specificity fields in PR0082b.

No filename-based container filtering. Server-side validation is the gate.
Unsupported extensions, missing objects, and oversize are server errors.
