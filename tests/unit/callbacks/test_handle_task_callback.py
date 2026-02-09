import asyncio

import pytest
from hatchet_sdk import NonRetryableException

from mageflow.callbacks import AcceptParams, HatchetResult
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus
from tests.integration.hatchet.models import ContextMessage
from tests.unit.assertions import assert_tasks_changed_status, assert_task_has_short_ttl
from tests.unit.callbacks.conftest import (
    MockContextConfig,
    create_mock_hatchet_context,
    decorated_func_factory,
    task_signature_factory,
)


@pytest.mark.asyncio
async def test__pending_signature__success__returns_wrapped_result(
    mock_workflow_run,
):
    # Arrange
    signature, _ = await task_signature_factory(status=SignatureStatus.PENDING)
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    handle_decorator, call_tracker = decorated_func_factory(return_value="my_result")
    message = ContextMessage()

    # Act
    result = await handle_decorator(message, ctx)

    # Assert
    assert isinstance(result, HatchetResult)
    assert result.hatchet_results == "my_result"
    await assert_tasks_changed_status([signature.key], SignatureStatus.DONE)
    assert len(call_tracker) == 1


@pytest.mark.asyncio
async def test__pending_signature__success_wrap_false__returns_raw(
    mock_workflow_run,
):
    # Arrange
    signature, _ = await task_signature_factory(status=SignatureStatus.PENDING)
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    handle_decorator, call_tracker = decorated_func_factory(
        wrap_res=False, return_value="raw_result"
    )
    message = ContextMessage()

    # Act
    result = await handle_decorator(message, ctx)

    # Assert
    assert result == "raw_result"
    assert not isinstance(result, HatchetResult)
    await assert_tasks_changed_status([signature.key], SignatureStatus.DONE)


@pytest.mark.asyncio
async def test__pending_signature__error_with_retry__raises_without_failing(
    mock_workflow_run,
):
    # Arrange
    signature, _ = await task_signature_factory(
        status=SignatureStatus.PENDING, retries=3
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    handle_decorator, _ = decorated_func_factory(raises=ValueError("test error"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(ValueError, match="test error"):
        await handle_decorator(message, ctx)

    reloaded = await TaskSignature.get_safe(signature.key)
    assert reloaded.task_status.status != SignatureStatus.FAILED
    assert len(mock_workflow_run) == 0


@pytest.mark.asyncio
async def test__pending_signature__error_exhausted_retries__marks_failed(
    mock_workflow_run,
    error_callback_signature,
):
    # Arrange
    signature, _ = await task_signature_factory(
        status=SignatureStatus.PENDING,
        retries=3,
        error_callbacks=[error_callback_signature],
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=3)
    )
    decorated_func, _ = decorated_func_factory(raises=ValueError("test error"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(ValueError, match="test error"):
        await decorated_func(message, ctx)

    await assert_tasks_changed_status([signature.key], SignatureStatus.FAILED)
    assert len(mock_workflow_run) == 1


@pytest.mark.asyncio
async def test__active_signature__success__marks_done(
    mock_workflow_run,
    callback_signature,
):
    # Arrange
    signature, _ = await task_signature_factory(
        status=SignatureStatus.ACTIVE, success_callbacks=[callback_signature]
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    decorated_func, _ = decorated_func_factory(return_value="done")
    message = ContextMessage()

    # Act
    await decorated_func(message, ctx)

    # Assert
    await assert_tasks_changed_status([signature.key], SignatureStatus.DONE)
    assert len(mock_workflow_run) == 1


@pytest.mark.asyncio
async def test__active_signature__error__marks_failed(
    mock_workflow_run,
    error_callback_signature,
):
    # Arrange
    signature, _ = await task_signature_factory(
        status=SignatureStatus.ACTIVE,
        retries=1,
        error_callbacks=[error_callback_signature],
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    decorated_func, _ = decorated_func_factory(raises=RuntimeError("fail"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(RuntimeError, match="fail"):
        await decorated_func(message, ctx)

    await assert_tasks_changed_status([signature.key], SignatureStatus.FAILED)
    assert len(mock_workflow_run) == 1


@pytest.mark.asyncio
async def test__suspended_signature__cancel_called():
    # Arrange
    signature, _ = await task_signature_factory(status=SignatureStatus.SUSPENDED)
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key, job_name="test_task", cancel_raises=True
        )
    )
    decorated_func, call_tracker = decorated_func_factory()
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(asyncio.CancelledError):
        await decorated_func(message, ctx)

    ctx.aio_cancel.assert_awaited_once()
    assert len(call_tracker) == 0


@pytest.mark.asyncio
async def test__suspended_signature__cancel_raises__propagates_error():
    # Arrange
    signature, _ = await task_signature_factory(status=SignatureStatus.SUSPENDED)
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key, job_name="test_task", cancel_raises=True
        )
    )
    decorated_func, call_tracker = decorated_func_factory()
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(asyncio.CancelledError):
        await decorated_func(message, ctx)

    assert len(call_tracker) == 0


@pytest.mark.asyncio
async def test__suspended_signature__kwargs_updated():
    # Arrange
    signature, _ = await task_signature_factory(status=SignatureStatus.SUSPENDED)
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key, job_name="test_task", cancel_raises=True
        )
    )
    decorated_func, _ = decorated_func_factory()
    message = ContextMessage(base_data={"key": "value"})

    # Act
    with pytest.raises(asyncio.CancelledError):
        await decorated_func(message, ctx)

    # Assert
    reloaded = await TaskSignature.get_safe(signature.key)
    assert "base_data" in reloaded.kwargs
    assert reloaded.kwargs["base_data"] == {"key": "value"}


@pytest.mark.asyncio
async def test__canceled_signature__cancel_called():
    # Arrange
    signature, _ = await task_signature_factory(status=SignatureStatus.CANCELED)
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key, job_name="test_task", cancel_raises=True
        )
    )
    decorated_func, call_tracker = decorated_func_factory()
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(asyncio.CancelledError):
        await decorated_func(message, ctx)

    ctx.aio_cancel.assert_awaited_once()
    assert len(call_tracker) == 0


@pytest.mark.asyncio
async def test__canceled_signature__removed():
    # Arrange
    signature, _ = await task_signature_factory(status=SignatureStatus.CANCELED)
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key, job_name="test_task", cancel_raises=True
        )
    )
    decorated_func, _ = decorated_func_factory()
    message = ContextMessage()

    # Act
    with pytest.raises(asyncio.CancelledError):
        await decorated_func(message, ctx)

    # Assert
    await assert_task_has_short_ttl(signature.key)


@pytest.mark.asyncio
async def test__done_signature__should_not_run():
    # Arrange
    signature, _ = await task_signature_factory(status=SignatureStatus.DONE)
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key, job_name="test_task", cancel_raises=True
        )
    )
    decorated_func, call_tracker = decorated_func_factory()
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(asyncio.CancelledError):
        await decorated_func(message, ctx)

    ctx.aio_cancel.assert_awaited_once()
    assert len(call_tracker) == 0


@pytest.mark.asyncio
async def test__failed_signature__should_not_run():
    # Arrange
    signature, _ = await task_signature_factory(status=SignatureStatus.FAILED)
    ctx = create_mock_hatchet_context(
        MockContextConfig(
            task_id=signature.key, job_name="test_task", cancel_raises=True
        )
    )
    decorated_func, call_tracker = decorated_func_factory()
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(asyncio.CancelledError):
        await decorated_func(message, ctx)

    ctx.aio_cancel.assert_awaited_once()
    assert len(call_tracker) == 0


@pytest.mark.asyncio
async def test__no_task_id__success__returns_directly(
    mock_workflow_run,
):
    # Arrange
    await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=None, job_name="test_task")
    )
    decorated_func, call_tracker = decorated_func_factory(return_value="direct")
    message = ContextMessage()

    # Act
    result = await decorated_func(message, ctx)

    # Assert
    assert result == "direct"
    assert not isinstance(result, HatchetResult)
    assert len(call_tracker) == 1


@pytest.mark.asyncio
async def test__no_task_id__error__raises_directly(
    mock_workflow_run,
):
    # Arrange
    await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=None, job_name="test_task")
    )
    decorated_func, _ = decorated_func_factory(raises=ValueError("vanilla error"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(ValueError, match="vanilla error"):
        await decorated_func(message, ctx)

    assert len(mock_workflow_run) == 0


@pytest.mark.asyncio
async def test__no_task_id__no_workflow_calls(
    mock_workflow_run,
):
    # Arrange
    await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=None, job_name="test_task")
    )
    decorated_func, _ = decorated_func_factory(return_value="result")
    message = ContextMessage()

    # Act
    await decorated_func(message, ctx)

    # Assert
    assert len(mock_workflow_run) == 0


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
    decorated_func, call_tracker = decorated_func_factory()
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(Exception):
        await decorated_func(message, ctx)

    assert len(call_tracker) == 0


@pytest.mark.asyncio
async def test__no_retries__error__marks_failed(
    mock_workflow_run,
    error_callback_signature,
):
    # Arrange
    signature, _ = await task_signature_factory(
        retries=None, error_callbacks=[error_callback_signature]
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    decorated_func, _ = decorated_func_factory(raises=RuntimeError("error"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(RuntimeError, match="error"):
        await decorated_func(message, ctx)

    await assert_tasks_changed_status([signature.key], SignatureStatus.FAILED)
    assert len(mock_workflow_run) == 1


@pytest.mark.asyncio
async def test__retries_3_attempt_1__error__not_failed(
    mock_workflow_run,
):
    # Arrange
    signature, _ = await task_signature_factory(retries=3)
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    decorated_func, _ = decorated_func_factory(raises=RuntimeError("retry"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(RuntimeError, match="retry"):
        await decorated_func(message, ctx)

    reloaded = await TaskSignature.get_safe(signature.key)
    assert reloaded.task_status.status != SignatureStatus.FAILED
    assert len(mock_workflow_run) == 0


@pytest.mark.asyncio
async def test__retries_3_attempt_3__error__marks_failed(
    mock_workflow_run,
    error_callback_signature,
):
    # Arrange
    signature, _ = await task_signature_factory(
        retries=3, error_callbacks=[error_callback_signature]
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=3)
    )
    decorated_func, _ = decorated_func_factory(raises=RuntimeError("final"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(RuntimeError, match="final"):
        await decorated_func(message, ctx)

    await assert_tasks_changed_status([signature.key], SignatureStatus.FAILED)
    assert len(mock_workflow_run) == 1


@pytest.mark.asyncio
async def test__non_retryable_exception__always_fails(
    mock_workflow_run,
    error_callback_signature,
):
    # Arrange
    signature, _ = await task_signature_factory(
        retries=5, error_callbacks=[error_callback_signature]
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    decorated_func, _ = decorated_func_factory(
        raises=NonRetryableException("non-retryable")
    )
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(NonRetryableException, match="non-retryable"):
        await decorated_func(message, ctx)

    await assert_tasks_changed_status([signature.key], SignatureStatus.FAILED)
    assert len(mock_workflow_run) == 1


@pytest.mark.asyncio
async def test__with_success_callbacks__on_success__triggered(
    mock_workflow_run,
    callback_signature,
):
    # Arrange
    signature, _ = await task_signature_factory(success_callbacks=[callback_signature])
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    decorated_func, _ = decorated_func_factory(return_value="success")
    message = ContextMessage()

    # Act
    await decorated_func(message, ctx)

    # Assert
    assert len(mock_workflow_run) == 1
    assert mock_workflow_run[0].config.name == "callback_task"


@pytest.mark.asyncio
async def test__with_success_callbacks__on_error__not_triggered(
    mock_workflow_run,
    callback_signature,
):
    # Arrange
    signature, _ = await task_signature_factory(
        retries=3, success_callbacks=[callback_signature]
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    decorated_func, _ = decorated_func_factory(raises=RuntimeError("err"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(RuntimeError):
        await decorated_func(message, ctx)

    assert len(mock_workflow_run) == 0


@pytest.mark.asyncio
async def test__with_error_callbacks__on_error_no_retry__triggered(
    mock_workflow_run,
    error_callback_signature,
):
    # Arrange
    signature, _ = await task_signature_factory(
        retries=None, error_callbacks=[error_callback_signature]
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    decorated_func, _ = decorated_func_factory(raises=RuntimeError("error"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(RuntimeError):
        await decorated_func(message, ctx)

    assert len(mock_workflow_run) == 1
    assert mock_workflow_run[0].config.name == "error_callback_task"


@pytest.mark.asyncio
async def test__with_error_callbacks__on_error_with_retry__not_triggered(
    mock_workflow_run,
    error_callback_signature,
):
    # Arrange
    signature, _ = await task_signature_factory(
        retries=3, error_callbacks=[error_callback_signature]
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    decorated_func, _ = decorated_func_factory(raises=RuntimeError("error"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(RuntimeError):
        await decorated_func(message, ctx)

    assert len(mock_workflow_run) == 0


@pytest.mark.asyncio
async def test__with_both_callbacks__on_success__only_success_triggered(
    mock_workflow_run,
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
    decorated_func, _ = decorated_func_factory(return_value="ok")
    message = ContextMessage()

    # Act
    await decorated_func(message, ctx)

    # Assert
    assert len(mock_workflow_run) == 1
    assert mock_workflow_run[0].config.name == "callback_task"


@pytest.mark.asyncio
async def test__with_both_callbacks__on_error__only_error_triggered(
    mock_workflow_run,
    callback_signature,
    error_callback_signature,
):
    # Arrange
    signature, _ = await task_signature_factory(
        retries=None,
        success_callbacks=[callback_signature],
        error_callbacks=[error_callback_signature],
    )
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task", attempt_number=1)
    )
    decorated_func, _ = decorated_func_factory(raises=RuntimeError("err"))
    message = ContextMessage()

    # Act & Assert
    with pytest.raises(RuntimeError):
        await decorated_func(message, ctx)

    assert len(mock_workflow_run) == 1
    assert mock_workflow_run[0].config.name == "error_callback_task"


@pytest.mark.asyncio
async def test__just_message__func_receives_only_message(
    mock_workflow_run,
):
    # Arrange
    signature, _ = await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    decorated_func, call_tracker = decorated_func_factory(
        expected_params=AcceptParams.JUST_MESSAGE
    )
    message = ContextMessage(base_data={"test": "data"})

    # Act
    await decorated_func(message, ctx)

    # Assert
    assert len(call_tracker) == 1
    assert call_tracker[0].args == (message,)
    assert call_tracker[0].kwargs == {}


@pytest.mark.asyncio
async def test__no_ctx__func_receives_message_and_kwargs(
    mock_workflow_run,
):
    # Arrange
    signature, _ = await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    decorated_func, call_tracker = decorated_func_factory(
        expected_params=AcceptParams.NO_CTX
    )
    message = ContextMessage()

    # Act
    await decorated_func(message, ctx)

    # Assert
    assert len(call_tracker) == 1
    assert call_tracker[0].args[0] == message


@pytest.mark.asyncio
async def test__all__func_receives_message_and_ctx(
    mock_workflow_run,
):
    # Arrange
    signature, _ = await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    decorated_func, call_tracker = decorated_func_factory(
        expected_params=AcceptParams.ALL
    )
    message = ContextMessage()

    # Act
    await decorated_func(message, ctx)

    # Assert
    assert len(call_tracker) == 1
    assert call_tracker[0].args == (message, ctx)


@pytest.mark.asyncio
async def test__send_signature_true__in_kwargs(
    mock_workflow_run,
):
    # Arrange
    signature, _ = await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    decorated_func, call_tracker = decorated_func_factory(send_signature=True)
    message = ContextMessage()

    # Act
    await decorated_func(message, ctx)

    # Assert
    assert len(call_tracker) == 1
    assert "signature" in call_tracker[0].kwargs
    assert call_tracker[0].kwargs["signature"].key == signature.key


@pytest.mark.asyncio
async def test__send_signature_false__not_in_kwargs(
    mock_workflow_run,
):
    # Arrange
    signature, _ = await task_signature_factory()
    ctx = create_mock_hatchet_context(
        MockContextConfig(task_id=signature.key, job_name="test_task")
    )
    decorated_func, call_tracker = decorated_func_factory(send_signature=False)
    message = ContextMessage()

    # Act
    await decorated_func(message, ctx)

    # Assert
    assert len(call_tracker) == 1
    assert "signature" not in call_tracker[0].kwargs
