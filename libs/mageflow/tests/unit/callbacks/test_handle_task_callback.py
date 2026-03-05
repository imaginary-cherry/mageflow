import asyncio

import pytest
from hatchet_sdk import NonRetryableException

from mageflow.callbacks import AcceptParams, HatchetResult
from tests.integration.hatchet.models import ContextMessage
from tests.unit.assertions import assert_task_has_short_ttl, assert_tasks_changed_status
from tests.unit.callbacks.conftest import (
    MockContextConfig,
    create_mock_hatchet_context,
    handler_factory,
    task_signature_factory,
)
from thirdmagic.signature import SignatureStatus
from thirdmagic.task import TaskSignature


@pytest.mark.asyncio
async def test__pending_signature__success__returns_wrapped_result(
    adapter_with_lifecycle,
):
    # Arrange
    signature, _ = await task_signature_factory(status=SignatureStatus.PENDING)
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    returning_handler, tracked_calls = handler_factory(return_value="my_result")
    message = ContextMessage()

    # Act
    result = await returning_handler(message, ctx)

    # Assert
    assert isinstance(result, HatchetResult)
    assert result.hatchet_results == "my_result"
    await assert_tasks_changed_status([signature.key], SignatureStatus.DONE)
    assert len(tracked_calls) == 1


@pytest.mark.asyncio
async def test__pending_signature__success_wrap_false__returns_raw(
    adapter_with_lifecycle,
):
    # Arrange
    signature, _ = await task_signature_factory(status=SignatureStatus.PENDING)
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    unwrapped_handler, tracked_calls = handler_factory(
        wrap_res=False, return_value="raw_result"
    )
    message = ContextMessage()

    # Act
    result = await unwrapped_handler(message, ctx)

    # Assert
    assert result == "raw_result"
    assert not isinstance(result, HatchetResult)
    await assert_tasks_changed_status([signature.key], SignatureStatus.DONE)


@pytest.mark.asyncio
async def test__pending_signature__error_with_retry__raises_without_failing(
    adapter_with_lifecycle,
):
    # Arrange
    signature, _ = await task_signature_factory(
        status=SignatureStatus.PENDING, retries=3
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    raising_handler, _ = handler_factory(raises=ValueError("test error"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(ValueError, match="test error"):
        await raising_handler(message, ctx)

    reloaded = await TaskSignature.aget(signature.key)
    assert reloaded.task_status.status != SignatureStatus.FAILED
    adapter_with_lifecycle.acall_signatures.assert_not_awaited()


@pytest.mark.asyncio
async def test__pending_signature__error_exhausted_retries__marks_failed(
    adapter_with_lifecycle,
    error_callback_signature,
):
    # Arrange
    adapter_with_lifecycle.should_task_retry.return_value = False
    signature, _ = await task_signature_factory(
        status=SignatureStatus.PENDING,
        retries=3,
        error_callbacks=[error_callback_signature],
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=3)
    )
    raising_handler, _ = handler_factory(raises=ValueError("test error"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(ValueError, match="test error"):
        await raising_handler(message, ctx)

    await assert_tasks_changed_status([signature.key], SignatureStatus.FAILED)
    adapter_with_lifecycle.acall_signatures.assert_awaited_once_with(
        [error_callback_signature],
        message.model_dump(mode="json", exclude_unset=True),
        False,
    )


@pytest.mark.asyncio
async def test__pending_signature__cancel_error__marks_failed_and_reraises(
    adapter_with_lifecycle,
    error_callback_signature,
):
    # Arrange
    signature, _ = await task_signature_factory(
        status=SignatureStatus.PENDING,
        retries=3,
        error_callbacks=[error_callback_signature],
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    raising_handler, _ = handler_factory(raises=asyncio.CancelledError())
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(asyncio.CancelledError):
        await raising_handler(message, ctx)

    await assert_tasks_changed_status([signature.key], SignatureStatus.FAILED)
    adapter_with_lifecycle.acall_signatures.assert_awaited_once_with(
        [error_callback_signature],
        message.model_dump(mode="json", exclude_unset=True),
        False,
    )


@pytest.mark.asyncio
async def test__active_signature__success__marks_done(
    adapter_with_lifecycle,
    callback_signature,
):
    # Arrange
    signature, _ = await task_signature_factory(
        status=SignatureStatus.ACTIVE, success_callbacks=[callback_signature]
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    task_return_value = "done"
    returning_handler, _ = handler_factory(return_value=task_return_value)
    message = ContextMessage()

    # Act
    await returning_handler(message, ctx)

    # Assert
    await assert_tasks_changed_status([signature.key], SignatureStatus.DONE)
    adapter_with_lifecycle.acall_signatures.assert_awaited_once_with(
        [callback_signature], task_return_value, True
    )


@pytest.mark.asyncio
async def test__active_signature__error__marks_failed(
    adapter_with_lifecycle,
    error_callback_signature,
):
    # Arrange
    adapter_with_lifecycle.should_task_retry.return_value = False
    signature, _ = await task_signature_factory(
        status=SignatureStatus.ACTIVE,
        retries=1,
        error_callbacks=[error_callback_signature],
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    raising_handler, _ = handler_factory(raises=RuntimeError("fail"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(RuntimeError, match="fail"):
        await raising_handler(message, ctx)

    await assert_tasks_changed_status([signature.key], SignatureStatus.FAILED)
    adapter_with_lifecycle.acall_signatures.assert_awaited_once_with(
        [error_callback_signature],
        message.model_dump(mode="json", exclude_unset=True),
        False,
    )


@pytest.mark.asyncio
async def test__suspended_signature__cancel_called():
    # Arrange
    signature, _ = await task_signature_factory(status=SignatureStatus.SUSPENDED)
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key, job_name="test_task", cancel_raises=True
        )
    )
    default_handler, tracked_calls = handler_factory()
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(asyncio.CancelledError):
        await default_handler(message, ctx)

    ctx.aio_cancel.assert_awaited_once()
    assert len(tracked_calls) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status", [SignatureStatus.SUSPENDED, SignatureStatus.CANCELED]
)
async def test__task_should_not_run__cancel_raises__propagates_error(status):
    # Arrange
    signature, _ = await task_signature_factory(status=status)
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key, job_name="test_task", cancel_raises=True
        )
    )
    default_handler, tracked_calls = handler_factory()
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(asyncio.CancelledError):
        await default_handler(message, ctx)

    assert len(tracked_calls) == 0


@pytest.mark.asyncio
async def test__suspended_signature__kwargs_updated():
    # Arrange
    signature, _ = await task_signature_factory(status=SignatureStatus.SUSPENDED)
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key, job_name="test_task", cancel_raises=True
        )
    )
    default_handler, _ = handler_factory()
    message = ContextMessage(base_data={"key": "value"})

    # Act
    with pytest.raises(asyncio.CancelledError):
        await default_handler(message, ctx)

    # Assert
    reloaded = await TaskSignature.aget(signature.key)
    assert "base_data" in reloaded.kwargs
    assert reloaded.kwargs["base_data"] == {"key": "value"}


@pytest.mark.asyncio
async def test__canceled_signature__removed(redis_client):
    # Arrange
    signature, _ = await task_signature_factory(status=SignatureStatus.CANCELED)
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key, job_name="test_task", cancel_raises=True
        )
    )
    default_handler, _ = handler_factory()
    message = ContextMessage()

    # Act
    with pytest.raises(asyncio.CancelledError):
        await default_handler(message, ctx)

    # Assert
    await assert_task_has_short_ttl(redis_client, signature.key)


@pytest.mark.asyncio
async def test__done_signature__should_not_run():
    # Arrange
    signature, _ = await task_signature_factory(status=SignatureStatus.DONE)
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key, job_name="test_task", cancel_raises=True
        )
    )
    default_handler, tracked_calls = handler_factory()
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(asyncio.CancelledError):
        await default_handler(message, ctx)

    ctx.aio_cancel.assert_awaited_once()
    assert len(tracked_calls) == 0


@pytest.mark.asyncio
async def test__failed_signature__should_not_run():
    # Arrange
    signature, _ = await task_signature_factory(status=SignatureStatus.FAILED)
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key, job_name="test_task", cancel_raises=True
        )
    )
    default_handler, tracked_calls = handler_factory()
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(asyncio.CancelledError):
        await default_handler(message, ctx)

    ctx.aio_cancel.assert_awaited_once()
    assert len(tracked_calls) == 0


@pytest.mark.asyncio
async def test__no_task_id__success__returns_directly(
    adapter_with_lifecycle,
):
    # Arrange
    await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=None, job_name="test_task")
    )
    returning_handler, tracked_calls = handler_factory(return_value="direct")
    message = ContextMessage()

    # Act
    result = await returning_handler(message, ctx)

    # Assert
    assert result == "direct"
    assert not isinstance(result, HatchetResult)
    assert len(tracked_calls) == 1


@pytest.mark.asyncio
async def test__no_task_id__error__raises_directly(
    adapter_with_lifecycle,
):
    # Arrange
    await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=None, job_name="test_task")
    )
    raising_handler, _ = handler_factory(raises=ValueError("vanilla error"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(ValueError, match="vanilla error"):
        await raising_handler(message, ctx)

    adapter_with_lifecycle.acall_signatures.assert_not_awaited()


@pytest.mark.asyncio
async def test__no_task_id__no_workflow_calls(
    adapter_with_lifecycle,
):
    # Arrange
    await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=None, job_name="test_task")
    )
    returning_handler, _ = handler_factory(return_value="result")
    message = ContextMessage()

    # Act
    await returning_handler(message, ctx)

    # Assert
    adapter_with_lifecycle.acall_signatures.assert_not_awaited()


@pytest.mark.asyncio
async def test__invalid_task_id__should_not_run():
    # Arrange
    await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id="nonexistent-task-id",
            job_name="test_task",
            cancel_raises=True,
        )
    )
    handler_bad_signature_key, tracked_calls = handler_factory()
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(NonRetryableException):
        await handler_bad_signature_key(message, ctx)

    assert len(tracked_calls) == 0


@pytest.mark.asyncio
async def test__no_retries__error__marks_failed(
    adapter_with_lifecycle,
    error_callback_signature,
):
    # Arrange
    adapter_with_lifecycle.should_task_retry.return_value = False
    signature, _ = await task_signature_factory(
        retries=None, error_callbacks=[error_callback_signature]
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    raising_handler, _ = handler_factory(raises=RuntimeError("error"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(RuntimeError, match="error"):
        await raising_handler(message, ctx)

    await assert_tasks_changed_status([signature.key], SignatureStatus.FAILED)
    adapter_with_lifecycle.acall_signatures.assert_awaited_once_with(
        [error_callback_signature],
        message.model_dump(mode="json", exclude_unset=True),
        False,
    )


@pytest.mark.asyncio
async def test__retries_3_attempt_1__error__not_failed(
    adapter_with_lifecycle,
):
    # Arrange
    signature, _ = await task_signature_factory(retries=3)
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    raising_handler, _ = handler_factory(raises=RuntimeError("retry"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(RuntimeError, match="retry"):
        await raising_handler(message, ctx)

    reloaded = await TaskSignature.aget(signature.key)
    assert reloaded.task_status.status != SignatureStatus.FAILED
    adapter_with_lifecycle.acall_signatures.assert_not_awaited()


@pytest.mark.asyncio
async def test__retries_3_attempt_3__error__marks_failed(
    adapter_with_lifecycle,
    error_callback_signature,
):
    # Arrange
    adapter_with_lifecycle.should_task_retry.return_value = False
    signature, _ = await task_signature_factory(
        retries=3, error_callbacks=[error_callback_signature]
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=3)
    )
    raising_handler, _ = handler_factory(raises=RuntimeError("final"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(RuntimeError, match="final"):
        await raising_handler(message, ctx)

    await assert_tasks_changed_status([signature.key], SignatureStatus.FAILED)
    adapter_with_lifecycle.acall_signatures.assert_awaited_once_with(
        [error_callback_signature],
        message.model_dump(mode="json", exclude_unset=True),
        False,
    )


@pytest.mark.asyncio
async def test__non_retryable_exception__always_fails(
    adapter_with_lifecycle,
    error_callback_signature,
):
    # Arrange
    adapter_with_lifecycle.should_task_retry.return_value = False
    signature, _ = await task_signature_factory(
        retries=5, error_callbacks=[error_callback_signature]
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    non_retryable_handler, _ = handler_factory(
        raises=NonRetryableException("non-retryable")
    )
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(NonRetryableException, match="non-retryable"):
        await non_retryable_handler(message, ctx)

    await assert_tasks_changed_status([signature.key], SignatureStatus.FAILED)
    adapter_with_lifecycle.acall_signatures.assert_awaited_once_with(
        [error_callback_signature],
        message.model_dump(mode="json", exclude_unset=True),
        False,
    )


@pytest.mark.asyncio
async def test__with_success_callbacks__on_success__triggered(
    adapter_with_lifecycle,
    callback_signature,
):
    # Arrange
    signature, _ = await task_signature_factory(success_callbacks=[callback_signature])
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    return_value = "success"
    returning_handler, _ = handler_factory(return_value=return_value)
    message = ContextMessage()

    # Act
    await returning_handler(message, ctx)

    # Assert
    adapter_with_lifecycle.acall_signatures.assert_awaited_once_with(
        [callback_signature], return_value, True
    )


@pytest.mark.asyncio
async def test__with_success_callbacks__on_error__not_triggered(
    adapter_with_lifecycle,
    callback_signature,
):
    # Arrange
    signature, _ = await task_signature_factory(
        retries=3, success_callbacks=[callback_signature]
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    raising_handler, _ = handler_factory(raises=RuntimeError("err"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(RuntimeError):
        await raising_handler(message, ctx)

    adapter_with_lifecycle.acall_signatures.assert_not_awaited()


@pytest.mark.asyncio
async def test__with_error_callbacks__on_error_no_retry__triggered(
    adapter_with_lifecycle,
    error_callback_signature,
):
    # Arrange
    adapter_with_lifecycle.should_task_retry.return_value = False
    signature, _ = await task_signature_factory(
        retries=None, error_callbacks=[error_callback_signature]
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    raising_handler, _ = handler_factory(raises=RuntimeError("error"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(RuntimeError):
        await raising_handler(message, ctx)

    adapter_with_lifecycle.acall_signatures.assert_awaited_once_with(
        [error_callback_signature],
        message.model_dump(mode="json", exclude_unset=True),
        False,
    )


@pytest.mark.asyncio
async def test__with_error_callbacks__on_error_with_retry__not_triggered(
    adapter_with_lifecycle,
    error_callback_signature,
):
    # Arrange
    signature, _ = await task_signature_factory(
        retries=3, error_callbacks=[error_callback_signature]
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    raising_handler, _ = handler_factory(raises=RuntimeError("error"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(RuntimeError):
        await raising_handler(message, ctx)

    adapter_with_lifecycle.acall_signatures.assert_not_awaited()


@pytest.mark.asyncio
async def test__with_both_callbacks__on_success__only_success_triggered(
    adapter_with_lifecycle,
    callback_signature,
    error_callback_signature,
):
    # Arrange
    signature, _ = await task_signature_factory(
        success_callbacks=[callback_signature],
        error_callbacks=[error_callback_signature],
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    return_value = "ok"
    returning_handler, _ = handler_factory(return_value=return_value)
    message = ContextMessage()

    # Act
    await returning_handler(message, ctx)

    # Assert
    adapter_with_lifecycle.acall_signatures.assert_awaited_once_with(
        [callback_signature], return_value, True
    )


@pytest.mark.asyncio
async def test__with_both_callbacks__on_error__only_error_triggered(
    adapter_with_lifecycle,
    callback_signature,
    error_callback_signature,
):
    # Arrange
    adapter_with_lifecycle.should_task_retry.return_value = False
    signature, _ = await task_signature_factory(
        retries=None,
        success_callbacks=[callback_signature],
        error_callbacks=[error_callback_signature],
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    raising_handler, _ = handler_factory(raises=RuntimeError("err"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(RuntimeError):
        await raising_handler(message, ctx)

    adapter_with_lifecycle.acall_signatures.assert_awaited_once_with(
        [error_callback_signature],
        message.model_dump(mode="json", exclude_unset=True),
        False,
    )


@pytest.mark.asyncio
async def test__just_message__func_receives_only_message(
    adapter_with_lifecycle,
):
    # Arrange
    signature, _ = await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    just_message_handler, tracked_calls = handler_factory(
        expected_params=AcceptParams.JUST_MESSAGE
    )
    message = ContextMessage(base_data={"test": "data"})

    # Act
    await just_message_handler(message, ctx)

    # Assert
    assert len(tracked_calls) == 1
    assert tracked_calls[0].args == (message,)
    assert tracked_calls[0].kwargs == {}


@pytest.mark.asyncio
async def test__no_ctx__func_receives_message_and_kwargs(
    adapter_with_lifecycle,
):
    # Arrange
    signature, _ = await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    no_ctx_handler, tracked_calls = handler_factory(expected_params=AcceptParams.NO_CTX)
    message = ContextMessage()

    # Act
    await no_ctx_handler(message, ctx)

    # Assert
    assert len(tracked_calls) == 1
    assert tracked_calls[0].args[0] == message


@pytest.mark.asyncio
async def test__all__func_receives_message_and_ctx(
    adapter_with_lifecycle,
):
    # Arrange
    signature, _ = await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    all_params_handler, tracked_calls = handler_factory(
        expected_params=AcceptParams.ALL
    )
    message = ContextMessage()

    # Act
    await all_params_handler(message, ctx)

    # Assert
    assert len(tracked_calls) == 1
    assert tracked_calls[0].args == (message, ctx)


@pytest.mark.asyncio
async def test__send_signature_true__in_kwargs(
    adapter_with_lifecycle,
):
    # Arrange
    signature, _ = await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    signature_sending_handler, tracked_calls = handler_factory(send_signature=True)
    message = ContextMessage()

    # Act
    await signature_sending_handler(message, ctx)

    # Assert
    assert len(tracked_calls) == 1
    assert "signature" in tracked_calls[0].kwargs
    assert tracked_calls[0].kwargs["signature"].key == signature.key


@pytest.mark.asyncio
async def test__send_signature_false__not_in_kwargs(
    adapter_with_lifecycle,
):
    # Arrange
    signature, _ = await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    no_signature_handler, tracked_calls = handler_factory(send_signature=False)
    message = ContextMessage()

    # Act
    await no_signature_handler(message, ctx)

    # Assert
    assert len(tracked_calls) == 1
    assert "signature" not in tracked_calls[0].kwargs
