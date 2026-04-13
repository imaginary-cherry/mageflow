import asyncio

import pytest

import mageflow
from tests.integration.hatchet.assertions import (
    assert_chain_done,
    assert_redis_is_clean,
    assert_signature_done,
    assert_signature_failed,
    assert_signature_not_called,
    get_runs,
)
from tests.integration.hatchet.conftest import HatchetInitData
from tests.integration.hatchet.models import WorkflowTestMessage
from tests.integration.hatchet.worker import (
    accept_msg_results,
    chain_callback,
    error_callback,
    task3,
    test_dag_wf,
)

pytestmark = pytest.mark.hatchet


async def _cleanup_hook_keys(redis_client):
    """Remove user-hook-* keys written by workflow on_success/on_failure hooks."""
    hook_keys = await redis_client.keys("user-hook-*")
    if hook_keys:
        await redis_client.delete(*hook_keys)


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
        [sign_task1, test_dag_wf, accept_msg_results],
        success=success_cb,
        error=error_cb,
    )
    chain_tasks = await chain_signature.sub_tasks()
    wf_signature = chain_tasks[1]
    accept_msg_results_signature = chain_tasks[2]

    # Act
    await chain_signature.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(12)
    runs = await get_runs(hatchet, ctx_metadata)

    # TODO should be moved to assert chain done once we create an api for data returned from test logs
    wf_info = assert_signature_done(runs, wf_signature, check_called_once=False)
    last_task_info = assert_signature_done(runs, accept_msg_results_signature)

    # Check the next task start only after all workflow is done
    assert wf_info.started_at
    assert wf_info.started_at < last_task_info.started_at

    assert_chain_done(runs, chain_signature, chain_tasks + [success_cb, error_cb])
    assert_signature_not_called(runs, error_cb)
    await _cleanup_hook_keys(redis_client)
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
    dag_sign = await mageflow.asign(
        test_dag_wf, **message.model_dump(mode="json", exclude_unset=True)
    )

    chain_signature = await mageflow.achain(
        [sign_task1, dag_sign, task3],
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

    assert_signature_failed(runs, wf_signature)
    assert_signature_not_called(runs, task3_signature)
    assert_signature_not_called(runs, success_cb)
    assert_signature_done(runs, error_cb)
    await _cleanup_hook_keys(redis_client)
    await assert_redis_is_clean(redis_client)
