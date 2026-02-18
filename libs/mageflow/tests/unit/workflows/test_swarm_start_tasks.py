import pytest
from thirdmagic.swarm.model import SwarmTaskSignature, SwarmConfig

import mageflow
from mageflow.clients.inner_task_names import SWARM_FILL_TASK
from mageflow.swarm.messages import SwarmMessage
from mageflow.swarm.workflows import swarm_start_tasks
from tests.integration.hatchet.models import ContextMessage
from tests.unit.conftest import create_mock_context_with_metadata


@pytest.mark.asyncio
async def test_swarm_start_tasks_sanity_basic_flow(mock_invoker_wait_task):
    # Arrange
    original_tasks = [
        await mageflow.asign(f"test_task_{i}", model_validators=ContextMessage)
        for i in range(5)
    ]
    swarm_task = await mageflow.aswarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=2),
        tasks=original_tasks,
    )

    ctx = create_mock_context_with_metadata()
    msg = SwarmMessage(swarm_task_id=swarm_task.key)
    expected_msg = SwarmMessage(swarm_task_id=swarm_task.key)

    # Act
    await swarm_start_tasks(msg, ctx)

    # Assert
    mock_invoker_wait_task.assert_called_once_with(SWARM_FILL_TASK, expected_msg)


@pytest.mark.asyncio
async def test_swarm_start_tasks_sanity_all_tasks_start(mock_invoker_wait_task):
    # Arrange
    original_tasks = [
        await mageflow.asign(f"test_task_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]
    swarm_task = await mageflow.aswarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=5),
        tasks=original_tasks,
    )

    ctx = create_mock_context_with_metadata()
    msg = SwarmMessage(swarm_task_id=swarm_task.key)
    expected_msg = SwarmMessage(swarm_task_id=swarm_task.key)

    # Act
    await swarm_start_tasks(msg, ctx)

    # Assert
    mock_invoker_wait_task.assert_called_once_with(SWARM_FILL_TASK, expected_msg)
    reloaded_swarm = await SwarmTaskSignature.aget(swarm_task.key)
    assert len(reloaded_swarm.tasks_left_to_run) == 3
    assert reloaded_swarm.tasks_left_to_run == reloaded_swarm.tasks


@pytest.mark.asyncio
async def test_swarm_start_tasks_already_started_edge_case(mock_adapter):
    # Arrange
    original_tasks = [
        await mageflow.asign(f"test_task_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]
    swarm_task = await mageflow.aswarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=2),
        tasks=original_tasks,
    )
    async with swarm_task.alock() as locked_swarm:
        await locked_swarm.aupdate(current_running_tasks=1)

    ctx = create_mock_context_with_metadata()
    msg = SwarmMessage(swarm_task_id=swarm_task.key)

    # Act
    await swarm_start_tasks(msg, ctx)

    # Assert
    mock_adapter.acall_signatures.assert_not_awaited()
    mock_adapter.acall_signature.assert_not_awaited()


@pytest.mark.asyncio
async def test_swarm_start_tasks_max_concurrency_zero_edge_case(
    mock_adapter, mock_invoker_wait_task
):
    # Arrange
    original_tasks = [
        await mageflow.asign(f"test_task_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]
    swarm_task = await mageflow.aswarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=0),
        tasks=original_tasks,
    )

    ctx = create_mock_context_with_metadata()
    msg = SwarmMessage(swarm_task_id=swarm_task.key)

    # Act
    await swarm_start_tasks(msg, ctx)

    # Assert
    mock_adapter.acall_signatures.assert_not_awaited()
    mock_adapter.acall_signature.assert_not_awaited()


@pytest.mark.asyncio
async def test_swarm_start_tasks_empty_tasks_list_edge_case(mock_invoker_wait_task):
    # Arrange
    swarm_task = await mageflow.aswarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=2),
    )

    ctx = create_mock_context_with_metadata()
    msg = SwarmMessage(swarm_task_id=swarm_task.key)

    # Act & Assert
    await swarm_start_tasks(msg, ctx)
