import asyncio

import pytest
from hatchet_sdk.runnables.types import EmptyModel

import mageflow
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus
from mageflow.swarm.consts import (
    SWARM_TASK_ID_PARAM_NAME,
    SWARM_ITEM_TASK_ID_PARAM_NAME,
)
from mageflow.swarm.model import SwarmTaskSignature, SwarmConfig
from mageflow.swarm.workflows import swarm_item_failed
from tests.integration.hatchet.models import ContextMessage
from tests.unit.swarm.conftest import create_mock_context_with_metadata


@pytest.mark.asyncio
async def test_swarm_item_failed_sanity_continue_after_failure(mock_fill_running_tasks):
    # Arrange
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1, stop_after_n_failures=2),
    )

    original_tasks = [
        await mageflow.sign(f"test_task_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]
    batch_tasks = [await swarm_task.add_task(task) for task in original_tasks]

    async with swarm_task.apipeline():
        swarm_task.current_running_tasks = 1
        swarm_task.tasks.extend([t.key for t in batch_tasks])
    await swarm_task.tasks_left_to_run.aextend([batch_tasks[1].key, batch_tasks[2].key])

    item_task = await mageflow.sign("item_task", model_validators=ContextMessage)

    ctx = create_mock_context_with_metadata(
        task_id=item_task.key,
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_tasks[0].key,
    )
    msg = EmptyModel()

    # Act
    await swarm_item_failed(msg, ctx)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_task.key)

    assert batch_tasks[0].key in reloaded_swarm.failed_tasks
    assert len(reloaded_swarm.failed_tasks) == 1

    assert reloaded_swarm.task_status.status != SignatureStatus.CANCELED

    mock_fill_running_tasks.assert_called_once()


@pytest.mark.asyncio
async def test_swarm_item_failed_sanity_stop_after_threshold(
    mock_activate_error,
    mock_swarm_remove,
    mock_fill_running_tasks,
):
    # Arrange
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1, stop_after_n_failures=2),
    )

    original_tasks = [
        await mageflow.sign(f"test_task_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]
    batch_tasks = [await swarm_task.add_task(task) for task in original_tasks]

    async with swarm_task.apipeline():
        swarm_task.current_running_tasks = 1
        swarm_task.tasks.extend([t.key for t in batch_tasks])
    await swarm_task.failed_tasks.aappend(batch_tasks[0].key)

    item_task = await mageflow.sign("item_task", model_validators=ContextMessage)

    ctx = create_mock_context_with_metadata(
        task_id=item_task.key,
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_tasks[1].key,
    )
    msg = EmptyModel()

    # Act
    await swarm_item_failed(msg, ctx)

    # Assert
    mock_fill_running_tasks.assert_called_once()


@pytest.mark.asyncio
async def test_swarm_item_failed_stop_after_n_failures_none_edge_case(
    mock_activate_error,
    mock_fill_running_tasks_zero,
):
    # Arrange
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1, stop_after_n_failures=None),
    )

    original_tasks = [
        await mageflow.sign(f"test_task_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]
    batch_tasks = [await swarm_task.add_task(task) for task in original_tasks]

    async with swarm_task.apipeline():
        swarm_task.current_running_tasks = 1
        swarm_task.tasks.extend([t.key for t in batch_tasks])
    await swarm_task.failed_tasks.aextend([batch_tasks[0].key, batch_tasks[1].key])

    item_task = await mageflow.sign("item_task", model_validators=ContextMessage)

    ctx = create_mock_context_with_metadata(
        task_id=item_task.key,
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_tasks[2].key,
    )
    msg = EmptyModel()

    # Act
    await swarm_item_failed(msg, ctx)

    # Assert
    mock_activate_error.assert_not_awaited()

    mock_fill_running_tasks_zero.assert_called_once()

    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_task.key)
    assert reloaded_swarm.task_status.status != SignatureStatus.CANCELED


@pytest.mark.asyncio
async def test_swarm_item_failed_below_threshold_edge_case(
    mock_activate_error,
    mock_fill_running_tasks_zero,
):
    # Arrange
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1, stop_after_n_failures=3),
    )

    original_task = await mageflow.sign("test_task", model_validators=ContextMessage)
    batch_task = await swarm_task.add_task(original_task)

    async with swarm_task.apipeline():
        swarm_task.current_running_tasks = 1

    item_task = await mageflow.sign("item_task", model_validators=ContextMessage)

    ctx = create_mock_context_with_metadata(
        task_id=item_task.key, swarm_task_id=swarm_task.key, swarm_item_id=batch_task.key
    )
    msg = EmptyModel()

    # Act
    await swarm_item_failed(msg, ctx)

    # Assert
    mock_activate_error.assert_not_awaited()
    mock_fill_running_tasks_zero.assert_called_once()


@pytest.mark.asyncio
async def test_swarm_item_failed_missing_task_key_edge_case(mock_context):
    # Arrange
    ctx = mock_context
    ctx.additional_metadata = {
        "task_data": {
            SWARM_TASK_ID_PARAM_NAME: "some_swarm",
            SWARM_ITEM_TASK_ID_PARAM_NAME: "some_item",
        }
    }
    msg = EmptyModel()

    # Act & Assert
    with pytest.raises(KeyError):
        await swarm_item_failed(msg, ctx)


@pytest.mark.asyncio
async def test_swarm_item_failed_concurrent_failures_edge_case():
    # Arrange
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=3, stop_after_n_failures=5),
    )

    original_tasks = [
        await mageflow.sign(f"test_task_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]
    batch_tasks = [await swarm_task.add_task(task) for task in original_tasks]

    item_tasks = [
        await mageflow.sign(f"item_task_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]

    async with swarm_task.apipeline():
        swarm_task.current_running_tasks = 3
        swarm_task.tasks.extend([t.key for t in batch_tasks])

    contexts = [
        create_mock_context_with_metadata(
            task_id=item_tasks[i].key,
            swarm_task_id=swarm_task.key,
            swarm_item_id=batch_tasks[i].key,
        )
        for i in range(3)
    ]

    msgs = [EmptyModel() for _ in range(3)]

    # Act
    await asyncio.gather(
        *[swarm_item_failed(msgs[i], contexts[i]) for i in range(3)],
        return_exceptions=True,
    )

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_task.key)

    assert len(reloaded_swarm.failed_tasks) == 3
    for batch_task in batch_tasks:
        assert batch_task.key in reloaded_swarm.failed_tasks

    assert reloaded_swarm.task_status.status != SignatureStatus.CANCELED
