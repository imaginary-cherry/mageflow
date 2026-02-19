import asyncio

import pytest

from tests.integration.hatchet.assertions import get_runs
from tests.integration.hatchet.conftest import HatchetInitData


@pytest.mark.asyncio(loop_scope="session")
async def test_swarm_fill_running_tasks_with_failed_task(
    hatchet_client_init: HatchetInitData, ctx_metadata, trigger_options, sign_task1
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )

    swarm = await hatchet.aswarm(
        tasks=(await sign_task1.aduplicate_many(5)), is_swarm_closed=True
    )

    # Act
    # Call many afill swarm
    await asyncio.gather(
        swarm.ClientAdapter.afill_swarm(swarm, max_tasks=1, options=trigger_options),
        swarm.ClientAdapter.afill_swarm(swarm, max_tasks=1, options=trigger_options),
        swarm.ClientAdapter.afill_swarm(swarm, max_tasks=1, options=trigger_options),
    )
    await asyncio.sleep(13)

    # Assert
    runs = await get_runs(hatchet, ctx_metadata)
    logs = await asyncio.gather(
        *[hatchet.logs.aio_list(task_run_id=wf.task_external_id) for wf in runs]
    )
