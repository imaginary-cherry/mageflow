import asyncio

import pytest

import mageflow
from tests.integration.hatchet.assertions import (
    assert_redis_is_clean,
    assert_signature_done,
    assert_signature_failed,
    assert_signature_not_called,
    get_runs,
)
from tests.integration.hatchet.conftest import HatchetInitData
from tests.integration.hatchet.models import WorkflowTestMessage
from tests.integration.hatchet.worker import (
    chain_callback,
    error_callback,
    task3,
    test_dag_wf,
)

pytestmark = pytest.mark.hatchet


@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_in_chain_success(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
    sign_task1,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    message = WorkflowTestMessage(base_data=test_ctx)

    success_cb = await mageflow.asign(chain_callback)
    error_cb = await mageflow.asign(error_callback)

    chain_signature = await mageflow.achain(
        [sign_task1, test_dag_wf, task3],
        success=success_cb,
        error=error_cb,
    )
    chain_tasks = await chain_signature.sub_tasks()
    wf_signature = chain_tasks[1]
    task3_signature = chain_tasks[2]

    # Act
    await chain_signature.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(12)
    runs = await get_runs(hatchet, ctx_metadata)

    # TODO should be moved to assert chaind done once we create an api for data returned from test logs
    assert_signature_done(runs, sign_task1)
    assert_signature_done(runs, wf_signature, check_called_once=False)
    assert_signature_done(runs, task3_signature)
    assert_signature_done(runs, success_cb)
    assert_signature_not_called(runs, error_cb)
    await assert_redis_is_clean(redis_client)


@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_in_chain_failure(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
    sign_task1,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    message = WorkflowTestMessage(base_data=test_ctx, fail_at_step=2)

    success_cb = await mageflow.asign(chain_callback)
    error_cb = await mageflow.asign(error_callback)

    chain_signature = await mageflow.achain(
        [sign_task1, test_dag_wf, task3],
        success=success_cb,
        error=error_cb,
    )
    chain_tasks = await chain_signature.sub_tasks()
    wf_signature = chain_tasks[1]
    task3_signature = chain_tasks[2]

    # Act
    await chain_signature.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(15)
    runs = await get_runs(hatchet, ctx_metadata)

    assert_signature_done(runs, sign_task1)
    assert_signature_failed(runs, wf_signature)
    assert_signature_not_called(runs, task3_signature)
    assert_signature_not_called(runs, success_cb)
    assert_signature_done(runs, error_cb)
    await assert_redis_is_clean(redis_client)
