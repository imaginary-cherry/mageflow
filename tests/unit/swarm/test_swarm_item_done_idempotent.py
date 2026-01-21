from unittest.mock import patch

import pytest
import rapyer

from mageflow.invokers.hatchet import HatchetInvoker
from mageflow.swarm.workflows import swarm_item_done
from tests.unit.swarm.conftest import SwarmItemDoneSetup


async def assert_swarm_item_done_state(
    setup: SwarmItemDoneSetup,
    expected_finished_count: int = 1,
    expected_running_tasks: int = 0,
    expected_results_count: int | None = 1,
    check_batch_in_finished: bool = True,
):
    finished_tasks = await setup.swarm_task.finished_tasks.aload()
    assert len(finished_tasks) == expected_finished_count
    if check_batch_in_finished:
        assert setup.batch_task.key in finished_tasks
    assert len(set(finished_tasks)) == len(finished_tasks)

    if expected_results_count is not None:
        tasks_results = await setup.swarm_task.tasks_results.aload()
        assert len(tasks_results) == expected_results_count

    running_tasks = await setup.swarm_task.current_running_tasks.aload()
    assert running_tasks == expected_running_tasks


@pytest.mark.asyncio
async def test_two_consecutive_calls_same_item_no_duplicate_idempotent(
    swarm_item_done_setup, mock_fill_running_tasks
):
    # Arrange
    setup = swarm_item_done_setup

    # Act
    await swarm_item_done(setup.msg, setup.ctx)
    await swarm_item_done(setup.msg, setup.ctx)

    # Assert
    await assert_swarm_item_done_state(setup)


@pytest.mark.asyncio
async def test_retry_with_prepopulated_done_state_skips_update_idempotent(
    swarm_item_done_setup, mock_fill_running_tasks
):
    # Arrange
    setup = swarm_item_done_setup

    # Act
    with patch.object(HatchetInvoker, "wait_task", side_effect=Exception):
        with pytest.raises(Exception):
            await swarm_item_done(setup.msg, setup.ctx)
    await swarm_item_done(setup.msg, setup.ctx)

    # Assert
    await assert_swarm_item_done_state(setup)
    mock_fill_running_tasks.assert_called_once()


@pytest.mark.asyncio
async def test_crash_before_pipeline_retry_executes_normally_idempotent(
    swarm_item_done_setup, mock_fill_running_tasks
):
    # Arrange
    setup = swarm_item_done_setup

    # Act - First call crashes before pipeline
    with patch.object(rapyer, "afind", side_effect=RuntimeError):
        with pytest.raises(RuntimeError):
            await swarm_item_done(setup.msg, setup.ctx)

    # Verify no state change - crashed before pipeline
    await assert_swarm_item_done_state(
        setup,
        expected_finished_count=0,
        expected_running_tasks=1,
        expected_results_count=None,
        check_batch_in_finished=False,
    )

    # Act - Retry should succeed
    await swarm_item_done(setup.msg, setup.ctx)

    # Assert idempotency
    await assert_swarm_item_done_state(setup, expected_results_count=None)


@pytest.mark.asyncio
async def test_retry_after_wait_task_failure_no_duplicate_idempotent(
    swarm_item_done_setup, mock_fill_running_tasks
):
    # Arrange
    setup = swarm_item_done_setup

    # Act
    with patch.object(
        HatchetInvoker,
        "wait_task",
        side_effect=RuntimeError("Simulated wait_task failure"),
    ):
        with pytest.raises(RuntimeError, match="Simulated wait_task failure"):
            await swarm_item_done(setup.msg, setup.ctx)

    await swarm_item_done(setup.msg, setup.ctx)

    # Assert
    await assert_swarm_item_done_state(setup)
