"""FastMCP server factory, lifespan hook, and CLI entry point for mageflow-mcp."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import rapyer
from mcp.server.fastmcp import FastMCP
from redis.asyncio import Redis

from mageflow_mcp.adapters.base import BaseMCPAdapter
from mageflow_mcp.tools import register_tools


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Initialise Redis and Rapyer before serving, tear down after.

    Reads REDIS_URL from the environment (default: redis://localhost:6379).
    The Redis client is created inside the async context to avoid event-loop
    mismatch issues that occur when it is instantiated at module import time.
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = Redis.from_url(redis_url, decode_responses=True)
    await redis_client.ping()
    await rapyer.init_rapyer(redis_client, prefer_normal_json_dump=True)
    yield
    await rapyer.teardown_rapyer()


def create_server(
    server_name: str = "mageflow-mcp",
    adapter: BaseMCPAdapter | None = None,
) -> FastMCP:
    """Create and return a configured FastMCP instance with all tools registered.

    Args:
        server_name: Display name registered with the MCP client.
        adapter: Optional backend adapter for log retrieval. Tools may receive
                 the adapter via the MCP context in future phases.

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
