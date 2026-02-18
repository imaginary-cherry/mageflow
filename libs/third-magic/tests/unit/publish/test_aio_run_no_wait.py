import pytest
from hatchet_sdk.clients.admin import TriggerWorkflowOptions

import thirdmagic
from tests.unit.messages import ContextMessage
from thirdmagic.swarm.consts import SWARM_MESSAGE_PARAM_NAME
from thirdmagic.swarm.model import SwarmTaskSignature


@pytest.mark.asyncio
async def test_aio_run_no_wait_calls_workflow_with_correct_params(
    chain_with_two_tasks, mock_adapter
):
    # Arrange
    chain, first_task, first_task_kwargs = chain_with_two_tasks
    base_data = {"chain": "data"}
    test_ctx = {"ctx": "value"}
    msg = ContextMessage(base_data=base_data, test_ctx=test_ctx)
    options = TriggerWorkflowOptions(additional_metadata={"chain_custom": "value"})

    # Act
    await chain.aio_run_no_wait(msg, options)

    # Assert
    mock_adapter.acall_signature.assert_awaited_once_with(
        first_task, msg, set_return_field=False, options=options
    )


@pytest.mark.asyncio
async def test_aio_run_no_wait_calls_workflow_with_correct_params(
    mock_adapter,
):
    # Arrange
    base_data = {"test": "data"}
    test_ctx = {"ctx_key": "ctx_value"}
    signature = await thirdmagic.sign("test_task", model_validators=ContextMessage)
    msg = ContextMessage(base_data=base_data, test_ctx=test_ctx)

    # Act
    await signature.aio_run_no_wait(msg)

    # Assert
    mock_adapter.acall_signature.assert_awaited_once_with(signature, msg, False)


@pytest.mark.asyncio
async def test_aio_run_no_wait_updates_kwargs_from_message(
    swarm_with_kwargs: tuple[SwarmTaskSignature, dict], mock_adapter
):
    # Arrange
    swarm, swarm_kwargs = swarm_with_kwargs
    base_data = {"new": "data"}
    msg = ContextMessage(base_data=base_data)
    options = TriggerWorkflowOptions(additional_metadata={"swarm_custom": "metadata"})

    # Act
    await swarm.aio_run_no_wait(msg, options)

    # Assert
    mock_adapter.astart_swarm.assert_awaited_once_with(swarm, options=options)
    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm.key)
    msg_dump = msg.model_dump(mode="json", exclude_unset=True)
    assert reloaded_swarm.kwargs[SWARM_MESSAGE_PARAM_NAME] == msg_dump
    assert reloaded_swarm.kwargs["existing"] == swarm_kwargs["existing"]
