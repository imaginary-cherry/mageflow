import pytest
from hatchet_sdk.clients.admin import TriggerWorkflowOptions

import thirdmagic
from tests.unit.messages import ContextMessage


@pytest.mark.asyncio
async def test_aio_run_calls_await_signature_with_correct_params(mock_adapter):
    # Arrange
    base_data = {"test": "data"}
    test_ctx = {"ctx_key": "ctx_value"}
    signature = await thirdmagic.sign("test_task", model_validators=ContextMessage)
    msg = ContextMessage(base_data=base_data, test_ctx=test_ctx)

    # Act
    await signature.aio_run(msg)

    # Assert
    mock_adapter.await_signature.assert_awaited_once_with(
        signature, msg, set_return_field=False
    )


@pytest.mark.asyncio
async def test_aio_run_calls_await_signature_with_options(mock_adapter):
    # Arrange
    base_data = {"test": "data"}
    test_ctx = {"ctx_key": "ctx_value"}
    signature = await thirdmagic.sign("test_task", model_validators=ContextMessage)
    msg = ContextMessage(base_data=base_data, test_ctx=test_ctx)
    options = TriggerWorkflowOptions(additional_metadata={"custom": "value"})

    # Act
    await signature.aio_run(msg, options)

    # Assert
    mock_adapter.await_signature.assert_awaited_once_with(
        signature, msg, set_return_field=False, options=options
    )


@pytest.mark.asyncio
async def test_aio_run_without_options_does_not_pass_options_kwarg(mock_adapter):
    # Arrange
    signature = await thirdmagic.sign("test_task", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"test": "data"})

    # Act
    await signature.aio_run(msg)

    # Assert
    call_kwargs = mock_adapter.await_signature.await_args.kwargs
    assert "options" not in call_kwargs
