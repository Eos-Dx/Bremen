"""Bremen Report page — presentation-ready report with External/Internal tabs.

Owns GET /demo/report/{job_id}. Reads job data from
GET /demo/api/jobs/{job_id} and report data from
GET /demo/api/jobs/{job_id}/reports/bremen.

PR0082b — Bremen Product-Grade Demo Redesign.
PR0093 — Presentation-grade report renderer with Print/Save PDF.
PR0093B — Report contract and layout parity with promised report artifacts.
"""

from __future__ import annotations

import json as _json
from typing import Any

# ---------------------------------------------------------------------------
# Normalized report builders
# ---------------------------------------------------------------------------

REPORT_SCHEMA_VERSION = "v0.1"
INTERNAL_REPORT_SCHEMA_VERSION = "v0.1"


def _safe_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _dash(value: Any) -> str:
    if value is None:
        return "\u2014"
    if value == "":
        return "\u2014"
    return str(value)


def _get_path(obj: Any, *path: str, default: Any = None) -> Any:
    cur = obj
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return default if cur is None else cur


def _first_present(*values: Any, default: Any = None) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return default


def _checksum_prefix(value: Any, length: int = 8) -> str | None:
    if not value:
        return None
    text = str(value)
    if len(text) <= length:
        return text
    return text[:length]


def _report_id(job_id: str | None, generated_at: str | None) -> str:
    safe_job = str(job_id or "unknown").replace("-", "")[:8]
    safe_time = (
        str(generated_at or "unknown")
        .replace("-", "")
        .replace(":", "")
        .replace(".", "")
    )
    return f"{safe_time[:15]}_{safe_job}"


def _format_score(value: Any) -> Any:
    if isinstance(value, (int, float)):
        return round(float(value), 3)
    return value


def _normalize_signal_level(level: Any) -> str:
    if level in {"small", "moderate", "larger", "not_available"}:
        return str(level)
    return "not_available"


def _external_signal(signal: Any) -> dict:
    signal = _safe_dict(signal)
    return {
        "label": _dash(signal.get("label")),
        "difference_level": _normalize_signal_level(signal.get("difference_level")),
    }


def _internal_signal(signal: Any) -> dict:
    signal = _safe_dict(signal)
    return {
        "label": _dash(signal.get("label")),
        "feature_family": _safe_list(signal.get("feature_family")),
        "difference_level": _normalize_signal_level(signal.get("difference_level")),
    }


def build_external_report_json(report: dict) -> dict:
    """Return the External report JSON contract.

    This is the live API/report shape. It must match bremen_external_report.yaml
    by key structure, but values must come from real job/report data.
    """
    report = _safe_dict(report)
    payload = _safe_dict(report.get("payload"))
    ds = _safe_dict(
        _first_present(
            payload.get("decision_support_report"),
            report.get("decision_support_report"),
            report.get("decision_support"),
            default={},
        )
    )

    prediction = _safe_dict(
        _first_present(
            ds.get("prediction_summary"),
            payload.get("prediction_summary"),
            report.get("prediction_summary"),
            default={},
        )
    )

    model = _safe_dict(
        _first_present(
            ds.get("model_metadata"),
            payload.get("model_metadata"),
            report.get("model_metadata"),
            default={},
        )
    )

    input_summary = _safe_dict(
        _first_present(
            ds.get("input_summary"),
            payload.get("input_summary"),
            report.get("input_summary"),
            default={},
        )
    )

    symmetry = _safe_dict(
        _first_present(
            ds.get("symmetry_signals"),
            payload.get("symmetry_signals"),
            report.get("symmetry_signals"),
            default={},
        )
    )

    generated_at = _first_present(
        report.get("completed_at"),
        report.get("created_at"),
        payload.get("completed_at"),
        payload.get("created_at"),
        ds.get("generated_at"),
    )

    job_id = _first_present(
        report.get("job_id"), payload.get("job_id"), ds.get("job_id")
    )
    request_id = _first_present(
        report.get("request_id"), payload.get("request_id"), ds.get("request_id")
    )

    threshold_value = _first_present(
        prediction.get("threshold_value"),
        model.get("threshold_value"),
        ds.get("threshold_value"),
    )

    decision_policy_id = _first_present(
        prediction.get("decision_policy_id"),
        model.get("threshold_version"),
        ds.get("decision_policy_id"),
    )

    decision_policy_version = _first_present(
        prediction.get("decision_policy_version"),
        model.get("decision_policy_version"),
        ds.get("decision_policy_version"),
    )

    return {
        "output_type": "bremen_decision_support_report",
        "report_schema_version": _first_present(
            ds.get("report_schema_version"), REPORT_SCHEMA_VERSION
        ),
        "report_id": _first_present(
            ds.get("report_id"), _report_id(job_id, generated_at)
        ),
        "generated_at": generated_at,
        "job_id": job_id,
        "request_id": request_id,
        "patient_reference": _first_present(
            ds.get("patient_reference"), report.get("patient_reference"), default="\u2014"
        ),
        "analysis_author": "Bremen demo environment",
        "intended_use": (
            "MRI continuation decision support only. Not a diagnosis, not clinically "
            "validated, does not replace MRI, biopsy, radiologist, clinician, or clinical judgment."
        ),
        "limitations": [
            "Decision-support output only, not a diagnostic result.",
            "Not clinically validated.",
            "Does not replace MRI, biopsy, radiologist, clinician, or clinical judgment.",
        ],
        "model_metadata": {
            "model_version": _first_present(
                model.get("model_version"), report.get("model_version")
            ),
            "feature_schema_version": _first_present(
                model.get("feature_schema_version"), ds.get("feature_schema_version")
            ),
            "threshold_version": decision_policy_id,
            "threshold_value": threshold_value,
        },
        "input_summary": {
            "input_mode": _first_present(
                input_summary.get("input_mode"), report.get("input_mode"), default="\u2014"
            ),
            "explicit_refs_provided": _first_present(
                input_summary.get("explicit_refs_provided"), default=None
            ),
            "layout_category": _first_present(
                input_summary.get("layout_category"), default="\u2014"
            ),
        },
        "prediction_summary": {
            "p_mri_needed": _format_score(
                _first_present(
                    prediction.get("p_mri_needed"),
                    ds.get("p_mri_needed"),
                    report.get("score"),
                )
            ),
            "decision_code": _first_present(
                prediction.get("decision_code"),
                ds.get("decision_code"),
                report.get("decision_code"),
            ),
            "decision_display_name": _first_present(
                prediction.get("decision_display_name"),
                ds.get("decision_display_name"),
                default="Continue MRI evaluation",
            ),
            "decision_policy_id": decision_policy_id,
            "decision_policy_version": decision_policy_version,
            "qc_status": _first_present(
                prediction.get("qc_status"),
                ds.get("qc_status"),
                payload.get("qc_status"),
            ),
            "qc_flags": _safe_list(
                _first_present(
                    prediction.get("qc_flags"),
                    ds.get("qc_flags"),
                    payload.get("qc_flags"),
                    default=[],
                )
            ),
        },
        "decision_support": {
            "recommendation": _first_present(
                _get_path(ds, "decision_support", "recommendation"),
                prediction.get("decision_code"),
                ds.get("decision_code"),
            )
        },
        "symmetry_signals": {
            "schema_status": _first_present(
                symmetry.get("schema_status"), default="unavailable"
            ),
            "measurement_summary": _safe_dict(symmetry.get("measurement_summary")),
            "signals": [
                _external_signal(s) for s in _safe_list(symmetry.get("signals"))
            ],
            "note": _first_present(
                symmetry.get("note"),
                default="Reference statistics are not yet available; "
                "qualitative asymmetry calibration is pending.",
            ),
        },
    }


def build_internal_report_json(report: dict) -> dict:
    """Return the Internal report JSON contract.

    This shape follows bremen_internal_report.yaml. It is still safe for
    unauthenticated /demo/*: prefix checksum only, no raw values/cutoffs/PHI.
    """
    report = _safe_dict(report)
    payload = _safe_dict(report.get("payload"))
    external = build_external_report_json(report)

    supporting = _safe_dict(
        _first_present(
            payload.get("supporting_technical_evidence"),
            report.get("supporting_technical_evidence"),
            default={},
        )
    )
    detail = _safe_dict(
        _first_present(
            supporting.get("symmetry_signal_detail"),
            payload.get("symmetry_signal_detail"),
            report.get("symmetry_signal_detail"),
            default={},
        )
    )

    trace = _first_present(
        payload.get("execution_trace_summary"),
        report.get("execution_trace_summary"),
        report.get("execution_trace"),
        default={},
    )

    model_checksum_prefix = _checksum_prefix(
        _first_present(
            supporting.get("model_checksum_prefix"),
            payload.get("model_checksum_prefix"),
            report.get("model_checksum_prefix"),
            report.get("model_checksum"),
        )
    )

    return {
        "output_type": "bremen_internal_report",
        "report_schema_version": INTERNAL_REPORT_SCHEMA_VERSION,
        "report_id": external["report_id"],
        "generated_at": external["generated_at"],
        "job_identity": {
            "job_id": external["job_id"],
            "request_id": external["request_id"],
            "created_at": _first_present(
                report.get("created_at"), payload.get("created_at")
            ),
            "completed_at": _first_present(
                report.get("completed_at"), payload.get("completed_at")
            ),
            "status": _first_present(report.get("status"), payload.get("status")),
        },
        "model_and_plugin": {
            "model_version": _get_path(external, "model_metadata", "model_version"),
            "model_checksum_prefix": model_checksum_prefix,
            "feature_schema_version": _get_path(
                external, "model_metadata", "feature_schema_version"
            ),
            "plugin_id": _first_present(
                supporting.get("plugin_id"),
                payload.get("plugin_id"),
                default="bremen.default",
            ),
            "plugin_version": _first_present(
                supporting.get("plugin_version"),
                payload.get("plugin_version"),
                default="0.1",
            ),
            "report_schema_version": INTERNAL_REPORT_SCHEMA_VERSION,
        },
        "decision_policy": {
            "decision_code": _get_path(external, "prediction_summary", "decision_code"),
            "decision_policy_id": _get_path(
                external, "prediction_summary", "decision_policy_id"
            ),
            "decision_policy_version": _get_path(
                external, "prediction_summary", "decision_policy_version"
            ),
            "threshold_value": _get_path(external, "model_metadata", "threshold_value"),
            "qc_status": _get_path(external, "prediction_summary", "qc_status"),
            "qc_flags": _get_path(
                external, "prediction_summary", "qc_flags", default=[]
            ),
        },
        "input_summary": external["input_summary"],
        "execution_trace_summary": _normalize_execution_trace_summary(trace),
        "symmetry_signal_detail": {
            "schema_status": _first_present(
                detail.get("schema_status"),
                _get_path(external, "symmetry_signals", "schema_status"),
                default="unavailable",
            ),
            "measurement_summary": _safe_dict(
                _first_present(
                    detail.get("measurement_summary"),
                    _get_path(external, "symmetry_signals", "measurement_summary"),
                    default={},
                )
            ),
            "signals": [
                _internal_signal(s)
                for s in _safe_list(
                    _first_present(
                        detail.get("signals"),
                        _get_path(external, "symmetry_signals", "signals"),
                        default=[],
                    )
                )
            ],
            "note": _first_present(
                detail.get("note"),
                _get_path(external, "symmetry_signals", "note"),
                default="Named feature families shown for traceability. "
                "Raw magnitudes intentionally omitted.",
            ),
        },
    }


def _normalize_execution_trace_summary(trace: Any) -> dict:
    if isinstance(trace, list):
        out: dict[str, int] = {}
        for stage in trace:
            if not isinstance(stage, dict):
                continue
            name = stage.get("name") or stage.get("stage")
            duration = stage.get("duration_ms")
            if not name or duration is None:
                continue
            out[str(name)] = duration
        return out
    if isinstance(trace, dict):
        return {str(k): v for k, v in trace.items() if v is not None}
    return {}


# ---------------------------------------------------------------------------
# Design tokens (from BREMEN_DESIGN_SPEC_v1.md)
# ---------------------------------------------------------------------------

_CSS = """
:root {
  --bg-page: #F7F8F8;
  --bg-surface: #FFFFFF;
  --text-primary: #16202A;
  --text-secondary: #5B6570;
  --accent: #1F6F6B;
  --border: #E3E7E6;
  --status-available: #2E7D5B;
  --status-pending: #B8894A;
  --status-unconfigured: #9AA3A8;
  --status-error: #C1483D;
  --tint-accent: #F1F5F4;
  --tint-pending: #FBF3E9;
  --tint-error: #FBEEEC;
  --radius-card: 10px;
  --radius-pill: 999px;
  --shadow-card: 0 1px 2px rgba(22,32,42,0.04), 0 1px 8px rgba(22,32,42,0.03);
  --fs-32: 32px;
  --fs-22: 22px;
  --fs-17: 17px;
  --fs-14: 14px;
  --fs-13: 13px;
  --fs-11: 11px;
  --sp-4: 4px;
  --sp-8: 8px;
  --sp-12: 12px;
  --sp-16: 16px;
  --sp-24: 24px;
  --sp-32: 32px;
  --sp-48: 48px;
  --sp-64: 64px;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:var(--bg-page);color:var(--text-primary);line-height:1.5;-webkit-font-smoothing:antialiased}
.report-page{max-width:1440px;margin:0 auto;padding:var(--sp-32);min-height:100vh;display:flex;flex-direction:column}

/* Tab chrome */
.report-tabs{display:flex;align-items:center;gap:var(--sp-4);border-bottom:2px solid var(--border);margin-bottom:var(--sp-24);padding-bottom:0;position:relative}
.tab-btn{background:none;border:none;color:var(--text-secondary);font-size:var(--fs-14);font-weight:500;padding:var(--sp-12) var(--sp-24);cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px;transition:color 0.15s,border-color 0.15s}
.tab-btn:hover{color:var(--text-primary)}
.tab-btn[aria-selected="true"]{color:var(--accent);border-bottom-color:var(--accent);font-weight:600}
.tab-btn:focus-visible{outline:3px solid var(--accent);outline-offset:-3px;border-radius:2px}
.tab-spacer{flex:1}
.print-button{background:var(--accent);color:#FFFFFF;border:none;border-radius:var(--radius-card);padding:var(--sp-8) var(--sp-16);font-size:var(--fs-13);font-weight:600;cursor:pointer;white-space:nowrap}
.print-button:hover{opacity:0.9}
.print-button:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
@media(prefers-reduced-motion:reduce){.tab-btn{transition:none}}

/* Content area */
.report-content{flex:1;max-width:1100px;margin:0 auto;width:100%}
.tab-panel[hidden]{display:none}

/* Loading / error */
.report-loading{text-align:center;padding:var(--sp-64) var(--sp-24)}
.report-loading-spinner{display:inline-block;width:32px;height:32px;border:3px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin 0.8s linear infinite;margin-bottom:var(--sp-16)}
@keyframes spin{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){.report-loading-spinner{animation:none}}
.report-loading-text{font-size:var(--fs-14);color:var(--text-secondary)}
.report-error{text-align:center;padding:var(--sp-48) var(--sp-24);background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-card)}
.report-error-title{font-size:var(--fs-17);font-weight:600;color:var(--status-error);margin-bottom:var(--sp-8)}
.report-error-text{font-size:var(--fs-14);color:var(--text-secondary);margin-bottom:var(--sp-16)}

/* ============ REPORT DOCUMENT LAYOUT ============ */
.report-document{background:var(--bg-surface);padding:var(--sp-48) var(--sp-48);max-width:960px;margin:0 auto;border:1px solid var(--border);border-radius:var(--radius-card);box-shadow:var(--shadow-card)}

/* Header area */
.report-document .report-header{display:flex;align-items:flex-start;justify-content:space-between;padding-bottom:var(--sp-24);margin-bottom:var(--sp-24);border-bottom:1px solid var(--border);flex-wrap:wrap;gap:var(--sp-12)}
.report-document .report-brand{font-size:var(--fs-22);font-weight:600;color:var(--text-primary)}
.report-document h1{font-size:var(--fs-22);font-weight:600;color:var(--text-primary);margin:var(--sp-4) 0 var(--sp-8) 0}
.report-document h2{font-size:var(--fs-17);font-weight:600;color:var(--text-primary);margin:var(--sp-24) 0 var(--sp-12) 0;padding-bottom:var(--sp-8);border-bottom:1px solid var(--border)}
.report-document h3{font-size:var(--fs-14);font-weight:600;color:var(--text-primary);margin:var(--sp-8) 0 var(--sp-4) 0}
.report-document .report-subtitle{font-size:var(--fs-13);color:var(--text-secondary);margin-top:var(--sp-4);line-height:1.5}
.report-document p{font-size:var(--fs-14);color:var(--text-primary);line-height:1.6;margin-bottom:var(--sp-12)}

/* Meta block */
.report-meta-block{display:flex;flex-wrap:wrap;gap:var(--sp-8) var(--sp-24);font-size:var(--fs-11);color:var(--text-secondary);margin-top:var(--sp-12)}
.report-meta-block div{display:flex;gap:var(--sp-4)}
.report-meta-block dt{font-weight:600;color:var(--text-secondary)}
.report-meta-block dd{color:var(--text-primary);font-family:monospace}

/* Divider */
.report-divider{height:1px;background:var(--border);margin:var(--sp-16) 0 var(--sp-24) 0}

/* Recommendation hero */
.recommendation-hero{background:var(--accent);color:#FFFFFF;border-radius:var(--radius-card);padding:var(--sp-24) var(--sp-32);margin-bottom:var(--sp-24);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:var(--sp-16)}
.recommendation-hero .hero-kicker{font-size:var(--fs-11);font-weight:700;letter-spacing:1px;margin-bottom:var(--sp-4);opacity:0.85}
.recommendation-hero .hero-title{font-size:var(--fs-22);font-weight:700;line-height:1.3}
.recommendation-hero p{font-size:var(--fs-13);margin:0;color:rgba(255,255,255,0.9)}
.recommendation-hero strong{color:#FFFFFF}
.recommendation-left{flex:1;min-width:240px}
.recommendation-right{flex:1;min-width:200px;text-align:right}
@media(max-width:600px){.recommendation-hero{flex-direction:column;align-items:flex-start}.recommendation-right{text-align:left}}

/* Decision policy text */
.decision-policy-text{font-size:var(--fs-11);color:var(--text-secondary);font-style:italic;margin-bottom:var(--sp-24);padding-left:var(--sp-16);border-left:2px solid var(--border);line-height:1.5}

/* Technical demo notice */
.technical-demo-notice{background:var(--tint-pending);border:1px solid var(--status-pending);border-radius:var(--radius-card);padding:var(--sp-16) var(--sp-20);margin-bottom:var(--sp-24);font-size:var(--fs-13);color:var(--text-primary);line-height:1.6}
.technical-demo-notice strong{color:var(--status-pending)}

/* Structural comparison */
.structural-comparison{margin-bottom:var(--sp-24)}
.structural-comparison>p{font-size:var(--fs-13);color:var(--text-secondary);margin-bottom:var(--sp-16)}

/* Signal card grid */
.signal-card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:var(--sp-12)}
.signal-card{border:1px solid var(--border);border-radius:var(--radius-card);padding:var(--sp-16);background:var(--bg-surface)}
.signal-card h3{font-size:var(--fs-13);font-weight:600;color:var(--text-primary);margin-bottom:var(--sp-8);line-height:1.4}
.signal-card p{font-size:var(--fs-11);color:var(--text-secondary);margin:var(--sp-8) 0 0 0}

/* Level dots */
.level-dots{display:flex;gap:var(--sp-4);margin:var(--sp-8) 0}
.level-dot{width:12px;height:12px;border-radius:50%;background:var(--border);border:1px solid var(--border)}
.level-dot.is-filled{background:var(--accent);border-color:var(--accent)}
.signal-level-small .level-dot.is-filled{background:var(--status-available);border-color:var(--status-available)}
.signal-level-moderate .level-dot.is-filled{background:var(--status-pending);border-color:var(--status-pending)}
.signal-level-larger .level-dot.is-filled{background:var(--status-error);border-color:var(--status-error)}

/* Decision meaning */
.decision-meaning{margin-bottom:var(--sp-24)}
.decision-meaning-grid{display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-12)}
@media(max-width:600px){.decision-meaning-grid{grid-template-columns:1fr}}
.decision-meaning-card{border:1px solid var(--border);border-radius:var(--radius-card);padding:var(--sp-16);background:var(--bg-surface)}
.decision-meaning-card h3{font-size:var(--fs-11);font-weight:700;letter-spacing:0.5px;color:var(--text-secondary);margin-bottom:var(--sp-4)}
.decision-meaning-card p{font-size:var(--fs-12);color:var(--text-secondary);margin:0;line-height:1.5}
.decision-meaning-card.is-current{border:2px solid var(--accent);background:var(--tint-accent)}
.decision-meaning-card.is-current h3{color:var(--accent)}
.decision-meaning-card.is-current p{color:var(--text-primary)}

/* Model table section */
.model-table-section{margin-bottom:var(--sp-24)}
.field-table{width:100%}
.field-row{display:flex;padding:var(--sp-6) 0;border-bottom:1px solid var(--border);font-size:var(--fs-13)}
.field-row:last-child{border-bottom:none}
.field-label{width:200px;flex-shrink:0;color:var(--text-secondary);font-weight:500;padding-right:var(--sp-16)}
.field-value{flex:1;color:var(--text-primary);min-width:0;word-break:break-all}
.field-value.mono{font-family:monospace;font-size:var(--fs-11)}

/* ============ INTERNAL REPORT ============ */
.internal-technical-report h1{font-size:var(--fs-22);font-weight:600;color:var(--text-primary);margin:var(--sp-4) 0 var(--sp-8) 0}
.internal-technical-report h2{font-size:var(--fs-17);font-weight:600;color:var(--text-primary);margin:var(--sp-24) 0 var(--sp-12) 0;padding-bottom:var(--sp-8);border-bottom:1px solid var(--border)}
.internal-technical-report section{margin-bottom:var(--sp-24)}

/* Internal header */
.internal-report-header{padding-bottom:var(--sp-24);border-bottom:1px solid var(--border);margin-bottom:var(--sp-24)}
.internal-report-header .report-brand{font-size:var(--fs-22);font-weight:600;color:var(--text-primary)}
.internal-report-header h1{font-size:var(--fs-22);font-weight:600;color:var(--text-primary);margin:var(--sp-4) 0 var(--sp-8) 0}
.internal-report-header .report-subtitle{font-size:var(--fs-13);color:var(--text-secondary);margin-bottom:var(--sp-12)}
.report-pill-row{display:flex;gap:var(--sp-8);flex-wrap:wrap}
.report-pill{display:inline-block;padding:var(--sp-2) var(--sp-10);border-radius:var(--radius-pill);font-size:var(--fs-11);font-weight:600;border:1px solid var(--border)}
.certification-pill{background:var(--tint-accent);color:var(--status-available);border-color:var(--status-available)}
.demo-pill{background:var(--tint-pending);color:var(--status-pending);border-color:var(--status-pending)}

/* Boundary note */
.boundary-note{font-size:var(--fs-12);color:var(--text-secondary);font-style:italic;padding:var(--sp-12) var(--sp-16);background:var(--tint-pending);border-radius:var(--radius-card);margin:var(--sp-16) 0;line-height:1.6}

/* Section note */
.section-note{font-size:var(--fs-12);color:var(--text-secondary);margin-bottom:var(--sp-12);line-height:1.5}

/* Signal breakdown table */
.signal-breakdown-table{width:100%;border-collapse:collapse;font-size:var(--fs-13);margin:var(--sp-12) 0}
.signal-breakdown-table th{text-align:left;padding:var(--sp-8) var(--sp-12);border-bottom:2px solid var(--border);color:var(--text-secondary);font-weight:600;font-size:var(--fs-11);text-transform:uppercase;letter-spacing:0.5px}
.signal-breakdown-table td{padding:var(--sp-8) var(--sp-12);border-bottom:1px solid var(--border);color:var(--text-primary)}
.signal-breakdown-table td:first-child{font-weight:500}
.signal-breakdown-table td:nth-child(2){font-family:monospace;font-size:var(--fs-11);color:var(--text-secondary);word-break:break-all}

/* Execution trace */
.execution-trace-summary{margin-bottom:var(--sp-24)}
.trace-stage{display:flex;align-items:center;gap:var(--sp-12);padding:var(--sp-8) var(--sp-12);border-left:2px solid var(--border);margin-bottom:var(--sp-4);font-size:var(--fs-13)}
.trace-stage.completed{border-left-color:var(--status-available)}
.trace-stage.failed{border-left-color:var(--status-error);background:var(--tint-error)}
.trace-stage-icon{width:16px;text-align:center;font-size:var(--fs-13)}
.trace-stage-icon.completed{color:var(--status-available)}
.trace-stage-icon.failed{color:var(--status-error)}
.trace-stage-label{flex:1;color:var(--text-primary)}
.trace-stage-dur{font-size:var(--fs-11);color:var(--text-secondary);font-family:monospace}

/* Footer */
.report-document .report-footer{text-align:center;padding:var(--sp-20) 0 0 0;font-size:var(--fs-11);color:var(--text-secondary);border-top:1px solid var(--border);margin-top:var(--sp-32);line-height:1.6}

/* Sample banner */
.sample-banner{background:var(--tint-error);border:2px solid var(--status-error);border-radius:var(--radius-card);padding:var(--sp-16) var(--sp-24);margin-bottom:var(--sp-24);text-align:center}
.sample-banner-title{font-size:var(--fs-17);font-weight:700;color:var(--status-error);margin-bottom:var(--sp-8)}
.sample-banner-text{font-size:var(--fs-13);color:var(--text-primary);line-height:1.6}

/* Responsive */
@media(max-width:768px){.report-page{padding:var(--sp-12)}.report-content{max-width:100%}.report-document{padding:var(--sp-16)}.tab-btn{padding:var(--sp-8) var(--sp-12);font-size:var(--fs-13)}.print-button{padding:var(--sp-8) var(--sp-12);font-size:var(--fs-11)}.field-label{width:120px}}

/* Print */
@media print {
  body{background:#FFFFFF;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .report-page{padding:0;max-width:100%}
  .report-nav,.report-tabs,.tab-btn,.tab-spacer,.print-button,
  .report-loading,.report-error,
  .report-loading-spinner{display:none !important}
  .tab-panel[hidden]{display:none !important}
  .tab-panel:not([hidden]){display:block !important}
  .report-document{box-shadow:none;border:none;padding:0;max-width:100%;page-break-after:avoid}
  .recommendation-hero{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .technical-demo-notice{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .boundary-note{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .signal-card{-webkit-print-color-adjust:exact;print-color-adjust:exact;page-break-inside:avoid}
  .level-dot.is-filled{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .decision-meaning-card.is-current{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .signal-breakdown-table{page-break-inside:avoid}
  .trace-stage.completed{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .trace-stage.failed{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .report-document .report-header{border-bottom:1px solid #E3E7E6}
  .report-document .report-footer{border-top:1px solid #E3E7E6}
  .section-title{border-bottom:1px solid #E3E7E6}
}
"""

# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------

_JS = r"""
<script>
(function(){
var baseUrl='__BASE_URL__';
var jobId='__JOB_ID__';
var isSample='__IS_SAMPLE__'==='1';
var sampleData=null;
var activeTab='external';

function init(){
  if(isSample){
    try{
      var el=document.getElementById('sample-data-json');
      if(el) sampleData=JSON.parse(el.textContent);
    }catch(e){}
    if(sampleData){
      document.getElementById('sample-banner').hidden=false;
      renderAll(sampleData.job,sampleData.report);
    }
    return;
  }
  if(jobId){
    loadReport(jobId);
  }
}

function loadReport(jid){
  var content=document.getElementById('report-content');
  Promise.all([
    fetch(baseUrl+'/demo/api/jobs/'+jid).then(function(r){return r.json()}),
    fetch(baseUrl+'/demo/api/jobs/'+jid+'/reports/bremen').then(function(r){return r.json()}),
    fetch(baseUrl+'/demo/api/reports/'+jid+'/external').then(function(r){return r.json()}),
    fetch(baseUrl+'/demo/api/reports/'+jid+'/internal').then(function(r){return r.json()})
  ]).then(function(results){
    renderAll(results[0],results[1],results[2],results[3]);
  }).catch(function(){
    content.innerHTML='<div class="report-error"><div class="report-error-title">Failed to load report</div><div class="report-error-text">Could not load the report data. The job may have expired or the server may be unavailable.</div></div>';
  });
}

function renderAll(job,reportData,extReport,intReport){
  var report=reportData.report||{};
  renderExternalReport(extReport||buildExternalReport(report));
  renderInternalReport(intReport||buildInternalReport(report));
}

/* ==========================================================
   NORMALIZED REPORT BUILDERS (JS equivalents of Python builders)
   ========================================================== */

function _safeDict(v){return v&&typeof v==='object'&&!Array.isArray(v)?v:{}}
function _safeList(v){return Array.isArray(v)?v:[]}
function _dash(v){return(v==null||v==='')?'\u2014':String(v)}
function _firstPresent(){for(var i=0;i<arguments.length-1;i++){var a=arguments[i];if(a!=null&&a!=='')return a}return arguments[arguments.length-1]}
function _checksumPrefix(v,len){len=len||8;if(!v)return null;var t=String(v);return t.length<=len?t:t.substring(0,len)}

function buildExternalReport(report){
  report=_safeDict(report);
  var payload=_safeDict(report.payload);
  var ds=_safeDict(_firstPresent(payload.decision_support_report,report.decision_support_report,report.decision_support,{}));
  var prediction=_safeDict(_firstPresent(ds.prediction_summary,payload.prediction_summary,report.prediction_summary,{}));
  var model=_safeDict(_firstPresent(ds.model_metadata,payload.model_metadata,report.model_metadata,{}));
  var inputSummary=_safeDict(_firstPresent(ds.input_summary,payload.input_summary,report.input_summary,{}));
  var symmetry=_safeDict(_firstPresent(ds.symmetry_signals,payload.symmetry_signals,report.symmetry_signals,{}));
  var generatedAt=_firstPresent(report.completed_at,report.created_at,payload.completed_at,payload.created_at,ds.generated_at);
  var rJobId=_firstPresent(report.job_id,payload.job_id,ds.job_id);
  var rReqId=_firstPresent(report.request_id,payload.request_id,ds.request_id);
  var thresholdValue=_firstPresent(prediction.threshold_value,model.threshold_value,ds.threshold_value);
  var policyId=_firstPresent(prediction.decision_policy_id,model.threshold_version,ds.decision_policy_id);
  var policyVer=_firstPresent(prediction.decision_policy_version,model.decision_policy_version,ds.decision_policy_version);
  return {
    output_type:'bremen_decision_support_report',
    report_schema_version:_firstPresent(ds.report_schema_version,'v0.1'),
    report_id:_firstPresent(ds.report_id,_reportId(rJobId,generatedAt)),
    generated_at:generatedAt,job_id:rJobId,request_id:rReqId,
    patient_reference:_firstPresent(ds.patient_reference,report.patient_reference,'\u2014'),
    analysis_author:'Bremen demo environment',
    intended_use:'MRI continuation decision support only. Not a diagnosis, not clinically validated, does not replace MRI, biopsy, radiologist, clinician, or clinical judgment.',
    limitations:['Decision-support output only, not a diagnostic result.','Not clinically validated.','Does not replace MRI, biopsy, radiologist, clinician, or clinical judgment.'],
    model_metadata:{model_version:_firstPresent(model.model_version,report.model_version),feature_schema_version:_firstPresent(model.feature_schema_version,ds.feature_schema_version),threshold_version:policyId,threshold_value:thresholdValue},
    input_summary:{input_mode:_firstPresent(inputSummary.input_mode,report.input_mode,'\u2014'),explicit_refs_provided:_firstPresent(inputSummary.explicit_refs_provided,null),layout_category:_firstPresent(inputSummary.layout_category,'\u2014')},
    prediction_summary:{p_mri_needed:formatScore(_firstPresent(prediction.p_mri_needed,ds.p_mri_needed,report.score)),decision_code:_firstPresent(prediction.decision_code,ds.decision_code,report.decision_code),decision_display_name:_firstPresent(prediction.decision_display_name,ds.decision_display_name,'Continue MRI evaluation'),decision_policy_id:policyId,decision_policy_version:policyVer,qc_status:_firstPresent(prediction.qc_status,ds.qc_status,payload.qc_status),qc_flags:_safeList(_firstPresent(prediction.qc_flags,ds.qc_flags,payload.qc_flags,[]))},
    decision_support:{recommendation:_firstPresent(ds.decision_support&&ds.decision_support.recommendation,prediction.decision_code,ds.decision_code)},
    symmetry_signals:{schema_status:_firstPresent(symmetry.schema_status,'unavailable'),measurement_summary:_safeDict(symmetry.measurement_summary),signals:(symmetry.signals||[]).map(function(s){return{label:_dash(s.label),difference_level:normalizeLevel(s.difference_level)}}),note:_firstPresent(symmetry.note,'Reference statistics are not yet available; qualitative asymmetry calibration is pending.')}
  };
}

function buildInternalReport(report){
  report=_safeDict(report);
  var payload=_safeDict(report.payload);
  var external=buildExternalReport(report);
  var supporting=_safeDict(_firstPresent(payload.supporting_technical_evidence,report.supporting_technical_evidence,{}));
  var detail=_safeDict(_firstPresent(supporting.symmetry_signal_detail,payload.symmetry_signal_detail,report.symmetry_signal_detail,{}));
  var trace=_firstPresent(payload.execution_trace_summary,report.execution_trace_summary,report.execution_trace,{});
  var checksumPrefix=_checksumPrefix(_firstPresent(supporting.model_checksum_prefix,payload.model_checksum_prefix,report.model_checksum_prefix,report.model_checksum));
  return {
    output_type:'bremen_internal_report',
    report_schema_version:'v0.1',
    report_id:external.report_id,
    generated_at:external.generated_at,
    job_identity:{job_id:external.job_id,request_id:external.request_id,created_at:_firstPresent(report.created_at,payload.created_at),completed_at:_firstPresent(report.completed_at,payload.completed_at),status:_firstPresent(report.status,payload.status)},
    model_and_plugin:{model_version:external.model_metadata.model_version,model_checksum_prefix:checksumPrefix,feature_schema_version:external.model_metadata.feature_schema_version,plugin_id:_firstPresent(supporting.plugin_id,payload.plugin_id,'bremen.default'),plugin_version:_firstPresent(supporting.plugin_version,payload.plugin_version,'0.1'),report_schema_version:'v0.1'},
    decision_policy:{decision_code:external.prediction_summary.decision_code,decision_policy_id:external.prediction_summary.decision_policy_id,decision_policy_version:external.prediction_summary.decision_policy_version,threshold_value:external.model_metadata.threshold_value,qc_status:external.prediction_summary.qc_status,qc_flags:external.prediction_summary.qc_flags},
    input_summary:external.input_summary,
    execution_trace_summary:normalizeTrace(trace),
    symmetry_signal_detail:{schema_status:_firstPresent(detail.schema_status,external.symmetry_signals.schema_status,'unavailable'),measurement_summary:_safeDict(_firstPresent(detail.measurement_summary,external.symmetry_signals.measurement_summary,{})),signals:_safeList(_firstPresent(detail.signals,external.symmetry_signals.signals,[])).map(function(s){return{label:_dash(s.label),feature_family:_safeList(s.feature_family),difference_level:normalizeLevel(s.difference_level)}}),note:_firstPresent(detail.note,external.symmetry_signals.note,'Named feature families shown for traceability. Raw magnitudes intentionally omitted.')}
  };
}

function normalizeLevel(level){return(level==='small'||level==='moderate'||level==='larger'||level==='not_available')?level:'not_available'}
function formatScore(v){return(typeof v==='number')?v.toFixed(3):v}
function formatDate(d){return d?String(d).substring(0,19).replace('T',' '):'\u2014'}
function formatFlags(flags){return _safeList(flags).join(', ')||'\u2014'}
function measurementSummaryText(sym){var s=_safeDict(sym);var m=s.measurement_summary||{};return m.label||'Asymmetry assessment'}

function _reportId(jid,gen){
  var safeJob=(jid||'unknown').replace(/-/g,'').substring(0,8);
  var safeTime=(gen||'unknown').replace(/-/g,'').replace(/:/g,'').replace(/\./g,'').substring(0,15);
  return safeTime+'_'+safeJob;
}

/* ---------- Level labels ---------- */

function levelLabel(level){
  if(level==='small')return'Small Difference';
  if(level==='moderate')return'Moderate Difference';
  if(level==='larger')return'Larger Difference';
  return'Calibration pending';
}

/* ---------- Rendering helpers ---------- */

function escapeHtml(str){
  if(!str)return'';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function escapeAttr(str){return escapeHtml(str)}

function renderFieldTable(cls,rows){
  var html='<div class="field-table '+cls+'">';
  for(var i=0;i<rows.length;i++){
    html+='<div class="field-row"><div class="field-label">'+escapeHtml(rows[i][0])+'</div><div class="field-value mono">'+escapeHtml(String(rows[i][1]!=null?rows[i][1]:'\u2014'))+'</div></div>';
  }
  html+='</div>';
  return html;
}

function renderLevelDots(level){
  var count=level==='small'?1:level==='moderate'?2:level==='larger'?3:0;
  var html='<div class="level-dots" aria-label="'+escapeAttr(levelLabel(level))+'">';
  for(var i=0;i<3;i++){html+='<span class="level-dot'+(i<count?' is-filled':'')+'"></span>';}
  html+='</div>';
  return html;
}

function renderExternalSignalCard(signal){
  var level=signal.difference_level||'not_available';
  return'<article class="signal-card signal-level-'+escapeAttr(level)+'"><h3>'+escapeHtml(signal.label||'\u2014')+'</h3>'+renderLevelDots(level)+'<p>'+escapeHtml(levelLabel(level))+'</p></article>';
}

/* ==========================================================
   EXTERNAL REPORT RENDERER
   ========================================================== */

function renderExternalReport(report){
  if(!report||report.error){return renderFallback('Report data is not available for this job.');}
  var prediction=report.prediction_summary||{};
  var model=report.model_metadata||{};
  var signals=((report.symmetry_signals||{}).signals||[]);
  var score=prediction.p_mri_needed;
  var threshold=model.threshold_value;
  var decisionCode=prediction.decision_code;
  var decisionName=prediction.decision_display_name||'Continue MRI evaluation';

  var decisionCard='';
  if(decisionCode==='CONTINUE_MRI'||decisionCode==='MRI_REVIEW_DEFER'){
    decisionCard='<div class="decision-meaning-card'+(decisionCode==='CONTINUE_MRI'?' is-current':'')+'"><h3>'+(decisionCode==='CONTINUE_MRI'?'CONTINUE MRI \u00B7 THIS RESULT':'MRI REVIEW DEFER')+'</h3><p>'+explanationText(decisionCode)+'</p></div>';
  }

  var html='';
  html+='<article class="report-document external-report-document">';

  // Header
  html+='<header class="report-header"><div><div class="report-brand">Bremen</div><h1>MRI-Continuation Decision-Support Report</h1><p class="report-subtitle">For the referring clinician / breast-imaging radiologist</p></div><dl class="report-meta-block"><div><dt>Job ID</dt><dd>'+escapeHtml(report.job_id||'\u2014')+'</dd></div><div><dt>Request ID</dt><dd>'+escapeHtml(report.request_id||'\u2014')+'</dd></div><div><dt>Generated</dt><dd>'+escapeHtml(formatDate(report.generated_at))+'</dd></div><div><dt>Patient reference</dt><dd>'+escapeHtml(report.patient_reference||'\u2014')+'</dd></div></dl></header>';

  html+='<div class="report-divider"></div>';

  // Recommendation hero
  html+='<section class="recommendation-hero" role="alert"><div class="recommendation-left"><div class="hero-kicker">RECOMMENDATION</div><div class="hero-title">'+escapeHtml(decisionName)+'</div></div><div class="recommendation-right"><p>Model score (p_mri_needed) <strong>'+escapeHtml(formatScore(score))+'</strong> \u00B7 threshold '+escapeHtml(formatScore(threshold))+'</p><p>QC status <strong>'+escapeHtml(prediction.qc_status||'\u2014')+'</strong></p></div></section>';

  // Decision policy
  html+='<p class="decision-policy-text">Decision policy '+escapeHtml(prediction.decision_policy_id||'\u2014')+' '+escapeHtml(prediction.decision_policy_version||'')+' \u00B7 score \u2265 threshold \u2192 MRI continuation flagged for clinician review</p>';

  // Tech demo notice
  html+='<section class="technical-demo-notice"><strong>Technical demo only. Not a diagnosis. Not clinically validated.</strong> Does not replace MRI, biopsy, radiologist, clinician, or clinical judgment. This output is decision support only and requires qualified clinical review.</section>';

  // Structural comparison
  html+='<section class="structural-comparison"><h2>Left/right structural comparison</h2><p>Bremen compares structural symmetry between both breasts rather than scoring one pre-identified side. Each panel below is a different kind of comparison; more filled dots means a larger left/right difference was detected in that comparison. These are indicators for clinical context, not independent diagnostic findings.</p><div class="signal-card-grid">';
  for(var i=0;i<signals.length;i++){html+=renderExternalSignalCard(signals[i]);}
  html+='</div></section>';

  // Decision meaning
  html+='<section class="decision-meaning"><h2>What this recommendation means</h2><div class="decision-meaning-grid"><div class="decision-meaning-card"><h3>MRI REVIEW DEFER</h3><p>Score below threshold. MRI continuation may be deferred, subject to clinician review.</p></div>'+decisionCard+'</div></section>';

  // Model table
  html+='<section class="model-table-section"><h2>Model</h2>'+renderFieldTable('',[['Model',model.model_version],['Feature schema',model.feature_schema_version],['Decision policy',(prediction.decision_policy_id||'\u2014')+' '+(prediction.decision_policy_version||'')],['Scientific certification','Pending \u2014 research draft']])+'</section>';

  // Footer
  html+='<footer class="report-footer"><p>Bremen \u00B7 Eos-Dx \u00B7 This report is decision support only and does not constitute a diagnosis, a validated clinical result, or a substitute for radiologist or clinician judgment. Generated from a technical demonstration environment.</p></footer>';

  html+='</article>';

  document.getElementById('panel-external').innerHTML=html;
}

function explanationText(code){
  if(code==='CONTINUE_MRI')return'Score at or above threshold. MRI continuation is flagged for clinician review.';
  if(code==='MRI_REVIEW_DEFER')return'Score below threshold. MRI continuation may be deferred, subject to clinician review.';
  return'Model output is not conclusive. A qualified clinician must review the full case.';
}

function renderFallback(msg){
  var html='<article class="report-document"><p style="font-size:var(--fs-14);color:var(--text-secondary);text-align:center;padding:var(--sp-48)">'+escapeHtml(msg)+'</p></article>';
  document.getElementById('panel-external').innerHTML=html;
}

/* ==========================================================
   INTERNAL REPORT RENDERER
   ========================================================== */

function renderInternalReport(report){
  if(!report||report.error){
    var panel=document.getElementById('panel-internal');
    panel.innerHTML='<article class="report-document internal-technical-report"><p style="font-size:var(--fs-14);color:var(--text-secondary);text-align:center;padding:var(--sp-48)">Internal report data is not available for this job.</p></article>';
    return;
  }
  var job=report.job_identity||{};
  var model=report.model_and_plugin||{};
  var policy=report.decision_policy||{};
  var detail=report.symmetry_signal_detail||{};
  var signals=detail.signals||[];
  var trace=report.execution_trace_summary||{};

  var html='';
  html+='<article class="report-document internal-technical-report">';

  // Header
  html+='<header class="internal-report-header"><div class="report-brand">Bremen</div><h1>Internal Technical Report</h1><p class="report-subtitle">Audit / provenance detail \u2014 not for patient or external distribution</p><div class="report-pill-row"><span class="report-pill certification-pill">Scientific certification: pending</span><span class="report-pill demo-pill">Technical demo only</span></div></header>';
  html+='<div class="report-divider"></div>';

  // Job identity
  html+='<section><h2>Request &amp; job identity</h2>'+renderFieldTable('identity-table',[['Job ID',job.job_id],['Request ID',job.request_id],['Created',job.created_at],['Completed',job.completed_at],['Status',job.status]])+'</section>';

  // Model & plugin
  html+='<section><h2>Model &amp; runtime plugin</h2>'+renderFieldTable('model-plugin-table',[['Model version',model.model_version],['Model checksum (prefix)',model.model_checksum_prefix],['Feature schema version',model.feature_schema_version],['Plugin ID',model.plugin_id],['Plugin version',model.plugin_version],['Report schema version',model.report_schema_version]])+'</section>';

  // Boundary note
  html+='<section class="boundary-note">Checksum shown as prefix only. Bremen\'s demo routes are unauthenticated and public; this report never renders the full 64-character checksum, raw target/control references, feature values, or patient/session identifiers, regardless of audience \u2014 there is no separate authenticated surface to gate a fuller view behind.</section>';

  // Decision policy
  html+='<section><h2>Decision policy</h2>'+renderFieldTable('decision-policy-table',[['Decision code',policy.decision_code],['Decision policy ID',policy.decision_policy_id],['Decision policy version',policy.decision_policy_version],['Threshold value',policy.threshold_value],['QC status',policy.qc_status],['QC flags',formatFlags(policy.qc_flags)]])+'</section>';

  // Symmetry signals
  html+='<section><h2>Symmetry signal breakdown</h2><p class="section-note">Qualitative buckets derived from the 15-feature contract. Raw magnitudes intentionally omitted \u2014 see boundary note above.</p><table class="signal-breakdown-table"><thead><tr><th>SIGNAL</th><th>FEATURE FAMILY</th><th>DIFFERENCE</th></tr></thead><tbody>';
  for(var j=0;j<signals.length;j++){
    var sig=signals[j];
    var level=sig.difference_level||'not_available';
    var label=level==='not_available'?'Reference statistics unavailable':levelLabel(level);
    html+='<tr><td>'+escapeHtml(sig.label||'\u2014')+'</td><td>'+escapeHtml((sig.feature_family||[]).join(', ')||'\u2014')+'</td><td>'+escapeHtml(label)+'</td></tr>';
  }
  html+='</tbody></table></section>';

  // Execution trace
  var traceKeys=Object.keys(trace);
  if(traceKeys.length>0){
    html+='<section class="execution-trace-summary"><h2>Execution trace (stage summary)</h2>';
    var traceEntries=[];
    for(var k=0;k<traceKeys.length;k++){
      var stageName=traceKeys[k];
      traceEntries.push([stageName,String(trace[stageName])+'ms']);
    }
    html+=renderFieldTable('',traceEntries);
    html+='</section>';
  }

  // Footer
  html+='<footer class="report-footer"><p>Bremen \u00B7 Eos-Dx \u00B7 Internal technical report. Not a diagnosis. Not clinically validated. Does not replace MRI, biopsy, radiologist, clinician, or clinical judgment. Distribution limited to internal engineering, scientific, and product review.</p></footer>';

  html+='</article>';
  document.getElementById('panel-internal').innerHTML=html;
}

/* ---------- Tab switching ---------- */

function switchTab(tabId){
  activeTab=tabId;
  var tabs=document.querySelectorAll('.tab-btn[role="tab"]');
  for(var i=0;i<tabs.length;i++){
    var t=tabs[i];
    var selected=t.getAttribute('data-tab')===tabId;
    t.setAttribute('aria-selected',selected?'true':'false');
    t.tabIndex=selected?0:-1;
  }
  var panels=document.querySelectorAll('.tab-panel[role="tabpanel"]');
  for(var j=0;j<panels.length;j++){
    var p=panels[j];
    if(p.id==='panel-'+tabId){p.removeAttribute('hidden');}
    else{p.setAttribute('hidden','');}
  }
  // Show only the active print button
  var btnExt=document.getElementById('print-btn-external');
  var btnInt=document.getElementById('print-btn-internal');
  if(btnExt) btnExt.style.display=tabId==='external'?'':'none';
  if(btnInt) btnInt.style.display=tabId==='internal'?'':'none';
}

function printActiveTab(){
  switchTab(activeTab);
  window.print();
}

/* ---------- Keyboard navigation ---------- */
document.addEventListener('keydown',function(e){
  if(e.key==='ArrowRight'||e.key==='ArrowLeft'){
    var tabs=document.querySelectorAll('.tab-btn[role="tab"]');
    var currentIdx=-1;
    for(var i=0;i<tabs.length;i++){
      if(tabs[i].getAttribute('aria-selected')==='true'){currentIdx=i;break;}
    }
    if(currentIdx>=0){
      if(e.key==='ArrowRight') currentIdx=(currentIdx+1)%tabs.length;
      else currentIdx=(currentIdx-1+tabs.length)%tabs.length;
      var nextTab=tabs[currentIdx].getAttribute('data-tab');
      if(nextTab) switchTab(nextTab);
      tabs[currentIdx].focus();
    }
    e.preventDefault();
  }
});

window.switchTab=switchTab;
window.printActiveTab=printActiveTab;
window.loadReport=loadReport;

init();
})();
</script>
"""


def build_report_page(
    base_url: str = "http://localhost:8000",
    job_id: str = "",
    sample_data: dict | None = None,
) -> str:
    """Build the Bremen Report page HTML.

    Parameters
    ----------
    base_url : Base URL of the service.
    job_id : The job ID to display the report for.
    sample_data : Optional sample data dict for offline sample mode.
        When provided, data is embedded directly in the HTML and no
        fetch calls are made. The page displays a prominent synthetic
        sample banner. Must NOT be used in production.

    Returns
    -------
    A complete HTML5 document as a string.
    """
    is_sample = "1" if sample_data else "0"
    sample_json = ""
    if sample_data:
        sample_json = (
            '<script type="application/json" id="sample-data-json">'
            + _json.dumps(sample_data, ensure_ascii=False)
            + "</script>"
        )

    js = _JS.replace("__BASE_URL__", base_url)
    js = js.replace("__JOB_ID__", job_id)
    js = js.replace("__IS_SAMPLE__", is_sample)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bremen Report — MRI Triage Decision Support</title>
<style>{_CSS}</style>
</head>
<body>
<div class="report-page">
  <div class="report-tabs" role="tablist" aria-label="Report tabs">
    <button class="tab-btn" role="tab" id="tab-external-btn"
            aria-selected="true" aria-controls="panel-external"
            data-tab="external" onclick="switchTab('external')"
            tabindex="0">External</button>
    <button class="tab-btn" role="tab" id="tab-internal-btn"
            aria-selected="false" aria-controls="panel-internal"
            data-tab="internal" onclick="switchTab('internal')"
            tabindex="-1">Internal</button>
    <div class="tab-spacer"></div>
    <button class="print-button" id="print-btn-external"
            onclick="printActiveTab()">Print / Save PDF</button>
    <button class="print-button" id="print-btn-internal"
            onclick="printActiveTab()" style="display:none">Print / Save PDF</button>
  </div>

  <div class="report-content" id="report-content">
    <div id="panel-external" class="tab-panel" role="tabpanel"
         aria-labelledby="tab-external-btn">
      <div class="report-loading">
        <div class="report-loading-spinner"></div>
        <div class="report-loading-text">Loading report...</div>
      </div>
    </div>
    <div id="panel-internal" class="tab-panel" role="tabpanel"
         aria-labelledby="tab-internal-btn" hidden>
      <div class="report-loading">
        <div class="report-loading-spinner"></div>
        <div class="report-loading-text">Loading report...</div>
      </div>
    </div>
  </div>
</div>
{sample_json}
{js}
</body>
</html>"""
