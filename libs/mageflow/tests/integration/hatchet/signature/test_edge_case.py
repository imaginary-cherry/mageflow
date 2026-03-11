import asyncio
from datetime import datetime

import pytest
from hatchet_sdk import NonRetryableException
from hatchet_sdk.clients.rest import V1TaskStatus
from hatchet_sdk.runnables.workflow import Standalone
from thirdmagic.signature import SignatureStatus
from thirdmagic.task import TaskSignature

import mageflow
from tests.integration.hatchet.assertions import (
    assert_signature_done,
    assert_signature_failed,
    assert_signature_not_called,
    assert_task_was_paused,
    get_runs,
    map_wf_by_id,
)
from tests.integration.hatchet.conftest import HatchetInitData
from tests.integration.hatchet.models import ContextMessage, MageflowTestError
from tests.integration.hatchet.worker import (
    cancel_retry,
    error_callback,
    fail_task,
    normal_retry_once,
    retry_once,
    retry_timeout_task,
    task1_callback,
    timeout_task,
)


@pytest.mark.asyncio(loop_scope="session")
async def test__timeout_task__call_error_callback(
    hatchet_client_init: HatchetInitData, test_ctx, ctx_metadata, trigger_options
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    error_sign = await mageflow.asign(error_callback)
    timeout_sign = await mageflow.asign(timeout_task, error_callbacks=[error_sign])
    message = ContextMessage(base_data=test_ctx)
    expected_task_input = message.model_dump(mode="json", exclude_unset=True)

    # Act
    await timeout_sign.aio_run_no_wait(message, options=trigger_options)
    await asyncio.sleep(5)

    # Assert
    runs = await get_runs(hatchet, ctx_metadata)
    assert_signature_done(runs, error_sign, **expected_task_input)
    map_runs = map_wf_by_id(runs)
    timeout_task_summary = map_runs[timeout_sign.key]
    assert timeout_task_summary.retry_count == 0

    # Check signature has failed
    reloaded_sign = await TaskSignature.aget(timeout_sign.key)
    assert reloaded_sign.task_status.status == SignatureStatus.FAILED


@pytest.mark.asyncio(loop_scope="session")
async def test__retry_once_with_callbacks__success_callback_called_error_callback_not_edge_case(
    hatchet_client_init: HatchetInitData, test_ctx, ctx_metadata, trigger_options
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )

    error_callback_sign = await mageflow.asign(error_callback)
    success_callback_sign = await mageflow.asign(task1_callback)
    retry_once_sign = await mageflow.asign(
        retry_once,
        error_callbacks=[error_callback_sign],
        success_callbacks=[success_callback_sign],
    )
    message = ContextMessage(base_data=test_ctx)

    # Act
    await retry_once_sign.aio_run_no_wait(message, options=trigger_options)
    await asyncio.sleep(6)

    # Assert
    runs = await get_runs(hatchet, ctx_metadata)
    assert_signature_done(runs, retry_once_sign, base_data=test_ctx)
    assert_signature_done(runs, success_callback_sign, task_result="Nice")
    assert_signature_not_called(runs, error_callback_sign)


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize(
    ["retry_task", "wait_time", "retries"],
    [
        [retry_to_failure, 6, 3],
        [retry_timeout_task, 15, 2],
    ],
)
async def test__retry_to_failure_with_error_callback__error_callback_called_once_after_retries_edge_case(
    hatchet_client_init: HatchetInitData,
    test_ctx,
    ctx_metadata,
    trigger_options,
    retry_task: Standalone,
    wait_time: float,
    retries: int,
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )

    message = ContextMessage(base_data=test_ctx)
    error_callback_sign = await mageflow.asign(error_callback)
    retry_to_failure_sign = await mageflow.asign(
        retry_task, error_callbacks=[error_callback_sign]
    )

    # Act
    await retry_to_failure_sign.aio_run_no_wait(message, options=trigger_options)
    await asyncio.sleep(wait_time)

    # Assert
    runs = await get_runs(hatchet, ctx_metadata)
    failed_summary = assert_signature_failed(runs, retry_to_failure_sign)
    assert failed_summary.retry_count == retries
    assert_signature_done(runs, error_callback_sign, base_data=test_ctx)

    # Verify error callback was called only once after all retries
    finish_retry_time = await redis_client.get(
        f"finish-{retry_to_failure_sign.key}-{retries + 1}"
    )
    finish_retry_time = datetime.fromisoformat(finish_retry_time)
    wf_by_task_id = map_wf_by_id(runs, also_not_done=True)
    error_callback_run = wf_by_task_id[error_callback_sign.key]
    callback_start_time = error_callback_run.task_inserted_at
    finish_retry_time = finish_retry_time.astimezone(callback_start_time.tzinfo)
    assert (
        callback_start_time > finish_retry_time
    ), "Error callback should be called after retry task starts"


@pytest.mark.asyncio(loop_scope="session")
async def test__retry_but_override_with_exception__check_error_callback_is_called(
    hatchet_client_init: HatchetInitData, test_ctx, ctx_metadata, trigger_options
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )

    error_callback_sign = await mageflow.asign(error_callback)
    message = ContextMessage(base_data=test_ctx)
    cancel_retry_sign = await mageflow.asign(
        cancel_retry, error_callbacks=[error_callback_sign]
    )

    # Act
    await cancel_retry_sign.aio_run_no_wait(message, options=trigger_options)
    await asyncio.sleep(4)

    # Assert
    runs = await get_runs(hatchet, ctx_metadata)
    failed_summary = assert_signature_failed(runs, cancel_retry_sign)
    assert failed_summary.retry_count == 0
    assert_signature_done(runs, error_callback_sign, base_data=test_ctx)


@pytest.mark.asyncio(loop_scope="session")
async def test_check_normal_task_fails__sanity(
    hatchet_client_init: HatchetInitData, test_ctx, ctx_metadata, trigger_options
):
    # Arrange
    hatchet = hatchet_client_init.hatchet

    # Act
    message = ContextMessage(base_data=test_ctx)
    await fail_task.aio_run_no_wait(message, options=trigger_options)
    await asyncio.sleep(3)

    # Assert
    runs = await get_runs(hatchet, ctx_metadata)

    assert len(runs) == 1
    failed_task_summary = runs[0]
    assert failed_task_summary.status == V1TaskStatus.FAILED
    error_class_name = MageflowTestError.__name__
    err_msg = failed_task_summary.error_message
    assert err_msg.startswith(
        error_class_name
    ), f"{err_msg} doesn't start with {error_class_name}"


@pytest.mark.asyncio(loop_scope="session")
async def test_retry_normal_tasks__sanity(
    hatchet_client_init: HatchetInitData, test_ctx, ctx_metadata, trigger_options
):
    # Arrange
    hatchet = hatchet_client_init.hatchet

    # Act
    message = ContextMessage(base_data=test_ctx)
    await normal_retry_once.aio_run_no_wait(message, options=trigger_options)
    await asyncio.sleep(5)

    # Assert
    runs = await get_runs(hatchet, ctx_metadata)

    assert len(runs) == 1
    retry_task_summary = runs[0]
    assert retry_task_summary.status == V1TaskStatus.COMPLETED
    assert retry_task_summary.retry_count == 1
    assert retry_task_summary.output == message.model_dump(mode="json")


@pytest.mark.asyncio(loop_scope="session")
async def test_cancel_task_output__sanity(
    hatchet_client_init: HatchetInitData, test_ctx, ctx_metadata, trigger_options
):
    # Arrange
    hatchet = hatchet_client_init.hatchet

    # Act
    message = ContextMessage(base_data=test_ctx)
    await cancel_retry.aio_run_no_wait(message, options=trigger_options)
    await asyncio.sleep(5)

    # Assert
    runs = await get_runs(hatchet, ctx_metadata)

    assert len(runs) == 1
    cancel_task_summary = runs[0]
    assert cancel_task_summary.status == V1TaskStatus.FAILED
    assert cancel_task_summary.retry_count == 0
    assert NonRetryableException.__name__ in cancel_task_summary.error_message


@pytest.mark.asyncio(loop_scope="session")
async def test_timeout_task_output__sanity(
    hatchet_client_init: HatchetInitData, test_ctx, ctx_metadata, trigger_options
):
    # Arrange
    hatchet = hatchet_client_init.hatchet

    # Act
    message = ContextMessage(base_data=test_ctx)
    await timeout_task.aio_run_no_wait(message, options=trigger_options)
    await asyncio.sleep(5)

    # Assert
    runs = await get_runs(hatchet, ctx_metadata)

    assert len(runs) == 1
    timeout_task_summary = runs[0]
    assert timeout_task_summary.status == V1TaskStatus.FAILED
    # No error message
    assert not timeout_task_summary.error_message


@pytest.mark.asyncio(loop_scope="session")
async def test__suspended_task_with_retries__does_not_retry(
    hatchet_client_init: HatchetInitData, test_ctx, ctx_metadata, trigger_options
):
    # Arrange
    redis_client, hatchet = (
        hatchet_client_init.redis_client,
        hatchet_client_init.hatchet,
    )
    retry_task_sign = await mageflow.asign(retry_once)
    message = ContextMessage(base_data=test_ctx)

    # Act
    await retry_task_sign.suspend()
    await retry_task_sign.aio_run_no_wait(message, options=trigger_options)
    await asyncio.sleep(5)

    # Assert
    runs = await get_runs(hatchet, ctx_metadata)

    loaded_signature = await TaskSignature.aget(retry_task_sign.key)
    assert_task_was_paused(runs, loaded_signature)

    wf_by_task_id = map_wf_by_id(runs, also_not_done=True)
    task_summary = wf_by_task_id[retry_task_sign.key]
    assert (
        task_summary.retry_count == 0
    ), f"Expected retry_count=0, got {task_summary.retry_count}"


# TODO - what happen when task is cancelled from outside? does the server allow it to continue later? should we call error callback?
