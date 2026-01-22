import pytest

from mageflow.swarm.messages import SwarmMessage
from mageflow.swarm.model import SwarmTaskSignature
from mageflow.swarm.workflows import fill_swarm_running_tasks


@pytest.mark.asyncio
async def test_handle_finish_tasks_sanity_starts_next_task(
    swarm_with_ready_task: SwarmTaskSignature,
    mock_context,
    mock_batch_task_run,
    mock_activate_success,
):
    # Arrange
    msg = SwarmMessage(swarm_task_id=swarm_with_ready_task.key)

    # Act
    await fill_swarm_running_tasks(msg, mock_context)

    # Assert
    assert len(mock_batch_task_run.called_instances) == 1

    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_with_ready_task.key)
    assert len(reloaded_swarm.tasks_left_to_run) == 0

    mock_activate_success.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_finish_tasks_no_tasks_left_edge_case(
    empty_swarm: SwarmTaskSignature, mock_context
):
    # Arrange
    msg = SwarmMessage(swarm_task_id=empty_swarm.key)

    # Act
    await fill_swarm_running_tasks(msg, mock_context)

    # Assert
    mock_context.log.assert_any_call(
        f"Swarm item no new task to run in {empty_swarm.key}"
    )
