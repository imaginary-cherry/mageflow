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


async def _has_json_module(client: aioredis.Redis) -> bool:
    modules = await client.execute_command("MODULE", "LIST")
    names = {
        (m[1].decode() if isinstance(m[1], bytes) else m[1])
        for m in modules
        if len(m) > 1
    }
    return "ReJSON" in names or "json" in names


@pytest_asyncio.fixture
async def real_redis():
    client = aioredis.Redis.from_url(REDIS_URL)
    try:
        await client.ping()
    except Exception:
        pytest.skip(f"No Redis reachable at {REDIS_URL}")
    if not await _has_json_module(client):
        await client.aclose()
        pytest.skip(f"Redis at {REDIS_URL} lacks the RedisJSON module")
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
