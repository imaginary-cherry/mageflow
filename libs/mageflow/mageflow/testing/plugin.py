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
)

# Re-export redis fixtures so pytest discovers them via the pytest11 plugin entry point.
# Without this, external packages using mageflow_client fixture cannot resolve the
# _mageflow_redis_client / _mageflow_init_rapyer dependencies.
__all__ = [
    "_mageflow_redis_client",
    "_mageflow_flush_redis",
    "_mageflow_init_rapyer",
]


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
    local_execution = overrides.get("local_execution") or _mageflow_testing_config.get(
        "local_execution", False
    )
    task_defs = {}
    if client_path:
        real_client = _load_client(client_path)
        task_defs = real_client._task_defs
        await MageflowTaskDefinition.ainsert(*task_defs)
        for task_def in task_defs:
            task_defs[task_def.task_name] = task_def

    adapter = TestClientAdapter(task_defs=task_defs, local_execution=local_execution)

    original_adapter = Signature.ClientAdapter
    Signature.ClientAdapter = adapter
    try:
        yield adapter
    finally:
        Signature.ClientAdapter = original_adapter
