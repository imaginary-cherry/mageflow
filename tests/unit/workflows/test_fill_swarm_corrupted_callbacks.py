import base64

import pytest
from hatchet_sdk.runnables.types import EmptyModel

from mageflow.models.message import DEFAULT_RESULT_NAME
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.signature.model import TaskSignature
from mageflow.swarm.workflows import fill_swarm_running_tasks
from tests.unit.workflows.conftest import CompletedSwarmWithSuccessCallback


async def corrupt_model_validators_in_redis(signature_key: str, redis_client):
    invalid_pickle = base64.b64encode(b"invalid_pickle_data").decode("utf-8")
    await redis_client.json().set(signature_key, "$.model_validators", invalid_pickle)


@pytest.mark.asyncio
async def test_activate_success_with_corrupted_callback_model_validators_succeeds(
    completed_swarm_with_success_callback: CompletedSwarmWithSuccessCallback,
    mock_workflow_run,
    redis_client,
):
    # Arrange
    setup = completed_swarm_with_success_callback
    success_callbacks = setup.swarm_task.success_callbacks
    for signature in success_callbacks:
        await corrupt_model_validators_in_redis(signature, redis_client)

    # Act
    await fill_swarm_running_tasks(setup.msg, setup.ctx)

    # Assert
    assert len(mock_workflow_run.captured_workflows) == len(success_callbacks)
    for workflow in mock_workflow_run.captured_workflows:
        signature_id = workflow._task_ctx[TASK_ID_PARAM_NAME]
        assert signature_id in success_callbacks
        assert workflow._return_value_field == DEFAULT_RESULT_NAME
        reloaded_callback = await TaskSignature.get_safe(signature_id)
        assert reloaded_callback.model_validators is None
        assert workflow.input_validator == EmptyModel


@pytest.mark.asyncio
async def test_activate_error_with_corrupted_callback_model_validators_succeeds(
    completed_swarm_with_success_callback: CompletedSwarmWithSuccessCallback,
    mock_workflow_run,
    redis_client,
):
    # Arrange
    setup = completed_swarm_with_success_callback
    error_callbacks = setup.swarm_task.success_callbacks
    for signature in error_callbacks:
        await corrupt_model_validators_in_redis(signature, redis_client)

    # Act
    await fill_swarm_running_tasks(setup.msg, setup.ctx)

    # Assert
    assert len(mock_workflow_run.captured_workflows) == len(error_callbacks)
    for workflow in mock_workflow_run.captured_workflows:
        signature_id = workflow._task_ctx[TASK_ID_PARAM_NAME]
        reloaded_callback = await TaskSignature.get_safe(signature_id)
        assert reloaded_callback.model_validators is None
        assert signature_id in error_callbacks
        assert workflow._return_value_field == DEFAULT_RESULT_NAME
        assert workflow.input_validator == EmptyModel
