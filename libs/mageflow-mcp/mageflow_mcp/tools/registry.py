import math

from rapyer.errors import RapyerError
from thirdmagic.task_def import MageflowTaskDefinition

from mageflow_mcp.models import (
    ErrorResponse,
    PaginatedTaskDefinitionList,
    TaskDefinitionInfo,
)
from mageflow_mcp.tools.signatures import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX


async def list_registered_tasks(
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> PaginatedTaskDefinitionList | ErrorResponse:
    """
    List all registered MageflowTaskDefinition entries from the Redis registry.

    Returns paginated results with task name, type, and retry configuration.
    """
    effective_page_size = min(page_size, PAGE_SIZE_MAX)

    try:
        all_defs = await MageflowTaskDefinition.afind()
    except RapyerError:
        return ErrorResponse(
            error="redis_error",
            message="Could not retrieve task definitions from Redis.",
            suggestion="Verify that the MCP server started successfully with a valid REDIS_URL.",
        )

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
