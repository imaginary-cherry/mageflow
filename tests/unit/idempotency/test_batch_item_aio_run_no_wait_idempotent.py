from unittest.mock import patch

import pytest

from mageflow.signature.model import TaskSignature
from mageflow.swarm.model import SwarmTaskSignature
from tests.unit.conftest import mock_fill_running_tasks


@pytest.mark.asyncio
async def test_crash_at_get_swarm_no_state_change_retry_succeeds_idempotent(
    batch_item_run_setup, mock_fill_running_tasks
):
    # Arrange
    setup = batch_item_run_setup
    swarm_task = setup.swarm_task

    # Act
    with patch.object(SwarmTaskSignature, "get_safe", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            await setup.batch_task.aio_run_no_wait(setup.msg)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_task.key)
    assert reloaded_swarm == swarm_task

    # Act
    await setup.batch_task.aio_run_no_wait(setup.msg)

    # Assert
    swarm_copy = swarm_task.copy()
    swarm_copy.tasks_left_to_run.append(setup.batch_task.key)
    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_task.key)
    assert reloaded_swarm == swarm_task
    mock_fill_running_tasks.assert_awaited_once_with(max_tasks=1)


@pytest.mark.asyncio
async def test_crash_on_fill_running_task__check_data_update_the_same(
    batch_item_run_setup_at_max_concurrency,
):
    # Arrange
    setup = batch_item_run_setup_at_max_concurrency
    swarm = setup.swarm_task
    duplicated_task = await setup.original_task.aduplicate()
    duplicate_batch_item = await swarm.add_task(duplicated_task)

    # Act
    with patch.object(
        SwarmTaskSignature, "fill_running_tasks", side_effect=RuntimeError
    ):
        with pytest.raises(RuntimeError):
            await setup.batch_task.aio_run_no_wait(setup.msg)
    await setup.batch_task.aio_run_no_wait(setup.msg)
    await duplicate_batch_item.aio_run_no_wait(setup.msg)

    # Assert
    loaded_duplicate = await TaskSignature.get_safe(duplicated_task.key)
    loaded_task = await TaskSignature.get_safe(setup.original_task.key)
    assert loaded_duplicate.kwargs == loaded_task.kwargs
