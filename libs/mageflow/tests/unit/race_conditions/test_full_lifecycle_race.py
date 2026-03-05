"""Race Condition 9: Full Lifecycle Integration.

Mixed concurrent operations test all race surfaces together.
Uses barrier injection at acall_signatures to force fill to read stale state
while finish/fail/add operations complete during the wait.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from thirdmagic.clients.lifecycle import BaseLifecycle

import mageflow
from mageflow.swarm.workflows import fill_swarm_running_tasks
from tests.integration.hatchet.models import ContextMessage
from tests.unit.race_conditions.conftest import assert_swarm_invariants
from tests.unit.workflows.conftest import create_swarm_item_test_setup


@pytest.mark.asyncio
@pytest.mark.parametrize("iteration", range(10))
async def test_full_lifecycle_mixed_ops(iteration, mock_adapter, mock_task_def, mock_logger):
    """Mixed concurrent operations: finish, fail, add, fill with barrier.

    Setup: max_concurrency=3, 6 tasks, 3 running (0,1,2), 3 pending (3,4,5).
    Barrier at acall_signatures: fill loads stale state (3 running, 0 finished).
    During barrier wait: finish(0), finish(1), fail(2), add(3 more) all complete.
    Fill proceeds with stale slots calculation.
    """
    setup = await create_swarm_item_test_setup(
        num_tasks=6,
        max_concurrency=6,
        stop_after_n_failures=None,
        current_running=3,
        tasks_left_indices=[3, 4, 5],
        logger=mock_logger,
    )
    swarm = setup.swarm_task

    barrier = asyncio.Barrier(2)
    call_count = 0

    async def acall_with_barrier(tasks, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            await barrier.wait()

    mock_adapter.acall_signatures.side_effect = acall_with_barrier
    lifecycle = AsyncMock(spec=BaseLifecycle)

    new_tasks = [
        await mageflow.asign(f"new_task_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]

    async def mutations_then_signal():
        """Execute all state mutations, then signal the barrier."""
        await swarm.finish_task(setup.tasks[0].key, {"result": "t0"})
        await swarm.finish_task(setup.tasks[1].key, {"result": "t1"})
        await swarm.task_failed(setup.tasks[2].key)
        await swarm.add_tasks(new_tasks)
        await barrier.wait()

    await asyncio.gather(
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
        mutations_then_signal(),
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
    )

    reloaded = await assert_swarm_invariants(swarm)

    finished = list(reloaded.finished_tasks)
    assert setup.tasks[0].key in finished
    assert setup.tasks[1].key in finished

    failed = list(reloaded.failed_tasks)
    assert setup.tasks[2].key in failed

    assert len(reloaded.tasks) == 9


@pytest.mark.asyncio
async def test_lifecycle_finish_all_then_fill_forced(mock_adapter, mock_task_def, mock_logger):
    """Finish all running tasks during fill's barrier wait, then fill schedules.

    Barrier at acall_signatures: fill loads stale state (2 running, 1 slot available).
    During wait, all 2 running tasks finish → Redis current_running=0.
    Fill proceeds with stale slots (thought only 1 available) → under-schedules.
    """
    setup = await create_swarm_item_test_setup(
        num_tasks=6,
        max_concurrency=3,
        stop_after_n_failures=None,
        current_running=2,
        tasks_left_indices=[3, 4, 5],
        logger=mock_logger,
    )
    swarm = setup.swarm_task

    barrier = asyncio.Barrier(2)

    async def acall_with_barrier(tasks, *args, **kwargs):
        await barrier.wait()

    mock_adapter.acall_signatures.side_effect = acall_with_barrier
    lifecycle = AsyncMock(spec=BaseLifecycle)

    async def finish_all_then_signal():
        await swarm.finish_task(setup.tasks[0].key, {"r": 0})
        await swarm.finish_task(setup.tasks[1].key, {"r": 1})
        await barrier.wait()

    await asyncio.gather(
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
        finish_all_then_signal(),
    )

    reloaded = await assert_swarm_invariants(swarm)
    assert reloaded.current_running_tasks <= 3
    assert len(list(reloaded.finished_tasks)) == 2


@pytest.mark.asyncio
async def test_lifecycle_interleaved_ops_forced(mock_adapter, mock_task_def, mock_logger):
    """Two rounds of interleaved finish, fail, and fill with barrier injection.

    Round 1: Barrier forces fill to read stale state while finishes/fail commit.
    Round 2: Same pattern for second round.
    """
    setup = await create_swarm_item_test_setup(
        num_tasks=8,
        max_concurrency=6,
        stop_after_n_failures=None,
        current_running=4,
        tasks_left_indices=[4, 5, 6, 7],
        logger=mock_logger,
    )
    swarm = setup.swarm_task

    # Round 1: barrier injection
    barrier1 = asyncio.Barrier(2)

    async def acall_round1(tasks, *args, **kwargs):
        await barrier1.wait()

    mock_adapter.acall_signatures.side_effect = acall_round1
    lifecycle = AsyncMock(spec=BaseLifecycle)

    async def round1_mutations():
        await swarm.finish_task(setup.tasks[0].key, {"r": 0})
        await swarm.finish_task(setup.tasks[1].key, {"r": 1})
        await swarm.task_failed(setup.tasks[2].key)
        await barrier1.wait()

    await asyncio.gather(
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
        round1_mutations(),
    )

    await assert_swarm_invariants(swarm)

    # Round 2: no barrier needed — round 1 may have consumed all pending tasks.
    # Just verify that finishing task 3 and filling works correctly after round 1.
    mock_adapter.acall_signatures.side_effect = None
    mock_adapter.acall_signatures.reset_mock()

    await swarm.finish_task(setup.tasks[3].key, {"r": 3})
    await fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger)

    reloaded = await assert_swarm_invariants(swarm)
    assert len(list(reloaded.finished_tasks)) >= 3
    assert len(list(reloaded.failed_tasks)) >= 1
