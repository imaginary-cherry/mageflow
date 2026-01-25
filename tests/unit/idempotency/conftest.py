from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest_asyncio
from hatchet_sdk.runnables.types import EmptyModel
from pydantic import BaseModel

import mageflow
from mageflow.signature.model import TaskSignature
from mageflow.swarm.messages import SwarmMessage, SwarmResultsMessage
from mageflow.swarm.model import SwarmTaskSignature, BatchItemTaskSignature, SwarmConfig
from mageflow.swarm.state import PublishState
from tests.integration.hatchet.models import ContextMessage
from tests.unit.conftest import create_mock_context_with_metadata, SwarmItemDoneSetup


@dataclass
class FailedSwarmSetup:
    swarm_task: SwarmTaskSignature
    batch_task: BatchItemTaskSignature
    original_task: TaskSignature
    ctx: MagicMock
    msg: SwarmMessage


@dataclass
class CompletedSwarmSetup:
    swarm_task: SwarmTaskSignature
    batch_task: BatchItemTaskSignature
    original_task: TaskSignature
    ctx: MagicMock
    msg: SwarmMessage


@dataclass
class SwarmItemFailedSetup:
    swarm_task: SwarmTaskSignature
    batch_task: BatchItemTaskSignature
    item_task: TaskSignature
    ctx: MagicMock
    msg: BaseModel


@pytest_asyncio.fixture
async def publish_state():
    state = PublishState()
    await state.asave()
    return state


@pytest_asyncio.fixture
async def failed_swarm_setup():
    # Arrange
    swarm_task = await mageflow.swarm(
        task_name="test_swarm_failed",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1, stop_after_n_failures=1),
    )
    original_task = await mageflow.sign("item_task")
    batch_task = await swarm_task.add_task(original_task)
    async with swarm_task.apipeline():
        swarm_task.failed_tasks.append(batch_task.key)
        swarm_task.current_running_tasks += 1

    ctx = create_mock_context_with_metadata(swarm_task_id=swarm_task.key)
    msg = SwarmMessage(swarm_task_id=swarm_task.key)

    return FailedSwarmSetup(
        swarm_task=swarm_task,
        batch_task=batch_task,
        original_task=original_task,
        ctx=ctx,
        msg=msg,
    )


@pytest_asyncio.fixture
async def completed_swarm_setup():
    # Arrange
    swarm_task = await mageflow.swarm(
        task_name="test_swarm_completed",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1),
    )
    original_task = await mageflow.sign("item_task")
    batch_task = await swarm_task.add_task(original_task)

    # Mark task as finished and swarm as closed/done
    async with swarm_task.apipeline():
        swarm_task.finished_tasks.append(batch_task.key)

    # Use aupdate for scalar fields as apipeline doesn't persist them
    async with swarm_task.alock() as locked_swarm:
        await locked_swarm.aupdate(is_swarm_closed=True)

    ctx = create_mock_context_with_metadata(swarm_task_id=swarm_task.key)
    msg = SwarmMessage(swarm_task_id=swarm_task.key)

    return CompletedSwarmSetup(
        swarm_task=swarm_task,
        batch_task=batch_task,
        original_task=original_task,
        ctx=ctx,
        msg=msg,
    )


@pytest_asyncio.fixture
async def swarm_item_failed_setup(swarm_setup):
    swarm_task, batch_task, item_task, ctx = swarm_setup
    msg = EmptyModel()

    return SwarmItemFailedSetup(
        swarm_task=swarm_task,
        batch_task=batch_task,
        item_task=item_task,
        ctx=ctx,
        msg=msg,
    )


@pytest_asyncio.fixture
async def swarm_item_done_setup(swarm_setup):
    swarm_task, batch_task, item_task, ctx = swarm_setup
    msg = SwarmResultsMessage(
        mageflow_results=42,
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_task.key,
    )

    return SwarmItemDoneSetup(
        swarm_task=swarm_task,
        batch_task=batch_task,
        item_task=item_task,
        ctx=ctx,
        msg=msg,
    )


@dataclass
class BatchItemRunSetup:
    swarm_task: SwarmTaskSignature
    batch_task: BatchItemTaskSignature
    original_task: TaskSignature
    msg: BaseModel


@pytest_asyncio.fixture
async def batch_item_run_setup(publish_state):
    swarm_task = await mageflow.swarm(
        task_name="test_swarm_batch_item",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=2),
    )
    original_task = await mageflow.sign("item_task", model_validators=ContextMessage)
    batch_task = await swarm_task.add_task(original_task)
    msg = EmptyModel()

    return BatchItemRunSetup(
        swarm_task=swarm_task,
        batch_task=batch_task,
        original_task=original_task,
        msg=msg,
    )


@pytest_asyncio.fixture
async def batch_item_run_setup_at_max_concurrency(publish_state):
    swarm_task = await mageflow.swarm(
        task_name="test_swarm_batch_item_max",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=2),
    )
    original_task = await mageflow.sign("item_task", model_validators=ContextMessage)
    batch_task = await swarm_task.add_task(original_task)

    async with swarm_task.alock() as locked_swarm:
        await locked_swarm.current_running_tasks.aincrease(2)

    msg = EmptyModel()

    return BatchItemRunSetup(
        swarm_task=swarm_task,
        batch_task=batch_task,
        original_task=original_task,
        msg=msg,
    )
