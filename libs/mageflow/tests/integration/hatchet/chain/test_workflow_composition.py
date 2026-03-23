import asyncio

import pytest
from thirdmagic.task import TaskSignature

import mageflow
from tests.integration.hatchet.assertions import (
    assert_chain_done,
    assert_redis_is_clean,
    assert_signature_done,
    assert_signature_failed,
    get_runs,
    map_wf_by_id,
)
from tests.integration.hatchet.conftest import HatchetInitData
from tests.integration.hatchet.models import ContextMessage
from tests.integration.hatchet.worker import (
    chain_test_wf,
    chain_test_wf_fail,
    chain_test_wf_hooks,
    chain_test_wf_hooks_fail,
    error_callback,
    task2,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_in_chain_no_hooks_success(
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

    wf_sig = await mageflow.asign(chain_test_wf)
    task2_sig = await mageflow.asign(task2)

    # Act
    chain_signature = await mageflow.achain([wf_sig, task2_sig])
    chain_tasks = await TaskSignature.afind()

    await chain_signature.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(15)
    runs = await get_runs(hatchet, ctx_metadata)

    assert_chain_done(
        runs,
        chain_signature,
        chain_tasks,
        check_callbacks=False,
    )

    assert_signature_done(runs, wf_sig, check_called_once=False)
    assert_signature_done(runs, task2_sig, check_called_once=False)

    # Check redis is clean
    await assert_redis_is_clean(redis_client)


@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_in_chain_no_hooks_failure(
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

    wf_sig = await mageflow.asign(chain_test_wf_fail)
    task2_sig = await mageflow.asign(task2)
    error_cb_sig = await mageflow.asign(error_callback)

    # Act
    chain_signature = await mageflow.achain(
        [wf_sig, task2_sig],
        error=error_cb_sig,
    )

    await chain_signature.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(15)
    runs = await get_runs(hatchet, ctx_metadata)

    # Workflow step should have failed
    assert_signature_failed(runs, wf_sig)

    # task2 should NOT have been called (chain stops on failure)
    wf_by_id = map_wf_by_id(runs, also_not_done=True)
    assert task2_sig.key not in wf_by_id, (
        f"task2 was called even though the chain step failed"
    )

    # Error callback should have been called
    assert_signature_done(runs, error_cb_sig, check_called_once=True)

    # Check redis is clean
    await assert_redis_is_clean(redis_client)


@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_in_chain_with_hooks_success(
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

    wf_sig = await mageflow.asign(chain_test_wf_hooks)
    task2_sig = await mageflow.asign(task2)

    # Act
    chain_signature = await mageflow.achain([wf_sig, task2_sig])
    chain_tasks = await TaskSignature.afind()

    await chain_signature.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(15)
    runs = await get_runs(hatchet, ctx_metadata)

    # Chain should have completed — both sub-tasks done
    assert_chain_done(
        runs,
        chain_signature,
        chain_tasks,
        check_callbacks=False,
    )

    assert_signature_done(runs, wf_sig, check_called_once=False)
    assert_signature_done(runs, task2_sig, check_called_once=False)

    # Check redis is clean (user-hook-success key should have expired or been cleaned)
    await assert_redis_is_clean(redis_client)


@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_in_chain_with_hooks_failure(
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

    wf_sig = await mageflow.asign(chain_test_wf_hooks_fail)
    task2_sig = await mageflow.asign(task2)
    error_cb_sig = await mageflow.asign(error_callback)

    # Act
    chain_signature = await mageflow.achain(
        [wf_sig, task2_sig],
        error=error_cb_sig,
    )

    await chain_signature.aio_run_no_wait(message, options=trigger_options)

    # Assert
    await asyncio.sleep(15)
    runs = await get_runs(hatchet, ctx_metadata)

    # Workflow step should have failed
    assert_signature_failed(runs, wf_sig)

    # task2 should NOT have been called (chain stops on failure)
    wf_by_id = map_wf_by_id(runs, also_not_done=True)
    assert task2_sig.key not in wf_by_id, (
        f"task2 was called even though the chain step failed"
    )

    # Error callback should have been called (proving chain error handling activated)
    assert_signature_done(runs, error_cb_sig, check_called_once=True)

    # Check redis is clean
    await assert_redis_is_clean(redis_client)
