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
    error_callback,
    task1_callback,
    test_dag_wf,
    test_dag_wf_hooks,
)

pytestmark = pytest.mark.hatchet

WORKFLOW_PARAMS = pytest.mark.parametrize(
    "workflow",
    [
        pytest.param(test_dag_wf, id="no_hooks"),
        pytest.param(test_dag_wf_hooks, id="with_hooks"),
    ],
)


@WORKFLOW_PARAMS
@pytest.mark.asyncio(loop_scope="session")
async def test_signed_dag_workflow_success(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
    workflow,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    message = WorkflowTestMessage(base_data=test_ctx)

    signature = await mageflow.asign(workflow)

    # Act
    await signature.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(8)
    runs = await get_runs(hatchet, ctx_metadata)
    assert_signature_done(runs, signature, check_called_once=False)
    await assert_redis_is_clean(redis_client)


@WORKFLOW_PARAMS
@pytest.mark.asyncio(loop_scope="session")
async def test_signed_dag_workflow_failure(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
    workflow,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    message = WorkflowTestMessage(base_data=test_ctx, fail_at_step=2)

    signature = await mageflow.asign(workflow)

    # Act
    await signature.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(8)
    runs = await get_runs(hatchet, ctx_metadata)
    assert_signature_failed(runs, signature)
    await assert_redis_is_clean(redis_client)


@WORKFLOW_PARAMS
@pytest.mark.asyncio(loop_scope="session")
async def test_signed_dag_workflow_with_success_callbacks(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
    workflow,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    message = WorkflowTestMessage(base_data=test_ctx)

    success_cb = await mageflow.asign(task1_callback)
    error_cb = await mageflow.asign(error_callback)
    signature = await mageflow.asign(
        workflow,
        success_callbacks=[success_cb],
        error_callbacks=[error_cb],
    )

    # Act
    await signature.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(8)
    runs = await get_runs(hatchet, ctx_metadata)
    assert_signature_done(runs, signature, check_called_once=False)
    assert_signature_done(runs, success_cb)
    assert_signature_not_called(runs, error_cb)
    await assert_redis_is_clean(redis_client)


@WORKFLOW_PARAMS
@pytest.mark.asyncio(loop_scope="session")
async def test_signed_dag_workflow_with_error_callbacks(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
    workflow,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    message = WorkflowTestMessage(base_data=test_ctx, fail_at_step=2)

    success_cb = await mageflow.asign(task1_callback)
    error_cb = await mageflow.asign(error_callback)
    signature = await mageflow.asign(
        workflow,
        error_callbacks=[error_cb],
        success_callbacks=[success_cb],
    )

    # Act
    await signature.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(8)
    runs = await get_runs(hatchet, ctx_metadata)
    assert_signature_done(runs, error_cb)
    assert_signature_not_called(runs, success_cb)
    await assert_redis_is_clean(redis_client)
