"""Race Condition 3: Add-While-Fill.

THE RACE:
    add_tasks() extends tasks_left_to_run in a pipeline while fill_running_tasks()
    reads tasks_left_to_run and calculates num_of_task_to_run from a stale snapshot.

INTERLEAVING ANALYSIS:
    fill_running_tasks reads tasks_left_to_run OUTSIDE its first pipeline (line 102),
    but inside the first pipeline (line 104), it does a FRESH read from Redis
    (apipeline.__aenter__ calls aget). So the slice uses the fresh list, but
    num_of_task_to_run was calculated from the stale local object.

    With fakeredis (synchronous), coroutines serialize naturally. The race would
    require true parallel execution (real Redis, multiple workers) to manifest
    data loss. These tests verify invariants hold under asyncio.gather scheduling.

HOW IT'S FORCED:
    Inject a barrier at acall_signatures. Fill loads the swarm, reads
    tasks_left_to_run (stale), enters first pipeline and takes tasks, then
    reaches acall_signatures → waits at barrier.
    Meanwhile, add_tasks extends tasks_left_to_run and signals the barrier.
    Fill proceeds with the stale num_of_task_to_run → under-scheduling.

NOTE: In production with multiple workers hitting real Redis, the pipeline atomicity
protects against corrupted data, but tasks could be under-scheduled (fill calculates
fewer slots than available because add_tasks extended the list after the stale read).
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
async def test_add_while_fill_forced(mock_adapter, mock_task_def, mock_logger):
    """
    Force fill to read stale tasks_left_to_run while add_tasks extends it.

    Barrier at acall_signatures: fill reaches here after reading stale
    tasks_left_to_run (3 tasks) and taking tasks. During the barrier wait,
    add_tasks extends tasks_left_to_run with 3 more tasks. Fill proceeds
    with stale num_of_task_to_run → may under-schedule.
    """
    setup = await create_swarm_item_test_setup(
        max_concurrency=5,
        stop_after_n_failures=None,
        current_running=0,
        tasks_left_indices=[0, 1, 2],
        logger=mock_logger,
    )
    swarm = setup.swarm_task

    new_tasks = [
        await mageflow.asign(f"new_task_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]

    barrier = asyncio.Barrier(2)

    async def acall_with_barrier(tasks, *args, **kwargs):
        await barrier.wait()

    mock_adapter.acall_signatures.side_effect = acall_with_barrier
    lifecycle = AsyncMock(spec=BaseLifecycle)

    async def add_then_signal():
        await swarm.add_tasks(new_tasks)
        await barrier.wait()

    await asyncio.gather(
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
        add_then_signal(),
    )

    reloaded = await assert_swarm_invariants(swarm)

    # All 6 tasks should be in swarm.tasks
    assert (
        len(reloaded.tasks) == 6
    ), f"Expected 6 total tasks, got {len(reloaded.tasks)}"

    # Every task should be accounted for in some state
    left = set(reloaded.tasks_left_to_run)
    finished = set(reloaded.finished_tasks)
    failed = set(reloaded.failed_tasks)
    all_tasks = set(reloaded.tasks)
    accounted = left | finished | failed
    running = all_tasks - accounted
    assert reloaded.current_running_tasks == len(running), (
        f"current_running_tasks ({reloaded.current_running_tasks}) doesn't match "
        f"unaccounted tasks ({len(running)})"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("iteration", range(10))
async def test_add_while_fill_stress(
    iteration, mock_adapter, mock_task_def, mock_logger
):
    """
    Stress: concurrent adds and fills with barrier injection.

    Barrier at acall_signatures (parties=3): both fills and one add_tasks
    all synchronize. Fills read stale tasks_left_to_run before adds extend it.
    """
    setup = await create_swarm_item_test_setup(
        max_concurrency=10,
        stop_after_n_failures=None,
        current_running=0,
        tasks_left_indices=[0, 1, 2],
        logger=mock_logger,
    )
    swarm = setup.swarm_task

    lifecycle = AsyncMock(spec=BaseLifecycle)

    batch1 = [
        await mageflow.asign(f"batch1_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]
    batch2 = [
        await mageflow.asign(f"batch2_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]

    barrier = asyncio.Barrier(2)
    call_count = 0

    async def acall_with_barrier(tasks, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Only first fill waits at barrier
            await barrier.wait()

    mock_adapter.acall_signatures.side_effect = acall_with_barrier

    async def add_batches_then_signal():
        await swarm.add_tasks(batch1)
        await swarm.add_tasks(batch2)
        await barrier.wait()

    await asyncio.gather(
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
        add_batches_then_signal(),
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
    )

    reloaded = await assert_swarm_invariants(swarm)
    assert (
        len(reloaded.tasks) == 9
    ), f"Stress iteration {iteration}: expected 9 tasks, got {len(reloaded.tasks)}"
