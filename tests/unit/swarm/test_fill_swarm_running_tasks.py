import pytest

from mageflow.signature.model import TaskSignature
from mageflow.signature.status import TaskStatus, SignatureStatus
from mageflow.swarm.messages import SwarmMessage
from mageflow.swarm.model import SwarmTaskSignature, SwarmConfig
from mageflow.swarm.workflows import fill_swarm_running_tasks
from tests.integration.hatchet.models import ContextMessage


@pytest.mark.asyncio
async def test_handle_finish_tasks_sanity_starts_next_task(
    mock_context, mock_batch_task_run, mock_activate_success, publish_state
):
    # Arrange
    swarm_task = SwarmTaskSignature(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=2),
        current_running_tasks=0,
        is_swarm_closed=False,
        publishing_state_id=publish_state.key,
    )
    await swarm_task.asave()

    original_task = TaskSignature(task_name="test_task", model_validators=ContextMessage)
    await original_task.asave()

    batch_task = await swarm_task.add_task(original_task)
    await swarm_task.tasks_left_to_run.aappend(batch_task.key)

    msg = SwarmMessage(swarm_task_id=swarm_task.key)

    # Act
    await fill_swarm_running_tasks(msg, mock_context)

    # Assert
    assert len(mock_batch_task_run.called_instances) == 1

    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_task.key)
    assert len(reloaded_swarm.tasks_left_to_run) == 0

    mock_activate_success.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_finish_tasks_sanity_swarm_completes(
    mock_context, mock_activate_success, publish_state
):
    # Arrange
    swarm_task = SwarmTaskSignature(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1),
        current_running_tasks=0,
        is_swarm_closed=True,
        publishing_state_id=publish_state.key,
        task_status=TaskStatus(status=SignatureStatus.DONE),
    )
    await swarm_task.asave()

    task = TaskSignature(task_name="test_task", model_validators=ContextMessage)
    await task.asave()

    await swarm_task.tasks.aappend(task.key)
    await swarm_task.finished_tasks.aappend(task.key)

    msg = SwarmMessage(swarm_task_id=swarm_task.key)

    # Act
    await fill_swarm_running_tasks(msg, mock_context)

    # Assert
    mock_activate_success.assert_awaited_once_with(msg)


@pytest.mark.asyncio
async def test_handle_finish_tasks_no_tasks_left_edge_case(mock_context, publish_state):
    # Arrange
    swarm_task = SwarmTaskSignature(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=2),
        current_running_tasks=0,
        is_swarm_closed=False,
        publishing_state_id=publish_state.key,
    )
    await swarm_task.asave()

    msg = SwarmMessage(swarm_task_id=swarm_task.key)

    # Act
    await fill_swarm_running_tasks(msg, mock_context)

    # Assert
    mock_context.log.assert_any_call(
        f"Swarm item no new task to run in {swarm_task.key}"
    )


@pytest.mark.asyncio
async def test_handle_finish_tasks_exception_during_activate_success_edge_case(
    mock_context, mock_activate_success_error, publish_state
):
    # Arrange
    swarm_task = SwarmTaskSignature(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1),
        current_running_tasks=0,
        is_swarm_closed=True,
        publishing_state_id=publish_state.key,
        task_status=TaskStatus(status=SignatureStatus.DONE),
    )
    await swarm_task.asave()

    task = TaskSignature(task_name="test_task", model_validators=ContextMessage)
    await task.asave()

    await swarm_task.tasks.aappend(task.key)
    await swarm_task.finished_tasks.aappend(task.key)

    msg = SwarmMessage(swarm_task_id=swarm_task.key)

    # Act & Assert
    with pytest.raises(RuntimeError):
        await fill_swarm_running_tasks(msg, mock_context)

    mock_activate_success_error.assert_awaited_once_with(msg)
