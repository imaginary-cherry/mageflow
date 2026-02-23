from logging import Logger
from unittest.mock import MagicMock

import pytest
from thirdmagic.swarm.model import SwarmTaskSignature

import mageflow
from mageflow.swarm.messages import SwarmResultsMessage
from mageflow.swarm.workflows import swarm_item_done
from tests.integration.hatchet.models import ContextMessage
from tests.unit.workflows.conftest import create_swarm_item_test_setup


@pytest.mark.asyncio
async def test_swarm_item_done_sanity_basic_flow(mock_adapter, mock_logger):
    # Arrange
    setup = await create_swarm_item_test_setup(
        num_tasks=3,
        max_concurrency=1,
        stop_after_n_failures=None,
        tasks_left_indices=[1, 2],
        logger=mock_logger,
    )
    msg = SwarmResultsMessage(
        mageflow_results={"status": "success", "value": 42},
        swarm_task_id=setup.swarm_task.key,
        swarm_item_id=setup.tasks[0].key,
    )

    # Act
    await swarm_item_done(msg.swarm_task_id, msg.swarm_item_id, msg.mageflow_results, setup.logger)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.aget(setup.swarm_task.key)

    assert setup.tasks[0].key in reloaded_swarm.finished_tasks
    assert len(reloaded_swarm.finished_tasks) == 1

    assert len(reloaded_swarm.tasks_results) == 1
    assert reloaded_swarm.tasks_results[0] == msg.mageflow_results

    mock_adapter.afill_swarm.assert_awaited_once()


@pytest.mark.asyncio
async def test_swarm_item_done_sanity_last_item_completes(mock_adapter, mock_logger):
    # Arrange
    setup = await create_swarm_item_test_setup(
        num_tasks=2,
        max_concurrency=2,
        stop_after_n_failures=None,
        finished_indices=[0],
        logger=mock_logger,
    )
    await setup.swarm_task.aupdate(is_swarm_closed=True)

    msg = SwarmResultsMessage(
        mageflow_results={"status": "complete"},
        swarm_task_id=setup.swarm_task.key,
        swarm_item_id=setup.tasks[1].key,
    )

    # Act
    await swarm_item_done(msg.swarm_task_id, msg.swarm_item_id, msg.mageflow_results, setup.logger)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.aget(setup.swarm_task.key)
    assert setup.tasks[1].key in reloaded_swarm.finished_tasks
    assert len(reloaded_swarm.finished_tasks) == 2
    mock_adapter.afill_swarm.assert_awaited_once()


@pytest.mark.asyncio
async def test_swarm_item_done_nonexistent_swarm_edge_case():
    # Arrange
    logger = MagicMock(spec=Logger)
    msg = SwarmResultsMessage(
        mageflow_results={},
        swarm_task_id="nonexistent_swarm",
        swarm_item_id="nonexistent_item",
    )

    # Act & Assert
    with pytest.raises(Exception):
        await swarm_item_done(msg.swarm_task_id, msg.swarm_item_id, msg.mageflow_results, logger)


@pytest.mark.asyncio
async def test_swarm_item_done_swarm_not_found_edge_case():
    # Arrange
    logger = MagicMock(spec=Logger)
    msg = SwarmResultsMessage(
        mageflow_results={},
        swarm_task_id="nonexistent_swarm",
        swarm_item_id="some_item",
    )

    # Act & Assert
    with pytest.raises(Exception):
        await swarm_item_done(msg.swarm_task_id, msg.swarm_item_id, msg.mageflow_results, logger)


@pytest.mark.asyncio
async def test_swarm_item_done_exception_during_handle_finish_edge_case(
    mock_adapter, mock_logger,
):
    # Arrange
    mock_adapter.afill_swarm.side_effect = RuntimeError("Finish tasks error")

    swarm_task = await mageflow.aswarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
    )
    async with swarm_task.apipeline():
        swarm_task.current_running_tasks = 1

    original_task = await mageflow.asign(
        "original_task", model_validators=ContextMessage
    )
    task = await swarm_task.add_task(original_task)

    msg = SwarmResultsMessage(
        mageflow_results={},
        swarm_task_id=swarm_task.key,
        swarm_item_id=task.key,
    )

    # Act & Assert
    with pytest.raises(RuntimeError, match="Finish tasks error"):
        await swarm_item_done(msg.swarm_task_id, msg.swarm_item_id, msg.mageflow_results, mock_logger)

    mock_adapter.afill_swarm.assert_awaited_once()
