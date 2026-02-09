from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from hatchet_sdk.clients.admin import TriggerWorkflowOptions

import mageflow
from mageflow.errors import TooManyTasksError, SwarmIsCanceledError
from mageflow.invokers.hatchet import HatchetInvoker
from mageflow.signature.model import TaskSignature
from mageflow.signature.status import SignatureStatus
from mageflow.swarm.consts import ON_SWARM_START
from mageflow.swarm.messages import SwarmMessage
from mageflow.swarm.model import SwarmTaskSignature, SwarmConfig
from tests.integration.hatchet.models import ContextMessage
from tests.unit.conftest import TaskRunTracker, assert_task_were_published


@dataclass
class RunTaskCall:
    task_name: str
    msg: Any
    kwargs: dict = field(default_factory=dict)


@pytest.fixture
def mock_run_task():
    calls: list[RunTaskCall] = []

    async def capture(task_name, msg, validator=None, **kwargs):
        calls.append(RunTaskCall(task_name=task_name, msg=msg, kwargs=kwargs))

    with patch.object(HatchetInvoker, "run_task", side_effect=capture):
        yield calls


@pytest_asyncio.fixture
async def swarm_with_kwargs():
    swarm_kwargs = {"existing": "value"}
    swarm = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        kwargs=swarm_kwargs,
        config=SwarmConfig(max_concurrency=5),
    )
    return swarm, swarm_kwargs


@pytest.mark.asyncio
async def test_aio_run_no_wait_updates_kwargs_from_message(
    mock_run_task: list[RunTaskCall],
    swarm_with_kwargs: tuple[SwarmTaskSignature, dict],
):
    # Arrange
    swarm, swarm_kwargs = swarm_with_kwargs
    base_data = {"new": "data"}
    msg = ContextMessage(base_data=base_data)

    # Act
    await swarm.aio_run_no_wait(msg)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm.key)
    assert reloaded_swarm.kwargs["base_data"] == base_data
    assert reloaded_swarm.kwargs["existing"] == swarm_kwargs["existing"]


@pytest.mark.asyncio
async def test_aio_run_no_wait_calls_workflow_with_correct_params(
    mock_run_task: list[RunTaskCall],
    swarm_with_kwargs: tuple[SwarmTaskSignature, dict],
):
    # Arrange
    swarm, swarm_kwargs = swarm_with_kwargs
    base_data = {"swarm": "data"}
    test_ctx = {"ctx": "swarm_ctx"}
    msg = ContextMessage(base_data=base_data, test_ctx=test_ctx)

    # Act
    await swarm.aio_run_no_wait(msg)

    # Assert
    assert len(mock_run_task) == 1
    call = mock_run_task[0]
    assert call.task_name == ON_SWARM_START
    assert isinstance(call.msg, SwarmMessage)
    assert call.msg.swarm_task_id == swarm.key


@pytest.mark.asyncio
async def test_aio_run_no_wait_passes_hatchet_options(
    mock_run_task: list[RunTaskCall],
    swarm_with_kwargs: tuple[SwarmTaskSignature, dict],
):
    # Arrange
    swarm, _ = swarm_with_kwargs
    msg = ContextMessage(base_data={"swarm": "data"})
    options = TriggerWorkflowOptions(additional_metadata={"swarm_custom": "metadata"})

    # Act
    await swarm.aio_run_no_wait(msg, options=options)

    # Assert
    assert len(mock_run_task) == 1
    call = mock_run_task[0]
    assert call.kwargs.get("options") == options


@pytest.mark.asyncio
async def test_aio_run_in_swarm_adds_task_and_publishes_it(
    mock_task_run: TaskRunTracker,
    swarm_with_kwargs: tuple[SwarmTaskSignature, dict],
):
    # Arrange
    swarm, _ = swarm_with_kwargs
    sub_task = await mageflow.sign("sub_task", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"key": "value"})

    # Act
    published = await swarm.aio_run_in_swarm(sub_task, msg)

    # Assert
    reloaded_swarm = await SwarmTaskSignature.get_safe(swarm.key)
    assert published is not None
    assert sub_task.key in reloaded_swarm.tasks
    assert_task_were_published(mock_task_run, [published.key])


@pytest.mark.asyncio
async def test_aio_run_in_swarm_updates_task_kwargs_with_message_data(
    mock_task_aio_run_no_wait,
    swarm_with_kwargs: tuple[SwarmTaskSignature, dict],
):
    # Arrange
    swarm, _ = swarm_with_kwargs
    sub_task = await mageflow.sign("sub_task", model_validators=ContextMessage)
    base_data = {"msg": "data"}
    test_ctx = {"ctx": "info"}
    msg = ContextMessage(base_data=base_data, test_ctx=test_ctx)

    # Act
    await swarm.aio_run_in_swarm(sub_task, msg)

    # Assert
    reloaded_task = await TaskSignature.get_safe(sub_task.key)
    assert reloaded_task.kwargs["base_data"] == base_data
    assert reloaded_task.kwargs["test_ctx"] == test_ctx


@pytest.mark.asyncio
async def test_aio_run_in_swarm_passes_options_to_published_task(
    mock_task_aio_run_no_wait,
    swarm_with_kwargs: tuple[SwarmTaskSignature, dict],
):
    # Arrange
    swarm, _ = swarm_with_kwargs
    sub_task = await mageflow.sign("sub_task", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"key": "val"})
    options = TriggerWorkflowOptions(additional_metadata={"custom": "meta"})

    # Act
    await swarm.aio_run_in_swarm(sub_task, msg, options=options)

    # Assert
    mock_task_aio_run_no_wait.assert_called_once()
    call_kwargs = mock_task_aio_run_no_wait.call_args.kwargs
    assert call_kwargs.get("options") == options


@pytest.mark.asyncio
async def test_aio_run_in_swarm_at_max_concurrency_returns_empty(
    mock_task_aio_run_no_wait,
):
    # Arrange
    swarm = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=2),
    )
    async with swarm.apipeline():
        swarm.current_running_tasks += 2
    sub_task = await mageflow.sign("sub_task", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"key": "val"})

    # Act
    result = await swarm.aio_run_in_swarm(sub_task, msg)

    # Assert
    assert result == []
    mock_task_aio_run_no_wait.assert_not_called()


@pytest.mark.asyncio
async def test_aio_run_in_swarm_close_on_max_task_true_triggers_close_swarm(
    mock_close_swarm,
    mock_task_aio_run_no_wait,
):
    # Arrange
    swarm = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_task_allowed=1),
    )
    sub_task = await mageflow.sign("sub_task", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"key": "val"})

    # Act
    await swarm.aio_run_in_swarm(sub_task, msg, close_on_max_task=True)

    # Assert
    mock_close_swarm.assert_called_once()


@pytest.mark.asyncio
async def test_aio_run_in_swarm_close_on_max_task_false_does_not_close_swarm(
    mock_close_swarm,
    mock_task_aio_run_no_wait,
):
    # Arrange
    swarm = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_task_allowed=1),
    )
    sub_task = await mageflow.sign("sub_task", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"key": "val"})

    # Act
    await swarm.aio_run_in_swarm(sub_task, msg, close_on_max_task=False)

    # Assert
    mock_close_swarm.assert_not_called()


@pytest.mark.asyncio
async def test_aio_run_in_swarm_raises_too_many_tasks_error_when_over_limit():
    # Arrange
    swarm = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_task_allowed=1),
    )
    first_task = await mageflow.sign("first_task", model_validators=ContextMessage)
    await swarm.add_task(first_task, close_on_max_task=False)
    second_task = await mageflow.sign("second_task", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"key": "val"})

    # Act & Assert
    with pytest.raises(TooManyTasksError):
        await swarm.aio_run_in_swarm(second_task, msg)


@pytest.mark.asyncio
async def test_aio_run_in_swarm_raises_swarm_is_canceled_error():
    # Arrange
    swarm = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
    )
    swarm.task_status.status = SignatureStatus.CANCELED
    await swarm.asave()
    sub_task = await mageflow.sign("sub_task", model_validators=ContextMessage)
    msg = ContextMessage(base_data={"key": "val"})

    # Act & Assert
    with pytest.raises(SwarmIsCanceledError):
        await swarm.aio_run_in_swarm(sub_task, msg)
