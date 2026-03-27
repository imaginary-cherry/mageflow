"""Tests for lifespan startup — rapyer.init_rapyer called with Redis client."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from visualizer.server import lifespan


@pytest.mark.asyncio
async def test_rapyer_initialized_during_lifespan():
    """Verify rapyer.init_rapyer is called during lifespan startup."""

    app = FastAPI()
    app.state.secrets = {"redisUrl": "redis://localhost:6379", "hatchetApiKey": ""}

    mock_redis = AsyncMock()
    mock_redis.close = AsyncMock()

    with patch("visualizer.server.Redis") as MockRedis, patch(
        "visualizer.server.rapyer"
    ) as mock_rapyer:
        MockRedis.from_url.return_value = mock_redis
        mock_rapyer.init_rapyer = AsyncMock()
        mock_rapyer.teardown_rapyer = AsyncMock()

        async with lifespan(app):
            pass

        mock_rapyer.init_rapyer.assert_called_once_with(
            mock_redis, prefer_normal_json_dump=True
        )
        mock_rapyer.teardown_rapyer.assert_called_once()
