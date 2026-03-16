import pytest_asyncio
from thirdmagic.signature import Signature

from mageflow.testing._adapter import TestClientAdapter
from mageflow.testing._redis import (
    _mageflow_flush_redis,
    _mageflow_init_rapyer,
    _mageflow_redis_client,
    _mageflow_redis_container,
)

# Re-export private fixtures so pytest discovers them in this conftest scope.
# These names must be present at module level for pytest fixture discovery.
__all__ = [
    "_mageflow_redis_container",
    "_mageflow_redis_client",
    "_mageflow_flush_redis",
    "_mageflow_init_rapyer",
]


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def test_adapter(_mageflow_init_rapyer):
    """Fresh TestClientAdapter per test, wired as the global Signature.ClientAdapter."""
    adapter = TestClientAdapter()
    original = Signature.ClientAdapter
    Signature.ClientAdapter = adapter
    yield adapter
    Signature.ClientAdapter = original
