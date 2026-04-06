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
from tests.integration.hatchet.models import ContextMessage
from tests.integration.hatchet.worker import (
    chain_test_wf,
    chain_test_wf_fail,
    chain_test_wf_hooks,
    chain_test_wf_hooks_fail,
    error_callback,
    task1_callback,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_signed_workflow_no_hooks_success(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    message = ContextMessage(base_data=test_ctx)

    signature = await mageflow.asign(chain_test_wf)

    # Act
    await signature.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(15)
    runs = await get_runs(hatchet, ctx_metadata)
    assert_signature_done(runs, signature, check_called_once=False)
    await assert_redis_is_clean(redis_client)


@pytest.mark.asyncio(loop_scope="session")
async def test_signed_workflow_no_hooks_failure(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    message = ContextMessage(base_data=test_ctx)

    signature = await mageflow.asign(chain_test_wf_fail)

    # Act
    await signature.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(8)
    runs = await get_runs(hatchet, ctx_metadata)
    assert_signature_failed(runs, signature)
    await assert_redis_is_clean(redis_client)


@pytest.mark.asyncio(loop_scope="session")
async def test_signed_workflow_with_success_callbacks(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    message = ContextMessage(base_data=test_ctx)

    success_cb = await mageflow.asign(task1_callback)
    error_cb = await mageflow.asign(error_callback)
    signature = await mageflow.asign(
        chain_test_wf,
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


@pytest.mark.asyncio(loop_scope="session")
async def test_signed_workflow_with_error_callbacks(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    message = ContextMessage(base_data=test_ctx)

    success_cb = await mageflow.asign(task1_callback)
    error_cb = await mageflow.asign(error_callback)
    signature = await mageflow.asign(
        chain_test_wf_fail,
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


@pytest.mark.asyncio(loop_scope="session")
async def test_signed_workflow_with_hooks_success(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    message = ContextMessage(base_data=test_ctx)

    signature = await mageflow.asign(chain_test_wf_hooks)

    # Act
    await signature.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(8)
    runs = await get_runs(hatchet, ctx_metadata)
    assert_signature_done(runs, signature, check_called_once=False)
    await assert_redis_is_clean(redis_client)


@pytest.mark.asyncio(loop_scope="session")
async def test_signed_workflow_with_hooks_failure(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    message = ContextMessage(base_data=test_ctx)

    signature = await mageflow.asign(chain_test_wf_hooks_fail)

    # Act
    await signature.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(8)
    runs = await get_runs(hatchet, ctx_metadata)
    assert_signature_failed(runs, signature)
    await assert_redis_is_clean(redis_client)
