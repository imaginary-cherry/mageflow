"""Race Condition 2: Double-Completion (Duplicate Success Callbacks).

THE RACE:
    fill_swarm_running_tasks() loads the swarm (line 56), checks is_swarm_done()
    (line 82) and has_published_callback() (line 81) on the LOCAL object.
    Two concurrent calls can both see done=True, published=False, and both
    call lifecycle.task_success().

HOW IT'S FORCED:
    Unlike double-fill, this race manifests naturally with asyncio.gather() because
    fill_swarm_running_tasks has multiple await points between loading the swarm
    and calling lifecycle.task_success:
      - await fill_running_tasks(...) → internally awaits PublishState.aget, pipeline, etc.
      - await swarm_task.is_swarm_done()

    These await points yield control to the event loop, allowing both coroutines
    to pass the is_swarm_done/has_published_callback checks before either calls
    lifecycle.task_success.

    For extra reliability, we also inject a slow lifecycle.task_success (Test 2b)
    to widen the window.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from thirdmagic.clients.lifecycle import BaseLifecycle
from thirdmagic.swarm.model import SwarmTaskSignature

from mageflow.swarm.workflows import fill_swarm_running_tasks
from tests.unit.workflows.conftest import create_swarm_item_test_setup


async def _create_completed_swarm(mock_logger):
    """Create a swarm where all tasks are done and swarm is closed."""
    setup = await create_swarm_item_test_setup(
        num_tasks=3,
        max_concurrency=3,
        stop_after_n_failures=None,
        current_running=0,
        tasks_left_indices=None,
        finished_indices=[0, 1, 2],
        logger=mock_logger,
    )
    swarm = setup.swarm_task
    await swarm.aupdate(is_swarm_closed=True)
    return swarm


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Known race: both callers see done=True, published=False before either publishes"
)
async def test_double_completion_basic(mock_adapter, mock_task_def, mock_logger):
    """Two concurrent fills on a completed swarm → task_success called multiple times.

    Both coroutines load the swarm, see is_swarm_done()=True and
    has_published_callback()=False (status not yet DONE), and both call
    lifecycle.task_success(). No injection needed — natural await points
    allow interleaving.
    """
    swarm = await _create_completed_swarm(mock_logger)
    lifecycle = AsyncMock(spec=BaseLifecycle)

    await asyncio.gather(
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
    )

    assert lifecycle.task_success.await_count <= 1, (
        f"task_success called {lifecycle.task_success.await_count} times, expected <= 1"
    )


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Known race: slow callback widens the window for duplicate completion"
)
async def test_double_completion_with_slow_callback(mock_adapter, mock_task_def, mock_logger):
    """Delay injection: make task_success slow to widen the race window.

    Even if the first coroutine calls task_success, the status change
    doesn't happen immediately, so the second coroutine still sees
    has_published_callback()=False.
    """
    swarm = await _create_completed_swarm(mock_logger)

    call_count = 0

    async def slow_task_success(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)

    lifecycle = AsyncMock(spec=BaseLifecycle)
    lifecycle.task_success.side_effect = slow_task_success

    await asyncio.gather(
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
        fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger),
    )

    assert call_count <= 1, (
        f"task_success called {call_count} times with delay injection, expected <= 1"
    )


@pytest.mark.asyncio
@pytest.mark.xfail(
    reason="Known race: concurrent fills all call task_success on completed swarm"
)
@pytest.mark.parametrize("iteration", range(10))
async def test_double_completion_stress(iteration, mock_adapter, mock_task_def, mock_logger):
    """Stress: 3 concurrent fills on a completed swarm."""
    swarm = await _create_completed_swarm(mock_logger)
    lifecycle = AsyncMock(spec=BaseLifecycle)

    await asyncio.gather(
        *[
            fill_swarm_running_tasks(swarm.key, None, lifecycle, mock_logger)
            for _ in range(3)
        ]
    )

    assert lifecycle.task_success.await_count <= 1, (
        f"Stress iteration {iteration}: task_success called "
        f"{lifecycle.task_success.await_count} times, expected <= 1"
    )
