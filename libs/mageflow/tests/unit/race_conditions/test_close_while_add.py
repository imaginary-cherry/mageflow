"""Race Condition 5: Close-While-Add.

THE RACE:
    add_tasks() does NOT check is_swarm_closed before adding tasks.
    Tasks can be added to a closed swarm, causing is_swarm_done() to never return
    True (the newly added tasks are never finished).

HOW IT'S DEMONSTRATED:
    This race doesn't require injection — it's a missing guard, not a timing issue.
    The sequential test (close then add) reliably demonstrates that add_tasks
    succeeds on a closed swarm, breaking the completion check.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from thirdmagic.swarm.model import SwarmTaskSignature

import mageflow
from tests.integration.hatchet.models import ContextMessage
from tests.unit.race_conditions.conftest import assert_swarm_invariants
from tests.unit.workflows.conftest import create_swarm_item_test_setup


@pytest.mark.asyncio
async def test_close_while_add_concurrent(mock_adapter, mock_task_def, mock_logger):
    """Concurrent close and add_tasks — state should be consistent."""
    setup = await create_swarm_item_test_setup(
        num_tasks=3,
        max_concurrency=10,
        stop_after_n_failures=None,
        current_running=0,
        tasks_left_indices=[0, 1, 2],
        logger=mock_logger,
    )
    swarm = setup.swarm_task

    new_tasks = [
        await mageflow.asign(f"late_task_{i}", model_validators=ContextMessage)
        for i in range(3)
    ]

    results = await asyncio.gather(
        swarm.close_swarm(),
        swarm.add_tasks(new_tasks),
        return_exceptions=True,
    )

    reloaded = await SwarmTaskSignature.afind_one(swarm.key)
    assert reloaded.is_swarm_closed is True

    add_result = results[1]
    if not isinstance(add_result, Exception):
        for task in new_tasks:
            assert task.key in list(reloaded.tasks)

    await assert_swarm_invariants(swarm)


@pytest.mark.asyncio
async def test_close_then_add_sequential(mock_adapter, mock_task_def, mock_logger):
    """Sequential close then add demonstrates the missing guard.

    add_tasks() doesn't check is_swarm_closed, so tasks are added after close.
    This means is_swarm_done() returns False because the new tasks aren't finished,
    but no more fill cycles will pick them up → swarm hangs.
    """
    setup = await create_swarm_item_test_setup(
        num_tasks=3,
        max_concurrency=10,
        stop_after_n_failures=None,
        current_running=0,
        tasks_left_indices=[0, 1, 2],
        logger=mock_logger,
    )
    swarm = setup.swarm_task

    await swarm.close_swarm()

    reloaded = await SwarmTaskSignature.afind_one(swarm.key)
    assert reloaded.is_swarm_closed is True

    # add_tasks succeeds even though swarm is closed — this is the bug
    new_tasks = [
        await mageflow.asign(f"late_task_{i}", model_validators=ContextMessage)
        for i in range(2)
    ]
    await swarm.add_tasks(new_tasks)

    reloaded = await SwarmTaskSignature.afind_one(swarm.key)
    assert len(reloaded.tasks) == 5

    # Swarm can never complete: closed but has unfinished tasks added after close
    is_done = await reloaded.is_swarm_done()
    assert is_done is False


@pytest.mark.asyncio
@pytest.mark.parametrize("iteration", range(10))
async def test_close_while_add_stress(iteration, mock_adapter, mock_task_def, mock_logger):
    """Stress: concurrent close and multiple add operations."""
    setup = await create_swarm_item_test_setup(
        num_tasks=3,
        max_concurrency=10,
        stop_after_n_failures=None,
        current_running=0,
        tasks_left_indices=[0, 1, 2],
        logger=mock_logger,
    )
    swarm = setup.swarm_task

    batches = []
    for b in range(3):
        batch = [
            await mageflow.asign(f"batch{b}_task_{i}", model_validators=ContextMessage)
            for i in range(2)
        ]
        batches.append(batch)

    results = await asyncio.gather(
        swarm.close_swarm(),
        swarm.add_tasks(batches[0]),
        swarm.add_tasks(batches[1]),
        swarm.add_tasks(batches[2]),
        return_exceptions=True,
    )

    reloaded = await SwarmTaskSignature.afind_one(swarm.key)
    assert reloaded.is_swarm_closed is True
    await assert_swarm_invariants(swarm)
