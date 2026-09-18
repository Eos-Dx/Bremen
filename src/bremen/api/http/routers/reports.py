"""Reports HTTP route translation."""

from __future__ import annotations
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from bremen.api.http.http_policy import (
    _check_auth_gate,
)


def register(app: FastAPI, version=None):

    @app.get("/demo/api/jobs/{job_id}/reports")
    async def demo_job_reports_route(
        job_id: str,
        request: Request,
    ) -> JSONResponse:
        """List reports for a job.

        Mirrors ``handle_job_reports()`` from job_api_handler.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
        import uuid as _uuid  # noqa: PLC0415
        from bremen.platform.reports.service import get_job_reports

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        result = get_job_reports(job_id)
        result["request_id"] = request_id
        result["technical_demo_only"] = True
        return JSONResponse(content=result)

    @app.get("/demo/api/jobs/{job_id}/reports/{workflow_id}")
    async def demo_job_report_detail_route(
        job_id: str,
        workflow_id: str,
        request: Request,
    ) -> JSONResponse:
        """Get a specific workflow report.

        Mirrors ``handle_job_report()`` from job_api_handler.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
        import uuid as _uuid  # noqa: PLC0415
        from bremen.platform.reports.service import get_job_report

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())
        result = get_job_report(job_id, workflow_id)
        result["request_id"] = request_id
        result["technical_demo_only"] = True
        return JSONResponse(content=result)

    @app.get("/demo/api/reports/{job_id}/external")
    async def demo_external_report_route(
        job_id: str,
        request: Request,
    ) -> JSONResponse:
        """Return external report JSON.

        Mirrors ``handle_external_report()`` from job_api_handler.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
        import uuid as _uuid  # noqa: PLC0415
        from bremen.platform.jobs.service import _jobs
        from bremen.platform.jobs.service import _jobs_lock
        from bremen.platform.reports.service import _get_report_provider
        from bremen.report_ui import build_external_report_json  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())

        with _jobs_lock:
            job = _jobs.get(job_id)

        if job is None:
            return JSONResponse(
                content={
                    "error": "Job not found",
                    "job_id": job_id,
                    "request_id": request_id,
                    "technical_demo_only": True,
                }
            )

        provider = _get_report_provider("bremen")
        wf_run = job.workflow_runs.get("bremen")
        if provider is None or wf_run is None:
            return JSONResponse(
                content={
                    "error": "Report not available",
                    "job_id": job_id,
                    "request_id": request_id,
                    "technical_demo_only": True,
                }
            )

        report = provider.generate_report(
            job_id=job_id,
            workflow_result=wf_run.result_summary,
            model_identity=wf_run.model_identity,
            readiness_snapshot=wf_run.readiness_snapshot,
        )
        external = build_external_report_json(report.to_dict())
        external["request_id"] = request_id
        external["technical_demo_only"] = True
        return JSONResponse(content=external)

    @app.get("/demo/api/reports/{job_id}/internal")
    async def demo_internal_report_route(
        job_id: str,
        request: Request,
    ) -> JSONResponse:
        """Return internal report JSON.

        Mirrors ``handle_internal_report()`` from job_api_handler.
        """
        gate = _check_auth_gate(request)
        if gate is not None:
            return gate
        import uuid as _uuid  # noqa: PLC0415
        from bremen.platform.jobs.service import _jobs
        from bremen.platform.jobs.service import _jobs_lock
        from bremen.platform.reports.service import _get_report_provider
        from bremen.report_ui import build_internal_report_json  # noqa: PLC0415

        request_id = request.headers.get("X-Request-ID") or str(_uuid.uuid4())

        with _jobs_lock:
            job = _jobs.get(job_id)

        if job is None:
            return JSONResponse(
                content={
                    "error": "Job not found",
                    "job_id": job_id,
                    "request_id": request_id,
                    "technical_demo_only": True,
                }
            )

        provider = _get_report_provider("bremen")
        wf_run = job.workflow_runs.get("bremen")
        if provider is None or wf_run is None:
            return JSONResponse(
                content={
                    "error": "Report not available",
                    "job_id": job_id,
                    "request_id": request_id,
                    "technical_demo_only": True,
                }
            )

        report = provider.generate_report(
            job_id=job_id,
            workflow_result=wf_run.result_summary,
            model_identity=wf_run.model_identity,
            readiness_snapshot=wf_run.readiness_snapshot,
        )
        internal = build_internal_report_json(report.to_dict())
        internal["request_id"] = request_id
        internal["technical_demo_only"] = True
        return JSONResponse(content=internal)
