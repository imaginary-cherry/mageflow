from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest_asyncio
from pydantic import BaseModel
from thirdmagic.signature import Signature
from thirdmagic.swarm.model import SwarmTaskSignature, SwarmConfig
from thirdmagic.swarm.state import PublishState

import mageflow
from mageflow.swarm.messages import (
    SwarmResultsMessage,
    SwarmErrorMessage,
    FillSwarmMessage,
)
from tests.integration.hatchet.models import ContextMessage
from tests.unit.conftest import create_mock_context_with_metadata, SwarmItemDoneSetup


@dataclass
class FailedSwarmSetup:
    swarm_task: SwarmTaskSignature
    task: Signature
    ctx: MagicMock
    msg: FillSwarmMessage


@dataclass
class CompletedSwarmSetup:
    swarm_task: SwarmTaskSignature
    task: Signature
    ctx: MagicMock
    msg: FillSwarmMessage


@dataclass
class SwarmItemFailedSetup:
    swarm_task: SwarmTaskSignature
    task: Signature
    ctx: MagicMock
    msg: BaseModel


@pytest_asyncio.fixture
async def publish_state():
    state = PublishState()
    await state.asave()
    return state


@pytest_asyncio.fixture
async def failed_swarm_setup(mock_task_def):
    # Arrange
    swarm_task = await mageflow.aswarm(
        task_name="test_swarm_failed",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1, stop_after_n_failures=1),
    )
    original_task = await mageflow.asign("item_task")
    task = await swarm_task.add_task(original_task)
    async with swarm_task.apipeline():
        swarm_task.tasks_left_to_run.remove_range(0, len(swarm_task.tasks_left_to_run))
        swarm_task.failed_tasks.append(task.key)
        swarm_task.current_running_tasks += 1

    ctx = create_mock_context_with_metadata()
    msg = FillSwarmMessage(swarm_task_id=swarm_task.key)

    return FailedSwarmSetup(swarm_task=swarm_task, task=task, ctx=ctx, msg=msg)


@pytest_asyncio.fixture
async def completed_swarm_setup(mock_task_def):
    # Arrange
    swarm_task = await mageflow.aswarm(
        task_name="test_swarm_completed",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1),
    )
    original_task = await mageflow.asign("item_task")
    task = await swarm_task.add_task(original_task)

    # Mark task as finished and swarm as closed/done
    async with swarm_task.apipeline():
        swarm_task.tasks_left_to_run.remove_range(0, len(swarm_task.tasks_left_to_run))
        swarm_task.finished_tasks.append(task.key)
        swarm_task.is_swarm_closed = True

    ctx = create_mock_context_with_metadata()
    msg = FillSwarmMessage(swarm_task_id=swarm_task.key)

    return CompletedSwarmSetup(swarm_task=swarm_task, task=task, ctx=ctx, msg=msg)


@pytest_asyncio.fixture
async def swarm_item_failed_setup(swarm_setup):
    swarm_task, task, ctx = swarm_setup
    msg = SwarmErrorMessage(swarm_task_id=swarm_task.key, swarm_item_id=task.key)

    return SwarmItemFailedSetup(swarm_task=swarm_task, task=task, ctx=ctx, msg=msg)


@pytest_asyncio.fixture
async def swarm_item_done_setup(swarm_setup):
    swarm_task, task, ctx = swarm_setup
    msg = SwarmResultsMessage(
        mageflow_results=42,
        swarm_task_id=swarm_task.key,
        swarm_item_id=task.key,
    )

    return SwarmItemDoneSetup(swarm_task=swarm_task, task=task, ctx=ctx, msg=msg)
