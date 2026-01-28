import asyncio
from unittest.mock import patch

import pytest
import pytest_asyncio
import rapyer
from mageflow.signature.model import TaskSignature
from mageflow.swarm.model import SwarmTaskSignature, SwarmConfig, BatchItemTaskSignature
from mageflow.swarm.state import PublishState
from tests.integration.hatchet.models import ContextMessage
from tests.unit.conftest import assert_task_were_published


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
    publish_state, swarm_signature, original_tasks, mock_task_run
):
    # Arrange
    batch_tasks = [
        await swarm_signature.add_task(original_task)
        for original_task in original_tasks
    ]
    task_keys = [task.key for task in batch_tasks]
    original_task_keys = [task.original_task_id for task in batch_tasks]
    await swarm_signature.tasks_left_to_run.aextend(task_keys)
    expected_num_of_tasks_left = (
        len(swarm_signature.tasks_left_to_run) - swarm_signature.config.max_concurrency
    )

    # Act
    with pytest.raises(RuntimeError):
        with patch.object(BatchItemTaskSignature, "afind", side_effect=RuntimeError):
            await swarm_signature.fill_running_tasks()
    await swarm_signature.fill_running_tasks()

    # Assert
    # Check the tasks were executed
    assert_task_were_published(mock_task_run, original_task_keys[:3])

    # Check the tasks were deleted from the swarm left to run
    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_signature.key)
    assert len(reloaded_swarm.tasks_left_to_run) == expected_num_of_tasks_left

    # Check the publish state was cleared
    reloaded_publish_state = await PublishState.aget(publish_state.key)
    assert list(reloaded_publish_state.task_ids) == []


@pytest.mark.asyncio
async def test_retry_does_not_double_append_to_publish_state_idempotent(
    publish_state, swarm_signature, original_tasks, mock_task_run
):
    # Arrange
    batch_tasks = [
        await swarm_signature.add_task(original_task)
        for original_task in original_tasks
    ]
    task_keys = [task.key for task in batch_tasks]
    original_task_keys = [task.original_task_id for task in batch_tasks]
    await swarm_signature.tasks_left_to_run.aextend(task_keys[:3])

    # Act
    await swarm_signature.fill_running_tasks()

    # Assert
    assert len(mock_task_run.called_instances) == 3
    called_task_ids = [instance.key for instance in mock_task_run.called_instances]
    assert set(called_task_ids) == set(original_task_keys[:3])


@pytest.mark.asyncio
async def test_retry_removes_correct_tasks_from_tasks_left_to_run_idempotent(
    publish_state, swarm_signature, original_tasks, mock_task_run
):
    # Arrange
    batch_tasks = [
        await swarm_signature.add_task(original_task)
        for original_task in original_tasks
    ]
    task_keys = [task.key for task in batch_tasks]
    await swarm_signature.tasks_left_to_run.aextend(task_keys)

    await publish_state.task_ids.aextend(task_keys[:3])

    # Act
    await swarm_signature.fill_running_tasks()

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_signature.key)
    assert reloaded_swarm.tasks_left_to_run == task_keys[3:]


@pytest.mark.asyncio
async def test_two_consecutive_calls_ignore_second_call__no_concurrency_resource_left(
    swarm_signature, original_tasks, mock_task_run
):
    # Arrange
    batch_tasks = [
        await swarm_signature.add_task(original_task)
        for original_task in original_tasks
    ]
    task_keys = [task.key for task in batch_tasks]
    await swarm_signature.tasks_left_to_run.aextend(task_keys)

    # Act
    result1 = await swarm_signature.fill_running_tasks()
    result2 = await swarm_signature.fill_running_tasks()

    # Assert
    assert len(result1) == 3
    assert len(result2) == 0
    assert len(mock_task_run.called_instances) == 3

    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_signature.key)
    assert reloaded_swarm.tasks_left_to_run == swarm_signature.tasks[-2:]
    relaoded_pbulish_state = await PublishState.aget(
        swarm_signature.publishing_state_id
    )
    assert relaoded_pbulish_state.task_ids == []


@pytest.mark.asyncio
async def test_concurrent_calls_single_execution_idempotent(
    publish_state, swarm_signature, original_tasks
):
    # Arrange
    batch_tasks = [
        await swarm_signature.add_task(original_task)
        for original_task in original_tasks
    ]
    task_keys = [task.key for task in batch_tasks]
    await swarm_signature.tasks_left_to_run.aextend(task_keys)

    called_instances = []
    call_lock = asyncio.Lock()

    async def track_calls(self, *args, **kwargs):
        async with call_lock:
            called_instances.append(self)
        return None

    # Act
    with patch.object(TaskSignature, "aio_run_no_wait", new=track_calls):
        results = await asyncio.gather(
            swarm_signature.fill_running_tasks(),
            swarm_signature.fill_running_tasks(),
            swarm_signature.fill_running_tasks(),
        )

    # Assert
    total_tasks_started = sum([len(res) for res in results])
    assert total_tasks_started == 5

    called_task_ids = [instance.key for instance in called_instances]
    assert len(called_task_ids) == len(set(called_task_ids))

    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_signature.key)
    assert reloaded_swarm.tasks_left_to_run == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["total_tasks", "prepopulated_count", "max_concurrency", "expected_remaining"],
    [
        [5, 3, 5, 2],
        [3, 3, 5, 0],
        [10, 5, 10, 5],
        [5, 0, 3, 2],
    ],
)
async def test_various_batch_sizes_idempotent(
    total_tasks,
    prepopulated_count,
    max_concurrency,
    expected_remaining,
    publish_state,
    mock_task_run,
):
    # Arrange
    original_tasks = [
        TaskSignature(task_name=f"original_task_{i}", model_validators=ContextMessage)
        for i in range(total_tasks)
    ]
    await rapyer.ainsert(*original_tasks)
    swarm_signature = SwarmTaskSignature(
        task_name="test_swarm",
        model_validators=ContextMessage,
        current_running_tasks=0,
        config=SwarmConfig(max_concurrency=max_concurrency),
        publishing_state_id=publish_state.key,
    )
    await rapyer.ainsert(swarm_signature)
    batch_tasks = [
        await swarm_signature.add_task(original_task)
        for original_task in original_tasks
    ]
    task_keys = [task.key for task in batch_tasks]
    await swarm_signature.tasks_left_to_run.aextend(task_keys)

    if prepopulated_count > 0:
        await publish_state.task_ids.aextend(task_keys[:prepopulated_count])

    # Act
    await swarm_signature.fill_running_tasks()

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_signature.key)
    assert len(reloaded_swarm.tasks_left_to_run) == expected_remaining

    reloaded_publish_state = await PublishState.aget(publish_state.key)
    assert list(reloaded_publish_state.task_ids) == []


@pytest.mark.asyncio
async def test_retry_after_partial_aio_run_failure_publishes_same_tasks_idempotent(
    publish_state, swarm_signature, original_tasks, failing_mock_task_run
):
    # Arrange
    batch_tasks = [
        await swarm_signature.add_task(original_task)
        for original_task in original_tasks
    ]
    task_keys = [task.key for task in batch_tasks]
    original_task_keys = [task.original_task_id for task in batch_tasks]
    batch_to_original = {task.key: task.original_task_id for task in batch_tasks}
    await swarm_signature.tasks_left_to_run.aextend(task_keys)
    publish_state_key = swarm_signature.publishing_state_id

    failing_mock_task_run.fail_on_call = 3

    # Act
    with pytest.raises(RuntimeError):
        await swarm_signature.fill_running_tasks()

    reloaded_publish_state = await PublishState.aget(publish_state_key)
    first_run_batch_task_ids = list(reloaded_publish_state.task_ids)
    first_run_original_task_ids = [
        batch_to_original[k] for k in first_run_batch_task_ids
    ]

    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_signature.key)
    assert len(first_run_batch_task_ids) == 3
    assert reloaded_swarm.tasks_left_to_run == task_keys

    failing_mock_task_run.reset_failure()
    await swarm_signature.fill_running_tasks()

    # Assert
    all_called_keys = [
        instance.key for instance in failing_mock_task_run.called_instances
    ]
    unique_task_keys = set(all_called_keys)
    assert len(unique_task_keys) == 3
    assert unique_task_keys == set(first_run_original_task_ids)

    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_signature.key)
    assert len(reloaded_swarm.tasks_left_to_run) == 2

    reloaded_publish_state = await PublishState.aget(publish_state_key)
    assert list(reloaded_publish_state.task_ids) == []
