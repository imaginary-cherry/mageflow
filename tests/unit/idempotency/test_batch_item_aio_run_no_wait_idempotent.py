import asyncio
from unittest.mock import patch, AsyncMock

import pytest

from mageflow.signature.model import TaskSignature
from mageflow.swarm.model import SwarmTaskSignature


@pytest.mark.asyncio
async def test_crash_at_get_swarm_no_state_change_retry_succeeds_idempotent(
    batch_item_run_setup, mock_task_aio_run_no_wait
):
    # Arrange
    setup = batch_item_run_setup
    initial_counter = setup.swarm_task.current_running_tasks

    # Act
    with patch.object(SwarmTaskSignature, "get_safe", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            await setup.batch_task.aio_run_no_wait(setup.msg)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(setup.swarm_task.key)
    assert reloaded_swarm.current_running_tasks == initial_counter

    # Act
    await setup.batch_task.aio_run_no_wait(setup.msg)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(setup.swarm_task.key)
    assert reloaded_swarm.current_running_tasks == initial_counter + 1
    mock_task_aio_run_no_wait.assert_called_once()


@pytest.mark.asyncio
async def test_crash_after_add_to_running_before_update_kwargs_no_double_increment_idempotent(
    batch_item_run_setup, mock_task_aio_run_no_wait
):
    # Arrange
    setup = batch_item_run_setup
    initial_counter = setup.swarm_task.current_running_tasks

    # Act
    with patch.object(
        TaskSignature, "aupdate_real_task_kwargs", side_effect=RuntimeError
    ):
        with pytest.raises(RuntimeError):
            await setup.batch_task.aio_run_no_wait(setup.msg)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(setup.swarm_task.key)
    assert reloaded_swarm.current_running_tasks == initial_counter + 1

    # Act
    await setup.batch_task.aio_run_no_wait(setup.msg)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(setup.swarm_task.key)
    assert reloaded_swarm.current_running_tasks == initial_counter + 1
    mock_task_aio_run_no_wait.assert_called_once()


@pytest.mark.asyncio
async def test_crash_after_update_kwargs_before_workflow_no_double_increment_idempotent(
    batch_item_run_setup,
):
    # Arrange
    setup = batch_item_run_setup
    initial_counter = setup.swarm_task.current_running_tasks

    mock_aio_run = AsyncMock(side_effect=[RuntimeError(), None])

    # Act
    with patch.object(TaskSignature, "aio_run_no_wait", mock_aio_run):
        with pytest.raises(RuntimeError):
            await setup.batch_task.aio_run_no_wait(setup.msg)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(setup.swarm_task.key)
    assert reloaded_swarm.current_running_tasks == initial_counter + 1

    # Act
    with patch.object(TaskSignature, "aio_run_no_wait", mock_aio_run):
        await setup.batch_task.aio_run_no_wait(setup.msg)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(setup.swarm_task.key)
    assert reloaded_swarm.current_running_tasks == initial_counter + 1
    assert mock_aio_run.call_count == 2


@pytest.mark.asyncio
async def test_crash_on_queue_path_no_duplicate_append_idempotent(
    batch_item_run_setup_at_max_concurrency,
):
    # Arrange
    setup = batch_item_run_setup_at_max_concurrency

    # Act
    with patch.object(
        TaskSignature, "aupdate_real_task_kwargs", side_effect=RuntimeError
    ):
        with pytest.raises(RuntimeError):
            await setup.batch_task.aio_run_no_wait(setup.msg)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(setup.swarm_task.key)
    assert setup.batch_task.key in reloaded_swarm.tasks_left_to_run
    queue_length_before = len(reloaded_swarm.tasks_left_to_run)

    # Act
    await setup.batch_task.aio_run_no_wait(setup.msg)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(setup.swarm_task.key)
    task_occurrences = list(reloaded_swarm.tasks_left_to_run).count(
        setup.batch_task.key
    )
    assert task_occurrences == 1
    assert len(reloaded_swarm.tasks_left_to_run) == queue_length_before


@pytest.mark.asyncio
async def test_crash_after_workflow_started_no_duplicate_execution_idempotent(
    batch_item_run_setup,
):
    # Arrange
    setup = batch_item_run_setup
    workflow_call_count = 0

    async def track_and_crash(*args, **kwargs):
        nonlocal workflow_call_count
        workflow_call_count += 1
        if workflow_call_count == 1:
            raise RuntimeError("Crash after workflow trigger")
        return None

    # Act
    with patch.object(TaskSignature, "aio_run_no_wait", side_effect=track_and_crash):
        with pytest.raises(RuntimeError):
            await setup.batch_task.aio_run_no_wait(setup.msg)

    # Assert
    assert workflow_call_count == 1

    # Act
    with patch.object(TaskSignature, "aio_run_no_wait", side_effect=track_and_crash):
        await setup.batch_task.aio_run_no_wait(setup.msg)

    # Assert
    assert workflow_call_count == 1


@pytest.mark.asyncio
async def test_two_consecutive_calls_same_task_no_duplicate_idempotent(
    batch_item_run_setup, mock_task_aio_run_no_wait
):
    # Arrange
    setup = batch_item_run_setup
    initial_counter = setup.swarm_task.current_running_tasks

    # Act
    await setup.batch_task.aio_run_no_wait(setup.msg)
    await setup.batch_task.aio_run_no_wait(setup.msg)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(setup.swarm_task.key)
    assert reloaded_swarm.current_running_tasks == initial_counter + 1
    assert mock_task_aio_run_no_wait.call_count == 1


@pytest.mark.asyncio
async def test_concurrent_calls_same_task_single_execution_idempotent(
    batch_item_run_setup,
):
    # Arrange
    setup = batch_item_run_setup
    initial_counter = setup.swarm_task.current_running_tasks
    workflow_calls = []
    call_lock = asyncio.Lock()

    async def track_calls(*args, **kwargs):
        async with call_lock:
            workflow_calls.append(1)
        return None

    # Act
    with patch.object(TaskSignature, "aio_run_no_wait", new=track_calls):
        await asyncio.gather(
            setup.batch_task.aio_run_no_wait(setup.msg),
            setup.batch_task.aio_run_no_wait(setup.msg),
            setup.batch_task.aio_run_no_wait(setup.msg),
        )

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(setup.swarm_task.key)
    assert reloaded_swarm.current_running_tasks == initial_counter + 1
    assert len(workflow_calls) == 1
