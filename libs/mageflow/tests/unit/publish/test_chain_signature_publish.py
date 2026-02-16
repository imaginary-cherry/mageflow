import pytest
import pytest_asyncio
from hatchet_sdk.clients.admin import TriggerWorkflowOptions

import mageflow
from tests.integration.hatchet.models import ContextMessage
from tests.unit.conftest import WorkflowCallCapture


@pytest_asyncio.fixture
async def chain_with_two_tasks():
    first_task_kwargs = {"first_param": "first_value"}
    first_task = await mageflow.sign(
        "first_task", model_validators=ContextMessage, **first_task_kwargs
    )
    second_task = await mageflow.sign("second_task", model_validators=ContextMessage)
    chain = await mageflow.chain([first_task, second_task])
    return chain, first_task, first_task_kwargs


@pytest.mark.asyncio
async def test_aio_run_no_wait_calls_workflow_with_correct_params(
    mock_workflow_run_with_args: list[WorkflowCallCapture],
    chain_with_two_tasks,
):
    # Arrange
    chain, first_task, first_task_kwargs = chain_with_two_tasks
    base_data = {"chain": "data"}
    test_ctx = {"ctx": "value"}
    msg = ContextMessage(base_data=base_data, test_ctx=test_ctx)

    # Act
    await chain.aio_run_no_wait(msg)

    # Assert
    assert len(mock_workflow_run_with_args) == 1
    call = mock_workflow_run_with_args[0]
    assert call.workflow.config.name == first_task.task_name
    serialized = call.workflow._serialize_input(msg)
    expected = {"base_data": base_data, "test_ctx": test_ctx, **first_task_kwargs}
    assert serialized == expected


@pytest.mark.asyncio
async def test_aio_run_no_wait_passes_hatchet_options(
    mock_workflow_run_with_args: list[WorkflowCallCapture],
    chain_with_two_tasks,
):
    # Arrange
    chain, _, _ = chain_with_two_tasks
    msg = ContextMessage(base_data={"chain": "data"})
    options = TriggerWorkflowOptions(additional_metadata={"chain_custom": "value"})

    # Act
    await chain.aio_run_no_wait(msg, options=options)

    # Assert
    assert len(mock_workflow_run_with_args) == 1
    call = mock_workflow_run_with_args[0]
    assert call.kwargs.get("options") == options
