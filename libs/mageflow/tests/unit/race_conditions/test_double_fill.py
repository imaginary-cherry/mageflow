"""Race Condition 1: Double-Fill (Over-Scheduling / Double-Dispatch).

THE RACE:
    fill_running_tasks() reads current_running_tasks OUTSIDE any pipeline (line 97),
    calculates available slots, takes tasks in a first pipeline, dispatches via
    acall_signatures, then increments current_running_tasks in a second pipeline.

    Two concurrent calls create two distinct race manifestations:

    VARIANT A - Double-Dispatch via PublishState:
        Coroutine A takes tasks and sets them in PublishState. Coroutine B loads
        PublishState and dispatches the SAME tasks again. Both increment crt but
        the JSON.SET in the pipeline overwrites the NUMINCRBY, leaving crt = N
        instead of 2N. Result: same tasks sent to workers twice.

    VARIANT B - Under-Counted Dispatch via stale reads:
        Both coroutines load empty PublishState before either writes. Both enter
        the 'if not task_ids_to_run' block and take DIFFERENT tasks from
        tasks_left_to_run (pipeline atomicity ensures no overlap). Both dispatch
        their tasks, but crt only reflects one batch (SET overwrites NUMINCRBY).
        Result: 2N tasks running with crt = N. When all complete, crt goes negative.

HOW THEY'RE FORCED:
    Variant A: Barrier at acall_signatures — A's first pipeline sets PublishState
    before B loads it. B uses PublishState tasks instead of tasks_left_to_run.

    Variant B: Barrier at PublishState.aget — both load empty PublishState, both
    go through the task-selection logic independently.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from thirdmagic.clients.lifecycle import BaseLifecycle
from thirdmagic.swarm.model import SwarmTaskSignature
from thirdmagic.swarm import PublishState

from mageflow.swarm.workflows import fill_swarm_running_tasks
from tests.unit.race_conditions.conftest import assert_swarm_invariants
from tests.unit.workflows.conftest import create_swarm_item_test_setup


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Known race: PublishState causes double-dispatch of same tasks"
)
async def test_double_fill_double_dispatch(mock_adapter, mock_task_def, mock_logger):
    """Variant A: Barrier at acall_signatures → same tasks dispatched twice.

    Coroutine A's first pipeline sets PublishState with task IDs.
    Coroutine B loads those from PublishState and dispatches the same tasks.
    Both dispatch the same 2 tasks → double-dispatch.
    """
    setup = await create_swarm_item_test_setup(
        num_tasks=4,
        max_concurrency=2,
        stop_after_n_failures=None,
        current_running=0,
        tasks_left_indices=[0, 1, 2, 3],
        logger=mock_logger,
    )
    swarm = setup.swarm_task
    await swarm.aupdate(is_swarm_closed=True)

    barrier = asyncio.Barrier(2)
    dispatched_task_ids = []

    async def acall_with_barrier(tasks, *args, **kwargs):
        dispatched_task_ids.append([t.key for t in tasks])
        await barrier.wait()

    mock_adapter.acall_signatures.side_effect = acall_with_barrier
    lifecycle = AsyncMock(spec=BaseLifecycle)

    await asyncio.gather(
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
    )

    # Should dispatch max_concurrency tasks total, not more
    assert len(dispatched_task_ids) <= 1, (
        f"acall_signatures called {len(dispatched_task_ids)} times, "
        f"expected at most 1 (tasks should not be double-dispatched)"
    )


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Known race: stale PublishState reads cause under-counted dispatches"
)
async def test_double_fill_under_counted(mock_adapter, mock_task_def, mock_logger):
    """Variant B: Barrier at PublishState.aget → both take different tasks.

    Both coroutines load empty PublishState, both calculate resource_to_run=2,
    both take 2 tasks from tasks_left_to_run. 4 unique tasks dispatched but
    current_running_tasks = 2 (SET overwrites NUMINCRBY). When all 4 complete,
    each decrements → crt goes to -2.
    """
    setup = await create_swarm_item_test_setup(
        num_tasks=4,
        max_concurrency=2,
        stop_after_n_failures=None,
        current_running=0,
        tasks_left_indices=[0, 1, 2, 3],
        logger=mock_logger,
    )
    swarm = setup.swarm_task
    await swarm.aupdate(is_swarm_closed=True)

    aget_barrier = asyncio.Barrier(2)
    original_aget = PublishState.aget

    @classmethod
    async def aget_with_barrier(cls, key, **kwargs):
        result = await original_aget(key, **kwargs)
        await aget_barrier.wait()
        return result

    dispatched_task_ids = []

    async def track_acall(tasks, *args, **kwargs):
        dispatched_task_ids.append([t.key for t in tasks])

    mock_adapter.acall_signatures.side_effect = track_acall
    lifecycle = AsyncMock(spec=BaseLifecycle)

    with patch.object(PublishState, 'aget', aget_with_barrier):
        await asyncio.gather(
            fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
            fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
        )

    all_dispatched = [t for batch in dispatched_task_ids for t in batch]
    unique_dispatched = set(all_dispatched)

    # Should dispatch at most max_concurrency unique tasks
    assert len(unique_dispatched) <= 2, (
        f"Dispatched {len(unique_dispatched)} unique tasks, "
        f"expected at most max_concurrency=2"
    )

    # Verify under-counting: crt doesn't reflect all dispatched tasks
    reloaded = await SwarmTaskSignature.afind_one(swarm.key)
    assert reloaded.current_running_tasks == len(unique_dispatched), (
        f"current_running_tasks={reloaded.current_running_tasks} but "
        f"{len(unique_dispatched)} unique tasks were actually dispatched"
    )


@pytest.mark.asyncio
async def test_double_fill_gather_only(mock_adapter, mock_task_def, mock_logger):
    """Without forced interleaving, fakeredis serializes calls → no race.

    Documents that asyncio.gather alone doesn't trigger the race with
    synchronous fakeredis.
    """
    setup = await create_swarm_item_test_setup(
        num_tasks=4,
        max_concurrency=2,
        stop_after_n_failures=None,
        current_running=0,
        tasks_left_indices=[0, 1, 2, 3],
        logger=mock_logger,
    )
    swarm = setup.swarm_task
    await swarm.aupdate(is_swarm_closed=True)

    lifecycle = AsyncMock(spec=BaseLifecycle)

    await asyncio.gather(
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
    )

    reloaded = await assert_swarm_invariants(swarm)
    assert reloaded.current_running_tasks <= 2
