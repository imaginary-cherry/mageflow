import pytest

import mageflow
from mageflow.models.message import DEFAULT_RESULT_NAME
from mageflow.signature.model import TaskSignature
from mageflow.task.model import HatchetTaskModel
from tests.integration.hatchet.models import (
    ContextMessage,
    MessageWithData,
    CommandMessageWithResult,
)


@pytest.mark.asyncio
async def test__await_task__stored_in_redis__sanity(hatchet_mock, redis_client):
    # Arrange
    @hatchet_mock.task(name="test_task")
    def test_task(msg):
        return msg

    # Act
    task = await mageflow.sign(test_task)

    # Assert
    assert await redis_client.exists(task.key)


@pytest.mark.asyncio
async def test__signature_create_save_load__input_output_same__sanity(hatchet_mock):
    # Arrange
    @hatchet_mock.task(name="test_task")
    def test_task(msg):
        return msg

    kwargs = {"arg1": "test", "arg2": 123}

    # Act
    original_signature = await mageflow.sign(test_task, **kwargs)
    loaded_signature = await TaskSignature.get_safe(original_signature.key)

    # Assert
    assert original_signature == loaded_signature


@pytest.mark.asyncio
async def test__from_signature__create_signature_from_existing__all_data_same_except_pk__sanity(
    hatchet_mock,
):
    # Arrange
    @hatchet_mock.task(name="test_task")
    def test_task(msg):
        return msg

    kwargs = {"arg1": "test", "arg2": 123}
    success_callbacks = ["callback1", "callback2"]
    error_callbacks = ["error_callback1"]

    original_signature = await mageflow.sign(
        test_task,
        success_callbacks=success_callbacks,
        error_callbacks=error_callbacks,
        **kwargs,
    )

    # Act
    new_signature = await original_signature.aduplicate()

    # Assert
    original_data = original_signature.model_dump(exclude={"pk"})
    new_data = new_signature.model_dump(exclude={"pk"})
    assert original_data == new_data
    assert new_signature.pk != original_signature.pk


@pytest.mark.asyncio
async def test__from_task__model_with_return_value__return_field_name_set(hatchet_mock):
    # Arrange
    @hatchet_mock.task(name="task_with_return", input_validator=MessageWithData)
    def task_with_return(msg):
        return msg

    # Act
    signature = await mageflow.sign(task_with_return)

    # Assert
    assert signature.return_field_name == "data"


@pytest.mark.asyncio
async def test__from_task__model_without_return_value__return_field_name_is_default(
    hatchet_mock,
):
    # Arrange
    @hatchet_mock.task(name="task_no_return", input_validator=ContextMessage)
    def task_no_return(msg):
        return msg

    # Act
    signature = await mageflow.sign(task_no_return)

    # Assert
    assert signature.return_field_name == DEFAULT_RESULT_NAME


@pytest.mark.asyncio
async def test__from_task__no_input_validator__return_field_name_is_default(
    hatchet_mock,
):
    # Arrange
    @hatchet_mock.task(name="task_no_validator")
    def task_no_validator(msg):
        return msg

    # Act
    signature = await mageflow.sign(task_no_validator)

    # Assert
    assert signature.return_field_name == DEFAULT_RESULT_NAME


@pytest.mark.asyncio
async def test__from_task_name__task_model_in_redis_with_return_value__return_field_name_set():
    # Arrange
    task_name = "redis_task_with_return"
    task_model = HatchetTaskModel(
        mageflow_task_name=task_name,
        task_name=task_name,
        input_validator=MessageWithData,
    )
    await task_model.asave()

    # Act
    signature = await mageflow.sign(task_name)

    # Assert
    assert signature.return_field_name == "data"


@pytest.mark.asyncio
async def test__from_task_name__explicit_model_validators_with_return_value__return_field_name_set():
    # Arrange
    task_name = "task_with_explicit_validators"

    # Act
    signature = await mageflow.sign(
        task_name, model_validators=CommandMessageWithResult
    )

    # Assert
    assert signature.return_field_name == "task_result"
