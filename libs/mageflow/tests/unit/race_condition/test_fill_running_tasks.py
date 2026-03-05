import asyncio
from unittest.mock import patch

import pytest

import mageflow
from mageflow.swarm.workflows import fill_running_tasks
from tests.integration.hatchet.models import ContextMessage
from thirdmagic.swarm.model import SwarmTaskSignature


@pytest.mark.asyncio
async def test_aio_run_in_swarm_kwargs_set_before_fill_running_tasks(
    empty_swarm, mock_task_def, mock_adapter
):
    swarm = empty_swarm
    task = await mageflow.asign("item_task", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"key": "value"}, more_context={"extra": "data"})

    tasks_added = asyncio.Event()
    fill_done = asyncio.Event()
    original_add_tasks = SwarmTaskSignature.add_tasks

    async def add_tasks_with_sync(self, tasks, close_on_max_task=True):
        result = await original_add_tasks(self, tasks, close_on_max_task)
        tasks_added.set()  # Tasks are in Redis now
        await fill_done.wait()  # Hold here until fill_running_tasks finishes
        return result

    async def fill_after_tasks_added():
        await tasks_added.wait()  # Wait for tasks to be in Redis
        result = await fill_running_tasks(swarm)
        fill_done.set()  # Let aio_run_in_swarm continue to kwargs pipeline
        return result

    with patch.object(SwarmTaskSignature, "add_tasks", add_tasks_with_sync):
        await asyncio.gather(
            swarm.aio_run_in_swarm(task, msg),
            fill_after_tasks_added(),
        )

    # Assert: tasks passed to acall_signatures should have per-task kwargs
    call_args = mock_adapter.acall_signatures.call_args
    assert not call_args, "Swarm added tasks before tasks were filled and updated"
