import asyncio
from unittest.mock import patch

import pytest
import pytest_asyncio
import rapyer
from thirdmagic.task import TaskSignature
from thirdmagic.swarm.model import SwarmTaskSignature, SwarmConfig
from thirdmagic.swarm.state import PublishState

from tests.integration.hatchet.models import ContextMessage


@pytest_asyncio.fixture()
async def original_tasks():
    swarm_tasks = [
        TaskSignature(task_name=f"original_task_{i}", model_validators=ContextMessage)
        for i in range(5)
    ]
    await rapyer.ainsert(*swarm_tasks)
    yield swarm_tasks


@pytest_asyncio.fixture()
async def swarm_signature(publish_state):
    swarm_signature = SwarmTaskSignature(
        task_name="test_swarm",
        model_validators=ContextMessage,
        current_running_tasks=0,
        config=SwarmConfig(max_concurrency=3),
        publishing_state_id=publish_state.key,
    )
    await rapyer.ainsert(swarm_signature)
    yield swarm_signature


@pytest.mark.asyncio
async def test_retry_after_crash_after_moved_tasks_to_publish_state__no_more_tasks_added_to_publish_state(
    publish_state, swarm_signature, original_tasks, mock_adapter
):
    # Arrange
    tasks = await swarm_signature.add_tasks(original_tasks)
    task_keys = [task.key for task in tasks]
    await swarm_signature.tasks_left_to_run.aclear()
    await swarm_signature.tasks_left_to_run.aextend(task_keys)
    expected_num_of_tasks_left = (
        len(swarm_signature.tasks_left_to_run) - swarm_signature.config.max_concurrency
    )

    # Act
    with pytest.raises(RuntimeError):
        with patch("rapyer.afind", side_effect=RuntimeError):
            await swarm_signature.fill_running_tasks()
    await swarm_signature.fill_running_tasks()

    # Assert
    # Check the tasks were executed
    mock_adapter.acall_signatures.assert_awaited_once_with(
        tasks[:3], [None] * 3, set_return_field=False
    )

    # Check the tasks were deleted from the swarm left to run
    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_signature.key)
    assert len(reloaded_swarm.tasks_left_to_run) == expected_num_of_tasks_left

    # Check the publish state was cleared
    reloaded_publish_state = await PublishState.aget(publish_state.key)
    assert list(reloaded_publish_state.task_ids) == []


@pytest.mark.asyncio
async def test_two_consecutive_calls_ignore_second_call__no_concurrency_resource_left(
    swarm_signature, original_tasks, mock_adapter
):
    # Arrange
    tasks = await swarm_signature.add_tasks(original_tasks)
    task_keys = [task.key for task in tasks]
    await swarm_signature.tasks_left_to_run.aclear()
    await swarm_signature.tasks_left_to_run.aextend(task_keys)

    # Act
    result1 = await swarm_signature.fill_running_tasks()
    result2 = await swarm_signature.fill_running_tasks()

    # Assert
    assert len(result1) == 3
    assert len(result2) == 0
    mock_adapter.acall_signatures.assert_awaited_once_with(
        tasks[:3], [None] * 3, set_return_field=False
    )

    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_signature.key)
    assert reloaded_swarm.tasks_left_to_run == swarm_signature.tasks[-2:]
    reloaded_publish_state = await PublishState.aget(
        swarm_signature.publishing_state_id
    )
    assert reloaded_publish_state.task_ids == []


@pytest.mark.asyncio
async def test_concurrent_calls_single_execution_idempotent(
    publish_state, swarm_signature, original_tasks, mock_adapter
):
    # Arrange
    tasks = await swarm_signature.add_tasks(original_tasks)
    task_keys = [task.key for task in tasks]
    await swarm_signature.tasks_left_to_run.aclear()
    await swarm_signature.tasks_left_to_run.aextend(task_keys)

    # Act
    results = await asyncio.gather(
        swarm_signature.fill_running_tasks(),
        swarm_signature.fill_running_tasks(),
        swarm_signature.fill_running_tasks(),
    )

    # Assert
    total_tasks_started = sum([len(res) for res in results])
    assert total_tasks_started == 3

    mock_adapter.acall_signatures.assert_awaited_once_with(
        tasks[:3], [None] * 3, set_return_field=False
    )

    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_signature.key)
    assert len(reloaded_swarm.tasks_left_to_run) == 2


@pytest.mark.asyncio
async def test__retry_when_swarm_task_was_changed_between_retry__publish_state_ignore_new_task(
    publish_state, swarm_signature, original_tasks, mock_adapter
):
    # Arrange
    tasks = await swarm_signature.add_tasks(original_tasks)
    task_keys = [task.key for task in tasks]
    max_curr = swarm_signature.config.max_concurrency
    tasks_left_run = task_keys[: max_curr - 1]
    expected_published_tasks = original_tasks[: max_curr - 1]
    await swarm_signature.tasks_left_to_run.aclear()
    await swarm_signature.tasks_left_to_run.aextend(tasks_left_run)

    # Act
    with pytest.raises(RuntimeError):
        with patch("rapyer.afind", side_effect=RuntimeError):
            await swarm_signature.fill_running_tasks()
    await swarm_signature.tasks_left_to_run.aappend(task_keys[max_curr])
    await swarm_signature.fill_running_tasks()

    # Assert
    mock_adapter.acall_signatures.assert_called_once_with(
        expected_published_tasks,
        [None] * len(expected_published_tasks),
        set_return_field=False,
    )
    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_signature.key)
    assert reloaded_swarm.tasks_left_to_run == [task_keys[max_curr]]
    reloaded_publish_state = await PublishState.aget(
        swarm_signature.publishing_state_id
    )
    assert list(reloaded_publish_state.task_ids) == []
