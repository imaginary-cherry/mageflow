import pytest
import pytest_asyncio
from thirdmagic.signature import Signature
from thirdmagic.task_def import MageflowTaskDefinition

from mageflow.testing._adapter import TestClientAdapter
from mageflow.testing._config import _load_client, _read_testing_config
from mageflow.testing._redis import (
    _mageflow_flush_redis,
    _mageflow_init_rapyer,
    _mageflow_redis_client,
    _mageflow_redis_container,
)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "mageflow(...): configure mageflow testing fixture for this test",
    )


@pytest.fixture(scope="session")
def _mageflow_testing_config(request):
    return _read_testing_config(request.config.rootdir)


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def mageflow_client(
    request,
    _mageflow_redis_client,
    _mageflow_init_rapyer,
    _mageflow_testing_config,
):
    marker = request.node.get_closest_marker("mageflow")
    overrides = marker.kwargs if marker else {}

    client_path = overrides.get("client") or _mageflow_testing_config.get("client")
    task_defs = {}
    if client_path:
        real_client = _load_client(client_path)
        for task_def in real_client._task_defs:
            await MageflowTaskDefinition.ainsert(task_def)
            task_defs[task_def.task_name] = task_def

    adapter = TestClientAdapter(task_defs=task_defs)

    original_adapter = Signature.ClientAdapter
    Signature.ClientAdapter = adapter
    try:
        yield adapter
    finally:
        Signature.ClientAdapter = original_adapter
