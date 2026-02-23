"""Signature read tools for the mageflow MCP server."""
from __future__ import annotations

import math
from datetime import datetime

import rapyer
from rapyer.errors.base import KeyNotFound
from thirdmagic.chain.model import ChainTaskSignature
from thirdmagic.signature.status import SignatureStatus
from thirdmagic.swarm.model import SwarmTaskSignature
from thirdmagic.task.model import TaskSignature

from mageflow_mcp.models import PaginatedSignatureList, SignatureInfo

PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 50
MAX_FETCH = 200


async def get_signature(signature_id: str) -> SignatureInfo | dict:
    """Retrieve a single task signature by its Redis key.

    Returns curated signature details including type, status, task_name,
    kwargs, creation_time, return_value, and worker_task_id (if applicable).
    Returns a structured error dict if the key is not found or Redis is unavailable.

    Args:
        signature_id: The full Redis key for the signature,
            e.g. 'TaskSignature:abc-123'.
    """
    try:
        sig = await rapyer.aget(signature_id)
    except KeyNotFound:
        return {
            "error": "key_not_found",
            "message": f"Signature '{signature_id}' does not exist or has expired.",
            "suggestion": "Use list_signatures to browse available signature IDs.",
        }
    except Exception:
        return {
            "error": "redis_error",
            "message": "Could not retrieve signature from Redis.",
            "suggestion": "Verify that the MCP server started successfully with a valid REDIS_URL.",
        }
    return SignatureInfo(
        key=sig.key,
        signature_type=type(sig).__name__,
        task_name=sig.task_name,
        status=sig.task_status.status,
        creation_time=sig.creation_time,
        kwargs=dict(sig.kwargs),
        return_value=dict(sig.kwargs).get(sig.return_field_name)
        if hasattr(sig, "return_field_name")
        else None,
        worker_task_id=sig.worker_task_id
        if hasattr(sig, "worker_task_id") and sig.worker_task_id
        else None,
    )


async def list_signatures(
    status: SignatureStatus | None = None,
    task_name: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> PaginatedSignatureList | dict:
    """List task signatures with optional filters and pagination.

    Fetches TaskSignature, ChainTaskSignature, and SwarmTaskSignature records
    from Redis, applies Python-side filtering, sorts by creation_time descending
    (most recent first), and returns a paginated result set.

    Args:
        status: Filter by signature status (pending, active, done, failed,
            suspended, interrupted, canceled). Omit to return all statuses.
        task_name: Filter by exact task name. Omit for all task names.
        created_after: Include only signatures created after this timestamp
            (ISO 8601). Omit for no lower bound.
        created_before: Include only signatures created before this timestamp
            (ISO 8601). Omit for no upper bound.
        page: Page number (1-based, default 1).
        page_size: Number of results per page (default 20, maximum 50).
    """
    effective_page_size = min(page_size, PAGE_SIZE_MAX)
    try:
        tasks = await TaskSignature.afind(max_results=MAX_FETCH)
        chains = await ChainTaskSignature.afind(max_results=MAX_FETCH)
        swarms = await SwarmTaskSignature.afind(max_results=MAX_FETCH)
    except Exception:
        return {
            "error": "redis_error",
            "message": "Could not retrieve signatures from Redis.",
            "suggestion": "Verify that the MCP server started successfully with a valid REDIS_URL.",
        }

    all_sigs = list(tasks) + list(chains) + list(swarms)

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
        items=[
            SignatureInfo(
                key=s.key,
                signature_type=type(s).__name__,
                task_name=s.task_name,
                status=s.task_status.status,
                creation_time=s.creation_time,
                kwargs=dict(s.kwargs),
                return_value=dict(s.kwargs).get(s.return_field_name)
                if hasattr(s, "return_field_name")
                else None,
                worker_task_id=s.worker_task_id
                if hasattr(s, "worker_task_id") and s.worker_task_id
                else None,
            )
            for s in page_sigs
        ],
        total_count=total,
        page=page,
        page_size=effective_page_size,
        total_pages=math.ceil(total / effective_page_size) if total > 0 else 1,
    )
