"""Race Condition 4: Finish-While-Fill (Under-Scheduling).

THE RACE:
    finish_task() decrements current_running_tasks via NUMINCRBY(-1) in a pipeline.
    fill_running_tasks() reads current_running_tasks from a LOCAL snapshot loaded
    via afind_one (line 56 of fill_swarm_running_tasks), which may be stale.

    If finish_task commits its decrement AFTER fill loads the swarm, fill sees
    a higher current_running_tasks than reality → calculates fewer available slots
    → under-schedules. This is BENIGN (the next fill cycle catches up).

HOW IT'S FORCED:
    Inject a barrier at acall_signatures. The fill coroutine loads the swarm
    with the pre-finish running count, then proceeds through first pipeline.
    The finish coroutine completes (NUMINCRBY -1) during fill's barrier wait.
    Fill then does NUMINCRBY +N in the second pipeline, resulting in:
      Redis = (pre_finish - 1) + N  (correct, not over-scheduled)

    The under-scheduling manifests in the FIRST pipeline where num_of_task_to_run
    was calculated from the stale (higher) running count.
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
async def test_finish_while_fill_forced_under_scheduling(
    mock_adapter, mock_task_def, mock_logger
):
    """Force under-scheduling: fill reads stale running count, schedules fewer tasks.

    Setup: 2 running, max_concurrency=5, 5 pending.
    Fill reads current_running=2 → resource=3 → takes 3 tasks.
    Meanwhile finish decrements → Redis current_running=1.
    Fill NUMINCRBY +3 → Redis current_running=1+3=4.
    But could have scheduled 4 tasks (resource=5-1=4). Under-scheduled by 1.
    """
    setup = await create_swarm_item_test_setup(
        num_tasks=7,
        max_concurrency=5,
        stop_after_n_failures=None,
        current_running=2,
        tasks_left_indices=[2, 3, 4, 5, 6],
        logger=mock_logger,
    )
    swarm = setup.swarm_task

    barrier = asyncio.Barrier(2)

    async def acall_with_barrier(*args, **kwargs):
        await barrier.wait()

    mock_adapter.acall_signatures.side_effect = acall_with_barrier

    lifecycle = AsyncMock(spec=BaseLifecycle)

    async def finish_then_signal():
        await swarm.finish_task(setup.tasks[0].key, {"result": "ok"})
        await barrier.wait()

    await asyncio.gather(
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
        finish_then_signal(),
    )

    reloaded = await assert_swarm_invariants(swarm)
    assert reloaded.current_running_tasks >= 0
    assert reloaded.current_running_tasks <= 5


@pytest.mark.asyncio
async def test_finish_while_fill_multiple_forced(
    mock_adapter, mock_task_def, mock_logger
):
    """Force 3 finishes to complete while fill waits at barrier.

    Fill reads current_running=3, calculates resource=2.
    During barrier wait, 3 finishes complete → Redis current_running=0.
    Fill proceeds with resource=2 → schedules 2 tasks.
    Could have scheduled 5 tasks (resource=5-0=5). Under-scheduled by 3.
    """
    setup = await create_swarm_item_test_setup(
        num_tasks=8,
        max_concurrency=5,
        stop_after_n_failures=None,
        current_running=3,
        tasks_left_indices=[3, 4, 5, 6, 7],
        logger=mock_logger,
    )
    swarm = setup.swarm_task

    barrier = asyncio.Barrier(2)

    async def acall_with_barrier(*args, **kwargs):
        await barrier.wait()

    mock_adapter.acall_signatures.side_effect = acall_with_barrier
    lifecycle = AsyncMock(spec=BaseLifecycle)

    async def finish_all_then_signal():
        await swarm.finish_task(setup.tasks[0].key, {"result": "ok_0"})
        await swarm.finish_task(setup.tasks[1].key, {"result": "ok_1"})
        await swarm.finish_task(setup.tasks[2].key, {"result": "ok_2"})
        await barrier.wait()

    await asyncio.gather(
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
        finish_all_then_signal(),
    )

    reloaded = await assert_swarm_invariants(swarm)
    for i in range(3):
        assert setup.tasks[i].key in list(reloaded.finished_tasks)


@pytest.mark.asyncio
@pytest.mark.parametrize("iteration", range(10))
async def test_finish_while_fill_stress(iteration, mock_adapter, mock_task_def, mock_logger):
    """Stress: multiple finishes racing with fill via barrier injection.

    Barrier at acall_signatures: fill reads stale running count.
    Two finishes complete during barrier wait, then second fill runs.
    """
    setup = await create_swarm_item_test_setup(
        num_tasks=10,
        max_concurrency=5,
        stop_after_n_failures=None,
        current_running=4,
        tasks_left_indices=[4, 5, 6, 7, 8, 9],
        logger=mock_logger,
    )
    swarm = setup.swarm_task

    barrier = asyncio.Barrier(2)
    call_count = 0

    async def acall_with_barrier(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            await barrier.wait()

    mock_adapter.acall_signatures.side_effect = acall_with_barrier
    lifecycle = AsyncMock(spec=BaseLifecycle)

    async def finish_then_signal():
        await swarm.finish_task(setup.tasks[0].key, {"r": 0})
        await swarm.finish_task(setup.tasks[1].key, {"r": 1})
        await barrier.wait()

    await asyncio.gather(
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
        finish_then_signal(),
        swarm.finish_task(setup.tasks[2].key, {"r": 2}),
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
    )

    reloaded = await assert_swarm_invariants(swarm)
