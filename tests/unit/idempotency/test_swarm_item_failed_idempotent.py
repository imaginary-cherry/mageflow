from unittest.mock import patch

import pytest

from mageflow.invokers.hatchet import HatchetInvoker
from mageflow.swarm.model import SwarmTaskSignature
from mageflow.swarm.workflows import swarm_item_failed
from tests.unit.idempotency.conftest import SwarmItemFailedSetup


async def assert_swarm_item_failed_state(
    setup: SwarmItemFailedSetup,
    expected_failed_count: int = 1,
    expected_running_tasks: int = 0,
    check_batch_in_failed: bool = True,
):
    failed_tasks = await setup.swarm_task.failed_tasks.aload()
    assert len(failed_tasks) == expected_failed_count
    if check_batch_in_failed:
        assert setup.batch_task.key in failed_tasks
    # Check no duplicates
    assert len(set(failed_tasks)) == len(failed_tasks)

    running_tasks = await setup.swarm_task.current_running_tasks.aload()
    assert running_tasks == expected_running_tasks


@pytest.mark.asyncio
async def test_two_consecutive_calls_same_item_no_duplicate_idempotent(
    swarm_item_failed_setup, mock_fill_running_tasks
):
    # Arrange
    setup = swarm_item_failed_setup

    # Act
    await swarm_item_failed(setup.msg, setup.ctx)
    await swarm_item_failed(setup.msg, setup.ctx)

    # Assert
    await assert_swarm_item_failed_state(setup)


@pytest.mark.asyncio
async def test_retry_with_prepopulated_failed_state_skips_update_idempotent(
    swarm_item_failed_setup, mock_fill_running_tasks
):
    # Arrange
    setup = swarm_item_failed_setup

    # Act
    with patch.object(HatchetInvoker, "wait_task", side_effect=Exception):
        with pytest.raises(Exception):
            await swarm_item_failed(setup.msg, setup.ctx)
    await swarm_item_failed(setup.msg, setup.ctx)

    # Assert
    await assert_swarm_item_failed_state(setup)
    # This is not necessary, but we check it to ensure what happened during the test
    mock_fill_running_tasks.assert_called_once()


@pytest.mark.asyncio
async def test_crash_before_get_safe_retry_executes_normally_idempotent(
    swarm_item_failed_setup, mock_fill_running_tasks
):
    # Arrange
    setup = swarm_item_failed_setup

    # Act - First call crashes before get_safe
    with patch.object(SwarmTaskSignature, "get_safe", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            await swarm_item_failed(setup.msg, setup.ctx)

    # Verify no state change - crashed before state update
    await assert_swarm_item_failed_state(
        setup,
        expected_failed_count=0,
        expected_running_tasks=1,
        check_batch_in_failed=False,
    )

    # Act - Retry should succeed
    await swarm_item_failed(setup.msg, setup.ctx)

    # Assert idempotency
    await assert_swarm_item_failed_state(setup)


@pytest.mark.asyncio
async def test_retry_after_wait_task_failure_no_duplicate_idempotent(
    swarm_item_failed_setup, mock_fill_running_tasks
):
    # Arrange
    setup = swarm_item_failed_setup

    # Act
    with patch.object(
        HatchetInvoker,
        "wait_task",
        side_effect=RuntimeError("Simulated wait_task failure"),
    ):
        with pytest.raises(RuntimeError, match="Simulated wait_task failure"):
            await swarm_item_failed(setup.msg, setup.ctx)

    await swarm_item_failed(setup.msg, setup.ctx)

    # Assert
    await assert_swarm_item_failed_state(setup)
