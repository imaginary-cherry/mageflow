from dataclasses import dataclass
from unittest.mock import AsyncMock, patch, MagicMock

import fakeredis
import pytest
import pytest_asyncio
import rapyer
from hatchet_sdk import Hatchet, ClientConfig, Context

import mageflow
from mageflow.invokers.hatchet import HatchetInvoker
from mageflow.signature.consts import TASK_ID_PARAM_NAME
from mageflow.signature.model import TaskSignature
from mageflow.startup import update_register_signature_models, mageflow_config
from mageflow.swarm.consts import (
    SWARM_TASK_ID_PARAM_NAME,
    SWARM_ITEM_TASK_ID_PARAM_NAME,
)
from mageflow.swarm.messages import SwarmResultsMessage
from mageflow.swarm.model import SwarmTaskSignature, BatchItemTaskSignature, SwarmConfig
from tests.integration.hatchet.models import ContextMessage
from tests.unit.change_status.conftest import ChainTestData

pytest.register_assert_rewrite("tests.assertions")


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


@pytest_asyncio.fixture(autouse=True, scope="function")
async def redis_client():
    await update_register_signature_models()
    client = fakeredis.aioredis.FakeRedis()
    mageflow_config.redis_client = redis_client
    await client.flushall()
    try:
        yield client
    finally:
        await client.flushall()
        await client.aclose()


@pytest.fixture(autouse=True, scope="function")
def hatchet_mock():
    config_obj = ClientConfig(
        token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJodHRwczovL2xvY2FsaG9zdCIsImV4cCI6NDkwNTQ3NzYyNiwiZ3JwY19icm9hZGNhc3RfYWRkcmVzcyI6Imh0dHBzOi8vbG9jYWxob3N0IiwiaWF0IjoxNzUxODc3NjI2LCJpc3MiOiJodHRwczovL2xvY2FsaG9zdCIsInNlcnZlcl91cmwiOiJodHRwczovL2xvY2FsaG9zdCIsInN1YiI6IjdlY2U4ZTk4LWNiMjMtNDg3Ny1hZGNlLWFmYTBiNDMxYTgyMyIsInRva2VuX2lkIjoiNjk0MjBkOGMtMTQ4NS00NGRlLWFmY2YtMDlkYzM5NmJiYzI0In0.l2yHtg1ZGJSkge6MnLXj_zGyg1w_6LZ7ZuyyNrWORnc",
        tls_strategy="tls",
    )
    hatchet = Hatchet(config=config_obj)
    mageflow_config.hatchet_client = hatchet

    yield hatchet


@pytest.fixture()
def orch(hatchet_mock, redis_client):
    yield mageflow.Mageflow(hatchet_mock, redis_client)


@pytest_asyncio.fixture(autouse=True, scope="function")
async def init_models(redis_client):
    await rapyer.init_rapyer(redis_client)


@pytest.fixture
def mock_aio_run_no_wait():
    with patch(
        f"{TaskSignature.__module__}.{TaskSignature.__name__}.aio_run_no_wait",
        new_callable=AsyncMock,
    ) as mock_aio_run:
        yield mock_aio_run


@pytest_asyncio.fixture
async def chain_with_tasks():
    task_signatures = [
        await mageflow.sign(f"chain_task_{i}", model_validators=ContextMessage)
        for i in range(1, 4)
    ]

    chain_signature = await mageflow.chain([task.key for task in task_signatures])

    return ChainTestData(
        task_signatures=task_signatures, chain_signature=chain_signature
    )


@pytest.fixture
def mock_close_swarm():
    with patch.object(
        SwarmTaskSignature, "close_swarm", new_callable=AsyncMock
    ) as mock_close:
        yield mock_close


@pytest.fixture
def mock_batch_task_run():
    called_instances = []

    async def track_calls(self, *args, **kwargs):
        called_instances.append(self)
        return None

    with patch.object(BatchItemTaskSignature, "aio_run_no_wait", new=track_calls):
        yield BatchTaskRunTracker(called_instances=called_instances)


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
def mock_handle_finish_tasks_error():
    with patch.object(
        HatchetInvoker, "wait_task", side_effect=RuntimeError("Finish tasks error")
    ) as mock_finish:
        yield mock_finish


@pytest.fixture
def mock_activate_success():
    with patch.object(
        SwarmTaskSignature, "activate_success", new_callable=AsyncMock
    ) as mock_success:
        yield mock_success


@pytest.fixture
def mock_activate_success_error():
    with patch.object(
        SwarmTaskSignature, "activate_success", side_effect=RuntimeError()
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


def create_mock_context_with_metadata(
    task_id=None, swarm_task_id=None, swarm_item_id=None
):
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


@pytest_asyncio.fixture
async def swarm_setup():
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

    item_task = await mageflow.sign("item_task", model_validators=ContextMessage)

    ctx = create_mock_context_with_metadata(
        task_id=item_task.key,
        swarm_task_id=swarm_task.key,
        swarm_item_id=batch_task.key,
    )
    return [swarm_task, batch_task, item_task, ctx]


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=Context)
    ctx.log = MagicMock()
    ctx.additional_metadata = {}
    return ctx


@pytest_asyncio.fixture
async def empty_swarm():
    swarm_task = await mageflow.swarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=2),
        is_swarm_closed=False,
    )
    yield swarm_task


@pytest_asyncio.fixture
async def swarm_task(empty_swarm: SwarmTaskSignature):
    swarm_task = empty_swarm
    task = await mageflow.sign("item_task")
    await swarm_task.add_task(task)
    return swarm_task


@pytest_asyncio.fixture
async def swarm_with_ready_task(swarm_task: SwarmTaskSignature):
    await swarm_task.tasks_left_to_run.aappend(swarm_task.tasks[0])
    yield swarm_task
