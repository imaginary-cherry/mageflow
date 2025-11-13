from dataclasses import dataclass, fields
from datetime import datetime
from typing import Optional, List, Dict, Any

import pytest

import orchestrator
from orchestrator import TaskSignature


@dataclass
class SignParamOptions:
    kwargs: Optional[Dict[str, Any]] = None
    workflow_params: Optional[Dict[str, Any]] = None
    creation_time: Optional[datetime] = None
    success_callbacks: Optional[List[orchestrator.TaskIdentifierType]] = None
    error_callbacks: Optional[List[orchestrator.TaskIdentifierType]] = None
    task_identifiers: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {}
        for field in fields(self):
            value = getattr(self, field.name)
            if value is not None:
                if field.name == "kwargs" and value:
                    result.update(value)
                else:
                    result[field.name] = value
        return result


@pytest.fixture
def hatchet_task(orch):
    @orch.task(name="test_task")
    def test_task(msg):
        return msg

    yield test_task


@pytest.fixture
def hatchet_task_name(orch):
    @orch.task(name="test_task")
    def test_task(msg):
        return msg

    return "test_task"


@pytest.fixture
def task(request):
    return request.getfixturevalue(request.param)


@pytest.mark.parametrize("task", ["hatchet_task", "hatchet_task_name"], indirect=True)
@pytest.mark.parametrize(
    ["sign_options", "expected_signature"],
    [
        [
            SignParamOptions(),
            orchestrator.TaskSignature(
                task_name="test_task",
                kwargs={},
                workflow_params={},
                task_identifiers={},
            ),
        ],
        [
            SignParamOptions(kwargs={"param1": "value1"}),
            orchestrator.TaskSignature(
                task_name="test_task",
                kwargs={"param1": "value1"},
                workflow_params={},
                task_identifiers={},
            ),
        ],
        [
            SignParamOptions(workflow_params={"workflow_param": "value"}),
            orchestrator.TaskSignature(
                task_name="test_task",
                kwargs={},
                workflow_params={"workflow_param": "value"},
                task_identifiers={},
            ),
        ],
        [
            SignParamOptions(creation_time=datetime(2023, 1, 1)),
            orchestrator.TaskSignature(
                task_name="test_task",
                kwargs={},
                workflow_params={},
                creation_time=datetime(2023, 1, 1),
                task_identifiers={},
            ),
        ],
        [
            SignParamOptions(task_identifiers={"identifier": "test_id"}),
            orchestrator.TaskSignature(
                task_name="test_task",
                kwargs={},
                workflow_params={},
                task_identifiers={"identifier": "test_id"},
            ),
        ],
        [
            SignParamOptions(success_callbacks=["TaskSignature:success_task_1"]),
            orchestrator.TaskSignature(
                task_name="test_task",
                kwargs={},
                workflow_params={},
                success_callbacks=["TaskSignature:success_task_1"],
                task_identifiers={},
            ),
        ],
        [
            SignParamOptions(error_callbacks=["TaskSignature:error_task_1"]),
            orchestrator.TaskSignature(
                task_name="test_task",
                kwargs={},
                workflow_params={},
                error_callbacks=["TaskSignature:error_task_1"],
                task_identifiers={},
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
            orchestrator.TaskSignature(
                task_name="test_task",
                kwargs={},
                workflow_params={},
                success_callbacks=[
                    "TaskSignature:success_task_1",
                    "TaskSignature:success_task_2",
                ],
                error_callbacks=["TaskSignature:error_task_1"],
                task_identifiers={},
            ),
        ],
        [
            SignParamOptions(
                kwargs={"param1": "value1", "param2": 42},
                workflow_params={"wp1": "val1", "wp2": True},
                creation_time=datetime(2023, 6, 15),
                task_identifiers={"id1": "test", "id2": "another"},
                success_callbacks=["TaskSignature:complex_success"],
                error_callbacks=[
                    "TaskSignature:complex_error_1",
                    "TaskSignature:complex_error_2",
                ],
            ),
            orchestrator.TaskSignature(
                task_name="test_task",
                kwargs={"param1": "value1", "param2": 42},
                workflow_params={"wp1": "val1", "wp2": True},
                creation_time=datetime(2023, 6, 15),
                success_callbacks=["TaskSignature:complex_success"],
                error_callbacks=[
                    "TaskSignature:complex_error_1",
                    "TaskSignature:complex_error_2",
                ],
                task_identifiers={"id1": "test", "id2": "another"},
            ),
        ],
    ],
)
@pytest.mark.asyncio
async def test__sign_task__sanity(
    task, sign_options, expected_signature: TaskSignature
):
    # Arrange
    sign_params = sign_options.to_dict()
    if not (isinstance(task, str) or expected_signature.model_validators):
        expected_signature.model_validators = task.input_validator

    # Act
    signature = await orchestrator.sign(task, **sign_params)

    # Assert
    signature.creation_time = expected_signature.creation_time
    assert signature.model_dump() == expected_signature.model_dump()
