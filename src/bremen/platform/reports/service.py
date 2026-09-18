"""Reports application operations."""

from __future__ import annotations
import logging
import uuid as _uuid
from typing import Any
from bremen.platform.jobs.models import (
    AnalysisJob,
    ReportMetadata,
)
from bremen.contracts.reports import (
    ReportEnvelope,
    ReportProvider,
    REPORT_STATUS_AVAILABLE,
    REPORT_STATUS_UNAVAILABLE,
)
from bremen.platform.reports.mapper import build_standard_result
from bremen.platform.jobs.repository import (
    _jobs,
    _report_providers,
    _jobs_lock,
    _providers_lock,
)

_log = logging.getLogger(__name__)


def register_report_provider(provider: ReportProvider) -> None:
    """Register a report provider for a workflow."""
    with _providers_lock:
        _report_providers[provider.workflow_id] = provider


def _get_report_provider(workflow_id: str) -> ReportProvider | None:
    # Snapshot providers dict under lock for safe read
    with _providers_lock:
        providers = dict(_report_providers)
    return providers.get(workflow_id)


def _safe_report_identifier(value: Any) -> str:
    """Return a short opaque identifier, or empty string when unsafe.

    Never returns a path, S3 URI, or free-form text.
    """
    import re

    if not isinstance(value, str):
        return ""
    clean = value.strip()
    if not clean or "/" in clean or "\\" in clean or "://" in clean:
        return ""
    return clean if re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", clean) else ""


class _AraminaLocalReportProvider(ReportProvider):
    """Expose the local runner's numeric result through existing report APIs."""

    workflow_id = "aramina"

    def generate_report(
        self,
        job_id: str,
        workflow_result: dict[str, Any],
        *,
        model_identity: dict[str, str] | None = None,
        readiness_snapshot: dict[str, bool] | None = None,
        job_context: dict[str, Any] | None = None,
    ) -> ReportEnvelope:
        import math

        external = workflow_result.get("external_report", {})
        score = external.get("risk_score") if isinstance(external, dict) else None
        valid = type(score) in (int, float) and math.isfinite(score) and 0 <= score <= 1
        identity = model_identity or {}
        context = job_context or {}

        # PR0143: additive report metadata. The requested side comes from the
        # workflow result (the side actually scored); the patient identifier
        # comes from the job context. Both are sanitized and omitted when
        # unknown, so the existing contract is unchanged.
        target_side = ""
        if isinstance(external, dict):
            candidate = external.get("target_side")
            if candidate in {"left", "right"}:
                target_side = candidate
        patient_id = _safe_report_identifier(context.get("patient_id"))

        return ReportEnvelope(
            report_id=str(_uuid.uuid4()),
            workflow_id="aramina",
            job_id=job_id,
            report_schema_version="v0.1",
            workflow_status=REPORT_STATUS_AVAILABLE
            if valid
            else REPORT_STATUS_UNAVAILABLE,
            model_id=identity.get("model_id"),
            model_version=identity.get("model_version"),
            scientifically_certified=False,
            disclaimer="Research draft. Requires clinical review.",
            payload={"risk_score": float(score), "technical_demo_only": True}
            if valid
            else {},
            patient_id=patient_id or None,
            target_side=target_side or None,
            links={
                "job": f"/demo/api/jobs/{job_id}",
                "json": f"/demo/api/jobs/{job_id}/reports/aramina",
            },
        )


def _register_default_providers() -> None:
    """Register built-in report providers."""
    from bremen.platform.reports.bremen import BremenReportProvider  # noqa: PLC0415

    with _providers_lock:
        if "bremen" not in _report_providers:
            _report_providers["bremen"] = BremenReportProvider()
        if "aramina" not in _report_providers:
            _report_providers["aramina"] = _AraminaLocalReportProvider()


def get_job_reports(job_id: str) -> dict[str, Any]:
    """Return reports for a job, keyed by workflow_id."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return {"reports": {}, "job_id": job_id}
    # Snapshot report data under lock to avoid mutation during iteration
    with _jobs_lock:
        reports_snapshot = dict(job.reports)
    return {
        "reports": {
            wid: {
                "report_id": rm.report_id,
                "workflow_id": rm.workflow_id,
                "report_schema_version": rm.report_schema_version,
                "status": rm.status,
                "generated_at": rm.generated_at,
                "model_id": rm.model_id,
                "model_version": rm.model_version,
                "scientifically_certified": rm.scientifically_certified,
            }
            for wid, rm in reports_snapshot.items()
        },
        "job_id": job_id,
    }


def _report_job_context(job: AnalysisJob) -> dict[str, Any]:
    """Return safe job-level metadata for report providers.

    PR0143: exposes only the requested patient identifier and target side.
    Never includes source_key, container paths, or artifact internals.  Its
    key set is a locked report-provider contract and is intentionally left
    unchanged by PR0157.
    """
    summary = job.input_summary or {}
    return {
        "patient_id": summary.get("patient_display_name", ""),
        "target_side": summary.get("target_side", ""),
    }


def _mapper_job_context(job: AnalysisJob) -> dict[str, Any]:
    """Standard Model Result mapper context (PR0157), derived from ``job``.

    Adds sanitized request metadata (author/comment) on top of the locked
    PR0143 report-provider context.  Only patient_id, target_side,
    analysis_author and prediction_comment appear; source_key, container paths
    and artifact internals never enter this mapping, and author/comment were
    sanitized at ingestion.
    """
    context = dict(_report_job_context(job))
    summary = job.input_summary or {}
    context["analysis_author"] = summary.get("analysis_author", "")
    context["prediction_comment"] = summary.get("prediction_comment", "")
    return context


def get_job_report(job_id: str, workflow_id: str) -> dict[str, Any]:
    """Return a specific workflow report, or unavailable."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return {
            "report": {"status": "job_not_found"},
            "job_id": job_id,
            "workflow_id": workflow_id,
        }

    # Snapshot only the requested run. A failed sibling must not hide a
    # completed workflow's report. Diagnostics are projected, never mutated.
    with _jobs_lock:
        wf_run = job.workflow_runs.get(workflow_id)
        stored_report = job.reports.get(workflow_id)
        overall_status = job.overall_status
        context = dict(_report_job_context(job))
        requested = workflow_id in job.requested_workflows or wf_run is not None
        failed_run = wf_run is not None and wf_run.status in {
            "failed",
            "workflow_unavailable",
            "workflow_incompatible",
            "workflow_configuration_required",
            "model_invalid",
            "inference_failed",
            "report_failed",
        }
        failed_job = overall_status in {"failed", "normalization_failed"}
        failure = wf_run.failure if wf_run is not None else None
        details = dict(wf_run.failure_details) if wf_run is not None else {}
        identity = (
            dict(wf_run.model_identity)
            if wf_run is not None
            else {
                "model_id": job.input_summary.get("model_id", ""),
            }
        )
    if requested and (failed_run or (failed_job and wf_run is None)):
        from bremen.platform.reports.failures import build_failure_report

        return {
            "report": build_failure_report(
                workflow_id,
                failure=failure,
                failure_details=details,
                model_identity=identity,
                job_context=context,
                normalization_failed=overall_status == "normalization_failed",
            ),
            "job_id": job_id,
            "workflow_id": workflow_id,
        }
    if failed_job and wf_run is None:
        return {
            "report": {
                "status": REPORT_STATUS_UNAVAILABLE,
                "reason_code": "REPORT_NOT_AVAILABLE",
            },
            "job_id": job_id,
            "workflow_id": workflow_id,
        }

    provider = _get_report_provider(workflow_id)
    if provider is None or wf_run is None:
        return {
            "report": {
                "status": REPORT_STATUS_UNAVAILABLE,
                "reason_code": "WORKFLOW_OR_REPORT_PROVIDER_NOT_CONFIGURED",
            },
            "job_id": job_id,
            "workflow_id": workflow_id,
        }

    # Generate the report fresh
    report = provider.generate_report(
        job_id=job_id,
        workflow_result=wf_run.result_summary,
        model_identity=wf_run.model_identity,
        readiness_snapshot=wf_run.readiness_snapshot,
        job_context=_report_job_context(job),
    )
    # PR0157 (additive): map a completed scientific result into Standard Model
    # Result Contract v1.  Attached only for an available report whose runtime
    # result carries authoritative probability + threshold (the mapper returns
    # None otherwise), so default/unavailable/failed envelopes serialize exactly
    # as before.  The mapper consumes the model-owned result; it recomputes
    # nothing and adds no new top-level provider field.
    if report.workflow_status == REPORT_STATUS_AVAILABLE:
        # PR0158a: canonical Standard Model Result identity comes from the
        # ALREADY-STORED ReportMetadata so repeated GETs are byte-identical.
        # Only a legacy/test-only job with no stored report falls back to the
        # freshly-generated envelope (which would otherwise drift per GET).
        # created_at keeps its raw stored representation; the mapper's
        # normalize_timestamp() produces the RFC3339 seconds-precision form.
        standard_report_id = (
            stored_report.report_id
            if stored_report is not None and stored_report.report_id
            else report.report_id
        )
        standard_created_at = (
            stored_report.generated_at
            if stored_report is not None and stored_report.generated_at
            else report.generated_at
        )
        standard = build_standard_result(
            workflow_id,
            wf_run.result_summary,
            model_identity=wf_run.model_identity,
            job_context=_mapper_job_context(job),
            report_id=standard_report_id,
            created_at=standard_created_at,
        )
        if standard is not None:
            report.standard_result = standard
    return {
        "report": report.to_dict(),
        "job_id": job_id,
        "workflow_id": workflow_id,
    }


def _generate_job_reports(job: AnalysisJob) -> None:
    """Generate reports for all completed workflow runs.

    Caller must ensure exclusive access to *job.reports*.
    """
    for wid, wf_run in list(job.workflow_runs.items()):
        provider = _get_report_provider(wid)
        if provider is None:
            job.reports[wid] = ReportMetadata(
                report_id=str(_uuid.uuid4()),
                workflow_id=wid,
                report_schema_version="v0.1",
                status=REPORT_STATUS_UNAVAILABLE,
            )
            continue

        report = provider.generate_report(
            job_id=job.job_id,
            workflow_result=wf_run.result_summary,
            model_identity=wf_run.model_identity,
            readiness_snapshot=wf_run.readiness_snapshot,
            job_context=_report_job_context(job),
        )

        job.reports[wid] = ReportMetadata(
            report_id=report.report_id,
            workflow_id=wid,
            report_schema_version=report.report_schema_version,
            status=report.workflow_status,
            generated_at=report.generated_at,
            model_id=report.model_id,
            model_version=report.model_version,
            scientifically_certified=report.scientifically_certified,
        )


def _find_existing_completed_report(
    source_key: str,
    workflow_id: str,
    model_id: str,
    target_side: str = "",
) -> tuple[str, str] | None:
    """Check if a completed report exists for source + workflow + model.

    Returns (job_id, workflow_id) if found, None otherwise.

    PR0141: ``target_side`` is part of the Aramina inference request, so an
    Aramina duplicate identity must include it. A completed left-side run must
    not block a right-side run for the same source and model.

    Bremen behavior is unchanged: ``target_side`` is empty for Bremen, and an
    empty requested side matches any stored side, so the original
    source + workflow + model identity is preserved exactly.
    """
    if not source_key or not model_id:
        return None
    with _jobs_lock:
        for job in _jobs.values():
            if job.overall_status != "completed":
                continue
            isk = job.input_summary or {}
            if isk.get("source_key") != source_key:
                continue
            if isk.get("model_id") != model_id:
                continue
            if workflow_id not in job.requested_workflows:
                continue
            # Side-aware identity: only enforced when a side is requested.
            if target_side and isk.get("target_side", "") != target_side:
                continue
            # Check for completed report
            rm = job.reports.get(workflow_id)
            if rm and rm.status == REPORT_STATUS_AVAILABLE:
                return (job.job_id, workflow_id)
    return None


def delete_report(
    job_id: str,
    workflow_id: str,
) -> dict[str, Any]:
    """Delete a report for a specific job/workflow.

    Returns a result dict with status and metadata.
    Does NOT delete source files, catalog entries, or other model reports.
    """
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return {"status": "not_found", "error": "report_not_found"}

    rm = job.reports.get(workflow_id)
    if rm is None:
        return {"status": "not_found", "error": "report_not_found"}

    model_id = (job.input_summary or {}).get("model_id", "")

    # Soft-delete: mark report as unavailable
    with _jobs_lock:
        job.reports[workflow_id] = ReportMetadata(
            report_id=rm.report_id,
            workflow_id=rm.workflow_id,
            report_schema_version=rm.report_schema_version,
            status=REPORT_STATUS_UNAVAILABLE,
            generated_at=rm.generated_at,
            model_id=rm.model_id,
            model_version=rm.model_version,
            scientifically_certified=rm.scientifically_certified,
        )

    return {
        "status": "deleted",
        "job_id": job_id,
        "workflow_id": workflow_id,
        "model_id": model_id,
        "report_deleted": True,
    }
