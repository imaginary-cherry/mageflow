from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

import mageflow
from mageflow.swarm.messages import SwarmMessage
from mageflow.swarm.model import SwarmTaskSignature, SwarmConfig
from mageflow.workflows import MageflowWorkflow
from tests.integration.hatchet.models import ContextMessage
from tests.unit.conftest import create_mock_context_with_metadata


@dataclass
class CompletedSwarmWithSuccessCallback:
    swarm_task: SwarmTaskSignature
    ctx: MagicMock
    msg: SwarmMessage


@pytest_asyncio.fixture
async def completed_swarm_with_success_callback():
    # Arrange
    success_callback = await mageflow.sign(
        "unittest_success_callback_task", model_validators=ContextMessage
    )
    error_callback = await mageflow.sign(
        "unittest_error_callback_task", model_validators=ContextMessage
    )
    error_callback2 = await mageflow.sign(
        "unittest_error_callback_task", model_validators=ContextMessage
    )

    swarm_task = await mageflow.swarm(
        task_name="test_swarm_completed_with_callback",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1),
        success_callbacks=[success_callback],
        error_callbacks=[error_callback, error_callback2],
    )
    original_task = await mageflow.sign("item_task")
    batch_task = await swarm_task.add_task(original_task)

    async with swarm_task.apipeline():
        swarm_task.finished_tasks.append(batch_task.key)

    async with swarm_task.alock() as locked_swarm:
        await locked_swarm.aupdate(is_swarm_closed=True)

    ctx = create_mock_context_with_metadata(swarm_task_id=swarm_task.key)
    msg = SwarmMessage(swarm_task_id=swarm_task.key)

    return CompletedSwarmWithSuccessCallback(swarm_task=swarm_task, ctx=ctx, msg=msg)


@pytest.fixture
def mock_workflow_run():
    captured_workflows = []

    async def capture_and_mock(self, *args, **kwargs):
        captured_workflows.append(self)

    with patch.object(MageflowWorkflow, "aio_run_no_wait", capture_and_mock) as mock:
        mock.captured_workflows = captured_workflows
        yield mock
