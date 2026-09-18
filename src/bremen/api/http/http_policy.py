"""Shared HTTP authentication and safe request rejection policy."""

from __future__ import annotations
from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

_JOB_FIELDS = frozenset(
    {
        "workflow_id",
        "model_id",
        "source_id",
        "upload_id",
        "h5_path",
        "container_id",
        "action",
        "patient_id",
        "target_side",
        "analysis_author",
        "prediction_comment",
    }
)


def _log_job_rejection(
    reason: str, fields=(), stage: str = "request_validation"
) -> None:
    """Always-on rejection reason; field names only, never request values."""
    import logging

    allowed_reasons = {
        "INVALID_JSON",
        "INVALID_REQUEST_SCHEMA",
        "UNSUPPORTED_ACTION",
        "ARAMINA_INVALID_REQUEST",
        "AMBIGUOUS_SOURCE",
        "MISSING_SOURCE",
        "SOURCE_ERROR",
        "ARAMINA_PATIENT_MISMATCH",
    }
    safe_reason = reason if reason in allowed_reasons else "INVALID_REQUEST_SCHEMA"
    safe_stage = (
        stage
        if stage in {"request_validation", "source_resolution", "job_creation"}
        else "request_validation"
    )
    safe_fields = (
        ",".join(
            sorted(
                {
                    field
                    for field in fields
                    if isinstance(field, str) and field in _JOB_FIELDS
                }
            )
        )
        or "none"
    )
    try:
        logging.getLogger(__name__).warning(
            "runtime.job_request.rejected\tstage=%s\tstatus=rejected\thttp_status=400\treason=%s\tinvalid_fields=%s",
            safe_stage,
            safe_reason,
            safe_fields,
        )
    except Exception:  # noqa: BLE001, S110 -- diagnostics cannot alter API behavior
        pass


def _invalid_aramina_fields(body: dict) -> list[str]:
    """Name invalid Aramina inputs using the runtime's current field rules."""
    fields = []
    patient = body.get("patient_id", "")
    side = body.get("target_side", "")
    if not isinstance(patient, str) or not patient.strip():
        fields.append("patient_id")
    if not isinstance(side, str) or side.strip().lower() not in {"left", "right"}:
        fields.append("target_side")
    for field in ("analysis_author", "prediction_comment"):
        if not isinstance(body.get(field, ""), str):
            fields.append(field)
    return fields


# ------------------------------------------------------------------
# Auth enforcement dependency (PR0111)
# ------------------------------------------------------------------

_AUTH_ERROR_SHAPE: dict = {
    "error": "Authentication failed",
    "token_type": "Bearer",
    "technical_demo_only": True,
}


def _check_auth_gate(request: Request) -> JSONResponse | None:
    """Check auth gate for a request.

    Returns None if request is allowed, or a JSONResponse 401 if rejected.
    When auth is disabled or has validation_error, all requests pass.
    When auth is enabled, a valid Bearer access token is required.
    """
    from bremen.api.http.auth_config import _get_auth_config as _gac  # noqa: PLC0415

    config = _gac()
    if not config.enabled or config.validation_error:
        return None  # auth not active — allow

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.strip().startswith("Bearer "):
        return JSONResponse(content=_AUTH_ERROR_SHAPE, status_code=401)

    from bremen.auth import (  # noqa: PLC0415
        decode_access_token,
        AuthError,
    )

    token = (
        auth_header.split(None, 1)[1].strip()
        if len(auth_header.split(None, 1)) == 2
        else ""
    )
    if not token:
        return JSONResponse(content=_AUTH_ERROR_SHAPE, status_code=401)

    try:
        decode_access_token(config, token)
    except AuthError:
        return JSONResponse(content=_AUTH_ERROR_SHAPE, status_code=401)

    return None  # token valid — allow


def _check_auth_gate_with_ticket(
    request: Request,
    job_id: str,
    purpose: str,
) -> JSONResponse | None:
    """Check auth gate with ticket fallback for SSE/report routes.

    Gate ordering:
    1. If auth disabled → allow (unchanged)
    2. If Authorization header present:
       a. Try Bearer access token
       b. If valid → allow
       c. If invalid → fall through to step 3
    3. If query parameter ``auth_ticket`` present:
       a. Decode as stream_ticket
       b. Validate job_id and purpose
       c. If valid → allow; if invalid → 401
    4. Otherwise → 401
    """
    from bremen.api.http.auth_config import _get_auth_config as _gac  # noqa: PLC0415

    config = _gac()
    if not config.enabled or config.validation_error:
        return None  # auth not active — allow

    # Step 2: Try Bearer access token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.strip().startswith("Bearer "):
        token = (
            auth_header.split(None, 1)[1].strip()
            if len(auth_header.split(None, 1)) == 2
            else ""
        )
        if token:
            try:
                from bremen.auth import decode_access_token  # noqa: PLC0415

                decode_access_token(config, token)
                return None  # valid Bearer — allow
            except Exception:  # noqa: BLE001
                pass  # invalid Bearer — fall through to ticket check

    # Step 3: Try auth_ticket query parameter
    ticket = request.query_params.get("auth_ticket", "")
    if ticket:
        try:
            from bremen.auth import decode_stream_ticket  # noqa: PLC0415

            decode_stream_ticket(config, ticket, job_id, purpose)
            return None  # valid ticket — allow
        except Exception:  # noqa: BLE001
            return JSONResponse(content=_AUTH_ERROR_SHAPE, status_code=401)

    # Step 4: No valid auth
    return JSONResponse(content=_AUTH_ERROR_SHAPE, status_code=401)


def _browser_auth_redirect(
    gate: JSONResponse | None,
    next_path: str,
) -> RedirectResponse | None:
    """Convert a JSON auth gate failure into a login redirect for browser routes.

    Browser document navigation cannot attach Authorization headers, so
    browser-navigation HTML routes must not return raw JSON Bearer errors as
    the page body. When the gate rejects a request, redirect to the login page
    with a ``next`` parameter so the user can return after authenticating.

    Returns None when the gate allowed the request, or a RedirectResponse to
    ``/demo/login?next=<next_path>`` when the gate rejected it.
    """
    if gate is None:
        return None
    # next_path is always constructed from controlled values (fixed paths and
    # UUID job IDs), which are URL-safe. Encode any remaining unsafe characters
    # manually to avoid importing urllib (prohibited in this module).
    safe_path = next_path.replace("%", "%25").replace(" ", "%20")
    return RedirectResponse(
        url=f"/demo/login?next={safe_path}",
        status_code=302,
    )
