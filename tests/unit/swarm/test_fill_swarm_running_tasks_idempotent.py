from unittest.mock import patch, AsyncMock

import pytest

from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus
from mageflow.swarm.model import SwarmTaskSignature
from mageflow.swarm.workflows import fill_swarm_running_tasks
from tests.unit.swarm.conftest import FailedSwarmSetup, CompletedSwarmSetup


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


@pytest.mark.asyncio
async def test_failure_path_crash_at_activate_error_retry_succeeds_idempotent(
    failed_swarm_setup,
):
    # Arrange
    setup: FailedSwarmSetup = failed_swarm_setup

    # Act - First call crashes at activate_error
    with patch.object(SwarmTaskSignature, "activate_error", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            await fill_swarm_running_tasks(setup.msg, setup.ctx)

    # Assert - swarm still exists (remove wasn't called due to crash)
    swarm = await SwarmTaskSignature.get_safe(setup.swarm_task.key)
    assert swarm is not None

    # Act - Retry succeeds (activate_error can be called multiple times - it's idempotent)
    with patch.object(
        SwarmTaskSignature, "activate_error", new_callable=AsyncMock
    ) as mock_activate:
        with patch.object(
            SwarmTaskSignature, "remove", new_callable=AsyncMock
        ) as mock_remove:
            await fill_swarm_running_tasks(setup.msg, setup.ctx)

            # Assert - both activate_error and remove were called on retry
            mock_activate.assert_called_once()
            mock_remove.assert_called_once()


@pytest.mark.asyncio
async def test_completion_path_crash_at_activate_success_retry_idempotent(
    completed_swarm_setup, mock_batch_task_run
):
    # Arrange
    setup: CompletedSwarmSetup = completed_swarm_setup
    call_count = 0

    async def fail_first_time(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("activate_success failed")

    # Mock done() to avoid side effects
    with patch.object(SwarmTaskSignature, "done", new_callable=AsyncMock):
        # Act - First call crashes at activate_success
        with patch.object(
            SwarmTaskSignature, "activate_success", side_effect=fail_first_time
        ):
            with pytest.raises(RuntimeError, match="activate_success failed"):
                await fill_swarm_running_tasks(setup.msg, setup.ctx)

        # Assert - first call raised
        assert call_count == 1

        # Act - Retry succeeds
        with patch.object(
            SwarmTaskSignature, "activate_success", new_callable=AsyncMock
        ) as mock_success:
            await fill_swarm_running_tasks(setup.msg, setup.ctx)

            # Assert - activate_success was called on retry
            mock_success.assert_called_once()


@pytest.mark.asyncio
async def test_completion_path_multiple_calls_activate_success_once_idempotent(
    completed_swarm_setup, mock_batch_task_run
):
    # Arrange
    setup: CompletedSwarmSetup = completed_swarm_setup
    activate_success_call_count = 0

    async def track_and_update_status(*args, **kwargs):
        nonlocal activate_success_call_count
        activate_success_call_count += 1
        # Simulate what activate_success does - changes status so condition won't be met again
        async with SwarmTaskSignature.lock_from_key(setup.swarm_task.key) as swarm:
            await swarm.aupdate(task_status={"status": SignatureStatus.ACTIVE.value})

    # Mock done() and activate_success to track calls
    with patch.object(SwarmTaskSignature, "done", new_callable=AsyncMock):
        with patch.object(
            SwarmTaskSignature, "activate_success", side_effect=track_and_update_status
        ):
            # Act - First call
            await fill_swarm_running_tasks(setup.msg, setup.ctx)

            # Assert - called once
            assert activate_success_call_count == 1

            # Act - Second call - has_published_callback() should now be False
            # because status changed from DONE to ACTIVE
            await fill_swarm_running_tasks(setup.msg, setup.ctx)

            # Assert - still only called once (second call didn't trigger it)
            assert activate_success_call_count == 1
