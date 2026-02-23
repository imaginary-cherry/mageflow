"""Registry read tools for the mageflow MCP server."""
from __future__ import annotations

import math

from thirdmagic.task_def import MageflowTaskDefinition

from mageflow_mcp.models import PaginatedTaskDefinitionList, TaskDefinitionInfo
from mageflow_mcp.tools.signatures import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX


async def list_registered_tasks(
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> PaginatedTaskDefinitionList | dict:
    """List all registered MageflowTaskDefinition entries from the Redis registry.

    Returns paginated results with task name, type, and retry configuration.

    Args:
        page: Page number (1-based).
        page_size: Results per page (max 50, default 20).
    """
    effective_page_size = min(page_size, PAGE_SIZE_MAX)

    try:
        all_defs = await MageflowTaskDefinition.afind()
    except Exception:
        return {
            "error": "redis_error",
            "message": "Could not retrieve task definitions from Redis.",
            "suggestion": "Verify that the MCP server started successfully with a valid REDIS_URL.",
        }

    all_defs = list(all_defs)
    total = len(all_defs)
    start = (page - 1) * effective_page_size
    page_defs = all_defs[start : start + effective_page_size]

    return PaginatedTaskDefinitionList(
        items=[
            TaskDefinitionInfo(
                mageflow_task_name=d.mageflow_task_name,
                task_name=d.task_name,
                retries=d.retries,
            )
            for d in page_defs
        ],
        total_count=total,
        page=page,
        page_size=effective_page_size,
        total_pages=max(math.ceil(total / effective_page_size) if total > 0 else 1, 1),
    )
