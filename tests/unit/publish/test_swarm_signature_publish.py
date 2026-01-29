import pytest
import pytest_asyncio
from hatchet_sdk.clients.admin import TriggerWorkflowOptions

import mageflow
from mageflow.swarm.consts import ON_SWARM_START, SWARM_TASK_ID_PARAM_NAME
from mageflow.swarm.model import SwarmTaskSignature, SwarmConfig
from tests.integration.hatchet.models import ContextMessage
from tests.unit.conftest import WorkflowCallCapture


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
    mock_workflow_run_with_args: list[WorkflowCallCapture],
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
    mock_workflow_run_with_args: list[WorkflowCallCapture],
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
    assert len(mock_workflow_run_with_args) == 1
    call = mock_workflow_run_with_args[0]
    assert call.workflow.config.name == ON_SWARM_START
    serialized = call.workflow._serialize_input(msg)
    assert serialized["base_data"] == base_data
    assert serialized["test_ctx"] == test_ctx
    assert serialized["existing"] == swarm_kwargs["existing"]
    assert serialized[SWARM_TASK_ID_PARAM_NAME] == swarm.key


@pytest.mark.asyncio
async def test_aio_run_no_wait_passes_hatchet_options(
    mock_workflow_run_with_args: list[WorkflowCallCapture],
    swarm_with_kwargs: tuple[SwarmTaskSignature, dict],
):
    # Arrange
    swarm, _ = swarm_with_kwargs
    msg = ContextMessage(base_data={"swarm": "data"})
    options = TriggerWorkflowOptions(additional_metadata={"swarm_custom": "metadata"})

    # Act
    await swarm.aio_run_no_wait(msg, options=options)

    # Assert
    assert len(mock_workflow_run_with_args) == 1
    call = mock_workflow_run_with_args[0]
    assert call.kwargs.get("options") == options
