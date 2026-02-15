from unittest.mock import MagicMock

import fakeredis
import pytest
import pytest_asyncio
import rapyer

from thirdmagic.clients import BaseClientAdapter
from thirdmagic.signature.model import TaskSignature


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
    TaskSignature.ClientAdapter = adapter
    yield adapter
