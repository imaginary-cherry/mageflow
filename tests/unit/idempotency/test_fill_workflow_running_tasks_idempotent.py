from unittest.mock import patch

import pytest

from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus
from mageflow.swarm.model import SwarmTaskSignature
from mageflow.swarm.workflows import fill_swarm_running_tasks
from tests.unit.assertions import assert_task_has_short_ttl
from tests.unit.idempotency.conftest import CompletedSwarmSetup, FailedSwarmSetup


@pytest.mark.asyncio
async def test_failure_path_crash_at_interrupt_retry_succeeds_idempotent(
    failed_swarm_setup, mock_activate_error
):
    # Arrange
    setup: FailedSwarmSetup = failed_swarm_setup

    # Act - First call crashes at interrupt
    with patch.object(SwarmTaskSignature, "interrupt", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            await fill_swarm_running_tasks(setup.msg, setup.ctx)

    # Assert - swarm still exists (interrupt failed before remove)
    swarm = await SwarmTaskSignature.get_safe(setup.swarm_task.key)
    assert swarm is not None

    # Act - Retry succeeds
    await fill_swarm_running_tasks(setup.msg, setup.ctx)

    # Assert - linked tasks status changed (via interrupt -> suspend)
    original_task = await TaskSignature.get_safe(setup.original_task.key)
    assert original_task.task_status.status == SignatureStatus.SUSPENDED

    # Assert - activate_error and remove were called
    mock_activate_error.assert_called()
    await assert_task_has_short_ttl(setup.swarm_task.key)
    await assert_task_has_short_ttl(setup.batch_task.key)
    await assert_task_has_short_ttl(setup.batch_task.original_task_id)


@pytest.mark.asyncio
async def test_failure_path_crash_at_activate_error_retry_succeeds_idempotent(
    failed_swarm_setup, mock_activate_error
):
    # Arrange
    setup: FailedSwarmSetup = failed_swarm_setup
    mock_activate_error.side_effect = RuntimeError

    # Act - First call crashes at activate_error
    with pytest.raises(RuntimeError):
        await fill_swarm_running_tasks(setup.msg, setup.ctx)

    # Assert - swarm still exists (remove wasn't called due to crash)
    swarm = await SwarmTaskSignature.get_safe(setup.swarm_task.key)
    assert swarm is not None

    # Act - Retry succeeds (activate_error can be called multiple times - it's idempotent)
    mock_activate_error.side_effect = None
    await fill_swarm_running_tasks(setup.msg, setup.ctx)

    # Assert - both activate_error and remove were called on retry
    await assert_task_has_short_ttl(setup.swarm_task.key)
    await assert_task_has_short_ttl(setup.batch_task.key)
    await assert_task_has_short_ttl(setup.batch_task.original_task_id)


@pytest.mark.asyncio
async def test__failure_swarm_retry_twice__not_removing_or_republish(
    failed_swarm_setup, mock_activate_error, mock_swarm_remove, mock_interrupt
):
    # Arrange
    setup: FailedSwarmSetup = failed_swarm_setup

    # Act
    await fill_swarm_running_tasks(setup.msg, setup.ctx)
    await fill_swarm_running_tasks(setup.msg, setup.ctx)

    # Assert
    assert mock_swarm_remove.call_count == 1
    assert mock_activate_error.call_count == 1
    assert mock_interrupt.call_count == 1


@pytest.mark.asyncio
async def test_on_remove_task__finish_removing_all(
    completed_swarm_setup, mock_batch_task_run
):
    # Arrange
    setup: CompletedSwarmSetup = completed_swarm_setup

    # Act - First call crashes at activate_success
    with pytest.raises(RuntimeError):
        with patch.object(
            SwarmTaskSignature, "remove_task", side_effect=RuntimeError()
        ):
            await fill_swarm_running_tasks(setup.msg, setup.ctx)

    # Act - Retry succeeds
    await fill_swarm_running_tasks(setup.msg, setup.ctx)

    # Assert
    await assert_task_has_short_ttl(setup.swarm_task.key)
    await assert_task_has_short_ttl(setup.batch_task.key)
