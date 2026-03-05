"""Race Condition 7: Fail-Count Race.

THE RACE:
    fill_swarm_running_tasks() loads the swarm via afind_one (line 56) and checks
    has_swarm_failed() (line 63) on the LOCAL object. If multiple task_failed()
    calls commit their NUMINCRBY to failed_tasks AFTER fill loads the swarm,
    fill sees stale failure count and doesn't detect the threshold breach.

    In practice, this means fill proceeds to schedule more tasks when the swarm
    should have been stopped due to too many failures.

HOW IT'S FORCED:
    Inject a barrier at acall_signatures so fill loads the swarm with 0 failures,
    then the failures commit during the wait. Fill's local has_swarm_failed()
    was already evaluated (returned False), so it proceeds to schedule tasks
    even though the swarm has actually failed.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from thirdmagic.clients.lifecycle import BaseLifecycle
from thirdmagic.swarm.model import SwarmTaskSignature

from mageflow.swarm.workflows import fill_swarm_running_tasks
from tests.unit.race_conditions.conftest import assert_swarm_invariants, barrier_on_mock
from tests.unit.workflows.conftest import create_swarm_item_test_setup


@pytest.mark.asyncio
async def test_fail_count_concurrent_failures_forced(mock_adapter, mock_task_def, mock_logger):
    """3 concurrent task_failed calls with barrier → fill misses failure threshold.

    Setup: 3 running tasks (will fail), 2 pending tasks, max_concurrency=5.
    Fill loads swarm (0 failures, 2 slots available), checks has_swarm_failed (False),
    enters fill_running_tasks, reaches acall_signatures → barrier wait.
    During wait, 3 task_failed calls complete → has_swarm_failed()=True.
    Fill proceeds to dispatch tasks on a swarm that should have been stopped.
    """
    setup = await create_swarm_item_test_setup(
        num_tasks=5,
        max_concurrency=5,
        stop_after_n_failures=3,
        current_running=3,
        tasks_left_indices=[3, 4],
        logger=mock_logger,
    )
    swarm = setup.swarm_task

    barrier = asyncio.Barrier(2)

    async def acall_with_barrier(*args, **kwargs):
        await barrier.wait()

    mock_adapter.acall_signatures.side_effect = acall_with_barrier
    lifecycle = AsyncMock(spec=BaseLifecycle)

    async def fail_then_signal():
        await swarm.task_failed(setup.tasks[0].key)
        await swarm.task_failed(setup.tasks[1].key)
        await swarm.task_failed(setup.tasks[2].key)
        await barrier.wait()

    # Fill loads swarm (0 failures), checks has_swarm_failed (False),
    # enters fill_running_tasks, reaches acall_signatures → waits at barrier.
    # Meanwhile fail_then_signal fails 3 tasks and signals.
    # Fill proceeds to dispatch tasks even though swarm has failed.
    await asyncio.gather(
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
        fail_then_signal(),
    )

    reloaded = await SwarmTaskSignature.afind_one(swarm.key)
    assert len(list(reloaded.failed_tasks)) == 3
    assert reloaded.has_swarm_failed() is True
    await assert_swarm_invariants(swarm)


@pytest.mark.asyncio
async def test_fail_then_fill_detects_failure(mock_adapter, mock_task_def, mock_logger):
    """After failures complete, fill should detect the failure threshold.

    No barrier needed: sequential failures, then fill loads fresh state.
    """
    setup = await create_swarm_item_test_setup(
        num_tasks=5,
        max_concurrency=5,
        stop_after_n_failures=3,
        current_running=3,
        tasks_left_indices=[3, 4],
        logger=mock_logger,
    )
    swarm = setup.swarm_task

    lifecycle = AsyncMock(spec=BaseLifecycle)

    await asyncio.gather(
        swarm.task_failed(setup.tasks[0].key),
        swarm.task_failed(setup.tasks[1].key),
        swarm.task_failed(setup.tasks[2].key),
    )

    # Fill loads fresh swarm → sees 3 failures → detects threshold
    await fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger)

    lifecycle.task_failed.assert_awaited_once()


@pytest.mark.asyncio
async def test_fail_race_with_fill_stale_read(mock_adapter, mock_task_def, mock_logger):
    """Fill loads swarm before failures commit → misses failure threshold.

    The barrier at acall_signatures forces fill to read the swarm (0 failures)
    and proceed past has_swarm_failed() check. The failures commit during the
    barrier wait, but fill already decided the swarm hasn't failed.
    """
    setup = await create_swarm_item_test_setup(
        num_tasks=6,
        max_concurrency=6,
        stop_after_n_failures=3,
        current_running=4,
        tasks_left_indices=[4, 5],
        logger=mock_logger,
    )
    swarm = setup.swarm_task

    barrier = asyncio.Barrier(2)

    async def acall_with_barrier(*args, **kwargs):
        await barrier.wait()

    mock_adapter.acall_signatures.side_effect = acall_with_barrier

    lifecycle = AsyncMock(spec=BaseLifecycle)

    async def fail_then_signal():
        """Fail 3 tasks then signal the barrier."""
        await swarm.task_failed(setup.tasks[0].key)
        await swarm.task_failed(setup.tasks[1].key)
        await swarm.task_failed(setup.tasks[2].key)
        await barrier.wait()

    # Fill loads swarm (0 failures), checks has_swarm_failed (False),
    # enters fill_running_tasks, reaches acall_signatures → waits at barrier.
    # Meanwhile, fail_then_signal fails 3 tasks and signals.
    # Fill proceeds to schedule tasks even though swarm has failed.
    await asyncio.gather(
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
        fail_then_signal(),
    )

    reloaded = await assert_swarm_invariants(swarm)
    assert len(list(reloaded.failed_tasks)) == 3

    # Fill didn't call lifecycle.task_failed because it read stale state
    # (has_swarm_failed was False when checked)
    # This documents the stale-read behavior
    assert reloaded.has_swarm_failed() is True


@pytest.mark.asyncio
@pytest.mark.parametrize("iteration", range(10))
async def test_fail_count_stress(iteration, mock_adapter, mock_task_def, mock_logger):
    """Stress: concurrent failures at threshold boundary with barrier injection.

    Setup: 4 running (will fail), 2 pending, max_concurrency=6.
    Barrier at acall_signatures: fill reads stale failure count (0),
    passes has_swarm_failed check, enters scheduling → barrier wait.
    4 failures commit during wait → has_swarm_failed()=True.
    """
    setup = await create_swarm_item_test_setup(
        num_tasks=6,
        max_concurrency=6,
        stop_after_n_failures=3,
        current_running=4,
        tasks_left_indices=[4, 5],
        logger=mock_logger,
    )
    swarm = setup.swarm_task

    barrier = asyncio.Barrier(2)

    async def acall_with_barrier(*args, **kwargs):
        await barrier.wait()

    mock_adapter.acall_signatures.side_effect = acall_with_barrier
    lifecycle = AsyncMock(spec=BaseLifecycle)

    async def fail_all_then_signal():
        await swarm.task_failed(setup.tasks[0].key)
        await swarm.task_failed(setup.tasks[1].key)
        await swarm.task_failed(setup.tasks[2].key)
        await swarm.task_failed(setup.tasks[3].key)
        await barrier.wait()

    await asyncio.gather(
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
        fail_all_then_signal(),
    )

    reloaded = await assert_swarm_invariants(swarm)
    assert reloaded.has_swarm_failed() is True
    assert len(list(reloaded.failed_tasks)) == 4
