"""Race Condition 6: Double-Finish (Idempotency).

THE (NON-)RACE:
    Two finish_task() calls for the same task → each enters apipeline() which
    does a FRESH read from Redis. The second call sees the task already in
    finished_tasks and returns early. NUMINCRBY(-1) only happens once.

WHY IT'S SAFE:
    apipeline().__aenter__ calls aget(self.key) which loads the latest Redis state.
    The idempotency check `if task_key in swarm_task.finished_tasks` uses this
    fresh state. The pipeline transaction ensures atomicity.

    Expected: ALL tests PASS.
"""

import asyncio

import pytest
from thirdmagic.swarm.model import SwarmTaskSignature

from tests.unit.race_conditions.conftest import assert_swarm_invariants
from tests.unit.workflows.conftest import create_swarm_item_test_setup


@pytest.mark.asyncio
async def test_double_finish_idempotent(mock_adapter, mock_task_def, mock_logger):
    """Two concurrent finish_task calls for the same task: only one decrement."""
    setup = await create_swarm_item_test_setup(
        num_tasks=3,
        max_concurrency=3,
        stop_after_n_failures=None,
        current_running=1,
        tasks_left_indices=[1, 2],
        logger=mock_logger,
    )
    swarm = setup.swarm_task
    task = setup.tasks[0]

    await asyncio.gather(
        swarm.finish_task(task.key, {"result": "first"}),
        swarm.finish_task(task.key, {"result": "second"}),
    )

    reloaded = await assert_swarm_invariants(swarm)

    finished = list(reloaded.finished_tasks)
    assert finished.count(task.key) == 1, (
        f"Task appears {finished.count(task.key)} times in finished_tasks"
    )
    assert reloaded.current_running_tasks == 0
    assert len(list(reloaded.tasks_results)) == 1


@pytest.mark.asyncio
async def test_double_finish_different_tasks(mock_adapter, mock_task_def, mock_logger):
    """Two concurrent finishes for different tasks: both succeed."""
    setup = await create_swarm_item_test_setup(
        num_tasks=3,
        max_concurrency=3,
        stop_after_n_failures=None,
        current_running=2,
        tasks_left_indices=[2],
        logger=mock_logger,
    )
    swarm = setup.swarm_task

    await asyncio.gather(
        swarm.finish_task(setup.tasks[0].key, {"result": "task_0"}),
        swarm.finish_task(setup.tasks[1].key, {"result": "task_1"}),
    )

    reloaded = await assert_swarm_invariants(swarm)
    finished = list(reloaded.finished_tasks)
    assert setup.tasks[0].key in finished
    assert setup.tasks[1].key in finished
    assert reloaded.current_running_tasks == 0
    assert len(list(reloaded.tasks_results)) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("iteration", range(20))
async def test_double_finish_stress(iteration, mock_adapter, mock_task_def, mock_logger):
    """Stress: 5 concurrent finish calls for the same task."""
    setup = await create_swarm_item_test_setup(
        num_tasks=3,
        max_concurrency=3,
        stop_after_n_failures=None,
        current_running=1,
        tasks_left_indices=[1, 2],
        logger=mock_logger,
    )
    swarm = setup.swarm_task
    task = setup.tasks[0]

    await asyncio.gather(
        *[swarm.finish_task(task.key, {"result": f"attempt_{i}"}) for i in range(5)]
    )

    reloaded = await assert_swarm_invariants(swarm)
    assert list(reloaded.finished_tasks).count(task.key) == 1
    assert reloaded.current_running_tasks == 0
