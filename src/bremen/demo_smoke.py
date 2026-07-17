"""Demo/smoke runner for a running Bremen HTTP service.

Calls the Bremen HTTP API and produces a machine-readable JSON summary
plus pass/fail text suitable for demos, CI smoke tests, and operator
verification.

Standard library only — no third-party dependencies.

Safety
------
- No inference expansion.
- No model loading or deserialization.
- No H5 reads.
- No AWS/S3/network clients (stdlib ``urllib.request`` to supplied base URL only).
- No clinical diagnosis or replacement claims.
- ``technical_demo_only: true`` in every output.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def run_demo_smoke(
    base_url: str = "http://127.0.0.1:8000",
    timeout: int = 30,
    skip_prediction: bool = False,
) -> dict:
    """Run the demo smoke checks against a running Bremen service.

    Performs five checks in order:

    1. **Health check** — ``GET {base_url}/health``
    2. **Model version check** — ``GET {base_url}/model/version``
    3. **Prediction smoke** — ``POST {base_url}/predictions`` (optional;
       skipped if *skip_prediction* is ``True`` or no fixture available).
    4. **Demo route check** — ``GET {base_url}/demo``
    5. **Demo evidence check** — ``GET {base_url}/demo/api/evidence``

    Parameters
    ----------
    base_url : Base URL of the Bremen HTTP service (e.g.
        ``http://127.0.0.1:8000``).
    timeout : Request timeout in seconds.
    skip_prediction : If ``True``, skip the prediction check.

    Returns
    -------
    A dict with keys:
    ``base_url``, ``request_id``, ``checks``, ``health``,
    ``model_version``, ``prediction``, ``demo_routes``,
    ``demo_evidence``, ``warnings``, ``status``,
    ``technical_demo_only``, ``timestamp``.
    """
    request_id = str(uuid.uuid4())
    warnings: list[str] = []
    checks: dict[str, str] = {}
    health_result: dict = {}
    model_version_result: dict = {}
    prediction_result: dict = {
        "status": "not_available",
        "reason": "Prediction check was skipped via --skip-prediction flag.",
    }

    # Strip trailing slash from base_url
    base = base_url.rstrip("/")

    def _request(
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict | None = None,
    ) -> tuple[int, bytes, dict]:
        """Make an HTTP request and return (status, body, headers)."""
        req_headers = {
            "X-Request-ID": request_id,
            **(headers or {}),
        }
        req = Request(
            f"{base}{path}",
            data=body,
            headers=req_headers,
            method=method,
        )
        resp = urlopen(req, timeout=timeout)
        return resp.status, resp.read(), dict(resp.headers)

    # ---- Check 1: Health ----
    try:
        status, body, resp_headers = _request("GET", "/health")
        data = json.loads(body)
        health_result = {
            "status": data.get("status"),
            "model_ready": data.get("model_ready"),
            "service": data.get("service"),
            "version": data.get("version"),
        }
        if status == 200 and data.get("status") == "ok":
            checks["health"] = "pass"
        else:
            checks["health"] = "fail"
            warnings.append(
                f"Health check unexpected: HTTP {status}, "
                f"status={data.get('status')!r}"
            )
    except HTTPError as exc:
        checks["health"] = "fail"
        warnings.append(f"Health check HTTP error: {exc.code}")
        health_result = {"error": str(exc.code)}
    except URLError as exc:
        checks["health"] = "fail"
        warnings.append(f"Health check connection error: {exc.reason}")
        health_result = {"error": str(exc.reason)}
    except Exception as exc:
        checks["health"] = "fail"
        warnings.append(f"Health check error: {exc}")
        health_result = {"error": str(exc)}

    # ---- Check 2: Model version ----
    try:
        status, body, resp_headers = _request("GET", "/model/version")
        data = json.loads(body)
        model_version_result = {
            "model_configured": data.get("model_configured"),
            "model_version": data.get("model_version"),
            "model_checksum": data.get("model_checksum"),
            "feature_schema_version": data.get("feature_schema_version"),
            "threshold_version": data.get("threshold_version"),
            "model_status": data.get("model_status"),
        }
        if status == 200:
            checks["model_version"] = "pass"
        else:
            checks["model_version"] = "fail"
            warnings.append(
                f"Model version check unexpected: HTTP {status}"
            )
    except HTTPError as exc:
        checks["model_version"] = "fail"
        warnings.append(f"Model version check HTTP error: {exc.code}")
        model_version_result = {"error": str(exc.code)}
    except URLError as exc:
        checks["model_version"] = "fail"
        warnings.append(
            f"Model version check connection error: {exc.reason}"
        )
        model_version_result = {"error": str(exc.reason)}
    except Exception as exc:
        checks["model_version"] = "fail"
        warnings.append(f"Model version check error: {exc}")
        model_version_result = {"error": str(exc)}

    # ---- Check 3: Prediction smoke (optional) ----
    if skip_prediction:
        prediction_result = {
            "status": "not_available",
            "reason": "Prediction check was skipped via --skip-prediction flag.",
        }
    else:
        try:
            # Use a lightweight prediction request without requiring a real H5 file
            # Send the minimal valid payload — the server will accept it as an
            # async job submission. The existence of the H5 file is validated
            # during inference execution, not at submission time.
            payload = {
                "target_scan_ref": "demo:target/001",
                "control_scan_ref": "demo:control/001",
                "h5_path": "/tmp/bremen_demo_smoke_placeholder.h5",
                "request_id": request_id,
            }
            body_bytes = json.dumps(payload).encode("utf-8")
            status, body, resp_headers = _request(
                "POST",
                "/predictions",
                body=body_bytes,
                headers={"Content-Type": "application/json"},
            )
            data = json.loads(body)

            if status == 202:
                job_id = data.get("job_id", "")
                prediction_result = {
                    "status": "accepted",
                    "job_id": job_id,
                    "poll_link": data.get("links", {}).get("poll"),
                    "detail": (
                        "Prediction job accepted. The service will attempt "
                        "inference asynchronously. Results depend on H5 file "
                        "availability at the configured path."
                    ),
                }
                checks["prediction"] = "pass"

                # Optional: poll once for status (non-blocking)
                try:
                    time.sleep(0.5)
                    poll_status, poll_body, _ = _request(
                        "GET", f"/predictions/{job_id}"
                    )
                    poll_data = json.loads(poll_body)
                    prediction_result["poll_status"] = poll_data.get("status")
                    if poll_data.get("status") == "completed":
                        result = poll_data.get("result", {})
                        prediction_result["completed"] = True
                        prediction_result["qc_status"] = result.get("qc_status")
                        if result.get("decision_support_report"):
                            dsr = result["decision_support_report"]
                            prediction_result["decision_support"] = {
                                "report_schema_version": dsr.get("report_schema_version"),
                                "p_mri_needed": dsr.get("p_mri_needed"),
                                "triage_recommendation": dsr.get("triage_recommendation"),
                            }
                except Exception:
                    # Poll failure is non-fatal for demo smoke
                    pass
            else:
                prediction_result = {
                    "status": "failed",
                    "http_status": status,
                    "error": data.get("error", "Unknown error"),
                }
                checks["prediction"] = "fail"
                warnings.append(f"Prediction check HTTP {status}: {data.get('error')}")
        except HTTPError as exc:
            prediction_result = {
                "status": "failed",
                "http_status": exc.code,
                "error": str(exc),
            }
            checks["prediction"] = "fail"
            warnings.append(f"Prediction check HTTP error: {exc.code}")
        except URLError as exc:
            prediction_result = {
                "status": "error",
                "error": str(exc.reason),
            }
            checks["prediction"] = "fail"
            warnings.append(
                f"Prediction check connection error: {exc.reason}"
            )
        except Exception as exc:
            prediction_result = {
                "status": "error",
                "error": str(exc),
            }
            checks["prediction"] = "fail"
            warnings.append(f"Prediction check error: {exc}")

    # ---- Check 4: Demo route (/demo) ----
    try:
        status, body, resp_headers = _request("GET", "/demo")
        body_text = body.decode("utf-8")
        html_ok = (
            status == 200
            and "Bremen" in body_text
            and "technical demo" in body_text.lower()
        )
        demo_routes_result = {
            "status": "pass" if html_ok else "fail",
            "http_status": status,
            "contains_bremen": "Bremen" in body_text,
            "contains_technical_demo": "technical demo" in body_text.lower(),
        }
        if html_ok:
            checks["demo_routes"] = "pass"
        else:
            checks["demo_routes"] = "fail"
            warnings.append(
                f"/demo check: HTTP {status}, "
                f"Bremen={'Bremen' in body_text}, "
                f"tech_demo={'technical demo' in body_text.lower()}"
            )
    except HTTPError as exc:
        demo_routes_result = {
            "status": "fail", "http_status": exc.code, "error": str(exc),
        }
        checks["demo_routes"] = "fail"
        warnings.append(f"/demo HTTP error: {exc.code}")
    except URLError as exc:
        demo_routes_result = {
            "status": "error", "error": str(exc.reason),
        }
        checks["demo_routes"] = "fail"
        warnings.append(f"/demo connection error: {exc.reason}")
    except Exception as exc:
        demo_routes_result = {
            "status": "error", "error": str(exc),
        }
        checks["demo_routes"] = "fail"
        warnings.append(f"/demo check error: {exc}")

    # ---- Check 5: Demo evidence route (/demo/api/evidence) ----
    try:
        status, body, resp_headers = _request(
            "GET", "/demo/api/evidence"
        )
        data = json.loads(body)
        json_ok = (
            status == 200
            and data.get("technical_demo_only") is True
            and data.get("product") == "Bremen"
        )
        demo_evidence_result = {
            "status": "pass" if json_ok else "fail",
            "http_status": status,
            "technical_demo_only": data.get("technical_demo_only"),
            "product": data.get("product"),
        }
        if json_ok:
            checks["demo_evidence"] = "pass"
        else:
            checks["demo_evidence"] = "fail"
            warnings.append(
                f"/demo/api/evidence check: HTTP {status}, "
                f"technical_demo_only={data.get('technical_demo_only')}, "
                f"product={data.get('product')}"
            )
    except HTTPError as exc:
        demo_evidence_result = {
            "status": "fail", "http_status": exc.code, "error": str(exc),
        }
        checks["demo_evidence"] = "fail"
        warnings.append(f"/demo/api/evidence HTTP error: {exc.code}")
    except URLError as exc:
        demo_evidence_result = {
            "status": "error", "error": str(exc.reason),
        }
        checks["demo_evidence"] = "fail"
        warnings.append(
            f"/demo/api/evidence connection error: {exc.reason}"
        )
    except (json.JSONDecodeError, Exception) as exc:
        demo_evidence_result = {
            "status": "error", "error": str(exc),
        }
        checks["demo_evidence"] = "fail"
        warnings.append(f"/demo/api/evidence check error: {exc}")

    # ---- Overall status ----
    check_values = set(checks.values())
    if check_values == {"pass"}:
        overall = "pass"
    elif "fail" in check_values:
        overall = "partial" if "pass" in check_values else "fail"
    else:
        overall = "fail"

    result = {
        "technical_demo_only": True,
        "base_url": base_url,
        "request_id": request_id,
        "checks": checks,
        "health": health_result,
        "model_version": model_version_result,
        "prediction": prediction_result,
        "demo_routes": demo_routes_result,
        "demo_evidence": demo_evidence_result,
        "warnings": warnings,
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Add evidence bundle (additive — backward-compatible)
    from .demo_evidence import build_demo_evidence_bundle  # noqa: PLC0415

    result["evidence"] = build_demo_evidence_bundle(
        base_url=base_url,
        request_id=request_id,
        job_id=prediction_result.get("job_id"),
        model_status=model_version_result.get("model_status"),
        model_version=model_version_result.get("model_version"),
        feature_schema_version=model_version_result.get(
            "feature_schema_version"
        ),
        prediction_status=prediction_result.get("status"),
        decision_support=prediction_result.get("decision_support"),
        checks=checks,
        warnings=warnings,
    )

    return result


def main(argv: list[str] | None = None) -> int:
    """Run the demo smoke checks and print the summary.

    Parameters
    ----------
    argv : Command-line args (excluding program name). Default: sys.argv[1:].

    Returns
    -------
    0 if overall is ``\"pass\"`` or ``\"partial\"``, 1 if ``\"fail\"``.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="bremen demo-smoke",
        description=(
            "Run production demo smoke checks against a running "
            "Bremen HTTP service."
        ),
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://127.0.0.1:8000",
        help="Base URL of the Bremen HTTP service (default: http://127.0.0.1:8000).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30).",
    )
    parser.add_argument(
        "--skip-prediction",
        action="store_true",
        help="Skip the prediction check.",
    )

    args = parser.parse_args(argv)

    result = run_demo_smoke(
        base_url=args.base_url,
        timeout=args.timeout,
        skip_prediction=args.skip_prediction,
    )

    # Print machine-readable JSON summary
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Print human-readable summary
    status_str = result["status"].upper()
    print(f"\nDemo Smoke Result: {status_str}")
    for key, value in result["checks"].items():
        print(f"  {key}: {value}")
    if result["warnings"]:
        print("  Warnings:")
        for w in result["warnings"]:
            print(f"    - {w}")
    print(f"  request_id: {result['request_id']}")

    return 0 if result["status"] in ("pass", "partial") else 1


if __name__ == "__main__":
    raise SystemExit(main())
