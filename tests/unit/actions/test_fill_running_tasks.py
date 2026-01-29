from unittest.mock import patch

import pytest

import mageflow
from mageflow.signature.model import TaskSignature
from mageflow.swarm.model import SwarmConfig
from tests.integration.hatchet.models import ContextMessage


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["num_tasks_left", "current_running", "max_concurrency", "expected_started"],
    [
        [3, 2, 5, 3],  # Can start all 3 remaining tasks (5 - 2 = 3 available slots)
        [5, 0, 3, 3],  # Can only start 3 tasks (limited by max_concurrency)
    ],
)
async def test_fill_running_tasks_sanity(
    num_tasks_left, current_running, max_concurrency, expected_started
):
    # Arrange
    # Create original task signatures using list comprehension
    original_tasks = [
        await mageflow.sign(f"original_task_{i}", model_validators=ContextMessage)
        for i in range(num_tasks_left + 2)  # Create extra tasks for the swarm
    ]

    # Create swarm with config
    swarm_signature = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=max_concurrency),
    )
    async with swarm_signature.alock() as locked_swarm:
        await locked_swarm.aupdate(current_running_tasks=current_running)

    # Add tasks to swarm to create BatchItemTaskSignatures using list comprehension
    batch_tasks = [
        await swarm_signature.add_task(original_task)
        for original_task in original_tasks
    ]

    # Populate tasks_left_to_run with batch task IDs using aextend
    tasks_to_queue = batch_tasks[:num_tasks_left]
    task_keys_to_queue = [task.key for task in tasks_to_queue]
    await swarm_signature.tasks_left_to_run.aextend(task_keys_to_queue)
    original_tasks_in_queue = [task.original_task_id for task in tasks_to_queue]

    # Act
    # Track which instances the method was called on
    called_instances = []

    async def track_calls(self, *args, **kwargs):
        called_instances.append(self)
        return None  # Return what the original method would return

    with patch.object(TaskSignature, "aio_run_no_wait", new=track_calls):
        await swarm_signature.fill_running_tasks()

    # Assert
    assert len(called_instances) == expected_started

    # Verify the instances have the correct IDs and no duplicates
    called_task_ids = [instance.key for instance in called_instances]

    # Check all IDs are from our expected tasks (tasks that were queued)
    for task_id in called_task_ids:
        assert (
            task_id in original_tasks_in_queue
        ), f"Unexpected task ID: {task_id} not in queued tasks"

    # Check for duplicates
    assert len(called_task_ids) == len(
        set(called_task_ids)
    ), f"Duplicate task IDs found: {called_task_ids}"

    # Verify we called exactly the expected number of unique tasks
    assert len(set(called_task_ids)) == expected_started
