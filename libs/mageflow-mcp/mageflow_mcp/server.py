"""FastMCP server factory, lifespan hook, and CLI entry point for mageflow-mcp."""
from __future__ import annotations

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
    """Initialise Redis, Rapyer, and the Hatchet adapter before serving.

    Reads REDIS_URL from the environment (default: redis://localhost:6379).
    Reads HATCHET_CLIENT_TOKEN from the environment for HatchetMCPAdapter.

    The Redis client is created inside the async context to avoid event-loop
    mismatch issues that occur when it is instantiated at module import time.

    If HATCHET_CLIENT_TOKEN is missing or invalid, the adapter is set to None
    and a warning is logged. Phase 2 tools (Redis-only) remain fully functional.
    The get_logs tool will return an ErrorResponse when the adapter is None.
    """
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

    yield {"adapter": adapter}
    await rapyer.teardown_rapyer()


def create_server(
    server_name: str = "mageflow-mcp",
    adapter: BaseMCPAdapter | None = None,
) -> FastMCP:
    """Create and return a configured FastMCP instance with all tools registered.

    Args:
        server_name: Display name registered with the MCP client.
        adapter: Optional backend adapter for log retrieval. When provided,
                 it is used for testing purposes. In production, the adapter
                 is created inside the lifespan hook from HATCHET_CLIENT_TOKEN.

    Returns:
        A FastMCP instance with the lifespan hook wired and all read tools
        registered via register_tools().
    """
    mcp = FastMCP(name=server_name, lifespan=lifespan)
    register_tools(mcp)
    return mcp


def main() -> None:
    """CLI entry point: create the server and run it over stdio transport."""
    mcp = create_server()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
