import asyncio

import pytest
from hatchet_sdk.clients.rest import V1TaskStatus

from tests.integration.hatchet.assertions import (
    assert_logs_dont_overlap,
    get_specific_refs,
)
from tests.integration.hatchet.conftest import HatchetInitData


@pytest.mark.asyncio(loop_scope="session")
async def test__fill_swarm_workflow_is_locked(
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
    task_refs = await asyncio.gather(
        swarm.ClientAdapter.afill_swarm(swarm, max_tasks=1, options=trigger_options),
        swarm.ClientAdapter.afill_swarm(swarm, max_tasks=1, options=trigger_options),
        swarm.ClientAdapter.afill_swarm(swarm, max_tasks=1, options=trigger_options),
        swarm.ClientAdapter.afill_swarm(swarm, max_tasks=1, options=trigger_options),
    )
    await asyncio.sleep(8)

    # Assert
    runs = await get_specific_refs(hatchet, task_refs)
    # Check only 2 where running
    done_runs = [run for run in runs if run.status == V1TaskStatus.COMPLETED]
    assert len(done_runs) == 2
    logs = await asyncio.gather(
        *[hatchet.logs.aio_list(task_run_id=wf.task_external_id) for wf in done_runs]
    )
    assert_logs_dont_overlap(logs)
