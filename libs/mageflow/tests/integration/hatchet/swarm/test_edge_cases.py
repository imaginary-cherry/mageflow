import asyncio

import pytest

import mageflow
from mageflow.signature.model import TaskSignature
from mageflow.swarm.model import SwarmConfig
from tests.integration.hatchet.assertions import get_runs, assert_swarm_task_done
from tests.integration.hatchet.conftest import HatchetInitData
from tests.integration.hatchet.models import ContextMessage
from tests.integration.hatchet.worker import timeout_task, task1


@pytest.mark.asyncio(loop_scope="session")
async def test__sub_task_is_cancelled__swarm_still_finish(
    hatchet_client_init: HatchetInitData, ctx_metadata, trigger_options
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    swarm_tasks = [timeout_task]
    swarm = await mageflow.swarm(
        tasks=swarm_tasks, config=SwarmConfig(max_concurrency=1)
    )

    # Act
    regular_message = ContextMessage()
    for i in range(2):
        await swarm.aio_run_in_swarm(task1, regular_message, options=trigger_options)
    await swarm.close_swarm()
    tasks = await TaskSignature.afind(*swarm.tasks)
    await asyncio.sleep(15)

    # Assert
    runs = await get_runs(hatchet, ctx_metadata)

    # Check swarm callback was called
    assert_swarm_task_done(runs, swarm, tasks)
