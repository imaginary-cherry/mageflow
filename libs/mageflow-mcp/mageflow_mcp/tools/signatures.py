import math
from datetime import datetime
from typing import cast

import rapyer
from rapyer.errors.base import KeyNotFound, RapyerError
from thirdmagic.chain.model import ChainTaskSignature
from thirdmagic.signature import Signature
from thirdmagic.signature.status import SignatureStatus
from thirdmagic.swarm.model import SwarmTaskSignature
from thirdmagic.task.model import TaskSignature

from mageflow_mcp.models import ErrorResponse, PaginatedSignatureList, SignatureInfo

PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 50
MAX_FETCH = 200


async def get_signature(signature_id: str) -> SignatureInfo | ErrorResponse:
    """
    Retrieve a single task signature by its Redis key.

    Returns curated signature details including type, status, task_name,
    kwargs, creation_time, return_value, and worker_task_id (if applicable).
    Returns a structured ErrorResponse if the key is not found or Redis is unavailable.
    """
    try:
        sig = await rapyer.aget(signature_id)
        sig = cast(Signature, sig)
    except KeyNotFound:
        return ErrorResponse(
            error="key_not_found",
            message=f"Signature '{signature_id}' does not exist or has expired.",
            suggestion="Use list_signatures to browse available signature IDs.",
        )
    except RapyerError:
        return ErrorResponse(
            error="redis_error",
            message="Could not retrieve signature from Redis.",
            suggestion="Verify that the MCP server started successfully with a valid REDIS_URL.",
        )
    return SignatureInfo.from_sig(sig)


async def list_signatures(
    status: SignatureStatus | None = None,
    task_name: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> PaginatedSignatureList | ErrorResponse:
    """
    List task signatures with optional filters and pagination.

    Fetches TaskSignature, ChainTaskSignature, and SwarmTaskSignature records
    from Redis, applies Python-side filtering, sorts by creation_time descending
    (most recent first), and returns a paginated result set.
    """
    effective_page_size = min(page_size, PAGE_SIZE_MAX)
    try:
        tasks = await TaskSignature.afind(max_results=MAX_FETCH)
        chains = await ChainTaskSignature.afind(max_results=MAX_FETCH)
        swarms = await SwarmTaskSignature.afind(max_results=MAX_FETCH)
    except RapyerError as e:
        return ErrorResponse(
            error="redis_error",
            message=f"Could not retrieve signatures from Redis. {e}",
            suggestion="Verify that the MCP server started successfully with a valid REDIS_URL.",
        )

    all_sigs = list(tasks) + list(chains) + list(swarms)

    # TODO - add server side filtering
    # Apply Python-side filters (no Redis indexes available on thirdmagic models)
    if status is not None:
        all_sigs = [s for s in all_sigs if s.task_status.status == status]
    if task_name is not None:
        all_sigs = [s for s in all_sigs if s.task_name == task_name]
    if created_after is not None:
        all_sigs = [s for s in all_sigs if s.creation_time >= created_after]
    if created_before is not None:
        all_sigs = [s for s in all_sigs if s.creation_time <= created_before]

    # Sort most-recent first
    all_sigs.sort(key=lambda s: s.creation_time, reverse=True)

    total = len(all_sigs)
    start = (page - 1) * effective_page_size
    page_sigs = all_sigs[start : start + effective_page_size]

    return PaginatedSignatureList(
        items=[SignatureInfo.from_sig(s) for s in page_sigs],
        total_count=total,
        page=page,
        page_size=effective_page_size,
        total_pages=math.ceil(total / effective_page_size) if total > 0 else 1,
    )
