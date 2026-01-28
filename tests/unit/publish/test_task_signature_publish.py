import pytest
from hatchet_sdk.clients.admin import TriggerWorkflowOptions

import mageflow
from tests.integration.hatchet.models import ContextMessage
from tests.unit.conftest import WorkflowCallCapture


@pytest.mark.asyncio
async def test_aio_run_no_wait_calls_workflow_with_correct_params(
    mock_workflow_run_with_args: list[WorkflowCallCapture],
):
    # Arrange
    task_kwargs = {"task_param": "task_value", "nested": {"key": "value"}}
    base_data = {"test": "data"}
    test_ctx = {"ctx_key": "ctx_value"}
    signature = await mageflow.sign(
        "test_task",
        model_validators=ContextMessage,
        **task_kwargs,
    )
    msg = ContextMessage(base_data=base_data, test_ctx=test_ctx)

    # Act
    await signature.aio_run_no_wait(msg)

    # Assert
    assert len(mock_workflow_run_with_args) == 1
    call = mock_workflow_run_with_args[0]
    assert call.workflow.config.name == "test_task"
    serialized = call.workflow._serialize_input(msg)
    expected = {"base_data": base_data, "test_ctx": test_ctx, **task_kwargs}
    assert serialized == expected


@pytest.mark.asyncio
async def test_aio_run_no_wait_passes_hatchet_options(
    mock_workflow_run_with_args: list[WorkflowCallCapture],
):
    # Arrange
    signature = await mageflow.sign("test_task", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"test": "data"})
    options = TriggerWorkflowOptions(additional_metadata={"custom": "metadata"})

    # Act
    await signature.aio_run_no_wait(msg, options=options)

    # Assert
    assert len(mock_workflow_run_with_args) == 1
    call = mock_workflow_run_with_args[0]
    assert call.kwargs.get("options") == options
