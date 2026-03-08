import asyncio

import pytest

import mageflow
from tests.integration.hatchet.assertions import (
    assert_signature_done,
    assert_swarm_task_done,
    get_runs,
)
from tests.integration.hatchet.conftest import HatchetInitData
from tests.integration.hatchet.models import ContextMessage
from tests.integration.hatchet.worker import task1, timeout_task
from thirdmagic.swarm.model import SwarmConfig
from thirdmagic.task import TaskSignature


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
    swarm = await mageflow.aswarm(
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


@pytest.mark.asyncio(loop_scope="session")
async def test__swarm_with_corrupted_callback_input_validator__checks_it_receives_full_msg(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
    sign_task1,
    sign_callback1,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )

    results = "results"
    swarm_tasks = [sign_task1]
    swarm = await mageflow.aswarm(
        tasks=swarm_tasks,
        success_callbacks=[sign_callback1],
        kwargs={"param1": "nice", "param2": ["test", 2]},
        is_swarm_closed=True,
    )
    async with swarm.apipeline():
        await sign_callback1.aupdate(model_validators=None)
        swarm.finished_tasks.extend(swarm.tasks)
        swarm.tasks_results.append(results)

    reloaded_callback1 = await TaskSignature.aget(sign_callback1.key)
    assert reloaded_callback1.model_validators is None

    # Act
    from hatchet_sdk.runnables.contextvars import ctx_additional_metadata

    add_metadata = ctx_additional_metadata.get() or {}
    add_metadata.update(ctx_metadata)
    ctx_additional_metadata.set(add_metadata)

    await swarm.close_swarm()
    await asyncio.sleep(10)

    # Assert
    runs = await get_runs(hatchet, ctx_metadata)
    assert_signature_done(runs, sign_callback1, task_result=[results])
