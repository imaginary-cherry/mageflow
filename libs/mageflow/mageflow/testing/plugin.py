import pytest
import pytest_asyncio
from thirdmagic.signature import Signature
from thirdmagic.task_def import MageflowTaskDefinition

from mageflow.testing._adapter import TestClientAdapter
from mageflow.testing._config import _load_client, _read_testing_config


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "mageflow(...): configure mageflow testing fixture for this test",
    )


@pytest.fixture(scope="session")
def _mageflow_testing_config(request):
    return _read_testing_config(request.config.rootdir)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _mageflow_redis_client(_mageflow_testing_config):
    from mageflow.testing._redis import BackendOptions, _get_backend

    backend = _get_backend(_mageflow_testing_config)
    if backend == BackendOptions.FAKE_REDIS:
        import fakeredis

        client = fakeredis.aioredis.FakeRedis(decode_responses=True)
        yield client
        await client.aclose()
    else:
        from testcontainers.redis import AsyncRedisContainer

        with AsyncRedisContainer(
            image="redis/redis-stack-server:7.2.0-v13"
        ) as container:
            client = await container.get_async_client(decode_responses=True)
            yield client
        await client.aclose()


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def _mageflow_flush_redis(_mageflow_redis_client):
    yield
    await _mageflow_redis_client.flushdb()


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def _mageflow_init_rapyer(_mageflow_redis_client, _mageflow_flush_redis):
    import rapyer

    await rapyer.init_rapyer(_mageflow_redis_client, prefer_normal_json_dump=True)
    yield
    await rapyer.teardown_rapyer()


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def mageflow_client(
    request,
    _mageflow_redis_client,
    _mageflow_init_rapyer,
    _mageflow_testing_config,
):
    marker = request.node.get_closest_marker("mageflow")
    overrides = marker.kwargs if marker else {}

    client_path = (
        overrides["client"]
        if "client" in overrides
        else _mageflow_testing_config.get("client")
    )
    local_execution = (
        overrides["local_execution"]
        if "local_execution" in overrides
        else _mageflow_testing_config.get("local_execution", False)
    )
    task_defs = {}
    if client_path:
        real_client = _load_client(client_path)
        task_def_list = real_client._task_defs
        await MageflowTaskDefinition.ainsert(*task_def_list)
        for task_def in task_def_list:
            task_defs[task_def.task_name] = task_def

    adapter = TestClientAdapter(task_defs=task_defs, local_execution=local_execution)

    original_adapter = Signature.ClientAdapter
    Signature.ClientAdapter = adapter
    try:
        yield adapter
    finally:
        Signature.ClientAdapter = original_adapter
