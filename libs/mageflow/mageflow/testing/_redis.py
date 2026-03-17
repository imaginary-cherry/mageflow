import os
from enum import Enum
from pathlib import Path

import pytest
import pytest_asyncio
import rapyer

from mageflow.testing._config import _read_testing_config


class BackendOptions(str, Enum):
    TESTCONTAINERS = "testcontainers"
    FAKE_REDIS = "fakeredis"


def _get_backend() -> BackendOptions:
    """
    Return the configured Redis backend: 'testcontainers' (default) or 'fakeredis'.

    Checks MAGEFLOW_TESTING_BACKEND env var first, then falls back to pyproject.toml config.
    """
    env_backend = os.environ.get("MAGEFLOW_TESTING_BACKEND")
    if not env_backend:
        config = _read_testing_config(Path.cwd())
        env_backend = config.get("backend", "testcontainers")
    if env_backend == "fakeredis":
        return BackendOptions.FAKE_REDIS
    return BackendOptions.TESTCONTAINERS


@pytest.fixture(scope="session")
def _mageflow_redis_container():
    if _get_backend() == "fakeredis":
        yield None
        return
    from testcontainers.redis import AsyncRedisContainer

    with AsyncRedisContainer(image="redis/redis-stack-server:7.2.0-v13") as container:
        yield container


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _mageflow_redis_client(_mageflow_redis_container):
    if _mageflow_redis_container is None:
        import fakeredis

        client = fakeredis.aioredis.FakeRedis(decode_responses=True)
        yield client
        await client.aclose()
        return
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
