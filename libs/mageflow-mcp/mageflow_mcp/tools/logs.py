"""Log retrieval tool for the mageflow MCP server."""
from __future__ import annotations

import math

import rapyer
from hatchet_sdk.clients.rest.exceptions import (
    ForbiddenException,
    ServiceException,
    UnauthorizedException,
)
from mcp.server.fastmcp import Context
from rapyer.errors.base import KeyNotFound
from thirdmagic.container import ContainerTaskSignature

from mageflow_mcp.models import ErrorResponse, LogEntry, LogsResponse
from mageflow_mcp.tools.signatures import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX

_TERMINAL_STATUSES = {"COMPLETED", "CANCELLED", "FAILED"}
_VALID_LEVELS = {"debug", "info", "warn", "error"}


async def get_logs(
    signature_id: str,
    ctx: Context,
    level: str | None = None,
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> LogsResponse | ErrorResponse:
    """Retrieve execution log lines for a dispatched task signature.

    Fetches logs from the Hatchet API for the workflow run associated with
    the given signature's worker_task_id. Returns paginated log entries with
    an is_complete flag indicating whether the run has finished.

    For container signatures (chains/swarms), logs are grouped by sub-task
    with separator entries. Each sub-task's logs are fetched individually.

    Args:
        signature_id: The Redis key of the signature, e.g. 'TaskSignature:abc-123'
            or 'ChainTaskSignature:abc-123'.
        level: Filter by log level. One of: debug, info, warn, error. Omit for all levels.
        page: Page number (1-based, default 1).
        page_size: Number of log lines per page (default 20, maximum 50).
    """
    # Step 0 — Get adapter from context
    adapter = ctx.request_context.lifespan_context.get("adapter")
    if adapter is None:
        return ErrorResponse(
            error="adapter_not_configured",
            message="The Hatchet adapter is not configured. The get_logs tool requires a valid HATCHET_CLIENT_TOKEN.",
            suggestion="Set the HATCHET_CLIENT_TOKEN environment variable and restart the MCP server.",
        )
    effective_page_size = min(page_size, PAGE_SIZE_MAX)

    # Step 1 — Resolve signature from Redis
    try:
        sig = await rapyer.aget(signature_id)
    except KeyNotFound:
        return ErrorResponse(
            error="key_not_found",
            message=f"Signature '{signature_id}' does not exist or has expired.",
            suggestion="Use list_signatures to browse available signature IDs.",
        )
    except Exception:
        return ErrorResponse(
            error="redis_error",
            message="Could not retrieve signature from Redis.",
            suggestion="Verify that the MCP server started successfully with a valid REDIS_URL.",
        )

    # Step 2 — Handle container vs simple task
    if isinstance(sig, ContainerTaskSignature):
        task_keys = list(sig.task_ids)
        sub_tasks = await rapyer.afind(*task_keys, skip_missing=True) if task_keys else []

        all_logs: list[LogEntry] = []
        dispatched_worker_task_id = ""
        container_is_complete = True

        for sub_task in sub_tasks:
            sub_worker_task_id = getattr(sub_task, "worker_task_id", None)
            status_str = sub_task.task_status.status.value if hasattr(sub_task.task_status, "status") else str(sub_task.task_status.status)

            if sub_worker_task_id:
                if not dispatched_worker_task_id:
                    dispatched_worker_task_id = sub_worker_task_id

                # Separator entry
                all_logs.append(
                    LogEntry(
                        line=f"--- Sub-task: {sub_task.key} (status: {status_str}) ---",
                        sub_task_id=sub_task.key,
                    )
                )

                # Fetch logs for this sub-task
                try:
                    sub_logs = await adapter.get_logs(sub_worker_task_id)
                except (UnauthorizedException, ForbiddenException):
                    return ErrorResponse(
                        error="auth_failure",
                        message="Hatchet API rejected the request due to an authentication or authorization error.",
                        suggestion="Verify that HATCHET_CLIENT_TOKEN is set correctly in the server environment.",
                    )
                except ServiceException:
                    return ErrorResponse(
                        error="hatchet_unavailable",
                        message="Hatchet API is unreachable or returned a server error.",
                        suggestion="Check Hatchet service health and retry shortly.",
                    )
                except Exception:
                    return ErrorResponse(
                        error="unexpected_error",
                        message="An unexpected error occurred while fetching logs from Hatchet.",
                        suggestion="Check the server logs for details.",
                    )

                for entry in sub_logs:
                    all_logs.append(
                        LogEntry(
                            line=entry.line,
                            timestamp=entry.timestamp,
                            level=entry.level,
                            sub_task_id=sub_task.key,
                        )
                    )

                # Check run status for is_complete
                try:
                    run_status = await adapter.get_run_status(sub_worker_task_id)
                    if run_status not in _TERMINAL_STATUSES:
                        container_is_complete = False
                except Exception:
                    container_is_complete = False
            else:
                # Sub-task not dispatched yet
                all_logs.append(
                    LogEntry(
                        line=f"--- Sub-task: {sub_task.key} — not dispatched (no logs) ---",
                        sub_task_id=sub_task.key,
                    )
                )
                container_is_complete = False

        # If no sub-tasks were dispatched, is_complete should be False
        if not dispatched_worker_task_id:
            container_is_complete = False

        worker_task_id = dispatched_worker_task_id
        is_complete = container_is_complete

    else:
        # Simple task: check worker_task_id (ERR-02)
        worker_task_id = getattr(sig, "worker_task_id", None)
        if not worker_task_id:
            return ErrorResponse(
                error="task_not_dispatched",
                message=f"Signature '{signature_id}' has no worker_task_id. The task has not been dispatched to Hatchet yet.",
                suggestion="Wait for the task to be dispatched, then call get_logs again.",
            )

        # Step 3 — Fetch logs from adapter
        try:
            all_logs = await adapter.get_logs(worker_task_id)
        except (UnauthorizedException, ForbiddenException):
            return ErrorResponse(
                error="auth_failure",
                message="Hatchet API rejected the request due to an authentication or authorization error.",
                suggestion="Verify that HATCHET_CLIENT_TOKEN is set correctly in the server environment.",
            )
        except ServiceException:
            return ErrorResponse(
                error="hatchet_unavailable",
                message="Hatchet API is unreachable or returned a server error.",
                suggestion="Check Hatchet service health and retry shortly.",
            )
        except Exception:
            return ErrorResponse(
                error="unexpected_error",
                message="An unexpected error occurred while fetching logs from Hatchet.",
                suggestion="Check the server logs for details.",
            )

        # Step 6 — Determine is_complete (simple task)
        is_complete = False
        try:
            run_status = await adapter.get_run_status(worker_task_id)
            is_complete = run_status in _TERMINAL_STATUSES
        except Exception:
            pass  # is_complete stays False — non-fatal

    # Step 4 — Apply level filter (Python-side)
    if level is not None:
        normalized = level.lower()
        if normalized == "warning":
            normalized = "warn"
        if normalized not in _VALID_LEVELS:
            return ErrorResponse(
                error="invalid_filter",
                message=f"Unknown log level '{level}'. Valid values: debug, info, warn, error.",
                suggestion="Use one of: debug, info, warn, error.",
            )
        all_logs = [e for e in all_logs if (e.level or "").lower() == normalized]

    # Step 5 — Paginate
    total = len(all_logs)
    start = (page - 1) * effective_page_size
    page_logs = all_logs[start : start + effective_page_size]

    return LogsResponse(
        items=page_logs,
        total_count=total,
        page=page,
        page_size=effective_page_size,
        total_pages=math.ceil(total / effective_page_size) if total > 0 else 1,
        is_complete=is_complete,
        worker_task_id=worker_task_id,
    )
