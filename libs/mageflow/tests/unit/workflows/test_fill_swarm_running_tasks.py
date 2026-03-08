from unittest.mock import AsyncMock

import pytest

from mageflow.swarm.messages import FillSwarmMessage
from mageflow.swarm.workflows import fill_swarm_running_tasks
from thirdmagic.clients.lifecycle import BaseLifecycle
from thirdmagic.swarm.model import SwarmTaskSignature


@pytest.mark.asyncio
async def test_handle_finish_tasks_sanity_starts_next_task(
    swarm_task: SwarmTaskSignature,
    mock_adapter,
    mock_activate_success,
    mock_logger,
):
    # Arrange
    msg = FillSwarmMessage(swarm_task_id=swarm_task.key)
    lifecycle = AsyncMock(spec=BaseLifecycle)

    # Act
    await fill_swarm_running_tasks(
        msg.swarm_task_id, msg.max_tasks, lifecycle, mock_logger
    )

    # Assert
    assert mock_adapter.acall_signatures.call_count == 1

    reloaded_swarm = await SwarmTaskSignature.afind_one(swarm_task.key)
    assert len(reloaded_swarm.tasks_left_to_run) == 0

    mock_activate_success.assert_not_awaited()


@pytest.mark.asyncio
async def test_fill_swarm_with_max_tasks_zero_does_not_publish(
    swarm_task: SwarmTaskSignature,
    mock_adapter,
    mock_logger,
):
    # Arrange
    msg = FillSwarmMessage(swarm_task_id=swarm_task.key, max_tasks=0)
    original_tasks = list(swarm_task.tasks_left_to_run)
    lifecycle = AsyncMock(spec=BaseLifecycle)

    # Act
    await fill_swarm_running_tasks(
        msg.swarm_task_id, msg.max_tasks, lifecycle, mock_logger
    )

    # Assert
    mock_adapter.acall_signatures.assert_not_called()
    reloaded_swarm = await SwarmTaskSignature.afind_one(swarm_task.key)
    assert list(reloaded_swarm.tasks_left_to_run) == original_tasks
    assert len(original_tasks)


@pytest.mark.asyncio
async def test_handle_finish_tasks_no_tasks_left_edge_case(
    empty_swarm: SwarmTaskSignature, mock_logger
):
    # Arrange
    msg = FillSwarmMessage(swarm_task_id=empty_swarm.key)
    lifecycle = AsyncMock(spec=BaseLifecycle)

    # Act
    await fill_swarm_running_tasks(
        msg.swarm_task_id, msg.max_tasks, lifecycle, mock_logger
    )

    # Assert
    mock_logger.info.assert_any_call(
        f"Swarm item no new task to run in {empty_swarm.key}"
    )
