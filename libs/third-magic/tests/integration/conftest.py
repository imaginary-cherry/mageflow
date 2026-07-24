import os
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
import rapyer
import redis.asyncio as aioredis

from thirdmagic.clients import BaseClientAdapter
from thirdmagic.signature import Signature

# Cascade needs a real Redis Stack (Functions + RedisJSON); fakeredis cannot emulate it.
REDIS_URL = os.environ.get("THIRDMAGIC_TEST_REDIS_URL", "redis://localhost:6379")


@pytest_asyncio.fixture
async def real_redis():
    client = aioredis.Redis.from_url(REDIS_URL, decode_responses=True)
    await client.flushall()
    await rapyer.init_rapyer(client)
    try:
        yield client
    finally:
        await client.flushall()
        await client.aclose()


@pytest.fixture
def mock_adapter():
    adapter = MagicMock(spec=BaseClientAdapter)
    Signature.ClientAdapter = adapter
    yield adapter
