from dataclasses import dataclass
from unittest.mock import AsyncMock, patch, MagicMock

import fakeredis
import pytest
import pytest_asyncio
import rapyer
from hatchet_sdk import Hatchet, ClientConfig, Context
from thirdmagic.chain.model import ChainTaskSignature
from thirdmagic.clients import BaseClientAdapter
from thirdmagic.consts import TASK_ID_PARAM_NAME
from thirdmagic.signature.model import TaskSignature
from thirdmagic.swarm.model import SwarmTaskSignature, SwarmConfig
from thirdmagic.task import MageflowTaskDefinition

import mageflow
from mageflow.clients.hatchet.workflow import MageflowWorkflow
from mageflow.invokers.hatchet import HatchetInvoker
from mageflow.swarm.messages import SwarmResultsMessage
from tests.integration.hatchet.models import ContextMessage

pytest.register_assert_rewrite("tests.assertions")


@dataclass
class ChainTestData:
    task_signatures: list
    chain_signature: ChainTaskSignature


@dataclass
class WorkflowCallCapture:
    workflow: MageflowWorkflow
    args: tuple
    kwargs: dict


@dataclass
class SwarmItemDoneSetup:
    swarm_task: SwarmTaskSignature
    task: TaskSignature
    ctx: MagicMock
    msg: SwarmResultsMessage


@pytest_asyncio.fixture(autouse=True, scope="function")
async def redis_client():
    client = fakeredis.aioredis.FakeRedis()
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
        await mageflow.asign(f"chain_task_{i}", model_validators=ContextMessage)
        for i in range(1, 4)
    ]

    chain_signature = await mageflow.achain([task.key for task in task_signatures])

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
def mock_task_aio_run_no_wait():
    with patch.object(
        TaskSignature, "aio_run_no_wait", new_callable=AsyncMock
    ) as mock_run:
        yield mock_run


@pytest.fixture
def mock_invoker_wait_task():
    with patch.object(HatchetInvoker, "run_task", new_callable=AsyncMock) as mock_fill:
        yield mock_fill


@pytest.fixture
def mock_fill_running_tasks():
    with patch.object(
        SwarmTaskSignature, "fill_running_tasks", new_callable=AsyncMock
    ) as mock_fill:
        yield mock_fill


@pytest.fixture
def mock_handle_finish_tasks_error():
    with patch.object(
        HatchetInvoker, "run_task", side_effect=RuntimeError("Finish tasks error")
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
def mock_interrupt():
    with patch.object(
        SwarmTaskSignature, "interrupt", new_callable=AsyncMock
    ) as mock_error:
        yield mock_error


@pytest.fixture
def mock_swarm_remove():
    with patch.object(
        SwarmTaskSignature, "remove", new_callable=AsyncMock
    ) as mock_remove:
        yield mock_remove


def create_mock_context_with_metadata(task_id=None):
    ctx = MagicMock(spec=Context)
    ctx.log = MagicMock()
    metadata = {}
    if task_id is not None:
        metadata[TASK_ID_PARAM_NAME] = task_id
    ctx.additional_metadata = {"task_data": metadata}
    return ctx


@pytest_asyncio.fixture
async def swarm_setup(mock_task_def):
    swarm_task = await mageflow.aswarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=1),
    )
    swarm_item_task = await mageflow.asign("item_task")
    task = await swarm_task.add_task(swarm_item_task)
    async with swarm_task.apipeline():
        swarm_task.current_running_tasks += 1
        swarm_task.tasks_left_to_run.remove_range(0, len(swarm_task.tasks_left_to_run))

    ctx = create_mock_context_with_metadata()
    return [swarm_task, task, ctx]


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=Context)
    ctx.log = MagicMock()
    ctx.additional_metadata = {}
    return ctx


@pytest_asyncio.fixture
async def empty_swarm():
    swarm_task = await mageflow.aswarm(
        task_name="test_swarm",
        model_validators=ContextMessage,
        config=SwarmConfig(max_concurrency=2),
        is_swarm_closed=False,
    )
    yield swarm_task


@pytest_asyncio.fixture
async def swarm_task(empty_swarm: SwarmTaskSignature, mock_task_def):
    swarm_task = empty_swarm
    task = await mageflow.asign("item_task")
    await swarm_task.add_task(task)
    return swarm_task


@pytest.fixture
def mock_adapter():
    adapter = AsyncMock(spec=BaseClientAdapter)
    TaskSignature.ClientAdapter = adapter
    yield adapter


@pytest.fixture
def mock_workflow_run_with_args():
    captured_calls = []

    async def capture_and_mock(self, *args, **kwargs):
        captured_calls.append(
            WorkflowCallCapture(workflow=self, args=args, kwargs=kwargs)
        )

    with patch.object(MageflowWorkflow, "aio_run_no_wait", capture_and_mock):
        yield captured_calls


@pytest.fixture
def mock_task_def():
    with patch.object(MageflowTaskDefinition, "aget") as mock_get:
        mock_get.side_effect = lambda task_name, **kwargs: MageflowTaskDefinition(
            mageflow_task_name=task_name, task_name=task_name
        )
        yield mock_get
