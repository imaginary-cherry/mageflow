import pytest
import pytest_asyncio


def pytest_configure(config):
    """Register the mageflow testing plugin if not already loaded via entry-point."""
    if not config.pluginmanager.has_plugin("mageflow"):
        import mageflow.testing.plugin

        config.pluginmanager.register(mageflow.testing.plugin, "mageflow")


@pytest_asyncio.fixture(autouse=True, scope="function")
async def redis_client():
    """Override parent autouse redis_client to prevent conflict with plugin's redis."""
    yield None


@pytest_asyncio.fixture(autouse=True, scope="function")
async def init_models():
    """Override parent autouse init_models to prevent conflict with plugin's rapyer init."""
    yield None
