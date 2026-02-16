from unittest.mock import call

import pytest
from hatchet_sdk.clients.admin import TriggerWorkflowOptions

import thirdmagic
from tests.unit.messages import ContextMessage
from thirdmagic.swarm.model import SwarmConfig


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ["num_tasks_left", "current_running", "max_concurrency", "expected_started"],
    [
        [3, 2, 5, 3],  # Can start all 3 remaining tasks (5 - 2 = 3 available slots)
        [5, 0, 3, 3],  # Can only start 3 tasks (limited by max_concurrency)
    ],
)
async def test_fill_running_tasks_sanity(
    mock_adapter, num_tasks_left, current_running, max_concurrency, expected_started
):
    # Arrange
    # Create original task signatures using list comprehension
    original_tasks = [
        await thirdmagic.sign(f"original_task_{i}", model_validators=ContextMessage)
        for i in range(num_tasks_left + 2)  # Create extra tasks for the swarm
    ]

    # Create swarm with config
    swarm_signature = await thirdmagic.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=max_concurrency),
        new_value=1,
    )
    async with swarm_signature.alock() as locked_swarm:
        await locked_swarm.aupdate(current_running_tasks=current_running)

    # Add tasks to swarm using list comprehension
    tasks = await swarm_signature.add_tasks(original_tasks)

    # Clear auto-populated tasks_left_to_run and re-populate with desired subset
    tasks_to_queue = tasks[:num_tasks_left]
    options = TriggerWorkflowOptions(additional_metadata={"swarm_custom": "metadata"})

    # Act
    await swarm_signature.fill_running_tasks(options=options)

    # Assert
    mock_adapter.acall_signatures.assert_awaited_once_with(
        tasks_to_queue[:expected_started],
        [None] * expected_started,
        options=options,
        new_value=1,
        set_return_field=False,
    )
