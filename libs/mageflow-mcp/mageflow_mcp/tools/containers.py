import math
from typing import cast

import rapyer
from rapyer.errors import RapyerError
from rapyer.errors.base import KeyNotFound
from thirdmagic.container import ContainerTaskSignature
from thirdmagic.signature import Signature
from thirdmagic.signature.status import SignatureStatus

from mageflow_mcp.models import (
    ContainerSummary,
    ErrorResponse,
    PaginatedSubTaskList,
    SubTaskInfo,
)
from mageflow_mcp.tools.signatures import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX


async def get_container_summary(container_id: str) -> ContainerSummary | ErrorResponse:
    """
    Get a summary of sub-task counts by status for a chain or swarm container.

    Fetches the container signature from Redis, retrieves all sub-task signatures
    in bulk, and returns a breakdown of sub-task counts by status (pending, active,
    done, failed, suspended, canceled).

    Returns a structured ErrorResponse if the key is not found, the key refers to a
    non-container signature, or Redis is unavailable.
    """
    try:
        container = await rapyer.aget(container_id)
        container = cast(ContainerTaskSignature, container)
    except KeyNotFound:
        return ErrorResponse(
            error="key_not_found",
            message=f"Container '{container_id}' does not exist or has expired.",
            suggestion=(
                "Use list_signatures to find valid container IDs "
                "(look for ChainTaskSignature or SwarmTaskSignature types)."
            ),
        )
    except RapyerError:
        return ErrorResponse(
            error="redis_error",
            message="Could not retrieve container from Redis.",
            suggestion=(
                "Verify that the MCP server started successfully with a valid REDIS_URL."
            ),
        )

    if not isinstance(container, ContainerTaskSignature):
        return ErrorResponse(
            error="not_a_container",
            message=(
                f"'{container_id}' is a {type(container).__name__}, "
                "not a container (chain/swarm)."
            ),
            suggestion="Use get_signature instead for non-container task signatures.",
        )

    task_keys = list(container.task_ids)
    sub_tasks = await rapyer.afind(*task_keys, skip_missing=True) if task_keys else []
    sub_tasks = cast(list[Signature], sub_tasks)

    counts = {s: 0 for s in SignatureStatus}
    for t in sub_tasks:
        counts[t.task_status.status] += 1

    return ContainerSummary(
        container_key=container.key,
        signature_type=type(container).__name__,
        total=len(task_keys),
        pending=counts[SignatureStatus.PENDING],
        active=counts[SignatureStatus.ACTIVE],
        done=counts[SignatureStatus.DONE],
        failed=counts[SignatureStatus.FAILED],
        suspended=counts[SignatureStatus.SUSPENDED],
        canceled=counts[SignatureStatus.CANCELED],
    )


async def list_sub_tasks(
    container_id: str,
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
    status: SignatureStatus | None = None,
) -> PaginatedSubTaskList | ErrorResponse:
    """
    List sub-tasks of a chain or swarm container with optional filtering and pagination.

    When no status filter is provided, paginates the sub-task key list directly
    (efficient — avoids loading all sub-tasks). When a status filter is provided,
    all sub-tasks must be loaded to apply the filter before pagination.

    Returns a structured ErrorResponse if the container key is not found, refers to a
    non-container signature, or Redis is unavailable.
    """
    effective_page_size = min(page_size, PAGE_SIZE_MAX)

    try:
        container = await rapyer.aget(container_id)
    except KeyNotFound:
        return ErrorResponse(
            error="key_not_found",
            message=f"Container '{container_id}' does not exist or has expired.",
            suggestion=(
                "Use list_signatures to find valid container IDs "
                "(look for ChainTaskSignature or SwarmTaskSignature types)."
            ),
        )
    except RapyerError:
        return ErrorResponse(
            error="redis_error",
            message="Could not retrieve container from Redis.",
            suggestion=(
                "Verify that the MCP server started successfully with a valid REDIS_URL."
            ),
        )

    if not isinstance(container, ContainerTaskSignature):
        return ErrorResponse(
            error="not_a_container",
            message=(
                f"'{container_id}' is a {type(container).__name__}, "
                "not a container (chain/swarm)."
            ),
            suggestion="Use get_signature instead for non-container task signatures.",
        )

    all_keys = list(container.task_ids)

    # TODO - add server side filtering (no Redis indexes available on thirdmagic models)
    if status is not None:
        # Must load all sub-tasks to apply status filter
        all_subs = await rapyer.afind(*all_keys, skip_missing=True) if all_keys else []
        all_subs = cast(list[Signature], all_subs)
        filtered = [t for t in all_subs if t.task_status.status == status]
        total = len(filtered)
        start = (page - 1) * effective_page_size
        page_items_raw = filtered[start : start + effective_page_size]
    else:
        # Efficient key-based pagination: only fetch the current page of keys
        total = len(all_keys)
        start = (page - 1) * effective_page_size
        page_keys = all_keys[start : start + effective_page_size]
        page_items_raw = (
            await rapyer.afind(*page_keys, skip_missing=True) if page_keys else []
        )

    items = [
        SubTaskInfo(
            key=t.key,
            task_name=t.task_name,
            status=t.task_status.status,
        )
        for t in page_items_raw
    ]

    return PaginatedSubTaskList(
        items=items,
        total_count=total,
        page=page,
        page_size=effective_page_size,
        total_pages=max(math.ceil(total / effective_page_size), 1),
    )
