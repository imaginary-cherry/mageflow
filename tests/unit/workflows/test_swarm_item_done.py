import pytest

import mageflow
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.swarm.messages import SwarmResultsMessage
from mageflow.swarm.model import SwarmTaskSignature, SwarmConfig
from mageflow.swarm.workflows import swarm_item_done
from tests.integration.hatchet.models import ContextMessage
from tests.unit.conftest import create_mock_context_with_metadata


@pytest.mark.asyncio
async def test_swarm_item_done_sanity_basic_flow(mock_invoker_wait_task):
    # Arrange
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1),
    )

    original_tasks = [
        await mageflow.sign(f"original_task_{i}", model_validators=ContextMessage)
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
    msg = SwarmResultsMessage(
        mageflow_results={"status": "success", "value": 42},
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_tasks[0].key,
    )

    # Act
    await swarm_item_done(msg, ctx)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_task.key)

    assert batch_tasks[0].key in reloaded_swarm.finished_tasks
    assert len(reloaded_swarm.finished_tasks) == 1

    assert len(reloaded_swarm.tasks_results) == 1
    assert reloaded_swarm.tasks_results[0] == msg.mageflow_results

    mock_invoker_wait_task.assert_called_once()


@pytest.mark.asyncio
async def test_swarm_item_done_sanity_last_item_completes(mock_invoker_wait_task):
    # Arrange
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=2),
    )

    original_tasks = [
        await mageflow.sign(f"original_task_{i}", model_validators=ContextMessage)
        for i in range(2)
    ]
    batch_tasks = [await swarm_task.add_task(task) for task in original_tasks]

    async with swarm_task.apipeline():
        swarm_task.current_running_tasks = 1
        swarm_task.tasks.extend([t.key for t in batch_tasks])
    await swarm_task.finished_tasks.aappend(batch_tasks[0].key)

    async with swarm_task.alock() as locked_swarm:
        await locked_swarm.aupdate(is_swarm_closed=True)

    item_task = await mageflow.sign("item_task", model_validators=ContextMessage)

    ctx = create_mock_context_with_metadata(
        task_id=item_task.key,
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_tasks[1].key,
    )
    msg = SwarmResultsMessage(
        mageflow_results={"status": "complete"},
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_tasks[1].key,
    )

    # Act
    await swarm_item_done(msg, ctx)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_task.key)
    assert batch_tasks[1].key in reloaded_swarm.finished_tasks
    assert len(reloaded_swarm.finished_tasks) == 2
    mock_invoker_wait_task.assert_called_once()


@pytest.mark.asyncio
async def test_swarm_item_done_nonexistent_swarm_edge_case(mock_context):
    # Arrange
    ctx = mock_context
    ctx.additional_metadata = {
        "task_data": {
            TASK_ID_PARAM_NAME: "some_task",
        }
    }
    msg = SwarmResultsMessage(
        mageflow_results={},
        swarm_task_id="nonexistent_swarm",
        swarm_item_id="nonexistent_item",
    )

    # Act & Assert
    with pytest.raises(AttributeError):
        await swarm_item_done(msg, ctx)


@pytest.mark.asyncio
async def test_swarm_item_done_nonexistent_batch_task_edge_case():
    # Arrange
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
    )
    async with swarm_task.apipeline():
        swarm_task.current_running_tasks = 1

    ctx = create_mock_context_with_metadata(
        task_id="some_task",
        swarm_task_id=swarm_task.key,
    )
    msg = SwarmResultsMessage(
        mageflow_results={},
        swarm_task_id=swarm_task.key,
        swarm_item_id="nonexistent_batch_task",
    )

    # Act & Assert
    with pytest.raises(AttributeError):
        await swarm_item_done(msg, ctx)


@pytest.mark.asyncio
async def test_swarm_item_done_swarm_not_found_edge_case():
    # Arrange
    item_task = await mageflow.sign("item_task", model_validators=ContextMessage)

    ctx = create_mock_context_with_metadata(
        task_id=item_task.key,
        swarm_task_id="nonexistent_swarm",
        swarm_item_id="some_item",
    )
    msg = SwarmResultsMessage(
        mageflow_results={},
        swarm_task_id="nonexistent_swarm",
        swarm_item_id="some_item",
    )

    # Act & Assert
    with pytest.raises(Exception):
        await swarm_item_done(msg, ctx)


@pytest.mark.asyncio
async def test_swarm_item_done_exception_during_handle_finish_edge_case(
    mock_handle_finish_tasks_error,
):
    # Arrange
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
    )
    async with swarm_task.apipeline():
        swarm_task.current_running_tasks = 1

    original_task = await mageflow.sign(
        "original_task", model_validators=ContextMessage
    )
    batch_task = await swarm_task.add_task(original_task)

    item_task = await mageflow.sign("item_task", model_validators=ContextMessage)

    ctx = create_mock_context_with_metadata(
        task_id=item_task.key,
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_task.key,
    )
    msg = SwarmResultsMessage(
        mageflow_results={},
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_task.key,
    )

    # Act & Assert
    with pytest.raises(RuntimeError, match="Finish tasks error"):
        await swarm_item_done(msg, ctx)

    mock_handle_finish_tasks_error.assert_called_once()
