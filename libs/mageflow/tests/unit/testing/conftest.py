import pytest_asyncio

pytest_plugins = ["mageflow.testing.plugin"]


@pytest_asyncio.fixture(autouse=True, scope="function")
async def redis_client():
    """Override parent autouse redis_client to prevent conflict with plugin's redis."""
    yield None


@pytest_asyncio.fixture(autouse=True, scope="function")
async def init_models():
    """Override parent autouse init_models to prevent conflict with plugin's rapyer init."""
    yield None
