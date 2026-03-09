import asyncio
from logging import Logger
from unittest.mock import MagicMock

import pytest
from rapyer.errors import KeyNotFound
from thirdmagic.signature.status import SignatureStatus
from thirdmagic.swarm.model import SwarmConfig, SwarmTaskSignature

import mageflow
from mageflow.swarm.messages import SwarmErrorMessage
from mageflow.swarm.workflows import swarm_item_failed
from tests.integration.hatchet.models import ContextMessage
from tests.unit.workflows.conftest import create_swarm_item_test_setup


@pytest.mark.asyncio
async def test_swarm_item_failed_sanity_continue_after_failure(
    mock_adapter, mock_logger
):
    # Arrange
    setup = await create_swarm_item_test_setup(
        tasks_left_indices=[1, 2], logger=mock_logger
    )
    msg = SwarmErrorMessage(
        swarm_task_id=setup.swarm_task.key,
        swarm_item_id=setup.tasks[0].key,
        error="test error",
    )

    # Act
    await swarm_item_failed(
        msg.swarm_task_id, msg.swarm_item_id, msg.error, setup.logger
    )

    # Assert
    reloaded_swarm = await SwarmTaskSignature.aget(setup.swarm_task.key)

    assert setup.tasks[0].key in reloaded_swarm.failed_tasks
    assert len(reloaded_swarm.failed_tasks) == 1

    assert reloaded_swarm.task_status.status != SignatureStatus.CANCELED

    mock_adapter.afill_swarm.assert_awaited_once()


@pytest.mark.asyncio
async def test_swarm_item_failed_sanity_stop_after_threshold(
    mock_activate_error,
    mock_swarm_remove,
    mock_adapter,
    mock_logger,
):
    # Arrange
    setup = await create_swarm_item_test_setup(failed_indices=[0], logger=mock_logger)
    msg = SwarmErrorMessage(
        swarm_task_id=setup.swarm_task.key,
        swarm_item_id=setup.tasks[1].key,
        error="test error",
    )

    # Act
    await swarm_item_failed(
        msg.swarm_task_id, msg.swarm_item_id, msg.error, setup.logger
    )

    # Assert
    mock_adapter.afill_swarm.assert_awaited_once()


@pytest.mark.asyncio
async def test_swarm_item_failed_stop_after_n_failures_none_edge_case(
    mock_activate_error,
    mock_adapter,
    mock_logger,
):
    # Arrange
    setup = await create_swarm_item_test_setup(
        stop_after_n_failures=None, failed_indices=[0, 1], logger=mock_logger
    )
    msg = SwarmErrorMessage(
        swarm_task_id=setup.swarm_task.key,
        swarm_item_id=setup.tasks[2].key,
        error="test error",
    )

    # Act
    await swarm_item_failed(
        msg.swarm_task_id, msg.swarm_item_id, msg.error, setup.logger
    )

    # Assert
    mock_activate_error.assert_not_awaited()

    mock_adapter.afill_swarm.assert_awaited_once()

    reloaded_swarm = await SwarmTaskSignature.aget(setup.swarm_task.key)
    assert reloaded_swarm.task_status.status != SignatureStatus.CANCELED


@pytest.mark.asyncio
async def test_swarm_item_failed_below_threshold_edge_case(
    mock_activate_error,
    mock_adapter,
    mock_logger,
):
    # Arrange
    swarm_task = await mageflow.aswarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1, stop_after_n_failures=3),
    )

    original_task = await mageflow.asign("test_task", model_validators=ContextMessage)
    task = await swarm_task.add_task(original_task)

    async with swarm_task.apipeline():
        swarm_task.current_running_tasks = 1

    msg = SwarmErrorMessage(
        swarm_task_id=swarm_task.key, swarm_item_id=task.key, error="test error"
    )

    # Act
    await swarm_item_failed(
        msg.swarm_task_id, msg.swarm_item_id, msg.error, mock_logger
    )

    # Assert
    mock_activate_error.assert_not_awaited()
    mock_adapter.afill_swarm.assert_awaited_once()


@pytest.mark.asyncio
async def test_swarm_item_failed_missing_task_key_edge_case():
    # Arrange
    logger = MagicMock(spec=Logger)
    msg = SwarmErrorMessage(
        swarm_task_id="some_swarm", swarm_item_id="some_item", error="test error"
    )

    # Act & Assert
    with pytest.raises(KeyNotFound):
        await swarm_item_failed(msg.swarm_task_id, msg.swarm_item_id, msg.error, logger)


@pytest.mark.asyncio
async def test_swarm_item_failed_concurrent_failures_edge_case():
    # Arrange
    logger = MagicMock(spec=Logger)
    swarm_task = await mageflow.aswarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=3, stop_after_n_failures=5),
    )

    original_tasks = [
        await mageflow.asign(f"test_task_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]
    tasks = [await swarm_task.add_task(task) for task in original_tasks]

    async with swarm_task.apipeline():
        swarm_task.current_running_tasks = 3

    msgs = [
        SwarmErrorMessage(
            swarm_task_id=swarm_task.key,
            swarm_item_id=tasks[i].key,
            error="test error",
        )
        for i in range(3)
    ]

    # Act
    await asyncio.gather(
        *[
            swarm_item_failed(m.swarm_task_id, m.swarm_item_id, m.error, logger)
            for m in msgs
        ],
        return_exceptions=True,
    )

    # Assert
    reloaded_swarm = await SwarmTaskSignature.aget(swarm_task.key)

    assert len(reloaded_swarm.failed_tasks) == 3
    for task in tasks:
        assert task.key in reloaded_swarm.failed_tasks

    assert reloaded_swarm.task_status.status != SignatureStatus.CANCELED
