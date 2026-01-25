from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from pytest import FixtureRequest

import mageflow
from mageflow.signature.model import TaskSignature
from mageflow.swarm.model import BatchItemTaskSignature, SwarmConfig, SwarmTaskSignature
from tests.integration.hatchet.models import ContextMessage


@dataclass
class SwarmWithCapacityData:
    swarm: SwarmTaskSignature
    swarm_kwargs: dict


@pytest_asyncio.fixture
async def test_message() -> ContextMessage:
    return ContextMessage(base_data={"msg_param": "msg_value"})


@pytest_asyncio.fixture
async def swarm_with_capacity(request: FixtureRequest) -> SwarmWithCapacityData:
    max_concurrency, current_running = request.param
    swarm_kwargs = {"swarm_param": "swarm_value"}
    swarm = await mageflow.swarm(
        task_name="test_swarm",
        kwargs=swarm_kwargs,
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=max_concurrency),
    )
    async with swarm.alock() as locked_swarm:
        await locked_swarm.aupdate(current_running_tasks=current_running)
    return SwarmWithCapacityData(swarm=swarm, swarm_kwargs=swarm_kwargs)


async def create_batch_item_with_task(
    swarm: SwarmTaskSignature,
) -> tuple[BatchItemTaskSignature, TaskSignature, dict]:
    task_kwargs = {"task_param": "task_value"}
    original_task = await mageflow.sign(
        "test_task",
        model_validators=ContextMessage,
        **task_kwargs,
    )
    batch_item = await swarm.add_task(original_task)
    return batch_item, original_task, task_kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "swarm_with_capacity",
    [
        [5, 5],  # Full
        [1, 1],  # Full
    ],
    indirect=True,
)
async def test_batch_item_aio_run_no_wait_no_capacity_sanity(
    swarm_with_capacity: SwarmWithCapacityData,
    mock_workflow_run: list,
    test_message: ContextMessage,
):
    # Arrange
    batch_item, original_task, task_kwargs = await create_batch_item_with_task(
        swarm_with_capacity.swarm
    )

    # Act
    await batch_item.aio_run_no_wait(test_message)

    # Assert
    reloaded_original_task = await TaskSignature.get_safe(original_task.key)
    assert len(mock_workflow_run) == 0
    message_data = test_message.model_dump(mode="json")
    expected_kwargs = {
        **task_kwargs,
        **batch_item.kwargs,
        **swarm_with_capacity.swarm_kwargs,
        **message_data,
    }
    assert reloaded_original_task.kwargs == expected_kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "swarm_with_capacity",
    [
        [5, 4],  # Has space
        [1, 0],  # Has space
    ],
    indirect=True,
)
async def test_batch_item_aio_run_no_wait_has_capacity_sanity(
    swarm_with_capacity: SwarmWithCapacityData,
    mock_fill_running_tasks: AsyncMock,
    test_message: ContextMessage,
):
    # Arrange
    batch_item, original_task, task_kwargs = await create_batch_item_with_task(
        swarm_with_capacity.swarm
    )

    # Act
    await batch_item.aio_run_no_wait(test_message)

    # Assert
    reloaded_original_task = await TaskSignature.get_safe(original_task.key)
    mock_fill_running_tasks.assert_awaited_once_with(max_tasks=1)
    expected_kwargs = {
        **task_kwargs,
        **batch_item.kwargs,
        **swarm_with_capacity.swarm_kwargs,
        **test_message.model_dump(mode="json"),
    }
    assert reloaded_original_task.kwargs == expected_kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize("swarm_with_capacity", [[1, 1]], indirect=True)
async def test_batch_item_no_capacity_includes_message_kwargs_sanity(
    swarm_with_capacity: SwarmWithCapacityData,
    mock_workflow_run: list,
    test_message: ContextMessage,
):
    # Arrange
    batch_item, original_task, task_kwargs = await create_batch_item_with_task(
        swarm_with_capacity.swarm
    )
    message_with_data = ContextMessage(
        base_data={"special_msg_key": "special_msg_value"}
    )

    # Act
    await batch_item.aio_run_no_wait(message_with_data)

    # Assert
    reloaded_original_task = await TaskSignature.get_safe(original_task.key)
    message_data = message_with_data.model_dump(mode="json")
    expected_kwargs = {
        **task_kwargs,
        **batch_item.kwargs,
        **swarm_with_capacity.swarm_kwargs,
        **message_data,
    }
    assert reloaded_original_task.kwargs == expected_kwargs
    assert len(mock_workflow_run) == 0
