from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis
import pytest
import pytest_asyncio
import rapyer
from hatchet_sdk import ClientConfig, Hatchet

from thirdmagic.clients import BaseClientAdapter
from thirdmagic.signature import Signature
from thirdmagic.swarm import SwarmTaskSignature
from thirdmagic.task_def import MageflowTaskDefinition


@pytest_asyncio.fixture(autouse=True, scope="function")
async def redis_client():
    client = fakeredis.aioredis.FakeRedis()
    await client.flushall()
    try:
        yield client
    finally:
        await client.flushall()
        await client.aclose()


@pytest_asyncio.fixture(autouse=True, scope="function")
async def init_models(redis_client):
    await rapyer.init_rapyer(redis_client)


@pytest.fixture()
def mock_adapter():
    adapter = MagicMock(spec=BaseClientAdapter)
    Signature.ClientAdapter = adapter
    yield adapter


@pytest.fixture(autouse=True, scope="function")
def hatchet_mock():
    config_obj = ClientConfig(
        token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJodHRwczovL2xvY2FsaG9zdCIsImV4cCI6NDkwNTQ3NzYyNiwiZ3JwY19icm9hZGNhc3RfYWRkcmVzcyI6Imh0dHBzOi8vbG9jYWxob3N0IiwiaWF0IjoxNzUxODc3NjI2LCJpc3MiOiJodHRwczovL2xvY2FsaG9zdCIsInNlcnZlcl91cmwiOiJodHRwczovL2xvY2FsaG9zdCIsInN1YiI6IjdlY2U4ZTk4LWNiMjMtNDg3Ny1hZGNlLWFmYTBiNDMxYTgyMyIsInRva2VuX2lkIjoiNjk0MjBkOGMtMTQ4NS00NGRlLWFmY2YtMDlkYzM5NmJiYzI0In0.l2yHtg1ZGJSkge6MnLXj_zGyg1w_6LZ7ZuyyNrWORnc",
        tls_strategy="tls",
    )
    hatchet = Hatchet(config=config_obj)

    yield hatchet


@pytest.fixture
def mock_close_swarm():
    with patch.object(
        SwarmTaskSignature, "close_swarm", new_callable=AsyncMock
    ) as mock_close:
        yield mock_close


@pytest_asyncio.fixture
async def test_task_def():
    task_df = MageflowTaskDefinition(
        mageflow_task_name="test_task", task_name="test_task"
    )
    await task_df.asave()
    return task_df


@pytest.fixture
def mock_task_def():
    with patch.object(MageflowTaskDefinition, "afind_one") as mock_get:
        mock_get.side_effect = lambda task_name: MageflowTaskDefinition(
            mageflow_task_name=task_name, task_name=task_name
        )
        yield mock_get
