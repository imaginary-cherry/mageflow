import asyncio

import pytest
from rapyer.errors import KeyNotFound

import mageflow
from thirdmagic.signature.status import SignatureStatus
from mageflow.swarm.messages import SwarmErrorMessage
from thirdmagic.swarm.model import SwarmTaskSignature, SwarmConfig
from mageflow.swarm.workflows import swarm_item_failed
from tests.integration.hatchet.models import ContextMessage
from tests.unit.conftest import create_mock_context_with_metadata
from tests.unit.workflows.conftest import create_swarm_item_test_setup


@pytest.mark.asyncio
async def test_swarm_item_failed_sanity_continue_after_failure(mock_invoker_wait_task):
    # Arrange
    setup = await create_swarm_item_test_setup(
        num_tasks=3,
        stop_after_n_failures=2,
        tasks_left_indices=[1, 2],
    )
    msg = SwarmErrorMessage(
        swarm_task_id=setup.swarm_task.key, swarm_item_id=setup.tasks[0].key
    )

    # Act
    await swarm_item_failed(msg, setup.ctx)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(setup.swarm_task.key)

    assert setup.tasks[0].key in reloaded_swarm.failed_tasks
    assert len(reloaded_swarm.failed_tasks) == 1

    assert reloaded_swarm.task_status.status != SignatureStatus.CANCELED

    mock_invoker_wait_task.assert_called_once()


@pytest.mark.asyncio
async def test_swarm_item_failed_sanity_stop_after_threshold(
    mock_activate_error,
    mock_swarm_remove,
    mock_invoker_wait_task,
):
    # Arrange
    setup = await create_swarm_item_test_setup(
        num_tasks=3,
        stop_after_n_failures=2,
        failed_indices=[0],
    )
    msg = SwarmErrorMessage(
        swarm_task_id=setup.swarm_task.key, swarm_item_id=setup.tasks[1].key
    )
    # Act
    await swarm_item_failed(msg, setup.ctx)

    # Assert
    mock_invoker_wait_task.assert_called_once()


@pytest.mark.asyncio
async def test_swarm_item_failed_stop_after_n_failures_none_edge_case(
    mock_activate_error,
    mock_invoker_wait_task,
):
    # Arrange
    setup = await create_swarm_item_test_setup(
        num_tasks=3,
        stop_after_n_failures=None,
        failed_indices=[0, 1],
    )
    msg = SwarmErrorMessage(
        swarm_task_id=setup.swarm_task.key, swarm_item_id=setup.tasks[2].key
    )

    # Act
    await swarm_item_failed(msg, setup.ctx)

    # Assert
    mock_activate_error.assert_not_awaited()

    mock_invoker_wait_task.assert_called_once()

    reloaded_swarm = await SwarmTaskSignature.get_safe(setup.swarm_task.key)
    assert reloaded_swarm.task_status.status != SignatureStatus.CANCELED


@pytest.mark.asyncio
async def test_swarm_item_failed_below_threshold_edge_case(
    mock_activate_error,
    mock_invoker_wait_task,
):
    # Arrange
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1, stop_after_n_failures=3),
    )

    original_task = await mageflow.sign("test_task", model_validators=ContextMessage)
    task = await swarm_task.add_task(original_task)

    async with swarm_task.apipeline():
        swarm_task.current_running_tasks = 1

    item_task = await mageflow.sign("item_task", model_validators=ContextMessage)

    ctx = create_mock_context_with_metadata(task_id=item_task.key)
    msg = SwarmErrorMessage(swarm_task_id=swarm_task.key, swarm_item_id=task.key)

    # Act
    await swarm_item_failed(msg, ctx)

    # Assert
    mock_activate_error.assert_not_awaited()
    mock_invoker_wait_task.assert_called_once()


@pytest.mark.asyncio
async def test_swarm_item_failed_missing_task_key_edge_case(mock_context):
    # Arrange
    ctx = mock_context
    msg = SwarmErrorMessage(swarm_task_id="some_swarm", swarm_item_id="some_item")

    # Act & Assert
    with pytest.raises(KeyNotFound):
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
    tasks = [await swarm_task.add_task(task) for task in original_tasks]

    item_tasks = [
        await mageflow.sign(f"item_task_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]

    async with swarm_task.apipeline():
        swarm_task.current_running_tasks = 3

    contexts = [
        create_mock_context_with_metadata(task_id=item_tasks[i].key) for i in range(3)
    ]

    msgs = [
        SwarmErrorMessage(
            swarm_task_id=swarm_task.key,
            swarm_item_id=tasks[i].key,
        )
        for i in range(3)
    ]

    # Act
    await asyncio.gather(
        *[swarm_item_failed(msgs[i], contexts[i]) for i in range(3)],
        return_exceptions=True,
    )

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm_task.key)

    assert len(reloaded_swarm.failed_tasks) == 3
    for task in tasks:
        assert task.key in reloaded_swarm.failed_tasks

    assert reloaded_swarm.task_status.status != SignatureStatus.CANCELED
