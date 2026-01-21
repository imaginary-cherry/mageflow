import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from mageflow.invokers.hatchet import HatchetInvoker
from mageflow.signature.model import TaskSignature
from mageflow.swarm.messages import SwarmResultsMessage
from mageflow.swarm.model import SwarmTaskSignature, SwarmConfig, BatchItemTaskSignature
from mageflow.swarm.workflows import swarm_item_done
from tests.integration.hatchet.models import ContextMessage


@pytest.mark.asyncio
async def test_two_consecutive_calls_same_item_no_duplicate_idempotent(
    create_mock_context_with_metadata, mock_fill_running_tasks, publish_state
):
    # Arrange
    swarm_task = SwarmTaskSignature(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1),
        current_running_tasks=1,
        publishing_state_id=publish_state.key,
    )
    await swarm_task.asave()

    batch_task = BatchItemTaskSignature(
        task_name="test_task",
        model_validators=ContextMessage,
        swarm_id=swarm_task.key,
        original_task_id="original_task",
    )
    await batch_task.asave()
    await swarm_task.tasks.aappend(batch_task.key)

    item_task = TaskSignature(task_name="item_task", model_validators=ContextMessage)
    await item_task.asave()

    ctx = create_mock_context_with_metadata(
        task_id=item_task.key,
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_task.key,
    )
    result = 42
    msg = SwarmResultsMessage(
        results=result,
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_task.key,
    )

    # Act
    await swarm_item_done(msg, ctx)
    await swarm_item_done(msg, ctx)

    # Assert
    finished_tasks = await swarm_task.finished_tasks.aload()
    assert batch_task.key in finished_tasks
    assert len(finished_tasks) == 1
    assert len(set(finished_tasks)) == len(finished_tasks)

    tasks_results = await swarm_task.tasks_results.aload()
    assert len(tasks_results) == 1

    running_tasks = await swarm_task.current_running_tasks.aload()
    assert running_tasks == 0


@pytest.mark.asyncio
async def test_retry_with_prepopulated_done_state_skips_update_idempotent(
    create_mock_context_with_metadata, mock_fill_running_tasks, publish_state
):
    # Arrange
    result = 42

    swarm_task = SwarmTaskSignature(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1),
        current_running_tasks=1,
        publishing_state_id=publish_state.key,
    )
    await swarm_task.asave()

    batch_task = BatchItemTaskSignature(
        task_name="test_task",
        model_validators=ContextMessage,
        swarm_id=swarm_task.key,
        original_task_id="original_task",
    )
    await batch_task.asave()

    item_task = TaskSignature(task_name="item_task", model_validators=ContextMessage)
    await item_task.asave()

    ctx = create_mock_context_with_metadata(
        task_id=item_task.key,
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_task.key,
    )
    msg = SwarmResultsMessage(
        results=result,
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_task.key,
    )

    # Act
    with patch.object(HatchetInvoker, "wait_task", side_effect=Exception):
        with pytest.raises(Exception):
            await swarm_item_done(msg, ctx)
    await swarm_item_done(msg, ctx)

    # Assert
    finished_tasks = await swarm_task.finished_tasks.aload()
    assert batch_task.key in finished_tasks
    assert len(finished_tasks) == 1
    assert len(set(finished_tasks)) == len(finished_tasks)

    tasks_results = await swarm_task.tasks_results.aload()
    assert len(tasks_results) == 1

    running_tasks = await swarm_task.current_running_tasks.aload()
    assert running_tasks == 0

    mock_fill_running_tasks.assert_called_once()


@pytest.mark.asyncio
async def test_crash_before_pipeline_retry_executes_normally_idempotent(
    create_mock_context_with_metadata, mock_fill_running_tasks, publish_state
):
    # Arrange
    swarm_task = SwarmTaskSignature(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1),
        current_running_tasks=1,
        publishing_state_id=publish_state.key,
    )
    await swarm_task.asave()

    batch_task = BatchItemTaskSignature(
        task_name="test_task",
        model_validators=ContextMessage,
        swarm_id=swarm_task.key,
        original_task_id="original_task",
    )
    await batch_task.asave()
    await swarm_task.tasks.aappend(batch_task.key)

    item_task = TaskSignature(task_name="item_task", model_validators=ContextMessage)
    await item_task.asave()

    ctx = create_mock_context_with_metadata(
        task_id=item_task.key,
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_task.key,
    )
    msg = SwarmResultsMessage(
        results=42,
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_task.key,
    )

    call_count = 0
    original_get_safe = SwarmTaskSignature.get_safe

    async def get_safe_crash_first(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Simulated crash before pipeline")
        return await original_get_safe(*args, **kwargs)

    # Act - First call crashes before pipeline
    with patch.object(SwarmTaskSignature, "get_safe", side_effect=get_safe_crash_first):
        with pytest.raises(RuntimeError, match="Simulated crash before pipeline"):
            await swarm_item_done(msg, ctx)

    # Verify no state change - crashed before pipeline
    finished_tasks = await swarm_task.finished_tasks.aload()
    assert len(finished_tasks) == 0

    running_tasks = await swarm_task.current_running_tasks.aload()
    assert running_tasks == 1

    # Act - Retry should succeed
    await swarm_item_done(msg, ctx)

    # Assert idempotency
    finished_tasks = await swarm_task.finished_tasks.aload()
    assert batch_task.key in finished_tasks
    assert len(finished_tasks) == 1
    assert len(set(finished_tasks)) == len(finished_tasks)

    running_tasks = await swarm_task.current_running_tasks.aload()
    assert running_tasks == 0


@pytest.mark.asyncio
async def test_retry_after_wait_task_failure_no_duplicate_idempotent(
    create_mock_context_with_metadata, publish_state
):
    # Arrange
    swarm_task = SwarmTaskSignature(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1),
        current_running_tasks=1,
        publishing_state_id=publish_state.key,
    )
    await swarm_task.asave()

    batch_task = BatchItemTaskSignature(
        task_name="test_task",
        model_validators=ContextMessage,
        swarm_id=swarm_task.key,
        original_task_id="original_task",
    )
    await batch_task.asave()
    await swarm_task.tasks.aappend(batch_task.key)

    item_task = TaskSignature(task_name="item_task", model_validators=ContextMessage)
    await item_task.asave()

    ctx = create_mock_context_with_metadata(
        task_id=item_task.key,
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_task.key,
    )
    msg = SwarmResultsMessage(
        results=42,
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_task.key,
    )

    # Act
    with patch.object(HatchetInvoker, "wait_task", RuntimeError):
        with pytest.raises(RuntimeError, match="Simulated wait_task failure"):
            await swarm_item_done(msg, ctx)

        await swarm_item_done(msg, ctx)

    # Assert
    finished_tasks = await swarm_task.finished_tasks.aload()
    assert batch_task.key in finished_tasks
    assert len(finished_tasks) == 1
    assert len(set(finished_tasks)) == len(finished_tasks)

    tasks_results = await swarm_task.tasks_results.aload()
    assert len(tasks_results) == 1

    running_tasks = await swarm_task.current_running_tasks.aload()
    assert running_tasks == 0
