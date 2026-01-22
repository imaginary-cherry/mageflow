from unittest.mock import MagicMock, patch

import pytest
from hatchet_sdk import Context
from rapyer.types import RedisInt


@pytest.fixture
def mock_context():
    ctx = MagicMock(spec=Context)
    ctx.log = MagicMock()
    ctx.additional_metadata = {}
    return ctx


@pytest.fixture
def mock_redis_int_increase_error():
    with patch.object(
        RedisInt, "increase", side_effect=RuntimeError("Redis error")
    ) as mock_increase:
        yield mock_increase
