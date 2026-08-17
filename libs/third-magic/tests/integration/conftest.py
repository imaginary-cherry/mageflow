import warnings
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
import rapyer

from thirdmagic.clients import BaseClientAdapter
from thirdmagic.signature import Signature

# Cascade needs a real Redis Stack (Functions + RedisJSON); fakeredis cannot emulate it.
REDIS_STACK_IMAGE = "redis/redis-stack-server:7.2.0-v13"


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _redis_container():
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="The @wait_container_is_ready decorator is deprecated.*",
            category=DeprecationWarning,
        )
        from testcontainers.redis import AsyncRedisContainer

    with AsyncRedisContainer(image=REDIS_STACK_IMAGE) as container:
        client = await container.get_async_client(decode_responses=True)
        yield client
        await client.aclose()


@pytest_asyncio.fixture(loop_scope="session")
async def real_redis(_redis_container):
    await _redis_container.flushall()
    await rapyer.init_rapyer(_redis_container)
    try:
        yield _redis_container
    finally:
        await rapyer.teardown_rapyer()
        await _redis_container.flushall()


@pytest.fixture
def mock_adapter():
    adapter = MagicMock(spec=BaseClientAdapter)
    Signature.ClientAdapter = adapter
    yield adapter
