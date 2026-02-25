from mcp.server.fastmcp import FastMCP

from mageflow_mcp.tools.containers import get_container_summary, list_sub_tasks
from mageflow_mcp.tools.logs import get_logs
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
    mcp.add_tool(get_signature)
    mcp.add_tool(list_signatures)
    mcp.add_tool(list_registered_tasks)
    mcp.add_tool(get_container_summary)
    mcp.add_tool(list_sub_tasks)
    mcp.add_tool(get_logs)
