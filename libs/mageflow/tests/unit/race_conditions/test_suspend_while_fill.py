"""Race Condition 8: Suspend-While-Fill.

THE RACE:
    suspend() changes task_status to SUSPENDED and suspends all sub-tasks.
    fill_running_tasks() dispatches tasks and increments current_running_tasks.
    If fill dispatches tasks AFTER suspend, those tasks run on a suspended swarm.

    fill_swarm_running_tasks doesn't check task_status before dispatching.
    The suspend status is only checked by external callers, not internally.

HOW IT'S FORCED:
    Barrier at acall_signatures: fill reaches acall_signatures after loading the
    swarm and taking tasks from the first pipeline. During the barrier wait,
    suspend completes and changes status to SUSPENDED. Fill proceeds to dispatch
    tasks on the now-suspended swarm.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from thirdmagic.clients.lifecycle import BaseLifecycle
from thirdmagic.signature.status import SignatureStatus
from thirdmagic.swarm.model import SwarmTaskSignature

from mageflow.swarm.workflows import fill_swarm_running_tasks
from tests.unit.race_conditions.conftest import assert_swarm_invariants, barrier_on_mock
from tests.unit.workflows.conftest import create_swarm_item_test_setup


@pytest.mark.asyncio
async def test_suspend_while_fill_forced(mock_adapter, mock_task_def, mock_logger):
    """Force fill to dispatch tasks AFTER suspend completes.

    Barrier at acall_signatures: fill loads swarm (not suspended), takes tasks,
    reaches acall_signatures → waits. Suspend completes during wait.
    Fill dispatches tasks on a suspended swarm.
    """
    setup = await create_swarm_item_test_setup(
        num_tasks=10,
        max_concurrency=5,
        stop_after_n_failures=None,
        current_running=0,
        tasks_left_indices=list(range(10)),
        logger=mock_logger,
    )
    swarm = setup.swarm_task

    barrier = asyncio.Barrier(2)

    async def acall_with_barrier(*args, **kwargs):
        await barrier.wait()

    mock_adapter.acall_signatures.side_effect = acall_with_barrier
    lifecycle = AsyncMock(spec=BaseLifecycle)

    async def suspend_then_signal():
        await swarm.suspend()
        await barrier.wait()

    await asyncio.gather(
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
        suspend_then_signal(),
    )

    reloaded = await SwarmTaskSignature.afind_one(swarm.key)
    assert reloaded.task_status.status == SignatureStatus.SUSPENDED
    # Tasks may have been dispatched after suspend — this documents the race
    # (fill doesn't check suspension status before dispatching)


@pytest.mark.asyncio
@pytest.mark.parametrize("iteration", range(10))
async def test_suspend_while_fill_stress(iteration, mock_adapter, mock_task_def, mock_logger):
    """Stress: suspend racing with multiple fills via barrier injection.

    Barrier at acall_signatures (first fill): forces first fill to wait
    while suspend completes. Second fill runs without barrier.
    """
    setup = await create_swarm_item_test_setup(
        num_tasks=10,
        max_concurrency=5,
        stop_after_n_failures=None,
        current_running=0,
        tasks_left_indices=list(range(10)),
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

    async def suspend_then_signal():
        await swarm.suspend()
        await barrier.wait()

    await asyncio.gather(
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
        suspend_then_signal(),
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
    )

    reloaded = await SwarmTaskSignature.afind_one(swarm.key)
    assert reloaded.task_status.status == SignatureStatus.SUSPENDED
    assert reloaded.current_running_tasks >= 0
