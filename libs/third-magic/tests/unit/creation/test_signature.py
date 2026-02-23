from datetime import datetime
from typing import Optional, Any

import pytest
from pydantic import BaseModel
from rapyer.fields import RapyerKey

import thirdmagic
from tests.unit.creation.conftest import extract_hatchet_validator
from tests.unit.messages import (
    ContextMessage,
    MessageWithData,
    CommandMessageWithResult,
)
from thirdmagic.message import DEFAULT_RESULT_NAME
from thirdmagic.task import TaskSignature
from thirdmagic.task_def import MageflowTaskDefinition


class SignParamOptions(BaseModel):
    kwargs: Optional[dict[str, Any]] = None
    creation_time: Optional[datetime] = None
    success_callbacks: Optional[list[RapyerKey]] = None
    error_callbacks: Optional[list[RapyerKey]] = None
    task_identifiers: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        result = self.model_dump(exclude_defaults=True, exclude={"kwargs"})
        if self.kwargs:
            result.update(self.kwargs)
        return result


@pytest.mark.asyncio
async def test__await_task__stored_in_redis__sanity(hatchet_mock, redis_client):
    # Arrange
    @hatchet_mock.task(name="test_task")
    def test_task(msg):
        return msg

    # Act
    task = await thirdmagic.sign(test_task)

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
    original_signature = await thirdmagic.sign(test_task, **kwargs)
    loaded_signature = await TaskSignature.aget(original_signature.key)

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

    original_signature = await thirdmagic.sign(
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
    signature = await thirdmagic.sign(task_with_return)

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
    signature = await thirdmagic.sign(task_no_return)

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
    signature = await thirdmagic.sign(task_no_validator)

    # Assert
    assert signature.return_field_name == DEFAULT_RESULT_NAME


@pytest.mark.asyncio
async def test__from_task_name__task_model_in_redis_with_return_value__return_field_name_set():
    # Arrange
    task_name = "redis_task_with_return"
    task_model = MageflowTaskDefinition(
        mageflow_task_name=task_name,
        task_name=task_name,
        input_validator=MessageWithData,
    )
    await task_model.asave()

    # Act
    signature = await thirdmagic.sign(task_name)

    # Assert
    assert signature.return_field_name == "data"


@pytest.mark.asyncio
async def test__from_task_name__explicit_model_validators_with_return_value__return_field_name_set():
    # Arrange
    task_name = "task_with_explicit_validators"

    # Act
    signature = await thirdmagic.sign(
        task_name, model_validators=CommandMessageWithResult
    )

    # Assert
    assert signature.return_field_name == "task_result"


@pytest.mark.parametrize("task", ["hatchet_task", "hatchet_task_name"], indirect=True)
@pytest.mark.parametrize(
    ["sign_options", "expected_signature"],
    [
        [
            SignParamOptions(kwargs={"param1": "value1"}),
            TaskSignature(task_name="test_task", kwargs={"param1": "value1"}),
        ],
        [
            SignParamOptions(),
            TaskSignature(task_name="test_task"),
        ],
        [
            SignParamOptions(creation_time=datetime(2023, 1, 1)),
            TaskSignature(task_name="test_task", creation_time=datetime(2023, 1, 1)),
        ],
        [
            SignParamOptions(task_identifiers={"identifier": "test_id"}),
            TaskSignature(
                task_name="test_task",
                kwargs={"task_identifiers": {"identifier": "test_id"}},
            ),
        ],
        [
            SignParamOptions(success_callbacks=["TaskSignature:success_task_1"]),
            TaskSignature(
                task_name="test_task",
                success_callbacks=["TaskSignature:success_task_1"],
            ),
        ],
        [
            SignParamOptions(error_callbacks=["TaskSignature:error_task_1"]),
            TaskSignature(
                task_name="test_task", error_callbacks=["TaskSignature:error_task_1"]
            ),
        ],
        [
            SignParamOptions(
                success_callbacks=[
                    "TaskSignature:success_task_1",
                    "TaskSignature:success_task_2",
                ],
                error_callbacks=["TaskSignature:error_task_1"],
            ),
            TaskSignature(
                task_name="test_task",
                success_callbacks=[
                    "TaskSignature:success_task_1",
                    "TaskSignature:success_task_2",
                ],
                error_callbacks=["TaskSignature:error_task_1"],
            ),
        ],
        [
            SignParamOptions(
                kwargs={"param1": "value1", "param2": 42},
                creation_time=datetime(2023, 6, 15),
                task_identifiers={"id1": "test", "id2": "another"},
                success_callbacks=["TaskSignature:complex_success"],
                error_callbacks=[
                    "TaskSignature:complex_error_1",
                    "TaskSignature:complex_error_2",
                ],
            ),
            TaskSignature(
                task_name="test_task",
                kwargs={
                    "param1": "value1",
                    "param2": 42,
                    "task_identifiers": {"id1": "test", "id2": "another"},
                },
                creation_time=datetime(2023, 6, 15),
                success_callbacks=["TaskSignature:complex_success"],
                error_callbacks=[
                    "TaskSignature:complex_error_1",
                    "TaskSignature:complex_error_2",
                ],
            ),
        ],
    ],
)
@pytest.mark.asyncio
async def test__sign_task__sanity(
    task, sign_options: SignParamOptions, expected_signature: TaskSignature
):
    # Arrange
    expected_signature = expected_signature.model_copy()
    sign_params = sign_options.to_dict()
    if not (isinstance(task, str) or expected_signature.model_validators):
        expected_signature.model_validators = extract_hatchet_validator(task)

    # Act
    signature = await thirdmagic.sign(task, **sign_params)

    # Assert
    signature.creation_time = expected_signature.creation_time
    assert signature.model_dump() == expected_signature.model_dump()
