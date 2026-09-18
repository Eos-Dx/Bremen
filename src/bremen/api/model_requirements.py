"""Model-specific container requirements API helpers.

PR0122 implements the public API shape only.
PR0124 adds manifest-backed validation awareness.
PR0126 adds read-only model pipeline dry-run validation.

No H5 is opened except during an authorized dry run.
No inference job is created here.
No report is created here.
No persistent state is created during a dry run.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)


class ModelRequirementsNotFoundError(Exception):
    """Requested model_id does not exist in the current catalog."""


# ---------------------------------------------------------------------------
# Dry-run result
# ---------------------------------------------------------------------------

_DRY_RUN_SAFE_FAILURE_STAGES = frozenset({
    "container_resolution",
    "normalization",
    "workflow_resolution",
    "model_artifact",
    "model_validation",
    "input_preparation",
    "feature_production",
    "feature_validation",
    "model_execution",
    "unknown",
})


@dataclass
class DryRunResult:
    """Structured result of a read-only model pipeline dry run.

    No job_id, no report_id, no score/decision payload.
    """

    status: str = "passed"  # "passed" | "failed"
    ready_to_run: bool = True
    checked_stages: list[str] = field(default_factory=list)
    failure_stage: str | None = None
    safe_reason: str = ""
    error_class: str = ""


def _safe_failure_stage(exc: Exception) -> str:
    """Map an exception to a safe stage name for the API response.

    Never exposes traceback, raw exception text, or internal paths.
    """
    msg = str(exc).lower()
    exc_name = type(exc).__name__

    # Container resolution failures
    if "source" in msg or "upload" in msg or "h5_bucket" in msg:
        return "container_resolution"
    if "resolution" in msg:
        return "container_resolution"

    # Normalization failures
    if "normaliz" in msg or "canonical" in msg or "layout" in msg:
        return "normalization"
    if "h5" in msg and ("open" in msg or "read" in msg or "file" in msg):
        return "normalization"

    # Workflow resolution
    if "workflow" in msg and "not found" in msg:
        return "workflow_resolution"

    # Model artifact / validation
    if "model" in msg and ("ready" in msg or "not" in msg or "valid" in msg):
        return "model_artifact"
    if "package" in msg or "checksum" in msg:
        return "model_artifact"

    # Input preparation / compatibility
    if "incompatible" in msg or "sides" in msg or "measurements" in msg:
        return "input_preparation"
    if "input" in msg or "preparation" in msg:
        return "input_preparation"

    # Feature production / validation
    if "feature" in msg:
        return "feature_production"

    # Model execution / inference
    if "predict" in msg or "inference" in msg or "logit" in msg:
        return "model_execution"

    # Known exception classes
    if "NormalizationError" in exc_name:
        return "normalization"
    if "WorkflowIncompatibleError" in exc_name:
        return "input_preparation"
    if "WorkflowConfigurationRequiredError" in exc_name:
        return "input_preparation"
    if "BremenWorkflowError" in exc_name:
        return "model_execution"

    # KeyError often indicates missing key in input data/metadata
    if exc_name == "KeyError":
        return "input_preparation"

    return "unknown"


# ---------------------------------------------------------------------------
# Catalog row helpers
# ---------------------------------------------------------------------------

def find_model_catalog_row(
    model_id: str,
    *,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return a safe public catalog row for model_id.

    Searches both available models and display-only unavailable models.
    This lets the requirements API support future unavailable Aramina
    catalog rows without treating them as executable.
    """
    if catalog is None:
        from bremen.platform.models.catalog import build_model_catalog  # noqa: PLC0415

        catalog = build_model_catalog()

    for key in ("models", "unavailable_models"):
        rows = catalog.get(key, [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("model_id") == model_id:
                return dict(row)

    return None


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            result.append(item)
    return result


def _runtime_input_requirements(model_id: str) -> dict[str, Any] | None:
    """Best-effort derive model-specific input requirements from the runtime.

    PR0153B connects the Model Requirements API to the Model Runtime Contract
    v1 so model-specific requirements come from the runtime rather than from
    duplicated platform knowledge.  Resolution is read-only and defensive:

    - constructs no artifact work and creates no job/report/persistent state;
    - returns ``None`` whenever no contract runtime is reachable (legacy or
      display-only registries, scaffold workflows), preserving the pre-runtime
      response byte-for-byte;
    - never surfaces paths, checksums, tokens or artifact internals (the
      runtime payload is static model-declared values only).
    """
    try:
        from bremen.platform.models.registry import get_model_entry  # noqa: PLC0415

        entry = get_model_entry(model_id)
        if entry is None:
            return None
        from bremen.platform.runtime.registry import get_descriptor_for_model  # noqa: PLC0415

        try:
            provider = get_descriptor_for_model(model_id)
        except ValueError:
            # Unroutable / display-only rows expose no executable runtime.
            return None
        runtime = provider.runtime
        if runtime is None:
            return None
        requirements = getattr(runtime, "model_requirements", None)
        if requirements is None:
            return None
        payload = requirements().to_input_requirements()
        return payload if isinstance(payload, dict) else None
    except Exception:  # noqa: BLE001 -- discovery must never break on runtime derivation
        return None


def _find_container_requirements(
    model_id: str,
    *,
    row: dict[str, Any] | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return model container requirements if available.

    Prefer explicit test/catalog row data when supplied. Otherwise read the
    immutable registry private metadata. This keeps /api/models free of full
    requirements details while letting /requirements expose the contract.
    """
    if row is not None and isinstance(row.get("container_requirements"), dict):
        return dict(row["container_requirements"])

    if catalog is not None:
        catalog_row = find_model_catalog_row(model_id, catalog=catalog)
        if catalog_row is not None and isinstance(
            catalog_row.get("container_requirements"), dict
        ):
            return dict(catalog_row["container_requirements"])

    from bremen.platform.models.registry import (  # noqa: PLC0415
        get_model_container_requirements,
    )

    requirements = get_model_container_requirements(model_id)
    if not isinstance(requirements, dict):
        return None
    return dict(requirements)


# ---------------------------------------------------------------------------
# GET requirements response
# ---------------------------------------------------------------------------

def _build_declared_requirements_response(
    model_id: str,
    row: dict[str, Any],
    requirements: dict[str, Any],
    *,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build a requirements response when a manifest is present."""
    required_fields = _coerce_string_list(requirements.get("required_fields"))
    if not required_fields:
        required_fields = _coerce_string_list(requirements.get("required_metadata"))

    optional_fields = _coerce_string_list(requirements.get("optional_fields"))
    if not optional_fields:
        optional_fields = _coerce_string_list(requirements.get("optional_metadata"))

    # Aramina entries: default required_fields for request_requirements
    workflow_id = row.get("workflow_id")
    if workflow_id == "aramina" and not required_fields:
        required_fields = ["container_id", "source_id", "patient_id", "target_side"]
        optional_fields = ["analysis_author", "prediction_comment"]

    # PR0153B — where a Model Runtime Contract v1 runtime is reachable, derive
    # model-specific request fields from the runtime instead of duplicating
    # platform knowledge, and annotate the container contract additively.
    # When no runtime is available (legacy/scaffold/display-only registries)
    # the response is unchanged.
    runtime_requirements = _runtime_input_requirements(model_id)
    if runtime_requirements is not None:
        if not required_fields:
            required_fields = _coerce_string_list(
                runtime_requirements.get("request_fields"),
            )
        if not optional_fields:
            optional_fields = _coerce_string_list(
                runtime_requirements.get("optional_request_fields"),
            )
        container_requirements = dict(requirements)
        container_requirements["model_runtime"] = {
            "contract_version": runtime_requirements.get("contract_version", "v1"),
            "input_requirements": runtime_requirements,
        }
    else:
        container_requirements = dict(requirements)

    response: dict[str, Any] = {
        "schema_version": "bremen.model_requirements.v1",
        "technical_demo_only": True,
        "model_id": model_id,
        "workflow_id": workflow_id,
        "model_version": row.get("model_version"),
        "feature_schema_version": row.get("feature_schema_version"),
        "requirements_available": True,
        "status": "requirements_declared",
        "required_container_contract": (
            requirements.get("required_container_contract")
            or requirements.get("input_container")
        ),
        "required_fields": required_fields,
        "optional_fields": optional_fields,
        "container_requirements": container_requirements,
        "notes": [
            "Model-specific container requirements are declared by "
            "container_requirements.json next to the model artifact.",
            "No container is opened by this discovery endpoint.",
            "No inference job is created.",
            "No report is generated.",
        ],
    }
    if request_id:
        response["request_id"] = request_id
    return response


def build_model_requirements_response(
    model_id: str,
    *,
    catalog: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build the model requirements response.

    When a valid container_requirements manifest is stored on the registry
    entry, returns a declared contract. Otherwise returns the PR0122 no-op.
    """
    row = find_model_catalog_row(model_id, catalog=catalog)
    if row is None:
        raise ModelRequirementsNotFoundError(model_id)

    requirements = _find_container_requirements(model_id, row=row, catalog=catalog)
    if requirements is not None:
        return _build_declared_requirements_response(
            model_id, row, requirements, request_id=request_id,
        )

    response: dict[str, Any] = {
        "schema_version": "bremen.model_requirements.v1",
        "technical_demo_only": True,
        "model_id": model_id,
        "workflow_id": row.get("workflow_id"),
        "model_version": row.get("model_version"),
        "feature_schema_version": row.get("feature_schema_version"),
        "requirements_available": False,
        "status": "requirements_not_declared",
        "required_container_contract": None,
        "required_fields": [],
        "optional_fields": [],
        "notes": [
            "This endpoint is reserved for model-specific H5/container requirements.",
            "The current runner does not yet declare raw H5 requirement fields.",
            "No container is opened.",
            "No inference job is created.",
            "No report is generated.",
        ],
    }
    if request_id:
        response["request_id"] = request_id
    return response


# ---------------------------------------------------------------------------
# Request payload validation
# ---------------------------------------------------------------------------

def _validate_request_payload(
    request_payload: dict[str, Any],
    requirements: dict[str, Any],
) -> tuple[bool, list[str], list[str]]:
    """Validate request payload against request_requirements from manifest.

    Returns (all_present, missing_required, invalid_fields).
    """
    req_reqs = requirements.get("request_requirements")
    if not isinstance(req_reqs, dict):
        # No request_requirements declared — default to requiring container_id
        required_fields = ["container_id"]
    else:
        required_fields = _coerce_string_list(req_reqs.get("required_fields"))
        if not required_fields:
            required_fields = ["container_id"]

    missing: list[str] = []
    for field_name in required_fields:
        value = request_payload.get(field_name)
        if not value:
            missing.append(field_name)

    return len(missing) == 0, missing, []


# ---------------------------------------------------------------------------
# Read-only model pipeline dry run (PR0126)
# ---------------------------------------------------------------------------

def _resolve_source_for_dry_run(source_id: str) -> str:
    """Resolve a source_id to a local filesystem path for dry-run.

    This is a thin wrapper around the production resolve_source so
    tests can mock it without needing real S3 configuration.
    """
    from bremen.platform.sources.service import resolve_source
    return resolve_source(source_id=source_id, upload_id=None)


def run_model_pipeline_dry_run(
    model_id: str,
    container_id: str,
    source_id: str,
    workflow_id: str,
) -> DryRunResult:
    """Execute a read-only dry run of the real model pipeline.

    Reuses existing production logic:
    - resolve_source for container/source resolution
    - descriptor input policy (raw by default, explicit legacy canonical adapter)
    - get_descriptor_for_model for package runtime selection
    - generic executor for the full package pipeline

    No persistent job state is created.
    No report is generated.
    No event store is written.
    No S3 writes occur.
    The H5 source is not mutated.

    Parameters
    ----------
    model_id : The model to execute against.
    container_id : The container display name (for provenance only).
    source_id : The opaque catalog source reference.
    workflow_id : The workflow to execute (e.g. "bremen").

    Returns
    -------
    A DryRunResult with status, failure_stage, and checked_stages.
    """
    checked_stages: list[str] = []
    h5_path: str = ""
    staged = False

    try:
        # --- Stage 1: Model resolution ---
        checked_stages.append("model_resolution")

        from bremen.platform.models.registry import get_model_entry  # noqa: PLC0415
        entry = get_model_entry(model_id)
        if entry is None:
            return DryRunResult(
                status="failed",
                ready_to_run=False,
                checked_stages=checked_stages,
                failure_stage="model_resolution",
                safe_reason="Model not found in registry",
            )

        h5_path = _resolve_source_for_dry_run(source_id)
        staged = True

        # --- Stage 3: Container resolution confirmed ---
        checked_stages.append("container_resolution")

        # --- Stage 4: H5 normalization ---
        checked_stages.append("normalization")


    # --- Stage 5: Workflow resolution ---
        checked_stages.append("workflow_resolution")

        from bremen.platform.runtime.registry import get_descriptor_for_model  # noqa: PLC0415
        try:
            provider = get_descriptor_for_model(model_id)
        except ValueError:
            return DryRunResult(
                status="failed",
                ready_to_run=False,
                checked_stages=checked_stages,
                failure_stage="workflow_resolution",
                safe_reason="Workflow provider not found for model",
            )

        # --- Stage 6: Full package runtime execution ---
        checked_stages.append("input_preparation")
        checked_stages.append("feature_production")
        checked_stages.append("model_execution")

        from bremen.platform.runtime.executor import run_workflow_request
        outcome = run_workflow_request(h5_path, workflow_id, model_id=model_id,
                                      registry=_single_runtime_registry(provider))
        wf_result = outcome.workflows.get(workflow_id)
        if wf_result is None:
            raise ValueError("Input preparation failed")

        if wf_result.status == "completed":
            return DryRunResult(
                status="passed",
                ready_to_run=True,
                checked_stages=checked_stages,
            )
        else:
            # Map the provider error to a safe failure stage
            error_msg = wf_result.error or ""
            if "incompatible" in error_msg.lower() or "sides" in error_msg.lower():
                fs = "input_preparation"
            elif "feature" in error_msg.lower():
                fs = "feature_production"
            elif "model" in error_msg.lower() and "ready" in error_msg.lower():
                fs = "model_artifact"
            elif "configuration" in error_msg.lower():
                fs = "input_preparation"
            else:
                fs = "model_execution"

            return DryRunResult(
                status="failed",
                ready_to_run=False,
                checked_stages=checked_stages,
                failure_stage=fs,
                safe_reason="Selected container failed read-only pipeline dry run.",
                error_class="workflow_failed",
            )

    except Exception as exc:
        fs = _safe_failure_stage(exc)
        checked_stages.append(fs) if fs not in checked_stages else None

        _log.debug(
            "bremen.dry_run.failed\tstage=%s\tmodel_id=%s\terror_class=%s",
            fs, model_id, type(exc).__name__,
        )

        return DryRunResult(
            status="failed",
            ready_to_run=False,
            checked_stages=checked_stages,
            failure_stage=fs,
            safe_reason="Selected container failed read-only pipeline dry run.",
            error_class=type(exc).__name__,
        )
    finally:
        # Clean up staged H5 file if we downloaded one
        if staged and h5_path:
            try:
                # Only clean up files in temp directories
                if h5_path.startswith("/tmp/") or "staging" in h5_path:
                    os.unlink(h5_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# POST validate response builder
# ---------------------------------------------------------------------------

def build_model_requirements_validation_response(
    model_id: str,
    request_payload: dict[str, Any],
    *,
    catalog: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build model requirements validation response.

    When valid container_requirements exist with request_requirements,
    performs a read-only model pipeline dry run after request payload validation.
    Otherwise returns the PR0122 no-op.

    The dry run reuses production pipeline logic but creates no persistent
    job state, no report, and no event store entries.
    """
    row = find_model_catalog_row(model_id, catalog=catalog)
    if row is None:
        raise ModelRequirementsNotFoundError(model_id)

    requirements = _find_container_requirements(
        model_id,
        row=row,
        catalog=catalog,
    )

    # Determine validation behavior
    validation_available = False
    validation_status = "not_available"
    ready_to_run: bool | None = None
    requirements_checked = False
    missing_required_fields: list[str] = []
    invalid_fields: list[str] = []
    can_submit_job: bool | None = None
    failure_stage: str | None = None
    checked_stages: list[str] = []
    next_step_reason = (
        "Model-specific requirements validation is not implemented yet. "
        "Use POST /demo/api/jobs for the current production execution path."
    )
    dry_run_mode = "request_payload"

    if requirements is not None:
        all_present, missing, invalid = _validate_request_payload(
            request_payload, requirements,
        )
        validation_available = True
        requirements_checked = True
        missing_required_fields = missing
        invalid_fields = invalid

        if not all_present:
            # Request payload validation failed — do not attempt dry run
            validation_status = "failed"
            ready_to_run = False
            can_submit_job = False
            failure_stage = "request_payload"
            dry_run_mode = "request_payload"
            next_step_reason = (
                "Required request fields are missing. "
                "Use POST /demo/api/jobs for execution."
            )
            checked_stages = ["request_payload"]
        else:
            # Request payload OK — run the model pipeline dry run
            dry_run_mode = "model_pipeline"
            workflow_id = row.get("workflow_id", "bremen")
            source_id = request_payload.get("source_id", "")
            container_id = request_payload.get("container_id", "")

            dry_result = run_model_pipeline_dry_run(
                model_id=model_id,
                container_id=container_id,
                source_id=source_id,
                workflow_id=workflow_id,
            )

            validation_status = dry_result.status
            ready_to_run = dry_result.ready_to_run
            failure_stage = dry_result.failure_stage
            can_submit_job = dry_result.ready_to_run

            if dry_result.status == "passed":
                next_step_reason = (
                    "Dry run passed. Use POST /demo/api/jobs for execution."
                )
            else:
                next_step_reason = dry_result.safe_reason or (
                    "Selected container failed read-only pipeline dry run."
                )

            checked_stages = ["request_payload"] + dry_result.checked_stages

    response: dict[str, Any] = {
        "schema_version": "bremen.model_requirements_validation.v1",
        "technical_demo_only": True,
        "model_id": model_id,
        "workflow_id": row.get("workflow_id"),
        "model_version": row.get("model_version"),
        "feature_schema_version": row.get("feature_schema_version"),
        "container_id": request_payload.get("container_id"),
        "source_id": request_payload.get("source_id"),
        "upload_id": request_payload.get("upload_id"),
        "h5_path_supplied": bool(request_payload.get("h5_path")),
        "requirements_available": requirements is not None,
        "requirements_status": (
            "requirements_declared"
            if requirements is not None
            else "requirements_not_declared"
        ),
        "validation_available": validation_available,
        "validation": {
            "status": validation_status,
            "ready_to_run": ready_to_run,
            "requirements_checked": requirements_checked,
            "inference_job_created": False,
            "report_created": False,
            "dry_run_mode": dry_run_mode,
            "read_only": True,
        },
        "checked_stages": checked_stages,
        "missing_required_fields": missing_required_fields,
        "invalid_fields": invalid_fields,
        "failure_stage": failure_stage,
        "next_step": {
            "can_submit_job": can_submit_job,
            "reason": next_step_reason,
        },
    }
    if request_id:
        response["request_id"] = request_id
    return response


def _single_runtime_registry(descriptor):
    from bremen.platform.runtime.registry import RuntimeRegistry
    registry = RuntimeRegistry()
    registry.register(descriptor)
    return registry
