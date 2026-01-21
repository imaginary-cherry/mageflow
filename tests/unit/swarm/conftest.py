from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from hatchet_sdk import Context
from rapyer.types import RedisInt

import mageflow
from mageflow.invokers.hatchet import HatchetInvoker
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.signature.model import TaskSignature
from mageflow.swarm.consts import (
    SWARM_TASK_ID_PARAM_NAME,
    SWARM_ITEM_TASK_ID_PARAM_NAME,
)
from mageflow.swarm.messages import SwarmResultsMessage
from mageflow.swarm.model import SwarmTaskSignature, BatchItemTaskSignature, SwarmConfig
from mageflow.swarm.state import PublishState
from tests.integration.hatchet.models import ContextMessage


@dataclass
class SwarmTestData:
    task_signatures: list
    swarm_signature: SwarmTaskSignature


@dataclass
class BatchTaskRunTracker:
    called_instances: list


@dataclass
class SwarmItemDoneSetup:
    swarm_task: SwarmTaskSignature
    batch_task: BatchItemTaskSignature
    item_task: TaskSignature
    ctx: MagicMock
    msg: SwarmResultsMessage


@pytest_asyncio.fixture
async def publish_state():
    state = PublishState()
    await state.asave()
    return state


@pytest_asyncio.fixture
async def swarm_item_done_setup(create_mock_context_with_metadata):
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1),
    )
    swarm_item_task = await mageflow.sign("item_task")
    batch_task = await swarm_task.add_task(swarm_item_task)
    async with swarm_task.apipeline():
        swarm_task.current_running_tasks += 1
        swarm_task.tasks.append(batch_task.key)

    item_task = TaskSignature(task_name="item_task", model_validators=ContextMessage)
    await item_task.asave()

    ctx = create_mock_context_with_metadata(
        task_id=item_task.key,
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_task.key,
    )
    msg = SwarmResultsMessage(
        results=42,
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


@pytest_asyncio.fixture
async def swarm_with_tasks(publish_state):
    swarm_task_signature_1 = TaskSignature(
        task_name="swarm_task_1", model_validators=ContextMessage
    )
    await swarm_task_signature_1.asave()

    swarm_task_signature_2 = TaskSignature(
        task_name="swarm_task_2", model_validators=ContextMessage
    )
    await swarm_task_signature_2.asave()

    swarm_task_signature_3 = TaskSignature(
        task_name="swarm_task_3", model_validators=ContextMessage
    )
    await swarm_task_signature_3.asave()

    task_signatures = [
        swarm_task_signature_1,
        swarm_task_signature_2,
        swarm_task_signature_3,
    ]

    swarm_signature = SwarmTaskSignature(
        task_name="test_swarm",
        model_validators=ContextMessage,
        tasks=[task.key for task in task_signatures],
        publishing_state_id=publish_state.key,
    )
    await swarm_signature.asave()

    return SwarmTestData(
        task_signatures=task_signatures, swarm_signature=swarm_signature
    )


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=Context)
    ctx.log = MagicMock()
    ctx.additional_metadata = {}
    return ctx


@pytest.fixture
def create_mock_context_with_metadata():
    def _create(task_id=None, swarm_task_id=None, swarm_item_id=None):
        ctx = MagicMock(spec=Context)
        ctx.log = MagicMock()
        metadata = {}
        if task_id is not None:
            metadata[TASK_ID_PARAM_NAME] = task_id
        if swarm_task_id is not None:
            metadata[SWARM_TASK_ID_PARAM_NAME] = swarm_task_id
        if swarm_item_id is not None:
            metadata[SWARM_ITEM_TASK_ID_PARAM_NAME] = swarm_item_id
        ctx.additional_metadata = {"task_data": metadata}
        return ctx

    return _create


@pytest.fixture
def mock_close_swarm():
    with patch.object(
        SwarmTaskSignature, "close_swarm", new_callable=AsyncMock
    ) as mock_close:
        yield mock_close


@pytest.fixture
def mock_task_aio_run_no_wait():
    with patch.object(
        TaskSignature, "aio_run_no_wait", new_callable=AsyncMock
    ) as mock_run:
        yield mock_run


@pytest.fixture
def mock_fill_running_tasks():
    with patch.object(HatchetInvoker, "wait_task", new_callable=AsyncMock) as mock_fill:
        yield mock_fill


@pytest.fixture
def mock_fill_running_tasks_zero():
    with patch.object(HatchetInvoker, "wait_task", new_callable=AsyncMock) as mock_fill:
        yield mock_fill


@pytest.fixture
def mock_activate_success():
    with patch.object(
        SwarmTaskSignature, "activate_success", new_callable=AsyncMock
    ) as mock_success:
        yield mock_success


@pytest.fixture
def mock_activate_error():
    with patch.object(
        SwarmTaskSignature, "activate_error", new_callable=AsyncMock
    ) as mock_error:
        yield mock_error


@pytest.fixture
def mock_swarm_remove():
    with patch.object(
        SwarmTaskSignature, "remove", new_callable=AsyncMock
    ) as mock_remove:
        yield mock_remove


@pytest.fixture
def mock_handle_finish_tasks_error():
    with patch.object(
        HatchetInvoker, "wait_task", side_effect=RuntimeError("Finish tasks error")
    ) as mock_finish:
        yield mock_finish


@pytest.fixture
def mock_redis_int_increase_error():
    with patch.object(
        RedisInt, "increase", side_effect=RuntimeError("Redis error")
    ) as mock_increase:
        yield mock_increase


@pytest.fixture
def mock_activate_success_error():
    with patch.object(
        SwarmTaskSignature,
        "activate_success",
        side_effect=RuntimeError("Callback error"),
    ) as mock_success:
        yield mock_success


@pytest.fixture
def mock_batch_task_run():
    called_instances = []

    async def track_calls(self, *args, **kwargs):
        called_instances.append(self)
        return None

    with patch.object(BatchItemTaskSignature, "aio_run_no_wait", new=track_calls):
        yield BatchTaskRunTracker(called_instances=called_instances)
