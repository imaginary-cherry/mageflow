from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
import rapyer
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
class FailingBatchTaskRunTracker:
    called_instances: list = field(default_factory=list)
    fail_on_call: int = 0
    should_fail: bool = True

    def reset_failure(self):
        self.should_fail = False


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

    ctx = create_mock_context_with_metadata()
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

    ctx = create_mock_context_with_metadata()
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
    msg = EmptyModel(swarm_task_id=swarm_task.key, swarm_item_id=batch_task.key)

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


@pytest.fixture
def failing_mock_task_run():
    tracker = FailingBatchTaskRunTracker()

    async def track_calls_with_failure(self, *args, **kwargs):
        tracker.called_instances.append(self)
        if tracker.should_fail and tracker.fail_on_call > 0:
            if len(tracker.called_instances) >= tracker.fail_on_call:
                raise RuntimeError("Simulated aio_run_no_wait failure")
        return None

    with patch.object(TaskSignature, "aio_run_no_wait", new=track_calls_with_failure):
        yield tracker


async def swarm_with_running_tasks(
    original_tasks: list[TaskSignature],
    task_to_run: int = None,
    max_concurrency: int = 5,
) -> tuple[SwarmTaskSignature, PublishState, list[str]]:
    swarm_signature = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=max_concurrency),
    )
    await rapyer.ainsert(swarm_signature, *original_tasks)
    publish_state = await PublishState.aget(swarm_signature.publishing_state_id)
    tasks_to_run = task_to_run or len(original_tasks)

    batch_tasks = [
        await swarm_signature.add_task(original_task)
        for original_task in original_tasks
    ]
    task_keys = [task.key for task in batch_tasks]
    task_keys = task_keys[:tasks_to_run]
    await swarm_signature.tasks_left_to_run.aextend(task_keys)
    return swarm_signature, publish_state, task_keys
