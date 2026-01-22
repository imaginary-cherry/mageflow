import pytest_asyncio

import mageflow
from mageflow.swarm.model import SwarmConfig, SwarmTaskSignature
from tests.integration.hatchet.models import ContextMessage


@pytest_asyncio.fixture
async def empty_swarm():
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=2),
        is_swarm_closed=False,
    )
    yield swarm_task


@pytest_asyncio.fixture
async def swarm_task(empty_swarm: SwarmTaskSignature):
    swarm_task = empty_swarm
    task = await mageflow.sign("item_task")
    await swarm_task.add_task(task)
    return swarm_task


@pytest_asyncio.fixture
async def swarm_with_ready_task(swarm_task: SwarmTaskSignature):
    await swarm_task.tasks_left_to_run.aappend(swarm_task.tasks[0])
    yield swarm_task
