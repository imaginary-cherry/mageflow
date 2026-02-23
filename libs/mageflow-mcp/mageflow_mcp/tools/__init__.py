"""Tool registration for the mageflow MCP server."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mageflow_mcp.tools.containers import get_container_summary, list_sub_tasks
from mageflow_mcp.tools.registry import list_registered_tasks
from mageflow_mcp.tools.signatures import (
    MAX_FETCH,
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    get_signature,
    list_signatures,
)

__all__ = [
    "register_tools",
    "PAGE_SIZE_DEFAULT",
    "PAGE_SIZE_MAX",
    "MAX_FETCH",
]


def register_tools(mcp: FastMCP) -> None:
    """Register all MCP tools onto the given FastMCP server instance.

    Args:
        mcp: The FastMCP server instance to register tools on.
    """
    mcp.add_tool(get_signature)
    mcp.add_tool(list_signatures)
    mcp.add_tool(list_registered_tasks)
    mcp.add_tool(get_container_summary)
    mcp.add_tool(list_sub_tasks)
