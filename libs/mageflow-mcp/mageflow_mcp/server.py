import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict

import rapyer
from mcp.server.fastmcp import FastMCP
from redis.asyncio import Redis

from mageflow_mcp.adapters.base import BaseMCPAdapter
from mageflow_mcp.tools import register_tools

logger = logging.getLogger(__name__)


class LifespanContext(TypedDict, total=False):
    adapter: BaseMCPAdapter | None


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[LifespanContext]:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = Redis.from_url(redis_url, decode_responses=True)
    await redis_client.ping()
    await rapyer.init_rapyer(redis_client, prefer_normal_json_dump=True)

    adapter: BaseMCPAdapter | None = None
    try:
        from hatchet_sdk import Hatchet

        from mageflow_mcp.adapters.hatchet import HatchetMCPAdapter

        hatchet = Hatchet()
        adapter = HatchetMCPAdapter(hatchet)
    except Exception:
        logger.warning(
            "Could not initialise HatchetMCPAdapter — get_logs tool will return "
            "an error. Ensure HATCHET_CLIENT_TOKEN is set. Phase 2 tools are unaffected."
        )

    yield LifespanContext(adapter=adapter)
    await rapyer.teardown_rapyer()


def create_server(server_name: str = "mageflow-mcp") -> FastMCP:
    mcp = FastMCP(name=server_name, lifespan=lifespan)
    register_tools(mcp)
    return mcp


def main() -> None:
    """CLI entry point: create the server and run it over stdio transport."""
    mcp = create_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
