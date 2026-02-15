import pytest
import pytest_asyncio
from pydantic import TypeAdapter

from thirdmagic.task import MageflowTaskDefinition


def extract_hatchet_validator(workflow):
    validator = workflow.input_validator
    if isinstance(validator, TypeAdapter):
        validator = validator._type
    return validator


@pytest.fixture(autouse=True)
def client_adapter(mock_adapter):
    mock_adapter.extract_validator.side_effect = extract_hatchet_validator
    mock_adapter.task_name.side_effect = lambda fn: fn.name
    yield mock_adapter


@pytest.fixture
def hatchet_task(hatchet_mock):
    @hatchet_mock.task(name="test_task")
    def test_task(msg):
        return msg

    yield test_task


@pytest_asyncio.fixture
async def hatchet_task_name(hatchet_mock):
    task_name = "test_task"

    @hatchet_mock.task(name=task_name)
    def test_task(msg):
        return msg

    task = MageflowTaskDefinition(
        mageflow_task_name=task_name, task_name="real_task_name"
    )
    await task.asave()

    return task_name


@pytest.fixture
def task(request):
    return request.getfixturevalue(request.param)
