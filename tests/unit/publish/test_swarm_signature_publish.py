from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from hatchet_sdk.clients.admin import TriggerWorkflowOptions

import mageflow
from mageflow.invokers.hatchet import HatchetInvoker
from mageflow.swarm.consts import ON_SWARM_START
from mageflow.swarm.messages import SwarmMessage
from mageflow.swarm.model import SwarmTaskSignature, SwarmConfig
from tests.integration.hatchet.models import ContextMessage


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
