import pytest

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
