"""Model-specific container requirements API helpers.

PR0122 implements the public API shape only.

The current runner/model stack does not yet declare raw H5/container
requirement fields, so these helpers intentionally return honest
not-available/no-op contracts.

No H5 is opened here.
No inference job is created here.
No report is created here.
"""

from __future__ import annotations

from typing import Any


class ModelRequirementsNotFoundError(Exception):
    """Requested model_id does not exist in the current catalog."""


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
        from bremen.api.model_catalog import build_model_catalog  # noqa: PLC0415

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

    from bremen.api.model_registry import (  # noqa: PLC0415
        get_model_container_requirements,
    )

    requirements = get_model_container_requirements(model_id)
    if not isinstance(requirements, dict):
        return None
    return dict(requirements)


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

    response: dict[str, Any] = {
        "schema_version": "bremen.model_requirements.v1",
        "technical_demo_only": True,
        "model_id": model_id,
        "workflow_id": row.get("workflow_id"),
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
        "container_requirements": dict(requirements),
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


def build_model_requirements_validation_response(
    model_id: str,
    request_payload: dict[str, Any],
    *,
    catalog: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build model requirements validation response.

    When valid container_requirements exist with request_requirements,
    performs request-payload-only validation (no H5, no S3, no inference).
    Otherwise returns the PR0122 no-op.
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
    next_step_reason = (
        "Model-specific requirements validation is not implemented yet. "
        "Use POST /demo/api/jobs for the current production execution path."
    )

    if requirements is not None:
        all_present, missing, invalid = _validate_request_payload(
            request_payload, requirements,
        )
        validation_available = True
        requirements_checked = True
        missing_required_fields = missing
        invalid_fields = invalid

        if all_present:
            validation_status = "passed"
            ready_to_run = True
            can_submit_job = True
            next_step_reason = (
                "All required request fields are present. "
                "Use POST /demo/api/jobs for execution."
            )
        else:
            validation_status = "failed"
            ready_to_run = False
            can_submit_job = False
            next_step_reason = (
                "Required request fields are missing. "
                "Use POST /demo/api/jobs for execution."
            )

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
        },
        "missing_required_fields": missing_required_fields,
        "invalid_fields": invalid_fields,
        "next_step": {
            "can_submit_job": can_submit_job,
            "reason": next_step_reason,
        },
    }
    if request_id:
        response["request_id"] = request_id
    return response
