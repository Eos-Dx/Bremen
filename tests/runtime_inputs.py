"""Build neutral inputs for existing canonical scientific fixtures."""

from bremen.contracts.model_runtime import ModelInput
from bremen.platform.runtime.executor import execute_model


def execute_case(
    descriptor, canonical, context=None, *, aramina_request=None, h5_path=""
):
    request = aramina_request
    model_input = ModelInput(
        workflow_id=descriptor.workflow_id,
        canonical=canonical,
        measurements=getattr(canonical, "measurements", ()),
        container_path=h5_path,
        patient_id=getattr(request, "patient_id", ""),
        target_side=getattr(request, "target_side", ""),
        parameters={
            "analysis_author": getattr(request, "analysis_author", ""),
            "prediction_comment": getattr(request, "prediction_comment", ""),
        },
    )
    return execute_model(
        descriptor, model_input, context, getattr(canonical, "source_checksum", "")
    )
