"""Shared fixtures for mageflow-mcp unit tests.

Provides fakeredis + rapyer fixtures for tool-level tests that need
Redis-backed data retrieval. All fixtures are autouse and function-scoped
to ensure test isolation.
"""

from __future__ import annotations

import fakeredis
import pytest_asyncio
import rapyer


@pytest_asyncio.fixture(autouse=True, scope="function")
async def redis_client():
    """Provide a clean FakeRedis client for each test function."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await client.flushall()
    try:
        yield client
    finally:
        await client.flushall()
        await client.aclose()


@pytest_asyncio.fixture(autouse=True, scope="function")
async def init_models(redis_client):
    """Initialise rapyer with the fakeredis client before each test."""
    await rapyer.init_rapyer(redis_client, prefer_normal_json_dump=True)
