"""Shared fixtures and invariant checker for race condition tests.

## How Race Conditions Are Forced

With single-threaded asyncio and fakeredis (which completes awaits synchronously),
coroutines rarely interleave at the critical points. To force interleaving, we
inject `asyncio.Barrier(N)` at strategic points via monkey-patching:

1. Identify the critical READ (stale snapshot) and WRITE (pipeline commit) phases
2. Inject a barrier between them so N coroutines all complete their reads before
   any of them write
3. After the barrier releases, both writes execute with stale data → race manifests

### Key insight about rapyer pipelines:
- `async with obj.apipeline()` does a FRESH read from Redis at entry
- `RedisInt += N` inside a pipeline queues `NUMINCRBY` (relative increment)
- `RedisInt += N` OUTSIDE a pipeline only updates local Python state
- Reads outside pipelines use the local object snapshot (potentially stale)

### Common injection points:
- `acall_signatures`: Between fill_running_tasks' first pipeline (takes tasks)
  and second pipeline (increments current_running_tasks). Both coroutines have
  already calculated slots from stale data.
- `is_swarm_done`: Between loading the swarm and checking completion status.
  Both coroutines see the same completion state before either publishes callback.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from thirdmagic.clients.lifecycle import BaseLifecycle
from thirdmagic.swarm.model import SwarmTaskSignature


async def assert_swarm_invariants(swarm_task: SwarmTaskSignature):
    """
    Validate core swarm invariants after concurrent operations.

    Reloads the swarm from Redis to get the latest state.
    """
    reloaded = await SwarmTaskSignature.afind_one(swarm_task.key)
    assert reloaded is not None, "Swarm should still exist"

    # current_running_tasks >= 0
    assert (
        reloaded.current_running_tasks >= 0
    ), f"current_running_tasks is negative: {reloaded.current_running_tasks}"

    # current_running_tasks <= max_concurrency
    assert reloaded.current_running_tasks <= reloaded.config.max_concurrency, (
        f"current_running_tasks ({reloaded.current_running_tasks}) exceeds "
        f"max_concurrency ({reloaded.config.max_concurrency})"
    )

    # No duplicates in finished_tasks
    finished = list(reloaded.finished_tasks)
    assert len(finished) == len(
        set(finished)
    ), f"Duplicate entries in finished_tasks: {finished}"

    # No duplicates in failed_tasks
    failed = list(reloaded.failed_tasks)
    assert len(failed) == len(
        set(failed)
    ), f"Duplicate entries in failed_tasks: {failed}"

    # No task in both finished and failed
    overlap = set(finished) & set(failed)
    assert not overlap, f"Tasks in both finished and failed: {overlap}"

    # finished_tasks, failed_tasks are subsets of tasks
    all_tasks = set(reloaded.tasks)
    assert (
        set(finished) <= all_tasks
    ), f"finished_tasks contains unknown tasks: {set(finished) - all_tasks}"
    assert (
        set(failed) <= all_tasks
    ), f"failed_tasks contains unknown tasks: {set(failed) - all_tasks}"

    # tasks_left_to_run is subset of tasks
    left = set(reloaded.tasks_left_to_run)
    assert (
        left <= all_tasks
    ), f"tasks_left_to_run contains unknown tasks: {left - all_tasks}"

    return reloaded


def barrier_on_mock(mock_obj: AsyncMock, method_name: str, barrier: asyncio.Barrier):
    """Set side_effect on a mock method to wait at a barrier before returning.

    This forces N concurrent callers to synchronize at this point.
    Use this to inject interleaving between a stale-read phase and a write phase.
    """

    async def wait_at_barrier(*args, **kwargs):
        await barrier.wait()

    getattr(mock_obj, method_name).side_effect = wait_at_barrier


@pytest.fixture
def mock_lifecycle():
    return AsyncMock(spec=BaseLifecycle)
