"""Standalone execution of the ``requirements`` / ``validate`` / ``predict``
operations against one local Model Release.

This is the ML-owned scientific execution path.  It uses the unchanged model
package runtimes and the neutral IR-02 JSON codecs.  Harness concerns
(installation, supervision, process limits, activation) are deliberately not
implemented here.
"""

from __future__ import annotations

from typing import Any, Callable

from bremen.contracts.model_runtime import (
    ModelConfigurationRequiredError,
    ModelInferenceFailedError,
    ModelInputInvalidError,
    ModelPreprocessingFailedError,
    ModelRuntimeError,
)
from bremen.contracts.worker_protocol import (
    ERROR_CODE_INFERENCE_FAILED,
    ERROR_CODE_INPUT_INVALID,
    ERROR_CODE_MODEL_NOT_READY,
    ERROR_CODE_PROTOCOL_ERROR,
    ERROR_CODE_QC_FAILED,
    RESULT_STATUS_ERROR,
    RESULT_STATUS_OK,
    WorkerError,
    WorkerProtocolError,
    WorkerRequest,
    WorkerResult,
    encode_model_requirements,
    encode_model_validation,
    encode_runtime_prediction,
)
from bremen.ml_plugin.errors import (
    PluginArtifactError,
    PluginError,
    PluginInputError,
    PluginReleaseError,
)
from bremen.ml_plugin.release import (
    ReleaseConfig,
    apply_preprocessing_environment,
    load_release_config,
)
from bremen.ml_plugin.variants import (
    VariantSpec,
    build_model_input,
    load_runtime,
    variant_spec,
)

__all__ = [
    "execute_operation",
    "runtime_for_requirements",
]

RuntimeLoader = Callable[..., Any]


def runtime_for_requirements(spec: VariantSpec) -> Any:
    """Construct the runtime needed to describe requirements.

    No artifact is deserialized: ``model_requirements()`` is static
    model-owned metadata, and the release avoids touching the artifact until a
    scientific operation actually needs it.
    """
    if spec.runtime_kind == "bremen":
        from bremen.model_packages.bremen_v01 import BremenRuntime

        return BremenRuntime(None)
    if spec.runtime_kind == "aramina":
        from bremen.model_packages.aramina_v0213 import AraminaRuntime
        from bremen.ml_plugin.variants import ArtifactEntry

        return AraminaRuntime(
            entry=ArtifactEntry(spec, artifact_path="", checksum=spec.artifact_checksum)
        )
    raise PluginReleaseError("unknown_runtime_kind")


def _error_result(
    request: WorkerRequest, code: str, safe_reason: str,
) -> WorkerResult:
    return WorkerResult(
        protocol=request.protocol,
        request_id=request.request_id,
        operation=request.operation,
        model_id=request.model_id,
        release_digest=request.release_digest,
        status=RESULT_STATUS_ERROR,
        payload=None,
        error=WorkerError(code=code, safe_reason=safe_reason),
    )


def _safe_reason(exc: BaseException) -> str:
    if isinstance(exc, PluginError):
        reason = exc.safe_reason or exc.code
        return reason if isinstance(reason, str) and reason else exc.code
    if isinstance(exc, WorkerProtocolError):
        return "protocol_error"
    if isinstance(exc, ModelRuntimeError):
        reason = exc.safe_reason
        if isinstance(reason, str) and reason:
            return reason
        return exc.category or "model_runtime_error"
    try:
        from bremen.model_packages.aramina_v0213.errors import (
            AraminaWorkflowError,
        )
    except Exception:  # pragma: no cover - defensive import guard
        AraminaWorkflowError = ()  # type: ignore[assignment]
    if isinstance(exc, AraminaWorkflowError):
        code = exc.code if isinstance(exc.code, str) else "ARAMINA_EXECUTION_FAILED"
        stage = getattr(exc, "stage", None)
        if code == "ARAMINA_UNSUPPORTED_INPUT" and isinstance(stage, str) and stage:
            return f"{code}:{stage}"
        return code
    return "inference_failed"


def _error_code(exc: BaseException) -> str:
    if isinstance(exc, PluginInputError):
        return ERROR_CODE_INPUT_INVALID
    if isinstance(exc, PluginArtifactError):
        return ERROR_CODE_MODEL_NOT_READY
    if isinstance(exc, PluginReleaseError):
        return ERROR_CODE_PROTOCOL_ERROR
    if isinstance(exc, ModelInputInvalidError):
        return ERROR_CODE_INPUT_INVALID
    if isinstance(exc, ModelConfigurationRequiredError):
        return ERROR_CODE_MODEL_NOT_READY
    if isinstance(exc, ModelInferenceFailedError):
        return ERROR_CODE_INFERENCE_FAILED
    if isinstance(exc, ModelPreprocessingFailedError):
        return ERROR_CODE_QC_FAILED
    if isinstance(exc, ModelRuntimeError):
        return ERROR_CODE_INFERENCE_FAILED
    try:
        from bremen.model_packages.aramina_v0213.errors import (
            AraminaWorkflowError,
        )
    except Exception:  # pragma: no cover - defensive import guard
        AraminaWorkflowError = ()  # type: ignore[assignment]
    if isinstance(exc, AraminaWorkflowError):
        if exc.code == "ARAMINA_INVALID_REQUEST":
            return ERROR_CODE_INPUT_INVALID
        if exc.code == "ARAMINA_UNSUPPORTED_INPUT":
            return ERROR_CODE_QC_FAILED
        if exc.code in {
            "ARAMINA_UNSUPPORTED_ARTIFACT",
            "ARAMINA_ARTIFACT_INTEGRITY_FAILED",
            "ARAMINA_MODEL_IDENTITY_MISMATCH",
        }:
            return ERROR_CODE_MODEL_NOT_READY
        return ERROR_CODE_INFERENCE_FAILED
    return ERROR_CODE_INFERENCE_FAILED


def _verify_release_binding(
    request: WorkerRequest, spec: VariantSpec, config: ReleaseConfig,
) -> None:
    if config.release_id != spec.release_id:
        raise PluginReleaseError("release_identity_mismatch")
    if request.model_id != spec.model_id:
        raise PluginReleaseError("model_identity_mismatch")
    if request.release_digest != config.manifest_sha256:
        raise PluginReleaseError("release_digest_mismatch")
    if config.artifact_sha256 != spec.artifact_checksum:
        raise PluginArtifactError("artifact_identity_mismatch")


def execute_operation(
    request: WorkerRequest,
    *,
    release_dir: str,
    job_dir: str,
    runtime_loader: RuntimeLoader | None = None,
) -> WorkerResult:
    """Execute one request against a local release and return a contract result.

    Any failure becomes a typed ``status=error`` result; no exception text,
    path, traceback or patient data is carried.  The function itself never
    raises for a request that already passed ``validate_worker_request``.
    """
    try:
        config = load_release_config(release_dir)
        spec = variant_spec(config.variant)
        _verify_release_binding(request, spec, config)
        apply_preprocessing_environment(config)

        if request.operation == "requirements":
            runtime = runtime_for_requirements(spec)
            payload = encode_model_requirements(runtime.model_requirements())
            # The model package's static requirements view is release-family
            # metadata; the release descriptor owns the concrete artifact
            # identity.  B1/B2/B3 share the Bremen package manifest, so bind
            # the requirements payload to this release's exact model_version
            # without changing any scientific field.
            payload["model_version"] = spec.model_version
            return WorkerResult(
                protocol=request.protocol,
                request_id=request.request_id,
                operation=request.operation,
                model_id=request.model_id,
                release_digest=request.release_digest,
                status=RESULT_STATUS_OK,
                payload=payload,
                error=None,
            )

        loader = runtime_loader or load_runtime
        runtime = loader(
            spec,
            artifact_path=config.artifact_path,
            checksum=config.artifact_sha256,
        )
        model_input = build_model_input(
            spec, release_dir=release_dir, job_dir=job_dir, payload=request.payload,
        )
        if request.operation == "validate":
            payload = encode_model_validation(runtime.validate_model_input(model_input))
        elif request.operation == "predict":
            payload = encode_runtime_prediction(runtime.predict_model(model_input))
        else:  # pragma: no cover - request validation already rejects this
            raise PluginReleaseError("unknown_operation")

        return WorkerResult(
            protocol=request.protocol,
            request_id=request.request_id,
            operation=request.operation,
            model_id=request.model_id,
            release_digest=request.release_digest,
            status=RESULT_STATUS_OK,
            payload=payload,
            error=None,
        )
    except Exception as exc:  # noqa: BLE001 -- fixed, safe boundary translation
        return _error_result(request, _error_code(exc), _safe_reason(exc))
