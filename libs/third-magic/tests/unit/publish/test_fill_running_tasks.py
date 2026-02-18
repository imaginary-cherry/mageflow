import pytest
from hatchet_sdk.clients.admin import TriggerWorkflowOptions

import thirdmagic
from tests.unit.messages import ContextMessage
from thirdmagic.swarm.consts import SWARM_MESSAGE_PARAM_NAME
from thirdmagic.swarm.model import SwarmConfig


@pytest.mark.asyncio
@pytest.mark.parametrize(
    [
        "num_tasks_left",
        "current_running",
        "max_concurrency",
        "expected_started",
        "set_return_field",
    ],
    [
        [
            3,
            2,
            5,
            3,
            False,
        ],  # Can start all 3 remaining tasks (5 - 2 = 3 available slots)
        [5, 0, 3, 3, False],  # Can only start 3 tasks (limited by max_concurrency)
        [5, 0, 3, 3, True],  # Can only start 3 tasks (limited by max_concurrency)
    ],
)
async def test_fill_running_tasks_sanity(
    mock_adapter,
    num_tasks_left,
    current_running,
    max_concurrency,
    expected_started,
    set_return_field,
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
        config=SwarmConfig(max_concurrency=max_concurrency),
        new_value=1,
    )
    msg = 4
    async with swarm_signature.apipeline() as locked_swarm:
        locked_swarm.config.send_swarm_message_to_return_field = set_return_field
        locked_swarm.kwargs[SWARM_MESSAGE_PARAM_NAME] = msg
        locked_swarm.current_running_tasks = current_running

    # Add tasks to swarm using list comprehension
    tasks = await swarm_signature.add_tasks(original_tasks)

    # Clear auto-populated tasks_left_to_run and re-populate with desired subset
    tasks_to_queue = tasks[:num_tasks_left]
    options = TriggerWorkflowOptions(additional_metadata={"swarm_custom": "metadata"})

    # Act
    await swarm_signature.fill_running_tasks(options=options)

    # Assert
    tasked_published = tasks_to_queue[:expected_started]
    for task in tasked_published:
        task.kwargs["new_value"] = 1

    mock_adapter.acall_signatures.assert_awaited_once_with(
        tasked_published,
        [msg] * expected_started,
        set_return_field=set_return_field,
        options=options,
    )
