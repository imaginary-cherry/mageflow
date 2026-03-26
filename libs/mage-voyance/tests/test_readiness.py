"""Tests for READY signal emission during lifespan."""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio


@pytest.mark.asyncio
async def test_ready_printed_after_init():
    """Capture stdout during lifespan startup, verify READY printed with flush."""
    from visualizer.server import lifespan
    from fastapi import FastAPI

    app = FastAPI()
    app.state.secrets = {"redisUrl": "redis://localhost:6379", "hatchetApiKey": ""}

    mock_redis = AsyncMock()
    mock_redis.close = AsyncMock()

    with patch("visualizer.server.Redis") as MockRedis, \
         patch("visualizer.server.rapyer") as mock_rapyer, \
         patch("builtins.print") as mock_print:
        MockRedis.from_url.return_value = mock_redis
        mock_rapyer.init_rapyer = AsyncMock()
        mock_rapyer.teardown_rapyer = AsyncMock()

        async with lifespan(app):
            pass

        mock_print.assert_any_call("READY", flush=True)
