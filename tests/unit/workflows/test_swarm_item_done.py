import pytest

import mageflow
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.swarm.messages import SwarmResultsMessage
from mageflow.swarm.model import SwarmTaskSignature
from mageflow.swarm.workflows import swarm_item_done
from tests.integration.hatchet.models import ContextMessage
from tests.unit.conftest import create_mock_context_with_metadata
from tests.unit.workflows.conftest import create_swarm_item_test_setup


@pytest.mark.asyncio
async def test_swarm_item_done_sanity_basic_flow(mock_invoker_wait_task):
    # Arrange
    setup = await create_swarm_item_test_setup(
        num_tasks=3,
        max_concurrency=1,
        stop_after_n_failures=None,
        tasks_left_indices=[1, 2],
    )
    msg = SwarmResultsMessage(
        mageflow_results={"status": "success", "value": 42},
        swarm_task_id=setup.swarm_task.key,
        swarm_item_id=setup.batch_tasks[0].key,
    )

    # Act
    await swarm_item_done(msg, setup.ctx)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(setup.swarm_task.key)

    assert setup.batch_tasks[0].key in reloaded_swarm.finished_tasks
    assert len(reloaded_swarm.finished_tasks) == 1

    assert len(reloaded_swarm.tasks_results) == 1
    assert reloaded_swarm.tasks_results[0] == msg.mageflow_results

    mock_invoker_wait_task.assert_called_once()


@pytest.mark.asyncio
async def test_swarm_item_done_sanity_last_item_completes(mock_invoker_wait_task):
    # Arrange
    setup = await create_swarm_item_test_setup(
        num_tasks=2,
        max_concurrency=2,
        stop_after_n_failures=None,
        finished_indices=[0],
    )
    async with setup.swarm_task.alock() as locked_swarm:
        await locked_swarm.aupdate(is_swarm_closed=True)

    msg = SwarmResultsMessage(
        mageflow_results={"status": "complete"},
        swarm_task_id=setup.swarm_task.key,
        swarm_item_id=setup.batch_tasks[1].key,
    )

    # Act
    await swarm_item_done(msg, setup.ctx)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(setup.swarm_task.key)
    assert setup.batch_tasks[1].key in reloaded_swarm.finished_tasks
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
async def test_swarm_item_done_swarm_not_found_edge_case():
    # Arrange
    item_task = await mageflow.sign("item_task", model_validators=ContextMessage)

    ctx = create_mock_context_with_metadata(task_id=item_task.key)
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

    ctx = create_mock_context_with_metadata(task_id=item_task.key)
    msg = SwarmResultsMessage(
        mageflow_results={},
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_task.key,
    )

    # Act & Assert
    with pytest.raises(RuntimeError, match="Finish tasks error"):
        await swarm_item_done(msg, ctx)

    mock_handle_finish_tasks_error.assert_called_once()
