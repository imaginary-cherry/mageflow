import pytest
from hatchet_sdk.runnables.types import EmptyModel

import mageflow
from mageflow.swarm.consts import SWARM_FILL_TASK
from mageflow.swarm.messages import SwarmMessage
from mageflow.swarm.model import SwarmTaskSignature, SwarmConfig
from mageflow.swarm.workflows import swarm_start_tasks
from tests.integration.hatchet.models import ContextMessage
from tests.unit.conftest import create_mock_context_with_metadata


@pytest.mark.asyncio
async def test_swarm_start_tasks_sanity_basic_flow(mock_invoker_wait_task):
    # Arrange
    original_tasks = [
        await mageflow.sign(f"test_task_{i}", model_validators=ContextMessage)
        for i in range(5)
    ]
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=2),
        tasks=original_tasks,
    )

    ctx = create_mock_context_with_metadata()
    msg = EmptyModel(swarm_task_id=swarm_task.key)
    expected_msg = SwarmMessage(swarm_task_id=swarm_task.key)

    # Act
    await swarm_start_tasks(msg, ctx)

    # Assert
    mock_invoker_wait_task.assert_called_once_with(SWARM_FILL_TASK, expected_msg)


@pytest.mark.asyncio
async def test_swarm_start_tasks_sanity_all_tasks_start(
    mock_task_aio_run_no_wait, mock_invoker_wait_task
):
    # Arrange
    original_tasks = [
        await mageflow.sign(f"test_task_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=5),
        tasks=original_tasks,
    )

    ctx = create_mock_context_with_metadata()
    msg = EmptyModel(swarm_task_id=swarm_task.key)
    expected_msg = SwarmMessage(swarm_task_id=swarm_task.key)

    # Act
    await swarm_start_tasks(msg, ctx)

    # Assert
    mock_invoker_wait_task.assert_called_once_with(SWARM_FILL_TASK, expected_msg)
    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_task.key)
    assert len(reloaded_swarm.tasks_left_to_run) == 0


@pytest.mark.asyncio
async def test_swarm_start_tasks_already_started_edge_case(mock_task_aio_run_no_wait):
    # Arrange
    original_tasks = [
        await mageflow.sign(f"test_task_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=2),
        tasks=original_tasks,
    )
    async with swarm_task.alock() as locked_swarm:
        await locked_swarm.aupdate(current_running_tasks=1)

    ctx = create_mock_context_with_metadata()
    msg = EmptyModel(swarm_task_id=swarm_task.key)

    # Act
    await swarm_start_tasks(msg, ctx)

    # Assert
    mock_task_aio_run_no_wait.assert_not_awaited()


@pytest.mark.asyncio
async def test_swarm_start_tasks_max_concurrency_zero_edge_case(
    mock_task_aio_run_no_wait, mock_invoker_wait_task
):
    # Arrange
    original_tasks = [
        await mageflow.sign(f"test_task_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=0),
        tasks=original_tasks,
    )

    ctx = create_mock_context_with_metadata()
    msg = EmptyModel(swarm_task_id=swarm_task.key)

    # Act
    await swarm_start_tasks(msg, ctx)

    # Assert
    mock_task_aio_run_no_wait.assert_not_awaited()


@pytest.mark.asyncio
async def test_swarm_start_tasks_empty_tasks_list_edge_case(mock_invoker_wait_task):
    # Arrange
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=2),
    )

    ctx = create_mock_context_with_metadata()
    msg = EmptyModel(swarm_task_id=swarm_task.key)

    # Act & Assert
    await swarm_start_tasks(msg, ctx)


@pytest.mark.asyncio
async def test_swarm_start_tasks_missing_swarm_task_id_edge_case(mock_context):
    # Arrange
    ctx = mock_context
    ctx.additional_metadata = {"task_data": {}}
    msg = EmptyModel()

    # Act & Assert
    with pytest.raises(KeyError):
        await swarm_start_tasks(msg, ctx)


@pytest.mark.asyncio
async def test_swarm_start_tasks_swarm_not_found_edge_case():
    # Arrange
    ctx = create_mock_context_with_metadata()
    msg = EmptyModel(swarm_task_id="nonexistent_swarm")

    # Act & Assert
    with pytest.raises(Exception):
        await swarm_start_tasks(msg, ctx)


@pytest.mark.asyncio
async def test_swarm_start_tasks_task_not_found_edge_case():
    # Arrange
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=2),
    )

    await swarm_task.tasks.aextend(["nonexistent_task_1", "nonexistent_task_2"])

    ctx = create_mock_context_with_metadata()
    msg = EmptyModel(swarm_task_id=swarm_task.key)

    # Act & Assert
    with pytest.raises(Exception):
        await swarm_start_tasks(msg, ctx)
