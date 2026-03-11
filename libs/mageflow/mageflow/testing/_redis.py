import pytest
import pytest_asyncio
import rapyer
from testcontainers.redis import AsyncRedisContainer


@pytest.fixture(scope="session")
def _mageflow_redis_container():
    with AsyncRedisContainer(image="redis/redis-stack-server:7.2.0-v13") as container:
        yield container


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _mageflow_redis_client(_mageflow_redis_container):
    client = await _mageflow_redis_container.get_async_client(decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def _mageflow_flush_redis(_mageflow_redis_client):
    yield
    await _mageflow_redis_client.flushdb()


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def _mageflow_init_rapyer(_mageflow_redis_client, _mageflow_flush_redis):
    await rapyer.init_rapyer(_mageflow_redis_client, prefer_normal_json_dump=True)
    yield
    await rapyer.teardown_rapyer()
